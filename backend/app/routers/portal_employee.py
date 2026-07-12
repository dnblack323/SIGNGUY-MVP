"""EC8 phase 8c — Employee Portal (employee-facing self-service routes).

Every route resolves the acting Employee from `identity["employee_id"]`
(set at token-mint time from the PortalIdentity doc) — never from a
client-supplied employee_id. Time Clock and Timesheet actions call straight
into the Phase 8b services (`time_clock_service`, `timesheet_service`) with
no duplicated business logic. Schedule/Announcements reuse the Phase 8a/8c
data directly with an explicit self/published-only filter.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..core.db import db
from ..core.time_utils import utc_now
from ..deps_portal import require_employee_portal_permission
from ..services import announcement_service, payroll_service, schedule_service, time_clock_service, timesheet_service
from ..services.portal_identity import update_portal_identity
from ..services.time_clock_service import TimeEntryError
from ..services.timesheet_service import TimesheetError

router = APIRouter(prefix="/portal/employee", tags=["portal_employee"])

VIEW = require_employee_portal_permission("portal:employee_view")
CLOCK = require_employee_portal_permission("portal:employee_time_clock")
TIMESHEET = require_employee_portal_permission("portal:employee_timesheet_view")
SCHEDULE = require_employee_portal_permission("portal:employee_schedule_view")
PAY = require_employee_portal_permission("portal:employee_pay_view")


def _raise(e):
    raise HTTPException(status_code=e.status_code, detail=e.detail)


def _public_employee_view(emp: dict) -> dict:
    """Strip manager-only / payroll-sensitive fields before returning to the portal."""
    hidden = {"hourly_rate_cents", "notes", "status_history", "linked_user_id", "overtime_policy"}
    return {k: v for k, v in emp.items() if k not in hidden}


async def _get_self_employee(identity: dict) -> dict:
    emp = await db.employees.find_one({"id": identity["employee_id"], "tenant_id": identity["tenant_id"]}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee record not found")
    return emp


async def _refresh_timesheet(tenant_id: str, employee_id: str, entry: dict) -> None:
    await timesheet_service.refresh_after_time_entry_change(
        tenant_id=tenant_id, employee_id=employee_id, work_date=entry["work_date"],
    )


# ---- Dashboard ----

@router.get("/dashboard")
async def dashboard(identity: dict = Depends(VIEW)) -> dict:
    tenant_id, employee_id = identity["tenant_id"], identity["employee_id"]
    emp = await _get_self_employee(identity)
    active_entry = await time_clock_service.get_active_entry(tenant_id=tenant_id, employee_id=employee_id)
    from ..services.time_period_utils import business_date, get_tenant_timezone
    tz = await get_tenant_timezone(tenant_id)
    today = business_date(utc_now(), tz)
    today_shifts = await schedule_service.list_shifts(
        tenant_id=tenant_id, employee_id=employee_id, date_from=today, date_to=today, published_only=True,
    )
    next_shifts = await schedule_service.list_shifts(
        tenant_id=tenant_id, employee_id=employee_id, date_from=today, published_only=True,
    )
    next_shift = next((s for s in next_shifts if s["status"] == "scheduled"), None)
    week_summary = await timesheet_service.get_or_create_weekly_timesheet(
        tenant_id=tenant_id, employee_id=employee_id, week_start=today,
    )
    announcements = await announcement_service.active_announcements(tenant_id=tenant_id, limit=3)
    visible_announcements = [
        a for a in announcements if a.get("audience") == "all" or employee_id in (a.get("employee_ids") or [])
    ]
    latest_pay = await _latest_pay_summary(tenant_id, employee_id)
    return {
        "employee": _public_employee_view(emp),
        "active_entry": active_entry,
        "today_shifts": [s for s in today_shifts if s["status"] != "cancelled"],
        "next_shift": next_shift,
        "week_hours": {"worked_minutes": week_summary["worked_minutes"], "week_start": week_summary["week_start"],
                       "week_end": week_summary["week_end"]},
        "timesheet_status": week_summary["status"],
        "announcements": visible_announcements,
        "tasks": {"available": False, "items": []},
        "pay": latest_pay,
    }


# ---- Time Clock (thin wrappers over the Phase 8b service — no duplicate logic) ----

class ClockInIn(BaseModel):
    work_order_id: Optional[str] = None
    notes: Optional[str] = None


@router.get("/time-clock/me")
async def time_clock_me(identity: dict = Depends(CLOCK)) -> dict:
    active = await time_clock_service.get_active_entry(tenant_id=identity["tenant_id"], employee_id=identity["employee_id"])
    return {"active_entry": active}


@router.post("/time-clock/clock-in")
async def clock_in(payload: ClockInIn, identity: dict = Depends(CLOCK)) -> dict:
    try:
        return await time_clock_service.clock_in(
            tenant_id=identity["tenant_id"], employee_id=identity["employee_id"],
            actor_user_id=f"portal:{identity['id']}", actor_email=identity["email"],
            source="self", work_order_id=payload.work_order_id, notes=payload.notes,
        )
    except TimeEntryError as e:
        _raise(e)


@router.post("/time-clock/clock-out")
async def clock_out(identity: dict = Depends(CLOCK)) -> dict:
    try:
        entry = await time_clock_service.clock_out(
            tenant_id=identity["tenant_id"], employee_id=identity["employee_id"],
            actor_user_id=f"portal:{identity['id']}", actor_email=identity["email"],
        )
        await _refresh_timesheet(identity["tenant_id"], identity["employee_id"], entry)
        return entry
    except TimeEntryError as e:
        _raise(e)


@router.post("/time-clock/break-start")
async def break_start(identity: dict = Depends(CLOCK)) -> dict:
    try:
        return await time_clock_service.start_break(
            tenant_id=identity["tenant_id"], employee_id=identity["employee_id"],
            actor_user_id=f"portal:{identity['id']}", actor_email=identity["email"],
        )
    except TimeEntryError as e:
        _raise(e)


@router.post("/time-clock/break-end")
async def break_end(identity: dict = Depends(CLOCK)) -> dict:
    try:
        return await time_clock_service.end_break(
            tenant_id=identity["tenant_id"], employee_id=identity["employee_id"],
            actor_user_id=f"portal:{identity['id']}", actor_email=identity["email"],
        )
    except TimeEntryError as e:
        _raise(e)


# ---- My Schedule (published-only, self-scoped) ----

@router.get("/schedule/today")
async def schedule_today(identity: dict = Depends(SCHEDULE)) -> dict:
    from ..services.time_period_utils import business_date, get_tenant_timezone
    tz = await get_tenant_timezone(identity["tenant_id"])
    today = business_date(utc_now(), tz)
    items = await schedule_service.list_shifts(
        tenant_id=identity["tenant_id"], employee_id=identity["employee_id"],
        date_from=today, date_to=today, published_only=True,
    )
    return {"date": today, "items": items}


@router.get("/schedule/week")
async def schedule_week(week_start: Optional[str] = None, identity: dict = Depends(SCHEDULE)) -> dict:
    from ..services.time_period_utils import business_date, get_tenant_timezone, week_bounds_for_date_str
    tz = await get_tenant_timezone(identity["tenant_id"])
    anchor = week_start or business_date(utc_now(), tz)
    start, end = week_bounds_for_date_str(anchor)
    items = await schedule_service.list_shifts(
        tenant_id=identity["tenant_id"], employee_id=identity["employee_id"],
        date_from=start, date_to=end, published_only=True,
    )
    return {"week_start": start, "week_end": end, "items": items}


# ---- My Timesheet (self-scoped, read-only — no approval action here) ----

# EC8 phase 8c — Timesheet fields that must stay in the (future) Phase 8d "My
# Pay" surface, not here. `estimated_gross_cents` is derived from the payroll
# rate; even though it isn't the rate itself, it lets an employee reverse
# it out of their known hours, so it is stripped from every portal response.
_TIMESHEET_HIDDEN_FIELDS = {"estimated_gross_cents"}


def _public_timesheet_view(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k not in _TIMESHEET_HIDDEN_FIELDS}


@router.get("/timesheet/summary")
async def timesheet_summary(period: str, date: str, identity: dict = Depends(TIMESHEET)) -> dict:
    try:
        result = await timesheet_service.period_summary(
            tenant_id=identity["tenant_id"], employee_id=identity["employee_id"], period=period, date_str=date,
        )
        return _public_timesheet_view(result)
    except TimesheetError as e:
        _raise(e)


@router.get("/timesheet/weekly")
async def timesheet_weekly(week_start: str, identity: dict = Depends(TIMESHEET)) -> dict:
    result = await timesheet_service.get_or_create_weekly_timesheet(
        tenant_id=identity["tenant_id"], employee_id=identity["employee_id"], week_start=week_start,
    )
    return _public_timesheet_view(result)


# ---- My Pay (self-scoped, EC8 phase 8d — reuses the Phase 8d payroll ledger,
# no parallel pay system). Strict allow-list of fields: never manager notes,
# other employees, audit internals, bank info, or tax data.) ----

_PAY_SNAPSHOT_FIELDS = (
    "pay_period_id", "period_start", "period_end", "payday", "period_status",
    "regular_minutes", "overtime_minutes", "hourly_rate_cents",
    "gross_regular_cents", "gross_overtime_cents", "adjustment_total_cents",
    "advance_total_cents", "repayment_total_cents", "payment_total_cents",
    "carryover_in_cents", "carryover_out_cents", "total_earned_cents",
    "total_paid_cents", "remaining_balance_cents",
)
_PAY_TXN_FIELDS = ("pay_period_id", "type", "amount_cents", "effective_date", "reference", "payment_method", "payment_date")


def _public_pay_view(snapshot: dict) -> dict:
    return {k: snapshot.get(k) for k in _PAY_SNAPSHOT_FIELDS}


def _public_txn_view(txn: dict) -> dict:
    return {k: txn.get(k) for k in _PAY_TXN_FIELDS}


async def _latest_pay_summary(tenant_id: str, employee_id: str) -> Optional[dict]:
    snaps = await payroll_service.list_employee_snapshots(tenant_id=tenant_id, employee_id=employee_id, limit=1)
    if not snaps:
        return None
    return _public_pay_view(snaps[0])


@router.get("/pay/summary")
async def pay_summary(identity: dict = Depends(PAY)) -> dict:
    latest = await _latest_pay_summary(identity["tenant_id"], identity["employee_id"])
    return {"latest_period": latest}


@router.get("/pay/periods")
async def pay_periods(identity: dict = Depends(PAY)) -> dict:
    snaps = await payroll_service.list_employee_snapshots(tenant_id=identity["tenant_id"], employee_id=identity["employee_id"])
    return {"items": [_public_pay_view(s) for s in snaps]}


@router.get("/pay/transactions")
async def pay_transactions(pay_period_id: Optional[str] = None, identity: dict = Depends(PAY)) -> dict:
    txns = await payroll_service.list_transactions(
        tenant_id=identity["tenant_id"], employee_id=identity["employee_id"], pay_period_id=pay_period_id,
    )
    return {"items": [_public_txn_view(t) for t in txns]}


# ---- Announcements (reuses Phase 8a Announcement — no second messaging system) ----

@router.get("/announcements")
async def announcements(identity: dict = Depends(VIEW)) -> dict:
    all_active = await announcement_service.active_announcements(tenant_id=identity["tenant_id"], limit=20)
    visible = [
        a for a in all_active
        if a.get("audience") == "all" or identity["employee_id"] in (a.get("employee_ids") or [])
    ]
    return {"items": visible}


# ---- My Tasks — clean boundary placeholder (no Task system exists yet) ----

@router.get("/tasks")
async def tasks(identity: dict = Depends(VIEW)) -> dict:
    return {"available": False, "items": [],
            "message": "Task assignments aren't available yet — coming in a future update."}


# ---- Profile ----

@router.get("/profile")
async def profile(identity: dict = Depends(VIEW)) -> dict:
    emp = await _get_self_employee(identity)
    return {
        "employee": _public_employee_view(emp),
        "portal_email": identity["email"],
        "portal_phone": identity.get("phone"),
        "portal_full_name": identity.get("full_name"),
    }


class ProfileUpdateIn(BaseModel):
    phone: Optional[str] = None
    full_name: Optional[str] = None


@router.patch("/profile")
async def update_profile(payload: ProfileUpdateIn, identity: dict = Depends(VIEW)) -> dict:
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates")
    updated = await update_portal_identity(identity_id=identity["id"], tenant_id=identity["tenant_id"], updates=updates)
    updated.pop("password_hash", None)
    return updated
