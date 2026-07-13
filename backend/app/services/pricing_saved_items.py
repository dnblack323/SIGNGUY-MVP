"""EC9 phase 9A/9D — Pricing Saved Item service.

`material_refs` must point at existing, tenant-owned canonical `Material`
records (EC7). No material data is copied — only the reference id is stored.

Phase 9D adds: the preloaded Promotional "commonly sold" starter items
(Business Cards / Magnetic Business Cards) per the controlling EC09 spec
(exact tiers, never invented), lazily seeded per tenant the same way
`pricing_settings` clones the starter pack on first access; a `quick_select`
list filter; and a pure exact-match quantity-tier price resolver used by the
tier-price lookup endpoint (and, later, EC9 phases 9E/9F).
"""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import utc_now
from ..models.pricing_saved_item import PricingSavedItem
from .starter_defaults import CATEGORY_IDS


def _now_iso() -> str:
    return utc_now().isoformat()


# EC09 §Appendix — Promotional Items / Business Cards: exact preloaded tiers.
# Quantity tiers are dollar-based {quantity, price} pairs. A quantity that does
# not exactly match a configured tier must NEVER get an invented price — see
# `resolve_quantity_tier_price`.
BUSINESS_CARD_STARTER_ITEMS: list[dict[str, Any]] = [
    {
        "name": "Standard Paper Business Cards",
        "category": "promotional",
        "default_pricing_method": "tier_pricing",
        "quantity_tiers": [
            {"quantity": 100, "price": 25.0},
            {"quantity": 250, "price": 45.0},
            {"quantity": 500, "price": 75.0},
            {"quantity": 1000, "price": 125.0},
            {"quantity": 2000, "price": 175.0},
            {"quantity": 2500, "price": 225.0},
        ],
        "default_notes": "Preloaded starter tier pricing (EC09 Promotional Items appendix).",
        "quick_select": True,
        "active": True,
        "created_from": "new",
    },
    {
        "name": "Magnetic Business Cards",
        "category": "promotional",
        "default_pricing_method": "tier_pricing",
        "quantity_tiers": [
            {"quantity": 25, "price": 25.0},
            {"quantity": 50, "price": 50.0},
            {"quantity": 100, "price": 75.0},
            {"quantity": 200, "price": 100.0},
            {"quantity": 500, "price": 175.0},
            {"quantity": 1000, "price": 275.0},
        ],
        "default_notes": "Preloaded starter tier pricing (EC09 Promotional Items appendix).",
        "quick_select": True,
        "active": True,
        "created_from": "new",
    },
]


async def seed_promotional_starter_items(tenant_id: str) -> None:
    """Idempotently clone the Business Card starter items into a tenant's
    saved-items list on first access — mirrors how `pricing_settings` clones
    the starter pack. Never overwrites a tenant's own edited/renamed copy."""
    names = [i["name"] for i in BUSINESS_CARD_STARTER_ITEMS]
    existing = {
        d["name"] async for d in db.pricing_saved_items.find(
            {"tenant_id": tenant_id, "name": {"$in": names}}, {"_id": 0, "name": 1}
        )
    }
    for starter in BUSINESS_CARD_STARTER_ITEMS:
        if starter["name"] in existing:
            continue
        doc = PricingSavedItem(tenant_id=tenant_id, **starter).model_dump()
        await db.pricing_saved_items.insert_one(dict(doc))


def resolve_quantity_tier_price(item: dict[str, Any], quantity: int) -> Optional[float]:
    """Exact-match tier lookup only. Returns None (never an invented price)
    when `quantity` does not exactly match a configured tier's `quantity`."""
    for tier in item.get("quantity_tiers") or []:
        if int(tier.get("quantity", -1)) == int(quantity):
            return float(tier["price"])
    return None


async def _validate_material_refs(tenant_id: str, material_ids: list[str]) -> None:
    for mid in material_ids or []:
        mat = await db.materials.find_one({"id": mid, "tenant_id": tenant_id}, {"_id": 0, "id": 1, "active": 1})
        if not mat:
            raise ValueError(f"Material '{mid}' not found for this tenant")
        if not mat.get("active", True):
            raise ValueError(f"Material '{mid}' is archived and cannot be newly selected — restore it first")


async def create_saved_item(tenant_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    if fields.get("category") not in CATEGORY_IDS:
        raise ValueError(f"Unknown category: {fields.get('category')}")
    await _validate_material_refs(tenant_id, fields.get("material_refs") or [])
    doc = PricingSavedItem(tenant_id=tenant_id, **fields).model_dump()
    await db.pricing_saved_items.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


async def list_saved_items(tenant_id: str, category: Optional[str] = None, active: Optional[bool] = None, quick_select: Optional[bool] = None) -> list[dict[str, Any]]:
    await seed_promotional_starter_items(tenant_id)
    filt: dict[str, Any] = {"tenant_id": tenant_id}
    if category:
        filt["category"] = category
    if active is not None:
        filt["active"] = active
    if quick_select is not None:
        filt["quick_select"] = quick_select
    return [doc async for doc in db.pricing_saved_items.find(filt, {"_id": 0}).sort("created_at", 1)]


async def get_saved_item(tenant_id: str, item_id: str) -> Optional[dict[str, Any]]:
    return await db.pricing_saved_items.find_one({"tenant_id": tenant_id, "id": item_id}, {"_id": 0})


async def update_saved_item(tenant_id: str, item_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    if updates.get("material_refs") is not None:
        await _validate_material_refs(tenant_id, updates["material_refs"])
    updates = {k: v for k, v in updates.items() if v is not None}
    updates["updated_at"] = _now_iso()
    res = await db.pricing_saved_items.update_one({"id": item_id, "tenant_id": tenant_id}, {"$set": updates})
    if res.matched_count == 0:
        raise ValueError("Saved item not found")
    doc = await db.pricing_saved_items.find_one({"id": item_id}, {"_id": 0})
    return doc or {}


async def save_as_variation(tenant_id: str, source_item_id: str, overrides: dict[str, Any]) -> dict[str, Any]:
    """Clone an existing saved item as a new variation (never mutates the source)."""
    source = await get_saved_item(tenant_id, source_item_id)
    if not source:
        raise ValueError("Source saved item not found")
    base = {k: v for k, v in source.items() if k not in ("id", "created_at", "updated_at", "tenant_id")}
    base.update(overrides)
    base["variation_of_id"] = source_item_id
    base["created_from"] = "variation"
    return await create_saved_item(tenant_id, base)
