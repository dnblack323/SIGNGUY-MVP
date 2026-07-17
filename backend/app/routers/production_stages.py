"""EC11 Phase 11C - live production stage endpoints."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import production_stage_service as svc
from ..services.production_stage_service import ProductionStageError

router = APIRouter(tags=["production-stages"])

_ERROR_STATUS = {
    "order_not_found": 404,
    "order_item_not_found": 404,
    "work_order_not_found": 404,
    "stage_not_found": 404,
    "employee_not_found": 404,
    "workflow_not_found": 404,
    "override_locked": 400,
    "workflow_has_no_stages": 400,
    "invalid_transition": 400,
    "previous_stage_incomplete": 409,
    "proof_gate_blocked": 409,
    "reason_required": 400,
    "skip_not_allowed": 400,
    "stage_not_reopenable": 400,
    "manager_required": 403,
    "employee_inactive": 400,
    "employee_user_link_required": 400,
    "assignment_blocked": 409,
    "assignment_warning_override_required": 409,
    "note_required": 400,
}


def _raise(ex: ProductionStageError) -> None:
    raise HTTPException(status_code=_ERROR_STATUS.get(ex.code, 400), detail=str(ex))


class OverrideIn(BaseModel):
    workflow_id: str
    stages: Optional[list[dict[str, Any]]] = None


class AssignIn(BaseModel):
    employee_id: str
    override_reason: Optional[str] = None


class ReasonIn(BaseModel):
    reason: Optional[str] = None


class CompleteIn(BaseModel):
    completion_note: Optional[str] = None


class DueDateIn(BaseModel):
    due_at: Optional[str] = None


class NoteIn(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


@router.get("/orders/{order_id}/items/{item_id}/production-workflow-preview")
async def preview_item_workflow(
    order_id: str,
    item_id: str,
    workflow_id: Optional[str] = None,
    user: dict = Depends(require_permission(Perm.WORK_ORDER_READ)),
) -> dict:
    try:
        return await svc.preview_item_workflow(
            tenant_id=user["tenant_id"], order_id=order_id, item_id=item_id, explicit_workflow_id=workflow_id,
        )
    except ProductionStageError as ex:
        _raise(ex)


@router.post("/orders/{order_id}/items/{item_id}/production-workflow-override")
async def save_item_override(
    order_id: str,
    item_id: str,
    payload: OverrideIn,
    user: dict = Depends(require_permission(Perm.WORK_ORDER_WRITE)),
) -> dict:
    try:
        return await svc.save_item_override(
            tenant_id=user["tenant_id"], order_id=order_id, item_id=item_id,
            workflow_id=payload.workflow_id, stages=payload.stages,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except ProductionStageError as ex:
        _raise(ex)


@router.get("/work-orders/{work_order_id}/stage-preview")
async def preview_work_order_generation(
    work_order_id: str,
    user: dict = Depends(require_permission(Perm.WORK_ORDER_READ)),
) -> dict:
    try:
        return await svc.preview_work_order_generation(tenant_id=user["tenant_id"], work_order_id=work_order_id)
    except ProductionStageError as ex:
        _raise(ex)


@router.post("/work-orders/{work_order_id}/stages/generate")
async def generate_work_order_stages(
    work_order_id: str,
    user: dict = Depends(require_permission(Perm.WORK_ORDER_WRITE)),
) -> dict:
    try:
        return await svc.generate_work_order_stages(
            tenant_id=user["tenant_id"], work_order_id=work_order_id,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except ProductionStageError as ex:
        _raise(ex)


@router.get("/work-orders/{work_order_id}/stages")
async def list_work_order_stages(
    work_order_id: str,
    user: dict = Depends(require_permission(Perm.WORK_ORDER_READ)),
) -> dict:
    try:
        return await svc.list_work_order_stages(tenant_id=user["tenant_id"], work_order_id=work_order_id)
    except ProductionStageError as ex:
        _raise(ex)


@router.get("/production-stages/{stage_id}")
async def get_stage(stage_id: str, user: dict = Depends(require_permission(Perm.WORK_ORDER_READ))) -> dict:
    try:
        return await svc.get_stage(tenant_id=user["tenant_id"], stage_id=stage_id)
    except ProductionStageError as ex:
        _raise(ex)


@router.post("/production-stages/{stage_id}/assign")
async def assign_stage(stage_id: str, payload: AssignIn, user: dict = Depends(require_permission(Perm.WORK_ORDER_WRITE))) -> dict:
    try:
        return await svc.assign_stage(
            tenant_id=user["tenant_id"], stage_id=stage_id,
            employee_id=payload.employee_id, override_reason=payload.override_reason, user=user,
        )
    except ProductionStageError as ex:
        _raise(ex)


@router.post("/production-stages/{stage_id}/unassign")
async def unassign_stage(stage_id: str, user: dict = Depends(require_permission(Perm.WORK_ORDER_WRITE))) -> dict:
    try:
        return await svc.unassign_stage(tenant_id=user["tenant_id"], stage_id=stage_id, user=user)
    except ProductionStageError as ex:
        _raise(ex)


@router.post("/production-stages/{stage_id}/start")
async def start_stage(stage_id: str, user: dict = Depends(require_permission(Perm.WORK_ORDER_WRITE))) -> dict:
    try:
        return await svc.transition_stage(tenant_id=user["tenant_id"], stage_id=stage_id, target="in_progress", user=user)
    except ProductionStageError as ex:
        _raise(ex)


@router.post("/production-stages/{stage_id}/wait")
async def wait_stage(stage_id: str, payload: ReasonIn = Body(default_factory=ReasonIn), user: dict = Depends(require_permission(Perm.WORK_ORDER_WRITE))) -> dict:
    try:
        return await svc.transition_stage(tenant_id=user["tenant_id"], stage_id=stage_id, target="waiting", user=user, reason=payload.reason)
    except ProductionStageError as ex:
        _raise(ex)


@router.post("/production-stages/{stage_id}/block")
async def block_stage(stage_id: str, payload: ReasonIn, user: dict = Depends(require_permission(Perm.WORK_ORDER_WRITE))) -> dict:
    try:
        return await svc.transition_stage(tenant_id=user["tenant_id"], stage_id=stage_id, target="blocked", user=user, reason=payload.reason)
    except ProductionStageError as ex:
        _raise(ex)


@router.post("/production-stages/{stage_id}/resume")
async def resume_stage(stage_id: str, user: dict = Depends(require_permission(Perm.WORK_ORDER_WRITE))) -> dict:
    try:
        return await svc.transition_stage(tenant_id=user["tenant_id"], stage_id=stage_id, target="in_progress", user=user)
    except ProductionStageError as ex:
        _raise(ex)


@router.post("/production-stages/{stage_id}/complete")
async def complete_stage(stage_id: str, payload: CompleteIn = Body(default_factory=CompleteIn), user: dict = Depends(require_permission(Perm.WORK_ORDER_WRITE))) -> dict:
    try:
        return await svc.transition_stage(
            tenant_id=user["tenant_id"], stage_id=stage_id, target="completed", user=user,
            completion_note=payload.completion_note,
        )
    except ProductionStageError as ex:
        _raise(ex)


@router.post("/production-stages/{stage_id}/skip")
async def skip_stage(stage_id: str, payload: ReasonIn = Body(default_factory=ReasonIn), user: dict = Depends(require_permission(Perm.WORK_ORDER_WRITE))) -> dict:
    try:
        return await svc.transition_stage(tenant_id=user["tenant_id"], stage_id=stage_id, target="skipped", user=user, reason=payload.reason)
    except ProductionStageError as ex:
        _raise(ex)


@router.post("/production-stages/{stage_id}/reopen")
async def reopen_stage(stage_id: str, payload: ReasonIn, user: dict = Depends(require_permission(Perm.WORK_ORDER_WRITE))) -> dict:
    try:
        return await svc.reopen_stage(tenant_id=user["tenant_id"], stage_id=stage_id, reason=payload.reason or "", user=user)
    except ProductionStageError as ex:
        _raise(ex)


@router.patch("/production-stages/{stage_id}/due-date")
async def update_stage_due_date(stage_id: str, payload: DueDateIn, user: dict = Depends(require_permission(Perm.WORK_ORDER_WRITE))) -> dict:
    try:
        return await svc.update_stage_due_date(tenant_id=user["tenant_id"], stage_id=stage_id, due_at=payload.due_at, user=user)
    except ProductionStageError as ex:
        _raise(ex)


@router.post("/production-stages/{stage_id}/notes")
async def add_stage_note(stage_id: str, payload: NoteIn, user: dict = Depends(require_permission(Perm.WORK_ORDER_WRITE))) -> dict:
    try:
        return await svc.add_stage_note(tenant_id=user["tenant_id"], stage_id=stage_id, note=payload.note, user=user)
    except ProductionStageError as ex:
        _raise(ex)
