"""EC13 Phase 13A - commercial catalog service contracts."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.permissions import PlatformPerm, has_platform_admin_access
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.commercial_catalog import (
    CommercialCatalogVersion,
    CommercialEntitlementRule,
    CommercialPrice,
    CommercialProduct,
    FounderTenantContract,
    PlatformFeeSchedule,
    PlatformFeeTransactionContract,
)
from .activity import record_activity_with_audit


class CommercialCatalogError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


FEATURE_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
FOUNDER_ACTIVE_STATUSES = {"pending", "active", "grace"}
PUBLISHED_LOCKED_PRICE_FIELDS = {
    "catalog_version_id",
    "product_id",
    "price_key",
    "billing_interval",
    "currency",
    "amount_cents",
    "is_active",
    "is_public",
    "is_stripe_syncable",
    "stripe_product_id",
    "stripe_price_id",
    "approved_by_owner",
    "approved_at",
    "effective_at",
    "retired_at",
    "replaces_price_id",
}


def _now_iso() -> str:
    return utc_now().isoformat()


def _is_platform_admin(user: dict) -> bool:
    return has_platform_admin_access(
        user,
        extra_permissions={PlatformPerm.PLATFORM_SUBSCRIPTION_ADMIN.value},
    )


def require_platform_admin(user: dict) -> None:
    if not _is_platform_admin(user):
        raise CommercialCatalogError("platform_admin_required", "Platform admin access is required", 403)


async def _audit(user: dict, action: str, entity_type: str, entity_id: str, summary: str, metadata: Optional[dict] = None) -> None:
    await record_activity_with_audit(
        tenant_id=user["tenant_id"],
        actor_user_id=user["id"],
        actor_email=user.get("email", "platform"),
        module="commercial_billing",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        metadata=metadata or {},
    )


async def _catalog(catalog_version_id: str) -> dict:
    doc = await db.commercial_catalog_versions.find_one({"id": catalog_version_id}, {"_id": 0})
    if not doc:
        raise CommercialCatalogError("catalog_version_not_found", "Catalog version not found", 404)
    return doc


async def _require_draft_catalog(catalog_version_id: str) -> dict:
    catalog = await _catalog(catalog_version_id)
    if catalog["status"] != "draft":
        raise CommercialCatalogError("catalog_immutable", "Only draft catalog versions may be changed", 409)
    return catalog


async def _product(product_id: str) -> dict:
    doc = await db.commercial_products.find_one({"id": product_id}, {"_id": 0})
    if not doc:
        raise CommercialCatalogError("product_not_found", "Commercial product not found", 404)
    return doc


def _clean_text(value: Any, field: str, *, limit: int = 160) -> str:
    text = str(value or "").strip()
    if not text:
        raise CommercialCatalogError(f"{field}_required", f"{field} is required", 400)
    if len(text) > limit:
        raise CommercialCatalogError(f"{field}_too_long", f"{field} must be {limit} characters or fewer", 400)
    return text


def _clean_optional_text(value: Any, *, limit: int = 2000) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:limit]


def _clean_currency(value: str | None) -> str:
    cur = (value or "usd").lower().strip()
    if len(cur) != 3 or not cur.isalpha():
        raise CommercialCatalogError("invalid_currency", "Currency must be a 3-letter ISO code", 400)
    return cur


def _validate_product_flags(fields: dict[str, Any]) -> None:
    status = fields.get("status")
    if status == "unavailable" and (fields.get("publishable") or fields.get("stripe_sync_enabled")):
        raise CommercialCatalogError(
            "product_unavailable",
            "Unavailable products cannot be public, purchasable, or Stripe-syncable",
            409,
        )
    if status in {"inactive", "retired"} and fields.get("stripe_sync_enabled"):
        raise CommercialCatalogError("product_not_sellable", "Inactive or retired products cannot be Stripe-syncable", 409)
    if fields.get("stripe_sync_enabled") and not fields.get("publishable"):
        raise CommercialCatalogError("stripe_requires_publishable", "Stripe-syncable products must also be publishable", 400)


async def _validate_price_contract(product: dict, fields: dict[str, Any]) -> None:
    if not isinstance(fields.get("amount_cents"), int) or isinstance(fields.get("amount_cents"), bool):
        raise CommercialCatalogError("integer_cents_required", "amount_cents must be an integer number of cents", 400)
    if fields["amount_cents"] < 0:
        raise CommercialCatalogError("invalid_amount", "amount_cents cannot be negative", 400)
    approved = bool(fields.get("approved_by_owner"))
    if (fields.get("is_active") or fields.get("is_public") or fields.get("is_stripe_syncable")) and not approved:
        raise CommercialCatalogError("owner_approval_required", "Active, public, or Stripe-syncable prices require owner approval", 409)
    if fields.get("is_stripe_syncable") and not fields.get("is_public"):
        raise CommercialCatalogError("stripe_requires_public_price", "Stripe-syncable prices must also be public", 400)
    if product["status"] in {"inactive", "unavailable", "retired"} and (
        fields.get("is_active") or fields.get("is_public") or fields.get("is_stripe_syncable")
    ):
        raise CommercialCatalogError("product_not_purchasable", "Inactive, unavailable, or retired products cannot have active public prices", 409)
    if product["product_type"] == "standalone" and fields.get("billing_interval") in {"monthly", "annual"}:
        if fields["amount_cents"] <= 0:
            raise CommercialCatalogError("standalone_price_required", "Standalone monthly or annual prices must be owner-approved non-zero prices", 409)


async def create_catalog_version(user: dict, fields: dict[str, Any]) -> dict:
    require_platform_admin(user)
    version = _clean_text(fields.get("version"), "version", limit=80)
    doc = CommercialCatalogVersion(
        version=version,
        effective_at=fields.get("effective_at"),
        notes=_clean_optional_text(fields.get("notes")),
        created_by_user_id=user["id"],
    ).model_dump()
    try:
        await db.commercial_catalog_versions.insert_one(prepare_for_mongo(doc))
    except DuplicateKeyError:
        raise CommercialCatalogError("duplicate_catalog_version", "Catalog version already exists", 409)
    await _audit(user, "commercial.catalog_version_created", "commercial_catalog_version", doc["id"], f"Commercial catalog version created: {version}")
    return serialize_doc(doc)


async def list_catalog_versions() -> dict:
    cur = db.commercial_catalog_versions.find({}, {"_id": 0}).sort([("created_at", -1)])
    items = [serialize_doc(doc) async for doc in cur]
    return {"items": items, "total": len(items)}


async def update_catalog_version(user: dict, catalog_version_id: str, updates: dict[str, Any]) -> dict:
    require_platform_admin(user)
    await _require_draft_catalog(catalog_version_id)
    clean = {k: updates[k] for k in ("effective_at", "notes") if k in updates}
    if "notes" in clean:
        clean["notes"] = _clean_optional_text(clean["notes"])
    if not clean:
        raise CommercialCatalogError("no_updates", "No supported updates provided", 400)
    clean["updated_at"] = _now_iso()
    await db.commercial_catalog_versions.update_one({"id": catalog_version_id}, {"$set": clean})
    await _audit(user, "commercial.catalog_version_updated", "commercial_catalog_version", catalog_version_id, "Commercial catalog version updated", {"fields": sorted(clean)})
    return serialize_doc(await db.commercial_catalog_versions.find_one({"id": catalog_version_id}, {"_id": 0}))


async def publish_catalog_version(user: dict, catalog_version_id: str) -> dict:
    require_platform_admin(user)
    await _require_draft_catalog(catalog_version_id)
    async for product in db.commercial_products.find({"catalog_version_id": catalog_version_id}, {"_id": 0}):
        _validate_product_flags(product)
        if product.get("publishable") or product.get("stripe_sync_enabled"):
            if product["status"] != "active":
                raise CommercialCatalogError("active_product_required", "Only active products may be publishable or Stripe-syncable", 409)
            active_prices = await db.commercial_prices.count_documents({
                "catalog_version_id": catalog_version_id,
                "product_id": product["id"],
                "is_active": True,
                "approved_by_owner": True,
            })
            if active_prices < 1:
                raise CommercialCatalogError("active_price_required", "Publishable active products require at least one active owner-approved price", 409)
    now = _now_iso()
    await db.commercial_catalog_versions.update_one(
        {"id": catalog_version_id},
        {"$set": {"status": "published", "published_by_user_id": user["id"], "published_at": now, "updated_at": now}},
    )
    await _audit(user, "commercial.catalog_version_published", "commercial_catalog_version", catalog_version_id, "Commercial catalog version published")
    return serialize_doc(await db.commercial_catalog_versions.find_one({"id": catalog_version_id}, {"_id": 0}))


async def create_product(user: dict, fields: dict[str, Any]) -> dict:
    require_platform_admin(user)
    await _require_draft_catalog(fields["catalog_version_id"])
    clean = {
        **fields,
        "product_key": _clean_text(fields.get("product_key"), "product_key", limit=100),
        "name": _clean_text(fields.get("name"), "name", limit=160),
        "description": _clean_optional_text(fields.get("description")),
        "metadata": fields.get("metadata") or {},
    }
    _validate_product_flags(clean)
    doc = CommercialProduct(**clean).model_dump()
    try:
        await db.commercial_products.insert_one(prepare_for_mongo(doc))
    except DuplicateKeyError:
        raise CommercialCatalogError("duplicate_product_key", "Product key already exists in this catalog version", 409)
    await _audit(user, "commercial.product_created", "commercial_product", doc["id"], f"Commercial product created: {doc['product_key']}", {"catalog_version_id": doc["catalog_version_id"]})
    return serialize_doc(doc)


async def update_product(user: dict, product_id: str, updates: dict[str, Any]) -> dict:
    require_platform_admin(user)
    product = await _product(product_id)
    await _require_draft_catalog(product["catalog_version_id"])
    allowed = {
        k: v
        for k, v in updates.items()
        if k in {"name", "description", "status", "owner_checkpoint", "requires_owner_activation", "publishable", "stripe_sync_enabled", "metadata"}
    }
    if not allowed:
        raise CommercialCatalogError("no_updates", "No supported updates provided", 400)
    merged = {**product, **allowed}
    _validate_product_flags(merged)
    if "name" in allowed:
        allowed["name"] = _clean_text(allowed["name"], "name", limit=160)
    if "description" in allowed:
        allowed["description"] = _clean_optional_text(allowed["description"])
    allowed["updated_at"] = _now_iso()
    await db.commercial_products.update_one({"id": product_id}, {"$set": allowed})
    await _audit(user, "commercial.product_updated", "commercial_product", product_id, "Commercial product updated", {"fields": sorted(allowed)})
    return serialize_doc(await db.commercial_products.find_one({"id": product_id}, {"_id": 0}))


async def list_products(*, status: Optional[str] = None, product_type: Optional[str] = None) -> dict:
    filt: dict[str, Any] = {}
    if status:
        filt["status"] = status
    if product_type:
        filt["product_type"] = product_type
    cur = db.commercial_products.find(filt, {"_id": 0}).sort([("catalog_version_id", 1), ("product_key", 1)])
    items = [serialize_doc(doc) async for doc in cur]
    return {"items": items, "total": len(items)}


async def purchase_eligibility(product_id: str) -> dict:
    product = await _product(product_id)
    if product["status"] in {"inactive", "unavailable", "retired"}:
        return {"product_id": product_id, "purchasable": False, "reason": f"product_{product['status']}"}
    if product["status"] != "active" or not product.get("publishable"):
        return {"product_id": product_id, "purchasable": False, "reason": "product_not_public"}
    active_price = await db.commercial_prices.find_one(
        {"product_id": product_id, "is_active": True, "is_public": True, "approved_by_owner": True},
        {"_id": 0},
    )
    if not active_price:
        return {"product_id": product_id, "purchasable": False, "reason": "active_public_price_required"}
    return {"product_id": product_id, "purchasable": True, "reason": None, "price_id": active_price["id"]}


async def create_price(user: dict, fields: dict[str, Any]) -> dict:
    require_platform_admin(user)
    await _require_draft_catalog(fields["catalog_version_id"])
    product = await _product(fields["product_id"])
    if product["catalog_version_id"] != fields["catalog_version_id"]:
        raise CommercialCatalogError("catalog_product_mismatch", "Product does not belong to the catalog version", 400)
    clean = {**fields, "currency": _clean_currency(fields.get("currency"))}
    await _validate_price_contract(product, clean)
    if clean.get("approved_by_owner") and not clean.get("approved_at"):
        clean["approved_at"] = _now_iso()
    doc = CommercialPrice(**clean).model_dump()
    try:
        await db.commercial_prices.insert_one(prepare_for_mongo(doc))
    except DuplicateKeyError:
        raise CommercialCatalogError("duplicate_price_key", "Price key already exists in this catalog version", 409)
    await _audit(user, "commercial.price_created", "commercial_price", doc["id"], f"Commercial price created: {doc['price_key']}", {"catalog_version_id": doc["catalog_version_id"], "product_id": doc["product_id"]})
    return serialize_doc(doc)


async def update_price(user: dict, price_id: str, updates: dict[str, Any]) -> dict:
    require_platform_admin(user)
    price = await db.commercial_prices.find_one({"id": price_id}, {"_id": 0})
    if not price:
        raise CommercialCatalogError("price_not_found", "Commercial price not found", 404)
    catalog = await _catalog(price["catalog_version_id"])
    if catalog["status"] == "published" and PUBLISHED_LOCKED_PRICE_FIELDS.intersection(updates):
        raise CommercialCatalogError("published_price_immutable", "Published prices are immutable; create a new price revision", 409)
    await _require_draft_catalog(price["catalog_version_id"])
    allowed = {k: v for k, v in updates.items() if k in PUBLISHED_LOCKED_PRICE_FIELDS}
    if not allowed:
        raise CommercialCatalogError("no_updates", "No supported updates provided", 400)
    merged = {**price, **allowed}
    product = await _product(merged["product_id"])
    await _validate_price_contract(product, merged)
    if allowed.get("approved_by_owner") and not merged.get("approved_at"):
        allowed["approved_at"] = _now_iso()
    if "currency" in allowed:
        allowed["currency"] = _clean_currency(allowed["currency"])
    allowed["updated_at"] = _now_iso()
    await db.commercial_prices.update_one({"id": price_id}, {"$set": allowed})
    await _audit(user, "commercial.price_updated", "commercial_price", price_id, "Commercial price updated", {"fields": sorted(allowed)})
    return serialize_doc(await db.commercial_prices.find_one({"id": price_id}, {"_id": 0}))


async def revise_price(user: dict, price_id: str, fields: dict[str, Any]) -> dict:
    require_platform_admin(user)
    source = await db.commercial_prices.find_one({"id": price_id}, {"_id": 0})
    if not source:
        raise CommercialCatalogError("price_not_found", "Commercial price not found", 404)
    await _require_draft_catalog(source["catalog_version_id"])
    product = await _product(source["product_id"])
    clean = {
        **source,
        **fields,
        "id": fields.get("id"),
        "catalog_version_id": source["catalog_version_id"],
        "product_id": source["product_id"],
        "replaces_price_id": source["id"],
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    clean.pop("_id", None)
    if not clean.get("id"):
        clean.pop("id", None)
    clean["currency"] = _clean_currency(clean.get("currency"))
    await _validate_price_contract(product, clean)
    if clean.get("approved_by_owner") and not clean.get("approved_at"):
        clean["approved_at"] = _now_iso()
    doc = CommercialPrice(**clean).model_dump()
    try:
        await db.commercial_prices.insert_one(prepare_for_mongo(doc))
    except DuplicateKeyError:
        raise CommercialCatalogError("duplicate_price_key", "Price revision key already exists in this catalog version", 409)
    await _audit(user, "commercial.price_revised", "commercial_price", doc["id"], "Commercial price revision created", {"replaces_price_id": source["id"]})
    return serialize_doc(doc)


async def list_prices(*, product_id: Optional[str] = None) -> dict:
    filt: dict[str, Any] = {}
    if product_id:
        filt["product_id"] = product_id
    cur = db.commercial_prices.find(filt, {"_id": 0}).sort([("catalog_version_id", 1), ("price_key", 1)])
    items = [serialize_doc(doc) async for doc in cur]
    return {"items": items, "total": len(items)}


async def create_entitlement_rule(user: dict, fields: dict[str, Any]) -> dict:
    require_platform_admin(user)
    await _require_draft_catalog(fields["catalog_version_id"])
    product = await _product(fields["product_id"])
    if product["catalog_version_id"] != fields["catalog_version_id"]:
        raise CommercialCatalogError("catalog_product_mismatch", "Product does not belong to the catalog version", 400)
    feature_key = _clean_text(fields.get("feature_key"), "feature_key", limit=120)
    if not FEATURE_KEY_RE.match(feature_key):
        raise CommercialCatalogError("invalid_feature_key", "Feature key must be lowercase dot/dash/underscore notation", 400)
    if product["status"] == "unavailable" and fields.get("enabled", True):
        raise CommercialCatalogError("unavailable_entitlement_forbidden", "Unavailable products cannot grant entitlements", 409)
    doc = CommercialEntitlementRule(**{**fields, "feature_key": feature_key}).model_dump()
    try:
        await db.commercial_entitlement_rules.insert_one(prepare_for_mongo(doc))
    except DuplicateKeyError:
        raise CommercialCatalogError("duplicate_entitlement_rule", "Entitlement rule already exists for this product", 409)
    await _audit(user, "commercial.entitlement_rule_created", "commercial_entitlement_rule", doc["id"], "Commercial entitlement rule created", {"feature_key": feature_key})
    return serialize_doc(doc)


async def list_entitlement_rules(*, product_id: Optional[str] = None) -> dict:
    filt: dict[str, Any] = {}
    if product_id:
        filt["product_id"] = product_id
    cur = db.commercial_entitlement_rules.find(filt, {"_id": 0}).sort([("catalog_version_id", 1), ("feature_key", 1)])
    items = [serialize_doc(doc) async for doc in cur]
    return {"items": items, "total": len(items)}


async def create_founder_contract(user: dict, fields: dict[str, Any]) -> dict:
    require_platform_admin(user)
    tenant = await db.tenants.find_one({"id": fields["tenant_id"]}, {"_id": 0})
    if not tenant:
        raise CommercialCatalogError("tenant_not_found", "Tenant not found", 404)
    if "user_id" in fields:
        raise CommercialCatalogError("founder_tenant_scoped", "Founder commercial status is tenant/shop-scoped, not user-scoped", 400)
    status = fields.get("founder_status")
    slot = fields.get("founder_slot_number")
    if status in FOUNDER_ACTIVE_STATUSES and slot is None:
        raise CommercialCatalogError("founder_slot_required", "Active Founder contracts require one of the first 25 shop slots", 400)
    doc = FounderTenantContract(**{**fields, "created_by_user_id": user["id"], "ec12_founder_access_preserved": True}).model_dump()
    try:
        await db.founder_tenant_contracts.insert_one(prepare_for_mongo(doc))
    except DuplicateKeyError:
        raise CommercialCatalogError("duplicate_founder_contract", "Founder tenant contract conflicts with an existing tenant or slot", 409)
    await _audit(user, "commercial.founder_contract_created", "founder_tenant_contract", doc["id"], "Founder tenant contract created", {"target_tenant_id": doc["tenant_id"], "founder_status": doc["founder_status"]})
    return serialize_doc(doc)


async def list_founder_contracts(user: dict, *, tenant_id: Optional[str] = None) -> dict:
    filt: dict[str, Any] = {}
    if tenant_id:
        if not _is_platform_admin(user) and tenant_id != user["tenant_id"]:
            raise CommercialCatalogError("tenant_scope_forbidden", "Founder contract lookup is tenant-scoped", 403)
        filt["tenant_id"] = tenant_id
    elif not _is_platform_admin(user):
        filt["tenant_id"] = user["tenant_id"]
    cur = db.founder_tenant_contracts.find(filt, {"_id": 0}).sort([("created_at", -1)])
    items = [serialize_doc(doc) async for doc in cur]
    return {"items": items, "total": len(items)}


async def create_platform_fee_schedule(user: dict, fields: dict[str, Any]) -> dict:
    require_platform_admin(user)
    await _require_draft_catalog(fields["catalog_version_id"])
    doc = PlatformFeeSchedule(**fields).model_dump()
    try:
        await db.platform_fee_schedules.insert_one(prepare_for_mongo(doc))
    except DuplicateKeyError:
        raise CommercialCatalogError("duplicate_fee_schedule", "Platform fee schedule key already exists in this catalog version", 409)
    await _audit(user, "commercial.platform_fee_schedule_created", "platform_fee_schedule", doc["id"], "Platform fee schedule created", {"fee_key": doc["fee_key"]})
    return serialize_doc(doc)


async def list_platform_fee_schedules() -> dict:
    cur = db.platform_fee_schedules.find({}, {"_id": 0}).sort([("catalog_version_id", 1), ("fee_key", 1)])
    items = [serialize_doc(doc) async for doc in cur]
    return {"items": items, "total": len(items)}


def _validate_positive_cents(field: str, value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise CommercialCatalogError("integer_cents_required", f"{field} must be a positive integer number of cents", 400)
    return value


async def create_platform_fee_transaction(user: dict, fields: dict[str, Any]) -> dict:
    require_platform_admin(user)
    _validate_positive_cents("basis_amount_cents", fields.get("basis_amount_cents"))
    _validate_positive_cents("platform_fee_cents", fields.get("platform_fee_cents"))
    doc = PlatformFeeTransactionContract(**{**fields, "created_by_user_id": user["id"], "status": "assessed"}).model_dump()
    await db.platform_fee_transactions.insert_one(prepare_for_mongo(doc))
    await _audit(user, "commercial.platform_fee_assessed_contract", "platform_fee_transaction", doc["id"], "Platform fee transaction contract recorded", {"source_transaction_type": doc["source_transaction_type"]})
    return serialize_doc(doc)


async def create_platform_fee_reversal(user: dict, original_id: str, refund_basis_amount_cents: int) -> dict:
    require_platform_admin(user)
    refund_basis_amount_cents = _validate_positive_cents("refund_basis_amount_cents", refund_basis_amount_cents)
    original = await db.platform_fee_transactions.find_one({"id": original_id, "reversal_of_fee_transaction_id": None}, {"_id": 0})
    if not original:
        raise CommercialCatalogError("platform_fee_transaction_not_found", "Original platform-fee transaction not found", 404)
    if refund_basis_amount_cents > original["basis_amount_cents"]:
        raise CommercialCatalogError("refund_exceeds_original", "Refund basis cannot exceed the original basis amount", 400)
    reversal_fee = int(
        (Decimal(original["platform_fee_cents"]) * Decimal(refund_basis_amount_cents) / Decimal(original["basis_amount_cents"]))
        .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    status = "reversed" if refund_basis_amount_cents == original["basis_amount_cents"] else "partially_reversed"
    doc = PlatformFeeTransactionContract(
        tenant_id=original["tenant_id"],
        source_transaction_type=original["source_transaction_type"],
        source_transaction_id=original["source_transaction_id"],
        fee_schedule_id=original.get("fee_schedule_id"),
        basis_amount_cents=refund_basis_amount_cents,
        platform_fee_cents=reversal_fee,
        currency=original.get("currency", "usd"),
        snapshot_rate_basis_points=original["snapshot_rate_basis_points"],
        status=status,
        reversal_of_fee_transaction_id=original["id"],
        provider_fee_cents=original.get("provider_fee_cents"),
        created_by_user_id=user["id"],
    ).model_dump()
    await db.platform_fee_transactions.insert_one(prepare_for_mongo(doc))
    await _audit(user, "commercial.platform_fee_reversal_contract", "platform_fee_transaction", doc["id"], "Platform fee reversal contract recorded", {"original_id": original_id, "status": status})
    return serialize_doc(doc)


async def create_platform_fee_adjustment(user: dict, original_id: str, fields: dict[str, Any]) -> dict:
    require_platform_admin(user)
    reason = _clean_text(fields.get("adjustment_reason"), "adjustment_reason", limit=500)
    original = await db.platform_fee_transactions.find_one({"id": original_id, "reversal_of_fee_transaction_id": None}, {"_id": 0})
    if not original:
        raise CommercialCatalogError("platform_fee_transaction_not_found", "Original platform-fee transaction not found", 404)
    if not isinstance(fields.get("platform_fee_cents"), int) or isinstance(fields.get("platform_fee_cents"), bool):
        raise CommercialCatalogError("integer_cents_required", "platform_fee_cents must be an integer number of cents", 400)
    doc = PlatformFeeTransactionContract(
        tenant_id=original["tenant_id"],
        source_transaction_type=original["source_transaction_type"],
        source_transaction_id=original["source_transaction_id"],
        fee_schedule_id=original.get("fee_schedule_id"),
        basis_amount_cents=int(fields.get("basis_amount_cents", 0)),
        platform_fee_cents=fields["platform_fee_cents"],
        currency=original.get("currency", "usd"),
        snapshot_rate_basis_points=original["snapshot_rate_basis_points"],
        status="adjusted",
        reversal_of_fee_transaction_id=original["id"],
        adjustment_reason=reason,
        provider_fee_cents=original.get("provider_fee_cents"),
        created_by_user_id=user["id"],
    ).model_dump()
    await db.platform_fee_transactions.insert_one(prepare_for_mongo(doc))
    await _audit(user, "commercial.platform_fee_adjustment_contract", "platform_fee_transaction", doc["id"], "Manual platform fee adjustment contract recorded", {"original_id": original_id, "reason": reason})
    return serialize_doc(doc)
