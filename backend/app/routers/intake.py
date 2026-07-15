"""EC10 Phase 10A — Intake router.

Staff-only. Customer-facing/public intake submission is explicitly deferred
to a later phase (10B/10E) per the EC10 preflight — no such route exists here.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import serialize_doc
from ..deps import require_permission
from ..services import intake_service
from ..models.intake_submission import IntakePricingStatus
from ..services.intake_service import IntakeError

router = APIRouter(prefix="/intake", tags=["intake"])

_ERROR_STATUS = {
    "customer_not_found": 404, "quote_not_found": 404, "order_not_found": 404,
    "assigned_user_not_found": 404, "file_not_found": 404,
    "questionnaire_submission_not_found": 404, "intake_not_found": 404,
    "item_not_found": 404, "pricing_snapshot_not_found": 404,
    "intake_locked": 400, "invalid_transition": 400, "reason_required": 400,
    "quote_id_required": 400, "order_id_required": 400, "missing_information": 400,
    "item_converted_cannot_remove": 400, "reorder_mismatch": 400, "manual_price_required": 400,
}


def _raise(ex: IntakeError) -> None:
    detail: Any = {"message": str(ex), "missing_fields": ex.details} if ex.details else str(ex)
    raise HTTPException(status_code=_ERROR_STATUS.get(ex.code, 400), detail=detail)


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


class IntakeItemUpdateIn(BaseModel):
    """Phase 10B — edit an existing item. All fields optional/partial (PATCH
    semantics). Excludes `id`/`conversion_status`/`quote_line_item_id`/
    `order_item_id` — those remain server-controlled."""
    category: Optional[str] = None
    item_name: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[int] = None
    measurements: Optional[dict[str, Any]] = None
    category_inputs: Optional[dict[str, Any]] = None
    saved_item_id: Optional[str] = None
    material_profile_id: Optional[str] = None
    pricing_component_ids: Optional[list[str]] = None
    file_ids: Optional[list[str]] = None
    customer_notes: Optional[str] = None
    internal_notes: Optional[str] = None
    proof_required: Optional[bool] = None
    approval_required: Optional[bool] = None
    requested_due_date: Optional[str] = None
    installation_required: Optional[bool] = None
    # Additive pricing workflow contract (§6) — reference-only, never invents a price.
    pricing_status: Optional[IntakePricingStatus] = None
    pricing_snapshot_id: Optional[str] = None
    selected_price_source: Optional[str] = None
    manual_price_cents: Optional[int] = None
    pricing_warning_codes: Optional[list[str]] = None
    pricing_ready: Optional[bool] = None
    pricing_notes: Optional[str] = None


class IntakeReorderIn(BaseModel):
    item_ids: list[str]


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
    status: Optional[list[str]] = Query(None), customer_id: Optional[str] = Query(None),
    quote_id: Optional[str] = Query(None), order_id: Optional[str] = Query(None),
    assigned_user_id: Optional[str] = Query(None), source_type: Optional[str] = Query(None),
    priority: Optional[str] = Query(None), due_before: Optional[str] = Query(None),
    due_after: Optional[str] = Query(None), q: Optional[str] = Query(None),
    limit: int = Query(100, le=500), skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.INTAKE_READ)),
) -> dict:
    tid = user["tenant_id"]
    query: dict = {"tenant_id": tid}
    if status: query["status"] = {"$in": status}
    if customer_id: query["customer_id"] = customer_id
    if quote_id: query["quote_id"] = quote_id
    if order_id: query["order_id"] = order_id
    if assigned_user_id: query["assigned_user_id"] = assigned_user_id
    if source_type: query["source_type"] = source_type
    if priority: query["priority"] = priority
    if due_before or due_after:
        rng: dict = {}
        if due_before: rng["$lte"] = due_before
        if due_after: rng["$gte"] = due_after
        query["requested_due_date"] = rng
    if q:
        pattern = {"$regex": re.escape(q), "$options": "i"}
        or_clauses: list[dict] = [
            {"project_name": pattern}, {"contact_name": pattern},
            {"contact_email": pattern}, {"contact_phone": pattern},
        ]
        if q.isdigit():
            or_clauses.append({"intake_number": int(q)})
        cust_ids = [c["id"] async for c in db.customers.find({"tenant_id": tid, "name": pattern}, {"_id": 0, "id": 1})]
        if cust_ids:
            or_clauses.append({"customer_id": {"$in": cust_ids}})
        query["$or"] = or_clauses
    total = await db.intake_submissions.count_documents(query)
    cur = db.intake_submissions.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    items = []
    async for d in cur:
        doc = serialize_doc(d)
        doc["missing_information"] = intake_service.missing_information_for_submission(doc)
        items.append(doc)
    return {"items": items, "total": total, "limit": limit, "skip": skip}


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


@router.patch("/{intake_id}/items/reorder")
async def reorder_items(
    intake_id: str, payload: IntakeReorderIn, user: dict = Depends(require_permission(Perm.INTAKE_WRITE)),
) -> dict:
    try:
        return await intake_service.reorder_items(
            tenant_id=user["tenant_id"], intake_id=intake_id, ordered_item_ids=payload.item_ids,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except IntakeError as ex:
        _raise(ex)


@router.patch("/{intake_id}/items/{item_id}")
async def update_item(
    intake_id: str, item_id: str, payload: IntakeItemUpdateIn,
    user: dict = Depends(require_permission(Perm.INTAKE_WRITE)),
) -> dict:
    try:
        return await intake_service.update_item(
            tenant_id=user["tenant_id"], intake_id=intake_id, item_id=item_id,
            updates=payload.model_dump(exclude_unset=True),
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except IntakeError as ex:
        _raise(ex)


@router.delete("/{intake_id}/items/{item_id}")
async def remove_item(
    intake_id: str, item_id: str, user: dict = Depends(require_permission(Perm.INTAKE_WRITE)),
) -> dict:
    try:
        return await intake_service.remove_item(
            tenant_id=user["tenant_id"], intake_id=intake_id, item_id=item_id,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except IntakeError as ex:
        _raise(ex)


@router.post("/{intake_id}/items/{item_id}/duplicate", status_code=201)
async def duplicate_item(
    intake_id: str, item_id: str, user: dict = Depends(require_permission(Perm.INTAKE_WRITE)),
) -> dict:
    try:
        return await intake_service.duplicate_item(
            tenant_id=user["tenant_id"], intake_id=intake_id, item_id=item_id,
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


@router.get("/{intake_id}/missing-information")
async def missing_information(intake_id: str, user: dict = Depends(require_permission(Perm.INTAKE_READ))) -> dict:
    """Compact missing-information summary (§12) — pure structural check, no DB round-trips."""
    doc = await db.intake_submissions.find_one({"id": intake_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Intake submission not found")
    return {"missing_fields": intake_service.missing_information_for_submission(doc)}
