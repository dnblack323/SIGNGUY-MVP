"""EC9 phase 9A — Pricing Saved Item router.

Saved items reference canonical EC7 Materials by id — never copy material or
inventory data.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..core.time_utils import serialize_doc
from ..deps import require_permission
from ..services.audit import record_audit
from ..services.pricing_saved_items import (
    create_saved_item,
    get_saved_item,
    list_saved_items,
    resolve_quantity_tier_price,
    save_as_variation,
    update_saved_item,
)

router = APIRouter(prefix="/pricing/saved-items", tags=["pricing"])


class PricingSavedItemIn(BaseModel):
    name: str
    category: str
    material_refs: list[str] = Field(default_factory=list)
    pricing_component_refs: list[str] = Field(default_factory=list)
    quantity_tiers: list[dict[str, Any]] = Field(default_factory=list)
    default_production_assumptions: dict[str, Any] = Field(default_factory=dict)
    default_pricing_method: Optional[str] = None
    default_notes: Optional[str] = None
    saved_config: dict[str, Any] = Field(default_factory=dict)
    quick_select: bool = False
    active: bool = True


class PricingSavedItemUpdateIn(BaseModel):
    name: Optional[str] = None
    material_refs: Optional[list[str]] = None
    pricing_component_refs: Optional[list[str]] = None
    quantity_tiers: Optional[list[dict[str, Any]]] = None
    default_production_assumptions: Optional[dict[str, Any]] = None
    default_pricing_method: Optional[str] = None
    default_notes: Optional[str] = None
    saved_config: Optional[dict[str, Any]] = None
    quick_select: Optional[bool] = None
    active: Optional[bool] = None


class SaveAsVariationIn(BaseModel):
    name: str
    saved_config: Optional[dict[str, Any]] = None


@router.get("")
async def list_pricing_saved_items(
    category: Optional[str] = None, active: Optional[bool] = None, quick_select: Optional[bool] = None,
    user: dict = Depends(require_permission(Perm.PRICING_READ)),
) -> dict:
    items = await list_saved_items(user["tenant_id"], category=category, active=active, quick_select=quick_select)
    return {"items": [serialize_doc(d) for d in items]}


@router.get("/{item_id}/tier-price")
async def get_saved_item_tier_price(item_id: str, quantity: int, user: dict = Depends(require_permission(Perm.PRICING_READ))) -> dict:
    """Exact-match quantity-tier lookup (e.g. Business Card tiers). Never
    invents a price for a quantity that doesn't match a configured tier —
    the caller must fall back to manual pricing in that case."""
    doc = await get_saved_item(user["tenant_id"], item_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Saved item not found")
    price = resolve_quantity_tier_price(doc, quantity)
    return {"item_id": item_id, "quantity": quantity, "matched": price is not None, "price": price}


@router.get("/{item_id}")
async def get_pricing_saved_item(item_id: str, user: dict = Depends(require_permission(Perm.PRICING_READ))) -> dict:
    doc = await get_saved_item(user["tenant_id"], item_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Saved item not found")
    return serialize_doc(doc)


@router.post("", status_code=201)
async def create_pricing_saved_item(payload: PricingSavedItemIn, user: dict = Depends(require_permission(Perm.PRICING_WRITE))) -> dict:
    try:
        doc = await create_saved_item(user["tenant_id"], payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="pricing.saved_item.create", entity_type="pricing_saved_item", entity_id=doc["id"],
        summary=f"Created saved pricing item '{payload.name}'",
    )
    return serialize_doc(doc)


@router.patch("/{item_id}")
async def patch_pricing_saved_item(item_id: str, payload: PricingSavedItemUpdateIn, user: dict = Depends(require_permission(Perm.PRICING_WRITE))) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    try:
        doc = await update_saved_item(user["tenant_id"], item_id, updates)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="pricing.saved_item.update", entity_type="pricing_saved_item", entity_id=item_id,
        summary="Updated saved pricing item", diff={"changes": updates},
    )
    return serialize_doc(doc)


@router.post("/{item_id}/save-as-variation", status_code=201)
async def post_save_as_variation(item_id: str, payload: SaveAsVariationIn, user: dict = Depends(require_permission(Perm.PRICING_WRITE))) -> dict:
    overrides = payload.model_dump(exclude_none=True)
    try:
        doc = await save_as_variation(user["tenant_id"], item_id, overrides)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="pricing.saved_item.save_as_variation", entity_type="pricing_saved_item", entity_id=doc["id"],
        summary=f"Saved variation '{payload.name}' from item '{item_id}'",
    )
    return serialize_doc(doc)
