"""EC9 phase 9A — Pricing Saved Item service.

`material_refs` must point at existing, tenant-owned canonical `Material`
records (EC7). No material data is copied — only the reference id is stored.
"""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import utc_now
from ..models.pricing_saved_item import PricingSavedItem
from .starter_defaults import CATEGORY_IDS


def _now_iso() -> str:
    return utc_now().isoformat()


async def _validate_material_refs(tenant_id: str, material_ids: list[str]) -> None:
    for mid in material_ids or []:
        exists = await db.materials.find_one({"id": mid, "tenant_id": tenant_id}, {"_id": 0, "id": 1})
        if not exists:
            raise ValueError(f"Material '{mid}' not found for this tenant")


async def create_saved_item(tenant_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    if fields.get("category") not in CATEGORY_IDS:
        raise ValueError(f"Unknown category: {fields.get('category')}")
    await _validate_material_refs(tenant_id, fields.get("material_refs") or [])
    doc = PricingSavedItem(tenant_id=tenant_id, **fields).model_dump()
    await db.pricing_saved_items.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


async def list_saved_items(tenant_id: str, category: Optional[str] = None, active: Optional[bool] = None) -> list[dict[str, Any]]:
    filt: dict[str, Any] = {"tenant_id": tenant_id}
    if category:
        filt["category"] = category
    if active is not None:
        filt["active"] = active
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
