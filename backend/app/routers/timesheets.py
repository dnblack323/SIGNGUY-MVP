"""EC8 phase 8b — Timesheets router."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..core.permissions import Perm, permissions_for_role
from ..deps import require_permission
from ..services import employee_service, timesheet_service
from ..services.timesheet_service import TimesheetError

router = APIRouter(prefix="/timesheets", tags=["timesheets"])


class RejectIn(BaseModel):
    reason: str


class ReopenIn(BaseModel):
    reason: str


def _raise(e):
    raise HTTPException(status_code=e.status_code, detail=e.detail)


async def _resolve_self_employee(user: dict) -> dict:
    emp = await employee_service.get_employee_by_linked_user(tenant_id=user["tenant_id"], user_id=user["id"])
    if not emp:
        raise HTTPException(status_code=404, detail="No employee record is linked to your account")
    return emp


def _can_view_others(user: dict) -> bool:
    perms = set(permissions_for_role(user.get("role", "staff")))
    return Perm.TIMESHEET_READ.value in perms or Perm.TIMESHEET_MANAGE.value in perms


@router.get("/summary")
async def summary(period: str, date: str, employee_id: Optional[str] = None,
                   user: dict = Depends(require_permission(Perm.TIMESHEET_SELF))) -> dict:
    if employee_id and not _can_view_others(user):
        raise HTTPException(status_code=403, detail="You may only view your own timesheet")
    if employee_id:
        target_employee_id = employee_id
    else:
        emp = await _resolve_self_employee(user)
        target_employee_id = emp["id"]
    try:
        return await timesheet_service.period_summary(tenant_id=user["tenant_id"], employee_id=target_employee_id,
                                                        period=period, date_str=date)
    except TimesheetError as e:
        _raise(e)


@router.get("/weekly")
async def weekly(week_start: str, employee_id: Optional[str] = None,
                  user: dict = Depends(require_permission(Perm.TIMESHEET_SELF))) -> dict:
    if employee_id and not _can_view_others(user):
        raise HTTPException(status_code=403, detail="You may only view your own timesheet")
    if employee_id:
        target_employee_id = employee_id
    else:
        emp = await _resolve_self_employee(user)
        target_employee_id = emp["id"]
    return await timesheet_service.get_or_create_weekly_timesheet(
        tenant_id=user["tenant_id"], employee_id=target_employee_id, week_start=week_start,
    )


@router.get("")
async def list_timesheets(employee_id: Optional[str] = None, status: Optional[str] = None,
                           user: dict = Depends(require_permission(Perm.TIMESHEET_READ))) -> dict:
    items = await timesheet_service.list_timesheets(tenant_id=user["tenant_id"], employee_id=employee_id, status=status)
    return {"items": items}


@router.get("/pending-review")
async def pending_review(user: dict = Depends(require_permission(Perm.TIMESHEET_READ))) -> dict:
    items = await timesheet_service.list_pending_review(tenant_id=user["tenant_id"])
    return {"items": items}


@router.post("/{timesheet_id}/approve")
async def approve(timesheet_id: str, user: dict = Depends(require_permission(Perm.TIMESHEET_MANAGE))) -> dict:
    try:
        return await timesheet_service.approve(tenant_id=user["tenant_id"], timesheet_id=timesheet_id,
                                                actor_user_id=user["id"], actor_email=user["email"])
    except TimesheetError as e:
        _raise(e)


@router.post("/{timesheet_id}/reject")
async def reject(timesheet_id: str, payload: RejectIn, user: dict = Depends(require_permission(Perm.TIMESHEET_MANAGE))) -> dict:
    try:
        return await timesheet_service.reject(tenant_id=user["tenant_id"], timesheet_id=timesheet_id,
                                               actor_user_id=user["id"], actor_email=user["email"], reason=payload.reason)
    except TimesheetError as e:
        _raise(e)


@router.post("/{timesheet_id}/reopen")
async def reopen(timesheet_id: str, payload: ReopenIn, user: dict = Depends(require_permission(Perm.TIMESHEET_MANAGE))) -> dict:
    try:
        return await timesheet_service.reopen(tenant_id=user["tenant_id"], timesheet_id=timesheet_id,
                                               actor_user_id=user["id"], actor_email=user["email"], reason=payload.reason)
    except TimesheetError as e:
        _raise(e)
