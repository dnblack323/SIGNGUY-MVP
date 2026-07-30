"""EC14 - Webstores service layer."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Any, Optional

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.permissions import Perm, permissions_for_role
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.customer import Customer
from ..models.order import Order, OrderItem
from ..models.webstore import (
    WEBSTORE_LIFECYCLE_STATES,
    WEBSTORE_TYPES,
    Webstore,
    WebstoreAIUsageEvent,
    WebstoreActivity,
    WebstoreArtworkFile,
    WebstoreBuyerOrder,
    WebstoreLaunchPacket,
    WebstoreLedgerEntry,
    WebstoreMockup,
    WebstoreOwner,
    WebstoreProduct,
    WebstoreProductTemplate,
    WebstorePurchaseIntent,
    WebstoreQuestionnaireSubmission,
)
from ..repositories.webstores import WebstoreRepository
from .activity import record_activity_with_audit
from .entitlements import has_entitlement
from .portal_identity import create_portal_identity
from .sequence import next_number, next_record_number

WEBSTORES_FEATURE_KEY = "webstores"
LIVE_BLOCKING_STATUSES = {"closed", "archived"}
PRODUCT_PURCHASABLE_STATUSES = {"active"}
SLUG_RE = re.compile(r"[^a-z0-9]+")
PUBLIC_CHECKOUT_ENABLED = False
VALID_WEBSTORE_TYPES = set(WEBSTORE_TYPES)
VALID_WEBSTORE_STATUSES = set(WEBSTORE_LIFECYCLE_STATES)
WEBSTORE_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"questionnaire_sent", "waiting_on_store_owner", "questionnaire_submitted", "products_selected", "store_packet_generated", "archived"},
    "questionnaire_sent": {"waiting_on_store_owner", "questionnaire_submitted", "changes_requested", "archived"},
    "waiting_on_store_owner": {"questionnaire_submitted", "changes_requested", "archived"},
    "questionnaire_submitted": {"ai_setup_ready", "artwork_needs_review", "products_selected", "store_packet_generated", "archived"},
    "ai_setup_ready": {"ai_product_suggestions_ready", "artwork_needs_review", "products_selected", "archived"},
    "ai_product_suggestions_ready": {"artwork_needs_review", "products_selected", "archived"},
    "artwork_needs_review": {"mockups_generated", "products_selected", "archived"},
    "mockups_generated": {"mockups_approved", "changes_requested", "products_selected", "archived"},
    "mockups_approved": {"products_selected", "store_packet_generated", "archived"},
    "products_selected": {"store_packet_generated", "sent_for_approval", "archived"},
    "store_packet_generated": {"sent_for_approval", "changes_requested", "archived"},
    "sent_for_approval": {"approved", "changes_requested", "archived"},
    "changes_requested": {"questionnaire_submitted", "store_packet_generated", "sent_for_approval", "archived"},
    "approved": {"live", "archived"},
    "live": {"closing_soon", "closed", "in_production", "completed", "archived"},
    "closing_soon": {"closed", "archived"},
    "closed": {"relaunch_ready", "archived"},
    "in_production": {"completed", "closed", "archived"},
    "completed": {"relaunch_ready", "archived"},
    "relaunch_ready": {"approved", "live", "archived"},
    "archived": set(),
}

owners_repo = WebstoreRepository("webstore_owners")
stores_repo = WebstoreRepository("webstores")
templates_repo = WebstoreRepository("webstore_product_templates")
products_repo = WebstoreRepository("webstore_products")
submissions_repo = WebstoreRepository("webstore_questionnaire_submissions")
artwork_repo = WebstoreRepository("webstore_artwork_files")
mockups_repo = WebstoreRepository("webstore_mockups")
packets_repo = WebstoreRepository("webstore_launch_packets")
buyer_orders_repo = WebstoreRepository("webstore_buyer_orders")
ledger_repo = WebstoreRepository("webstore_ledger_entries")
activity_repo = WebstoreRepository("webstore_activity_events")
ai_repo = WebstoreRepository("webstore_ai_usage_events")


class WebstoreError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _now_iso() -> str:
    return utc_now().isoformat()


def _clean_text(value: Any, field: str, *, limit: int = 200) -> str:
    text = str(value or "").strip()
    if not text:
        raise WebstoreError(f"{field}_required", f"{field} is required", 400)
    if len(text) > limit:
        raise WebstoreError(f"{field}_too_long", f"{field} must be {limit} characters or fewer", 400)
    return text


def _clean_optional_text(value: Any, *, limit: int = 2000) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def _slug(value: str) -> str:
    text = SLUG_RE.sub("-", value.strip().lower()).strip("-")
    return text[:80] or "webstore"


def _normalize_store_type(value: Any) -> str:
    key = _slug(str(value or "general")).replace("-", "_")
    aliases = {"b_2_b": "b2b", "business_to_business": "b2b"}
    key = aliases.get(key, key)
    if key not in VALID_WEBSTORE_TYPES:
        raise WebstoreError("invalid_webstore_type", "Unsupported Webstore type", 400)
    return key


async def _public_slug_available(public_slug: str, *, existing_webstore_id: Optional[str] = None) -> bool:
    existing = await db.webstores.find_one({"public_slug": public_slug}, {"_id": 0, "id": 1})
    return not existing or existing.get("id") == existing_webstore_id


async def _generate_public_slug(*, tenant_id: str, shop_context: str, store_name: str, internal_slug: str) -> str:
    base = _slug(f"{shop_context}-{store_name}")[:72] or internal_slug
    candidate = base
    if await _public_slug_available(candidate):
        return candidate
    seed = _slug(f"{tenant_id}-{internal_slug}")[:72] or internal_slug
    candidate = seed
    if await _public_slug_available(candidate):
        return candidate
    for suffix in range(2, 1000):
        candidate = f"{seed[:72]}-{suffix}"
        if await _public_slug_available(candidate):
            return candidate
    raise WebstoreError("public_slug_unavailable", "Unable to allocate a public Webstore slug", 409)


async def _ensure_public_slug(store: dict) -> dict:
    if store.get("public_slug"):
        return store
    public_slug = await _generate_public_slug(
        tenant_id=store["tenant_id"],
        shop_context=store["tenant_id"],
        store_name=store.get("name") or store.get("slug") or store["id"],
        internal_slug=store.get("slug") or store["id"],
    )
    await db.webstores.update_one(
        {"tenant_id": store["tenant_id"], "id": store["id"], "public_slug": {"$exists": False}},
        {"$set": {"public_slug": public_slug, "public_url": f"/p/webstores/{public_slug}", "updated_at": _now_iso()}},
    )
    updated = await db.webstores.find_one({"tenant_id": store["tenant_id"], "id": store["id"]}, {"_id": 0})
    return serialize_doc(updated or {**store, "public_slug": public_slug, "public_url": f"/p/webstores/{public_slug}"})


def _validate_transition(current: str, requested: str) -> None:
    if requested not in VALID_WEBSTORE_STATUSES:
        raise WebstoreError("invalid_webstore_status", "Unsupported Webstore lifecycle status", 400)
    if requested == current:
        return
    allowed = WEBSTORE_TRANSITIONS.get(current, set())
    if requested not in allowed:
        raise WebstoreError("invalid_webstore_transition", f"Cannot move Webstore from {current} to {requested}", 409)


def _require_staff_perm(user: dict, perm: Perm) -> None:
    if perm.value not in set(permissions_for_role(user.get("role", "staff"))):
        raise WebstoreError("permission_denied", f"Missing permission: {perm.value}", 403)


async def _audit(
    *,
    tenant_id: str,
    webstore_id: str,
    actor_type: str,
    action: str,
    entity_type: str,
    entity_id: str,
    summary: str,
    actor_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    activity = WebstoreActivity(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        metadata=metadata or {},
    ).model_dump()
    await db.webstore_activity_events.insert_one(prepare_for_mongo(activity))
    await record_activity_with_audit(
        tenant_id=tenant_id,
        actor_user_id=actor_id or actor_type,
        actor_email=actor_email or actor_type,
        module="webstores",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        metadata={"webstore_id": webstore_id, **(metadata or {})},
    )


def _public_product(product: dict) -> dict:
    allowed = {
        "id",
        "webstore_id",
        "name",
        "description",
        "category",
        "product_type",
        "sku",
        "selling_price_cents",
        "currency",
        "variants",
        "personalization_enabled",
        "image_file_ids",
        "mockup_ids",
        "public",
        "featured",
        "status",
    }
    return {k: v for k, v in product.items() if k in allowed}


def _public_store(store: dict) -> dict:
    allowed = {
        "id",
        "name",
        "slug",
        "public_slug",
        "store_type",
        "status",
        "description",
        "branding",
        "deadline_at",
        "public_url",
        "checkout_enabled",
    }
    result = {k: v for k, v in store.items() if k in allowed}
    result["checkout_enabled"] = bool(result.get("checkout_enabled")) and PUBLIC_CHECKOUT_ENABLED
    result["checkout_unavailable_reason"] = "Real Webstore checkout is not connected yet." if not PUBLIC_CHECKOUT_ENABLED else None
    return result


def _portal_store(store: dict) -> dict:
    allowed = {
        "id",
        "name",
        "slug",
        "public_slug",
        "store_type",
        "status",
        "description",
        "branding",
        "deadline_at",
        "public_url",
        "checkout_enabled",
        "terms_fee_acknowledged",
        "owner_approved_at",
        "launch_packet_id",
        "setup_state",
        "setup_profile",
        "target_launch_at",
        "event_start_at",
        "event_location",
    }
    result = {k: v for k, v in store.items() if k in allowed}
    result["checkout_enabled"] = bool(result.get("checkout_enabled")) and PUBLIC_CHECKOUT_ENABLED
    result["checkout_unavailable_reason"] = "Real Webstore checkout is not connected yet."
    return result


def _portal_launch_packet(packet: Optional[dict]) -> Optional[dict]:
    if not packet:
        return None
    allowed = {
        "id",
        "webstore_id",
        "status",
        "snapshot",
        "pricing_summary",
        "promotion_copy",
        "qr_code_url",
        "share_url",
        "sent_at",
        "owner_decision_at",
        "change_request_reason",
    }
    return {k: v for k, v in packet.items() if k in allowed}


async def _get_store(tenant_id: str, webstore_id: str) -> dict:
    store = await stores_repo.get(tenant_id=tenant_id, entity_id=webstore_id)
    if not store:
        raise WebstoreError("webstore_not_found", "Webstore not found", 404)
    return store


async def _get_owner(tenant_id: str, owner_id: str) -> dict:
    owner = await owners_repo.get(tenant_id=tenant_id, entity_id=owner_id)
    if not owner:
        raise WebstoreError("webstore_owner_not_found", "Webstore owner not found", 404)
    return owner


async def _get_product(tenant_id: str, product_id: str, webstore_id: Optional[str] = None) -> dict:
    filt = {"tenant_id": tenant_id, "id": product_id}
    if webstore_id:
        filt["webstore_id"] = webstore_id
    product = await products_repo.find_one(filt)
    if not product:
        raise WebstoreError("webstore_product_not_found", "Webstore product not found", 404)
    return product


async def create_owner(user: dict, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    email = _clean_text(fields.get("email"), "email", limit=254).lower()
    owner = WebstoreOwner(
        tenant_id=user["tenant_id"],
        name=_clean_text(fields.get("name"), "name"),
        email=email,
        phone=_clean_optional_text(fields.get("phone"), limit=40),
        organization=_clean_optional_text(fields.get("organization")),
        customer_id=fields.get("customer_id"),
        status=fields.get("status", "active"),
    ).model_dump()
    try:
        await db.webstore_owners.insert_one(prepare_for_mongo(owner))
    except DuplicateKeyError:
        raise WebstoreError("duplicate_webstore_owner", "A Webstore owner already exists for that email", 409)
    if fields.get("create_portal_identity", True):
        try:
            identity = await create_portal_identity(
                tenant_id=user["tenant_id"],
                portal_type="webstore_owner",
                webstore_owner_id=owner["id"],
                email=email,
                full_name=owner["name"],
                phone=owner.get("phone"),
                role_label="Webstore Owner",
                permissions_preset="webstore_owner_admin",
                magic_link_only=True,
            )
            owner["portal_identity_id"] = identity["id"]
            await db.webstore_owners.update_one(
                {"tenant_id": user["tenant_id"], "id": owner["id"]},
                {"$set": {"portal_identity_id": identity["id"], "updated_at": _now_iso()}},
            )
        except ValueError as e:
            raise WebstoreError(str(e), "Unable to create Webstore owner portal identity", 409)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=owner["id"],
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.owner_created",
        entity_type="webstore_owner",
        entity_id=owner["id"],
        summary="Webstore owner created",
    )
    return serialize_doc(owner)  # type: ignore[return-value]


async def list_owners(user: dict) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    return await owners_repo.list(tenant_id=user["tenant_id"], sort=[("name", 1)])


async def create_webstore(user: dict, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    if fields.get("idempotency_key"):
        existing = await db.webstores.find_one(
            {"tenant_id": user["tenant_id"], "creation_idempotency_key": fields["idempotency_key"]},
            {"_id": 0},
        )
        if existing:
            return serialize_doc(existing)
    owner = await _get_owner(user["tenant_id"], fields["owner_id"])
    slug = _slug(fields.get("slug") or fields.get("name") or owner["name"])
    tenant = await db.tenants.find_one({"id": user["tenant_id"]}, {"_id": 0, "name": 1, "slug": 1})
    public_slug = await _generate_public_slug(
        tenant_id=user["tenant_id"],
        shop_context=(tenant or {}).get("slug") or (tenant or {}).get("name") or user["tenant_id"],
        store_name=fields.get("name") or owner["name"],
        internal_slug=slug,
    )
    store = Webstore(
        tenant_id=user["tenant_id"],
        owner_id=owner["id"],
        name=_clean_text(fields.get("name"), "name"),
        slug=slug,
        public_slug=public_slug,
        store_type=_normalize_store_type(fields.get("store_type", "general")),
        description=_clean_optional_text(fields.get("description")),
        branding=fields.get("branding") or {},
        direct_owner_payout_required=bool(fields.get("direct_owner_payout_required", False)),
        stripe_onboarding_required=bool(fields.get("stripe_onboarding_required", False)),
        stripe_payment_ready=False,
        deadline_at=fields.get("deadline_at"),
        target_launch_at=fields.get("target_launch_at"),
        event_start_at=fields.get("event_start_at"),
        event_location=fields.get("event_location"),
        setup_profile=fields.get("setup_profile") or {},
        setup_requirements=fields.get("setup_requirements") or {},
        creation_idempotency_key=fields.get("idempotency_key"),
        public_url=f"/p/webstores/{public_slug}",
    ).model_dump()
    try:
        await db.webstores.insert_one(prepare_for_mongo(store))
    except DuplicateKeyError:
        raise WebstoreError("duplicate_webstore_slug", "Webstore slug already exists for this tenant", 409)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=store["id"],
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.created",
        entity_type="webstore",
        entity_id=store["id"],
        summary="Webstore created",
    )
    from .webstore_setup import WebstoreSetupError, initialize_store_setup

    try:
        await initialize_store_setup(user, store, owner, fields)
    except WebstoreSetupError as exc:
        await db.webstores.delete_one({"tenant_id": user["tenant_id"], "id": store["id"]})
        await db.webstore_access_assignments.delete_many({"tenant_id": user["tenant_id"], "webstore_id": store["id"]})
        await db.webstore_invitations.delete_many({"tenant_id": user["tenant_id"], "webstore_id": store["id"]})
        await db.webstore_questionnaire_submissions.delete_many({"tenant_id": user["tenant_id"], "webstore_id": store["id"]})
        await db.webstore_setup_files.delete_many({"tenant_id": user["tenant_id"], "webstore_id": store["id"]})
        await db.webstore_answer_applications.delete_many({"tenant_id": user["tenant_id"], "webstore_id": store["id"]})
        raise WebstoreError(exc.code, exc.detail, exc.status_code) from exc
    updated = await db.webstores.find_one({"tenant_id": user["tenant_id"], "id": store["id"]}, {"_id": 0})
    if updated:
        store = serialize_doc(updated)
    return serialize_doc(store)  # type: ignore[return-value]


async def list_webstores(user: dict, *, status: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    filters = {"status": status} if status else {}
    return await stores_repo.list(tenant_id=user["tenant_id"], filters=filters, sort=[("updated_at", -1)])


async def get_webstore(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _ensure_public_slug(await _get_store(user["tenant_id"], webstore_id))
    products = await list_products(user, webstore_id=webstore_id)
    packets = await packets_repo.list(tenant_id=user["tenant_id"], filters={"webstore_id": webstore_id}, sort=[("created_at", -1)], limit=10)
    return {"webstore": store, "products": products["items"], "launch_packets": packets["items"]}


async def update_webstore(user: dict, webstore_id: str, updates: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store_before = await _get_store(user["tenant_id"], webstore_id)
    allowed = {
        k: v
        for k, v in updates.items()
        if k
        in {
            "name",
            "description",
            "branding",
            "store_type",
            "terms_fee_acknowledged",
            "direct_owner_payout_required",
            "stripe_onboarding_required",
            "deadline_at",
        }
    }
    if "name" in allowed:
        allowed["name"] = _clean_text(allowed["name"], "name")
    if "description" in allowed:
        allowed["description"] = _clean_optional_text(allowed["description"])
    if "store_type" in allowed:
        allowed["store_type"] = _normalize_store_type(allowed["store_type"])
        if allowed["store_type"] != store_before.get("store_type"):
            owner_activity_count = sum(
                [
                    await db.webstore_access_assignments.count_documents({"tenant_id": user["tenant_id"], "webstore_id": webstore_id}),
                    await db.webstore_invitations.count_documents({"tenant_id": user["tenant_id"], "webstore_id": webstore_id}),
                    await db.webstore_questionnaire_submissions.count_documents({"tenant_id": user["tenant_id"], "webstore_id": webstore_id}),
                    await db.webstore_setup_files.count_documents({"tenant_id": user["tenant_id"], "webstore_id": webstore_id}),
                ]
            )
            if owner_activity_count:
                _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
                if not updates.get("confirm_type_change") or not updates.get("impact_review_acknowledged") or not updates.get("type_change_reason"):
                    raise WebstoreError(
                        "webstore_type_change_confirmation_required",
                        "Changing Webstore type after owner/setup activity requires confirmation, impact review, and a reason.",
                        409,
                    )
                inactive_keys: set[str] = set()
                async for submission in db.webstore_questionnaire_submissions.find({"tenant_id": user["tenant_id"], "webstore_id": webstore_id}, {"_id": 0, "answers": 1, "submitted_snapshot": 1}):
                    inactive_keys.update((submission.get("answers") or {}).keys())
                    inactive_keys.update(((submission.get("submitted_snapshot") or {}).get("answers") or {}).keys())
                if inactive_keys:
                    await db.webstore_questionnaire_submissions.update_many(
                        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id},
                        {"$addToSet": {"inactive_answer_paths": {"$each": sorted(inactive_keys)}}, "$set": {"updated_at": _now_iso()}},
                    )
                history_entry = {
                    "from": store_before.get("store_type"),
                    "to": allowed["store_type"],
                    "reason": updates.get("type_change_reason"),
                    "actor_user_id": user.get("id"),
                    "actor_email": user.get("email"),
                    "changed_at": _now_iso(),
                }
                await db.webstores.update_one(
                    {"tenant_id": user["tenant_id"], "id": webstore_id},
                    {"$push": {"setup_profile.type_change_history": history_entry}},
                )
    if "name" in allowed and allowed["name"] != store_before.get("name"):
        public_slug = await _generate_public_slug(
            tenant_id=user["tenant_id"],
            shop_context=user["tenant_id"],
            store_name=allowed["name"],
            internal_slug=store_before.get("slug") or store_before["id"],
        )
        allowed["public_slug"] = public_slug
        allowed["public_url"] = f"/p/webstores/{public_slug}"
    if not allowed:
        raise WebstoreError("no_updates", "No supported updates provided", 400)
    store = await stores_repo.update(tenant_id=user["tenant_id"], entity_id=webstore_id, updates=allowed)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.updated",
        entity_type="webstore",
        entity_id=webstore_id,
        summary="Webstore updated",
        metadata={"fields": sorted(allowed)},
    )
    if "store_type" in allowed and allowed["store_type"] != store_before.get("store_type"):
        await _audit(
            tenant_id=user["tenant_id"],
            webstore_id=webstore_id,
            actor_type="staff",
            actor_id=user["id"],
            actor_email=user.get("email"),
            action="webstore.type_changed",
            entity_type="webstore",
            entity_id=webstore_id,
            summary=f"Webstore type changed from {store_before.get('store_type')} to {allowed['store_type']}",
            metadata={"from": store_before.get("store_type"), "to": allowed["store_type"], "reason": updates.get("type_change_reason")},
        )
    return store or {}


async def set_webstore_status(user: dict, webstore_id: str, status: str, reason: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE if status in {"live", "closed", "archived"} else Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    _validate_transition(store.get("status", "draft"), status)
    if status == "live":
        readiness = await launch_readiness(user, webstore_id)
        if not readiness["ready"]:
            raise WebstoreError("launch_gates_failed", "Webstore launch gates are not satisfied", 409)
    updates: dict[str, Any] = {"status": status}
    if status == "live":
        updates["launched_at"] = _now_iso()
        updates["checkout_enabled"] = True
    elif status == "closed":
        updates["closed_at"] = _now_iso()
        updates["checkout_enabled"] = False
    elif status == "archived":
        updates["archived_at"] = _now_iso()
        updates["checkout_enabled"] = False
    updated = await stores_repo.update(tenant_id=user["tenant_id"], entity_id=webstore_id, updates=updates)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action=f"webstore.status.{status}",
        entity_type="webstore",
        entity_id=webstore_id,
        summary=f"Webstore status changed from {store.get('status')} to {status}",
        metadata={"from": store.get("status"), "to": status, "reason": reason},
    )
    return updated or {}


async def create_template(user: dict, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    template = WebstoreProductTemplate(
        tenant_id=user["tenant_id"],
        template_name=_clean_text(fields.get("template_name"), "template_name"),
        product_category=_clean_text(fields.get("product_category"), "product_category"),
        product_type=_clean_text(fields.get("product_type"), "product_type"),
        default_description=_clean_optional_text(fields.get("default_description")),
        best_store_types=fields.get("best_store_types") or [],
        default_variants=fields.get("default_variants") or [],
        mockup_supported=bool(fields.get("mockup_supported", True)),
        suggested_production_cost_cents=int(fields.get("suggested_production_cost_cents", 0)),
        suggested_selling_price_cents=int(fields.get("suggested_selling_price_cents", 0)),
        suggested_store_owner_share_cents=int(fields.get("suggested_store_owner_share_cents", 0)),
        platform_fee_basis_points=int(fields.get("platform_fee_basis_points", 150)),
        internal_notes=_clean_optional_text(fields.get("internal_notes")),
        active=bool(fields.get("active", True)),
    ).model_dump()
    await db.webstore_product_templates.insert_one(prepare_for_mongo(template))
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=template["id"],
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.template_created",
        entity_type="webstore_product_template",
        entity_id=template["id"],
        summary="Webstore product template created",
    )
    return serialize_doc(template)  # type: ignore[return-value]


async def list_templates(user: dict, *, active: Optional[bool] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    filters = {"active": active} if active is not None else {}
    return await templates_repo.list(tenant_id=user["tenant_id"], filters=filters, sort=[("template_name", 1)])


async def create_product(user: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    await _get_store(user["tenant_id"], webstore_id)
    template = None
    if fields.get("source_template_id"):
        template = await templates_repo.get(tenant_id=user["tenant_id"], entity_id=fields["source_template_id"])
        if not template or not template.get("active"):
            raise WebstoreError("template_not_available", "Product template is not active", 409)
    merged = {
        "name": fields.get("name") or (template or {}).get("template_name"),
        "description": fields.get("description") or (template or {}).get("default_description"),
        "category": fields.get("category") or (template or {}).get("product_category"),
        "product_type": fields.get("product_type") or (template or {}).get("product_type"),
        "production_cost_cents": fields.get("production_cost_cents", (template or {}).get("suggested_production_cost_cents", 0)),
        "selling_price_cents": fields.get("selling_price_cents", (template or {}).get("suggested_selling_price_cents", 0)),
        "store_owner_share_cents": fields.get("store_owner_share_cents", (template or {}).get("suggested_store_owner_share_cents", 0)),
        "platform_fee_basis_points": fields.get("platform_fee_basis_points", (template or {}).get("platform_fee_basis_points", 150)),
        "variants": fields.get("variants", (template or {}).get("default_variants", [])),
    }
    product = WebstoreProduct(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        source_template_id=fields.get("source_template_id"),
        name=_clean_text(merged["name"], "name"),
        description=_clean_optional_text(merged.get("description")),
        category=merged.get("category"),
        product_type=merged.get("product_type"),
        sku=fields.get("sku"),
        production_cost_cents=int(merged["production_cost_cents"] or 0),
        selling_price_cents=int(merged["selling_price_cents"] or 0),
        store_owner_share_cents=int(merged["store_owner_share_cents"] or 0),
        platform_fee_basis_points=int(merged["platform_fee_basis_points"] or 0),
        variants=list(merged.get("variants") or []),
        personalization_enabled=bool(fields.get("personalization_enabled", False)),
        image_file_ids=fields.get("image_file_ids") or [],
        production_notes=_clean_optional_text(fields.get("production_notes")),
        public=bool(fields.get("public", False)),
        featured=bool(fields.get("featured", False)),
        status=fields.get("status", "draft"),
    ).model_dump()
    await db.webstore_products.insert_one(prepare_for_mongo(product))
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.product_created",
        entity_type="webstore_product",
        entity_id=product["id"],
        summary="Webstore product created",
        metadata={"source_template_id": product.get("source_template_id")},
    )
    return serialize_doc(product)  # type: ignore[return-value]


async def list_products(user: dict, *, webstore_id: str, public_only: bool = False) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    filters: dict[str, Any] = {"webstore_id": webstore_id}
    if public_only:
        filters.update({"public": True, "status": "active"})
    return await products_repo.list(tenant_id=user["tenant_id"], filters=filters, sort=[("featured", -1), ("name", 1)])


async def submit_questionnaire(identity: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    store = await _owner_portal_store(identity, webstore_id)
    owner = await _get_owner(identity["tenant_id"], store["owner_id"])
    existing = await submissions_repo.find_one({"tenant_id": identity["tenant_id"], "webstore_id": webstore_id})
    payload = {
        "answers": fields.get("answers") or {},
        "known_products": fields.get("known_products") or [],
        "open_to_suggestions": bool(fields.get("open_to_suggestions", True)),
        "missing_info_flags": fields.get("missing_info_flags") or [],
        "status": "submitted",
        "submitted_at": _now_iso(),
    }
    if existing:
        submission = await submissions_repo.update(tenant_id=identity["tenant_id"], entity_id=existing["id"], updates=payload)
    else:
        doc = WebstoreQuestionnaireSubmission(
            tenant_id=identity["tenant_id"],
            webstore_id=webstore_id,
            owner_id=owner["id"],
            **payload,
        ).model_dump()
        await db.webstore_questionnaire_submissions.insert_one(prepare_for_mongo(doc))
        submission = serialize_doc(doc)
    await stores_repo.update(tenant_id=identity["tenant_id"], entity_id=webstore_id, updates={"status": "questionnaire_submitted"})
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal",
        actor_id=identity["id"],
        actor_email=identity.get("email"),
        action="webstore.questionnaire_submitted",
        entity_type="webstore_questionnaire_submission",
        entity_id=submission["id"],
        summary="Webstore owner submitted questionnaire",
    )
    return submission or {}


async def create_artwork(user: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    await _get_store(user["tenant_id"], webstore_id)
    art = WebstoreArtworkFile(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        uploaded_by_actor_type="staff",
        uploaded_by_id=user["id"],
        original_file_id=fields.get("original_file_id"),
        original_url=fields.get("original_url"),
        file_name=fields.get("file_name"),
        file_type=fields.get("file_type"),
        notes=_clean_optional_text(fields.get("notes")),
    ).model_dump()
    await db.webstore_artwork_files.insert_one(prepare_for_mongo(art))
    await stores_repo.update(tenant_id=user["tenant_id"], entity_id=webstore_id, updates={"status": "artwork_needs_review"})
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.artwork_uploaded",
        entity_type="webstore_artwork_file",
        entity_id=art["id"],
        summary="Webstore artwork uploaded",
    )
    return serialize_doc(art)  # type: ignore[return-value]


async def create_mockup(user: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    await _get_store(user["tenant_id"], webstore_id)
    mockup = WebstoreMockup(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        product_id=fields.get("product_id"),
        artwork_id=fields.get("artwork_id"),
        mockup_file_id=fields.get("mockup_file_id"),
        generation_source=fields.get("generation_source", "manual"),
        status=fields.get("status", "generated"),
        shop_approved=bool(fields.get("shop_approved", False)),
        owner_visible=bool(fields.get("owner_visible", False)),
        notes=_clean_optional_text(fields.get("notes")),
    ).model_dump()
    await db.webstore_mockups.insert_one(prepare_for_mongo(mockup))
    await stores_repo.update(tenant_id=user["tenant_id"], entity_id=webstore_id, updates={"status": "mockups_generated"})
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.mockup_created",
        entity_type="webstore_mockup",
        entity_id=mockup["id"],
        summary="Webstore mockup created",
    )
    return serialize_doc(mockup)  # type: ignore[return-value]


async def create_ai_usage_event(user: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    await _get_store(user["tenant_id"], webstore_id)
    event = WebstoreAIUsageEvent(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        action=_clean_text(fields.get("action"), "action"),
        status=fields.get("status", "drafted"),
        prompt_source=_clean_optional_text(fields.get("prompt_source")),
        output_snapshot=fields.get("output_snapshot") or {},
        reviewed_by_user_id=fields.get("reviewed_by_user_id"),
        reviewed_at=fields.get("reviewed_at"),
    ).model_dump()
    await db.webstore_ai_usage_events.insert_one(prepare_for_mongo(event))
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.ai_contract_recorded",
        entity_type="webstore_ai_usage_event",
        entity_id=event["id"],
        summary="Webstore AI suggestion contract recorded without provider call",
    )
    return serialize_doc(event)  # type: ignore[return-value]


async def generate_launch_packet(user: dict, webstore_id: str, fields: Optional[dict[str, Any]] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    fields = fields or {}
    store = await _get_store(user["tenant_id"], webstore_id)
    products = await products_repo.list(
        tenant_id=user["tenant_id"],
        filters={"webstore_id": webstore_id, "status": "active", "public": True},
        sort=[("featured", -1), ("name", 1)],
    )
    snapshot_products = [_public_product(p) for p in products["items"]]
    packet = WebstoreLaunchPacket(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        status="generated",
        snapshot={"webstore": _public_store(store), "products": snapshot_products},
        pricing_summary={
            "product_count": len(snapshot_products),
            "lowest_price_cents": min([p.get("selling_price_cents", 0) for p in snapshot_products], default=0),
            "highest_price_cents": max([p.get("selling_price_cents", 0) for p in snapshot_products], default=0),
        },
        promotion_copy=_clean_optional_text(fields.get("promotion_copy")),
        qr_code_url=fields.get("qr_code_url"),
        share_url=fields.get("share_url") or store.get("public_url"),
    ).model_dump()
    await db.webstore_launch_packets.insert_one(prepare_for_mongo(packet))
    await stores_repo.update(
        tenant_id=user["tenant_id"],
        entity_id=webstore_id,
        updates={"status": "store_packet_generated", "launch_packet_id": packet["id"]},
    )
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.launch_packet_generated",
        entity_type="webstore_launch_packet",
        entity_id=packet["id"],
        summary="Webstore launch packet generated",
    )
    return serialize_doc(packet)  # type: ignore[return-value]


async def send_launch_packet(user: dict, webstore_id: str, packet_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    packet = await packets_repo.get(tenant_id=user["tenant_id"], entity_id=packet_id)
    if not packet or packet["webstore_id"] != webstore_id:
        raise WebstoreError("launch_packet_not_found", "Launch packet not found", 404)
    packet = await packets_repo.update(
        tenant_id=user["tenant_id"],
        entity_id=packet_id,
        updates={"status": "sent_for_approval", "sent_at": _now_iso()},
    )
    await stores_repo.update(tenant_id=user["tenant_id"], entity_id=webstore_id, updates={"status": "sent_for_approval"})
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.launch_packet_sent",
        entity_type="webstore_launch_packet",
        entity_id=packet_id,
        summary="Webstore launch packet sent for owner approval",
    )
    return packet or {}


async def owner_approve_launch_packet(identity: dict, webstore_id: str, packet_id: str) -> dict:
    await _owner_portal_store(identity, webstore_id)
    packet = await packets_repo.get(tenant_id=identity["tenant_id"], entity_id=packet_id)
    if not packet or packet["webstore_id"] != webstore_id:
        raise WebstoreError("launch_packet_not_found", "Launch packet not found", 404)
    if packet.get("status") != "sent_for_approval":
        raise WebstoreError("launch_packet_not_sent", "Launch packet must be sent before owner approval", 409)
    now = _now_iso()
    packet = await packets_repo.update(
        tenant_id=identity["tenant_id"],
        entity_id=packet_id,
        updates={"status": "owner_approved", "owner_decision_at": now},
    )
    await stores_repo.update(
        tenant_id=identity["tenant_id"],
        entity_id=webstore_id,
        updates={"status": "approved", "owner_approved_at": now, "owner_approved_by_portal_identity_id": identity["id"]},
    )
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal",
        actor_id=identity["id"],
        actor_email=identity.get("email"),
        action="webstore.owner_approved_launch",
        entity_type="webstore_launch_packet",
        entity_id=packet_id,
        summary="Webstore owner approved launch packet",
    )
    return packet or {}


async def launch_readiness(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _ensure_public_slug(await _get_store(user["tenant_id"], webstore_id))
    checks: dict[str, bool] = {}
    checks["entitlement"] = await has_entitlement(tenant_id=user["tenant_id"], feature_key=store.get("entitlement_feature_key") or WEBSTORES_FEATURE_KEY)
    checks["not_closed_or_archived"] = store.get("status") not in LIVE_BLOCKING_STATUSES
    active_count = await db.webstore_products.count_documents(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "status": "active", "public": True, "selling_price_cents": {"$gt": 0}}
    )
    checks["active_public_products_with_prices"] = active_count > 0
    checks["public_branding"] = bool(store.get("name") and store.get("slug") and store.get("public_slug"))
    checks["launch_packet"] = bool(store.get("launch_packet_id"))
    checks["owner_approved"] = bool(store.get("owner_approved_at"))
    checks["terms_fee_acknowledged"] = bool(store.get("terms_fee_acknowledged"))
    checks["payment_ready"] = False
    ready = all(checks.values())
    return {
        "webstore_id": webstore_id,
        "ready": ready,
        "checks": checks,
        "payment_readiness_source": "computed",
        "payment_unavailable_reason": "Real verified provider checkout is not connected yet.",
    }


async def _storefront_by_slug(slug: str) -> dict:
    store = await db.webstores.find_one({"public_slug": slug}, {"_id": 0})
    if not store:
        raise WebstoreError("webstore_not_found", "Webstore not found", 404)
    store = await _ensure_public_slug(serialize_doc(store))
    if store.get("status") != "live":
        raise WebstoreError("webstore_not_live", "Webstore is not available", 404)
    products = [
        _public_product(doc)
        async for doc in db.webstore_products.find(
            {"tenant_id": store["tenant_id"], "webstore_id": store["id"], "status": "active", "public": True},
            {"_id": 0},
        ).sort([("featured", -1), ("name", 1)])
    ]
    return {"webstore": _public_store(serialize_doc(store)), "products": products}


async def public_storefront(slug: str) -> dict:
    return await _storefront_by_slug(slug)


UNAUTHORIZED_PUBLIC_MONEY_FIELDS = {
    "donation_cents",
    "shipping_cents",
    "tax_cents",
    "discount_cents",
    "fee_cents",
    "total_cents",
    "product_subtotal_cents",
}


def _reject_public_money_authority(fields: dict[str, Any]) -> None:
    supplied = [field for field in UNAUTHORIZED_PUBLIC_MONEY_FIELDS if int(fields.get(field) or 0) != 0]
    if supplied:
        raise WebstoreError(
            "public_money_fields_not_allowed",
            "Shipping, tax, discounts, donations, fees, and final totals are calculated by the server during verified checkout.",
            400,
        )


async def create_purchase_intent(slug: str, fields: dict[str, Any]) -> dict:
    _reject_public_money_authority(fields)
    storefront = await _storefront_by_slug(slug)
    store = storefront["webstore"]
    full_store = await db.webstores.find_one({"public_slug": slug, "id": store["id"]}, {"_id": 0})
    tenant_id = full_store["tenant_id"]
    if fields.get("idempotency_key"):
        existing = await db.webstore_purchase_intents.find_one(
            {"tenant_id": tenant_id, "webstore_id": store["id"], "idempotency_key": fields["idempotency_key"]},
            {"_id": 0},
        )
        if existing:
            return {"purchase_intent": serialize_doc(existing), "checkout_available": False, "checkout_unavailable_reason": "Real Webstore checkout is not connected yet."}
    product_map = {p["id"]: p for p in storefront["products"]}
    line_items: list[dict[str, Any]] = []
    subtotal = 0
    for raw in fields.get("line_items") or []:
        product_id = raw.get("product_id")
        product = product_map.get(product_id)
        if not product:
            raise WebstoreError("product_not_available", "Product is not available for checkout", 409)
        qty = int(raw.get("quantity") or 0)
        if qty <= 0:
            raise WebstoreError("invalid_quantity", "Quantity must be at least 1", 400)
        full_product = await _get_product(tenant_id, product_id, store["id"])
        unit = int(full_product["selling_price_cents"])
        line_total = unit * qty
        subtotal += line_total
        line_items.append(
            {
                "product_id": product_id,
                "product_snapshot": {
                    "id": product_id,
                    "name": full_product["name"],
                    "description": full_product.get("description"),
                    "category": full_product.get("category"),
                    "product_type": full_product.get("product_type"),
                    "sku": full_product.get("sku"),
                },
                "name": full_product["name"],
                "variant": raw.get("variant") or {},
                "quantity": qty,
                "unit_price_cents": unit,
                "line_total_cents": line_total,
                "personalization": raw.get("personalization") or {},
            }
        )
    if not line_items:
        raise WebstoreError("line_items_required", "At least one line item is required", 400)
    total = subtotal
    intent = WebstorePurchaseIntent(
        tenant_id=tenant_id,
        webstore_id=store["id"],
        public_slug=slug,
        buyer_name=_clean_text(fields.get("buyer_name"), "buyer_name"),
        buyer_email=_clean_text(fields.get("buyer_email"), "buyer_email", limit=254).lower(),
        buyer_phone=_clean_optional_text(fields.get("buyer_phone"), limit=40),
        line_items=line_items,
        product_subtotal_cents=subtotal,
        total_cents=total,
        idempotency_key=fields.get("idempotency_key"),
        immutable_snapshot={
            "webstore": _public_store(full_store),
            "line_items": line_items,
            "server_calculated_totals": {
                "product_subtotal_cents": subtotal,
                "donation_cents": 0,
                "shipping_cents": 0,
                "tax_cents": 0,
                "discount_cents": 0,
                "fee_cents": 0,
                "total_cents": total,
                "currency": "usd",
            },
        },
    ).model_dump()
    try:
        await db.webstore_purchase_intents.insert_one(prepare_for_mongo(intent))
    except DuplicateKeyError:
        existing = await db.webstore_purchase_intents.find_one(
            {"tenant_id": tenant_id, "webstore_id": store["id"], "idempotency_key": fields.get("idempotency_key")},
            {"_id": 0},
        )
        return {"purchase_intent": serialize_doc(existing), "checkout_available": False, "checkout_unavailable_reason": "Real Webstore checkout is not connected yet."}
    await _audit(
        tenant_id=tenant_id,
        webstore_id=store["id"],
        actor_type="public",
        actor_email=intent["buyer_email"],
        action="webstore.purchase_intent_created",
        entity_type="webstore_purchase_intent",
        entity_id=intent["id"],
        summary="Webstore purchase intent created without checkout",
        metadata={"total_cents": total},
    )
    saved = await db.webstore_purchase_intents.find_one({"tenant_id": tenant_id, "id": intent["id"]}, {"_id": 0})
    return {
        "purchase_intent": serialize_doc(saved),
        "checkout_available": False,
        "checkout_unavailable_reason": "Real Webstore checkout is not connected yet.",
    }


async def create_buyer_order(slug: str, fields: dict[str, Any]) -> dict:
    return await create_purchase_intent(slug, fields)


async def _create_ledger_rows(
    *,
    tenant_id: str,
    webstore_id: str,
    buyer_order_id: str,
    subtotal: int,
    donation: int,
    shipping: int,
    tax: int,
    total: int,
    platform_fee: int,
    owner_share: int,
    production_cost: int,
) -> None:
    shop_gross = subtotal - platform_fee - owner_share - production_cost
    rows = [
        ("buyer_payment", total, total, None),
        ("product_subtotal", subtotal, subtotal, None),
        ("donation", donation, donation, None),
        ("shipping", shipping, shipping, None),
        ("sales_tax", tax, tax, None),
        ("payment_processing_fee", 0, total, None),
        ("platform_usage_fee", platform_fee, subtotal, None),
        ("store_owner_share", owner_share, subtotal, None),
        ("production_cost_estimate", production_cost, subtotal, None),
        ("shop_gross_estimate", shop_gross, subtotal, None),
    ]
    for entry_type, amount, basis, bps in rows:
        entry = WebstoreLedgerEntry(
            tenant_id=tenant_id,
            webstore_id=webstore_id,
            buyer_order_id=buyer_order_id,
            entry_type=entry_type,  # type: ignore[arg-type]
            amount_cents=amount,
            basis_amount_cents=basis,
            snapshot_basis_points=bps,
            source_type="webstore_buyer_order",
            source_id=buyer_order_id,
        ).model_dump()
        await db.webstore_ledger_entries.insert_one(prepare_for_mongo(entry))


async def _ledger_for_order(tenant_id: str, buyer_order_id: str) -> list[dict]:
    cursor = db.webstore_ledger_entries.find({"tenant_id": tenant_id, "buyer_order_id": buyer_order_id}, {"_id": 0}).sort("created_at", 1)
    return [serialize_doc(doc) async for doc in cursor]


async def reverse_platform_fee(user: dict, ledger_entry_id: str, refund_basis_amount_cents: int) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    original = await db.webstore_ledger_entries.find_one(
        {"tenant_id": user["tenant_id"], "id": ledger_entry_id, "entry_type": "platform_usage_fee", "reversal_of_ledger_entry_id": None},
        {"_id": 0},
    )
    if not original:
        raise WebstoreError("platform_fee_not_found", "Original Webstore platform fee ledger entry not found", 404)
    if refund_basis_amount_cents <= 0 or refund_basis_amount_cents > int(original.get("basis_amount_cents") or 0):
        raise WebstoreError("invalid_refund_basis", "Refund basis must be positive and cannot exceed original basis", 400)
    reversal = int(
        (Decimal(original["amount_cents"]) * Decimal(refund_basis_amount_cents) / Decimal(original["basis_amount_cents"]))
        .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    entry = WebstoreLedgerEntry(
        tenant_id=original["tenant_id"],
        webstore_id=original["webstore_id"],
        buyer_order_id=original.get("buyer_order_id"),
        entry_type="platform_usage_fee_reversal",
        amount_cents=-reversal,
        basis_amount_cents=refund_basis_amount_cents,
        snapshot_basis_points=original.get("snapshot_basis_points"),
        source_type=original.get("source_type", "webstore_buyer_order"),
        source_id=original.get("source_id", original["id"]),
        status="reversed" if refund_basis_amount_cents == original.get("basis_amount_cents") else "adjusted",
        reversal_of_ledger_entry_id=original["id"],
        notes="Proportional platform-fee reversal. Original ledger entry is immutable.",
    ).model_dump()
    await db.webstore_ledger_entries.insert_one(prepare_for_mongo(entry))
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=original["webstore_id"],
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.platform_fee_reversed",
        entity_type="webstore_ledger_entry",
        entity_id=entry["id"],
        summary="Webstore platform fee reversal recorded",
        metadata={"original_ledger_entry_id": original["id"], "refund_basis_amount_cents": refund_basis_amount_cents},
    )
    return serialize_doc(entry)  # type: ignore[return-value]


async def bridge_buyer_order_to_order(user: dict, buyer_order_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    buyer = await buyer_orders_repo.get(tenant_id=user["tenant_id"], entity_id=buyer_order_id)
    if not buyer:
        raise WebstoreError("buyer_order_not_found", "Buyer order not found", 404)
    if not buyer.get("verified_payment_event_id") or buyer.get("payment_status") != "paid":
        raise WebstoreError(
            "verified_payment_required",
            "Legacy Webstore buyer orders cannot become canonical Orders without verified payment evidence.",
            409,
        )
    if buyer.get("bridged_order_id"):
        order = await db.orders.find_one({"tenant_id": user["tenant_id"], "id": buyer["bridged_order_id"]}, {"_id": 0})
        return {"order": serialize_doc(order), "bridge_status": buyer.get("bridge_status", "bridged")}
    customer = await db.customers.find_one({"tenant_id": user["tenant_id"], "email": buyer["buyer_email"]}, {"_id": 0})
    if not customer:
        customer_doc = Customer(
            tenant_id=user["tenant_id"],
            name=buyer["buyer_name"],
            email=buyer["buyer_email"],
            phone=buyer.get("buyer_phone"),
            notes=f"Created from Webstore buyer order {buyer['id']}",
        ).model_dump()
        customer_number = await next_record_number(
            tenant_id=user["tenant_id"],
            record_type="customer",
            issued_to_entity_type="customer",
            issued_to_entity_id=customer_doc["id"],
            actor_user_id=user["id"],
            actor_email=user.get("email"),
            reason="webstore.bridge_customer_create",
            context={"buyer_order_id": buyer["id"], "webstore_id": buyer["webstore_id"]},
        )
        customer_doc["number"] = customer_number.number
        await db.customers.insert_one(prepare_for_mongo(customer_doc))
        customer = customer_doc
    number = await next_number(tenant_id=user["tenant_id"], name="order")
    order = Order(
        tenant_id=user["tenant_id"],
        number=number,
        customer_id=customer["id"],
        job_name=f"Webstore order - {buyer['buyer_name']}",
        title=f"Webstore order {buyer['id']}",
        description="Created from Webstore buyer order",
        subtotal_cents=buyer["product_subtotal_cents"],
        tax_cents=buyer["tax_cents"],
        total_cents=buyer["total_cents"],
        balance_cents=buyer["total_cents"],
        status="confirmed",
        created_by=user["id"],
    ).model_dump()
    await db.orders.insert_one(prepare_for_mongo(order))
    for idx, line in enumerate(buyer.get("line_items") or []):
        item = OrderItem(
            tenant_id=user["tenant_id"],
            order_id=order["id"],
            position=idx,
            category="webstore",
            product_type="webstore_product",
            description=line["name"],
            quantity=int(line["quantity"]),
            unit_price_cents=int(line["unit_price_cents"]),
            line_subtotal_cents=int(line["line_total_cents"]),
            line_total_cents=int(line["line_total_cents"]),
            pricing_snapshot={"source": "webstore_buyer_order", "buyer_order_id": buyer["id"], "line_item": line},
            production_required=True,
        ).model_dump()
        await db.order_items.insert_one(prepare_for_mongo(item))
    await buyer_orders_repo.update(
        tenant_id=user["tenant_id"],
        entity_id=buyer["id"],
        updates={"bridged_order_id": order["id"], "bridge_status": "bridged", "status": "ready_for_production"},
    )
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=buyer["webstore_id"],
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.buyer_order_bridged",
        entity_type="order",
        entity_id=order["id"],
        summary="Webstore buyer order bridged to canonical Order",
        metadata={"buyer_order_id": buyer["id"]},
    )
    return {"order": serialize_doc(order), "bridge_status": "bridged"}


async def reports(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    await _get_store(user["tenant_id"], webstore_id)
    orders = [doc async for doc in db.webstore_buyer_orders.find({"tenant_id": user["tenant_id"], "webstore_id": webstore_id}, {"_id": 0})]
    ledger = [doc async for doc in db.webstore_ledger_entries.find({"tenant_id": user["tenant_id"], "webstore_id": webstore_id}, {"_id": 0})]
    by_entry: dict[str, int] = {}
    for row in ledger:
        by_entry[row["entry_type"]] = by_entry.get(row["entry_type"], 0) + int(row.get("amount_cents") or 0)
    product_qty: dict[str, int] = {}
    for order in orders:
        for line in order.get("line_items") or []:
            product_qty[line["product_id"]] = product_qty.get(line["product_id"], 0) + int(line.get("quantity") or 0)
    return {
        "webstore_id": webstore_id,
        "order_count": len(orders),
        "gross_sales_cents": sum(int(o.get("total_cents") or 0) for o in orders),
        "ledger_totals_cents": by_entry,
        "product_quantities": product_qty,
    }


async def _owner_portal_store(identity: dict, webstore_id: str) -> dict:
    if identity.get("portal_type") not in {"webstore_owner", "webstore_manager"}:
        raise WebstoreError("webstore_portal_required", "Webstore portal access required", 403)
    store = await _get_store(identity["tenant_id"], webstore_id)
    assignment = await db.webstore_access_assignments.find_one(
        {
            "tenant_id": identity["tenant_id"],
            "webstore_id": webstore_id,
            "portal_identity_id": identity.get("id"),
            "status": "active",
        },
        {"_id": 0},
    )
    if assignment:
        return store
    assignment_count = await db.webstore_access_assignments.count_documents(
        {"tenant_id": identity["tenant_id"], "portal_identity_id": identity.get("id")}
    )
    if assignment_count:
        raise WebstoreError("webstore_assignment_scope_forbidden", "Webstore portal access is limited to assigned Webstores", 403)
    owner_id = identity.get("webstore_owner_id")
    if owner_id and store.get("owner_id") != owner_id:
        raise WebstoreError("webstore_scope_forbidden", "Webstore portal access is owner-scoped", 403)
    if not owner_id:
        raise WebstoreError("webstore_owner_scope_required", "Webstore owner scope is required", 403)
    assigned_webstore_id = identity.get("webstore_id")
    if identity.get("portal_type") == "webstore_manager":
        if not assigned_webstore_id:
            raise WebstoreError("webstore_manager_assignment_required", "Webstore manager scope is required", 403)
        if assigned_webstore_id != webstore_id:
            raise WebstoreError("webstore_manager_scope_forbidden", "Webstore manager access is limited to the assigned Webstore", 403)
    return store


async def owner_portal_list(identity: dict) -> dict:
    if identity.get("portal_type") not in {"webstore_owner", "webstore_manager"} or not identity.get("webstore_owner_id"):
        raise WebstoreError("webstore_portal_required", "Webstore portal access required", 403)
    assignment_records = [
        doc
        async for doc in db.webstore_access_assignments.find(
            {"tenant_id": identity["tenant_id"], "portal_identity_id": identity.get("id")},
            {"_id": 0, "webstore_id": 1, "status": 1},
        )
    ]
    if assignment_records:
        assignments = [doc["webstore_id"] for doc in assignment_records if doc.get("status") == "active"]
        return await stores_repo.list(
            tenant_id=identity["tenant_id"],
            filters={"id": {"$in": assignments}},
            sort=[("updated_at", -1)],
        )
    filters = {"owner_id": identity["webstore_owner_id"]}
    if identity.get("portal_type") == "webstore_manager":
        if not identity.get("webstore_id"):
            raise WebstoreError("webstore_manager_assignment_required", "Webstore manager scope is required", 403)
        filters["id"] = identity["webstore_id"]
    return await stores_repo.list(
        tenant_id=identity["tenant_id"],
        filters=filters,
        sort=[("updated_at", -1)],
    )


async def owner_portal_detail(identity: dict, webstore_id: str) -> dict:
    store = await _owner_portal_store(identity, webstore_id)
    products = [
        _public_product(doc)
        async for doc in db.webstore_products.find({"tenant_id": identity["tenant_id"], "webstore_id": webstore_id}, {"_id": 0}).sort("name", 1)
    ]
    packet = None
    if store.get("launch_packet_id"):
        packet = await packets_repo.get(tenant_id=identity["tenant_id"], entity_id=store["launch_packet_id"])
    return {"webstore": _portal_store(store), "products": products, "launch_packet": _portal_launch_packet(packet)}
