"""EC8 phase 8c — Schedule service (single authoritative Schedule + Shift model).

Router calls this — never touches `db.schedules`/`db.shifts` directly for
mutations, so every write goes through the same conflict-detection + audit
path. Reuses Phase 8b's Saturday-Friday week boundary (`time_period_utils`)
so the Team Schedule week grid and the Time Clock/Timesheet week grid always
agree. Publishing/notifications reuse `services/notifications.py` (in-app,
for employees with a linked staff `User`) and `services/email.py` (for
Employee Portal identities) — no parallel messaging system.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.schedule import Schedule
from ..models.shift import Shift
from .activity import record_activity_with_audit
from .email import send_email
from .notifications import notify
from .time_period_utils import get_tenant_timezone, week_bounds_for_date_str

CONFLICT_PREFIX = "availability_conflict:"


class ScheduleError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _overlaps(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    return _parse_dt(a_start) < _parse_dt(b_end) and _parse_dt(b_start) < _parse_dt(a_end)


# ---- Schedule (weekly container) ----

async def _get_schedule(tenant_id: str, schedule_id: str) -> dict:
    doc = await db.schedules.find_one({"id": schedule_id, "tenant_id": tenant_id}, {"_id": 0})
    if not doc:
        raise ScheduleError(404, "Schedule not found")
    return doc


async def get_or_create_schedule(*, tenant_id: str, period_start: str, actor_user_id: str) -> dict:
    week_start, week_end = week_bounds_for_date_str(period_start)
    existing = await db.schedules.find_one({"tenant_id": tenant_id, "period_start": week_start}, {"_id": 0})
    if existing:
        return serialize_doc(existing)
    doc = Schedule(
        tenant_id=tenant_id, period_start=week_start, period_end=week_end,
        created_by=actor_user_id, updated_by=actor_user_id,
    ).model_dump()
    await db.schedules.insert_one(prepare_for_mongo(dict(doc)))
    doc.pop("_id", None)
    return serialize_doc(doc)


async def get_schedule_with_shifts(*, tenant_id: str, schedule_id: str) -> dict:
    schedule = await _get_schedule(tenant_id, schedule_id)
    shifts = [serialize_doc(s) async for s in db.shifts.find(
        {"tenant_id": tenant_id, "schedule_id": schedule_id}, {"_id": 0},
    ).sort("start_at", 1)]
    return {"schedule": serialize_doc(schedule), "shifts": shifts}


async def list_shifts(*, tenant_id: str, employee_id: Optional[str] = None,
                       date_from: Optional[str] = None, date_to: Optional[str] = None,
                       status: Optional[str] = None, published_only: bool = False) -> list[dict]:
    filt: dict[str, Any] = {"tenant_id": tenant_id}
    if employee_id:
        filt["employee_id"] = employee_id
    if status:
        filt["status"] = status
    if date_from or date_to:
        rng: dict[str, Any] = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to
        filt["shift_date"] = rng
    if published_only:
        published_schedule_ids = [s["id"] async for s in db.schedules.find(
            {"tenant_id": tenant_id, "status": "published"}, {"_id": 0, "id": 1},
        )]
        filt["schedule_id"] = {"$in": published_schedule_ids}
    cur = db.shifts.find(filt, {"_id": 0}).sort("start_at", 1).limit(500)
    return [serialize_doc(d) async for d in cur]


# ---- Conflict detection ----

async def _assert_hard_conflicts(tenant_id: str, employee_id: str, shift_date: str, start_at: str, end_at: str,
                                  exclude_shift_id: Optional[str] = None) -> None:
    if _parse_dt(end_at) <= _parse_dt(start_at):
        raise ScheduleError(400, "Shift end must be after shift start")
    base_filt: dict[str, Any] = {"tenant_id": tenant_id, "employee_id": employee_id, "status": {"$ne": "cancelled"}}
    if exclude_shift_id:
        base_filt["id"] = {"$ne": exclude_shift_id}
    dup = await db.shifts.find_one({**base_filt, "shift_date": shift_date, "start_at": start_at, "end_at": end_at})
    if dup:
        raise ScheduleError(409, "duplicate_shift: An identical shift already exists for this employee")
    async for other in db.shifts.find(base_filt, {"_id": 0}):
        if _overlaps(start_at, end_at, other["start_at"], other["end_at"]):
            raise ScheduleError(409, "overlapping_shift: This employee already has a shift that overlaps this time")


def _availability_conflict(employee: dict, shift_date: str, start_at: str, end_at: str) -> Optional[str]:
    d = date.fromisoformat(shift_date)
    for b in employee.get("availability_blocks", []) or []:
        if b.get("kind") != "unavailable":
            continue
        date_from, date_to = b.get("date_from"), b.get("date_to")
        day_of_week = b.get("day_of_week")
        matches_date = False
        if date_from and date_to:
            matches_date = date_from <= shift_date <= date_to
        elif day_of_week is not None:
            matches_date = d.weekday() == int(day_of_week)
        if not matches_date:
            continue
        start_time, end_time = b.get("start_time"), b.get("end_time")
        if start_time and end_time:
            shift_start_t = _parse_dt(start_at).strftime("%H:%M")
            shift_end_t = _parse_dt(end_at).strftime("%H:%M")
            if shift_end_t <= start_time or shift_start_t >= end_time:
                continue  # doesn't overlap the unavailable window on that day
        return b.get("note") or f"Employee marked unavailable on {shift_date}"
    return None


async def _get_active_employee(tenant_id: str, employee_id: str) -> dict:
    emp = await db.employees.find_one({"id": employee_id, "tenant_id": tenant_id}, {"_id": 0})
    if not emp:
        raise ScheduleError(404, "Employee not found")
    if emp.get("status") != "active":
        raise ScheduleError(400, f"Employee is {emp.get('status')}, cannot be scheduled")
    return emp


# ---- Shift mutations ----

async def create_shift(*, tenant_id: str, schedule_id: str, employee_id: str, shift_date: str,
                        start_at: str, end_at: str, actor_user_id: str, actor_email: str,
                        title: Optional[str] = None, location: Optional[str] = None,
                        notes: Optional[str] = None, break_minutes_expected: int = 0,
                        work_order_id: Optional[str] = None, order_id: Optional[str] = None,
                        override_reason: Optional[str] = None) -> dict:
    schedule = await _get_schedule(tenant_id, schedule_id)
    if schedule["status"] == "archived":
        raise ScheduleError(400, "Schedule is archived and cannot be edited")
    emp = await _get_active_employee(tenant_id, employee_id)
    await _assert_hard_conflicts(tenant_id, employee_id, shift_date, start_at, end_at)
    warning = _availability_conflict(emp, shift_date, start_at, end_at)
    if warning and not override_reason:
        raise ScheduleError(409, f"{CONFLICT_PREFIX}{warning}")
    doc = Shift(
        tenant_id=tenant_id, schedule_id=schedule_id, employee_id=employee_id, shift_date=shift_date,
        start_at=start_at, end_at=end_at, title=title, location=location, notes=notes,
        break_minutes_expected=break_minutes_expected, work_order_id=work_order_id, order_id=order_id,
        conflict_override_reason=(override_reason if warning else None),
        created_by=actor_user_id, updated_by=actor_user_id,
    ).model_dump()
    await db.shifts.insert_one(prepare_for_mongo(dict(doc)))
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="shift_created", entity_type="shift", entity_id=doc["id"],
        summary=f"Shift created for {emp['name']} on {shift_date}",
    )
    if warning and override_reason:
        await record_activity_with_audit(
            tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
            module="team", action="schedule_conflict_overridden", entity_type="shift", entity_id=doc["id"],
            summary=f"Availability conflict overridden for {emp['name']}: {warning} — {override_reason}",
            severity="warning",
        )
    if schedule["status"] == "published":
        await _notify_shift_change(tenant_id, emp, doc, "added")
    doc.pop("_id", None)
    return serialize_doc(doc)


async def _get_shift(tenant_id: str, shift_id: str) -> dict:
    doc = await db.shifts.find_one({"id": shift_id, "tenant_id": tenant_id}, {"_id": 0})
    if not doc:
        raise ScheduleError(404, "Shift not found")
    return doc


async def update_shift(*, tenant_id: str, shift_id: str, actor_user_id: str, actor_email: str,
                        updates: dict, override_reason: Optional[str] = None) -> dict:
    shift = await _get_shift(tenant_id, shift_id)
    schedule = await _get_schedule(tenant_id, shift["schedule_id"])
    if schedule["status"] == "archived":
        raise ScheduleError(400, "Schedule is archived and cannot be edited")
    new_employee_id = updates.get("employee_id", shift["employee_id"])
    new_date = updates.get("shift_date", shift["shift_date"])
    new_start = updates.get("start_at", shift["start_at"])
    new_end = updates.get("end_at", shift["end_at"])
    emp = await _get_active_employee(tenant_id, new_employee_id)
    time_or_employee_changed = (new_employee_id != shift["employee_id"] or new_date != shift["shift_date"]
                                 or new_start != shift["start_at"] or new_end != shift["end_at"])
    warning = None
    if time_or_employee_changed:
        await _assert_hard_conflicts(tenant_id, new_employee_id, new_date, new_start, new_end, exclude_shift_id=shift_id)
        warning = _availability_conflict(emp, new_date, new_start, new_end)
        if warning and not override_reason:
            raise ScheduleError(409, f"{CONFLICT_PREFIX}{warning}")
    allowed = {"employee_id", "shift_date", "start_at", "end_at", "title", "location", "notes",
               "break_minutes_expected", "work_order_id", "order_id", "status"}
    clean = {k: v for k, v in updates.items() if k in allowed}
    clean["updated_by"] = actor_user_id
    clean["updated_at"] = utc_now().isoformat()
    if warning and override_reason:
        clean["conflict_override_reason"] = override_reason
    await db.shifts.update_one({"id": shift_id, "tenant_id": tenant_id}, {"$set": clean})
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="shift_updated", entity_type="shift", entity_id=shift_id,
        summary=f"Shift updated for {emp['name']}", diff={"before": shift, "after": clean},
    )
    if warning and override_reason:
        await record_activity_with_audit(
            tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
            module="team", action="schedule_conflict_overridden", entity_type="shift", entity_id=shift_id,
            summary=f"Availability conflict overridden for {emp['name']}: {warning} — {override_reason}",
            severity="warning",
        )
    doc = await db.shifts.find_one({"id": shift_id, "tenant_id": tenant_id}, {"_id": 0})
    if schedule["status"] == "published":
        await _notify_shift_change(tenant_id, emp, doc, "changed")
    return serialize_doc(doc or {})


async def cancel_shift(*, tenant_id: str, shift_id: str, actor_user_id: str, actor_email: str,
                        reason: Optional[str] = None) -> dict:
    shift = await _get_shift(tenant_id, shift_id)
    if shift["status"] == "cancelled":
        raise ScheduleError(400, "Shift is already cancelled")
    schedule = await _get_schedule(tenant_id, shift["schedule_id"])
    now_iso = utc_now().isoformat()
    await db.shifts.update_one(
        {"id": shift_id, "tenant_id": tenant_id},
        {"$set": {"status": "cancelled", "notes": reason or shift.get("notes"),
                   "updated_by": actor_user_id, "updated_at": now_iso}},
    )
    emp = await db.employees.find_one({"id": shift["employee_id"], "tenant_id": tenant_id}, {"_id": 0})
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="shift_cancelled", entity_type="shift", entity_id=shift_id,
        summary=f"Shift cancelled for {(emp or {}).get('name', shift['employee_id'])}", severity="warning",
    )
    doc = await db.shifts.find_one({"id": shift_id, "tenant_id": tenant_id}, {"_id": 0})
    if schedule["status"] == "published" and emp:
        await _notify_shift_change(tenant_id, emp, doc, "cancelled")
    return serialize_doc(doc or {})


# ---- Bulk copy / assign helpers (thin wrappers over create_shift; skip-on-conflict) ----

def _shift_duration(shift: dict) -> timedelta:
    return _parse_dt(shift["end_at"]) - _parse_dt(shift["start_at"])


async def copy_shift(*, tenant_id: str, shift_id: str, actor_user_id: str, actor_email: str,
                      target_employee_ids: Optional[list[str]] = None,
                      target_dates: Optional[list[str]] = None) -> dict:
    source = await _get_shift(tenant_id, shift_id)
    duration = _shift_duration(source)
    employee_ids = target_employee_ids or [source["employee_id"]]
    dates = target_dates or [source["shift_date"]]
    created, skipped = [], []
    for emp_id in employee_ids:
        for d in dates:
            start_time = _parse_dt(source["start_at"]).strftime("%H:%M:%S")
            new_start = f"{d}T{start_time}"
            try:
                new_start_dt = _parse_dt(source["start_at"]).replace(
                    year=date.fromisoformat(d).year, month=date.fromisoformat(d).month, day=date.fromisoformat(d).day)
            except Exception:
                skipped.append({"employee_id": emp_id, "date": d, "reason": "invalid_date"})
                continue
            new_end_dt = new_start_dt + duration
            try:
                shift = await create_shift(
                    tenant_id=tenant_id, schedule_id=source["schedule_id"], employee_id=emp_id, shift_date=d,
                    start_at=new_start_dt.isoformat(), end_at=new_end_dt.isoformat(),
                    actor_user_id=actor_user_id, actor_email=actor_email,
                    title=source.get("title"), location=source.get("location"), notes=source.get("notes"),
                    break_minutes_expected=source.get("break_minutes_expected", 0),
                    work_order_id=source.get("work_order_id"), order_id=source.get("order_id"),
                )
                created.append(shift)
            except ScheduleError as e:
                skipped.append({"employee_id": emp_id, "date": d, "reason": e.detail})
    return {"created": created, "skipped": skipped}


async def assign_multiple_employees(*, tenant_id: str, schedule_id: str, employee_ids: list[str],
                                     shift_date: str, start_at: str, end_at: str,
                                     actor_user_id: str, actor_email: str,
                                     title: Optional[str] = None, location: Optional[str] = None,
                                     notes: Optional[str] = None) -> dict:
    created, skipped = [], []
    for emp_id in employee_ids:
        try:
            shift = await create_shift(
                tenant_id=tenant_id, schedule_id=schedule_id, employee_id=emp_id, shift_date=shift_date,
                start_at=start_at, end_at=end_at, actor_user_id=actor_user_id, actor_email=actor_email,
                title=title, location=location, notes=notes,
            )
            created.append(shift)
        except ScheduleError as e:
            skipped.append({"employee_id": emp_id, "reason": e.detail})
    return {"created": created, "skipped": skipped}


async def copy_day(*, tenant_id: str, schedule_id: str, source_date: str, target_date: str,
                    actor_user_id: str, actor_email: str) -> dict:
    source_shifts = [s async for s in db.shifts.find(
        {"tenant_id": tenant_id, "schedule_id": schedule_id, "shift_date": source_date, "status": {"$ne": "cancelled"}},
        {"_id": 0},
    )]
    created, skipped = [], []
    for s in source_shifts:
        result = await copy_shift(tenant_id=tenant_id, shift_id=s["id"], actor_user_id=actor_user_id,
                                   actor_email=actor_email, target_dates=[target_date])
        created += result["created"]
        skipped += result["skipped"]
    return {"created": created, "skipped": skipped}


async def copy_week(*, tenant_id: str, source_period_start: str, target_period_start: str,
                     actor_user_id: str, actor_email: str) -> dict:
    src_start, _ = week_bounds_for_date_str(source_period_start)
    tgt_start, tgt_end = week_bounds_for_date_str(target_period_start)
    source_schedule = await db.schedules.find_one({"tenant_id": tenant_id, "period_start": src_start}, {"_id": 0})
    if not source_schedule:
        raise ScheduleError(404, "Source schedule not found")
    target_schedule = await get_or_create_schedule(tenant_id=tenant_id, period_start=tgt_start, actor_user_id=actor_user_id)
    day_offset = (date.fromisoformat(tgt_start) - date.fromisoformat(src_start)).days
    source_shifts = [s async for s in db.shifts.find(
        {"tenant_id": tenant_id, "schedule_id": source_schedule["id"], "status": {"$ne": "cancelled"}}, {"_id": 0},
    )]
    created, skipped = [], []
    for s in source_shifts:
        new_date = (date.fromisoformat(s["shift_date"]) + timedelta(days=day_offset)).isoformat()
        new_start_dt = _parse_dt(s["start_at"]) + timedelta(days=day_offset)
        new_end_dt = _parse_dt(s["end_at"]) + timedelta(days=day_offset)
        try:
            shift = await create_shift(
                tenant_id=tenant_id, schedule_id=target_schedule["id"], employee_id=s["employee_id"],
                shift_date=new_date, start_at=new_start_dt.isoformat(), end_at=new_end_dt.isoformat(),
                actor_user_id=actor_user_id, actor_email=actor_email,
                title=s.get("title"), location=s.get("location"), notes=s.get("notes"),
                break_minutes_expected=s.get("break_minutes_expected", 0),
                work_order_id=s.get("work_order_id"), order_id=s.get("order_id"),
            )
            created.append(shift)
        except ScheduleError as e:
            skipped.append({"employee_id": s["employee_id"], "date": new_date, "reason": e.detail})
    return {"schedule": target_schedule, "created": created, "skipped": skipped}


# ---- Publish / republish / archive ----

async def _notify_shift_change(tenant_id: str, employee: dict, shift: dict, change: str) -> None:
    """Best-effort employee notification. Reuses `services/email.py` (Employee
    Portal identities generally have no staff login) and `services/notifications.py`
    (only if the employee also happens to have a linked staff `User`)."""
    verb = {"added": "added to your schedule", "changed": "changed on your schedule", "cancelled": "cancelled"}[change]
    title = f"Shift {verb}"
    body = f"{shift.get('shift_date')} {shift.get('start_at', '')[11:16]}–{shift.get('end_at', '')[11:16]}"
    if shift.get("location"):
        body += f" at {shift['location']}"
    body += ". View: /portal/employee/schedule"
    if employee.get("linked_user_id"):
        try:
            await notify(
                tenant_id=tenant_id, recipient_user_id=employee["linked_user_id"], module="team",
                kind=f"shift.{change}", title=title, body=body, entity_type="shift", entity_id=shift["id"],
                link="/team/schedule",
            )
        except Exception:
            pass
    if employee.get("email"):
        try:
            send_email(to_email=employee["email"], subject=f"SignGuy AI — {title}", body_text=body)
        except Exception:
            pass


async def publish_schedule(*, tenant_id: str, schedule_id: str, actor_user_id: str, actor_email: str) -> dict:
    schedule = await _get_schedule(tenant_id, schedule_id)
    if schedule["status"] == "archived":
        raise ScheduleError(400, "Schedule is archived")
    if schedule["status"] == "published":
        return serialize_doc(schedule)  # idempotent no-op — avoids duplicate notification spam
    shifts = [s async for s in db.shifts.find(
        {"tenant_id": tenant_id, "schedule_id": schedule_id, "status": {"$ne": "cancelled"}}, {"_id": 0},
    )]
    now_iso = utc_now().isoformat()
    await db.schedules.update_one(
        {"id": schedule_id, "tenant_id": tenant_id},
        {"$set": {"status": "published", "published_at": now_iso, "published_by": actor_user_id,
                   "last_notified_at": now_iso, "updated_at": now_iso}},
    )
    employee_ids = sorted({s["employee_id"] for s in shifts})
    for emp_id in employee_ids:
        emp = await db.employees.find_one({"id": emp_id, "tenant_id": tenant_id}, {"_id": 0})
        if emp:
            await _notify_shift_change(tenant_id, emp, {"id": schedule_id, "shift_date": schedule["period_start"],
                                                          "start_at": "", "end_at": "", "location": None}, "added")
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="schedule_published", entity_type="schedule", entity_id=schedule_id,
        summary=f"Schedule {schedule['period_start']}\u2013{schedule['period_end']} published ({len(employee_ids)} employee(s) notified)",
    )
    doc = await db.schedules.find_one({"id": schedule_id, "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})


async def republish_schedule(*, tenant_id: str, schedule_id: str, actor_user_id: str, actor_email: str) -> dict:
    schedule = await _get_schedule(tenant_id, schedule_id)
    if schedule["status"] != "published":
        raise ScheduleError(400, "Schedule must already be published to republish")
    last_notified = schedule.get("last_notified_at") or schedule.get("published_at")
    changed_shifts = [s async for s in db.shifts.find(
        {"tenant_id": tenant_id, "schedule_id": schedule_id, "updated_at": {"$gt": last_notified}}, {"_id": 0},
    )]
    if not changed_shifts:
        raise ScheduleError(400, "No changes since the last publish — nothing to republish")
    now_iso = utc_now().isoformat()
    new_version = schedule.get("version", 1) + 1
    await db.schedules.update_one(
        {"id": schedule_id, "tenant_id": tenant_id},
        {"$set": {"version": new_version, "published_at": now_iso, "published_by": actor_user_id,
                   "last_notified_at": now_iso, "updated_at": now_iso}},
    )
    employee_ids = sorted({s["employee_id"] for s in changed_shifts})
    for emp_id in employee_ids:
        emp = await db.employees.find_one({"id": emp_id, "tenant_id": tenant_id}, {"_id": 0})
        if emp:
            await _notify_shift_change(tenant_id, emp, {"id": schedule_id, "shift_date": schedule["period_start"],
                                                          "start_at": "", "end_at": "", "location": None}, "changed")
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="schedule_republished", entity_type="schedule", entity_id=schedule_id,
        summary=f"Schedule {schedule['period_start']}\u2013{schedule['period_end']} republished v{new_version} ({len(employee_ids)} employee(s) notified)",
    )
    doc = await db.schedules.find_one({"id": schedule_id, "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})


async def archive_schedule(*, tenant_id: str, schedule_id: str, actor_user_id: str, actor_email: str) -> dict:
    schedule = await _get_schedule(tenant_id, schedule_id)
    if schedule["status"] == "archived":
        raise ScheduleError(400, "Schedule is already archived")
    await db.schedules.update_one(
        {"id": schedule_id, "tenant_id": tenant_id},
        {"$set": {"status": "archived", "updated_at": utc_now().isoformat()}},
    )
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="schedule_updated", entity_type="schedule", entity_id=schedule_id,
        summary=f"Schedule {schedule['period_start']}\u2013{schedule['period_end']} archived",
    )
    doc = await db.schedules.find_one({"id": schedule_id, "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})


# ---- Team Dashboard compact scheduling snapshot ----

async def today_snapshot(*, tenant_id: str) -> dict:
    tz = await get_tenant_timezone(tenant_id)
    from .time_period_utils import business_date
    today = business_date(utc_now(), tz)
    published_schedule_ids = [s["id"] async for s in db.schedules.find(
        {"tenant_id": tenant_id, "status": "published"}, {"_id": 0, "id": 1},
    )]
    today_shifts = [s async for s in db.shifts.find(
        {"tenant_id": tenant_id, "shift_date": today, "status": {"$ne": "cancelled"},
         "schedule_id": {"$in": published_schedule_ids}}, {"_id": 0},
    )]
    scheduled_employee_ids = {s["employee_id"] for s in today_shifts}
    open_entries = [e async for e in db.time_entries.find(
        {"tenant_id": tenant_id, "status": "open"}, {"_id": 0, "employee_id": 1},
    )]
    clocked_in_ids = {e["employee_id"] for e in open_entries}
    draft_with_shifts = await db.schedules.count_documents({"tenant_id": tenant_id, "status": "draft"})
    conflicts_overridden = await db.shifts.count_documents(
        {"tenant_id": tenant_id, "status": {"$ne": "cancelled"}, "conflict_override_reason": {"$ne": None}}
    )
    return {
        "employees_scheduled_today": len(scheduled_employee_ids),
        "scheduled_not_clocked_in": len(scheduled_employee_ids - clocked_in_ids),
        "unpublished_draft_schedules": draft_with_shifts,
        "conflicts_overridden": conflicts_overridden,
    }
