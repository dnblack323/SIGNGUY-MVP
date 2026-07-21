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
    WebstoreQuestionnaireSubmission,
)
from ..repositories.webstores import WebstoreRepository
from .activity import record_activity_with_audit
from .entitlements import has_entitlement
from .portal_identity import create_portal_identity
from .sequence import next_number
from .webstore_stripe_connect import create_local_checkout_record

WEBSTORES_FEATURE_KEY = "webstores"
LIVE_BLOCKING_STATUSES = {"closed", "archived"}
PRODUCT_PURCHASABLE_STATUSES = {"active"}
SLUG_RE = re.compile(r"[^a-z0-9]+")

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
        "created_at",
        "updated_at",
    }
    return {k: serialize_doc(product).get(k) for k in allowed if k in product}


def _public_store(store: dict) -> dict:
    allowed = {
        "id",
        "name",
        "slug",
        "store_type",
        "status",
        "description",
        "branding",
        "deadline_at",
        "public_url",
        "checkout_enabled",
    }
    return {k: v for k, v in store.items() if k in allowed}


def _public_launch_packet(packet: Optional[dict]) -> Optional[dict]:
    if not packet:
        return None
    allowed = {
        "id",
        "webstore_id",
        "status",
        "snapshot",
        "promotion_copy",
        "qr_code_url",
        "share_url",
        "sent_at",
        "owner_decision_at",
        "change_request_reason",
        "created_at",
        "updated_at",
    }
    return {k: serialize_doc(packet).get(k) for k in allowed if k in packet}


def _public_buyer_order(order: Optional[dict]) -> dict:
    if not order:
        return {}
    allowed = {
        "id",
        "buyer_name",
        "buyer_email",
        "buyer_phone",
        "line_items",
        "product_subtotal_cents",
        "donation_cents",
        "shipping_cents",
        "tax_cents",
        "total_cents",
        "currency",
        "status",
        "payment_status",
        "fulfillment_status",
        "checkout_url",
        "created_at",
        "updated_at",
    }
    return {k: serialize_doc(order).get(k) for k in allowed if k in order}


