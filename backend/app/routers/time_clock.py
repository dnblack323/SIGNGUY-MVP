"""EC8 phase 8b — Time Clock router.

Self endpoints (`timeclock:self`) resolve the acting employee from the
current user's `Employee.linked_user_id` — never from a client-supplied
employee_id, which is what makes "employee cannot manage another employee"
structurally true rather than just policy. Admin endpoints (`timeclock:manage`)
accept an explicit `employee_id` path parameter.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import employee_service, time_clock_service, timesheet_service
from ..services.employee_service import EmployeeError
from ..services.time_clock_service import TimeEntryError

router = APIRouter(prefix="/time-clock", tags=["time-clock"])


class ClockInIn(BaseModel):
    work_order_id: Optional[str] = None
    notes: Optional[str] = None


class CorrectionIn(BaseModel):
    clock_in_at: Optional[str] = None
    clock_out_at: Optional[str] = None
    breaks: Optional[list[dict]] = None
    notes: Optional[str] = None
    work_order_id: Optional[str] = None
    reason: str


class VoidIn(BaseModel):
    reason: str


def _raise(e):
    raise HTTPException(status_code=e.status_code, detail=e.detail)


async def _resolve_self_employee(user: dict) -> dict:
    emp = await employee_service.get_employee_by_linked_user(tenant_id=user["tenant_id"], user_id=user["id"])
    if not emp:
        raise HTTPException(status_code=404, detail="No employee record is linked to your account")
    return emp


async def _refresh_timesheet(tenant_id: str, employee_id: str, entry: dict) -> None:
    await timesheet_service.refresh_after_time_entry_change(
        tenant_id=tenant_id, employee_id=employee_id, work_date=entry["work_date"],
    )


@router.get("/me")
async def my_status(user: dict = Depends(require_permission(Perm.TIMECLOCK_SELF))) -> dict:
    emp = await _resolve_self_employee(user)
    active = await time_clock_service.get_active_entry(tenant_id=user["tenant_id"], employee_id=emp["id"])
    return {"employee": emp, "active_entry": active}


@router.post("/clock-in")
async def self_clock_in(payload: ClockInIn, user: dict = Depends(require_permission(Perm.TIMECLOCK_SELF))) -> dict:
    emp = await _resolve_self_employee(user)
    try:
        return await time_clock_service.clock_in(
            tenant_id=user["tenant_id"], employee_id=emp["id"], actor_user_id=user["id"], actor_email=user["email"],
            source="self", work_order_id=payload.work_order_id, notes=payload.notes,
        )
    except TimeEntryError as e:
        _raise(e)


@router.post("/clock-out")
async def self_clock_out(user: dict = Depends(require_permission(Perm.TIMECLOCK_SELF))) -> dict:
    emp = await _resolve_self_employee(user)
    try:
        entry = await time_clock_service.clock_out(tenant_id=user["tenant_id"], employee_id=emp["id"],
                                                     actor_user_id=user["id"], actor_email=user["email"])
        await _refresh_timesheet(user["tenant_id"], emp["id"], entry)
        return entry
    except TimeEntryError as e:
        _raise(e)


@router.post("/break-start")
async def self_break_start(user: dict = Depends(require_permission(Perm.TIMECLOCK_SELF))) -> dict:
    emp = await _resolve_self_employee(user)
    try:
        return await time_clock_service.start_break(tenant_id=user["tenant_id"], employee_id=emp["id"],
                                                      actor_user_id=user["id"], actor_email=user["email"])
    except TimeEntryError as e:
        _raise(e)


@router.post("/break-end")
async def self_break_end(user: dict = Depends(require_permission(Perm.TIMECLOCK_SELF))) -> dict:
    emp = await _resolve_self_employee(user)
    try:
        return await time_clock_service.end_break(tenant_id=user["tenant_id"], employee_id=emp["id"],
                                                    actor_user_id=user["id"], actor_email=user["email"])
    except TimeEntryError as e:
        _raise(e)


@router.get("/entries")
async def list_my_entries(date_from: Optional[str] = None, date_to: Optional[str] = None,
                           user: dict = Depends(require_permission(Perm.TIMECLOCK_SELF))) -> dict:
    emp = await _resolve_self_employee(user)
    items = await time_clock_service.list_entries(tenant_id=user["tenant_id"], employee_id=emp["id"],
                                                    date_from=date_from, date_to=date_to)
    return {"items": items}


@router.get("/team-status")
async def team_status(user: dict = Depends(require_permission(Perm.TIMECLOCK_MANAGE))) -> dict:
    return await time_clock_service.team_status(tenant_id=user["tenant_id"])


@router.get("/{employee_id}/status")
async def employee_status(employee_id: str, user: dict = Depends(require_permission(Perm.TIMECLOCK_MANAGE))) -> dict:
    try:
        emp = await employee_service.get_employee(tenant_id=user["tenant_id"], employee_id=employee_id)
    except EmployeeError as e:
        _raise(e)
    active = await time_clock_service.get_active_entry(tenant_id=user["tenant_id"], employee_id=employee_id)
    return {"employee": emp, "active_entry": active}


@router.post("/{employee_id}/clock-in")
async def admin_clock_in(employee_id: str, payload: ClockInIn,
                          user: dict = Depends(require_permission(Perm.TIMECLOCK_MANAGE))) -> dict:
    try:
        return await time_clock_service.clock_in(
            tenant_id=user["tenant_id"], employee_id=employee_id, actor_user_id=user["id"], actor_email=user["email"],
            source="admin", work_order_id=payload.work_order_id, notes=payload.notes,
        )
    except TimeEntryError as e:
        _raise(e)


@router.post("/{employee_id}/clock-out")
async def admin_clock_out(employee_id: str, user: dict = Depends(require_permission(Perm.TIMECLOCK_MANAGE))) -> dict:
    try:
        entry = await time_clock_service.clock_out(tenant_id=user["tenant_id"], employee_id=employee_id,
                                                     actor_user_id=user["id"], actor_email=user["email"])
        await _refresh_timesheet(user["tenant_id"], employee_id, entry)
        return entry
    except TimeEntryError as e:
        _raise(e)


@router.post("/{employee_id}/break-start")
async def admin_break_start(employee_id: str, user: dict = Depends(require_permission(Perm.TIMECLOCK_MANAGE))) -> dict:
    try:
        return await time_clock_service.start_break(tenant_id=user["tenant_id"], employee_id=employee_id,
                                                      actor_user_id=user["id"], actor_email=user["email"])
    except TimeEntryError as e:
        _raise(e)


@router.post("/{employee_id}/break-end")
async def admin_break_end(employee_id: str, user: dict = Depends(require_permission(Perm.TIMECLOCK_MANAGE))) -> dict:
    try:
        return await time_clock_service.end_break(tenant_id=user["tenant_id"], employee_id=employee_id,
                                                    actor_user_id=user["id"], actor_email=user["email"])
    except TimeEntryError as e:
        _raise(e)


@router.get("/entries/all")
async def list_all_entries(employee_id: Optional[str] = None, date_from: Optional[str] = None,
                            date_to: Optional[str] = None, status: Optional[str] = None,
                            user: dict = Depends(require_permission(Perm.TIMECLOCK_MANAGE))) -> dict:
    items = await time_clock_service.list_entries(tenant_id=user["tenant_id"], employee_id=employee_id,
                                                    date_from=date_from, date_to=date_to, status=status)
    return {"items": items}


@router.post("/entries/{entry_id}/correct")
async def correct_entry(entry_id: str, payload: CorrectionIn,
                         user: dict = Depends(require_permission(Perm.TIMECLOCK_MANAGE))) -> dict:
    try:
        new_values = {k: v for k, v in payload.model_dump(exclude={"reason"}).items() if v is not None}
        entry = await time_clock_service.correct_entry(
            tenant_id=user["tenant_id"], entry_id=entry_id, actor_user_id=user["id"], actor_email=user["email"],
            new_values=new_values, reason=payload.reason,
        )
        await _refresh_timesheet(user["tenant_id"], entry["employee_id"], entry)
        return entry
    except TimeEntryError as e:
        _raise(e)


@router.post("/entries/{entry_id}/void")
async def void_entry(entry_id: str, payload: VoidIn, user: dict = Depends(require_permission(Perm.TIMECLOCK_MANAGE))) -> dict:
    try:
        entry = await time_clock_service.void_entry(
            tenant_id=user["tenant_id"], entry_id=entry_id, actor_user_id=user["id"], actor_email=user["email"],
            reason=payload.reason,
        )
        await _refresh_timesheet(user["tenant_id"], entry["employee_id"], entry)
        return entry
    except TimeEntryError as e:
        _raise(e)
