"""EC9 phase 9A — Material Pricing Profile service.

One profile per (tenant_id, material_id). The linked canonical `Material`
(EC7) is never duplicated — this service only ever reads `db.materials` to
validate the material exists and belongs to the tenant, and writes back the
existing (already reserved) `Material.pricing_material_id` field so the two
records point at each other.
"""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import utc_now
from ..models.material_pricing_profile import MaterialPricingProfile
from .starter_defaults import CATEGORY_IDS


def _now_iso() -> str:
    return utc_now().isoformat()


async def _get_tenant_material(tenant_id: str, material_id: str) -> Optional[dict[str, Any]]:
    return await db.materials.find_one({"id": material_id, "tenant_id": tenant_id}, {"_id": 0})


async def create_profile(tenant_id: str, material_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    material = await _get_tenant_material(tenant_id, material_id)
    if not material:
        raise ValueError("Material not found for this tenant")
    existing = await db.material_pricing_profiles.find_one({"tenant_id": tenant_id, "material_id": material_id})
    if existing:
        raise ValueError("A pricing profile already exists for this material")
    bad_categories = [c for c in fields.get("category_applicability") or [] if c not in CATEGORY_IDS]
    if bad_categories:
        raise ValueError(f"Unknown category id(s): {bad_categories}")
    profile = MaterialPricingProfile(tenant_id=tenant_id, material_id=material_id, **fields).model_dump()
    await db.material_pricing_profiles.insert_one(dict(profile))
    await db.materials.update_one({"id": material_id, "tenant_id": tenant_id}, {"$set": {"pricing_material_id": profile["id"]}})
    profile.pop("_id", None)
    return profile


async def get_profile_by_material(tenant_id: str, material_id: str) -> Optional[dict[str, Any]]:
    return await db.material_pricing_profiles.find_one({"tenant_id": tenant_id, "material_id": material_id}, {"_id": 0})


async def get_profile(tenant_id: str, profile_id: str) -> Optional[dict[str, Any]]:
    return await db.material_pricing_profiles.find_one({"tenant_id": tenant_id, "id": profile_id}, {"_id": 0})


async def list_profiles(tenant_id: str, active: Optional[bool] = None) -> list[dict[str, Any]]:
    filt: dict[str, Any] = {"tenant_id": tenant_id}
    if active is not None:
        filt["active"] = active
    return [doc async for doc in db.material_pricing_profiles.find(filt, {"_id": 0}).sort("created_at", 1)]


async def update_profile(tenant_id: str, profile_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    bad_categories = [c for c in updates.get("category_applicability") or [] if c not in CATEGORY_IDS]
    if bad_categories:
        raise ValueError(f"Unknown category id(s): {bad_categories}")
    updates = {k: v for k, v in updates.items() if v is not None}
    updates["updated_at"] = _now_iso()
    res = await db.material_pricing_profiles.update_one({"id": profile_id, "tenant_id": tenant_id}, {"$set": updates})
    if res.matched_count == 0:
        raise ValueError("Pricing profile not found")
    doc = await db.material_pricing_profiles.find_one({"id": profile_id}, {"_id": 0})
    return doc or {}
