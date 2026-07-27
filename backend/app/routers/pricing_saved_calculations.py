"""EC9 Phase 9I-G - Saved Calculation Library API."""
from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..deps import require_permission
from ..services.audit import record_audit
from ..services.pricing_saved_calculations import (
    SavedCalculationError,
    archive_saved_calculation,
    create_saved_calculation,
    duplicate_saved_calculation,
    get_saved_calculation,
    list_saved_calculations,
    recalculate_saved_calculation,
    restore_saved_calculation,
    update_saved_calculation_metadata,
)

router = APIRouter(prefix="/pricing/saved-calculations", tags=["pricing"])


class SavedCalculationCreateIn(BaseModel):
    name: str
    notes: Optional[str] = None
    calculation_inputs: dict[str, Any] = Field(default_factory=dict)
    selected_method_id: Optional[str] = None
    source_context: Literal["pricing_calculator", "quote_item", "order_item"] = "pricing_calculator"


class SavedCalculationUpdateIn(BaseModel):
    name: Optional[str] = None
    notes: Optional[str] = None


class SavedCalculationDuplicateIn(BaseModel):
    name: Optional[str] = None
    notes: Optional[str] = None


def _raise(exc: SavedCalculationError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("")
async def list_pricing_saved_calculations(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    archived: Optional[bool] = Query(False),
    user: dict = Depends(require_permission(Perm.PRICING_READ)),
) -> dict:
    try:
        items = await list_saved_calculations(user["tenant_id"], search=search, category=category, archived=archived)
    except SavedCalculationError as exc:
        _raise(exc)
    return {"items": items}


@router.post("", status_code=201)
async def create_pricing_saved_calculation(
    payload: SavedCalculationCreateIn,
    user: dict = Depends(require_permission(Perm.PRICING_WRITE, Perm.PRICING_CALCULATE)),
) -> dict:
    try:
        doc = await create_saved_calculation(user["tenant_id"], user, payload.model_dump())
    except SavedCalculationError as exc:
        _raise(exc)
    await record_audit(
        tenant_id=user["tenant_id"],
        actor_user_id=user["id"],
        actor_email=user.get("email"),
        action="pricing.saved_calculation.create",
        entity_type="pricing_saved_calculation",
        entity_id=doc["id"],
        summary=f"Saved pricing calculation '{doc['name']}'",
        diff={"category": doc["category"], "source_context": doc.get("source_context")},
    )
    return doc


@router.get("/{calculation_id}")
async def get_pricing_saved_calculation(
    calculation_id: str,
    user: dict = Depends(require_permission(Perm.PRICING_READ)),
) -> dict:
    doc = await get_saved_calculation(user["tenant_id"], calculation_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Saved calculation not found")
    return doc


@router.patch("/{calculation_id}")
async def patch_pricing_saved_calculation(
    calculation_id: str,
    payload: SavedCalculationUpdateIn,
    user: dict = Depends(require_permission(Perm.PRICING_WRITE)),
) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    try:
        doc = await update_saved_calculation_metadata(user["tenant_id"], calculation_id, user, updates)
    except SavedCalculationError as exc:
        _raise(exc)
    await record_audit(
        tenant_id=user["tenant_id"],
        actor_user_id=user["id"],
        actor_email=user.get("email"),
        action="pricing.saved_calculation.metadata_update",
        entity_type="pricing_saved_calculation",
        entity_id=calculation_id,
        summary="Updated saved calculation metadata",
        diff={"changes": updates},
    )
    return doc


@router.post("/{calculation_id}/duplicate", status_code=201)
async def duplicate_pricing_saved_calculation(
    calculation_id: str,
    payload: SavedCalculationDuplicateIn | None = None,
    user: dict = Depends(require_permission(Perm.PRICING_WRITE)),
) -> dict:
    payload = payload or SavedCalculationDuplicateIn()
    try:
        doc = await duplicate_saved_calculation(
            user["tenant_id"],
            calculation_id,
            user,
            name=payload.name,
            notes=payload.notes,
        )
    except SavedCalculationError as exc:
        _raise(exc)
    await record_audit(
        tenant_id=user["tenant_id"],
        actor_user_id=user["id"],
        actor_email=user.get("email"),
        action="pricing.saved_calculation.duplicate",
        entity_type="pricing_saved_calculation",
        entity_id=doc["id"],
        summary=f"Duplicated saved calculation '{calculation_id}'",
    )
    return doc


@router.post("/{calculation_id}/archive")
async def archive_pricing_saved_calculation(
    calculation_id: str,
    user: dict = Depends(require_permission(Perm.PRICING_WRITE)),
) -> dict:
    try:
        doc = await archive_saved_calculation(user["tenant_id"], calculation_id, user)
    except SavedCalculationError as exc:
        _raise(exc)
    await record_audit(
        tenant_id=user["tenant_id"],
        actor_user_id=user["id"],
        actor_email=user.get("email"),
        action="pricing.saved_calculation.archive",
        entity_type="pricing_saved_calculation",
        entity_id=calculation_id,
        summary="Archived saved calculation",
    )
    return doc


@router.post("/{calculation_id}/restore")
async def restore_pricing_saved_calculation(
    calculation_id: str,
    user: dict = Depends(require_permission(Perm.PRICING_WRITE)),
) -> dict:
    try:
        doc = await restore_saved_calculation(user["tenant_id"], calculation_id, user)
    except SavedCalculationError as exc:
        _raise(exc)
    await record_audit(
        tenant_id=user["tenant_id"],
        actor_user_id=user["id"],
        actor_email=user.get("email"),
        action="pricing.saved_calculation.restore",
        entity_type="pricing_saved_calculation",
        entity_id=calculation_id,
        summary="Restored saved calculation",
    )
    return doc


@router.post("/{calculation_id}/recalculate")
async def use_pricing_saved_calculation(
    calculation_id: str,
    user: dict = Depends(require_permission(Perm.PRICING_READ, Perm.PRICING_CALCULATE)),
) -> dict:
    try:
        return await recalculate_saved_calculation(user["tenant_id"], calculation_id)
    except SavedCalculationError as exc:
        _raise(exc)
