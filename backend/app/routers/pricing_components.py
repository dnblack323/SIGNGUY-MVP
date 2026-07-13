"""EC9 phase 9A — Pricing Component router (non-inventory charges/fees)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..core.time_utils import serialize_doc
from ..deps import require_permission
from ..services.audit import record_audit
from ..services.pricing_components import (
    create_component,
    get_component,
    list_components,
    update_component,
)

router = APIRouter(prefix="/pricing/components", tags=["pricing"])


class PricingComponentIn(BaseModel):
    key: str
    name: str
    charge_type: str = "other"
    amount: Optional[float] = Field(None, ge=0)
    percent: Optional[float] = Field(None, ge=0, le=200)
    category_applicability: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    active: bool = True


class PricingComponentUpdateIn(BaseModel):
    name: Optional[str] = None
    charge_type: Optional[str] = None
    amount: Optional[float] = Field(None, ge=0)
    percent: Optional[float] = Field(None, ge=0, le=200)
    category_applicability: Optional[list[str]] = None
    notes: Optional[str] = None
    active: Optional[bool] = None


@router.get("")
async def list_pricing_components(active: Optional[bool] = None, user: dict = Depends(require_permission(Perm.PRICING_READ))) -> dict:
    items = await list_components(user["tenant_id"], active=active)
    return {"items": [serialize_doc(d) for d in items]}


@router.get("/{component_id}")
async def get_pricing_component(component_id: str, user: dict = Depends(require_permission(Perm.PRICING_READ))) -> dict:
    doc = await get_component(user["tenant_id"], component_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Pricing component not found")
    return serialize_doc(doc)


@router.post("", status_code=201)
async def create_pricing_component(payload: PricingComponentIn, user: dict = Depends(require_permission(Perm.PRICING_WRITE))) -> dict:
    try:
        doc = await create_component(user["tenant_id"], payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="pricing.component.create", entity_type="pricing_component", entity_id=doc["id"],
        summary=f"Created pricing component '{payload.name}'",
    )
    return serialize_doc(doc)


@router.patch("/{component_id}")
async def patch_pricing_component(component_id: str, payload: PricingComponentUpdateIn, user: dict = Depends(require_permission(Perm.PRICING_WRITE))) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    try:
        doc = await update_component(user["tenant_id"], component_id, updates)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="pricing.component.update", entity_type="pricing_component", entity_id=component_id,
        summary="Updated pricing component", diff={"changes": updates},
    )
    return serialize_doc(doc)
