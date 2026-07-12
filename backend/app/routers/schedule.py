"""EC8 phase 8c — Team Schedule router (manager-facing).

Two routers in this module to avoid a `/schedules/{id}` vs `/schedules/shifts`
path-matching ambiguity: `router` (schedule-level actions) and `shifts_router`
(shift-level actions) mounted at a distinct `/schedule-shifts` prefix.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import schedule_service
from ..services.schedule_service import ScheduleError

router = APIRouter(prefix="/schedules", tags=["schedules"])
shifts_router = APIRouter(prefix="/schedule-shifts", tags=["schedules"])


def _raise(e: ScheduleError):
    raise HTTPException(status_code=e.status_code, detail=e.detail)


class ShiftCreateIn(BaseModel):
    employee_id: str
    shift_date: str
    start_at: str
    end_at: str
    title: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    break_minutes_expected: int = 0
    work_order_id: Optional[str] = None
    order_id: Optional[str] = None
    override_reason: Optional[str] = None


class ShiftUpdateIn(BaseModel):
    employee_id: Optional[str] = None
    shift_date: Optional[str] = None
    start_at: Optional[str] = None
    end_at: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    break_minutes_expected: Optional[int] = None
    work_order_id: Optional[str] = None
    order_id: Optional[str] = None
    status: Optional[str] = None
    override_reason: Optional[str] = None


class CancelIn(BaseModel):
    reason: Optional[str] = None


class CopyShiftIn(BaseModel):
    target_employee_ids: list[str] = Field(default_factory=list)
    target_dates: list[str] = Field(default_factory=list)


class CopyDayIn(BaseModel):
    source_date: str
    target_date: str


class CopyWeekIn(BaseModel):
    target_period_start: str


class AssignMultipleIn(BaseModel):
    employee_ids: list[str]
    shift_date: str
    start_at: str
    end_at: str
    title: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
async def get_week_schedule(period_start: str = Query(...),
                             user: dict = Depends(require_permission(Perm.SCHEDULE_READ))) -> dict:
    schedule = await schedule_service.get_or_create_schedule(
        tenant_id=user["tenant_id"], period_start=period_start, actor_user_id=user["id"],
    )
    return await schedule_service.get_schedule_with_shifts(tenant_id=user["tenant_id"], schedule_id=schedule["id"])


@router.get("/{schedule_id}")
async def get_schedule(schedule_id: str, user: dict = Depends(require_permission(Perm.SCHEDULE_READ))) -> dict:
    try:
        return await schedule_service.get_schedule_with_shifts(tenant_id=user["tenant_id"], schedule_id=schedule_id)
    except ScheduleError as e:
        _raise(e)


@router.post("/{schedule_id}/shifts", status_code=201)
async def create_shift(schedule_id: str, payload: ShiftCreateIn,
                        user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await schedule_service.create_shift(
            tenant_id=user["tenant_id"], schedule_id=schedule_id, actor_user_id=user["id"], actor_email=user["email"],
            **payload.model_dump(),
        )
    except ScheduleError as e:
        _raise(e)


@router.post("/{schedule_id}/assign", status_code=201)
async def assign_multiple(schedule_id: str, payload: AssignMultipleIn,
                           user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    return await schedule_service.assign_multiple_employees(
        tenant_id=user["tenant_id"], schedule_id=schedule_id, actor_user_id=user["id"], actor_email=user["email"],
        **payload.model_dump(),
    )


@router.post("/{schedule_id}/copy-day")
async def copy_day(schedule_id: str, payload: CopyDayIn,
                    user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    return await schedule_service.copy_day(
        tenant_id=user["tenant_id"], schedule_id=schedule_id, actor_user_id=user["id"], actor_email=user["email"],
        **payload.model_dump(),
    )


@router.post("/{schedule_id}/copy-week")
async def copy_week(schedule_id: str, payload: CopyWeekIn,
                     user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        detail = await schedule_service.get_schedule_with_shifts(tenant_id=user["tenant_id"], schedule_id=schedule_id)
    except ScheduleError as e:
        _raise(e)
    return await schedule_service.copy_week(
        tenant_id=user["tenant_id"], source_period_start=detail["schedule"]["period_start"],
        target_period_start=payload.target_period_start, actor_user_id=user["id"], actor_email=user["email"],
    )


@router.post("/{schedule_id}/publish")
async def publish(schedule_id: str, user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await schedule_service.publish_schedule(
            tenant_id=user["tenant_id"], schedule_id=schedule_id, actor_user_id=user["id"], actor_email=user["email"],
        )
    except ScheduleError as e:
        _raise(e)


@router.post("/{schedule_id}/republish")
async def republish(schedule_id: str, user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await schedule_service.republish_schedule(
            tenant_id=user["tenant_id"], schedule_id=schedule_id, actor_user_id=user["id"], actor_email=user["email"],
        )
    except ScheduleError as e:
        _raise(e)


@router.post("/{schedule_id}/archive")
async def archive(schedule_id: str, user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await schedule_service.archive_schedule(
            tenant_id=user["tenant_id"], schedule_id=schedule_id, actor_user_id=user["id"], actor_email=user["email"],
        )
    except ScheduleError as e:
        _raise(e)


@shifts_router.get("")
async def list_shifts(employee_id: Optional[str] = None, date_from: Optional[str] = None,
                       date_to: Optional[str] = None, status: Optional[str] = None,
                       user: dict = Depends(require_permission(Perm.SCHEDULE_READ))) -> dict:
    items = await schedule_service.list_shifts(
        tenant_id=user["tenant_id"], employee_id=employee_id, date_from=date_from, date_to=date_to, status=status,
    )
    return {"items": items}


@shifts_router.patch("/{shift_id}")
async def update_shift(shift_id: str, payload: ShiftUpdateIn,
                        user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        data = payload.model_dump(exclude={"override_reason"}, exclude_none=True)
        return await schedule_service.update_shift(
            tenant_id=user["tenant_id"], shift_id=shift_id, actor_user_id=user["id"], actor_email=user["email"],
            updates=data, override_reason=payload.override_reason,
        )
    except ScheduleError as e:
        _raise(e)


@shifts_router.post("/{shift_id}/cancel")
async def cancel_shift(shift_id: str, payload: CancelIn,
                        user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await schedule_service.cancel_shift(
            tenant_id=user["tenant_id"], shift_id=shift_id, actor_user_id=user["id"], actor_email=user["email"],
            reason=payload.reason,
        )
    except ScheduleError as e:
        _raise(e)


@shifts_router.post("/{shift_id}/copy")
async def copy_shift(shift_id: str, payload: CopyShiftIn,
                      user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await schedule_service.copy_shift(
            tenant_id=user["tenant_id"], shift_id=shift_id, actor_user_id=user["id"], actor_email=user["email"],
            target_employee_ids=payload.target_employee_ids or None, target_dates=payload.target_dates or None,
        )
    except ScheduleError as e:
        _raise(e)
