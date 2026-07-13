"""EC9 phase 9A — Material Pricing Profile router.

Links a canonical EC7 `Material` to a tenant-scoped pricing profile. Does not
create, edit, or duplicate any Material/inventory field.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..core.time_utils import serialize_doc
from ..deps import require_permission
from ..services.audit import record_audit
from ..services.pricing_materials import (
    create_profile,
    get_profile,
    list_profiles,
    update_profile,
)

router = APIRouter(prefix="/pricing/material-profiles", tags=["pricing"])


class MaterialPricingProfileIn(BaseModel):
    pricing_unit: str = "per_sqft"
    normalized_cost_basis: Optional[float] = Field(None, ge=0)
    waste_percent: float = Field(0.0, ge=0, le=100)
    default_markup_multiplier: Optional[float] = Field(None, ge=0)
    default_margin_percent: Optional[float] = Field(None, ge=0, le=99.9)
    suggested_sell_rate: Optional[float] = Field(None, ge=0)
    minimum_sell_amount: Optional[float] = Field(None, ge=0)
    category_applicability: list[str] = Field(default_factory=list)
    quantity_tiers: list[dict[str, Any]] = Field(default_factory=list)
    pricing_source: str = "manual"
    effective_at: Optional[str] = None
    pricing_notes: Optional[str] = None
    active: bool = True


class MaterialPricingProfileUpdateIn(BaseModel):
    pricing_unit: Optional[str] = None
    normalized_cost_basis: Optional[float] = Field(None, ge=0)
    waste_percent: Optional[float] = Field(None, ge=0, le=100)
    default_markup_multiplier: Optional[float] = Field(None, ge=0)
    default_margin_percent: Optional[float] = Field(None, ge=0, le=99.9)
    suggested_sell_rate: Optional[float] = Field(None, ge=0)
    minimum_sell_amount: Optional[float] = Field(None, ge=0)
    category_applicability: Optional[list[str]] = None
    quantity_tiers: Optional[list[dict[str, Any]]] = None
    pricing_notes: Optional[str] = None
    last_reviewed_at: Optional[str] = None
    active: Optional[bool] = None


@router.get("")
async def list_material_profiles(active: Optional[bool] = None, user: dict = Depends(require_permission(Perm.PRICING_READ))) -> dict:
    items = await list_profiles(user["tenant_id"], active=active)
    return {"items": [serialize_doc(d) for d in items]}


@router.get("/{profile_id}")
async def get_material_profile(profile_id: str, user: dict = Depends(require_permission(Perm.PRICING_READ))) -> dict:
    doc = await get_profile(user["tenant_id"], profile_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Pricing profile not found")
    return serialize_doc(doc)


@router.post("/materials/{material_id}", status_code=201)
async def create_material_profile(material_id: str, payload: MaterialPricingProfileIn, user: dict = Depends(require_permission(Perm.PRICING_WRITE))) -> dict:
    try:
        doc = await create_profile(user["tenant_id"], material_id, payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="pricing.material_profile.create", entity_type="material_pricing_profile", entity_id=doc["id"],
        summary=f"Created pricing profile for material '{material_id}'",
    )
    return serialize_doc(doc)


@router.patch("/{profile_id}")
async def patch_material_profile(profile_id: str, payload: MaterialPricingProfileUpdateIn, user: dict = Depends(require_permission(Perm.PRICING_WRITE))) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    try:
        doc = await update_profile(user["tenant_id"], profile_id, updates)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="pricing.material_profile.update", entity_type="material_pricing_profile", entity_id=profile_id,
        summary="Updated material pricing profile", diff={"changes": updates},
    )
    return serialize_doc(doc)
