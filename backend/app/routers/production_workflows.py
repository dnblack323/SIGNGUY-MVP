"""EC11 Phase 11A - production workflow configuration endpoints."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import production_workflow_service as svc
from ..services.production_workflow_service import ProductionWorkflowError

router = APIRouter(prefix="/production-workflows", tags=["production-workflows"])

_ERROR_STATUS = {
    "workflow_not_found": 404,
    "workflow_name_required": 400,
    "invalid_workflow_key": 400,
    "workflow_key_exists": 409,
    "stage_name_required": 400,
    "invalid_stage_key": 400,
    "duplicate_stage_key": 409,
    "invalid_stage_order": 400,
    "stage_not_found": 404,
    "starter_workflow_immutable": 400,
    "workflow_archived": 400,
}


def _raise(ex: ProductionWorkflowError) -> None:
    raise HTTPException(status_code=_ERROR_STATUS.get(ex.code, 400), detail=str(ex))


class StageIn(BaseModel):
    stage_key: Optional[str] = None
    display_name: str
    description: Optional[str] = None
    sequence: Optional[int] = None
    active: Optional[bool] = None
    required: Optional[bool] = None
    may_skip: Optional[bool] = None
    requires_reason_to_skip: Optional[bool] = None
    default_role: Optional[str] = None
    default_estimated_duration_minutes: Optional[int] = None
    due_date_offset_days: Optional[int] = None
    customer_visible: Optional[bool] = None
    employee_visible: Optional[bool] = None
    requires_previous_stage_complete: Optional[bool] = None
    proof_gate_type: Optional[str] = None
    equipment_requirement_ids: list[str] = Field(default_factory=list)
    certification_requirement_ids: list[str] = Field(default_factory=list)
    checklist_template_ids: list[str] = Field(default_factory=list)
    color: Optional[str] = None
    icon: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StagePatchIn(BaseModel):
    stage_key: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    sequence: Optional[int] = None
    active: Optional[bool] = None
    required: Optional[bool] = None
    may_skip: Optional[bool] = None
    requires_reason_to_skip: Optional[bool] = None
    default_role: Optional[str] = None
    default_estimated_duration_minutes: Optional[int] = None
    due_date_offset_days: Optional[int] = None
    customer_visible: Optional[bool] = None
    employee_visible: Optional[bool] = None
    requires_previous_stage_complete: Optional[bool] = None
    proof_gate_type: Optional[str] = None
    equipment_requirement_ids: Optional[list[str]] = None
    certification_requirement_ids: Optional[list[str]] = None
    checklist_template_ids: Optional[list[str]] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class WorkflowCreateIn(BaseModel):
    name: str
    description: Optional[str] = None
    workflow_key: Optional[str] = None
    scope_type: Optional[str] = None
    category_ids: list[str] = Field(default_factory=list)
    stages: list[StageIn] = Field(default_factory=list)


class WorkflowUpdateIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    workflow_key: Optional[str] = None


class DuplicateIn(BaseModel):
    name: Optional[str] = None


class CategoryAssignIn(BaseModel):
    category_ids: list[str] = Field(default_factory=list)


class ReorderIn(BaseModel):
    stage_keys: list[str]


@router.get("/statuses")
async def statuses(user: dict = Depends(require_permission(Perm.PRODUCTION_WORKFLOW_READ))) -> dict:
    return {"statuses": list(svc.STAGE_STATUSES), "transitions": {k: sorted(v) for k, v in svc.STAGE_TRANSITIONS.items()}}


@router.get("")
async def list_workflows(
    include_archived: bool = Query(False),
    user: dict = Depends(require_permission(Perm.PRODUCTION_WORKFLOW_READ)),
) -> dict:
    return {"items": await svc.list_workflows(tenant_id=user["tenant_id"], include_archived=include_archived)}


@router.get("/resolve")
async def resolve_workflow(
    category_id: Optional[str] = Query(None),
    explicit_workflow_id: Optional[str] = Query(None),
    user: dict = Depends(require_permission(Perm.PRODUCTION_WORKFLOW_READ)),
) -> dict:
    return await svc.resolve_workflow(
        tenant_id=user["tenant_id"], category_id=category_id, explicit_workflow_id=explicit_workflow_id,
    )


@router.post("", status_code=201)
async def create_workflow(payload: WorkflowCreateIn, user: dict = Depends(require_permission(Perm.PRODUCTION_WORKFLOW_MANAGE))) -> dict:
    try:
        return await svc.create_workflow(
            tenant_id=user["tenant_id"], payload=payload.model_dump(),
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except ProductionWorkflowError as ex:
        _raise(ex)


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str, user: dict = Depends(require_permission(Perm.PRODUCTION_WORKFLOW_READ))) -> dict:
    try:
        return await svc.get_workflow(tenant_id=user["tenant_id"], workflow_id=workflow_id)
    except ProductionWorkflowError as ex:
        _raise(ex)


@router.patch("/{workflow_id}")
async def update_workflow(workflow_id: str, payload: WorkflowUpdateIn, user: dict = Depends(require_permission(Perm.PRODUCTION_WORKFLOW_MANAGE))) -> dict:
    try:
        return await svc.update_workflow(
            tenant_id=user["tenant_id"], workflow_id=workflow_id, changes=payload.model_dump(exclude_unset=True),
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except ProductionWorkflowError as ex:
        _raise(ex)


@router.post("/{workflow_id}/duplicate", status_code=201)
async def duplicate_workflow(workflow_id: str, payload: DuplicateIn, user: dict = Depends(require_permission(Perm.PRODUCTION_WORKFLOW_MANAGE))) -> dict:
    try:
        return await svc.duplicate_workflow(
            tenant_id=user["tenant_id"], workflow_id=workflow_id, name=payload.name,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except ProductionWorkflowError as ex:
        _raise(ex)


@router.post("/{workflow_id}/archive")
async def archive_workflow(workflow_id: str, user: dict = Depends(require_permission(Perm.PRODUCTION_WORKFLOW_MANAGE))) -> dict:
    try:
        return await svc.set_archive_state(
            tenant_id=user["tenant_id"], workflow_id=workflow_id, archived=True,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except ProductionWorkflowError as ex:
        _raise(ex)


@router.post("/{workflow_id}/restore")
async def restore_workflow(workflow_id: str, user: dict = Depends(require_permission(Perm.PRODUCTION_WORKFLOW_MANAGE))) -> dict:
    try:
        return await svc.set_archive_state(
            tenant_id=user["tenant_id"], workflow_id=workflow_id, archived=False,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except ProductionWorkflowError as ex:
        _raise(ex)


@router.post("/{workflow_id}/set-default")
async def set_default(workflow_id: str, user: dict = Depends(require_permission(Perm.PRODUCTION_WORKFLOW_MANAGE))) -> dict:
    try:
        return await svc.set_tenant_default(
            tenant_id=user["tenant_id"], workflow_id=workflow_id,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except ProductionWorkflowError as ex:
        _raise(ex)


@router.post("/{workflow_id}/assign-category")
async def assign_category(workflow_id: str, payload: CategoryAssignIn, user: dict = Depends(require_permission(Perm.PRODUCTION_WORKFLOW_MANAGE))) -> dict:
    try:
        return await svc.assign_categories(
            tenant_id=user["tenant_id"], workflow_id=workflow_id, category_ids=payload.category_ids,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except ProductionWorkflowError as ex:
        _raise(ex)


@router.post("/{workflow_id}/stages")
async def add_stage(workflow_id: str, payload: StageIn, user: dict = Depends(require_permission(Perm.PRODUCTION_WORKFLOW_MANAGE))) -> dict:
    try:
        return await svc.add_stage(
            tenant_id=user["tenant_id"], workflow_id=workflow_id, payload=payload.model_dump(exclude_unset=True),
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except ProductionWorkflowError as ex:
        _raise(ex)


@router.patch("/{workflow_id}/stages/{stage_key}")
async def update_stage(workflow_id: str, stage_key: str, payload: StagePatchIn, user: dict = Depends(require_permission(Perm.PRODUCTION_WORKFLOW_MANAGE))) -> dict:
    try:
        return await svc.update_stage(
            tenant_id=user["tenant_id"], workflow_id=workflow_id, stage_key=stage_key,
            payload=payload.model_dump(exclude_unset=True), actor_user_id=user["id"], actor_email=user["email"],
        )
    except ProductionWorkflowError as ex:
        _raise(ex)


@router.post("/{workflow_id}/stages/reorder")
async def reorder_stages(workflow_id: str, payload: ReorderIn, user: dict = Depends(require_permission(Perm.PRODUCTION_WORKFLOW_MANAGE))) -> dict:
    try:
        return await svc.reorder_stages(
            tenant_id=user["tenant_id"], workflow_id=workflow_id, stage_keys=payload.stage_keys,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except ProductionWorkflowError as ex:
        _raise(ex)


@router.post("/{workflow_id}/stages/{stage_key}/archive")
async def archive_stage(workflow_id: str, stage_key: str, user: dict = Depends(require_permission(Perm.PRODUCTION_WORKFLOW_MANAGE))) -> dict:
    try:
        return await svc.archive_stage(
            tenant_id=user["tenant_id"], workflow_id=workflow_id, stage_key=stage_key,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except ProductionWorkflowError as ex:
        _raise(ex)