def _buyer_visible_ledger(rows: list[dict]) -> list[dict]:
    visible_types = {"buyer_payment", "product_subtotal", "donation", "shipping", "sales_tax", "refund"}
    allowed = {"id", "entry_type", "amount_cents", "currency", "basis_amount_cents", "status", "created_at"}
    return [
        {k: serialize_doc(row).get(k) for k in allowed if k in row}
        for row in rows
        if row.get("entry_type") in visible_types
    ]


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
    owner = await _get_owner(user["tenant_id"], fields["owner_id"])
    slug = _slug(fields.get("slug") or fields.get("name") or owner["name"])
    store = Webstore(
        tenant_id=user["tenant_id"],
        owner_id=owner["id"],
        name=_clean_text(fields.get("name"), "name"),
        slug=slug,
        store_type=fields.get("store_type", "general"),
        description=_clean_optional_text(fields.get("description")),
        branding=fields.get("branding") or {},
        direct_owner_payout_required=bool(fields.get("direct_owner_payout_required", False)),
        stripe_onboarding_required=bool(fields.get("stripe_onboarding_required", False)),
        stripe_payment_ready=bool(fields.get("stripe_payment_ready", False)),
        deadline_at=fields.get("deadline_at"),
        public_url=f"/p/webstores/{slug}",
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
    return serialize_doc(store)  # type: ignore[return-value]


async def list_webstores(user: dict, *, status: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    filters = {"status": status} if status else {}
    return await stores_repo.list(tenant_id=user["tenant_id"], filters=filters, sort=[("updated_at", -1)])


async def get_webstore(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _get_store(user["tenant_id"], webstore_id)
    products = await list_products(user, webstore_id=webstore_id)
    packets = await packets_repo.list(tenant_id=user["tenant_id"], filters={"webstore_id": webstore_id}, sort=[("created_at", -1)], limit=10)
    return {"webstore": store, "products": products["items"], "launch_packets": packets["items"]}


async def update_webstore(user: dict, webstore_id: str, updates: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    await _get_store(user["tenant_id"], webstore_id)
    allowed = {
        k: v
        for k, v in updates.items()
        if k
        in {
            "name",
            "description",
            "branding",
            "checkout_enabled",
            "terms_fee_acknowledged",
            "direct_owner_payout_required",
            "stripe_onboarding_required",
            "stripe_payment_ready",
            "deadline_at",
        }
    }
    if "name" in allowed:
        allowed["name"] = _clean_text(allowed["name"], "name")
    if "description" in allowed:
        allowed["description"] = _clean_optional_text(allowed["description"])
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
    return store or {}


async def set_webstore_status(user: dict, webstore_id: str, status: str, reason: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE if status in {"live", "closed", "archived"} else Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
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
    store = await _get_store(user["tenant_id"], webstore_id)
    checks: dict[str, bool] = {}
    checks["entitlement"] = await has_entitlement(tenant_id=user["tenant_id"], feature_key=store.get("entitlement_feature_key") or WEBSTORES_FEATURE_KEY)
    checks["not_closed_or_archived"] = store.get("status") not in LIVE_BLOCKING_STATUSES
    active_count = await db.webstore_products.count_documents(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "status": "active", "public": True, "selling_price_cents": {"$gt": 0}}
    )
    checks["active_public_products_with_prices"] = active_count > 0
    checks["public_branding"] = bool(store.get("name") and store.get("slug"))
    checks["launch_packet"] = bool(store.get("launch_packet_id"))
    checks["owner_approved"] = bool(store.get("owner_approved_at"))
    checks["terms_fee_acknowledged"] = bool(store.get("terms_fee_acknowledged"))
    checks["payment_ready"] = bool(store.get("stripe_payment_ready")) and (
        not store.get("stripe_onboarding_required") or store.get("direct_owner_payout_required") is False
    )
    ready = all(checks.values())
    return {"webstore_id": webstore_id, "ready": ready, "checks": checks}


async def _storefront_by_slug(slug: str) -> dict:
    store = await db.webstores.find_one({"slug": slug}, {"_id": 0})
    if not store:
        raise WebstoreError("webstore_not_found", "Webstore not found", 404)
    if store.get("status") != "live" or not store.get("checkout_enabled"):
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


async def create_buyer_order(slug: str, fields: dict[str, Any]) -> dict:
    storefront = await _storefront_by_slug(slug)
    store = storefront["webstore"]
    full_store = await db.webstores.find_one({"id": store["id"]}, {"_id": 0})
    tenant_id = full_store["tenant_id"]
    if fields.get("idempotency_key"):
        existing = await db.webstore_buyer_orders.find_one(
            {"tenant_id": tenant_id, "webstore_id": store["id"], "idempotency_key": fields["idempotency_key"]},
            {"_id": 0},
        )
        if existing:
            return {"buyer_order": _public_buyer_order(existing), "ledger": _buyer_visible_ledger(await _ledger_for_order(tenant_id, existing["id"]))}
    product_map = {p["id"]: p for p in storefront["products"]}
    line_items: list[dict[str, Any]] = []
    subtotal = 0
    production_cost_total = 0
    owner_share_total = 0
    platform_fee_total = 0
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
        production_cost_total += int(full_product.get("production_cost_cents") or 0) * qty
        owner_share_total += int(full_product.get("store_owner_share_cents") or 0) * qty
        fee = int((Decimal(line_total) * Decimal(full_product.get("platform_fee_basis_points", 0)) / Decimal(10000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        platform_fee_total += fee
        line_items.append(
            {
                "product_id": product_id,
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
    donation = int(fields.get("donation_cents") or 0)
    shipping = int(fields.get("shipping_cents") or 0)
    tax = int(fields.get("tax_cents") or 0)
    if min(donation, shipping, tax) < 0:
        raise WebstoreError("invalid_cents", "Money values must be non-negative integer cents", 400)
    total = subtotal + donation + shipping + tax
    order = WebstoreBuyerOrder(
        tenant_id=tenant_id,
        webstore_id=store["id"],
        buyer_name=_clean_text(fields.get("buyer_name"), "buyer_name"),
        buyer_email=_clean_text(fields.get("buyer_email"), "buyer_email", limit=254).lower(),
        buyer_phone=_clean_optional_text(fields.get("buyer_phone"), limit=40),
        line_items=line_items,
        product_subtotal_cents=subtotal,
        donation_cents=donation,
        shipping_cents=shipping,
        tax_cents=tax,
        total_cents=total,
        idempotency_key=fields.get("idempotency_key"),
    ).model_dump()
    try:
        await db.webstore_buyer_orders.insert_one(prepare_for_mongo(order))
    except DuplicateKeyError:
        existing = await db.webstore_buyer_orders.find_one(
            {"tenant_id": tenant_id, "webstore_id": store["id"], "idempotency_key": fields.get("idempotency_key")},
            {"_id": 0},
        )
        return {"buyer_order": _public_buyer_order(existing), "ledger": _buyer_visible_ledger(await _ledger_for_order(tenant_id, existing["id"]))}
    checkout = await create_local_checkout_record(
        tenant_id=tenant_id,
        webstore_id=store["id"],
        buyer_order_id=order["id"],
        amount_cents=total,
        idempotency_key=fields.get("idempotency_key"),
    )
    await db.webstore_buyer_orders.update_one(
        {"tenant_id": tenant_id, "id": order["id"]},
        {"$set": {"stripe_connect_checkout_id": checkout["id"], "checkout_url": checkout.get("checkout_url"), "updated_at": _now_iso()}},
    )
    await _create_ledger_rows(
        tenant_id=tenant_id,
        webstore_id=store["id"],
        buyer_order_id=order["id"],
        subtotal=subtotal,
        donation=donation,
        shipping=shipping,
        tax=tax,
        total=total,
        platform_fee=platform_fee_total,
        owner_share=owner_share_total,
        production_cost=production_cost_total,
    )
    await _audit(
        tenant_id=tenant_id,
        webstore_id=store["id"],
        actor_type="public",
        actor_email=order["buyer_email"],
        action="webstore.buyer_order_created",
        entity_type="webstore_buyer_order",
        entity_id=order["id"],
        summary="Webstore buyer order created",
        metadata={"total_cents": total},
    )
    saved = await db.webstore_buyer_orders.find_one({"tenant_id": tenant_id, "id": order["id"]}, {"_id": 0})
    return {"buyer_order": _public_buyer_order(saved), "ledger": _buyer_visible_ledger(await _ledger_for_order(tenant_id, order["id"]))}


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
    owner_id = identity.get("webstore_owner_id")
    if owner_id and store.get("owner_id") != owner_id:
        raise WebstoreError("webstore_scope_forbidden", "Webstore portal access is owner-scoped", 403)
    if not owner_id:
        raise WebstoreError("webstore_owner_scope_required", "Webstore owner scope is required", 403)
    return store


async def owner_portal_list(identity: dict) -> dict:
    if identity.get("portal_type") not in {"webstore_owner", "webstore_manager"} or not identity.get("webstore_owner_id"):
        raise WebstoreError("webstore_portal_required", "Webstore portal access required", 403)
    stores = await stores_repo.list(
        tenant_id=identity["tenant_id"],
        filters={"owner_id": identity["webstore_owner_id"]},
        sort=[("updated_at", -1)],
    )
    return {"items": [_public_store(store) for store in stores["items"]], "total": stores["total"]}


async def owner_portal_detail(identity: dict, webstore_id: str) -> dict:
    store = await _owner_portal_store(identity, webstore_id)
    products = [
        _public_product(doc)
        async for doc in db.webstore_products.find({"tenant_id": identity["tenant_id"], "webstore_id": webstore_id}, {"_id": 0}).sort("name", 1)
    ]
    packet = None
    if store.get("launch_packet_id"):
        packet = await packets_repo.get(tenant_id=identity["tenant_id"], entity_id=store["launch_packet_id"])
    return {"webstore": _public_store(store), "products": products, "launch_packet": _public_launch_packet(packet)}
