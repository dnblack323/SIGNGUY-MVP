"""EC10 Phase 10A — Intake router.

Staff-only. Customer-facing/public intake submission is explicitly deferred
to a later phase (10B/10E) per the EC10 preflight — no such route exists here.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import serialize_doc
from ..deps import require_permission
from ..services import intake_service
from ..services.intake_service import IntakeError

router = APIRouter(prefix="/intake", tags=["intake"])

_ERROR_STATUS = {
    "customer_not_found": 404, "quote_not_found": 404, "order_not_found": 404,
    "assigned_user_not_found": 404, "file_not_found": 404,
    "questionnaire_submission_not_found": 404, "intake_not_found": 404,
    "intake_locked": 400, "invalid_transition": 400, "reason_required": 400,
    "quote_id_required": 400, "order_id_required": 400,
}


def _raise(ex: IntakeError) -> None:
    raise HTTPException(status_code=_ERROR_STATUS.get(ex.code, 400), detail=str(ex))


class IntakeItemIn(BaseModel):
    category: Optional[str] = None
    item_name: Optional[str] = None
    description: Optional[str] = None
    quantity: int = 1
    measurements: dict[str, Any] = Field(default_factory=dict)
    category_inputs: dict[str, Any] = Field(default_factory=dict)
    saved_item_id: Optional[str] = None
    material_profile_id: Optional[str] = None
    pricing_component_ids: list[str] = Field(default_factory=list)
    file_ids: list[str] = Field(default_factory=list)
    customer_notes: Optional[str] = None
    internal_notes: Optional[str] = None
    proof_required: bool = False
    approval_required: bool = False
    requested_due_date: Optional[str] = None
    installation_required: bool = False


class IntakeCreateIn(BaseModel):
    source_type: str = "internal_user"
    source_reference: Optional[str] = None
    submitted_by_customer_id: Optional[str] = None
    customer_id: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    project_name: Optional[str] = None
    project_description: Optional[str] = None
    intake_type: Optional[str] = None
    priority: str = "normal"
    requested_due_date: Optional[str] = None
    installation_required: bool = False
    installation_location: Optional[str] = None
    installation_notes: Optional[str] = None
    assigned_user_id: Optional[str] = None
    quote_id: Optional[str] = None
    order_id: Optional[str] = None
    questionnaire_submission_ids: list[str] = Field(default_factory=list)
    file_ids: list[str] = Field(default_factory=list)
    items: list[IntakeItemIn] = Field(default_factory=list)
    proof_required: bool = False
    approval_required: bool = False
    internal_notes: Optional[str] = None
    customer_notes: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None


class IntakeUpdateIn(BaseModel):
    customer_id: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    project_name: Optional[str] = None
    project_description: Optional[str] = None
    intake_type: Optional[str] = None
    priority: Optional[str] = None
    requested_due_date: Optional[str] = None
    installation_required: Optional[bool] = None
    installation_location: Optional[str] = None
    installation_notes: Optional[str] = None
    assigned_user_id: Optional[str] = None
    quote_id: Optional[str] = None
    order_id: Optional[str] = None
    questionnaire_submission_ids: Optional[list[str]] = None
    file_ids: Optional[list[str]] = None
    proof_required: Optional[bool] = None
    approval_required: Optional[bool] = None
    internal_notes: Optional[str] = None
    customer_notes: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class IntakeTransitionIn(BaseModel):
    target: str
    reason: Optional[str] = None
    quote_id: Optional[str] = None
    order_id: Optional[str] = None


@router.post("", status_code=201)
async def create(payload: IntakeCreateIn, user: dict = Depends(require_permission(Perm.INTAKE_WRITE))) -> dict:
    try:
        return await intake_service.create_intake(
            tenant_id=user["tenant_id"],
            payload=payload.model_dump(),
            created_by_user_id=user["id"], actor_email=user["email"],
        )
    except IntakeError as ex:
        _raise(ex)


@router.get("")
async def list_intake(
    status: Optional[str] = Query(None), customer_id: Optional[str] = Query(None),
    quote_id: Optional[str] = Query(None), order_id: Optional[str] = Query(None),
    assigned_user_id: Optional[str] = Query(None),
    limit: int = Query(100, le=500), skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.INTAKE_READ)),
) -> dict:
    q: dict = {"tenant_id": user["tenant_id"]}
    if status: q["status"] = status
    if customer_id: q["customer_id"] = customer_id
    if quote_id: q["quote_id"] = quote_id
    if order_id: q["order_id"] = order_id
    if assigned_user_id: q["assigned_user_id"] = assigned_user_id
    total = await db.intake_submissions.count_documents(q)
    cur = db.intake_submissions.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    return {"items": [serialize_doc(d) async for d in cur], "total": total, "limit": limit, "skip": skip}


@router.get("/{intake_id}")
async def get_intake(intake_id: str, user: dict = Depends(require_permission(Perm.INTAKE_READ))) -> dict:
    doc = await db.intake_submissions.find_one({"id": intake_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Intake submission not found")
    return serialize_doc(doc)


@router.patch("/{intake_id}")
async def update(intake_id: str, payload: IntakeUpdateIn, user: dict = Depends(require_permission(Perm.INTAKE_WRITE))) -> dict:
    try:
        return await intake_service.update_intake(
            tenant_id=user["tenant_id"], intake_id=intake_id,
            updates=payload.model_dump(exclude_unset=True),
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except IntakeError as ex:
        _raise(ex)


@router.post("/{intake_id}/items", status_code=201)
async def add_item(intake_id: str, payload: IntakeItemIn, user: dict = Depends(require_permission(Perm.INTAKE_WRITE))) -> dict:
    try:
        return await intake_service.add_item(
            tenant_id=user["tenant_id"], intake_id=intake_id, item=payload.model_dump(),
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except IntakeError as ex:
        _raise(ex)


@router.post("/{intake_id}/transition")
async def transition(intake_id: str, payload: IntakeTransitionIn, user: dict = Depends(require_permission(Perm.INTAKE_WRITE))) -> dict:
    try:
        return await intake_service.transition(
            tenant_id=user["tenant_id"], intake_id=intake_id, target=payload.target,
            reason=payload.reason, quote_id=payload.quote_id, order_id=payload.order_id,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except IntakeError as ex:
        _raise(ex)


@router.get("/{intake_id}/conversion-preview")
async def conversion_preview(intake_id: str, user: dict = Depends(require_permission(Perm.INTAKE_READ))) -> dict:
    """Pure, non-persisting preview of what Phase 10F's conversion would write.
    Never invents a price; never writes a Quote/Order."""
    doc = await db.intake_submissions.find_one({"id": intake_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Intake submission not found")
    return intake_service.build_conversion_preview(doc)
