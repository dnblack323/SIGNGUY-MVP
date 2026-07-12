"""EC8 phase 8b — Timesheet service.

Daily/monthly views are pure aggregations over `time_entries` (no persisted
document). The WEEKLY Timesheet (Saturday-Friday) is the one persisted,
approvable unit; it is kept live-recomputed while `status == "pending"` and
frozen once approved/rejected (a reopen action unfreezes it).
"""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.timesheet import Timesheet
from .activity import record_activity_with_audit
from .time_clock_service import is_missed_clockout
from .time_period_utils import month_bounds_for_date_str, week_bounds_for_date_str


class TimesheetError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def _aggregate_range(tenant_id: str, employee_id: str, date_from: str, date_to: str) -> dict:
    cur = db.time_entries.find(
        {"tenant_id": tenant_id, "employee_id": employee_id, "work_date": {"$gte": date_from, "$lte": date_to},
         "status": {"$ne": "voided"}}, {"_id": 0},
    )
    worked = 0
    breaks = 0
    incomplete = 0
    missed = 0
    async for e in cur:
        worked += e.get("worked_minutes", 0)
        breaks += e.get("total_break_minutes", 0)
        if e.get("status") == "open":
            incomplete += 1
            if is_missed_clockout(e):
                missed += 1
    emp = await db.employees.find_one({"id": employee_id, "tenant_id": tenant_id}, {"_id": 0, "hourly_rate_cents": 1})
    rate_cents = (emp or {}).get("hourly_rate_cents", 0)
    estimated_gross_cents = round(worked / 60 * rate_cents)
    return {
        "worked_minutes": worked, "break_minutes": breaks, "regular_minutes": worked, "overtime_minutes": 0,
        "estimated_gross_cents": estimated_gross_cents, "incomplete_entry_count": incomplete, "missed_clock_count": missed,
    }


async def period_summary(*, tenant_id: str, employee_id: str, period: str, date_str: str) -> dict:
    if period == "daily":
        date_from = date_to = date_str
    elif period == "weekly":
        date_from, date_to = week_bounds_for_date_str(date_str)
    elif period == "monthly":
        date_from, date_to = month_bounds_for_date_str(date_str)
    else:
        raise TimesheetError(400, "period must be daily, weekly, or monthly")
    totals = await _aggregate_range(tenant_id, employee_id, date_from, date_to)
    return {"period": period, "date_from": date_from, "date_to": date_to, **totals}


async def get_or_create_weekly_timesheet(*, tenant_id: str, employee_id: str, week_start: str) -> dict:
    week_start_norm, week_end = week_bounds_for_date_str(week_start)
    existing = await db.timesheets.find_one({"tenant_id": tenant_id, "employee_id": employee_id, "week_start": week_start_norm}, {"_id": 0})
    totals = await _aggregate_range(tenant_id, employee_id, week_start_norm, week_end)
    if existing:
        if existing["status"] == "pending":
            await db.timesheets.update_one(
                {"id": existing["id"], "tenant_id": tenant_id},
                {"$set": {**totals, "updated_at": utc_now().isoformat()}},
            )
            existing.update(totals)
        return serialize_doc(existing)
    doc = Timesheet(tenant_id=tenant_id, employee_id=employee_id, week_start=week_start_norm, week_end=week_end, **totals).model_dump()
    await db.timesheets.insert_one(prepare_for_mongo(dict(doc)))
    doc.pop("_id", None)
    return serialize_doc(doc)


async def refresh_after_time_entry_change(*, tenant_id: str, employee_id: str, work_date: str) -> None:
    week_start, _ = week_bounds_for_date_str(work_date)
    await get_or_create_weekly_timesheet(tenant_id=tenant_id, employee_id=employee_id, week_start=week_start)


async def list_timesheets(*, tenant_id: str, employee_id: Optional[str] = None, status: Optional[str] = None) -> list[dict]:
    filt: dict[str, Any] = {"tenant_id": tenant_id}
    if employee_id:
        filt["employee_id"] = employee_id
    if status:
        filt["status"] = status
    cur = db.timesheets.find(filt, {"_id": 0}).sort("week_start", -1).limit(200)
    return [serialize_doc(d) async for d in cur]


