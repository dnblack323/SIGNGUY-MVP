"""EC14 - Webstores service layer."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import re
import secrets
from typing import Any, Optional

from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.config import get_settings
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
    WebstoreChangeRequest,
    WebstoreLaunchPacket,
    WebstoreLedgerEntry,
    WebstoreLifecycleEvent,
    WebstoreMockup,
    WebstoreOwner,
    WebstorePacketApproval,
    WebstoreProduct,
    WebstoreProductCategory,
    WebstoreProductTemplate,
    WebstorePurchaseIntent,
    WebstoreQuestionnaireSubmission,
    WebstoreStripeConnectRecord,
    WebstoreTermsAcceptance,
)
from ..repositories.webstores import WebstoreRepository
from .activity import record_activity_with_audit
from .approvals_signatures_service import record_approval
from . import webstore_branding as branding_svc
from .entitlements import has_entitlement
from .email import record_processed_activity, send_email
from .portal_identity import create_portal_identity
from .sequence import next_number, next_record_number
from . import storage
from .webstore_payment_provider import ProviderAuthority, get_webstore_payment_provider, provider_configuration_status
from .webstore_type_requirements import default_store_settings, evaluate_type_requirements

WEBSTORES_FEATURE_KEY = "webstores"
LIVE_BLOCKING_STATUSES = {"closed", "archived"}
PRODUCT_PURCHASABLE_STATUSES = {"active"}
PLATFORM_TEMPLATE_TENANT_ID = "__platform__"
TEMPLATE_SCOPES = {"tenant", "platform"}
TEMPLATE_STATUSES = {"draft", "active", "archived"}
PRODUCT_STATUSES = {"draft", "planned", "incomplete", "ready", "active", "inactive", "archived"}
CATALOG_PRODUCT_STATUSES = {"planned", "incomplete", "ready", "active", "archived"}
CATEGORY_STATUSES = {"active", "archived"}
CUSTOMER_IMAGE_SLOTS = {"primary", "secondary"}
PRODUCT_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "svg"}
FULFILLMENT_METHODS = {"pickup", "shipping"}
STAGE4A_PUBLICATION_FIELDS = {"public", "featured"}
PRODUCT_APPROVAL_DECISIONS = {"approve", "request_changes", "reject"}
PRODUCT_APPROVAL_STATUSES = {"not_submitted", "pending_owner_approval", "approved", "rejected", "changes_requested", "superseded"}
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
PUBLIC_CHECKOUT_ENABLED = True
VALID_WEBSTORE_TYPES = set(WEBSTORE_TYPES)
VALID_WEBSTORE_STATUSES = set(WEBSTORE_LIFECYCLE_STATES)
PHASE6_LIFECYCLE_STATES = (
    "draft",
    "intake_pending",
    "setup_in_progress",
    "owner_review",
    "payment_setup_pending",
    "ready_to_launch",
    "live",
    "closed",
    "archived",
)
CURRENT_WEBSTORE_TERMS_VERSION = "webstore_terms_2026_07"
PAYMENT_READINESS_STATES = {"not_configured", "pending", "restricted", "ready", "unavailable", "not_applicable"}
CHANGE_REQUEST_CATEGORIES = {
    "branding",
    "product",
    "price",
    "description",
    "artwork",
    "mockup",
    "variant",
    "personalization",
    "fulfillment",
    "availability",
    "policy",
    "general",
}
CHANGE_REQUEST_STATUSES = {"open", "answered", "resolved", "declined", "superseded"}
MATERIAL_STORE_FIELDS = {
    "name",
    "description",
    "branding",
    "store_type",
    "deadline_at",
    "target_launch_at",
    "event_start_at",
    "event_location",
    "intended_launch_at",
    "intended_close_at",
    "launch_timezone",
    "required_terms_version",
    "store_settings",
    "direct_owner_payout_required",
    "stripe_onboarding_required",
}
MATERIAL_PRODUCT_FIELDS = {
    "name",
    "short_description",
    "full_description",
    "description",
    "category_id",
    "category_name",
    "category",
    "product_type",
    "fulfillment_notes",
    "fulfillment_methods",
    "default_fulfillment_method",
    "pickup_instructions",
    "shipping_cost_cents",
    "sku",
    "selling_price_cents",
    "store_owner_share_cents",
    "fundraiser_share_cents",
    "platform_fee_basis_points",
    "variants",
    "personalization_enabled",
    "personalization_fields",
    "bundle_items",
    "inventory_policy",
    "inventory_quantity",
    "launch_packet_include",
    "customer_images",
    "artwork_associations",
    "mockup_associations",
    "public",
    "featured",
    "status",
}

STARTER_PRODUCT_TEMPLATE_MARKER = "starter_common_webstore_template_2026_08"
STARTER_PRODUCT_TEMPLATES = [
    {
        "template_name": "T-shirt",
        "product_category": "apparel",
        "product_type": "tshirt",
        "default_title": "T-shirt",
        "default_short_description": "Comfortable custom printed T-shirt.",
        "default_description": "A classic short-sleeve T-shirt customized with your store artwork. Available in common adult sizes and selected colors.",
        "suggested_category_name": "Apparel",
        "production_method": "screen_print_or_dtf",
        "default_variants": [{"size": size, "color": "", "selling_price_cents": 2500} for size in ["S", "M", "L", "XL", "2XL"]],
        "suggested_selling_price_cents": 2500,
    },
    {
        "template_name": "Hoodie",
        "product_category": "apparel",
        "product_type": "hoodie",
        "default_title": "Hoodie",
        "default_short_description": "Warm pullover hoodie with custom artwork.",
        "default_description": "A soft pullover hoodie decorated with your store artwork. Good for fundraisers, teams, events, and company stores.",
        "suggested_category_name": "Apparel",
        "production_method": "screen_print_or_dtf",
        "default_variants": [{"size": size, "color": "", "selling_price_cents": 4500} for size in ["S", "M", "L", "XL", "2XL"]],
        "suggested_selling_price_cents": 4500,
    },
    {
        "template_name": "Hat",
        "product_category": "apparel",
        "product_type": "hat",
        "default_title": "Hat",
        "default_short_description": "Adjustable hat with logo or store artwork.",
        "default_description": "An adjustable cap decorated with a logo, patch, or printed design for everyday wear.",
        "suggested_category_name": "Accessories",
        "production_method": "embroidery_or_patch",
        "default_variants": [{"size": "One size", "color": "", "selling_price_cents": 2800}],
        "suggested_selling_price_cents": 2800,
    },
    {
        "template_name": "Decal / Sticker",
        "product_category": "decals",
        "product_type": "decal",
        "default_title": "Decal / Sticker",
        "default_short_description": "Custom decal or sticker using store artwork.",
        "default_description": "A durable decal or sticker printed from your approved artwork. Great as an add-on item for events and fundraisers.",
        "suggested_category_name": "Decals",
        "production_method": "print_cut",
        "default_variants": [{"size": "Small", "color": "Full color", "selling_price_cents": 600}, {"size": "Large", "color": "Full color", "selling_price_cents": 1000}],
        "suggested_selling_price_cents": 600,
    },
    {
        "template_name": "Banner",
        "product_category": "signs",
        "product_type": "banner",
        "default_title": "Banner",
        "default_short_description": "Custom event or sponsor banner.",
        "default_description": "A printed banner customized with your store artwork, event information, sponsor logos, or promotional message.",
        "suggested_category_name": "Signs",
        "production_method": "digital_print",
        "default_variants": [{"size": "2x4", "color": "Full color", "selling_price_cents": 6500}, {"size": "3x6", "color": "Full color", "selling_price_cents": 11000}],
        "suggested_selling_price_cents": 6500,
    },
    {
        "template_name": "Tumbler",
        "product_category": "promotional",
        "product_type": "tumbler",
        "default_title": "Tumbler",
        "default_short_description": "Drinkware with custom logo or campaign artwork.",
        "default_description": "A branded tumbler or cup using your approved store artwork. Useful for company stores, fundraisers, and promotional campaigns.",
        "suggested_category_name": "Drinkware",
        "production_method": "sublimation_or_vendor",
        "default_variants": [{"size": "20 oz", "color": "", "selling_price_cents": 3000}],
        "suggested_selling_price_cents": 3000,
    },
]
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
    "approved": {"launch_ready", "scheduled", "live", "archived"},
    "launch_ready": {"scheduled", "paused", "live", "archived"},
    "scheduled": {"launch_ready", "paused", "live", "closed", "archived"},
    "paused": {"launch_ready", "scheduled", "closed", "archived"},
    "live": {"closing_soon", "closed", "in_production", "completed", "archived"},
    "closing_soon": {"closed", "archived"},
    "closed": {"relaunch_ready", "archived"},
    "in_production": {"completed", "closed", "archived"},
    "completed": {"relaunch_ready", "archived"},
    "relaunch_ready": {"approved", "launch_ready", "scheduled", "live", "archived"},
    "archived": set(),
}
PHASE6_LIFECYCLE_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"intake_pending", "archived"},
    "intake_pending": {"setup_in_progress", "archived"},
    "setup_in_progress": {"owner_review", "archived"},
    "owner_review": {"setup_in_progress", "payment_setup_pending", "archived"},
    "payment_setup_pending": {"owner_review", "ready_to_launch", "archived"},
    "ready_to_launch": {"payment_setup_pending", "live", "closed", "archived"},
    "live": {"closed", "archived"},
    "closed": {"archived"},
    "archived": set(),
}
PHASE6_TO_INTERNAL_STATUS = {
    "draft": "draft",
    "intake_pending": "waiting_on_store_owner",
    "setup_in_progress": "questionnaire_submitted",
    "owner_review": "store_packet_generated",
    "payment_setup_pending": "approved",
    "ready_to_launch": "launch_ready",
    "live": "live",
    "closed": "closed",
    "archived": "archived",
}
INTERNAL_STATUS_TO_PHASE6 = {
    "draft": "draft",
    "questionnaire_sent": "intake_pending",
    "waiting_on_store_owner": "intake_pending",
    "questionnaire_submitted": "setup_in_progress",
    "ai_setup_ready": "setup_in_progress",
    "ai_product_suggestions_ready": "setup_in_progress",
    "artwork_needs_review": "setup_in_progress",
    "mockups_generated": "setup_in_progress",
    "mockups_approved": "setup_in_progress",
    "products_selected": "setup_in_progress",
    "store_packet_generated": "owner_review",
    "sent_for_approval": "owner_review",
    "changes_requested": "owner_review",
    "approved": "payment_setup_pending",
    "launch_ready": "ready_to_launch",
    "scheduled": "ready_to_launch",
    "paused": "ready_to_launch",
    "live": "live",
    "closing_soon": "live",
    "in_production": "live",
    "completed": "closed",
    "closed": "closed",
    "relaunch_ready": "closed",
    "archived": "archived",
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
packet_approvals_repo = WebstoreRepository("webstore_packet_approvals")
terms_acceptances_repo = WebstoreRepository("webstore_terms_acceptances")
change_requests_repo = WebstoreRepository("webstore_change_requests")
buyer_orders_repo = WebstoreRepository("webstore_buyer_orders")
ledger_repo = WebstoreRepository("webstore_ledger_entries")
activity_repo = WebstoreRepository("webstore_activity_events")
lifecycle_events_repo = WebstoreRepository("webstore_lifecycle_events")
ai_repo = WebstoreRepository("webstore_ai_usage_events")


class WebstoreError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _now_iso() -> str:
    return utc_now().isoformat()


def _json_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _require_timezone_iso(value: Any, field: str) -> Optional[str]:
    if value in (None, ""):
        return None
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WebstoreError("invalid_schedule_datetime", f"{field} must be an ISO datetime with timezone", 400) from exc
    if parsed.tzinfo is None:
        raise WebstoreError("invalid_schedule_timezone", f"{field} must include a timezone offset", 400)
    return parsed.astimezone(timezone.utc).isoformat()


def _owner_safe_terms_snapshot(store: dict, owner: dict, packet: Optional[dict] = None) -> dict[str, Any]:
    return {
        "terms_version": store.get("required_terms_version") or CURRENT_WEBSTORE_TERMS_VERSION,
        "store_name": store.get("name"),
        "store_type": store.get("store_type"),
        "store_owner_name": owner.get("name"),
        "store_owner_email": owner.get("email"),
        "platform_fee_percent": "Configured by the shop and snapshotted for backend-authoritative buyer checkout.",
        "stripe_processing_note": "Payment provider readiness is tracked separately; canonical Orders are created only after verified payment evidence.",
        "owner_share_formula": "Owner-visible product share is shown in cents in the launch packet when configured.",
        "payout_method": "Not configured in this batch unless an existing provider record says otherwise.",
        "store_deadline": store.get("deadline_at") or store.get("intended_close_at"),
        "pickup_instructions": (store.get("setup_profile") or {}).get("pickup_instructions"),
        "refund_policy_summary": (store.get("setup_profile") or {}).get("refund_policy_summary") or "Policy wording is managed by the sign shop before launch.",
        "approval_packet_version": (packet or {}).get("version"),
        "administrative_setup_required": True,
    }


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


def _collect_nested_file_ids(value: Any) -> set[str]:
    file_ids: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "file_id" and child not in (None, ""):
                file_ids.add(str(child))
            else:
                file_ids.update(_collect_nested_file_ids(child))
    elif isinstance(value, list):
        for child in value:
            file_ids.update(_collect_nested_file_ids(child))
    return file_ids


async def _validate_webstore_asset_refs(tenant_id: str, webstore_id: str, value: Any, *, field: str) -> None:
    file_ids = _collect_nested_file_ids(value)
    if not file_ids:
        return
    found = {
        doc["id"]
        async for doc in db.webstore_setup_files.find(
            {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": {"$in": sorted(file_ids)}, "status": "active"},
            {"_id": 0, "id": 1},
        )
    }
    missing = sorted(file_ids - found)
    if missing:
        raise WebstoreError(
            "webstore_asset_scope_mismatch",
            f"{field} references files that do not belong to this Webstore.",
            400,
        )


def _clean_money(value: Any, *, default: int = 0) -> int:
    if value in (None, ""):
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise WebstoreError("money_must_be_integer_cents", "Money values must be integer cents", 400)
    amount = int(value)
    if amount < 0:
        raise WebstoreError("negative_money_not_allowed", "Money values cannot be negative", 400)
    return amount


def _clean_basis_points(value: Any, *, default: int = 0) -> int:
    if value in (None, ""):
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise WebstoreError("basis_points_must_be_integer", "Fee percentages must be stored as integer basis points", 400)
    amount = int(value)
    if amount < 0 or amount > 10000:
        raise WebstoreError("basis_points_out_of_range", "Fee basis points must be between 0 and 10000", 400)
    return amount


def _normalize_fulfillment_methods(value: Any, *, default: Optional[list[str]] = None) -> list[str]:
    if value is None:
        return list(default or [])
    if not isinstance(value, list):
        raise WebstoreError("fulfillment_methods_must_be_list", "Fulfillment methods must be a list", 400)
    methods = []
    for raw in value:
        method = str(raw or "").strip().lower()
        if method not in FULFILLMENT_METHODS:
            raise WebstoreError("invalid_fulfillment_method", "Fulfillment methods must be pickup or shipping", 400)
        if method not in methods:
            methods.append(method)
    return methods


def _effective_fulfillment_methods(product: dict[str, Any]) -> list[str]:
    if "fulfillment_methods" in product:
        return _normalize_fulfillment_methods(product.get("fulfillment_methods"))
    # Older accepted product records predate product-level fulfillment. Keep
    # them readable with a conservative pickup default until staff configures
    # an explicit Stage 6 fulfillment list.
    legacy_method = product.get("fulfillment_method")
    return _normalize_fulfillment_methods([legacy_method] if legacy_method else ["pickup"])


def _public_cart_config(store: dict[str, Any]) -> dict[str, Any]:
    setup = store.get("setup_profile") or {}
    settings = store.get("store_settings") or {}
    cart = settings.get("cart") or {}
    donation = settings.get("donations") or settings.get("donation") or {}
    fundraiser_goal = setup.get("fundraiser_goal_amount") or cart.get("fundraiser_goal_cents") or 0
    donation_enabled = donation.get("enabled", cart.get("donation_enabled", setup.get("allow_checkout_donations")))
    if isinstance(donation_enabled, str):
        donation_enabled = donation_enabled.strip().lower() in {"yes", "true", "1", "on"}
    return {
        "fundraiser_goal_cents": int(fundraiser_goal or 0) if store.get("store_type") == "fundraiser" else 0,
        "donation_enabled": bool(donation_enabled) if store.get("store_type") == "fundraiser" else False,
        "donation_min_cents": int(donation.get("minimum_cents", cart.get("donation_min_cents", 0)) or 0),
        "donation_max_cents": int(donation.get("maximum_cents", cart.get("donation_max_cents", 0)) or 0),
        "promo_codes_enabled": bool(settings.get("promo_codes") or cart.get("promo_codes")),
    }


def _clean_quantity(value: Any, *, default: Optional[int] = None, minimum: int = 0) -> Optional[int]:
    if value in (None, ""):
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise WebstoreError("quantity_must_be_integer", "Inventory and bundle quantities must be whole numbers", 400)
    amount = int(value)
    if amount < minimum:
        raise WebstoreError("quantity_out_of_range", "Inventory and bundle quantities cannot be negative", 400)
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
            "catalog_publication_not_available",
            "Products cannot be made public from Batch 1 catalog setup. Public launch and checkout are handled in later Webstore batches.",
            400,
        )
    if fields.get("featured") is True:
        raise WebstoreError(
            "catalog_featured_not_available",
            "Products cannot be featured publicly from Batch 1 catalog setup. Public storefront controls are handled later.",
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


def _phase6_state_for_status(status: str) -> str:
    return INTERNAL_STATUS_TO_PHASE6.get(status or "draft", "draft")


def _validate_phase6_transition(current: str, requested: str) -> None:
    if requested not in PHASE6_LIFECYCLE_STATES:
        raise WebstoreError("invalid_lifecycle_state", "Unsupported Phase 6 Webstores lifecycle state", 400)
    if requested == current:
        return
    allowed = PHASE6_LIFECYCLE_TRANSITIONS.get(current, set())
    if requested not in allowed:
        raise WebstoreError("invalid_lifecycle_transition", f"Cannot move Webstore from {current} to {requested}", 409)


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


async def _record_lifecycle_event(
    *,
    tenant_id: str,
    webstore_id: str,
    from_status: Optional[str],
    to_status: str,
    from_state: Optional[str],
    to_state: str,
    actor_id: Optional[str],
    actor_email: Optional[str],
    reason: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    event = WebstoreLifecycleEvent(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        from_status=from_status,
        to_status=to_status,
        from_state=from_state,
        to_state=to_state,
        actor_id=actor_id,
        actor_email=actor_email,
        reason=reason,
        metadata=metadata or {},
    ).model_dump()
    await db.webstore_lifecycle_events.insert_one(prepare_for_mongo(event))
    return serialize_doc(event)


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


def _variant_option_signature(variant: dict[str, Any]) -> str:
    option_keys = ["size", "color", "style", "material"]
    option_values = [
        f"{key}:{_normalize_name(str(variant.get(key) or ''))}"
        for key in option_keys
        if variant.get(key) not in (None, "")
    ]
    explicit_options = variant.get("options") if isinstance(variant.get("options"), dict) else {}
    for key in sorted(explicit_options):
        value = explicit_options.get(key)
        if value not in (None, ""):
            option_values.append(f"{_normalize_name(str(key))}:{_normalize_name(str(value))}")
    return "|".join(option_values) or _normalize_name(str(variant.get("name") or variant.get("sku") or "default"))


def _public_variant(variant: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "id",
        "name",
        "size",
        "color",
        "style",
        "material",
        "options",
        "sku",
        "price_delta_cents",
        "selling_price_cents",
        "inventory_quantity",
        "available",
        "status",
    }
    return {k: v for k, v in variant.items() if k in allowed and v not in (None, "")}


def _public_personalization_field(field: dict[str, Any]) -> dict[str, Any]:
    allowed = {"key", "label", "type", "required", "choices", "placeholder", "max_length"}
    return {k: v for k, v in field.items() if k in allowed and v not in (None, "")}


def _product_setup_requirements(product: dict) -> list[dict[str, Any]]:
    has_images = bool(_product_image_map(product)) or bool(product.get("mockup_associations"))
    has_variants = bool(product.get("variants")) or bool(product.get("sku"))
    requirements = [
        {"key": "basic_information", "label": "Basic information", "complete": bool(product.get("name") and product.get("product_type"))},
        {"key": "catalog_organization", "label": "Category", "complete": bool(product.get("category_id") or product.get("category_name") or product.get("category"))},
        {"key": "pricing", "label": "Selling price", "complete": int(product.get("selling_price_cents") or 0) > 0},
        {"key": "images_or_mockups", "label": "Image or mockup", "complete": has_images},
        {"key": "options_or_sku", "label": "SKU or options", "complete": has_variants},
    ]
    if product.get("personalization_enabled"):
        requirements.append({"key": "personalization", "label": "Personalization prompts", "complete": bool(product.get("personalization_fields"))})
    return requirements


def _derived_catalog_status(product: dict) -> str:
    status = product.get("status") or "planned"
    if status in {"archived", "active", "ready", "incomplete", "planned"}:
        return status
    if status == "draft":
        requirements = _product_setup_requirements(product)
        complete = sum(1 for item in requirements if item["complete"])
        if complete == 0:
            return "planned"
        return "ready" if all(item["complete"] for item in requirements) else "incomplete"
    if status == "inactive":
        return "incomplete"
    return "planned"


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


def _public_product_is_eligible(product: dict) -> bool:
    if product.get("status") != "active" or product.get("public") is not True:
        return False
    if product.get("approval_status") != "approved":
        return False
    if product.get("approval_invalidated_at"):
        return False
    if int(product.get("approval_revision") or 0) != int(product.get("revision") or 1):
        return False
    return bool(_effective_fulfillment_methods(product))


def _public_product(product: dict, *, public_slug: Optional[str] = None) -> dict:
    public_variants = [
        variant
        for variant in (_public_variant(item) for item in product.get("variants") or [] if item.get("status", "active") != "archived")
        if variant
    ]
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
        "personalization_fields": [
            _public_personalization_field(field)
            for field in product.get("personalization_fields") or []
        ],
        "images": [
            _image_reference_for_response(product, slot=slot, image=image, public_slug=public_slug)
            for slot, image in _product_image_map(product).items()
        ],
        "public": bool(product.get("public")),
        "featured": bool(product.get("featured")),
        "status": product.get("status"),
        "fulfillment_methods": _effective_fulfillment_methods(product),
        "default_fulfillment_method": product.get("default_fulfillment_method") or (_effective_fulfillment_methods(product) or [None])[0],
        "pickup_instructions": product.get("pickup_instructions"),
        "shipping_cost_cents": int(product.get("shipping_cost_cents") or 0),
    }
    if public_variants:
        result["variants"] = public_variants
    return {k: v for k, v in result.items() if v not in (None, "")}


def _portal_product(product: dict, *, public_slug: Optional[str] = None) -> dict:
    public = _public_product(product, public_slug=public_slug)
    public["webstore_id"] = product.get("webstore_id")
    for key in ("approval_status", "approval_revision", "approval_decision_at", "approval_snapshot_hash"):
        if product.get(key) not in (None, ""):
            public[key] = product.get(key)
    return {k: v for k, v in public.items() if v not in (None, "")}


def _staff_product(product: dict, *, public_slug: Optional[str] = None) -> dict:
    data = serialize_doc(product)
    data["images"] = [
        _image_reference_for_response(product, slot=slot, image=image, public_slug=public_slug, include_private_id=True)
        for slot, image in _product_image_map(product).items()
    ]
    data["catalog_status"] = _derived_catalog_status(product)
    data["setup_status"] = data["catalog_status"]
    data["setup_requirements"] = _product_setup_requirements(product)
    data["launch_packet_eligible"] = bool(product.get("launch_packet_eligible")) or data["catalog_status"] in {"ready", "active"}
    data["launch_packet_include"] = bool(product.get("launch_packet_include")) and data["launch_packet_eligible"]
    data["template_provenance"] = {
        "source_template_id": product.get("source_template_id"),
        "source_template_revision": product.get("source_template_revision"),
    }
    return data  # type: ignore[return-value]


def _approval_history_row(doc: dict) -> dict:
    return {
        key: doc.get(key)
        for key in (
            "id",
            "parent_type",
            "parent_id",
            "parent_version",
            "action",
            "reason",
            "actor_type",
            "actor_ref",
            "actor_display",
            "snapshot_hash",
            "status",
            "created_at",
            "superseded_at",
            "superseded_reason",
        )
        if doc.get(key) not in (None, "")
    }


async def _approval_history(tenant_id: str, parent_type: str, parent_id: str) -> list[dict[str, Any]]:
    return [
        _approval_history_row(doc)
        async for doc in db.approvals.find(
            {"tenant_id": tenant_id, "parent_type": parent_type, "parent_id": parent_id},
            {"_id": 0, "snapshot": 0},
        ).sort([("created_at", -1)])
    ]


def _owner_safe_product_snapshot(product: dict, *, public_slug: Optional[str] = None, mockups: Optional[list[dict[str, Any]]] = None) -> dict[str, Any]:
    safe = _portal_product(product, public_slug=public_slug)
    safe["revision"] = int(product.get("revision") or 1)
    safe["snapshot_type"] = "webstore_product"
    safe["mockups"] = mockups or []
    return safe


def _owner_safe_mockup_snapshot(mockup: dict, product: Optional[dict] = None, *, public_slug: Optional[str] = None) -> dict[str, Any]:
    snapshot = {
        "id": mockup.get("id"),
        "webstore_id": mockup.get("webstore_id"),
        "product_id": mockup.get("product_id"),
        "artwork_id": mockup.get("artwork_id"),
        "generation_source": mockup.get("generation_source"),
        "purpose": mockup.get("purpose"),
        "alt_text": mockup.get("alt_text"),
        "status": mockup.get("status"),
        "approval_status": mockup.get("approval_status"),
        "approval_decision_at": mockup.get("approval_decision_at"),
        "snapshot_type": "webstore_mockup",
    }
    if product:
        snapshot["product"] = _portal_product(product, public_slug=public_slug)
    return {k: v for k, v in snapshot.items() if v not in (None, "")}


def _mockup_approval_snapshot(mockup: dict, product: Optional[dict] = None, *, public_slug: Optional[str] = None) -> dict[str, Any]:
    snapshot = _owner_safe_mockup_snapshot(mockup, product, public_slug=public_slug)
    for key in ("approval_status", "approval_decision_at"):
        snapshot.pop(key, None)
    if isinstance(snapshot.get("product"), dict):
        for key in ("approval_status", "approval_revision", "approval_decision_at", "approval_snapshot_hash"):
            snapshot["product"].pop(key, None)
    return snapshot


async def _current_mockups_for_product(tenant_id: str, webstore_id: str, product: dict) -> list[dict[str, Any]]:
    mockup_ids = _association_ids(product.get("mockup_associations") or [], "mockup_id")
    query: dict[str, Any] = {"tenant_id": tenant_id, "webstore_id": webstore_id, "status": {"$ne": "archived"}}
    if mockup_ids:
        query["$or"] = [{"id": {"$in": sorted(mockup_ids)}}, {"product_id": product["id"], "owner_visible": True}]
    else:
        query["product_id"] = product["id"]
        query["owner_visible"] = True
    rows: list[dict[str, Any]] = []
    async for doc in db.webstore_mockups.find(query, {"_id": 0}).sort([("created_at", -1)]):
        rows.append(_owner_safe_mockup_snapshot(serialize_doc(doc)))
    return rows


async def _product_approval_snapshot(tenant_id: str, webstore_id: str, product: dict, *, public_slug: Optional[str]) -> dict[str, Any]:
    mockups = []
    for mockup in await _current_mockups_for_product(tenant_id, webstore_id, product):
        frozen = dict(mockup)
        frozen.pop("approval_status", None)
        frozen.pop("approval_decision_at", None)
        mockups.append(frozen)
    snapshot = _owner_safe_product_snapshot(
        product,
        public_slug=public_slug,
        mockups=mockups,
    )
    for key in ("approval_status", "approval_revision", "approval_decision_at", "approval_snapshot_hash"):
        snapshot.pop(key, None)
    return snapshot


async def _invalidate_product_approval_if_needed(
    *,
    tenant_id: str,
    webstore_id: str,
    product: dict,
    reason: str,
    actor_type: str,
    actor_id: Optional[str],
    actor_email: Optional[str],
) -> None:
    if product.get("approval_status") not in {"pending_owner_approval", "approved"}:
        return
    now = _now_iso()
    await db.approvals.update_many(
        {"tenant_id": tenant_id, "parent_type": "webstore_product", "parent_id": product["id"], "status": "current"},
        {"$set": {"status": "superseded", "superseded_at": now, "superseded_reason": reason}},
    )
    await db.webstore_products.update_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": product["id"]},
        {
            "$set": {
                "approval_status": "superseded",
                "approval_invalidated_at": now,
                "approval_invalidated_reason": reason,
                "updated_at": now,
            }
        },
    )
    await _audit(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_email=actor_email,
        action="webstore.product_approval_superseded",
        entity_type="webstore_product",
        entity_id=product["id"],
        summary="Webstore product approval superseded by material product change",
        metadata={"reason": reason},
    )


def _public_store(
    store: dict,
    published_branding: Optional[dict[str, Any]] = None,
    fundraiser_progress: Optional[dict[str, Any]] = None,
    provider_authority: Optional[bool] = None,
) -> dict:
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
    provider_status = provider_configuration_status(get_settings())
    provider_ready = provider_status["provider_authority"] if provider_authority is None else provider_authority
    result["checkout_enabled"] = bool(result.get("checkout_enabled")) and PUBLIC_CHECKOUT_ENABLED and provider_ready
    result["checkout_unavailable_reason"] = None if result["checkout_enabled"] else provider_status["reason"]
    result["cart_config"] = _public_cart_config(store)
    if store.get("store_type") == "fundraiser":
        result["fundraiser_progress"] = fundraiser_progress or {
            "goal_cents": result["cart_config"]["fundraiser_goal_cents"],
            "completed_sales_cents": 0,
            "percent": 0,
            "over_goal": False,
            "paid_only": True,
        }
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
        "launch_packet_version",
        "owner_approved_packet_id",
        "owner_approved_packet_version",
        "owner_approval_invalidated_at",
        "owner_approval_invalidated_reason",
        "required_terms_version",
        "terms_acceptance_id",
        "terms_accepted_version",
        "terms_accepted_at",
        "setup_state",
        "setup_profile",
        "store_settings",
        "target_launch_at",
        "intended_launch_at",
        "intended_close_at",
        "launch_timezone",
        "event_start_at",
        "event_location",
    }
    result = {k: v for k, v in store.items() if k in allowed}
    provider_status = provider_configuration_status(get_settings())
    result["checkout_enabled"] = bool(result.get("checkout_enabled")) and PUBLIC_CHECKOUT_ENABLED and provider_status["provider_authority"]
    result["checkout_unavailable_reason"] = None if result["checkout_enabled"] else provider_status["reason"]
    return result


def _portal_launch_packet(packet: Optional[dict]) -> Optional[dict]:
    if not packet:
        return None
    allowed = {
        "id",
        "webstore_id",
        "status",
        "version",
        "snapshot",
        "snapshot_hash",
        "pricing_summary",
        "promotion_copy",
        "qr_code_url",
        "share_url",
        "delivery_status",
        "delivery_recipient_email",
        "delivery_portal_path",
        "sent_at",
        "delivered_at",
        "owner_decision_at",
        "change_request_reason",
        "superseded_at",
        "invalidated_at",
        "invalidated_reason",
    }
    return {k: v for k, v in packet.items() if k in allowed}


async def _portal_launch_packet_with_history(tenant_id: str, packet: Optional[dict]) -> Optional[dict]:
    safe = _portal_launch_packet(packet)
    if not safe:
        return None
    safe["approval_history"] = await _approval_history(tenant_id, "webstore_launch_packet", safe["id"])
    return safe


def _portal_change_request(item: dict) -> dict:
    allowed = {
        "id",
        "packet_id",
        "packet_version",
        "category",
        "affected_item_ref",
        "owner_comment",
        "status",
        "owner_visible_history",
        "resolved_at",
        "created_at",
        "updated_at",
    }
    return {k: v for k, v in item.items() if k in allowed}


def _portal_terms_acceptance(item: Optional[dict]) -> Optional[dict]:
    if not item:
        return None
    allowed = {
        "id",
        "terms_version",
        "accepted_at",
        "packet_id",
        "packet_version",
        "terms_snapshot",
        "fee_summary_snapshot",
        "status",
    }
    return {k: v for k, v in item.items() if k in allowed}


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


async def _get_mockup(tenant_id: str, mockup_id: str, webstore_id: Optional[str] = None) -> dict:
    filt = {"tenant_id": tenant_id, "id": mockup_id}
    if webstore_id:
        filt["webstore_id"] = webstore_id
    mockup = await db.webstore_mockups.find_one(filt, {"_id": 0})
    if not mockup:
        raise WebstoreError("webstore_mockup_not_found", "Webstore mockup not found", 404)
    return serialize_doc(mockup)


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


async def _ensure_unique_product_skus(
    *,
    tenant_id: str,
    webstore_id: str,
    product_id: str,
    sku: Optional[str],
    variants: list[dict[str, Any]],
) -> None:
    supplied = [str(value).strip() for value in [sku, *[variant.get("sku") for variant in variants]] if str(value or "").strip()]
    lowered = [_normalize_name(value) for value in supplied]
    if len(lowered) != len(set(lowered)):
        raise WebstoreError("duplicate_product_sku", "Product and variant SKUs must be unique within this product", 409)
    if not lowered:
        return
    async for doc in db.webstore_products.find(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": {"$ne": product_id}, "status": {"$ne": "archived"}},
        {"_id": 0, "sku": 1, "variants": 1},
    ):
        existing = [str(value).strip() for value in [doc.get("sku"), *[variant.get("sku") for variant in doc.get("variants") or []]] if str(value or "").strip()]
        if set(lowered) & {_normalize_name(value) for value in existing}:
            raise WebstoreError("duplicate_product_sku", "Product and variant SKUs must be unique within this Webstore", 409)


def _normalize_variants(variants: Optional[list[dict[str, Any]]], *, base_selling_price_cents: int) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    signatures: set[str] = set()
    for index, item in enumerate(variants or []):
        if not isinstance(item, dict):
            raise WebstoreError("invalid_variant", "Each variant must be an object", 400)
        variant: dict[str, Any] = {
            "id": _clean_optional_text(item.get("id"), limit=80) or f"variant-{index + 1}",
            "name": _clean_optional_text(item.get("name"), limit=120),
            "size": _clean_optional_text(item.get("size"), limit=80),
            "color": _clean_optional_text(item.get("color"), limit=80),
            "style": _clean_optional_text(item.get("style"), limit=80),
            "material": _clean_optional_text(item.get("material"), limit=80),
            "sku": _clean_optional_text(item.get("sku"), limit=120),
            "options": item.get("options") if isinstance(item.get("options"), dict) else {},
            "status": _clean_status(item.get("status"), {"active", "inactive", "archived"}, "active", "variant_status"),
            "available": bool(item.get("available", True)),
            "inventory_quantity": _clean_quantity(item.get("inventory_quantity"), default=None),
            "production_cost_cents": _clean_money(item.get("production_cost_cents"), default=0),
            "store_owner_share_cents": _clean_money(item.get("store_owner_share_cents"), default=0),
            "fundraiser_share_cents": _clean_money(item.get("fundraiser_share_cents"), default=0),
            "price_delta_cents": _clean_money(item.get("price_delta_cents"), default=0),
        }
        variant["selling_price_cents"] = _clean_money(item.get("selling_price_cents"), default=base_selling_price_cents + variant["price_delta_cents"])
        if variant["store_owner_share_cents"] + variant["fundraiser_share_cents"] > variant["selling_price_cents"]:
            raise WebstoreError("share_exceeds_price", "Owner and fundraiser shares cannot exceed the variant selling price", 400)
        signature = _variant_option_signature(variant)
        if signature in signatures:
            raise WebstoreError("duplicate_variant_combination", "Each size/color/options variant combination must be unique", 409)
        signatures.add(signature)
        normalized.append({k: v for k, v in variant.items() if v not in (None, "", {})})
    return normalized


def _normalize_personalization_fields(items: Optional[list[dict[str, Any]]], *, enabled: bool) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items or []):
        if not isinstance(item, dict):
            raise WebstoreError("invalid_personalization_field", "Each personalization prompt must be an object", 400)
        label = _clean_text(item.get("label"), "personalization_label", limit=120)
        key = _clean_optional_text(item.get("key"), limit=80) or _slug(label).replace("-", "_") or f"field_{index + 1}"
        field_type = str(item.get("type") or "text").strip().lower()
        if field_type not in {"text", "textarea", "select", "number"}:
            raise WebstoreError("invalid_personalization_type", "Personalization prompts support text, textarea, select, or number", 400)
        field = {
            "key": key,
            "label": label,
            "type": field_type,
            "required": bool(item.get("required", False)),
            "choices": [str(choice).strip() for choice in item.get("choices") or [] if str(choice).strip()][:20],
            "placeholder": _clean_optional_text(item.get("placeholder"), limit=120),
            "max_length": _clean_quantity(item.get("max_length"), default=None, minimum=1),
        }
        if field_type == "select" and not field["choices"]:
            raise WebstoreError("personalization_choices_required", "Select personalization prompts require at least one choice", 400)
        normalized.append({k: v for k, v in field.items() if v not in (None, "", [])})
    if enabled and not normalized:
        raise WebstoreError("personalization_fields_required", "Add at least one personalization prompt or turn personalization off", 400)
    keys = [field["key"] for field in normalized]
    if len(keys) != len(set(keys)):
        raise WebstoreError("duplicate_personalization_field", "Personalization prompt keys must be unique", 409)
    return normalized


async def _normalize_bundle_items(
    user: dict,
    webstore_id: str,
    product_id: str,
    items: Optional[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items or []:
        if not isinstance(item, dict):
            raise WebstoreError("invalid_bundle_item", "Each bundle item must be an object", 400)
        bundled_product_id = str(item.get("product_id") or "").strip()
        if not bundled_product_id:
            continue
        if bundled_product_id == product_id:
            raise WebstoreError("bundle_self_reference", "A product bundle cannot include itself", 409)
        if bundled_product_id in seen:
            raise WebstoreError("duplicate_bundle_item", "Bundle items must be unique", 409)
        bundled = await _get_product(user["tenant_id"], bundled_product_id, webstore_id)
        if bundled.get("status") == "archived":
            raise WebstoreError("bundle_item_archived", "Archived products cannot be included in bundles", 409)
        seen.add(bundled_product_id)
        normalized.append(
            {
                "product_id": bundled_product_id,
                "name_snapshot": bundled.get("name"),
                "quantity": _clean_quantity(item.get("quantity"), default=1, minimum=1),
                "sku_snapshot": bundled.get("sku"),
            }
        )
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
        store_settings=default_store_settings(_normalize_store_type(fields.get("store_type", "general")), fields.get("store_settings") or {}),
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
    await _record_lifecycle_event(
        tenant_id=user["tenant_id"],
        webstore_id=store["id"],
        from_status=None,
        to_status=store["status"],
        from_state=None,
        to_state=_phase6_state_for_status(store["status"]),
        actor_id=user["id"],
        actor_email=user.get("email"),
        reason="Webstore created",
        metadata={"store_type": store["store_type"]},
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
    result = await stores_repo.list(tenant_id=user["tenant_id"], filters=filters, sort=[("updated_at", -1)])
    items = []
    for item in result["items"]:
        safe_item = dict(item)
        type_requirements = evaluate_type_requirements(safe_item)
        payment = await _payment_readiness(safe_item)
        safe_item["checkout_enabled"] = bool(item.get("checkout_enabled")) and payment["provider_authority"]
        safe_item["checkout_unavailable_reason"] = (
            None if safe_item["checkout_enabled"] else payment["reason"]
        )
        safe_item["phase6_lifecycle_state"] = _phase6_state_for_status(safe_item.get("status", "draft"))
        safe_item["type_requirements"] = {
            "label": type_requirements["label"],
            "complete": type_requirements["complete"],
            "missing_count": len(type_requirements["missing"]),
        }
        safe_item["manager_action_required"] = (
            f"Complete {type_requirements['label']} requirements: {type_requirements['missing'][0]['label']}"
            if type_requirements["missing"]
            else None
        )
        items.append(safe_item)
    return {**result, "items": items}


async def list_activity(user: dict, webstore_id: str, *, limit: int = 30) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _get_store(user["tenant_id"], webstore_id)
    safe_limit = max(1, min(limit, 100))
    items = [
        serialize_doc(doc)
        async for doc in db.webstore_activity_events.find(
            {"tenant_id": user["tenant_id"], "webstore_id": store["id"]},
            {"_id": 0},
        ).sort([("created_at", -1)]).limit(safe_limit)
    ]
    return {"items": items}


async def get_webstore(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _ensure_public_slug(await _get_store(user["tenant_id"], webstore_id))
    products = await list_products(user, webstore_id=webstore_id)
    detail_products = []
    for product in products["items"]:
        product["approval_history"] = await _approval_history(user["tenant_id"], "webstore_product", product["id"])
        detail_products.append(product)
    packets = await packets_repo.list(tenant_id=user["tenant_id"], filters={"webstore_id": webstore_id}, sort=[("created_at", -1)], limit=10)
    packet_items = []
    for packet in packets["items"]:
        safe_packet = dict(packet)
        safe_packet["approval_history"] = await _approval_history(user["tenant_id"], "webstore_launch_packet", packet["id"])
        packet_items.append(safe_packet)
    terms_version = store.get("required_terms_version") or CURRENT_WEBSTORE_TERMS_VERSION
    terms = await _terms_acceptance(user["tenant_id"], webstore_id, terms_version)
    changes = [
        _portal_change_request(doc)
        async for doc in db.webstore_change_requests.find({"tenant_id": user["tenant_id"], "webstore_id": webstore_id}, {"_id": 0}).sort([("created_at", -1)])
    ]
    return {
        "webstore": store,
        "products": detail_products,
        "launch_packets": packet_items,
        "change_requests": changes,
        "phase6_lifecycle_state": _phase6_state_for_status(store.get("status", "draft")),
        "type_requirements": evaluate_type_requirements(store),
        "terms_acceptance": _portal_terms_acceptance(terms),
        "current_terms_version": terms_version,
    }


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
            "required_terms_version",
            "direct_owner_payout_required",
            "stripe_onboarding_required",
            "deadline_at",
            "target_launch_at",
            "event_start_at",
            "event_location",
            "intended_launch_at",
            "intended_close_at",
            "launch_timezone",
            "payment_readiness_status",
            "store_settings",
        }
    }
    if "name" in allowed:
        allowed["name"] = _clean_text(allowed["name"], "name")
    if "description" in allowed:
        allowed["description"] = _clean_optional_text(allowed["description"])
    if "branding" in allowed:
        await _validate_webstore_asset_refs(user["tenant_id"], webstore_id, allowed.get("branding") or {}, field="branding")
    for date_key in ("deadline_at", "target_launch_at", "event_start_at", "intended_launch_at", "intended_close_at"):
        if date_key in allowed:
            allowed[date_key] = _require_timezone_iso(allowed.get(date_key), date_key)
    if allowed.get("intended_launch_at") and allowed.get("intended_close_at"):
        if allowed["intended_close_at"] <= allowed["intended_launch_at"]:
            raise WebstoreError("invalid_schedule_window", "Intended close must be after intended launch", 400)
    elif ("intended_launch_at" in allowed or "intended_close_at" in allowed) and (
        allowed.get("intended_launch_at", store_before.get("intended_launch_at")) and allowed.get("intended_close_at", store_before.get("intended_close_at"))
    ):
        start = allowed.get("intended_launch_at", store_before.get("intended_launch_at"))
        end = allowed.get("intended_close_at", store_before.get("intended_close_at"))
        if end <= start:
            raise WebstoreError("invalid_schedule_window", "Intended close must be after intended launch", 400)
    if "launch_timezone" in allowed:
        allowed["launch_timezone"] = _clean_optional_text(allowed.get("launch_timezone"), limit=80)
    if "payment_readiness_status" in allowed:
        allowed["payment_readiness_status"] = _clean_status(allowed.get("payment_readiness_status"), PAYMENT_READINESS_STATES, "not_configured", "payment_readiness_status")
    if "store_settings" in allowed:
        allowed["store_settings"] = default_store_settings(
            allowed.get("store_type") or store_before.get("store_type"),
            allowed["store_settings"] if isinstance(allowed.get("store_settings"), dict) else {},
        )
    if "required_terms_version" in allowed:
        allowed["required_terms_version"] = _clean_text(allowed["required_terms_version"], "required_terms_version", limit=80)
        if allowed["required_terms_version"] != store_before.get("required_terms_version", CURRENT_WEBSTORE_TERMS_VERSION):
            allowed["terms_fee_acknowledged"] = False
            allowed["terms_acceptance_id"] = None
            allowed["terms_accepted_version"] = None
            allowed["terms_accepted_at"] = None
            allowed["terms_accepted_by_portal_identity_id"] = None
    if "store_type" in allowed:
        allowed["store_type"] = _normalize_store_type(allowed["store_type"])
        if allowed["store_type"] != store_before.get("store_type"):
            if "store_settings" not in allowed:
                allowed["store_settings"] = default_store_settings(allowed["store_type"], store_before.get("store_settings") or {})
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
    changed = {key for key, value in allowed.items() if value != store_before.get(key)}
    material_changed = changed & MATERIAL_STORE_FIELDS
    if material_changed:
        await _invalidate_packet_approval_if_needed(
            tenant_id=user["tenant_id"],
            webstore_id=webstore_id,
            actor_type="staff",
            actor_id=user.get("id"),
            actor_email=user.get("email"),
            reason=f"Material store fields changed: {', '.join(sorted(material_changed))}",
            changed_fields=material_changed,
        )
    if "required_terms_version" in changed:
        await _audit(
            tenant_id=user["tenant_id"],
            webstore_id=webstore_id,
            actor_type="staff",
            actor_id=user["id"],
            actor_email=user.get("email"),
            action="webstore.terms_version_superseded",
            entity_type="webstore",
            entity_id=webstore_id,
            summary="Webstore required Terms version changed",
            metadata={"from": store_before.get("required_terms_version"), "to": allowed.get("required_terms_version")},
        )
    return store or {}


async def set_webstore_status(user: dict, webstore_id: str, status: str, reason: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE if status in {"live", "launch_ready", "scheduled", "closed", "archived"} else Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    _validate_transition(store.get("status", "draft"), status)
    if status == "scheduled":
        raise WebstoreError(
            "webstore_scheduling_deferred",
            "Webstore scheduling is handled after the public storefront checkpoint.",
            409,
        )
    if status in {"launch_ready", "scheduled", "live"}:
        readiness = await launch_readiness(user, webstore_id)
        if not readiness["ready"]:
            raise WebstoreError("launch_gates_failed", "Webstore launch gates are not satisfied", 409)
    updates: dict[str, Any] = {"status": status}
    if status == "live":
        updates["launched_at"] = _now_iso()
        updates["checkout_enabled"] = bool(readiness["payment_readiness"]["provider_authority"])
    elif status == "launch_ready":
        updates["checkout_enabled"] = False
    elif status == "scheduled":
        updates["checkout_enabled"] = False
        updates["scheduled_at"] = _now_iso()
    elif status == "paused":
        updates["checkout_enabled"] = False
    elif status == "closed":
        updates["closed_at"] = _now_iso()
        updates["checkout_enabled"] = False
    elif status == "archived":
        updates["archived_at"] = _now_iso()
        updates["checkout_enabled"] = False
    updated = await stores_repo.update(tenant_id=user["tenant_id"], entity_id=webstore_id, updates=updates)
    from_state = _phase6_state_for_status(store.get("status", "draft"))
    to_state = _phase6_state_for_status(status)
    await _record_lifecycle_event(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        from_status=store.get("status"),
        to_status=status,
        from_state=from_state,
        to_state=to_state,
        actor_id=user["id"],
        actor_email=user.get("email"),
        reason=reason,
        metadata={"source": "status_route"},
    )
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


async def transition_webstore_lifecycle(user: dict, webstore_id: str, lifecycle_state: str, reason: Optional[str] = None) -> dict:
    requested_state = (lifecycle_state or "").strip().lower().replace("-", "_")
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE if requested_state in {"ready_to_launch", "live", "closed", "archived"} else Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    current_state = _phase6_state_for_status(store.get("status", "draft"))
    _validate_phase6_transition(current_state, requested_state)
    target_status = PHASE6_TO_INTERNAL_STATUS[requested_state]
    if requested_state in {"ready_to_launch", "live"}:
        readiness = await launch_readiness(user, webstore_id)
        if not readiness["ready"]:
            raise WebstoreError("launch_gates_failed", "Webstore launch gates are not satisfied", 409)
    updates: dict[str, Any] = {"status": target_status}
    if target_status == "live":
        updates["launched_at"] = _now_iso()
        updates["checkout_enabled"] = bool(readiness["payment_readiness"]["provider_authority"])
    elif target_status in {"launch_ready", "approved"}:
        updates["checkout_enabled"] = False
    elif target_status == "closed":
        updates["closed_at"] = _now_iso()
        updates["checkout_enabled"] = False
    elif target_status == "archived":
        updates["archived_at"] = _now_iso()
        updates["checkout_enabled"] = False
    updated = await stores_repo.update(tenant_id=user["tenant_id"], entity_id=webstore_id, updates=updates)
    event = await _record_lifecycle_event(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        from_status=store.get("status"),
        to_status=target_status,
        from_state=current_state,
        to_state=requested_state,
        actor_id=user["id"],
        actor_email=user.get("email"),
        reason=reason,
        metadata={"source": "phase6_lifecycle_route"},
    )
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal_webstore_owner",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.lifecycle.transitioned",
        entity_type="webstore",
        entity_id=webstore_id,
        summary=f"Webstore lifecycle changed from {current_state} to {requested_state}",
        metadata={"from_state": current_state, "to_state": requested_state, "from_status": store.get("status"), "to_status": target_status, "reason": reason},
    )
    return {"webstore": updated or {}, "lifecycle_state": requested_state, "event": event}


async def list_lifecycle_events(user: dict, webstore_id: str, *, limit: int = 30) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _get_store(user["tenant_id"], webstore_id)
    safe_limit = max(1, min(limit, 100))
    items = [
        serialize_doc(doc)
        async for doc in db.webstore_lifecycle_events.find(
            {"tenant_id": user["tenant_id"], "webstore_id": store["id"]},
            {"_id": 0},
        ).sort([("created_at", -1)]).limit(safe_limit)
    ]
    return {"items": items}


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
        platform_fee_basis_points=int(fields.get("platform_fee_basis_points", 0)),
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


async def ensure_starter_product_templates(tenant_id: str) -> None:
    for starter in STARTER_PRODUCT_TEMPLATES:
        existing = await db.webstore_product_templates.find_one(
            {"tenant_id": tenant_id, "template_name": starter["template_name"]},
            {"_id": 0, "id": 1},
        )
        if existing:
            continue
        template = WebstoreProductTemplate(
            tenant_id=tenant_id,
            scope="tenant",
            status="active",
            active=True,
            editable_by_shop=True,
            internal_notes=STARTER_PRODUCT_TEMPLATE_MARKER,
            **starter,
        ).model_dump()
        await db.webstore_product_templates.insert_one(prepare_for_mongo(template))


async def list_templates(user: dict, *, active: Optional[bool] = None, scope: Optional[str] = None, status: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    await ensure_starter_product_templates(user["tenant_id"])
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
    production_cost_cents = _clean_money(fields.get("production_cost_cents"), default=int((template or {}).get("suggested_production_cost_cents") or 0))
    selling_price_cents = _clean_money(fields.get("selling_price_cents"), default=int((template or {}).get("suggested_selling_price_cents") or 0))
    store_owner_share_cents = _clean_money(fields.get("store_owner_share_cents"), default=int((template or {}).get("suggested_store_owner_share_cents") or 0))
    fundraiser_share_cents = _clean_money(fields.get("fundraiser_share_cents"), default=0)
    if store_owner_share_cents + fundraiser_share_cents > selling_price_cents:
        raise WebstoreError("share_exceeds_price", "Owner and fundraiser shares cannot exceed the product selling price", 400)
    status = _clean_status(fields.get("status"), PRODUCT_STATUSES, "draft", "product_status")
    if "display_order" in fields:
        display_order = _clean_quantity(fields.get("display_order"), default=0) or 0
    else:
        last = await db.webstore_products.find_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id},
            {"_id": 0, "display_order": 1},
            sort=[("display_order", -1)],
        )
        display_order = int((last or {}).get("display_order") or 0) + 100
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
        sku=_clean_optional_text(fields.get("sku"), limit=120),
        production_cost_cents=production_cost_cents,
        selling_price_cents=selling_price_cents,
        store_owner_share_cents=store_owner_share_cents,
        fundraiser_share_cents=fundraiser_share_cents,
        platform_fee_basis_points=_clean_basis_points(fields.get("platform_fee_basis_points"), default=int((template or {}).get("platform_fee_basis_points") or 0)),
        fulfillment_methods=_normalize_fulfillment_methods(fields.get("fulfillment_methods")),
        default_fulfillment_method=(str(fields.get("default_fulfillment_method")).strip().lower() if fields.get("default_fulfillment_method") else None),
        pickup_instructions=_clean_optional_text(fields.get("pickup_instructions"), limit=2000),
        shipping_cost_cents=_clean_money(fields.get("shipping_cost_cents"), default=0),
        variants=[],
        personalization_enabled=bool(fields.get("personalization_enabled", False)),
        personalization_fields=[],
        bundle_items=[],
        inventory_policy=str(fields.get("inventory_policy") or "not_tracked")[:80],
        inventory_quantity=_clean_quantity(fields.get("inventory_quantity"), default=None),
        launch_packet_eligible=bool(fields.get("launch_packet_eligible", False)),
        launch_packet_include=bool(fields.get("launch_packet_include", False)),
        display_order=display_order,
        image_file_ids=[],
        customer_images=customer_images,
        production_notes=_clean_optional_text(merged.get("production_notes")),
        public=False,
        featured=False,
        status=status,
        created_by_user_id=user.get("id"),
        updated_by_user_id=user.get("id"),
    ).model_dump()
    variant_source = fields.get("variants") if "variants" in fields else (template or {}).get("default_variants")
    product["variants"] = _normalize_variants(variant_source, base_selling_price_cents=selling_price_cents)
    if product.get("default_fulfillment_method") and product["default_fulfillment_method"] not in product.get("fulfillment_methods"):
        raise WebstoreError("invalid_default_fulfillment_method", "The default fulfillment method must be enabled for this product", 400)
    product["personalization_fields"] = _normalize_personalization_fields(
        fields.get("personalization_fields"),
        enabled=bool(product.get("personalization_enabled")),
    )
    product["bundle_items"] = await _normalize_bundle_items(user, webstore_id, product["id"], fields.get("bundle_items"))
    await _ensure_unique_product_skus(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        product_id=product["id"],
        sku=product.get("sku"),
        variants=product.get("variants") or [],
    )
    if product.get("launch_packet_include") and not bool(product.get("launch_packet_eligible")):
        product["launch_packet_eligible"] = True
    if product.get("status") in {"ready", "active"}:
        missing = [item["label"] for item in _product_setup_requirements(product) if not item["complete"]]
        if missing:
            raise WebstoreError("product_not_ready", f"Complete product setup before marking it ready: {', '.join(missing)}", 409)
        product["launch_packet_eligible"] = True
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
    result = await products_repo.list(tenant_id=user["tenant_id"], filters=filters, sort=[("display_order", 1), ("featured", -1), ("name", 1)])
    items = result["items"]
    if q:
        needle = _normalize_name(q)
        items = [item for item in items if needle in _normalize_name(item.get("name", ""))]
    return {**result, "items": [_staff_product(item, public_slug=store.get("public_slug")) for item in items], "total": len(items)}


async def duplicate_product(user: dict, webstore_id: str, product_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    product = await _get_product(user["tenant_id"], product_id, webstore_id)
    expected_revision = int(fields.get("expected_revision") or 0)
    if expected_revision != int(product.get("revision") or 1):
        raise WebstoreError("product_revision_conflict", "This product changed after you opened it. Reload it before duplicating.", 409)
    source = deepcopy(product)
    for key in (
        "_id",
        "id",
        "created_at",
        "updated_at",
        "revision",
        "approval_status",
        "approval_revision",
        "approval_snapshot_hash",
        "approval_decision_at",
        "approval_decision_by_portal_identity_id",
        "approval_invalidated_at",
        "approval_invalidated_reason",
        "stage4a_idempotency_key",
        "stage4a_idempotency_actor_id",
        "stage4a_idempotency_operation",
        "stage4a_idempotency_source_template_id",
        "stage4a_idempotency_payload_hash",
        "name",
        "status",
        "public",
        "featured",
        "launch_packet_include",
        "display_order",
        "created_by_user_id",
        "updated_by_user_id",
        "sku",
        "variants",
    ):
        source.pop(key, None)
    last = await db.webstore_products.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id},
        {"_id": 0, "display_order": 1},
        sort=[("display_order", -1)],
    )
    duplicate = WebstoreProduct(
        **source,
        id=secrets.token_urlsafe(18),
        name=_clean_text(fields.get("name") or f"{product.get('name', 'Product')} Copy", "name"),
        sku=None,
        variants=[{**variant, "sku": None} for variant in source.get("variants") or []],
        status="draft",
        public=False,
        featured=False,
        launch_packet_include=False,
        approval_status="not_submitted",
        display_order=int((last or {}).get("display_order") or 0) + 100,
        created_by_user_id=user.get("id"),
        updated_by_user_id=user.get("id"),
    ).model_dump()
    await db.webstore_products.insert_one(prepare_for_mongo(duplicate))
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal_webstore_owner",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.product_duplicated",
        entity_type="webstore_product",
        entity_id=duplicate["id"],
        summary="Webstore product duplicated into a private draft",
        metadata={"source_product_id": product_id},
    )
    return _staff_product(duplicate, public_slug=store.get("public_slug"))


async def reorder_products(user: dict, webstore_id: str, product_ids: list[str]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    ids = [str(item) for item in product_ids if str(item or "").strip()]
    existing = [
        doc
        async for doc in db.webstore_products.find(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "status": {"$ne": "archived"}},
            {"_id": 0, "id": 1},
        )
    ]
    expected_ids = {doc["id"] for doc in existing}
    if set(ids) != expected_ids or len(ids) != len(expected_ids):
        raise WebstoreError("reorder_requires_all_active_products", "Reorder must include each non-archived product exactly once", 400)
    now = _now_iso()
    for index, current_id in enumerate(ids):
        await db.webstore_products.update_one(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": current_id},
            {"$set": {"display_order": (index + 1) * 100, "updated_at": now, "updated_by_user_id": user.get("id")}},
        )
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.products_reordered",
        entity_type="webstore",
        entity_id=webstore_id,
        summary="Webstore product display order updated",
        metadata={"product_ids": ids},
    )
    return await list_products(user, webstore_id=webstore_id)


async def submit_product_for_approval(user: dict, webstore_id: str, product_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    product = await _get_product(user["tenant_id"], product_id, webstore_id)
    expected_revision = int(fields.get("expected_revision") or 0)
    if expected_revision != int(product.get("revision") or 1):
        raise WebstoreError("product_revision_conflict", "This product changed after you opened it. Reload it before sending for approval.", 409)
    if product.get("status") == "archived":
        raise WebstoreError("product_archived", "Archived products cannot be sent for approval", 409)
    snapshot = await _product_approval_snapshot(user["tenant_id"], webstore_id, product, public_slug=store.get("public_slug"))
    snapshot_hash = _json_hash(snapshot)
    now = _now_iso()
    updated = await db.webstore_products.find_one_and_update(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": product_id, "revision": expected_revision},
        {
            "$set": {
                "approval_status": "pending_owner_approval",
                "approval_revision": expected_revision,
                "approval_snapshot_hash": snapshot_hash,
                "approval_invalidated_at": None,
                "approval_invalidated_reason": None,
                "updated_at": now,
                "updated_by_user_id": user.get("id"),
            }
        },
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not updated:
        raise WebstoreError("product_revision_conflict", "This product changed after you opened it. Reload it before sending for approval.", 409)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.product_submitted_for_approval",
        entity_type="webstore_product",
        entity_id=product_id,
        summary="Webstore product submitted for owner approval",
        metadata={"product_revision": expected_revision, "snapshot_hash": snapshot_hash, "comment": fields.get("comment")},
    )
    data = _staff_product(updated, public_slug=store.get("public_slug"))
    data["approval_history"] = await _approval_history(user["tenant_id"], "webstore_product", product_id)
    data["approval_snapshot"] = snapshot
    return data


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
            for key in ("id", "product_id", "artwork_id", "purpose", "alt_text", "status", "shop_approved", "owner_visible", "owner_approved", "approval_status", "approval_snapshot_hash", "approval_decision_at")
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
            _reject_stage4a_publication_request(fields)
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
    if "sku" in fields:
        updates["sku"] = _clean_optional_text(fields.get("sku"), limit=120)
    selling_price_cents = int(product.get("selling_price_cents") or 0)
    if "selling_price_cents" in fields:
        selling_price_cents = _clean_money(fields.get("selling_price_cents"), default=selling_price_cents)
        updates["selling_price_cents"] = selling_price_cents
    if "production_cost_cents" in fields:
        updates["production_cost_cents"] = _clean_money(fields.get("production_cost_cents"), default=int(product.get("production_cost_cents") or 0))
    if "store_owner_share_cents" in fields:
        updates["store_owner_share_cents"] = _clean_money(fields.get("store_owner_share_cents"), default=int(product.get("store_owner_share_cents") or 0))
    if "fundraiser_share_cents" in fields:
        updates["fundraiser_share_cents"] = _clean_money(fields.get("fundraiser_share_cents"), default=int(product.get("fundraiser_share_cents") or 0))
    if "platform_fee_basis_points" in fields:
        updates["platform_fee_basis_points"] = _clean_basis_points(fields.get("platform_fee_basis_points"), default=int(product.get("platform_fee_basis_points") or 0))
    if "fulfillment_methods" in fields:
        updates["fulfillment_methods"] = _normalize_fulfillment_methods(fields.get("fulfillment_methods"))
    if "default_fulfillment_method" in fields:
        default_method = str(fields.get("default_fulfillment_method") or "").strip().lower() or None
        updates["default_fulfillment_method"] = default_method
    if "pickup_instructions" in fields:
        updates["pickup_instructions"] = _clean_optional_text(fields.get("pickup_instructions"), limit=2000)
    if "shipping_cost_cents" in fields:
        updates["shipping_cost_cents"] = _clean_money(fields.get("shipping_cost_cents"), default=int(product.get("shipping_cost_cents") or 0))
    if "variants" in fields:
        updates["variants"] = _normalize_variants(fields.get("variants"), base_selling_price_cents=selling_price_cents)
    personalization_enabled = bool(product.get("personalization_enabled"))
    if "personalization_enabled" in fields:
        personalization_enabled = bool(fields.get("personalization_enabled"))
        updates["personalization_enabled"] = personalization_enabled
    if "personalization_fields" in fields or "personalization_enabled" in fields:
        updates["personalization_fields"] = _normalize_personalization_fields(
            fields.get("personalization_fields", product.get("personalization_fields") or []),
            enabled=personalization_enabled,
        )
    if "bundle_items" in fields:
        updates["bundle_items"] = await _normalize_bundle_items(user, webstore_id, product_id, fields.get("bundle_items"))
    if "inventory_policy" in fields:
        updates["inventory_policy"] = str(fields.get("inventory_policy") or "not_tracked")[:80]
    if "inventory_quantity" in fields:
        updates["inventory_quantity"] = _clean_quantity(fields.get("inventory_quantity"), default=None)
    if "display_order" in fields:
        updates["display_order"] = _clean_quantity(fields.get("display_order"), default=int(product.get("display_order") or 0)) or 0
    if "launch_packet_eligible" in fields:
        updates["launch_packet_eligible"] = bool(fields.get("launch_packet_eligible"))
    if "launch_packet_include" in fields:
        updates["launch_packet_include"] = bool(fields.get("launch_packet_include"))
    projected_owner_share = int(updates.get("store_owner_share_cents", product.get("store_owner_share_cents") or 0) or 0)
    projected_fundraiser_share = int(updates.get("fundraiser_share_cents", product.get("fundraiser_share_cents") or 0) or 0)
    if projected_owner_share + projected_fundraiser_share > selling_price_cents:
        raise WebstoreError("share_exceeds_price", "Owner and fundraiser shares cannot exceed the product selling price", 400)
    await _ensure_unique_product_skus(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        product_id=product_id,
        sku=updates.get("sku", product.get("sku")),
        variants=updates.get("variants", product.get("variants") or []),
    )
    if "public" in fields:
        updates["public"] = bool(fields.get("public"))
    if "featured" in fields:
        updates["featured"] = bool(fields.get("featured"))
    if "status" in fields:
        updates["status"] = _clean_status(fields.get("status"), PRODUCT_STATUSES, product.get("status", "draft"), "product_status")
    projected = {**product, **updates}
    if projected.get("default_fulfillment_method") and projected["default_fulfillment_method"] not in _normalize_fulfillment_methods(projected.get("fulfillment_methods")):
        raise WebstoreError("invalid_default_fulfillment_method", "The default fulfillment method must be enabled for this product", 400)
    if projected.get("status") in {"ready", "active"}:
        missing = [item["label"] for item in _product_setup_requirements(projected) if not item["complete"]]
        if missing:
            raise WebstoreError("product_not_ready", f"Complete product setup before marking it ready: {', '.join(missing)}", 409)
        updates["launch_packet_eligible"] = True
    if updates.get("launch_packet_include") and not bool(projected.get("launch_packet_eligible") or updates.get("launch_packet_eligible")):
        updates["launch_packet_eligible"] = True
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
    changed_material_fields = {
        key for key in (set(updates) & MATERIAL_PRODUCT_FIELDS)
        if key in updated and updated.get(key) != product.get(key)
    }
    if changed_material_fields:
        await _invalidate_product_approval_if_needed(
            tenant_id=user["tenant_id"],
            webstore_id=webstore_id,
            product=product,
            actor_type="staff",
            actor_id=user.get("id"),
            actor_email=user.get("email"),
            reason=f"Material product fields changed: {', '.join(sorted(changed_material_fields))}",
        )
        updated["approval_status"] = "superseded"
        updated["approval_invalidated_at"] = _now_iso()
        updated["approval_invalidated_reason"] = f"Material product fields changed: {', '.join(sorted(changed_material_fields))}"
        await _invalidate_packet_approval_if_needed(
            tenant_id=user["tenant_id"],
            webstore_id=webstore_id,
            actor_type="staff",
            actor_id=user.get("id"),
            actor_email=user.get("email"),
            reason=f"Material product fields changed: {', '.join(sorted(changed_material_fields))}",
            changed_fields=changed_material_fields,
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


async def submit_mockup_for_approval(user: dict, webstore_id: str, mockup_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    mockup = await _get_mockup(user["tenant_id"], mockup_id, webstore_id)
    if mockup.get("status") == "archived":
        raise WebstoreError("mockup_archived", "Archived mockups cannot be sent for approval", 409)
    product = await _get_product(user["tenant_id"], mockup["product_id"], webstore_id) if mockup.get("product_id") else None
    snapshot = _mockup_approval_snapshot(mockup, product, public_slug=store.get("public_slug"))
    snapshot_hash = _json_hash(snapshot)
    now = _now_iso()
    updated = await db.webstore_mockups.find_one_and_update(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": mockup_id},
        {
            "$set": {
                "approval_status": "pending_owner_approval",
                "approval_snapshot_hash": snapshot_hash,
                "owner_visible": True,
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.mockup_submitted_for_approval",
        entity_type="webstore_mockup",
        entity_id=mockup_id,
        summary="Webstore mockup submitted for owner approval",
        metadata={"snapshot_hash": snapshot_hash, "comment": fields.get("comment")},
    )
    result = serialize_doc(updated or mockup)
    result["approval_history"] = await _approval_history(user["tenant_id"], "webstore_mockup", mockup_id)
    result["approval_snapshot"] = snapshot
    return result


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


async def _included_packet_products(tenant_id: str, webstore_id: str, public_slug: Optional[str]) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    async for product in db.webstore_products.find(
        {
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "status": {"$ne": "archived"},
            "launch_packet_include": True,
        },
        {"_id": 0},
    ).sort([("featured", -1), ("category_name", 1), ("name", 1)]):
        product = serialize_doc(product)
        requirements = _product_setup_requirements(product)
        eligible = bool(product.get("launch_packet_eligible")) and _derived_catalog_status(product) in {"ready", "active"}
        safe_product = _public_product(product, public_slug=public_slug)
        safe_product["packet_ref"] = product["id"]
        safe_product["revision"] = product.get("revision")
        safe_product["launch_packet_eligible"] = eligible
        safe_product["owner_visible_financial_summary"] = {
            "store_owner_share_cents": int(product.get("store_owner_share_cents") or 0),
            "fundraiser_share_cents": int(product.get("fundraiser_share_cents") or 0),
        }
        mockup_ids = _association_ids(product.get("mockup_associations") or [], "mockup_id")
        mockups: list[dict[str, Any]] = []
        async for mockup in db.webstore_mockups.find(
            {
                "tenant_id": tenant_id,
                "webstore_id": webstore_id,
                "$or": [
                    {"id": {"$in": sorted(mockup_ids)}} if mockup_ids else {"id": "__none__"},
                    {"product_id": product["id"], "owner_visible": True},
                ],
            },
            {"_id": 0},
        ).sort([("created_at", 1)]):
            mockup = serialize_doc(mockup)
            if mockup.get("status") == "archived":
                continue
            if not (mockup.get("owner_visible") or mockup.get("shop_approved") or mockup.get("status") in {"shop_approved", "owner_approved"}):
                continue
            mockups.append(
                {
                    "id": mockup.get("id"),
                    "purpose": mockup.get("purpose"),
                    "alt_text": mockup.get("alt_text"),
                    "status": mockup.get("status"),
                    "approval_status": mockup.get("approval_status"),
                    "owner_visible": bool(mockup.get("owner_visible")),
                }
            )
        safe_product["mockups"] = mockups
        product_approval_current = (
            product.get("approval_status") == "approved"
            and int(product.get("approval_revision") or 0) == int(product.get("revision") or 1)
            and not product.get("approval_invalidated_at")
        )
        included_mockups_approved = all(
            mockup.get("approval_status") == "approved" or mockup.get("status") == "owner_approved"
            for mockup in mockups
        )
        requirements = [
            *requirements,
            {"key": "product_owner_approval", "label": "Product owner approval", "complete": product_approval_current},
            {"key": "mockup_owner_approval", "label": "Mockup owner approval", "complete": included_mockups_approved},
        ]
        safe_product["approval_status"] = product.get("approval_status")
        safe_product["approval_revision"] = product.get("approval_revision")
        safe_product["readiness"] = {
            "status": "ready" if eligible and all(item["complete"] for item in requirements) else "blocked",
            "requirements": requirements,
        }
        products.append({k: v for k, v in safe_product.items() if v not in (None, "")})
    return products


async def _payment_readiness(store: dict) -> dict[str, Any]:
    settings = get_settings()
    record = await db.webstore_stripe_connect_records.find_one(
        {"tenant_id": store.get("tenant_id"), "webstore_id": store.get("id"), "record_type": "connected_account"},
        {"_id": 0},
    )
    authority = _provider_authority_from_record(record, settings)
    provider_status = provider_configuration_status(settings, authority)
    state = provider_status["state"]
    return {
        "state": state,
        "label": provider_status["label"],
        "ready": bool(provider_status["provider_authority"]),
        "required": True,
        "provider_authority": bool(provider_status["provider_authority"]),
        "provider_mode": (record or {}).get("provider_mode") or getattr(settings, "stripe_mode", "test"),
        "provider_account_reference": (record or {}).get("connected_account_reference"),
        "requirements_currently_due": (record or {}).get("requirements_currently_due") or [],
        "reason": provider_status["reason"],
        "violations": provider_status["violations"],
        "stored_flags_ignored": True,
    }


async def _terms_acceptance(tenant_id: str, webstore_id: str, terms_version: str, portal_identity_id: Optional[str] = None) -> Optional[dict]:
    query: dict[str, Any] = {
        "tenant_id": tenant_id,
        "webstore_id": webstore_id,
        "terms_version": terms_version,
        "status": "current",
    }
    if portal_identity_id:
        query["portal_identity_id"] = portal_identity_id
    doc = await db.webstore_terms_acceptances.find_one(query, {"_id": 0}, sort=[("accepted_at", -1)])
    return serialize_doc(doc) if doc else None


async def _open_change_requests(tenant_id: str, webstore_id: str) -> list[dict[str, Any]]:
    return [
        serialize_doc(doc)
        async for doc in db.webstore_change_requests.find(
            {"tenant_id": tenant_id, "webstore_id": webstore_id, "status": {"$in": ["open", "answered"]}},
            {"_id": 0},
        ).sort([("created_at", 1)])
    ]


async def _assemble_launch_packet_snapshot(user: dict, store: dict, fields: dict[str, Any]) -> dict[str, Any]:
    store = await _ensure_public_slug(store)
    owner = await _get_owner(user["tenant_id"], store["owner_id"])
    published_branding = await branding_svc.published_branding_for_store(store)
    products = await _included_packet_products(user["tenant_id"], store["id"], store.get("public_slug"))
    qr_destination = store.get("public_url") or f"/p/webstores/{store.get('public_slug')}"
    qr_reference = {
        "destination": qr_destination,
        "status": "launch_destination",
        "download_url": f"/api/webstores/{store['id']}/qr-code-preview",
        "warning": "QR destination opens to buyers only after the Webstore lifecycle status is live.",
    }
    pricing_summary = {
        "product_count": len(products),
        "lowest_price_cents": min([int(p.get("selling_price_cents") or 0) for p in products], default=0),
        "highest_price_cents": max([int(p.get("selling_price_cents") or 0) for p in products], default=0),
        "store_owner_share_cents": sum(int((p.get("owner_visible_financial_summary") or {}).get("store_owner_share_cents") or 0) for p in products),
        "fundraiser_share_cents": sum(int((p.get("owner_visible_financial_summary") or {}).get("fundraiser_share_cents") or 0) for p in products),
    }
    branding_source = published_branding or store.get("branding") or {}
    await _validate_webstore_asset_refs(user["tenant_id"], store["id"], branding_source, field="branding")
    brand_basics = branding_source.get("brand_basics") or {}
    colors_fonts = branding_source.get("colors_fonts") or {}
    hero = branding_source.get("hero") or {}
    store_information = branding_source.get("store_information") or {}
    owner_preview = {
        "display_name": brand_basics.get("display_name") or store.get("name"),
        "logo": brand_basics.get("primary_logo") or {},
        "banner_image": hero.get("image") or {},
        "accent_color": colors_fonts.get("accent_color") or colors_fonts.get("primary_color"),
        "headline": hero.get("headline") or brand_basics.get("display_name") or store.get("name"),
        "greeting": store_information.get("welcome_text") or store_information.get("store_instructions") or "",
        "catalog_product_count": len(products),
    }
    snapshot = {
        "schema": "webstore_launch_packet_v2",
        "webstore": {
            "name": store.get("name"),
            "store_type": store.get("store_type"),
            "description": store.get("description"),
            "public_slug": store.get("public_slug"),
            "share_url": qr_destination,
            "deadline_at": store.get("deadline_at"),
            "target_launch_at": store.get("target_launch_at") or store.get("intended_launch_at"),
            "intended_close_at": store.get("intended_close_at"),
            "event_start_at": store.get("event_start_at"),
            "event_location": store.get("event_location"),
        },
        "store_owner": {
            "name": owner.get("name"),
            "email": owner.get("email"),
            "organization": owner.get("organization"),
        },
        "branding": branding_source,
        "owner_preview": {k: v for k, v in owner_preview.items() if v not in (None, "", {})},
        "products": products,
        "pricing_summary": pricing_summary,
        "terms": _owner_safe_terms_snapshot(store, owner),
        "qr_reference": qr_reference,
        "approval_instructions": "Review this exact packet version. Approve it or submit a structured change request.",
        "public_commerce_status": "Webstore catalog and approval preparation are available. Verified provider checkout is used when Stripe Connect is ready; canonical Order and Production handoff remains deferred to Stage 8.",
    }
    promotion_copy = _clean_optional_text(fields.get("promotion_copy")) or f"{store.get('name')} is being prepared for owner review."
    return {
        "snapshot": snapshot,
        "snapshot_hash": _json_hash(snapshot),
        "pricing_summary": pricing_summary,
        "promotion_copy": promotion_copy,
        "qr_code_url": fields.get("qr_code_url") or qr_reference["download_url"],
        "share_url": fields.get("share_url") or qr_destination,
    }


async def _invalidate_packet_approval_if_needed(
    *,
    tenant_id: str,
    webstore_id: str,
    actor_type: str,
    actor_id: Optional[str],
    actor_email: Optional[str],
    reason: str,
    changed_fields: set[str],
) -> None:
    store = await _get_store(tenant_id, webstore_id)
    if not store.get("owner_approved_packet_id") or store.get("owner_approval_invalidated_at"):
        return
    now = _now_iso()
    await db.webstore_packet_approvals.update_many(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "packet_id": store.get("owner_approved_packet_id"), "status": "current"},
        {"$set": {"status": "invalidated", "invalidated_at": now, "invalidated_reason": reason, "updated_at": now}},
    )
    await db.approvals.update_many(
        {"tenant_id": tenant_id, "parent_type": "webstore_launch_packet", "parent_id": store.get("owner_approved_packet_id"), "status": "current"},
        {"$set": {"status": "superseded", "superseded_at": now, "superseded_reason": reason, "updated_at": now}},
    )
    await db.webstore_launch_packets.update_one(
        {"tenant_id": tenant_id, "id": store.get("owner_approved_packet_id")},
        {"$set": {"status": "invalidated", "invalidated_at": now, "invalidated_reason": reason, "updated_at": now}},
    )
    await db.webstores.update_one(
        {"tenant_id": tenant_id, "id": webstore_id},
        {
            "$set": {
                "owner_approved_at": None,
                "owner_approved_by_portal_identity_id": None,
                "owner_approved_packet_id": None,
                "owner_approved_packet_version": None,
                "owner_approval_invalidated_at": now,
                "owner_approval_invalidated_reason": reason,
                "status": "store_packet_generated" if store.get("status") in {"approved", "launch_ready", "scheduled"} else store.get("status"),
                "updated_at": now,
            }
        },
    )
    await _audit(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_email=actor_email,
        action="webstore.packet_approval_invalidated",
        entity_type="webstore",
        entity_id=webstore_id,
        summary="Webstore owner packet approval invalidated by material change",
        metadata={"reason": reason, "fields": sorted(changed_fields)},
    )


async def generate_launch_packet(user: dict, webstore_id: str, fields: Optional[dict[str, Any]] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    fields = fields or {}
    store = await _ensure_public_slug(await _get_store(user["tenant_id"], webstore_id))
    assembled = await _assemble_launch_packet_snapshot(user, store, fields)
    products = assembled["snapshot"].get("products") or []
    if not products or any((product.get("readiness") or {}).get("status") != "ready" for product in products):
        raise WebstoreError(
            "launch_packet_products_not_ready",
            "Finish product setup and current product/mockup owner approvals before generating the final launch packet.",
            409,
        )
    branding_validation = branding_svc.validation_for_branding(store, assembled["snapshot"].get("branding") or {})
    if branding_validation["errors"]:
        raise WebstoreError(
            "launch_packet_branding_not_ready",
            "Publish owner-safe branding before generating the final launch packet.",
            409,
        )
    last = await db.webstore_launch_packets.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id},
        {"_id": 0, "version": 1, "status": 1},
        sort=[("version", -1)],
    )
    version = int((last or {}).get("version") or 0) + 1
    now = _now_iso()
    await db.webstore_launch_packets.update_many(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "status": {"$in": ["generated", "sent_for_approval", "delivered", "changes_requested", "rejected"]}},
        {"$set": {"status": "superseded", "superseded_at": now, "updated_at": now}},
    )
    packet = WebstoreLaunchPacket(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        version=version,
        status="generated",
        snapshot=assembled["snapshot"],
        snapshot_hash=assembled["snapshot_hash"],
        pricing_summary=assembled["pricing_summary"],
        promotion_copy=assembled["promotion_copy"],
        qr_code_url=assembled["qr_code_url"],
        share_url=assembled["share_url"],
        generated_by_user_id=user.get("id"),
    ).model_dump()
    await db.webstore_launch_packets.insert_one(prepare_for_mongo(packet))
    await stores_repo.update(
        tenant_id=user["tenant_id"],
        entity_id=webstore_id,
        updates={
            "status": "store_packet_generated",
            "launch_packet_id": packet["id"],
            "launch_packet_version": version,
            "owner_approval_invalidated_at": None,
            "owner_approval_invalidated_reason": None,
        },
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
        summary=f"Webstore launch packet version {version} generated",
        metadata={"version": version, "snapshot_hash": packet.get("snapshot_hash")},
    )
    return serialize_doc(packet)  # type: ignore[return-value]


async def send_launch_packet(user: dict, webstore_id: str, packet_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    owner = await _get_owner(user["tenant_id"], store["owner_id"])
    if owner.get("status") != "active" or not owner.get("portal_identity_id") or not owner.get("email"):
        raise WebstoreError("launch_packet_recipient_not_verified", "A verified Store Owner portal recipient is required before delivery", 409)
    packet = await packets_repo.get(tenant_id=user["tenant_id"], entity_id=packet_id)
    if not packet or packet["webstore_id"] != webstore_id:
        raise WebstoreError("launch_packet_not_found", "Launch packet not found", 404)
    if packet.get("status") in {"sent_for_approval", "delivered"} and packet.get("delivery_recipient_email") == owner.get("email"):
        return packet
    if packet.get("status") != "generated":
        raise WebstoreError("launch_packet_not_deliverable", "Only the current generated packet can be delivered", 409)
    if packet.get("id") != store.get("launch_packet_id"):
        raise WebstoreError("launch_packet_superseded", "Only the current packet version can be delivered", 409)
    idempotency_key = f"{webstore_id}:packet:{packet_id}:owner:{owner['id']}:v{packet.get('version')}"
    existing = await db.webstore_launch_packets.find_one({"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "delivery_idempotency_key": idempotency_key}, {"_id": 0})
    if existing:
        return serialize_doc(existing)
    portal_path = f"/portal/webstores/{webstore_id}"
    subject = f"{store.get('name')} launch packet is ready for review"
    body = (
        f"Your SignGuy Webstore launch packet version {packet.get('version')} is ready for review. "
        f"Open your secure Store Owner portal: {portal_path}"
    )
    ok, msg_id, error = send_email(to_email=owner["email"], subject=subject, body_text=body)
    email_log_id = f"webstore-packet-delivery-{packet_id}"
    await db.email_logs.update_one(
        {"tenant_id": user["tenant_id"], "id": email_log_id},
        {
            "$setOnInsert": {
                "id": email_log_id,
                "tenant_id": user["tenant_id"],
                "related_type": "general",
                "related_id": packet_id,
                "template": "general",
                "to_email": owner["email"],
                "from_email": "system@signguy.ai",
                "subject": subject,
                "body": body,
                "sent_by": user["id"],
                "attachment_file_ids": [],
                "idempotency_key": idempotency_key,
                "created_at": _now_iso(),
            },
            "$set": {
                "status": "sent" if ok else "skipped",
                "error_message": error,
                "sendgrid_message_id": msg_id,
                "updated_at": _now_iso(),
            },
        },
        upsert=True,
    )
    await record_processed_activity(
        tenant_id=user["tenant_id"],
        email_log_id=email_log_id,
        to_email=owner["email"],
        sendgrid_message_id=msg_id,
        related_entity_type="webstore_launch_packet",
        related_entity_id=packet_id,
        ok=ok,
        error=error,
    )
    now = _now_iso()
    updated = await db.webstore_launch_packets.find_one_and_update(
        {
            "tenant_id": user["tenant_id"],
            "id": packet_id,
            "status": "generated",
            "$or": [{"delivery_idempotency_key": {"$exists": False}}, {"delivery_idempotency_key": None}],
        },
        {
            "$set": {
                "status": "delivered",
                "sent_at": now,
                "delivered_at": now if ok else None,
                "delivered_by_user_id": user.get("id"),
                "delivery_recipient_email": owner["email"],
                "delivery_status": "sent" if ok else "test_capture_unavailable",
                "delivery_error": error,
                "delivery_idempotency_key": idempotency_key,
                "delivery_portal_path": portal_path,
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not updated:
        existing = await db.webstore_launch_packets.find_one({"tenant_id": user["tenant_id"], "id": packet_id}, {"_id": 0})
        return serialize_doc(existing or {})
    packet = serialize_doc(updated)
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
        summary=f"Webstore launch packet version {packet.get('version')} delivered for owner approval",
        metadata={"version": packet.get("version"), "delivery_status": packet.get("delivery_status"), "email_log_id": email_log_id},
    )
    return packet


async def _record_launch_packet_decision(
    *,
    identity: dict,
    packet: dict,
    decision: str,
    reason: Optional[str] = None,
) -> dict:
    action = "decline" if decision == "reject" else decision
    return await record_approval(
        tenant_id=identity["tenant_id"],
        parent_type="webstore_launch_packet",
        parent_id=packet["id"],
        parent_version=int(packet.get("version") or 1),
        action=action,
        reason=reason,
        actor_type="portal_webstore_owner",
        actor_ref=identity["id"],
        actor_display=identity.get("full_name") or identity.get("name") or identity.get("email"),
        snapshot_hash=packet.get("snapshot_hash") or _json_hash(packet.get("snapshot") or {}),
        snapshot=packet.get("snapshot") or {},
    )


async def owner_approve_launch_packet(identity: dict, webstore_id: str, packet_id: str, fields: Optional[dict[str, Any]] = None) -> dict:
    fields = fields or {}
    store = await _owner_portal_store(identity, webstore_id)
    packet = await packets_repo.get(tenant_id=identity["tenant_id"], entity_id=packet_id)
    if not packet or packet["webstore_id"] != webstore_id:
        raise WebstoreError("launch_packet_not_found", "Launch packet not found", 404)
    if packet.get("id") != store.get("launch_packet_id"):
        raise WebstoreError("launch_packet_superseded", "Only the current packet version can be approved", 409)
    if packet.get("status") not in {"sent_for_approval", "delivered", "owner_approved"}:
        raise WebstoreError("launch_packet_not_sent", "Launch packet must be delivered before owner approval", 409)
    if packet.get("invalidated_at") or packet.get("status") == "invalidated":
        raise WebstoreError("launch_packet_invalidated", "This launch packet was invalidated and cannot be approved", 409)
    blocking_changes = await _open_change_requests(identity["tenant_id"], webstore_id)
    if blocking_changes:
        raise WebstoreError("blocking_change_requests", "Resolve open owner change requests before approving this packet", 409)
    existing = await db.webstore_packet_approvals.find_one(
        {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id, "packet_id": packet_id, "portal_identity_id": identity["id"]},
        {"_id": 0},
    )
    if existing and existing.get("status") == "current":
        return packet
    now = _now_iso()
    comment = _clean_optional_text(fields.get("comment"), limit=2000)
    shared_approval = await _record_launch_packet_decision(
        identity=identity,
        packet=packet,
        decision="approve",
        reason=comment,
    )
    approval = WebstorePacketApproval(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        packet_id=packet_id,
        packet_version=int(packet.get("version") or 1),
        portal_identity_id=identity["id"],
        approver_name=identity.get("full_name") or identity.get("name"),
        approver_email=identity.get("email"),
        accepted_snapshot_hash=packet.get("snapshot_hash") or _json_hash(packet.get("snapshot") or {}),
        approved_at=now,
        audit_evidence={
            "portal_identity_id": identity["id"],
            "portal_type": identity.get("portal_type"),
            "packet_status_at_approval": packet.get("status"),
            "approval_id": shared_approval.get("id"),
        },
    ).model_dump()
    try:
        await db.webstore_packet_approvals.insert_one(prepare_for_mongo(approval))
    except DuplicateKeyError:
        existing = await db.webstore_packet_approvals.find_one(
            {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id, "packet_id": packet_id, "portal_identity_id": identity["id"]},
            {"_id": 0},
        )
        if existing and existing.get("status") == "current":
            return packet
        raise
    packet = await packets_repo.update(
        tenant_id=identity["tenant_id"],
        entity_id=packet_id,
        updates={"status": "owner_approved", "owner_decision_at": now, "owner_decision_by_portal_identity_id": identity["id"]},
    )
    await stores_repo.update(
        tenant_id=identity["tenant_id"],
        entity_id=webstore_id,
        updates={
            "status": "approved",
            "owner_approved_at": now,
            "owner_approved_by_portal_identity_id": identity["id"],
            "owner_approved_packet_id": packet_id,
            "owner_approved_packet_version": int((packet or {}).get("version") or 1),
            "owner_approval_invalidated_at": None,
            "owner_approval_invalidated_reason": None,
        },
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
    result = packet or {}
    if result:
        result["approval_history"] = await _approval_history(identity["tenant_id"], "webstore_launch_packet", packet_id)
    return result


async def owner_request_launch_packet_changes(identity: dict, webstore_id: str, packet_id: str, fields: dict[str, Any]) -> dict:
    store = await _owner_portal_store(identity, webstore_id)
    packet = await packets_repo.get(tenant_id=identity["tenant_id"], entity_id=packet_id)
    if not packet or packet["webstore_id"] != webstore_id:
        raise WebstoreError("launch_packet_not_found", "Launch packet not found", 404)
    if packet.get("id") != store.get("launch_packet_id") or packet.get("status") in {"superseded", "invalidated"}:
        raise WebstoreError("launch_packet_superseded", "Only the current packet version can receive change requests", 409)
    if packet.get("status") not in {"sent_for_approval", "delivered", "changes_requested"}:
        raise WebstoreError("launch_packet_not_sent", "Launch packet must be delivered before requesting changes", 409)
    category = _clean_status(fields.get("category"), CHANGE_REQUEST_CATEGORIES, "general", "change_request_category")
    comment = _clean_text(fields.get("comment"), "comment", limit=2000)
    if len(comment.strip()) < 5:
        raise WebstoreError("change_request_comment_required", "Add a meaningful change-request comment", 400)
    now = _now_iso()
    await _record_launch_packet_decision(
        identity=identity,
        packet=packet,
        decision="request_changes",
        reason=comment,
    )
    request = WebstoreChangeRequest(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        packet_id=packet_id,
        packet_version=int(packet.get("version") or 1),
        category=category,
        affected_item_ref=_clean_optional_text(fields.get("affected_item_ref"), limit=200),
        owner_comment=comment,
        portal_identity_id=identity["id"],
        owner_visible_history=[
            {
                "at": now,
                "actor": "store_owner",
                "status": "open",
                "message": comment,
            }
        ],
    ).model_dump()
    await db.webstore_change_requests.insert_one(prepare_for_mongo(request))
    await packets_repo.update(
        tenant_id=identity["tenant_id"],
        entity_id=packet_id,
        updates={"status": "changes_requested", "owner_decision_at": now, "change_request_reason": comment},
    )
    await stores_repo.update(tenant_id=identity["tenant_id"], entity_id=webstore_id, updates={"status": "changes_requested"})
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal",
        actor_id=identity["id"],
        actor_email=identity.get("email"),
        action="webstore.change_request_submitted",
        entity_type="webstore_change_request",
        entity_id=request["id"],
        summary="Store Owner submitted Webstore launch packet change request",
        metadata={"packet_id": packet_id, "packet_version": packet.get("version"), "category": category},
    )
    return _portal_change_request(serialize_doc(request))


async def owner_reject_launch_packet(identity: dict, webstore_id: str, packet_id: str, fields: dict[str, Any]) -> dict:
    store = await _owner_portal_store(identity, webstore_id)
    packet = await packets_repo.get(tenant_id=identity["tenant_id"], entity_id=packet_id)
    if not packet or packet["webstore_id"] != webstore_id:
        raise WebstoreError("launch_packet_not_found", "Launch packet not found", 404)
    if packet.get("id") != store.get("launch_packet_id") or packet.get("status") in {"superseded", "invalidated", "rejected"}:
        raise WebstoreError("launch_packet_superseded", "Only the current packet version can be rejected", 409)
    if packet.get("status") not in {"sent_for_approval", "delivered", "changes_requested"}:
        raise WebstoreError("launch_packet_not_sent", "Launch packet must be delivered before rejection", 409)
    comment = _clean_text(fields.get("comment"), "comment", limit=2000)
    now = _now_iso()
    await _record_launch_packet_decision(
        identity=identity,
        packet=packet,
        decision="reject",
        reason=comment,
    )
    packet = await packets_repo.update(
        tenant_id=identity["tenant_id"],
        entity_id=packet_id,
        updates={"status": "rejected", "owner_decision_at": now, "owner_decision_by_portal_identity_id": identity["id"], "change_request_reason": comment},
    )
    await stores_repo.update(tenant_id=identity["tenant_id"], entity_id=webstore_id, updates={"status": "changes_requested"})
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal",
        actor_id=identity["id"],
        actor_email=identity.get("email"),
        action="webstore.launch_packet_rejected",
        entity_type="webstore_launch_packet",
        entity_id=packet_id,
        summary="Store Owner rejected Webstore launch packet",
        metadata={"packet_version": (packet or {}).get("version")},
    )
    result = packet or {}
    if result:
        result["approval_history"] = await _approval_history(identity["tenant_id"], "webstore_launch_packet", packet_id)
    return result


async def staff_update_change_request(user: dict, webstore_id: str, request_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    request = await db.webstore_change_requests.find_one({"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": request_id}, {"_id": 0})
    if not request:
        raise WebstoreError("change_request_not_found", "Change request not found", 404)
    status = _clean_status(fields.get("status"), CHANGE_REQUEST_STATUSES, request.get("status") or "open", "change_request_status")
    if request.get("status") in {"resolved", "declined", "superseded"} and status != request.get("status"):
        raise WebstoreError("change_request_closed", "Closed change requests cannot be silently edited", 409)
    response = _clean_optional_text(fields.get("response"), limit=2000)
    if status in {"answered", "resolved", "declined"} and not response:
        raise WebstoreError("change_request_response_required", "A staff response is required", 400)
    now = _now_iso()
    history_entry = {
        "at": now,
        "actor": "staff",
        "status": status,
        "message": response,
    }
    updates: dict[str, Any] = {
        "status": status,
        "updated_at": now,
    }
    push: dict[str, Any] = {"owner_visible_history": history_entry}
    internal_note = _clean_optional_text(fields.get("internal_note"), limit=2000)
    if internal_note:
        push["staff_only_history"] = {"at": now, "actor": "staff", "message": internal_note}
    if status in {"resolved", "declined", "superseded"}:
        updates["resolved_at"] = now
    updated = await db.webstore_change_requests.find_one_and_update(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": request_id},
        {"$set": updates, "$push": push},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if status in {"resolved", "declined", "superseded"}:
        remaining = await _open_change_requests(user["tenant_id"], webstore_id)
        if not remaining and store.get("status") == "changes_requested":
            await stores_repo.update(tenant_id=user["tenant_id"], entity_id=webstore_id, updates={"status": "store_packet_generated"})
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.change_request_updated",
        entity_type="webstore_change_request",
        entity_id=request_id,
        summary=f"Webstore change request marked {status}",
        metadata={"status": status},
    )
    return _portal_change_request(serialize_doc(updated or request))


async def owner_accept_terms(identity: dict, webstore_id: str, fields: Optional[dict[str, Any]] = None) -> dict:
    fields = fields or {}
    store = await _owner_portal_store(identity, webstore_id)
    owner = await _get_owner(identity["tenant_id"], store["owner_id"])
    version = store.get("required_terms_version") or CURRENT_WEBSTORE_TERMS_VERSION
    requested_version = fields.get("terms_version") or version
    if requested_version != version:
        raise WebstoreError("terms_version_mismatch", "The current required Terms version must be accepted", 409)
    existing = await _terms_acceptance(identity["tenant_id"], webstore_id, version, identity["id"])
    if existing:
        return _portal_terms_acceptance(existing) or existing
    packet = None
    if store.get("launch_packet_id"):
        packet = await packets_repo.get(tenant_id=identity["tenant_id"], entity_id=store["launch_packet_id"])
    now = _now_iso()
    terms_snapshot = _owner_safe_terms_snapshot(store, owner, packet)
    fee_summary = {
        "terms_version": version,
        "payment_readiness": await _payment_readiness(store),
        "store_owner_share_cents": ((packet or {}).get("pricing_summary") or {}).get("store_owner_share_cents", 0),
        "fundraiser_share_cents": ((packet or {}).get("pricing_summary") or {}).get("fundraiser_share_cents", 0),
    }
    authority_snapshot = {"terms": terms_snapshot, "fee_summary": fee_summary}
    authority_snapshot_hash = _json_hash(authority_snapshot)
    acceptance = WebstoreTermsAcceptance(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        terms_version=version,
        portal_identity_id=identity["id"],
        acceptor_name=identity.get("full_name") or identity.get("name"),
        acceptor_email=identity.get("email"),
        accepted_at=now,
        packet_id=(packet or {}).get("id"),
        packet_version=(packet or {}).get("version"),
        terms_snapshot=terms_snapshot,
        fee_summary_snapshot=fee_summary,
        audit_evidence={
            "portal_identity_id": identity["id"],
            "portal_type": identity.get("portal_type"),
            "terms_snapshot_hash": authority_snapshot_hash,
        },
    ).model_dump()
    try:
        await db.webstore_terms_acceptances.insert_one(prepare_for_mongo(acceptance))
    except DuplicateKeyError:
        existing = await _terms_acceptance(identity["tenant_id"], webstore_id, version, identity["id"])
        if existing:
            return _portal_terms_acceptance(existing) or existing
        raise
    shared_approval = await record_approval(
        tenant_id=identity["tenant_id"],
        parent_type="webstore_terms_acceptance",
        parent_id=acceptance["id"],
        action="approve",
        reason=f"Accepted Webstore Terms version {version}",
        actor_type="portal_webstore_owner",
        actor_ref=identity["id"],
        actor_display=identity.get("full_name") or identity.get("name") or identity.get("email"),
        snapshot_hash=authority_snapshot_hash,
        snapshot=authority_snapshot,
    )
    acceptance["audit_evidence"]["approval_id"] = shared_approval.get("id")
    await db.webstore_terms_acceptances.update_one(
        {"tenant_id": identity["tenant_id"], "id": acceptance["id"]},
        {"$set": {"audit_evidence": acceptance["audit_evidence"], "updated_at": _now_iso()}},
    )
    await stores_repo.update(
        tenant_id=identity["tenant_id"],
        entity_id=webstore_id,
        updates={
            "terms_fee_acknowledged": True,
            "terms_acceptance_id": acceptance["id"],
            "terms_accepted_version": version,
            "terms_accepted_at": now,
            "terms_accepted_by_portal_identity_id": identity["id"],
        },
    )
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal",
        actor_id=identity["id"],
        actor_email=identity.get("email"),
        action="webstore.terms_accepted",
        entity_type="webstore_terms_acceptance",
        entity_id=acceptance["id"],
        summary="Store Owner accepted Webstore Terms",
        metadata={"terms_version": version, "packet_id": (packet or {}).get("id")},
    )
    return _portal_terms_acceptance(serialize_doc(acceptance)) or serialize_doc(acceptance)


async def launch_readiness(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _ensure_public_slug(await _get_store(user["tenant_id"], webstore_id))
    owner = await owners_repo.get(tenant_id=user["tenant_id"], entity_id=store["owner_id"])
    packet = await packets_repo.get(tenant_id=user["tenant_id"], entity_id=store["launch_packet_id"]) if store.get("launch_packet_id") else None
    included_products = await _included_packet_products(user["tenant_id"], webstore_id, store.get("public_slug"))
    open_changes = await _open_change_requests(user["tenant_id"], webstore_id)
    questionnaire = await submissions_repo.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "status": {"$in": ["submitted", "reviewed"]}}
    )
    terms_version = store.get("required_terms_version") or CURRENT_WEBSTORE_TERMS_VERSION
    terms = await _terms_acceptance(user["tenant_id"], webstore_id, terms_version)
    payment = await _payment_readiness(store)
    type_requirements = evaluate_type_requirements(store)
    branding = await branding_svc.published_branding_for_store(store)
    branding_source = branding or store.get("branding") or {}
    branding_validation = (
        branding_svc.validation_for_branding(store, branding_source)
        if branding_source
        else {"errors": ["Publish owner-safe branding with logo/color/greeting content before launch readiness."], "warnings": []}
    )
    branding_complete = bool(branding_source) and not branding_validation["errors"]
    entitlement_ready = await has_entitlement(tenant_id=user["tenant_id"], feature_key=store.get("entitlement_feature_key") or WEBSTORES_FEATURE_KEY)
    delivered = bool(packet and packet.get("status") in {"delivered", "sent_for_approval", "owner_approved"} and packet.get("id") == store.get("launch_packet_id"))
    approved = bool(
        packet
        and store.get("owner_approved_packet_id") == packet.get("id")
        and store.get("owner_approved_packet_version") == packet.get("version")
        and store.get("owner_approved_at")
        and not store.get("owner_approval_invalidated_at")
        and packet.get("status") == "owner_approved"
    )
    active_public_count = await db.webstore_products.count_documents(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "status": "active", "public": True, "selling_price_cents": {"$gt": 0}}
    )
    gates = [
        {
            "key": "entitlement",
            "state": "ready" if entitlement_ready else "blocked",
            "reason": "Webstores entitlement is active." if entitlement_ready else "Webstores entitlement is not active.",
            "severity": "blocking",
            "action": "Enable the Webstores feature entitlement.",
            "resource": {"type": "webstore", "id": webstore_id},
            "owner_wording": "The store workspace is not available yet.",
            "blocking": not entitlement_ready,
        },
        {
            "key": "owner_authorized",
            "state": "ready" if owner and owner.get("status") == "active" and owner.get("portal_identity_id") else "blocked",
            "reason": "Store Owner portal recipient is active." if owner and owner.get("status") == "active" and owner.get("portal_identity_id") else "Assign an active Store Owner portal recipient.",
            "severity": "blocking",
            "action": "Create or resend the Store Owner portal invitation.",
            "resource": {"type": "webstore_owner", "id": store.get("owner_id")},
            "owner_wording": "Store Owner access is not ready yet.",
            "blocking": not (owner and owner.get("status") == "active" and owner.get("portal_identity_id")),
        },
        {
            "key": "store_identity",
            "state": "ready" if store.get("name") and store.get("slug") and store.get("public_slug") else "blocked",
            "reason": "Store identity and safe public reference are present." if store.get("name") and store.get("slug") and store.get("public_slug") else "Complete store name, internal slug, and public slug.",
            "severity": "blocking",
            "action": "Complete store setup details.",
            "resource": {"type": "webstore", "id": webstore_id},
            "owner_wording": "Store details are still being prepared.",
            "blocking": not (store.get("name") and store.get("slug") and store.get("public_slug")),
        },
        {
            "key": "questionnaire_complete",
            "state": "ready" if questionnaire else "blocked",
            "reason": "Store Owner questionnaire has been submitted." if questionnaire else "Store Owner questionnaire must be submitted before launch readiness.",
            "severity": "blocking",
            "action": "Send or complete the Webstore questionnaire.",
            "resource": {"type": "webstore_questionnaire_submission", "id": (questionnaire or {}).get("id")},
            "owner_wording": "Store questionnaire answers are still needed.",
            "blocking": not bool(questionnaire),
        },
        {
            "key": "included_products_ready",
            "state": "ready" if included_products and all((p.get("readiness") or {}).get("status") == "ready" for p in included_products) else "blocked",
            "reason": "Included products, product approvals, and mockup approvals are ready for owner review." if included_products and all((p.get("readiness") or {}).get("status") == "ready" for p in included_products) else "Include at least one ready product with price, variants/SKU, customer-facing media, and current product/mockup approvals.",
            "severity": "blocking",
            "action": "Finish Product Setup and packet inclusion.",
            "resource": {"type": "webstore_products", "id": webstore_id},
            "owner_wording": "Products are still being prepared.",
            "blocking": not (included_products and all((p.get("readiness") or {}).get("status") == "ready" for p in included_products)),
        },
        {
            "key": "branding_preview_complete",
            "state": "ready" if branding_complete else "blocked",
            "reason": "Owner-safe branding preview content is complete." if branding_complete else "Complete owner-visible branding display content.",
            "severity": "blocking",
            "action": "Review the Branding tab and complete the owner-safe preview.",
            "resource": {"type": "webstore_branding", "id": webstore_id},
            "owner_wording": "Store branding and welcome content are still being prepared.",
            "blocking": not branding_complete,
            "requirements": branding_validation,
        },
        {
            "key": "packet_generated",
            "state": "ready" if packet else "blocked",
            "reason": f"Launch packet version {packet.get('version')} exists." if packet else "Generate a Launch Packet.",
            "severity": "blocking",
            "action": "Generate the packet from current setup.",
            "resource": {"type": "webstore_launch_packet", "id": (packet or {}).get("id")},
            "owner_wording": "Your launch packet is not ready yet.",
            "blocking": not bool(packet),
        },
        {
            "key": "packet_delivered",
            "state": "ready" if delivered else "blocked",
            "reason": "Current packet version was delivered to the Store Owner portal." if delivered else "Deliver the current packet version to the Store Owner.",
            "severity": "blocking",
            "action": "Send the current packet version.",
            "resource": {"type": "webstore_launch_packet", "id": (packet or {}).get("id")},
            "owner_wording": "Your launch packet has not been delivered yet.",
            "blocking": not delivered,
        },
        {
            "key": "packet_approved",
            "state": "ready" if approved else "blocked",
            "reason": f"Store Owner approved packet version {packet.get('version')}." if approved else (store.get("owner_approval_invalidated_reason") or "Store Owner approval is required for the current packet version."),
            "severity": "blocking",
            "action": "Have the Store Owner approve the current packet version.",
            "resource": {"type": "webstore_launch_packet", "id": (packet or {}).get("id")},
            "owner_wording": "Approval is still required for the current packet version.",
            "blocking": not approved,
        },
        {
            "key": "terms_current",
            "state": "ready" if terms else "blocked",
            "reason": f"Current Terms version {terms_version} accepted." if terms else f"Store Owner must accept Terms version {terms_version}.",
            "severity": "blocking",
            "action": "Store Owner accepts the current Terms version.",
            "resource": {"type": "webstore_terms_acceptance", "id": (terms or {}).get("id")},
            "owner_wording": "Terms acceptance is still required.",
            "blocking": not bool(terms),
        },
        {
            "key": "change_requests_resolved",
            "state": "ready" if not open_changes else "blocked",
            "reason": "No open Store Owner change requests." if not open_changes else f"{len(open_changes)} owner change request(s) remain open or answered.",
            "severity": "blocking",
            "action": "Respond to and resolve owner change requests.",
            "resource": {"type": "webstore_change_requests", "id": webstore_id},
            "owner_wording": "Requested changes are being reviewed.",
            "blocking": bool(open_changes),
        },
        {
            "key": "type_requirements",
            "state": "ready" if type_requirements["complete"] else "blocked",
            "reason": "Store-type settings and requirements are complete." if type_requirements["complete"] else "Complete required store-type settings before launch.",
            "severity": "blocking",
            "action": "Review the Store Type Rules panel and complete missing settings.",
            "resource": {"type": "webstore_type_requirements", "id": webstore_id},
            "owner_wording": f"{type_requirements['label']} store details are still being completed.",
            "blocking": not type_requirements["complete"],
            "requirements": type_requirements["items"],
        },
        {
            "key": "payment_ready",
            "state": payment["state"],
            "reason": payment["reason"],
            "severity": "advisory",
            "action": "Complete existing payment-readiness prerequisites when available.",
            "resource": {"type": "payment_readiness", "id": webstore_id},
            "owner_wording": "Payment setup is not ready yet.",
            "blocking": False,
            "stage7_provider_authority": bool(payment["provider_authority"]),
        },
        {
            "key": "buyer_commerce_connected",
            "state": "ready" if payment["provider_authority"] else "blocked",
            "reason": "Verified provider checkout and webhook reconciliation are connected." if payment["provider_authority"] else payment["reason"],
            "severity": "advisory",
            "action": "Complete Stripe Connect setup and verification before enabling buyer checkout.",
            "resource": {"type": "batch_scope", "id": "batch_3"},
            "owner_wording": "Buyer checkout is available after provider verification.",
            "blocking": False,
            "stage7_provider_authority": bool(payment["provider_authority"]),
        },
    ]
    checks = {gate["key"]: not gate["blocking"] for gate in gates}
    checks.update(
        {
            "not_closed_or_archived": store.get("status") not in LIVE_BLOCKING_STATUSES,
            "active_public_products_with_prices": active_public_count > 0,
            "public_branding": branding_complete,
            "questionnaire_complete": bool(questionnaire),
            "launch_packet": bool(packet),
            "owner_approved": approved,
            "terms_fee_acknowledged": bool(terms),
            "payment_ready": bool(payment["ready"]),
            "buyer_commerce_connected": bool(payment["provider_authority"]),
        }
    )
    ready = all(not gate["blocking"] for gate in gates)
    return {
        "webstore_id": webstore_id,
        "ready": ready,
        "checks": checks,
        "gates": gates,
        "current_packet": await _portal_launch_packet_with_history(user["tenant_id"], packet),
        "current_terms_version": terms_version,
        "terms_acceptance": _portal_terms_acceptance(terms),
        "open_change_request_count": len(open_changes),
        "payment_readiness": payment,
        "type_requirements": type_requirements,
        "payment_readiness_source": "provider_boundary",
        "payment_unavailable_reason": payment["reason"],
        "public_launch_blocked_until_batch_3": not bool(payment["provider_authority"]),
    }


def _provider_authority_from_record(record: Optional[dict], settings: Any) -> Optional[ProviderAuthority]:
    if not record or not record.get("connected_account_reference"):
        return None
    base_status = provider_configuration_status(settings)
    return ProviderAuthority(
        provider="stripe",
        mode=str(record.get("provider_mode") or settings.stripe_mode),  # type: ignore[arg-type]
        account_reference=str(record["connected_account_reference"]),
        charge_model=str(settings.stripe_charge_model),
        webhook_verified=bool(base_status.get("configured")),
        verified=str(record.get("onboarding_state") or "") == "complete",
        restriction_status=record.get("restriction_status"),
        charges_enabled=bool(record.get("charges_enabled")),
        payouts_enabled=bool(record.get("payouts_enabled")),
        requirements_currently_due=tuple(str(value) for value in record.get("requirements_currently_due") or []),
    )


def _safe_provider_result(data: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "provider",
        "provider_mode",
        "account_reference",
        "onboarding_url",
        "onboarding_state",
        "charges_enabled",
        "payouts_enabled",
        "requirements_currently_due",
        "requirements_past_due",
        "restriction_status",
        "details_submitted",
    }
    return {key: value for key, value in data.items() if key in allowed}


async def _persist_provider_result(tenant_id: str, webstore_id: str, store: dict[str, Any], data: dict[str, Any]) -> None:
    account_reference = data.get("account_reference") or data.get("connected_account_reference")
    existing = await db.webstore_stripe_connect_records.find_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "record_type": "connected_account"},
        {"_id": 0},
    )
    now = utc_now().isoformat()
    updates: dict[str, Any] = {
        "updated_at": now,
        "provider_name": "stripe",
        "provider_mode": data.get("provider_mode") or (existing or {}).get("provider_mode") or "test",
    }
    if account_reference:
        updates["connected_account_reference"] = str(account_reference)
        updates["stripe_account_id"] = str(account_reference)
    for key in (
        "onboarding_state",
        "charges_enabled",
        "payouts_enabled",
        "requirements_currently_due",
        "requirements_past_due",
        "restriction_status",
    ):
        if key in data:
            updates[key] = data[key]
    if any(key in data for key in ("charges_enabled", "payouts_enabled", "requirements_currently_due", "restriction_status")):
        updates["last_provider_verified_at"] = now
    charges_enabled = bool(data.get("charges_enabled", (existing or {}).get("charges_enabled")))
    payouts_enabled = bool(data.get("payouts_enabled", (existing or {}).get("payouts_enabled")))
    requirements_currently_due = data.get("requirements_currently_due", (existing or {}).get("requirements_currently_due") or [])
    updates["status"] = "provider_ready" if charges_enabled and payouts_enabled and not requirements_currently_due else "pending_provider"
    base = WebstoreStripeConnectRecord(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        owner_id=store.get("owner_id"),
        record_type="connected_account",
        provider_mode=str(updates["provider_mode"]),
    ).model_dump()
    await db.webstore_stripe_connect_records.update_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "record_type": "connected_account"},
        {"$set": updates, "$setOnInsert": base},
        upsert=True,
    )
    await db.webstores.update_one(
        {"tenant_id": tenant_id, "id": webstore_id},
        {
            "$set": {
                "payment_provider_mode": updates["provider_mode"],
                "provider_account_reference": updates.get("connected_account_reference") or (existing or {}).get("connected_account_reference"),
                "provider_onboarding_state": updates.get("onboarding_state") or (existing or {}).get("onboarding_state") or "not_started",
                "provider_charges_enabled": bool(updates.get("charges_enabled") or (existing or {}).get("charges_enabled")),
                "provider_payouts_enabled": bool(updates.get("payouts_enabled") or (existing or {}).get("payouts_enabled")),
                "provider_requirements_currently_due": updates.get("requirements_currently_due") or (existing or {}).get("requirements_currently_due") or [],
                "updated_at": now,
            }
        },
    )


async def provider_authority_for_webstore(tenant_id: str, webstore_id: str) -> ProviderAuthority:
    settings = get_settings()
    record = await db.webstore_stripe_connect_records.find_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "record_type": "connected_account"},
        {"_id": 0},
    )
    authority = _provider_authority_from_record(record, settings)
    status = provider_configuration_status(settings, authority)
    if authority is None or not status["provider_authority"]:
        raise WebstoreError("payment_provider_not_configured", status["reason"], 503)
    return authority


async def payment_provider_status(user: dict, webstore_id: str) -> dict[str, Any]:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _get_store(user["tenant_id"], webstore_id)
    settings = get_settings()
    record = await db.webstore_stripe_connect_records.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "record_type": "connected_account"},
        {"_id": 0},
    )
    authority = _provider_authority_from_record(record, settings)
    status = provider_configuration_status(settings, authority)
    record = serialize_doc(record) if record else {}
    return {
        "webstore_id": webstore_id,
        "provider": "stripe",
        "status": status,
        "store_state": {
            "mode": record.get("provider_mode") or store.get("payment_provider_mode") or "test",
            "onboarding_state": record.get("onboarding_state") or store.get("provider_onboarding_state") or "not_started",
            "charges_enabled": bool(record.get("charges_enabled") or store.get("provider_charges_enabled")),
            "payouts_enabled": bool(record.get("payouts_enabled") or store.get("provider_payouts_enabled")),
            "requirements_currently_due": record.get("requirements_currently_due") or store.get("provider_requirements_currently_due") or [],
            "requirements_past_due": record.get("requirements_past_due") or store.get("provider_requirements_past_due") or [],
            "restriction_status": record.get("restriction_status"),
            "last_verified_at": record.get("last_provider_verified_at"),
            "provider_account_reference": record.get("connected_account_reference") or store.get("provider_account_reference"),
            "provider_authority": bool(status["provider_authority"]),
        },
        "actions": {
            "connect": True,
            "resume_onboarding": True,
            "refresh_status": True,
            "view_requirements": True,
            "disconnect": bool(record.get("connected_account_reference") or store.get("provider_account_reference")),
        },
    }


async def payment_provider_action(user: dict, webstore_id: str, action: str) -> dict[str, Any]:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    store = await _get_store(user["tenant_id"], webstore_id)
    settings = get_settings()
    if action not in {"connect", "resume_onboarding", "refresh_status", "view_requirements", "disconnect"}:
        raise WebstoreError("payment_provider_action_invalid", "Unsupported payment provider action", 400)
    record = await db.webstore_stripe_connect_records.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "record_type": "connected_account"},
        {"_id": 0},
    )
    record = serialize_doc(record) if record else {}
    provider = get_webstore_payment_provider(get_settings())
    if action in {"connect", "resume_onboarding"}:
        result = await provider.create_connected_account_onboarding_link(
            tenant_id=user["tenant_id"],
            webstore_id=webstore_id,
            owner_id=store.get("owner_id"),
            connected_account_reference=record.get("connected_account_reference"),
        )
    elif action == "refresh_status":
        result = await provider.synchronize_payment_readiness(
            tenant_id=user["tenant_id"],
            webstore_id=webstore_id,
            connected_account_reference=record.get("connected_account_reference"),
        )
    elif action == "view_requirements":
        result = await provider.retrieve_connected_account_status(
            tenant_id=user["tenant_id"],
            webstore_id=webstore_id,
            connected_account_reference=record.get("connected_account_reference"),
        )
    else:
        result = await provider.reconcile_provider_event(tenant_id=user["tenant_id"], webstore_id=webstore_id, action=action)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action=f"webstore.payment_provider_{action}",
        entity_type="webstore",
        entity_id=webstore_id,
        summary="Webstore payment provider action requested",
        metadata={"provider": "stripe", "result_code": result.code, "provider_authority": False},
    )
    if not result.ok:
        raise WebstoreError("payment_provider_not_configured", result.message, 503)
    result_data = dict(result.data or {})
    if result_data:
        await _persist_provider_result(user["tenant_id"], webstore_id, store, result_data)
    updated = await db.webstore_stripe_connect_records.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "record_type": "connected_account"},
        {"_id": 0},
    )
    authority = _provider_authority_from_record(updated, settings)
    status = provider_configuration_status(settings, authority)
    await db.webstores.update_one(
        {"tenant_id": user["tenant_id"], "id": webstore_id, "status": "live"},
        {"$set": {"checkout_enabled": bool(status["provider_authority"]), "updated_at": _now_iso()}},
    )
    return {"status": status, "result": {"ok": True, "code": result.code, **_safe_provider_result(result_data)}}


async def _fundraiser_progress(store: dict[str, Any]) -> dict[str, Any]:
    """Expose only completed, verified Webstore sales as fundraiser progress."""
    settings = store.get("store_settings") or {}
    setup = store.get("setup_profile") or {}
    cart = settings.get("cart") or {}
    donation = settings.get("donations") or settings.get("donation") or {}
    goal = int(
        setup.get("fundraiser_goal_amount")
        or cart.get("fundraiser_goal_cents")
        or donation.get("goal_amount_cents")
        or 0
    )
    paid_sales = 0
    async for intent in db.webstore_purchase_intents.find(
        {
            "tenant_id": store["tenant_id"],
            "webstore_id": store["id"],
            "status": "paid_order_created",
            "canonical_payment_id": {"$exists": True, "$ne": None},
        },
        {"_id": 0, "total_cents": 1},
    ):
        paid_sales += max(0, int(intent.get("total_cents") or 0))
    percent = int((Decimal(paid_sales) * Decimal(100) / Decimal(goal)).quantize(Decimal("1"))) if goal else 0
    return {
        "goal_cents": goal,
        "completed_sales_cents": paid_sales,
        "percent": percent,
        "over_goal": bool(goal and paid_sales > goal),
        "paid_only": True,
    }


async def _storefront_by_slug(slug: str) -> dict:
    store = await db.webstores.find_one({"public_slug": slug}, {"_id": 0})
    if not store:
        raise WebstoreError("webstore_not_found", "Webstore not found", 404)
    store = await _ensure_public_slug(serialize_doc(store))
    if store.get("status") != "live":
        raise WebstoreError("webstore_not_live", "Webstore is not available", 404)
    close_at = store.get("deadline_at") or store.get("intended_close_at")
    if close_at:
        try:
            closing = datetime.fromisoformat(str(close_at).replace("Z", "+00:00"))
            if closing.tzinfo and closing <= datetime.now(timezone.utc):
                raise WebstoreError("webstore_closed", "Webstore is not available", 404)
        except ValueError:
            pass
    access_mode = ((store.get("store_settings") or {}).get("access_policy") or {}).get("mode") or "open"
    if access_mode == "restricted":
        raise WebstoreError("webstore_not_public", "Webstore is not available", 404)
    products = []
    async for doc in db.webstore_products.find(
        {"tenant_id": store["tenant_id"], "webstore_id": store["id"], "status": "active", "public": True},
        {"_id": 0},
    ).sort([("featured", -1), ("name", 1)]):
        product = serialize_doc(doc)
        if _public_product_is_eligible(product):
            products.append(_public_product(product, public_slug=store.get("public_slug")))
    published_branding = await branding_svc.published_branding_for_store(store)
    fundraiser_progress = await _fundraiser_progress(store)
    provider_record = await db.webstore_stripe_connect_records.find_one(
        {"tenant_id": store["tenant_id"], "webstore_id": store["id"], "record_type": "connected_account"},
        {"_id": 0},
    )
    provider_status = provider_configuration_status(get_settings(), _provider_authority_from_record(provider_record, get_settings()))
    return {
        "webstore": _public_store(serialize_doc(store), published_branding, fundraiser_progress, provider_status["provider_authority"]),
        "products": products,
    }


async def public_storefront(slug: str) -> dict:
    return await _storefront_by_slug(slug)


async def public_product_detail(slug: str, product_id: str) -> dict:
    storefront = await _storefront_by_slug(slug)
    product = next((item for item in storefront["products"] if item.get("id") == product_id), None)
    if not product:
        raise WebstoreError("product_not_available", "Product is not available", 404)
    return {"webstore": storefront["webstore"], "product": product}


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
    if not product or not _public_product_is_eligible(product):
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


def _parse_public_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else None


def _promo_codes_for_store(store: dict[str, Any]) -> list[dict[str, Any]]:
    settings = store.get("store_settings") or {}
    configured = settings.get("promo_codes") or (settings.get("cart") or {}).get("promo_codes") or []
    return [item for item in configured if isinstance(item, dict)]


def _calculate_public_discount(store: dict[str, Any], code: Optional[str], subtotal: int, lines: list[dict[str, Any]]) -> tuple[int, Optional[str]]:
    normalized = str(code or "").strip().upper()
    if not normalized:
        return 0, None
    now = datetime.now(timezone.utc)
    promo = next((item for item in _promo_codes_for_store(store) if str(item.get("code") or "").strip().upper() == normalized), None)
    if not promo:
        raise WebstoreError("promo_code_invalid", "That promo code is not available for this Webstore", 409)
    if str(promo.get("status") or "active").lower() != "active":
        raise WebstoreError("promo_code_inactive", "That promo code is not available", 409)
    starts_at = _parse_public_time(promo.get("starts_at"))
    expires_at = _parse_public_time(promo.get("expires_at"))
    if starts_at and starts_at > now:
        raise WebstoreError("promo_code_not_started", "That promo code is not active yet", 409)
    if expires_at and expires_at <= now:
        raise WebstoreError("promo_code_expired", "That promo code has expired", 409)
    usage_limit = int(promo.get("usage_limit") or 0)
    if usage_limit and int(promo.get("times_validated") or 0) >= usage_limit:
        raise WebstoreError("promo_code_exhausted", "That promo code is no longer available", 409)
    minimum = int(promo.get("minimum_subtotal_cents") or 0)
    if subtotal < minimum:
        raise WebstoreError("promo_code_minimum_not_met", "Add more merchandise to use that promo code", 409)
    product_ids = {str(item) for item in promo.get("product_ids") or []}
    category_ids = {str(item) for item in promo.get("category_ids") or []}
    eligible_subtotal = subtotal
    if product_ids or category_ids:
        eligible_subtotal = sum(
            int(line["line_total_cents"])
            for line in lines
            if (not product_ids or line["product_id"] in product_ids)
            and (not category_ids or str(line.get("category_id") or "") in category_ids)
        )
        if eligible_subtotal <= 0:
            raise WebstoreError("promo_code_not_applicable", "That promo code does not apply to the selected products", 409)
    if str(promo.get("discount_type") or "fixed").lower() == "percentage":
        basis_points = int(promo.get("discount_basis_points") or 0)
        if basis_points <= 0 or basis_points > 10000:
            raise WebstoreError("promo_code_invalid", "That promo code is not configured correctly", 409)
        discount = int((Decimal(eligible_subtotal) * Decimal(basis_points) / Decimal(10000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    else:
        discount = int(promo.get("discount_cents") or 0)
    maximum = promo.get("maximum_discount_cents")
    if maximum not in (None, ""):
        discount = min(discount, int(maximum))
    return max(0, min(discount, eligible_subtotal)), normalized


async def quote_public_cart(slug: str, fields: dict[str, Any]) -> dict:
    storefront = await _storefront_by_slug(slug)
    store_view = storefront["webstore"]
    full_store = await db.webstores.find_one({"public_slug": slug, "id": store_view["id"]}, {"_id": 0})
    if not full_store:
        raise WebstoreError("webstore_not_found", "Webstore not found", 404)
    product_ids = [str(item.get("product_id")) for item in fields.get("line_items") or [] if item.get("product_id")]
    full_products = {
        doc["id"]: serialize_doc(doc)
        async for doc in db.webstore_products.find(
            {"tenant_id": full_store["tenant_id"], "webstore_id": full_store["id"], "id": {"$in": product_ids}},
            {"_id": 0},
        )
        if _public_product_is_eligible(doc)
    }
    public_products = {item["id"]: item for item in storefront["products"]}
    line_items: list[dict[str, Any]] = []
    subtotal = 0
    shipping = 0
    fulfillment_groups: dict[str, int] = {"pickup": 0, "shipping": 0}
    for raw in fields.get("line_items") or []:
        product_id = str(raw.get("product_id") or "")
        full_product = full_products.get(product_id)
        public_product = public_products.get(product_id)
        if not full_product or not public_product:
            raise WebstoreError("product_not_available", "Product is not available", 409)
        quantity = int(raw.get("quantity") or 0)
        if quantity < 1 or quantity > 99:
            raise WebstoreError("invalid_quantity", "Quantity must be between 1 and 99", 400)
        variant = raw.get("variant") or {}
        if full_product.get("variants") and not variant:
            raise WebstoreError("variant_required", "Choose an available product option", 400)
        if not _variant_allowed(full_product.get("variants") or [], variant):
            raise WebstoreError("variant_not_available", "That product option is not available", 409)
        _validate_personalization(full_product, raw.get("personalization") or {})
        methods = _effective_fulfillment_methods(full_product)
        selected_method = str(raw.get("fulfillment_method") or full_product.get("default_fulfillment_method") or (methods[0] if len(methods) == 1 else "")).lower()
        if selected_method not in methods:
            raise WebstoreError("fulfillment_method_required", "Choose an available fulfillment method for each product", 400)
        matched_variant = next((item for item in full_product.get("variants") or [] if _variant_allowed([item], variant)), None)
        unit_price = int(full_product.get("selling_price_cents") or 0)
        if matched_variant:
            if matched_variant.get("selling_price_cents") not in (None, ""):
                unit_price = int(matched_variant["selling_price_cents"])
            else:
                unit_price += int(matched_variant.get("price_delta_cents") or 0)
        line_total = unit_price * quantity
        line_shipping = int(full_product.get("shipping_cost_cents") or 0) * quantity if selected_method == "shipping" else 0
        subtotal += line_total
        shipping += line_shipping
        fulfillment_groups[selected_method] += line_total
        line_items.append({
            "product_id": product_id,
            "category_id": full_product.get("category_id"),
            "name": public_product.get("name"),
            "variant": variant,
            "personalization": raw.get("personalization") or {},
            "quantity": quantity,
            "fulfillment_method": selected_method,
            "unit_price_cents": unit_price,
            "line_total_cents": line_total,
            "shipping_cents": line_shipping,
        })
    donation = int(fields.get("donation_cents") or 0)
    cart_config = _public_cart_config(full_store)
    if donation < 0:
        raise WebstoreError("invalid_donation", "Donation cannot be negative", 400)
    if donation and not cart_config["donation_enabled"]:
        raise WebstoreError("donation_not_enabled", "Donations are not enabled for this Webstore", 409)
    if cart_config["donation_min_cents"] and donation and donation < cart_config["donation_min_cents"]:
        raise WebstoreError("donation_below_minimum", "Donation is below the configured minimum", 400)
    if cart_config["donation_max_cents"] and donation > cart_config["donation_max_cents"]:
        raise WebstoreError("donation_above_maximum", "Donation exceeds the configured maximum", 400)
    discount, applied_promo = _calculate_public_discount(full_store, fields.get("promo_code"), subtotal, line_items)
    total = max(0, subtotal + shipping + donation - discount)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    snapshot = {
        "webstore_id": full_store["id"],
        "public_slug": slug,
        "line_items": line_items,
        "subtotal_cents": subtotal,
        "shipping_cents": shipping,
        "donation_cents": donation,
        "discount_cents": discount,
        "total_cents": total,
        "promo_code": applied_promo,
        "currency": "usd",
        "expires_at": expires_at,
    }
    return {
        "quote_version": "webstore_cart_quote_v1",
        "quote_id": _json_hash(snapshot),
        "webstore_id": full_store["id"],
        "public_slug": slug,
        "line_items": line_items,
        "fulfillment_groups": {key: value for key, value in fulfillment_groups.items() if value},
        "subtotal_cents": subtotal,
        "shipping_cents": shipping,
        "donation_cents": donation,
        "discount_cents": discount,
        "total_cents": total,
        "currency": "usd",
        "expires_at": expires_at,
        "warnings": [],
        "applied_promo_code": applied_promo,
        "payment_status": "not_requested",
        "order_creation": "deferred_to_stage_8",
        "unpaid_progress_excluded": True,
    }


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


def _variant_allowed(configured: list[dict[str, Any]], supplied: dict[str, Any]) -> bool:
    if not supplied:
        return True
    for option in configured or []:
        if all(str(option.get(k)) == str(v) for k, v in supplied.items()):
            return True
    return False


def _validate_personalization(product: dict, supplied: dict[str, Any]) -> None:
    if not product.get("personalization_enabled"):
        return
    missing: list[str] = []
    for field in product.get("personalization_fields") or []:
        key = field.get("key") or field.get("name") or field.get("id")
        if bool(field.get("required")) and key and not str(supplied.get(key) or "").strip():
            missing.append(str(key))
    if missing:
        raise WebstoreError("personalization_required", "Required personalization fields are missing", 400)


def _checkout_response(intent: dict, *, created: bool) -> dict:
    public_intent = serialize_doc(intent)
    public_intent.pop("immutable_snapshot", None)
    return {
        "purchase_intent": public_intent,
        "checkout_available": False,
        "checkout_status": intent.get("checkout_status") or "created",
        "checkout": {
            "provider": intent.get("provider") or "deferred",
            "provider_checkout_id": intent.get("provider_checkout_id"),
            "payment_required": True,
            "payment_authority": "none",
            "verified_payment_creates_order": False,
            "unavailable_reason": "Provider checkout is unavailable until this Webstore's payment authority is enabled.",
        },
        "created": created,
    }


async def create_purchase_intent(slug: str, fields: dict[str, Any], *, allow_internal_draft: bool = False) -> dict:
    _reject_public_money_authority(fields)
    provider_status = provider_configuration_status(get_settings())
    if not allow_internal_draft and not provider_status["provider_authority"]:
        raise WebstoreError(
            "payment_provider_not_configured",
            "Online checkout is unavailable until the Webstore payment provider is configured and verified.",
            503,
        )
    storefront = await _storefront_by_slug(slug)
    store = storefront["webstore"]
    if not allow_internal_draft and not store.get("checkout_enabled"):
        raise WebstoreError("checkout_paused", "Checkout is currently paused for this Webstore", 409)
    full_store = await db.webstores.find_one({"public_slug": slug, "id": store["id"]}, {"_id": 0})
    tenant_id = full_store["tenant_id"]
    if fields.get("idempotency_key"):
        existing = await db.webstore_purchase_intents.find_one(
            {"tenant_id": tenant_id, "webstore_id": store["id"], "idempotency_key": fields["idempotency_key"]},
            {"_id": 0},
        )
        if existing:
            return _checkout_response(existing, created=False)
    product_map = {p["id"]: p for p in storefront["products"]}
    line_items: list[dict[str, Any]] = []
    financial_lines: list[dict[str, Any]] = []
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
        if not _variant_allowed(full_product.get("variants") or [], raw.get("variant") or {}):
            raise WebstoreError("variant_not_available", "Selected product variant is not available for checkout", 409)
        _validate_personalization(full_product, raw.get("personalization") or {})
        unit = int(full_product["selling_price_cents"])
        line_total = unit * qty
        subtotal += line_total
        fee_bps = int(full_product.get("platform_fee_basis_points") or 0)
        financial_lines.append(
            {
                "product_id": product_id,
                "line_total_cents": line_total,
                "platform_fee_basis_points": fee_bps,
                "platform_fee_cents": int((Decimal(line_total) * Decimal(fee_bps) / Decimal(10000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
                "store_owner_share_cents": int(full_product.get("store_owner_share_cents") or 0) * qty,
                "fundraiser_share_cents": int(full_product.get("fundraiser_share_cents") or 0) * qty,
                "production_cost_cents": int(full_product.get("production_cost_cents") or 0) * qty,
            }
        )
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
            "checkout_contract": {
                "authority": "verified_provider_event",
                "success_redirect_is_not_payment_evidence": True,
            },
            "financial_lines": financial_lines,
        },
    ).model_dump()
    intent["confirmation_token"] = secrets.token_urlsafe(24)
    try:
        await db.webstore_purchase_intents.insert_one(prepare_for_mongo(intent))
    except DuplicateKeyError:
        existing = await db.webstore_purchase_intents.find_one(
            {"tenant_id": tenant_id, "webstore_id": store["id"], "idempotency_key": fields.get("idempotency_key")},
            {"_id": 0},
        )
        return _checkout_response(existing, created=False)
    await _audit(
        tenant_id=tenant_id,
        webstore_id=store["id"],
        actor_type="public",
        actor_email=intent["buyer_email"],
        action="webstore.purchase_intent_created",
        entity_type="webstore_purchase_intent",
        entity_id=intent["id"],
        summary="Webstore checkout intent created; canonical records await verified payment evidence",
        metadata={"total_cents": total, "payment_authority": "verified_provider_event"},
    )
    saved = await db.webstore_purchase_intents.find_one({"tenant_id": tenant_id, "id": intent["id"]}, {"_id": 0})
    return _checkout_response(saved, created=True)


def _provider_checkout_response(intent: dict, provider_data: dict[str, Any], *, created: bool) -> dict:
    public_intent = serialize_doc(intent)
    public_intent.pop("immutable_snapshot", None)
    return {
        "purchase_intent": public_intent,
        "checkout_available": True,
        "checkout_status": intent.get("checkout_status") or "session_created",
        "checkout": {
            "provider": "stripe",
            "provider_checkout_id": intent.get("provider_checkout_id"),
            "checkout_url": intent.get("checkout_url"),
            "payment_required": True,
            "payment_authority": "verified_provider_event",
            "verified_payment_creates_order": False,
            "status": provider_data.get("checkout_status") or "open",
        },
        "created": created,
    }


async def create_checkout_session(slug: str, fields: dict[str, Any]) -> dict:
    """Create or reuse one server-priced Stripe Checkout Session.

    This boundary records only the purchase intent and provider session. The
    signed webhook boundary is the only path that can mark payment verified;
    canonical Order and Production creation remains a later stage.
    """
    _reject_public_money_authority(fields)
    if not str(fields.get("idempotency_key") or "").strip():
        raise WebstoreError("idempotency_key_required", "Checkout requires an idempotency key", 400)
    storefront = await _storefront_by_slug(slug)
    store = storefront["webstore"]
    full_store = await db.webstores.find_one({"public_slug": slug, "id": store["id"]}, {"_id": 0})
    if not full_store:
        raise WebstoreError("webstore_not_found", "Webstore not found", 404)
    authority = await provider_authority_for_webstore(full_store["tenant_id"], store["id"])
    if not store.get("checkout_enabled"):
        raise WebstoreError("checkout_paused", "Checkout is currently paused for this Webstore", 409)
    existing = None
    if fields.get("idempotency_key"):
        existing = await db.webstore_purchase_intents.find_one(
            {
                "tenant_id": full_store["tenant_id"],
                "webstore_id": store["id"],
                "idempotency_key": fields["idempotency_key"],
            },
            {"_id": 0},
        )
        if existing and existing.get("provider_checkout_id") and existing.get("checkout_url"):
            return _provider_checkout_response(existing, existing, created=False)
    intent_response = await create_purchase_intent(slug, fields, allow_internal_draft=True)
    intent_id = (intent_response.get("purchase_intent") or {}).get("id")
    intent = await db.webstore_purchase_intents.find_one(
        {"id": intent_id, "tenant_id": full_store["tenant_id"], "webstore_id": store["id"]},
        {"_id": 0},
    )
    if not intent:
        raise WebstoreError("purchase_intent_not_found", "Webstore purchase intent could not be created", 500)
    provider = get_webstore_payment_provider(get_settings())
    provider_result = await provider.create_checkout_session(
        tenant_id=full_store["tenant_id"],
        webstore_id=store["id"],
        purchase_intent_id=intent["id"],
        buyer_email=intent["buyer_email"],
        currency=intent.get("currency") or "usd",
        line_items=[
            {
                "name": item["name"],
                "quantity": int(item["quantity"]),
                "unit_amount_cents": int(item["unit_price_cents"]),
            }
            for item in intent.get("line_items") or []
        ],
        connected_account_reference=authority.account_reference,
        idempotency_key=fields.get("idempotency_key") or intent["id"],
    )
    if not provider_result.ok:
        raise WebstoreError("payment_provider_error", provider_result.message, 503)
    provider_data = dict(provider_result.data or {})
    checkout_id = str(provider_data.get("checkout_session_id") or "").strip()
    checkout_url = str(provider_data.get("checkout_url") or "").strip()
    if not checkout_id or not checkout_url:
        raise WebstoreError("payment_provider_error", "Stripe did not return a checkout session URL", 503)
    await db.webstore_purchase_intents.update_one(
        {"tenant_id": full_store["tenant_id"], "webstore_id": store["id"], "id": intent["id"], "status": "pending_payment"},
        {
            "$set": {
                "provider": "stripe",
                "provider_mode": provider_data.get("provider_mode") or get_settings().stripe_mode,
                "provider_checkout_id": checkout_id,
                "checkout_url": checkout_url,
                "checkout_status": "session_created",
                "checkout_attempt_id": checkout_id,
                "checkout_attempt_state": "created",
                "expected_amount_cents": int(intent.get("total_cents") or 0),
                "expected_currency": intent.get("currency") or "usd",
                "updated_at": utc_now().isoformat(),
            }
        },
    )
    saved = await db.webstore_purchase_intents.find_one({"id": intent["id"], "tenant_id": full_store["tenant_id"]}, {"_id": 0})
    return _provider_checkout_response(saved, provider_data, created=existing is None)


async def create_buyer_order(
    slug: str,
    fields: dict[str, Any],
    *,
    provider_authority: Optional[ProviderAuthority] = None,
) -> dict:
    """Create a pending intent only after typed internal authority exists.

    Public routers call ``create_purchase_intent`` with its fail-closed
    default. Without typed authority this compatibility helper remains
    fail-closed. With a controlled provider-authoritative fixture it creates
    only a pending intent and never creates a Payment, Order, inventory
    mutation, or Production record.
    """
    if provider_authority is None:
        return await create_purchase_intent(slug, fields)
    if not provider_authority.verified or not provider_authority.webhook_verified or provider_authority.charge_model == "deferred":
        raise WebstoreError("payment_provider_not_configured", "Provider-authoritative Webstore preparation is unavailable", 503)
    return await create_purchase_intent(slug, fields, allow_internal_draft=True)


async def public_confirmation(slug: str, confirmation_token: str) -> dict:
    storefront = await _storefront_by_slug(slug)
    store = storefront["webstore"]
    full_store = await db.webstores.find_one({"public_slug": slug, "id": store["id"]}, {"_id": 0})
    intent = await db.webstore_purchase_intents.find_one(
        {
            "tenant_id": full_store["tenant_id"],
            "webstore_id": store["id"],
            "public_slug": slug,
            "confirmation_token": confirmation_token,
            "canonical_order_id": {"$type": "string"},
        },
        {"_id": 0},
    )
    if not intent:
        raise WebstoreError("confirmation_not_found", "Webstore confirmation was not found", 404)
    public_intent = serialize_doc(intent)
    public_intent.pop("immutable_snapshot", None)
    order = await db.orders.find_one({"tenant_id": full_store["tenant_id"], "id": intent.get("canonical_order_id")}, {"_id": 0})
    return {
        "purchase_intent": public_intent,
        "order": {
            "id": intent.get("canonical_order_id"),
            "number": (order or {}).get("number"),
            "status": (order or {}).get("status"),
            "total_cents": int(intent.get("total_cents") or 0),
        },
        "payment_status": intent.get("status"),
        "fulfillment_status": intent.get("fulfillment_status"),
    }


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
    legacy_orders = [doc async for doc in db.webstore_buyer_orders.find({"tenant_id": user["tenant_id"], "webstore_id": webstore_id}, {"_id": 0})]
    purchase_intents = [
        serialize_doc(doc)
        async for doc in db.webstore_purchase_intents.find(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "canonical_order_id": {"$type": "string"}},
            {"_id": 0, "immutable_snapshot": 0},
        )
    ]
    ledger = [doc async for doc in db.webstore_ledger_entries.find({"tenant_id": user["tenant_id"], "webstore_id": webstore_id}, {"_id": 0})]
    by_entry: dict[str, int] = {}
    for row in ledger:
        by_entry[row["entry_type"]] = by_entry.get(row["entry_type"], 0) + int(row.get("amount_cents") or 0)
    product_qty: dict[str, int] = {}
    for order in [*legacy_orders, *purchase_intents]:
        for line in order.get("line_items") or []:
            product_qty[line["product_id"]] = product_qty.get(line["product_id"], 0) + int(line.get("quantity") or 0)
    gross = sum(int(o.get("total_cents") or 0) for o in purchase_intents) + sum(int(o.get("total_cents") or 0) for o in legacy_orders)
    return {
        "webstore_id": webstore_id,
        "order_count": len(purchase_intents) + len(legacy_orders),
        "canonical_order_count": len(purchase_intents),
        "legacy_order_count": len(legacy_orders),
        "gross_sales_cents": gross,
        "refund_total_cents": abs(by_entry.get("refund", 0)),
        "payout_total_cents": by_entry.get("payout", 0),
        "dispute_hold_cents": abs(by_entry.get("dispute_hold", 0)),
        "ledger_totals_cents": by_entry,
        "product_quantities": product_qty,
        "purchase_intents": purchase_intents,
    }


async def refund_webstore_payment(user: dict, webstore_id: str, payment_id: str, fields: dict[str, Any], idempotency_key: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    await _get_store(user["tenant_id"], webstore_id)
    from . import webstore_payments

    return await webstore_payments.initiate_webstore_refund(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        payment_id=payment_id,
        amount_cents=fields.get("amount_cents"),
        reason=_clean_text(fields.get("reason"), "reason", limit=500),
        actor_user_id=user["id"],
        actor_email=user.get("email") or "",
        idempotency_key=idempotency_key or fields.get("idempotency_key"),
    )


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
    products = []
    async for doc in db.webstore_products.find({"tenant_id": identity["tenant_id"], "webstore_id": webstore_id}, {"_id": 0}).sort([("display_order", 1), ("name", 1)]):
        item = _portal_product(doc, public_slug=store.get("public_slug"))
        item["mockups"] = await _current_mockups_for_product(identity["tenant_id"], webstore_id, doc)
        item["approval_history"] = await _approval_history(identity["tenant_id"], "webstore_product", doc["id"])
        products.append(item)
    packet = None
    if store.get("launch_packet_id"):
        packet = await packets_repo.get(tenant_id=identity["tenant_id"], entity_id=store["launch_packet_id"])
    terms_version = store.get("required_terms_version") or CURRENT_WEBSTORE_TERMS_VERSION
    terms = await _terms_acceptance(identity["tenant_id"], webstore_id, terms_version, identity.get("id"))
    changes = [
        _portal_change_request(doc)
        async for doc in db.webstore_change_requests.find(
            {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id},
            {"_id": 0, "staff_only_history": 0},
        ).sort([("created_at", -1)])
    ]
    payment = await _payment_readiness(store)
    owner_gates = [
        {
            "key": "packet_delivered",
            "state": "ready" if packet and packet.get("status") in {"delivered", "sent_for_approval", "owner_approved", "changes_requested"} else "waiting",
            "owner_wording": "Launch packet is available for review." if packet else "The shop is preparing your launch packet.",
        },
        {
            "key": "packet_approval",
            "state": "ready" if store.get("owner_approved_packet_id") == (packet or {}).get("id") else "waiting",
            "owner_wording": "You approved the current packet." if store.get("owner_approved_packet_id") == (packet or {}).get("id") else "Packet approval is still needed.",
        },
        {
            "key": "terms",
            "state": "ready" if terms else "waiting",
            "owner_wording": f"Terms version {terms_version} accepted." if terms else f"Terms version {terms_version} still needs acceptance.",
        },
        {
            "key": "payment",
            "state": payment["state"],
            "owner_wording": "Payment setup is not live yet.",
        },
    ]
    owner_report = await reports({"tenant_id": identity["tenant_id"], "role": "owner", "id": identity.get("id"), "email": identity.get("email")}, webstore_id)
    return {
        "webstore": _portal_store(store),
        "products": products,
        "launch_packet": await _portal_launch_packet_with_history(identity["tenant_id"], packet),
        "change_requests": changes,
        "current_terms_version": terms_version,
        "terms_acceptance": _portal_terms_acceptance(terms),
        "readiness_summary": owner_gates,
        "commerce_summary": {
            "order_count": owner_report["order_count"],
            "gross_sales_cents": owner_report["gross_sales_cents"],
            "refund_total_cents": owner_report["refund_total_cents"],
            "payout_total_cents": owner_report["payout_total_cents"],
            "dispute_hold_cents": owner_report["dispute_hold_cents"],
            "product_quantities": owner_report["product_quantities"],
        },
        "public_launch_blocked_until_batch_3": not bool(payment["provider_authority"]),
    }


async def owner_decide_product_approval(identity: dict, webstore_id: str, product_id: str, fields: dict[str, Any]) -> dict:
    store = await _owner_portal_store(identity, webstore_id)
    product = await _get_product(identity["tenant_id"], product_id, webstore_id)
    decision = str(fields.get("decision") or "").strip().lower()
    if decision not in PRODUCT_APPROVAL_DECISIONS:
        raise WebstoreError("invalid_product_approval_decision", "Choose approve, request_changes, or reject", 400)
    comment = _clean_optional_text(fields.get("comment"), limit=2000)
    if decision in {"request_changes", "reject"} and not comment:
        raise WebstoreError("approval_comment_required", "A comment is required when requesting changes or rejecting a product", 400)
    if product.get("approval_status") != "pending_owner_approval":
        raise WebstoreError("product_not_pending_approval", "This product is not waiting for owner approval", 409)
    expected_revision = int(product.get("approval_revision") or 0)
    if expected_revision != int(product.get("revision") or 1):
        raise WebstoreError("approval_revision_superseded", "This product changed after it was sent for approval", 409)
    snapshot = await _product_approval_snapshot(identity["tenant_id"], webstore_id, product, public_slug=store.get("public_slug"))
    snapshot_hash = _json_hash(snapshot)
    if snapshot_hash != product.get("approval_snapshot_hash"):
        raise WebstoreError("approval_snapshot_superseded", "This product review snapshot is no longer current", 409)
    action = "decline" if decision == "reject" else decision
    approval = await record_approval(
        tenant_id=identity["tenant_id"],
        parent_type="webstore_product",
        parent_id=product_id,
        parent_version=expected_revision,
        action=action,
        reason=comment,
        actor_type="staff",
        actor_ref=identity["id"],
        actor_display=identity.get("full_name") or identity.get("email"),
        snapshot_hash=snapshot_hash,
        snapshot=snapshot,
    )
    status = "approved" if decision == "approve" else ("changes_requested" if decision == "request_changes" else "rejected")
    now = _now_iso()
    updated = await db.webstore_products.find_one_and_update(
        {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id, "id": product_id},
        {
            "$set": {
                "approval_status": status,
                "approval_decision_at": now,
                "approval_decision_by_portal_identity_id": identity["id"],
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal",
        actor_id=identity.get("id"),
        actor_email=identity.get("email"),
        action=f"webstore.product_approval_{status}",
        entity_type="webstore_product",
        entity_id=product_id,
        summary=f"Webstore product approval decision: {status.replace('_', ' ')}",
        metadata={"approval_id": approval["id"], "product_revision": expected_revision},
    )
    result = _portal_product(updated or product, public_slug=store.get("public_slug"))
    result["approval_history"] = await _approval_history(identity["tenant_id"], "webstore_product", product_id)
    return result


async def owner_decide_mockup_approval(identity: dict, webstore_id: str, mockup_id: str, fields: dict[str, Any]) -> dict:
    store = await _owner_portal_store(identity, webstore_id)
    mockup = await _get_mockup(identity["tenant_id"], mockup_id, webstore_id)
    decision = str(fields.get("decision") or "").strip().lower()
    if decision not in PRODUCT_APPROVAL_DECISIONS:
        raise WebstoreError("invalid_mockup_approval_decision", "Choose approve, request_changes, or reject", 400)
    comment = _clean_optional_text(fields.get("comment"), limit=2000)
    if decision in {"request_changes", "reject"} and not comment:
        raise WebstoreError("approval_comment_required", "A comment is required when requesting changes or rejecting a mockup", 400)
    if mockup.get("approval_status") != "pending_owner_approval":
        raise WebstoreError("mockup_not_pending_approval", "This mockup is not waiting for owner approval", 409)
    product = await _get_product(identity["tenant_id"], mockup["product_id"], webstore_id) if mockup.get("product_id") else None
    snapshot = _mockup_approval_snapshot(mockup, product, public_slug=store.get("public_slug"))
    snapshot_hash = _json_hash(snapshot)
    if snapshot_hash != mockup.get("approval_snapshot_hash"):
        raise WebstoreError("mockup_snapshot_superseded", "This mockup review snapshot is no longer current", 409)
    action = "decline" if decision == "reject" else decision
    approval = await record_approval(
        tenant_id=identity["tenant_id"],
        parent_type="webstore_mockup",
        parent_id=mockup_id,
        action=action,
        reason=comment,
        actor_type="staff",
        actor_ref=identity["id"],
        actor_display=identity.get("full_name") or identity.get("email"),
        snapshot_hash=snapshot_hash,
        snapshot=snapshot,
    )
    status = "approved" if decision == "approve" else ("changes_requested" if decision == "request_changes" else "rejected")
    now = _now_iso()
    updated = await db.webstore_mockups.find_one_and_update(
        {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id, "id": mockup_id},
        {
            "$set": {
                "approval_status": status,
                "approval_decision_at": now,
                "approval_decision_by_portal_identity_id": identity["id"],
                "owner_approved": decision == "approve",
                "status": "owner_approved" if decision == "approve" else ("changes_requested" if decision == "request_changes" else mockup.get("status", "generated")),
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal",
        actor_id=identity.get("id"),
        actor_email=identity.get("email"),
        action=f"webstore.mockup_approval_{status}",
        entity_type="webstore_mockup",
        entity_id=mockup_id,
        summary=f"Webstore mockup approval decision: {status.replace('_', ' ')}",
        metadata={"approval_id": approval["id"]},
    )
    result = serialize_doc(updated or mockup)
    result["approval_history"] = await _approval_history(identity["tenant_id"], "webstore_mockup", mockup_id)
    return result
