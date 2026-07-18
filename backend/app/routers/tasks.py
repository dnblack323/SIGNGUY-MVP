"""EC12 Phase 12A - shared staff task endpoints."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import task_service
from ..services.task_service import TaskError

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _raise(e: TaskError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


class TaskCreateIn(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "normal"
    task_type: str = "general"
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    customer_id: Optional[str] = None
    quote_id: Optional[str] = None
    order_id: Optional[str] = None
    order_item_id: Optional[str] = None
    work_order_id: Optional[str] = None
    invoice_id: Optional[str] = None
    production_stage_id: Optional[str] = None
    assigned_user_id: Optional[str] = None
    assigned_employee_id: Optional[str] = None
    due_at: Optional[str] = None
    start_at: Optional[str] = None
    recurrence_rule: Optional[dict[str, Any]] = None
    reminder_policy: dict[str, Any] = Field(default_factory=dict)
    visibility: str = "staff"
    employee_visible: bool = False
    internal_only: bool = False
    idempotency_key: Optional[str] = None


class TaskUpdateIn(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    task_type: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    customer_id: Optional[str] = None
    quote_id: Optional[str] = None
    order_id: Optional[str] = None
    order_item_id: Optional[str] = None
    work_order_id: Optional[str] = None
    invoice_id: Optional[str] = None
    production_stage_id: Optional[str] = None
    due_at: Optional[str] = None
    start_at: Optional[str] = None
    visibility: Optional[str] = None
    employee_visible: Optional[bool] = None
    internal_only: Optional[bool] = None


class TaskAssignIn(BaseModel):
    assigned_user_id: Optional[str] = None
    assigned_employee_id: Optional[str] = None


class TaskActionIn(BaseModel):
    reason: Optional[str] = None


class TaskCommentIn(BaseModel):
    body: str
    visibility: str = "internal"


class TaskCommentEditIn(BaseModel):
    body: str


class ReminderPolicyIn(BaseModel):
    reminder_policy: dict[str, Any] = Field(default_factory=dict)


class ValidateLinkIn(BaseModel):
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    customer_id: Optional[str] = None
    quote_id: Optional[str] = None
    order_id: Optional[str] = None
    order_item_id: Optional[str] = None
    work_order_id: Optional[str] = None
    invoice_id: Optional[str] = None
    production_stage_id: Optional[str] = None


@router.get("")
async def list_tasks(
    status: Optional[str] = None,
    assigned_user_id: Optional[str] = None,
    assigned_employee_id: Optional[str] = None,
    priority: Optional[str] = None,
    task_type: Optional[str] = None,
    source_type: Optional[str] = None,
    linked_entity_type: Optional[str] = None,
    created_by_user_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    quote_id: Optional[str] = None,
    order_id: Optional[str] = None,
    order_item_id: Optional[str] = None,
    work_order_id: Optional[str] = None,
    invoice_id: Optional[str] = None,
    production_stage_id: Optional[str] = None,
    due_from: Optional[str] = None,
    due_to: Optional[str] = None,
    overdue: Optional[bool] = None,
    unassigned: Optional[bool] = None,
    view: Optional[str] = None,
    sort: str = "due_date",
    q: Optional[str] = None,
    include_archived: bool = False,
    limit: int = Query(100, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.TASK_READ)),
) -> dict:
    try:
        return await task_service.list_tasks(
            tenant_id=user["tenant_id"], status=status, assigned_user_id=assigned_user_id,
            assigned_employee_id=assigned_employee_id, priority=priority, task_type=task_type,
            source_type=source_type, linked_entity_type=linked_entity_type, created_by_user_id=created_by_user_id,
            customer_id=customer_id, quote_id=quote_id, order_id=order_id, order_item_id=order_item_id,
            work_order_id=work_order_id, invoice_id=invoice_id, production_stage_id=production_stage_id,
            due_from=due_from, due_to=due_to, overdue=overdue, unassigned=unassigned, view=view,
            current_user_id=user["id"], sort=sort,
            q=q, include_archived=include_archived, limit=limit, skip=skip,
        )
    except TaskError as e:
        _raise(e)


@router.get("/my")
async def my_tasks(
    view: Optional[str] = None,
    limit: int = Query(100, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.TASK_READ)),
) -> dict:
    try:
        return await task_service.list_my_tasks(tenant_id=user["tenant_id"], user_id=user["id"], view=view, limit=limit, skip=skip)
    except TaskError as e:
        _raise(e)


@router.get("/kanban")
async def kanban_tasks(
    include_completed: bool = False,
    include_archived: bool = False,
    group_by: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(200, ge=1, le=200),
    user: dict = Depends(require_permission(Perm.TASK_READ)),
) -> dict:
    try:
        return await task_service.kanban_tasks(
            tenant_id=user["tenant_id"], include_completed=include_completed,
            include_archived=include_archived, group_by=group_by, q=q, limit=limit,
        )
    except TaskError as e:
        _raise(e)


@router.post("", status_code=201)
async def create_task(payload: TaskCreateIn, user: dict = Depends(require_permission(Perm.TASK_CREATE))) -> dict:
    try:
        return await task_service.create_task(
            tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
            payload=payload.model_dump(),
        )
    except TaskError as e:
        _raise(e)


@router.get("/{task_id}")
async def get_task(task_id: str, include_archived: bool = False, user: dict = Depends(require_permission(Perm.TASK_READ))) -> dict:
    try:
        return await task_service.get_task(tenant_id=user["tenant_id"], task_id=task_id, include_archived=include_archived)
    except TaskError as e:
        _raise(e)


@router.patch("/{task_id}")
async def update_task(task_id: str, payload: TaskUpdateIn, user: dict = Depends(require_permission(Perm.TASK_UPDATE))) -> dict:
    try:
        return await task_service.update_task(
            tenant_id=user["tenant_id"], task_id=task_id, actor_user_id=user["id"], actor_email=user["email"],
            updates=payload.model_dump(exclude_none=True),
        )
    except TaskError as e:
        _raise(e)


@router.post("/{task_id}/assign")
async def assign_task(task_id: str, payload: TaskAssignIn, user: dict = Depends(require_permission(Perm.TASK_ASSIGN))) -> dict:
    try:
        return await task_service.assign_task(
            tenant_id=user["tenant_id"], task_id=task_id, actor_user_id=user["id"], actor_email=user["email"],
            assigned_user_id=payload.assigned_user_id, assigned_employee_id=payload.assigned_employee_id,
        )
    except TaskError as e:
        _raise(e)


async def _transition(task_id: str, target: str, payload: TaskActionIn, user: dict) -> dict:
    try:
        return await task_service.transition_task(
            tenant_id=user["tenant_id"], task_id=task_id, target=target,
            actor_user_id=user["id"], actor_email=user["email"], reason=payload.reason,
        )
    except TaskError as e:
        _raise(e)


@router.post("/{task_id}/start")
async def start_task(task_id: str, payload: TaskActionIn, user: dict = Depends(require_permission(Perm.TASK_UPDATE))) -> dict:
    return await _transition(task_id, "in_progress", payload, user)


@router.post("/{task_id}/wait")
async def wait_task(task_id: str, payload: TaskActionIn, user: dict = Depends(require_permission(Perm.TASK_UPDATE))) -> dict:
    return await _transition(task_id, "waiting", payload, user)


@router.post("/{task_id}/block")
async def block_task(task_id: str, payload: TaskActionIn, user: dict = Depends(require_permission(Perm.TASK_UPDATE))) -> dict:
    return await _transition(task_id, "blocked", payload, user)


@router.post("/{task_id}/resume")
async def resume_task(task_id: str, payload: TaskActionIn, user: dict = Depends(require_permission(Perm.TASK_UPDATE))) -> dict:
    return await _transition(task_id, "in_progress", payload, user)


@router.post("/{task_id}/complete")
async def complete_task(task_id: str, payload: TaskActionIn, user: dict = Depends(require_permission(Perm.TASK_COMPLETE))) -> dict:
    return await _transition(task_id, "completed", payload, user)


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str, payload: TaskActionIn, user: dict = Depends(require_permission(Perm.TASK_UPDATE))) -> dict:
    return await _transition(task_id, "canceled", payload, user)


@router.post("/{task_id}/reopen")
async def reopen_task(task_id: str, payload: TaskActionIn, user: dict = Depends(require_permission(Perm.TASK_COMPLETE))) -> dict:
    try:
        return await task_service.transition_task(
            tenant_id=user["tenant_id"], task_id=task_id, target="in_progress",
            actor_user_id=user["id"], actor_email=user["email"], reason=payload.reason, allow_reopen=True,
        )
    except TaskError as e:
        _raise(e)


@router.post("/{task_id}/archive")
async def archive_task(task_id: str, user: dict = Depends(require_permission(Perm.TASK_ARCHIVE))) -> dict:
    try:
        return await task_service.archive_task(
            tenant_id=user["tenant_id"], task_id=task_id, actor_user_id=user["id"], actor_email=user["email"],
        )
    except TaskError as e:
        _raise(e)


@router.post("/{task_id}/restore")
async def restore_task(task_id: str, user: dict = Depends(require_permission(Perm.TASK_ARCHIVE))) -> dict:
    try:
        return await task_service.restore_task(
            tenant_id=user["tenant_id"], task_id=task_id, actor_user_id=user["id"], actor_email=user["email"],
        )
    except TaskError as e:
        _raise(e)


@router.get("/{task_id}/comments")
async def list_comments(task_id: str, user: dict = Depends(require_permission(Perm.TASK_READ))) -> dict:
    try:
        return {"items": await task_service.list_comments(tenant_id=user["tenant_id"], task_id=task_id)}
    except TaskError as e:
        _raise(e)


@router.post("/{task_id}/comments", status_code=201)
async def add_comment(task_id: str, payload: TaskCommentIn, user: dict = Depends(require_permission(Perm.TASK_UPDATE))) -> dict:
    try:
        return await task_service.add_comment(
            tenant_id=user["tenant_id"], task_id=task_id, actor_user_id=user["id"],
            actor_email=user["email"], body=payload.body, visibility=payload.visibility,
        )
    except TaskError as e:
        _raise(e)


@router.patch("/{task_id}/comments/{comment_id}")
async def edit_comment(
    task_id: str,
    comment_id: str,
    payload: TaskCommentEditIn,
    user: dict = Depends(require_permission(Perm.TASK_UPDATE)),
) -> dict:
    try:
        return await task_service.edit_comment(
            tenant_id=user["tenant_id"], task_id=task_id, comment_id=comment_id,
            actor_user_id=user["id"], actor_email=user["email"], body=payload.body,
        )
    except TaskError as e:
        _raise(e)


@router.patch("/{task_id}/reminder-policy")
async def update_reminder_policy(
    task_id: str,
    payload: ReminderPolicyIn,
    user: dict = Depends(require_permission(Perm.TASK_UPDATE)),
) -> dict:
    try:
        return await task_service.update_reminder_policy(
            tenant_id=user["tenant_id"], task_id=task_id, actor_user_id=user["id"], actor_email=user["email"],
            reminder_policy=payload.reminder_policy,
        )
    except TaskError as e:
        _raise(e)


@router.post("/{task_id}/reminders/{reminder_kind}")
async def generate_reminder(
    task_id: str,
    reminder_kind: str,
    user: dict = Depends(require_permission(Perm.TASK_UPDATE)),
) -> dict:
    try:
        return await task_service.generate_reminder(
            tenant_id=user["tenant_id"], task_id=task_id, reminder_kind=reminder_kind,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except TaskError as e:
        _raise(e)


@router.post("/validate-link")
async def validate_link(payload: ValidateLinkIn, user: dict = Depends(require_permission(Perm.TASK_READ))) -> dict:
    try:
        refs = await task_service.validate_linked_records(user["tenant_id"], payload.model_dump(exclude_none=True))
        return {"valid": True, "linked_fields": sorted(refs.keys())}
    except TaskError as e:
        _raise(e)
