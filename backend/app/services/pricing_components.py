"""EC9 phase 9A — Pricing Component service (non-inventory charges/fees)."""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import utc_now
from ..models.pricing_component import PricingComponent
from .starter_defaults import CATEGORY_IDS


def _now_iso() -> str:
    return utc_now().isoformat()


def _validate_categories(cats: list[str]) -> None:
    bad = [c for c in cats or [] if c not in CATEGORY_IDS]
    if bad:
        raise ValueError(f"Unknown category id(s): {bad}")


async def create_component(tenant_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    _validate_categories(fields.get("category_applicability") or [])
    existing = await db.pricing_components.find_one({"tenant_id": tenant_id, "key": fields.get("key")})
    if existing:
        raise ValueError("A pricing component with this key already exists")
    doc = PricingComponent(tenant_id=tenant_id, **fields).model_dump()
    await db.pricing_components.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


async def list_components(tenant_id: str, active: Optional[bool] = None) -> list[dict[str, Any]]:
    filt: dict[str, Any] = {"tenant_id": tenant_id}
    if active is not None:
        filt["active"] = active
    return [doc async for doc in db.pricing_components.find(filt, {"_id": 0}).sort("created_at", 1)]


async def get_component(tenant_id: str, component_id: str) -> Optional[dict[str, Any]]:
    return await db.pricing_components.find_one({"tenant_id": tenant_id, "id": component_id}, {"_id": 0})


async def update_component(tenant_id: str, component_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    _validate_categories(updates.get("category_applicability") or [])
    updates = {k: v for k, v in updates.items() if v is not None}
    updates["updated_at"] = _now_iso()
    res = await db.pricing_components.update_one({"id": component_id, "tenant_id": tenant_id}, {"$set": updates})
    if res.matched_count == 0:
        raise ValueError("Pricing component not found")
    doc = await db.pricing_components.find_one({"id": component_id}, {"_id": 0})
    return doc or {}
