"""EC9 Phase 9G — Advisory request/response endpoints (§8-§12).

No live AI/web/market-data provider call exists anywhere behind these
endpoints. `POST /requests` always returns every requested advisory type as
`status="unavailable"` until EC16/EC17 wires in a real provider.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..deps import require_permission
from ..services.pricing_advisory import (
    create_advisory_request,
    decide_advisory_response,
    get_advisory_request,
    list_advisory_requests,
)

router = APIRouter(prefix="/pricing/advisory", tags=["pricing"])


class AdvisoryRequestIn(BaseModel):
    category: Optional[str] = None
    item_description: Optional[str] = None
    quantity: Optional[int] = None
    calculator_inputs: dict[str, Any] = Field(default_factory=dict)
    material_summary: dict[str, Any] = Field(default_factory=dict)
    component_summary: list[dict[str, Any]] = Field(default_factory=list)
    current_suggested_price_cents: Optional[int] = None
    manual_price_cents: Optional[int] = None
    selected_final_price_cents: Optional[int] = None
    estimated_cost_cents: Optional[int] = None
    target_margin_percent: Optional[float] = None
    historical_snapshot_id: Optional[str] = None
    geographic_market_scope: Optional[str] = None
    owner_notes: Optional[str] = None
    requested_advisory_types: list[str] = Field(default_factory=list)
    data_consent: bool = False


class AdvisoryDecisionIn(BaseModel):
    decision: str  # "accepted" | "rejected"
    notes: Optional[str] = None


@router.post("/requests", status_code=201)
async def create_request(payload: AdvisoryRequestIn, user: dict = Depends(require_permission(Perm.PRICING_WRITE))) -> dict:
    return await create_advisory_request(user["tenant_id"], user["id"], payload.model_dump())


@router.get("/requests")
async def list_requests(
    historical_snapshot_id: Optional[str] = Query(None),
    user: dict = Depends(require_permission(Perm.PRICING_READ)),
) -> dict:
    items = await list_advisory_requests(user["tenant_id"], historical_snapshot_id=historical_snapshot_id)
    return {"items": items}


@router.get("/requests/{request_id}")
async def get_request(request_id: str, user: dict = Depends(require_permission(Perm.PRICING_READ))) -> dict:
    doc = await get_advisory_request(user["tenant_id"], request_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Advisory request not found")
    return doc


@router.post("/requests/{request_id}/responses/{advisory_type}/decision")
async def decide(
    request_id: str, advisory_type: str, payload: AdvisoryDecisionIn,
    user: dict = Depends(require_permission(Perm.PRICING_WRITE)),
) -> dict:
    try:
        return await decide_advisory_response(
            user["tenant_id"], request_id, advisory_type, payload.decision,
            user_id=user["id"], notes=payload.notes,
        )
    except ValueError as e:
        code_map = {
            "invalid_decision": (400, "decision must be 'accepted' or 'rejected'"),
            "advisory_request_not_found": (404, "Advisory request not found"),
            "advisory_response_not_found": (404, "Advisory response not found for that type"),
        }
        status, msg = code_map.get(str(e), (400, str(e)))
        raise HTTPException(status_code=status, detail=msg)
