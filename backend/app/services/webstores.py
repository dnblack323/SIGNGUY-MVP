"""EC14 - Webstores service layer."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import re
from typing import Any, Optional

from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.permissions import PlatformPerm, Perm, has_platform_admin_access, permissions_for_role
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
    WebstoreProductCategory,
    WebstoreProductTemplate,
    WebstorePurchaseIntent,
    WebstoreQuestionnaireSubmission,
)
from ..repositories.webstores import WebstoreRepository
from .activity import record_activity_with_audit
from . import webstore_branding as branding_svc
from .entitlements import has_entitlement
from .portal_identity import create_portal_identity
from .sequence import next_number, next_record_number
from . import storage

WEBSTORES_FEATURE_KEY = "webstores"
LIVE_BLOCKING_STATUSES = {"closed", "archived"}
PRODUCT_PURCHASABLE_STATUSES = {"active"}
PLATFORM_TEMPLATE_TENANT_ID = "__platform__"
TEMPLATE_SCOPES = {"tenant", "platform"}
TEMPLATE_STATUSES = {"draft", "active", "archived"}
PRODUCT_STATUSES = {"draft", "active", "inactive", "archived"}
CATEGORY_STATUSES = {"active", "archived"}
CUSTOMER_IMAGE_SLOTS = {"primary", "secondary"}
PRODUCT_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "svg"}
STAGE4A_PUBLICATION_FIELDS = {"public", "featured", "status"}
STAGE4A_FINANCIAL_VARIANT_FIELDS = {
    "production_cost_cents",
    "selling_price_cents",
    "store_owner_share_cents",
    "platform_fee_basis_points",
    "margin_cents",
    "margin_percent",
    "revenue_cents",
    "fundraiser_share_cents",
    "owner_share_cents",
    "variants",
    "variant_pricing",
    "variant_skus",
    "sku",
    "personalization_enabled",
    "image_file_ids",
}
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
categories_repo = WebstoreRepository("webstore_product_categories")
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


def _clean_money(value: Any, *, default: int = 0) -> int:
    if value in (None, ""):
        return default
    amount = int(value)
    if amount < 0:
        raise WebstoreError("negative_money_not_allowed", "Money values cannot be negative", 400)
    return amount


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _clean_status(value: Any, allowed: set[str], default: str, field: str) -> str:
    status = str(value or default).strip().lower()
    if status not in allowed:
        raise WebstoreError(f"invalid_{field}", f"Unsupported {field.replace('_', ' ')}", 400)
    return status


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _hash_payload(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _reject_stage4a_publication_request(fields: dict[str, Any], *, allow_system_transition: bool = False) -> None:
    if allow_system_transition:
        return
    if fields.get("public") is True:
        raise WebstoreError(
            "stage4a_publication_not_available",
            "Products cannot be made public in Product Foundation. Publication is handled in a later Webstore stage.",
            400,
        )
    if fields.get("featured") is True:
        raise WebstoreError(
            "stage4a_featured_not_available",
            "Products cannot be featured in Product Foundation. Featuring products is handled in a later Webstore stage.",
            400,
        )
    if "status" in fields and str(fields.get("status") or "draft").lower() != "draft":
        raise WebstoreError(
            "stage4a_product_status_not_available",
            "Product Foundation can only create and edit private Draft products. Approval and publication are handled later.",
            400,
        )


def _reject_stage4a_financial_variant_request(fields: dict[str, Any]) -> None:
    blocked = sorted(STAGE4A_FINANCIAL_VARIANT_FIELDS & set(fields))
    if blocked:
        raise WebstoreError(
            "stage4a_financial_fields_not_available",
            "Product Foundation cannot create or change pricing, fees, shares, SKUs, or variants. Those controls are handled in a later Webstore stage.",
            400,
        )


def _stage4a_product_create_fingerprint(fields: dict[str, Any], *, operation: str, source_template_id: Optional[str]) -> str:
    comparable = {key: deepcopy(value) for key, value in fields.items() if key != "idempotency_key"}
    comparable["operation"] = operation
    comparable["source_template_id"] = source_template_id
    return _hash_payload(comparable)


def _check_idempotent_product_replay(
    existing: dict[str, Any],
    *,
    actor_id: Optional[str],
    operation: str,
    source_template_id: Optional[str],
    payload_hash: str,
) -> None:
    if (
        existing.get("stage4a_idempotency_actor_id") != actor_id
        or existing.get("stage4a_idempotency_operation") != operation
        or (existing.get("stage4a_idempotency_source_template_id") or None) != (source_template_id or None)
        or existing.get("stage4a_idempotency_payload_hash") != payload_hash
    ):
        raise WebstoreError(
            "stage4a_idempotency_conflict",
            "This product action key was already used for a different product action. Start a new action and try again.",
            409,
        )


def _association_ids(items: Any, key: str) -> set[str]:
    return {str(item.get(key)) for item in items or [] if isinstance(item, dict) and item.get(key)}


def _association_change_summary(before: list[dict[str, Any]], after: list[dict[str, Any]], *, key: str, label: str) -> tuple[str, str, Optional[str]]:
    before_ids = _association_ids(before, key)
    after_ids = _association_ids(after, key)
    added = sorted(after_ids - before_ids)
    removed = sorted(before_ids - after_ids)
    if added:
        return f"webstore.product_{label}_associated", f"Webstore product {label} associated", added[0]
    if removed:
        return f"webstore.product_{label}_removed", f"Webstore product {label} removed", removed[0]
    return f"webstore.product_{label}_updated", f"Webstore product {label} associations updated", None


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


def _require_platform_creator(user: dict) -> None:
    if not has_platform_admin_access(user, extra_permissions={PlatformPerm.PLATFORM_CREATOR.value}):
        raise WebstoreError("platform_creator_required", "Platform Creator access is required for platform starter templates", 403)


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


def _image_reference_for_response(
    product: dict,
    *,
    slot: str,
    image: dict[str, Any],
    public_slug: Optional[str] = None,
    include_private_id: bool = False,
) -> dict[str, Any]:
    result = {
        "slot": slot,
        "role": image.get("role") or slot,
        "alt_text": image.get("alt_text"),
        "file_name": image.get("file_name"),
        "content_type": image.get("content_type"),
        "recommended_dimensions": image.get("recommended_dimensions") or (
            "1600x1200 px or larger for primary images" if slot == "primary" else "1200x1200 px or larger for secondary images"
        ),
    }
    if image.get("url"):
        result["url"] = image["url"]
    elif public_slug and image.get("file_id"):
        result["url"] = f"/api/public/webstores/{public_slug}/product-images/{product['id']}/{slot}"
    if include_private_id and image.get("file_id"):
        result["file_id"] = image["file_id"]
        result["preview_url"] = f"/api/webstores/{product['webstore_id']}/setup-files/{image['file_id']}/preview"
    return {k: v for k, v in result.items() if v not in (None, "")}


def _product_image_map(product: dict) -> dict[str, dict[str, Any]]:
    images = product.get("customer_images") or {}
    if images:
        return {slot: dict(value or {}) for slot, value in images.items() if slot in CUSTOMER_IMAGE_SLOTS and value}
    legacy_ids = list(product.get("image_file_ids") or [])[:2]
    slots = ["primary", "secondary"]
    return {
        slots[index]: {"file_id": file_id, "role": slots[index], "alt_text": product.get("name"), "legacy": True}
        for index, file_id in enumerate(legacy_ids)
        if file_id
    }


def _image_slot_change_events(before: dict[str, Any], after: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    events: list[tuple[str, str, dict[str, Any]]] = []
    for slot in ("primary", "secondary"):
        before_image = dict((before or {}).get(slot) or {})
        after_image = dict((after or {}).get(slot) or {})
        if not before_image and not after_image:
            continue
        if before_image and after_image and before_image == after_image:
            continue
        if after_image and not before_image:
            action_word = "added"
            action = "webstore.product_image_added"
        elif before_image and not after_image:
            action_word = "removed"
            action = "webstore.product_image_removed"
        else:
            action_word = "replaced"
            action = "webstore.product_image_replaced"
        role = "Primary" if slot == "primary" else "Secondary"
        events.append(
            (
                action,
                f"{role} Webstore product image {action_word}",
                {
                    "image_association_id": f"{slot}_image",
                    "image_slot": slot,
                    "image_role": role,
                    "image_action": action_word,
                },
            )
        )
    return events


def _public_product(product: dict, *, public_slug: Optional[str] = None) -> dict:
    result = {
        "id": product.get("id"),
        "name": product.get("name"),
        "description": product.get("short_description") or product.get("description"),
        "full_description": product.get("full_description"),
        "category": product.get("category_name") or product.get("category"),
        "category_id": product.get("category_id"),
        "product_type": product.get("product_type"),
        "sku": product.get("sku"),
        "selling_price_cents": product.get("selling_price_cents"),
        "personalization_enabled": bool(product.get("personalization_enabled")),
        "images": [
            _image_reference_for_response(product, slot=slot, image=image, public_slug=public_slug)
            for slot, image in _product_image_map(product).items()
        ],
        "public": bool(product.get("public")),
        "featured": bool(product.get("featured")),
        "status": product.get("status"),
    }
    return {k: v for k, v in result.items() if v not in (None, "")}


def _portal_product(product: dict, *, public_slug: Optional[str] = None) -> dict:
    public = _public_product(product, public_slug=public_slug)
    public["webstore_id"] = product.get("webstore_id")
    return {k: v for k, v in public.items() if v not in (None, "")}


def _staff_product(product: dict, *, public_slug: Optional[str] = None) -> dict:
    data = serialize_doc(product)
    data["images"] = [
        _image_reference_for_response(product, slot=slot, image=image, public_slug=public_slug, include_private_id=True)
        for slot, image in _product_image_map(product).items()
    ]
    data["template_provenance"] = {
        "source_template_id": product.get("source_template_id"),
        "source_template_revision": product.get("source_template_revision"),
    }
    return data  # type: ignore[return-value]


def _public_store(store: dict, published_branding: Optional[dict[str, Any]] = None) -> dict:
    allowed = {
        "id",
        "name",
        "slug",
        "public_slug",
        "store_type",
        "status",
        "description",
        "deadline_at",
        "public_url",
        "checkout_enabled",
    }
    result = {k: v for k, v in store.items() if k in allowed}
    result["branding"] = published_branding or {}
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


async def _get_category(tenant_id: str, webstore_id: str, category_id: str) -> dict:
    category = await db.webstore_product_categories.find_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": category_id},
        {"_id": 0},
    )
    if not category:
        raise WebstoreError("webstore_category_not_found", "Webstore product category was not found", 404)
    return serialize_doc(category)


async def _setup_file_for_product_reference(tenant_id: str, webstore_id: str, file_id: str) -> dict:
    doc = await db.webstore_setup_files.find_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": file_id, "status": "active"},
        {"_id": 0},
    )
    if not doc:
        raise WebstoreError("product_file_not_found", "The selected product file was not found for this Webstore", 404)
    ext = str(doc.get("extension") or "").lower()
    if ext not in PRODUCT_IMAGE_EXTENSIONS:
        raise WebstoreError("product_image_type_not_allowed", "Product images must be JPG, PNG, WebP, or a safe SVG image", 400)
    if ext == "svg" and not doc.get("svg_sanitized"):
        raise WebstoreError("product_image_svg_not_safe", "SVG product images must pass the existing safe SVG policy", 400)
    return serialize_doc(doc)


async def _normalize_customer_images(tenant_id: str, webstore_id: str, images: Optional[dict[str, Any]]) -> dict[str, Any]:
    if images is None:
        return {}
    unknown = sorted(set(images.keys()) - CUSTOMER_IMAGE_SLOTS)
    if unknown:
        raise WebstoreError("too_many_product_image_slots", "Products support only primary and secondary customer-facing image slots", 400)
    normalized: dict[str, Any] = {}
    for slot in ("primary", "secondary"):
        image = dict(images.get(slot) or {})
        if not image:
            continue
        file_id = image.get("file_id")
        url = image.get("url")
        alt_text = _clean_optional_text(image.get("alt_text"), limit=200)
        if (file_id or url) and not alt_text:
            raise WebstoreError("product_image_alt_text_required", f"Add alternate text for the {slot} product image", 400)
        record = {
            "slot": slot,
            "role": _clean_optional_text(image.get("role"), limit=80) or slot,
            "alt_text": alt_text,
            "recommended_dimensions": image.get("recommended_dimensions") or (
                "1600x1200 px or larger" if slot == "primary" else "1200x1200 px or larger"
            ),
            "updated_at": _now_iso(),
        }
        if file_id:
            file_doc = await _setup_file_for_product_reference(tenant_id, webstore_id, str(file_id))
            record.update(
                {
                    "file_id": file_doc["id"],
                    "file_name": file_doc.get("file_name"),
                    "content_type": file_doc.get("detected_content_type") or file_doc.get("content_type"),
                    "file_version": file_doc.get("version"),
                }
            )
        elif url:
            record["url"] = str(url)
        normalized[slot] = {k: v for k, v in record.items() if v not in (None, "")}
    return normalized


def _reject_private_file_refs_for_platform_template(images: dict[str, Any], artwork: list[dict[str, Any]], mockups: Optional[list[dict[str, Any]]] = None) -> None:
    for image in (images or {}).values():
        if isinstance(image, dict) and image.get("file_id"):
            raise WebstoreError("platform_template_private_file_not_allowed", "Platform starter templates cannot reference tenant-private files", 400)
    for item in [*(artwork or []), *(mockups or [])]:
        if isinstance(item, dict) and (item.get("file_id") or item.get("artwork_id") or item.get("mockup_id")):
            raise WebstoreError("platform_template_private_file_not_allowed", "Platform starter templates cannot reference tenant-private files", 400)


def _has_private_image_file_refs(images: Any) -> bool:
    return any(isinstance(image, dict) and bool(image.get("file_id")) for image in (images or {}).values())


async def _normalize_product_category(user: dict, webstore_id: str, fields: dict[str, Any], existing: Optional[dict] = None) -> tuple[Optional[str], Optional[str], Optional[str]]:
    category_id = fields.get("category_id") if "category_id" in fields else (existing or {}).get("category_id")
    category_name = fields.get("category_name") if "category_name" in fields else (existing or {}).get("category_name")
    legacy_category = fields.get("category") if "category" in fields else (existing or {}).get("category")
    if category_id:
        category = await _get_category(user["tenant_id"], webstore_id, str(category_id))
        if category.get("status") != "active":
            raise WebstoreError("webstore_category_archived", "Archived categories cannot be assigned to products", 409)
        return category["id"], category["name"], category["name"]
    if category_name:
        return None, _clean_text(category_name, "category_name", limit=120), _clean_text(category_name, "category_name", limit=120)
    if legacy_category:
        cleaned = _clean_optional_text(legacy_category, limit=120)
        return None, cleaned, cleaned
    return None, None, None


async def _normalize_artwork_associations(user: dict, webstore_id: str, product_id: str, items: Optional[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    normalized = []
    for item in items or []:
        artwork_id = item.get("artwork_id") or item.get("id")
        if not artwork_id:
            continue
        art = await db.webstore_artwork_files.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": artwork_id},
            {"_id": 0},
        )
        if not art:
            raise WebstoreError("artwork_not_found", "Selected artwork was not found for this product", 404)
        if art.get("product_id") not in (None, "", product_id):
            raise WebstoreError("artwork_product_scope_mismatch", "Selected artwork belongs to a different product", 409)
        normalized.append({"artwork_id": artwork_id, "purpose": item.get("purpose") or art.get("purpose"), "note": _clean_optional_text(item.get("note"), limit=500)})
    return normalized


async def _normalize_mockup_associations(user: dict, webstore_id: str, product_id: str, items: Optional[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    normalized = []
    for item in items or []:
        mockup_id = item.get("mockup_id") or item.get("id")
        if not mockup_id:
            continue
        mockup = await db.webstore_mockups.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": mockup_id},
            {"_id": 0},
        )
        if not mockup:
            raise WebstoreError("mockup_not_found", "Selected mockup was not found for this product", 404)
        if mockup.get("product_id") not in (None, "", product_id):
            raise WebstoreError("mockup_product_scope_mismatch", "Selected mockup belongs to a different product", 409)
        normalized.append({
            "mockup_id": mockup_id,
            "purpose": item.get("purpose") or mockup.get("purpose"),
            "alt_text": _clean_optional_text(item.get("alt_text") or mockup.get("alt_text"), limit=200),
            "file_name": mockup.get("file_name"),
        })
    return normalized


async def _normalize_template_artwork_associations(user: dict, webstore_id: str, items: Optional[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    normalized = []
    for item in items or []:
        artwork_id = item.get("artwork_id") or item.get("id")
        if not artwork_id:
            continue
        art = await db.webstore_artwork_files.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": artwork_id},
            {"_id": 0},
        )
        if not art:
            raise WebstoreError("artwork_not_found", "Selected template artwork was not found for this Webstore", 404)
        if art.get("product_id"):
            raise WebstoreError("artwork_product_scope_mismatch", "Product-specific artwork cannot be used as a reusable template default", 409)
        normalized.append({"artwork_id": artwork_id, "purpose": item.get("purpose") or art.get("purpose"), "note": _clean_optional_text(item.get("note"), limit=500)})
    return normalized


async def _normalize_template_mockup_associations(user: dict, webstore_id: str, items: Optional[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    normalized = []
    for item in items or []:
        mockup_id = item.get("mockup_id") or item.get("id")
        if not mockup_id:
            continue
        mockup = await db.webstore_mockups.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": mockup_id},
            {"_id": 0},
        )
        if not mockup:
            raise WebstoreError("mockup_not_found", "Selected template mockup was not found for this Webstore", 404)
        if mockup.get("product_id"):
            raise WebstoreError("mockup_product_scope_mismatch", "Product-specific mockups cannot be used as reusable template defaults", 409)
        normalized.append({
            "mockup_id": mockup_id,
            "purpose": item.get("purpose") or mockup.get("purpose"),
            "alt_text": _clean_optional_text(item.get("alt_text") or mockup.get("alt_text"), limit=200),
            "file_name": mockup.get("file_name"),
        })
    return normalized


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
    scope = _clean_status(fields.get("scope"), TEMPLATE_SCOPES, "tenant", "template_scope")
    if scope == "platform":
        _require_platform_creator(user)
        tenant_id = PLATFORM_TEMPLATE_TENANT_ID
        _reject_private_file_refs_for_platform_template(
            fields.get("default_customer_images") or {},
            fields.get("default_artwork_associations") or [],
            fields.get("default_mockup_associations") or [],
        )
        default_customer_images = deepcopy(fields.get("default_customer_images") or {})
        default_artwork_associations = deepcopy(fields.get("default_artwork_associations") or [])
        default_mockup_associations = deepcopy(fields.get("default_mockup_associations") or [])
    else:
        _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
        tenant_id = user["tenant_id"]
        has_private_defaults = (
            _has_private_image_file_refs(fields.get("default_customer_images"))
            or bool(fields.get("default_artwork_associations"))
            or bool(fields.get("default_mockup_associations"))
        )
        if has_private_defaults and not fields.get("webstore_id"):
            raise WebstoreError(
                "template_webstore_required_for_private_assets",
                "Select a Webstore before using private uploaded files or assets in a tenant template",
                400,
            )
        default_customer_images = await _normalize_customer_images(user["tenant_id"], fields["webstore_id"], fields.get("default_customer_images")) if fields.get("webstore_id") else deepcopy(fields.get("default_customer_images") or {})
        default_artwork_associations = await _normalize_template_artwork_associations(user, fields["webstore_id"], fields.get("default_artwork_associations")) if fields.get("webstore_id") else []
        default_mockup_associations = await _normalize_template_mockup_associations(user, fields["webstore_id"], fields.get("default_mockup_associations")) if fields.get("webstore_id") else []
    status = _clean_status(fields.get("status"), TEMPLATE_STATUSES, "active" if fields.get("active", True) else "archived", "template_status")
    template = WebstoreProductTemplate(
        tenant_id=tenant_id,
        template_name=_clean_text(fields.get("template_name"), "template_name"),
        product_category=_clean_text(fields.get("product_category"), "product_category"),
        product_type=_clean_text(fields.get("product_type"), "product_type"),
        scope=scope,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        default_title=_clean_optional_text(fields.get("default_title"), limit=200),
        default_short_description=_clean_optional_text(fields.get("default_short_description"), limit=500),
        default_description=_clean_optional_text(fields.get("default_description")),
        suggested_category_name=_clean_optional_text(fields.get("suggested_category_name") or fields.get("product_category"), limit=120),
        production_method=_clean_optional_text(fields.get("production_method"), limit=120),
        supplier_source_info=_clean_optional_text(fields.get("supplier_source_info")),
        default_production_notes=_clean_optional_text(fields.get("default_production_notes")),
        default_customer_images=default_customer_images,
        default_artwork_associations=default_artwork_associations,
        default_mockup_associations=default_mockup_associations,
        best_store_types=fields.get("best_store_types") or [],
        default_variants=fields.get("default_variants") or [],
        mockup_supported=bool(fields.get("mockup_supported", True)),
        suggested_production_cost_cents=_clean_money(fields.get("suggested_production_cost_cents")),
        suggested_selling_price_cents=_clean_money(fields.get("suggested_selling_price_cents")),
        suggested_store_owner_share_cents=_clean_money(fields.get("suggested_store_owner_share_cents")),
        platform_fee_basis_points=int(fields.get("platform_fee_basis_points", 150)),
        internal_notes=_clean_optional_text(fields.get("internal_notes")),
        active=status == "active",
        created_by_user_id=user.get("id"),
        updated_by_user_id=user.get("id"),
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


async def list_templates(user: dict, *, active: Optional[bool] = None, scope: Optional[str] = None, status: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    status_filter = status
    if active is not None:
        status_filter = "active" if active else None
    query: dict[str, Any] = {"$or": [{"tenant_id": user["tenant_id"], "scope": {"$ne": "platform"}}, {"tenant_id": PLATFORM_TEMPLATE_TENANT_ID, "scope": "platform"}]}
    if status_filter:
        query["status"] = status_filter
    if scope:
        query["scope"] = scope
    cursor = db.webstore_product_templates.find(query, {"_id": 0}).sort([("scope", 1), ("template_name", 1)])
    items = [serialize_doc(doc) async for doc in cursor]
    return {"items": items, "total": len(items), "limit": 100, "skip": 0}


async def _get_template_for_staff(user: dict, template_id: str) -> dict:
    template = await db.webstore_product_templates.find_one(
        {"id": template_id, "$or": [{"tenant_id": user["tenant_id"]}, {"tenant_id": PLATFORM_TEMPLATE_TENANT_ID, "scope": "platform"}]},
        {"_id": 0},
    )
    if not template:
        raise WebstoreError("template_not_found", "Product template was not found", 404)
    return serialize_doc(template)


async def update_template(user: dict, template_id: str, fields: dict[str, Any]) -> dict:
    template = await _get_template_for_staff(user, template_id)
    if template.get("scope") == "platform" or template.get("tenant_id") == PLATFORM_TEMPLATE_TENANT_ID:
        _require_platform_creator(user)
        tenant_id = PLATFORM_TEMPLATE_TENANT_ID
    else:
        _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
        tenant_id = user["tenant_id"]
    expected = fields.get("expected_revision")
    if expected is None:
        raise WebstoreError("template_revision_required", "Reload this template before saving so we can verify you have the latest version.", 400)
    expected_revision = int(expected)
    updates: dict[str, Any] = {}
    text_fields = {
        "template_name": ("template_name", 200),
        "product_category": ("product_category", 120),
        "product_type": ("product_type", 120),
        "default_title": ("default_title", 200),
        "default_short_description": ("default_short_description", 500),
        "default_description": ("default_description", 2000),
        "suggested_category_name": ("suggested_category_name", 120),
        "production_method": ("production_method", 120),
        "supplier_source_info": ("supplier_source_info", 2000),
        "default_production_notes": ("default_production_notes", 2000),
        "internal_notes": ("internal_notes", 2000),
    }
    for key, (field, limit) in text_fields.items():
        if key in fields:
            if key in {"template_name", "product_category", "product_type"}:
                updates[field] = _clean_text(fields.get(key), field, limit=limit)
            else:
                updates[field] = _clean_optional_text(fields.get(key), limit=limit)
    for key in ("best_store_types", "default_variants"):
        if key in fields:
            updates[key] = deepcopy(fields.get(key) or [])
    if "default_artwork_associations" in fields:
        if template.get("scope") == "platform":
            _reject_private_file_refs_for_platform_template(
                fields.get("default_customer_images") or template.get("default_customer_images") or {},
                fields.get("default_artwork_associations") or [],
                fields.get("default_mockup_associations") or template.get("default_mockup_associations") or [],
            )
            updates["default_artwork_associations"] = deepcopy(fields.get("default_artwork_associations") or [])
        elif fields.get("webstore_id"):
            updates["default_artwork_associations"] = await _normalize_template_artwork_associations(user, fields["webstore_id"], fields.get("default_artwork_associations"))
        elif fields.get("default_artwork_associations"):
            raise WebstoreError(
                "template_webstore_required_for_private_assets",
                "Select a Webstore before using private uploaded files or assets in a tenant template",
                400,
            )
        else:
            updates["default_artwork_associations"] = []
    if "default_mockup_associations" in fields:
        if template.get("scope") == "platform":
            _reject_private_file_refs_for_platform_template(
                fields.get("default_customer_images") or template.get("default_customer_images") or {},
                fields.get("default_artwork_associations") or template.get("default_artwork_associations") or [],
                fields.get("default_mockup_associations") or [],
            )
            updates["default_mockup_associations"] = deepcopy(fields.get("default_mockup_associations") or [])
        elif fields.get("webstore_id"):
            updates["default_mockup_associations"] = await _normalize_template_mockup_associations(user, fields["webstore_id"], fields.get("default_mockup_associations"))
        elif fields.get("default_mockup_associations"):
            raise WebstoreError(
                "template_webstore_required_for_private_assets",
                "Select a Webstore before using private uploaded files or assets in a tenant template",
                400,
            )
        else:
            updates["default_mockup_associations"] = []
    if "default_customer_images" in fields:
        if template.get("scope") == "platform":
            _reject_private_file_refs_for_platform_template(
                fields.get("default_customer_images") or {},
                fields.get("default_artwork_associations") or template.get("default_artwork_associations") or [],
                fields.get("default_mockup_associations") or template.get("default_mockup_associations") or [],
            )
            updates["default_customer_images"] = deepcopy(fields.get("default_customer_images") or {})
        elif fields.get("webstore_id"):
            updates["default_customer_images"] = await _normalize_customer_images(user["tenant_id"], fields["webstore_id"], fields.get("default_customer_images"))
        elif _has_private_image_file_refs(fields.get("default_customer_images")):
            raise WebstoreError(
                "template_webstore_required_for_private_image",
                "Select a Webstore before using private uploaded files in a tenant template",
                400,
            )
        else:
            updates["default_customer_images"] = deepcopy(fields.get("default_customer_images") or {})
    for key in ("suggested_production_cost_cents", "suggested_selling_price_cents", "suggested_store_owner_share_cents"):
        if key in fields:
            updates[key] = _clean_money(fields.get(key))
    if "platform_fee_basis_points" in fields:
        bps = int(fields.get("platform_fee_basis_points") or 0)
        if bps < 0 or bps > 10000:
            raise WebstoreError("invalid_platform_fee", "Platform fee basis points must be between 0 and 10000", 400)
        updates["platform_fee_basis_points"] = bps
    if "status" in fields:
        updates["status"] = _clean_status(fields.get("status"), TEMPLATE_STATUSES, template.get("status", "active"), "template_status")
        updates["active"] = updates["status"] == "active"
    updates["revision"] = expected_revision + 1
    updates["updated_by_user_id"] = user.get("id")
    updates["updated_at"] = _now_iso()
    try:
        result = await db.webstore_product_templates.find_one_and_update(
            {"tenant_id": tenant_id, "id": template_id, "revision": expected_revision},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )
    except DuplicateKeyError:
        raise WebstoreError("duplicate_webstore_template", "An active template with that name already exists", 409)
    if not result:
        raise WebstoreError("template_revision_conflict", "This template changed after you opened it. Reload it before saving.", 409)
    action = "webstore.template_updated"
    summary = "Webstore product template updated"
    if updates.get("status") == "archived":
        action = "webstore.template_archived"
        summary = "Webstore product template archived"
    elif template.get("status") == "archived" and updates.get("status") == "active":
        action = "webstore.template_restored"
        summary = "Webstore product template restored"
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=template_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action=action,
        entity_type="webstore_product_template",
        entity_id=template_id,
        summary=summary,
    )
    return serialize_doc(result)


async def archive_template(user: dict, template_id: str, expected_revision: int) -> dict:
    template = await _get_template_for_staff(user, template_id)
    if int(expected_revision) != int(template.get("revision") or 1):
        raise WebstoreError("template_revision_conflict", "This template changed after you opened it. Reload it before archiving.", 409)
    if template.get("status") == "archived":
        return template
    return await update_template(user, template_id, {"status": "archived", "expected_revision": expected_revision})


async def restore_template(user: dict, template_id: str, expected_revision: int) -> dict:
    template = await _get_template_for_staff(user, template_id)
    if int(expected_revision) != int(template.get("revision") or 1):
        raise WebstoreError("template_revision_conflict", "This template changed after you opened it. Reload it before restoring.", 409)
    if template.get("status") == "active":
        return template
    return await update_template(user, template_id, {"status": "active", "expected_revision": expected_revision})


async def create_product(user: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    _reject_stage4a_publication_request(fields)
    _reject_stage4a_financial_variant_request(fields)
    idempotency_key = fields.get("idempotency_key")
    operation = "copy_template" if fields.get("source_template_id") else "create_blank"
    source_template_id = fields.get("source_template_id")
    payload_hash = _stage4a_product_create_fingerprint(fields, operation=operation, source_template_id=source_template_id)
    if idempotency_key:
        existing = await db.webstore_products.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "stage4a_idempotency_key": idempotency_key},
            {"_id": 0},
        )
        if existing:
            _check_idempotent_product_replay(
                existing,
                actor_id=user.get("id"),
                operation=operation,
                source_template_id=source_template_id,
                payload_hash=payload_hash,
            )
            return _staff_product(existing, public_slug=store.get("public_slug"))
    template = None
    if source_template_id:
        template = await _get_template_for_staff(user, source_template_id)
        if template.get("status") != "active" or not template.get("active", True):
            raise WebstoreError("template_not_available", "Product template is not active", 409)
    category_id, category_name, legacy_category = await _normalize_product_category(user, webstore_id, fields)
    customer_images = await _normalize_customer_images(user["tenant_id"], webstore_id, fields.get("customer_images"))
    if not customer_images and template:
        customer_images = deepcopy(template.get("default_customer_images") or {})
    merged = {
        "name": fields.get("name") or (template or {}).get("default_title") or (template or {}).get("template_name"),
        "short_description": fields.get("short_description") or (template or {}).get("default_short_description"),
        "full_description": fields.get("full_description") or fields.get("description") or (template or {}).get("default_description"),
        "description": fields.get("description") or (template or {}).get("default_short_description") or (template or {}).get("default_description"),
        "category": legacy_category or (template or {}).get("suggested_category_name") or (template or {}).get("product_category"),
        "product_type": fields.get("product_type") or (template or {}).get("product_type"),
        "production_method": fields.get("production_method") or (template or {}).get("production_method"),
        "supplier_source_info": fields.get("supplier_source_info") or (template or {}).get("supplier_source_info"),
        "production_notes": fields.get("production_notes") or (template or {}).get("default_production_notes"),
    }
    product = WebstoreProduct(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        source_template_id=source_template_id,
        source_template_revision=(template or {}).get("revision"),
        name=_clean_text(merged["name"], "name"),
        short_description=_clean_optional_text(merged.get("short_description"), limit=500),
        full_description=_clean_optional_text(merged.get("full_description")),
        description=_clean_optional_text(merged.get("description")),
        category_id=category_id,
        category_name=category_name or legacy_category or merged.get("category"),
        category=category_name or legacy_category or merged.get("category"),
        product_type=merged.get("product_type"),
        production_method=_clean_optional_text(merged.get("production_method"), limit=120),
        supplier_source_info=_clean_optional_text(merged.get("supplier_source_info")),
        fulfillment_notes=_clean_optional_text(fields.get("fulfillment_notes")),
        sku=None,
        production_cost_cents=0,
        selling_price_cents=0,
        store_owner_share_cents=0,
        platform_fee_basis_points=150,
        variants=[],
        personalization_enabled=False,
        image_file_ids=[],
        customer_images=customer_images,
        production_notes=_clean_optional_text(merged.get("production_notes")),
        public=False,
        featured=False,
        status="draft",
        created_by_user_id=user.get("id"),
        updated_by_user_id=user.get("id"),
    ).model_dump()
    if "artwork_associations" in fields:
        product["artwork_associations"] = await _normalize_artwork_associations(user, webstore_id, product["id"], fields.get("artwork_associations"))
    elif template:
        product["artwork_associations"] = deepcopy(template.get("default_artwork_associations") or [])
    if "mockup_associations" in fields:
        product["mockup_associations"] = await _normalize_mockup_associations(user, webstore_id, product["id"], fields.get("mockup_associations"))
    elif template:
        product["mockup_associations"] = deepcopy(template.get("default_mockup_associations") or [])
    if idempotency_key:
        product["stage4a_idempotency_key"] = idempotency_key
        product["stage4a_idempotency_actor_id"] = user.get("id")
        product["stage4a_idempotency_operation"] = operation
        product["stage4a_idempotency_source_template_id"] = source_template_id
        product["stage4a_idempotency_payload_hash"] = payload_hash
    try:
        await db.webstore_products.insert_one(prepare_for_mongo(product))
    except DuplicateKeyError:
        if not idempotency_key:
            raise
        existing = await db.webstore_products.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "stage4a_idempotency_key": idempotency_key},
            {"_id": 0},
        )
        if existing:
            _check_idempotent_product_replay(
                existing,
                actor_id=user.get("id"),
                operation=operation,
                source_template_id=source_template_id,
                payload_hash=payload_hash,
            )
            return _staff_product(existing, public_slug=store.get("public_slug"))
        raise WebstoreError("stage4a_idempotency_conflict", "This product action could not be safely retried. Start a new action and try again.", 409)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.product_created_from_template" if source_template_id else "webstore.product_created_blank",
        entity_type="webstore_product",
        entity_id=product["id"],
        summary="Webstore product created from a template" if source_template_id else "Blank Webstore product draft created",
        metadata={"source_template_id": product.get("source_template_id")},
    )
    return _staff_product(product, public_slug=store.get("public_slug"))


async def list_products(
    user: dict,
    *,
    webstore_id: str,
    public_only: bool = False,
    status: Optional[str] = None,
    category_id: Optional[str] = None,
    q: Optional[str] = None,
) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _get_store(user["tenant_id"], webstore_id)
    filters: dict[str, Any] = {"webstore_id": webstore_id}
    if public_only:
        filters.update({"public": True, "status": "active"})
    if status:
        filters["status"] = status
    if category_id:
        filters["category_id"] = category_id
    result = await products_repo.list(tenant_id=user["tenant_id"], filters=filters, sort=[("featured", -1), ("name", 1)])
    items = result["items"]
    if q:
        needle = _normalize_name(q)
        items = [item for item in items if needle in _normalize_name(item.get("name", ""))]
    return {**result, "items": [_staff_product(item, public_slug=store.get("public_slug")) for item in items], "total": len(items)}


async def list_artwork(user: dict, webstore_id: str, *, product_id: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    await _get_store(user["tenant_id"], webstore_id)
    query: dict[str, Any] = {"tenant_id": user["tenant_id"], "webstore_id": webstore_id}
    if product_id:
        query["product_id"] = {"$in": [None, "", product_id]}
    items = [
        {
            key: doc.get(key)
            for key in ("id", "product_id", "file_name", "file_type", "purpose", "artwork_status", "shop_approved_for_production")
            if doc.get(key) not in (None, "")
        }
        async for doc in db.webstore_artwork_files.find(query, {"_id": 0}).sort([("created_at", -1)])
    ]
    return {"items": items, "total": len(items)}


async def list_mockups(user: dict, webstore_id: str, *, product_id: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    await _get_store(user["tenant_id"], webstore_id)
    query: dict[str, Any] = {"tenant_id": user["tenant_id"], "webstore_id": webstore_id}
    if product_id:
        query["product_id"] = {"$in": [None, "", product_id]}
    items = [
        {
            key: doc.get(key)
            for key in ("id", "product_id", "artwork_id", "purpose", "alt_text", "status", "shop_approved")
            if doc.get(key) not in (None, "")
        }
        async for doc in db.webstore_mockups.find(query, {"_id": 0}).sort([("created_at", -1)])
    ]
    return {"items": items, "total": len(items)}


async def update_product(user: dict, webstore_id: str, product_id: str, fields: dict[str, Any], *, allow_system_transition: bool = False) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    product = await _get_product(user["tenant_id"], product_id, webstore_id)
    if not allow_system_transition:
        if STAGE4A_PUBLICATION_FIELDS & set(fields):
            raise WebstoreError(
                "stage4a_publication_not_available",
                "Product Foundation cannot approve, activate, publish, feature, or unpublish products. Those controls are handled in a later Webstore stage.",
                400,
            )
        _reject_stage4a_financial_variant_request(fields)
    expected = fields.get("expected_revision")
    if expected is None:
        raise WebstoreError("product_revision_required", "Reload this product before saving so we can verify you have the latest version.", 400)
    expected_revision = int(expected)
    updates: dict[str, Any] = {}
    text_fields = {
        "name": ("name", 200, True),
        "short_description": ("short_description", 500, False),
        "full_description": ("full_description", 2000, False),
        "description": ("description", 2000, False),
        "product_type": ("product_type", 120, False),
        "production_method": ("production_method", 120, False),
        "supplier_source_info": ("supplier_source_info", 2000, False),
        "fulfillment_notes": ("fulfillment_notes", 2000, False),
        "production_notes": ("production_notes", 2000, False),
    }
    for key, (field, limit, required) in text_fields.items():
        if key in fields:
            updates[field] = _clean_text(fields.get(key), field, limit=limit) if required else _clean_optional_text(fields.get(key), limit=limit)
    if {"category_id", "category_name", "category"} & set(fields):
        category_id, category_name, legacy_category = await _normalize_product_category(user, webstore_id, fields, product)
        updates.update({"category_id": category_id, "category_name": category_name, "category": legacy_category})
    if "customer_images" in fields:
        updates["customer_images"] = await _normalize_customer_images(user["tenant_id"], webstore_id, fields.get("customer_images"))
    if "artwork_associations" in fields:
        updates["artwork_associations"] = await _normalize_artwork_associations(user, webstore_id, product_id, fields.get("artwork_associations"))
    if "mockup_associations" in fields:
        updates["mockup_associations"] = await _normalize_mockup_associations(user, webstore_id, product_id, fields.get("mockup_associations"))
    if "public" in fields:
        updates["public"] = bool(fields.get("public"))
    if "featured" in fields:
        updates["featured"] = bool(fields.get("featured"))
    if "status" in fields:
        updates["status"] = _clean_status(fields.get("status"), PRODUCT_STATUSES, product.get("status", "draft"), "product_status")
    updates["revision"] = expected_revision + 1
    updates["updated_by_user_id"] = user.get("id")
    updates["updated_at"] = _now_iso()
    updated = await db.webstore_products.find_one_and_update(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": product_id, "revision": expected_revision},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not updated:
        raise WebstoreError("product_revision_conflict", "This product changed after you opened it. Reload it before saving.", 409)
    activity_events: list[tuple[str, str, dict[str, Any]]] = []
    if "customer_images" in updates:
        activity_events.extend(_image_slot_change_events(product.get("customer_images") or {}, updates.get("customer_images") or {}))
    if "artwork_associations" in updates:
        art_action, art_summary, artwork_id = _association_change_summary(
            product.get("artwork_associations") or [],
            updates.get("artwork_associations") or [],
            key="artwork_id",
            label="artwork",
        )
        activity_events.append((art_action, art_summary, {"artwork_id": artwork_id} if artwork_id else {}))
    if "mockup_associations" in updates:
        mock_action, mock_summary, mockup_id = _association_change_summary(
            product.get("mockup_associations") or [],
            updates.get("mockup_associations") or [],
            key="mockup_id",
            label="mockup",
        )
        activity_events.append((mock_action, mock_summary, {"mockup_id": mockup_id} if mockup_id else {}))
    action = "webstore.product_draft_updated"
    summary = "Webstore product draft updated"
    metadata: dict[str, Any] = {}
    if updates.get("status") == "archived":
        action = "webstore.product_archived"
        summary = "Webstore product archived"
    elif product.get("status") == "archived" and updates.get("status") == "draft":
        action = "webstore.product_restored"
        summary = "Webstore product restored to draft"
    elif len(activity_events) == 1:
        action, summary, metadata = activity_events[0]
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action=action,
        entity_type="webstore_product",
        entity_id=product_id,
        summary=summary,
        metadata={k: v for k, v in metadata.items() if v not in (None, "")},
    )
    for event_action, event_summary, metadata in activity_events:
        if event_action == action:
            continue
        await _audit(
            tenant_id=user["tenant_id"],
            webstore_id=webstore_id,
            actor_type="staff",
            actor_id=user.get("id"),
            actor_email=user.get("email"),
            action=event_action,
            entity_type="webstore_product",
            entity_id=product_id,
            summary=event_summary,
            metadata={k: v for k, v in metadata.items() if v not in (None, "")},
        )
    return _staff_product(updated, public_slug=store.get("public_slug"))


async def archive_product(user: dict, webstore_id: str, product_id: str, expected_revision: int) -> dict:
    product = await _get_product(user["tenant_id"], product_id, webstore_id)
    if int(expected_revision) != int(product.get("revision") or 1):
        raise WebstoreError("product_revision_conflict", "This product changed after you opened it. Reload it before archiving.", 409)
    if product.get("status") == "archived":
        return _staff_product(product)
    return await update_product(user, webstore_id, product_id, {"status": "archived", "expected_revision": expected_revision}, allow_system_transition=True)


async def restore_product(user: dict, webstore_id: str, product_id: str, expected_revision: int) -> dict:
    product = await _get_product(user["tenant_id"], product_id, webstore_id)
    if int(expected_revision) != int(product.get("revision") or 1):
        raise WebstoreError("product_revision_conflict", "This product changed after you opened it. Reload it before restoring.", 409)
    if product.get("status") == "draft":
        return _staff_product(product)
    if product.get("status") != "archived":
        raise WebstoreError("product_restore_not_archived", "Only archived products can be restored", 409)
    return await update_product(user, webstore_id, product_id, {"status": "draft", "public": False, "featured": False, "expected_revision": expected_revision}, allow_system_transition=True)


async def list_categories(user: dict, webstore_id: str, *, status: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    await _get_store(user["tenant_id"], webstore_id)
    query = {"tenant_id": user["tenant_id"], "webstore_id": webstore_id}
    if status:
        query["status"] = status
    items = []
    async for doc in db.webstore_product_categories.find(query, {"_id": 0}).sort([("status", 1), ("name", 1)]):
        item = serialize_doc(doc)
        item["product_count"] = await db.webstore_products.count_documents({"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "category_id": item["id"], "status": {"$ne": "archived"}})
        items.append(item)
    legacy_names = sorted({
        str(doc.get("category") or "").strip()
        async for doc in db.webstore_products.find(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "category_id": {"$in": [None, ""]}, "category": {"$nin": [None, ""]}},
            {"_id": 0, "category": 1},
        )
    })
    return {"items": items, "legacy_categories": legacy_names, "total": len(items)}


async def create_category(user: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    await _get_store(user["tenant_id"], webstore_id)
    name = _clean_text(fields.get("name"), "name", limit=120)
    category = WebstoreProductCategory(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        name=name,
        normalized_name=_normalize_name(name),
        description=_clean_optional_text(fields.get("description"), limit=500),
        created_by_user_id=user.get("id"),
        updated_by_user_id=user.get("id"),
    ).model_dump()
    try:
        await db.webstore_product_categories.insert_one(prepare_for_mongo(category))
    except DuplicateKeyError:
        raise WebstoreError("duplicate_webstore_category", "An active category with that name already exists for this Webstore", 409)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.category_created",
        entity_type="webstore_product_category",
        entity_id=category["id"],
        summary="Webstore product category created",
    )
    return serialize_doc(category)


async def update_category(user: dict, webstore_id: str, category_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    category = await _get_category(user["tenant_id"], webstore_id, category_id)
    expected = fields.get("expected_revision")
    if expected is None:
        raise WebstoreError("category_revision_required", "Reload this category before saving so we can verify you have the latest version.", 400)
    expected_revision = int(expected)
    updates: dict[str, Any] = {}
    if "name" in fields:
        updates["name"] = _clean_text(fields.get("name"), "name", limit=120)
        updates["normalized_name"] = _normalize_name(updates["name"])
    if "description" in fields:
        updates["description"] = _clean_optional_text(fields.get("description"), limit=500)
    if "status" in fields:
        updates["status"] = _clean_status(fields.get("status"), CATEGORY_STATUSES, category.get("status", "active"), "category_status")
    updates["revision"] = expected_revision + 1
    updates["updated_by_user_id"] = user.get("id")
    updates["updated_at"] = _now_iso()
    try:
        updated = await db.webstore_product_categories.find_one_and_update(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": category_id, "revision": expected_revision},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )
    except DuplicateKeyError:
        raise WebstoreError("duplicate_webstore_category", "An active category with that name already exists for this Webstore", 409)
    if not updated:
        raise WebstoreError("category_revision_conflict", "This category changed after you opened it. Reload it before saving.", 409)
    action = "webstore.category_updated"
    summary = "Webstore product category updated"
    if updates.get("status") == "archived":
        action = "webstore.category_archived"
        summary = "Webstore product category archived"
    elif category.get("status") == "archived" and updates.get("status") == "active":
        action = "webstore.category_restored"
        summary = "Webstore product category restored"
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action=action,
        entity_type="webstore_product_category",
        entity_id=category_id,
        summary=summary,
    )
    return serialize_doc(updated)


async def archive_category(user: dict, webstore_id: str, category_id: str, expected_revision: int) -> dict:
    category = await _get_category(user["tenant_id"], webstore_id, category_id)
    if int(expected_revision) != int(category.get("revision") or 1):
        raise WebstoreError("category_revision_conflict", "This category changed after you opened it. Reload it before archiving.", 409)
    if category.get("status") == "archived":
        return category
    count = await db.webstore_products.count_documents({"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "category_id": category_id, "status": {"$ne": "archived"}})
    if count:
        raise WebstoreError("category_in_use", "Move products out of this category before archiving it", 409)
    return await update_category(user, webstore_id, category_id, {"status": "archived", "expected_revision": expected_revision})


async def restore_category(user: dict, webstore_id: str, category_id: str, expected_revision: int) -> dict:
    category = await _get_category(user["tenant_id"], webstore_id, category_id)
    if int(expected_revision) != int(category.get("revision") or 1):
        raise WebstoreError("category_revision_conflict", "This category changed after you opened it. Reload it before restoring.", 409)
    if category.get("status") == "active":
        return category
    return await update_category(user, webstore_id, category_id, {"status": "active", "expected_revision": expected_revision})


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
    product_id = fields.get("product_id")
    if product_id:
        await _get_product(user["tenant_id"], product_id, webstore_id)
    file_id = fields.get("file_id") or fields.get("original_file_id")
    if file_id:
        file_doc = await db.webstore_setup_files.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": file_id, "status": "active"},
            {"_id": 0},
        )
        if not file_doc:
            raise WebstoreError("artwork_file_not_found", "Selected artwork file was not found for this Webstore", 404)
    art = WebstoreArtworkFile(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        product_id=product_id,
        uploaded_by_actor_type="staff",
        uploaded_by_id=user["id"],
        file_id=file_id,
        original_file_id=fields.get("original_file_id"),
        original_url=fields.get("original_url"),
        file_name=fields.get("file_name"),
        file_type=fields.get("file_type"),
        purpose=_clean_optional_text(fields.get("purpose"), limit=120),
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
    product_id = fields.get("product_id")
    if product_id:
        await _get_product(user["tenant_id"], product_id, webstore_id)
    file_id = fields.get("mockup_file_id")
    if file_id:
        await _setup_file_for_product_reference(user["tenant_id"], webstore_id, file_id)
    mockup = WebstoreMockup(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        product_id=product_id,
        artwork_id=fields.get("artwork_id"),
        mockup_file_id=fields.get("mockup_file_id"),
        generation_source=fields.get("generation_source", "manual"),
        purpose=_clean_optional_text(fields.get("purpose"), limit=120),
        alt_text=_clean_optional_text(fields.get("alt_text"), limit=200),
        staff_note=_clean_optional_text(fields.get("staff_note")),
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
    snapshot_products = [_public_product(p, public_slug=store.get("public_slug")) for p in products["items"]]
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
        _public_product(doc, public_slug=store.get("public_slug"))
        async for doc in db.webstore_products.find(
            {"tenant_id": store["tenant_id"], "webstore_id": store["id"], "status": "active", "public": True},
            {"_id": 0},
        ).sort([("featured", -1), ("name", 1)])
    ]
    published_branding = await branding_svc.published_branding_for_store(store)
    return {"webstore": _public_store(serialize_doc(store), published_branding), "products": products}


async def public_storefront(slug: str) -> dict:
    return await _storefront_by_slug(slug)


async def public_product_image(slug: str, product_id: str, slot: str) -> tuple[dict, bytes, str]:
    if slot not in CUSTOMER_IMAGE_SLOTS:
        raise WebstoreError("product_image_slot_not_found", "Product image was not found", 404)
    storefront = await _storefront_by_slug(slug)
    store = storefront["webstore"]
    full_store = await db.webstores.find_one({"public_slug": slug, "id": store["id"]}, {"_id": 0})
    product = await db.webstore_products.find_one(
        {
            "tenant_id": full_store["tenant_id"],
            "webstore_id": store["id"],
            "id": product_id,
            "status": "active",
            "public": True,
        },
        {"_id": 0},
    )
    if not product:
        raise WebstoreError("product_image_not_found", "Product image was not found", 404)
    image = _product_image_map(serialize_doc(product)).get(slot)
    if not image or not image.get("file_id"):
        raise WebstoreError("product_image_not_found", "Product image was not found", 404)
    file_doc = await db.webstore_setup_files.find_one(
        {"tenant_id": full_store["tenant_id"], "webstore_id": store["id"], "id": image["file_id"], "status": "active"},
        {"_id": 0},
    )
    if not file_doc:
        raise WebstoreError("product_image_not_found", "Product image was not found", 404)
    if str(file_doc.get("extension") or "").lower() not in PRODUCT_IMAGE_EXTENSIONS:
        raise WebstoreError("product_image_not_public", "Product image is not available publicly", 404)
    try:
        data, content_type = storage.get_bytes(file_doc["storage_key"])
    except FileNotFoundError:
        raise WebstoreError("product_image_not_found", "Product image was not found", 404)
    return serialize_doc(file_doc), data, file_doc.get("detected_content_type") or content_type


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
        _portal_product(doc, public_slug=store.get("public_slug"))
        async for doc in db.webstore_products.find({"tenant_id": identity["tenant_id"], "webstore_id": webstore_id}, {"_id": 0}).sort("name", 1)
    ]
    packet = None
    if store.get("launch_packet_id"):
        packet = await packets_repo.get(tenant_id=identity["tenant_id"], entity_id=store["launch_packet_id"])
    return {"webstore": _portal_store(store), "products": products, "launch_packet": _portal_launch_packet(packet)}