async def approve(*, tenant_id: str, timesheet_id: str, actor_user_id: str, actor_email: str) -> dict:
    ts = await db.timesheets.find_one({"id": timesheet_id, "tenant_id": tenant_id}, {"_id": 0})
    if not ts:
        raise TimesheetError(404, "Timesheet not found")
    if ts["status"] != "pending":
        raise TimesheetError(400, f"Timesheet is {ts['status']}, cannot approve")
    now_iso = utc_now().isoformat()
    history = ts.get("review_history", []) + [{"action": "approved", "by": actor_user_id, "at": now_iso}]
    await db.timesheets.update_one(
        {"id": timesheet_id, "tenant_id": tenant_id},
        {"$set": {"status": "approved", "approved_by": actor_user_id, "approved_at": now_iso, "review_history": history}},
    )
    await db.time_entries.update_many(
        {"tenant_id": tenant_id, "employee_id": ts["employee_id"], "work_date": {"$gte": ts["week_start"], "$lte": ts["week_end"]},
         "status": {"$in": ["completed", "corrected"]}},
        {"$set": {"status": "approved", "approved_by": actor_user_id, "approved_at": now_iso}},
    )
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="timesheet_approved", entity_type="timesheet", entity_id=timesheet_id,
        summary=f"Timesheet {ts['week_start']}\u2013{ts['week_end']} approved",
    )
    doc = await db.timesheets.find_one({"id": timesheet_id, "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})


async def reject(*, tenant_id: str, timesheet_id: str, actor_user_id: str, actor_email: str, reason: str) -> dict:
    if not reason or not reason.strip():
        raise TimesheetError(400, "A rejection reason is required")
    ts = await db.timesheets.find_one({"id": timesheet_id, "tenant_id": tenant_id}, {"_id": 0})
    if not ts:
        raise TimesheetError(404, "Timesheet not found")
    if ts["status"] != "pending":
        raise TimesheetError(400, f"Timesheet is {ts['status']}, cannot reject")
    now_iso = utc_now().isoformat()
    history = ts.get("review_history", []) + [{"action": "rejected", "by": actor_user_id, "at": now_iso, "reason": reason}]
    await db.timesheets.update_one(
        {"id": timesheet_id, "tenant_id": tenant_id},
        {"$set": {"status": "rejected", "rejected_by": actor_user_id, "rejected_at": now_iso,
                   "rejection_reason": reason, "review_history": history}},
    )
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="timesheet_rejected", entity_type="timesheet", entity_id=timesheet_id,
        summary=f"Timesheet {ts['week_start']}\u2013{ts['week_end']} rejected: {reason}", severity="warning",
    )
    doc = await db.timesheets.find_one({"id": timesheet_id, "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})


async def reopen(*, tenant_id: str, timesheet_id: str, actor_user_id: str, actor_email: str, reason: str) -> dict:
    ts = await db.timesheets.find_one({"id": timesheet_id, "tenant_id": tenant_id}, {"_id": 0})
    if not ts:
        raise TimesheetError(404, "Timesheet not found")
    if ts["status"] not in ("approved", "rejected"):
        raise TimesheetError(400, f"Timesheet is {ts['status']}, cannot reopen")
    was_approved = ts["status"] == "approved"
    now_iso = utc_now().isoformat()
    history = ts.get("review_history", []) + [{"action": "reopened", "by": actor_user_id, "at": now_iso, "reason": reason}]
    await db.timesheets.update_one(
        {"id": timesheet_id, "tenant_id": tenant_id},
        {"$set": {"status": "pending", "review_history": history}},
    )
    if was_approved:
        await db.time_entries.update_many(
            {"tenant_id": tenant_id, "employee_id": ts["employee_id"], "work_date": {"$gte": ts["week_start"], "$lte": ts["week_end"]},
             "status": "approved"},
            {"$set": {"status": "completed"}},
        )
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="timesheet_reopened", entity_type="timesheet", entity_id=timesheet_id,
        summary=f"Timesheet {ts['week_start']}\u2013{ts['week_end']} reopened: {reason}", severity="warning",
    )
    return await get_or_create_weekly_timesheet(tenant_id=tenant_id, employee_id=ts["employee_id"], week_start=ts["week_start"])


async def list_pending_review(*, tenant_id: str) -> list[dict]:
    cur = db.timesheets.find(
        {"tenant_id": tenant_id, "status": "pending", "$or": [{"worked_minutes": {"$gt": 0}}, {"incomplete_entry_count": {"$gt": 0}}]},
        {"_id": 0},
    ).sort("week_start", -1)
    return [serialize_doc(d) async for d in cur]
