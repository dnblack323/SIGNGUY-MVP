"""EC12 Phase 12D - shared calendar and appointment routes."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import calendar_service
from ..services.calendar_service import CalendarError

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _raise(e: CalendarError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


class CalendarEventIn(BaseModel):
    event_type: str = "custom"
    title: str
    description: Optional[str] = None
    start_at: str
    end_at: str
    all_day: bool = False
    timezone: Optional[str] = None
    location: Optional[str] = None
    customer_id: Optional[str] = None
    order_id: Optional[str] = None
    order_item_id: Optional[str] = None
    work_order_id: Optional[str] = None
    production_stage_id: Optional[str] = None
    employee_id: Optional[str] = None
    assigned_user_id: Optional[str] = None
    visibility: str = "staff"
    reminder_policy: dict = {}
    recurrence_rule: Optional[dict] = None
    conflict_override_reason: Optional[str] = None


class CalendarEventUpdateIn(BaseModel):
    event_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    start_at: Optional[str] = None
    end_at: Optional[str] = None
    all_day: Optional[bool] = None
    timezone: Optional[str] = None
    location: Optional[str] = None
    customer_id: Optional[str] = None
    order_id: Optional[str] = None
    order_item_id: Optional[str] = None
    work_order_id: Optional[str] = None
    production_stage_id: Optional[str] = None
    employee_id: Optional[str] = None
    assigned_user_id: Optional[str] = None
    visibility: Optional[str] = None
    reminder_policy: Optional[dict] = None
    recurrence_rule: Optional[dict] = None
    conflict_override_reason: Optional[str] = None


class CancelIn(BaseModel):
    reason: Optional[str] = None


@router.get("/feed")
async def feed(
    start_at: str,
    end_at: str,
    event_type: Optional[str] = None,
    employee_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    order_id: Optional[str] = None,
    work_order_id: Optional[str] = None,
    status: Optional[str] = None,
    source_type: Optional[str] = None,
    surface: Optional[str] = None,
    visibility: Optional[str] = None,
    limit: int = Query(200, ge=1, le=500),
    skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.SCHEDULE_READ)),
) -> dict:
    try:
        return await calendar_service.list_events(
            tenant_id=user["tenant_id"], start_at=start_at, end_at=end_at,
            event_type=event_type, employee_id=employee_id, customer_id=customer_id,
            order_id=order_id, work_order_id=work_order_id, status=status, source_type=source_type,
            surface=surface, visibility=visibility, limit=limit, skip=skip,
        )
    except CalendarError as e:
        _raise(e)


@router.get("/conflicts")
async def conflicts(start_at: str, end_at: str, employee_id: Optional[str] = None,
                    location: Optional[str] = None, customer_id: Optional[str] = None,
                    event_id: Optional[str] = None,
                    user: dict = Depends(require_permission(Perm.SCHEDULE_READ))) -> dict:
    try:
        return {"items": await calendar_service.check_conflicts(
            tenant_id=user["tenant_id"], start_at=start_at, end_at=end_at, employee_id=employee_id,
            location=location, customer_id=customer_id, event_id=event_id,
        )}
    except CalendarError as e:
        _raise(e)


@router.post("/events", status_code=201)
async def create_event(payload: CalendarEventIn,
                       user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await calendar_service.create_event(
            tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
            payload=payload.model_dump(exclude_none=True),
        )
    except CalendarError as e:
        _raise(e)


@router.get("/events/{event_id}")
async def get_event(event_id: str, user: dict = Depends(require_permission(Perm.SCHEDULE_READ))) -> dict:
    try:
        return await calendar_service.get_event(tenant_id=user["tenant_id"], event_id=event_id)
    except CalendarError as e:
        _raise(e)


@router.patch("/events/{event_id}")
async def update_event(event_id: str, payload: CalendarEventUpdateIn,
                       user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await calendar_service.update_event(
            tenant_id=user["tenant_id"], event_id=event_id, actor_user_id=user["id"], actor_email=user["email"],
            payload=payload.model_dump(exclude_none=True),
        )
    except CalendarError as e:
        _raise(e)


@router.post("/events/{event_id}/reschedule")
async def reschedule_event(event_id: str, payload: CalendarEventUpdateIn,
                           user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await calendar_service.reschedule_event(
            tenant_id=user["tenant_id"], event_id=event_id, actor_user_id=user["id"], actor_email=user["email"],
            payload=payload.model_dump(exclude_none=True),
        )
    except CalendarError as e:
        _raise(e)


@router.post("/events/{event_id}/cancel")
async def cancel_event(event_id: str, payload: CancelIn,
                       user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await calendar_service.cancel_event(
            tenant_id=user["tenant_id"], event_id=event_id, actor_user_id=user["id"],
            actor_email=user["email"], reason=payload.reason,
        )
    except CalendarError as e:
        _raise(e)


@router.post("/events/{event_id}/archive")
async def archive_event(event_id: str, user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await calendar_service.archive_event(
            tenant_id=user["tenant_id"], event_id=event_id, actor_user_id=user["id"], actor_email=user["email"],
        )
    except CalendarError as e:
        _raise(e)


@router.post("/events/{event_id}/restore")
async def restore_event(event_id: str, user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await calendar_service.restore_event(
            tenant_id=user["tenant_id"], event_id=event_id, actor_user_id=user["id"], actor_email=user["email"],
        )
    except CalendarError as e:
        _raise(e)
