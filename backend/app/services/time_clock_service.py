"""EC8 phase 8b — Time Clock service (single authoritative TimeEntry model).

Router calls this — never touches `db.time_entries` directly for mutations,
so every write goes through the same validation + audit path.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.time_entry import TimeEntry
from .activity import record_activity_with_audit
from .time_period_utils import business_date, get_tenant_timezone

MISSED_CLOCKOUT_THRESHOLD_HOURS = 14


class TimeEntryError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _minutes_between(a: str, b: str) -> int:
    ta = datetime.fromisoformat(a)
    tb = datetime.fromisoformat(b)
    return max(0, int((tb - ta).total_seconds() // 60))


async def _get_employee(tenant_id: str, employee_id: str) -> dict:
    emp = await db.employees.find_one({"id": employee_id, "tenant_id": tenant_id}, {"_id": 0})
    if not emp:
        raise TimeEntryError(404, "Employee not found")
    return emp


async def get_active_entry(*, tenant_id: str, employee_id: str) -> Optional[dict]:
    doc = await db.time_entries.find_one({"tenant_id": tenant_id, "employee_id": employee_id, "status": "open"}, {"_id": 0})
    return serialize_doc(doc) if doc else None


def _active_break(entry: dict) -> Optional[dict]:
    for b in entry.get("breaks", []):
        if not b.get("end_at"):
            return b
    return None


async def clock_in(*, tenant_id: str, employee_id: str, actor_user_id: str, actor_email: str,
                    source: str, work_order_id: Optional[str] = None, notes: Optional[str] = None) -> dict:
    emp = await _get_employee(tenant_id, employee_id)
    if emp["status"] != "active":
        raise TimeEntryError(400, f"Employee is {emp['status']}, cannot clock in")
    if await get_active_entry(tenant_id=tenant_id, employee_id=employee_id):
        raise TimeEntryError(409, "Employee already has an active time entry")
    now = utc_now()
    tz = await get_tenant_timezone(tenant_id)
    doc = TimeEntry(
        tenant_id=tenant_id, employee_id=employee_id, linked_user_id=emp.get("linked_user_id"),
        work_date=business_date(now, tz), clock_in_at=now.isoformat(), status="open", source=source,
        work_order_id=work_order_id, notes=notes, created_by=actor_user_id, updated_by=actor_user_id,
    ).model_dump()
    try:
        await db.time_entries.insert_one(prepare_for_mongo(dict(doc)))
    except DuplicateKeyError:
        raise TimeEntryError(409, "Employee already has an active time entry")
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="employee_clocked_in", entity_type="time_entry", entity_id=doc["id"],
        summary=f"{emp['name']} clocked in",
    )
    doc.pop("_id", None)
    return serialize_doc(doc)


async def clock_out(*, tenant_id: str, employee_id: str, actor_user_id: str, actor_email: str) -> dict:
    entry = await get_active_entry(tenant_id=tenant_id, employee_id=employee_id)
    if not entry:
        raise TimeEntryError(400, "Employee is not currently clocked in")
    emp = await _get_employee(tenant_id, employee_id)
    now = utc_now()
    now_iso = now.isoformat()
    breaks = entry.get("breaks", [])
    total_break_minutes = 0
    for b in breaks:
        if not b.get("end_at"):
            b["end_at"] = now_iso  # safely close any active break at clock-out time
        total_break_minutes += _minutes_between(b["start_at"], b["end_at"])
    worked_minutes = max(0, _minutes_between(entry["clock_in_at"], now_iso) - total_break_minutes)
    upd = {
        "clock_out_at": now_iso, "breaks": breaks, "total_break_minutes": total_break_minutes,
        "worked_minutes": worked_minutes, "regular_minutes": worked_minutes, "overtime_minutes": 0,
        "status": "completed", "updated_by": actor_user_id, "updated_at": now_iso,
    }
    await db.time_entries.update_one({"id": entry["id"], "tenant_id": tenant_id}, {"$set": upd})
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="employee_clocked_out", entity_type="time_entry", entity_id=entry["id"],
        summary=f"{emp['name']} clocked out ({worked_minutes} min worked)",
    )
    doc = await db.time_entries.find_one({"id": entry["id"], "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})


async def start_break(*, tenant_id: str, employee_id: str, actor_user_id: str, actor_email: str) -> dict:
    entry = await get_active_entry(tenant_id=tenant_id, employee_id=employee_id)
    if not entry:
        raise TimeEntryError(400, "Employee is not currently clocked in")
    if _active_break(entry):
        raise TimeEntryError(409, "A break is already in progress")
    now_iso = utc_now().isoformat()
    breaks = entry.get("breaks", []) + [{"start_at": now_iso, "end_at": None}]
    await db.time_entries.update_one({"id": entry["id"], "tenant_id": tenant_id},
                                      {"$set": {"breaks": breaks, "updated_by": actor_user_id, "updated_at": now_iso}})
    emp = await _get_employee(tenant_id, employee_id)
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="employee_break_started", entity_type="time_entry", entity_id=entry["id"],
        summary=f"{emp['name']} started a break",
    )
    doc = await db.time_entries.find_one({"id": entry["id"], "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})


async def end_break(*, tenant_id: str, employee_id: str, actor_user_id: str, actor_email: str) -> dict:
    entry = await get_active_entry(tenant_id=tenant_id, employee_id=employee_id)
    if not entry:
        raise TimeEntryError(400, "Employee is not currently clocked in")
    active = _active_break(entry)
    if not active:
        raise TimeEntryError(400, "No break is currently in progress")
    now_iso = utc_now().isoformat()
    breaks = entry.get("breaks", [])
    for b in breaks:
        if b is active or (b.get("start_at") == active["start_at"] and not b.get("end_at")):
            b["end_at"] = now_iso
            break
    total_break_minutes = sum(_minutes_between(b["start_at"], b["end_at"]) for b in breaks if b.get("end_at"))
    await db.time_entries.update_one(
        {"id": entry["id"], "tenant_id": tenant_id},
        {"$set": {"breaks": breaks, "total_break_minutes": total_break_minutes, "updated_by": actor_user_id, "updated_at": now_iso}},
    )
    emp = await _get_employee(tenant_id, employee_id)
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="employee_break_ended", entity_type="time_entry", entity_id=entry["id"],
        summary=f"{emp['name']} ended a break",
    )
    doc = await db.time_entries.find_one({"id": entry["id"], "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})


async def list_entries(*, tenant_id: str, employee_id: Optional[str] = None,
                        date_from: Optional[str] = None, date_to: Optional[str] = None,
                        status: Optional[str] = None) -> list[dict]:
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
        filt["work_date"] = rng
    cur = db.time_entries.find(filt, {"_id": 0}).sort("clock_in_at", -1).limit(500)
    return [serialize_doc(d) async for d in cur]


def _overlaps(a_start: str, a_end: Optional[str], b_start: str, b_end: Optional[str]) -> bool:
    a_end_dt = datetime.fromisoformat(a_end) if a_end else datetime.now(timezone.utc)
    b_end_dt = datetime.fromisoformat(b_end) if b_end else datetime.now(timezone.utc)
    return datetime.fromisoformat(a_start) < b_end_dt and datetime.fromisoformat(b_start) < a_end_dt


async def correct_entry(*, tenant_id: str, entry_id: str, actor_user_id: str, actor_email: str,
                         new_values: dict, reason: str) -> dict:
    if not reason or not reason.strip():
        raise TimeEntryError(400, "A correction reason is required")
    entry = await db.time_entries.find_one({"id": entry_id, "tenant_id": tenant_id}, {"_id": 0})
    if not entry:
        raise TimeEntryError(404, "Time entry not found")
    if entry["status"] == "approved":
        raise TimeEntryError(409, "Approved entries cannot be corrected — reopen the timesheet first")
    if entry["status"] == "voided":
        raise TimeEntryError(409, "Voided entries cannot be corrected")

    new_clock_in = new_values.get("clock_in_at", entry["clock_in_at"])
    new_clock_out = new_values.get("clock_out_at", entry.get("clock_out_at"))
    new_breaks = new_values.get("breaks", entry.get("breaks", []))
    if new_clock_out and datetime.fromisoformat(new_clock_out) <= datetime.fromisoformat(new_clock_in):
        raise TimeEntryError(400, "Clock-out must be after clock-in")
    for b in new_breaks:
        if not b.get("end_at"):
            raise TimeEntryError(400, "All break periods must have an end time on a corrected entry")

    others = db.time_entries.find(
        {"tenant_id": tenant_id, "employee_id": entry["employee_id"], "id": {"$ne": entry_id},
         "status": {"$ne": "voided"}}, {"_id": 0},
    )
    async for other in others:
        if _overlaps(new_clock_in, new_clock_out, other["clock_in_at"], other.get("clock_out_at")):
            raise TimeEntryError(409, "This time range overlaps another time entry for this employee")

    total_break_minutes = sum(_minutes_between(b["start_at"], b["end_at"]) for b in new_breaks)
    worked_minutes = _minutes_between(new_clock_in, new_clock_out) - total_break_minutes if new_clock_out else 0
    worked_minutes = max(0, worked_minutes)
    tz = await get_tenant_timezone(tenant_id)
    new_work_date = business_date(datetime.fromisoformat(new_clock_in), tz)

    original_snapshot = {
        "clock_in_at": entry["clock_in_at"], "clock_out_at": entry.get("clock_out_at"),
        "breaks": entry.get("breaks", []), "total_break_minutes": entry.get("total_break_minutes", 0),
        "worked_minutes": entry.get("worked_minutes", 0), "work_date": entry.get("work_date"),
    }
    now_iso = utc_now().isoformat()
    new_snapshot = {
        "clock_in_at": new_clock_in, "clock_out_at": new_clock_out, "breaks": new_breaks,
        "total_break_minutes": total_break_minutes, "worked_minutes": worked_minutes, "work_date": new_work_date,
    }
    correction_record = {"original": original_snapshot, "new": new_snapshot, "reason": reason,
                          "editor_user_id": actor_user_id, "at": now_iso}
    upd = {
        **new_snapshot, "regular_minutes": worked_minutes, "overtime_minutes": 0,
        "status": "corrected" if new_clock_out else "open",
        "notes": new_values.get("notes", entry.get("notes")),
        "work_order_id": new_values.get("work_order_id", entry.get("work_order_id")),
        "updated_by": actor_user_id, "updated_at": now_iso,
    }
    await db.time_entries.update_one(
        {"id": entry_id, "tenant_id": tenant_id},
        {"$set": upd, "$push": {"corrections": correction_record}},
    )
    emp = await _get_employee(tenant_id, entry["employee_id"])
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="time_entry_corrected", entity_type="time_entry", entity_id=entry_id,
        summary=f"Time entry corrected for {emp['name']}: {reason}",
        diff={"before": original_snapshot, "after": new_snapshot}, severity="warning",
    )
    doc = await db.time_entries.find_one({"id": entry_id, "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})


async def void_entry(*, tenant_id: str, entry_id: str, actor_user_id: str, actor_email: str, reason: str) -> dict:
    if not reason or not reason.strip():
        raise TimeEntryError(400, "A void reason is required")
    entry = await db.time_entries.find_one({"id": entry_id, "tenant_id": tenant_id}, {"_id": 0})
    if not entry:
        raise TimeEntryError(404, "Time entry not found")
    if entry["status"] == "approved":
        raise TimeEntryError(409, "Approved entries cannot be voided — reopen the timesheet first")
    if entry["status"] == "voided":
        raise TimeEntryError(400, "Time entry is already voided")
    now_iso = utc_now().isoformat()
    await db.time_entries.update_one(
        {"id": entry_id, "tenant_id": tenant_id},
        {"$set": {"status": "voided", "void_reason": reason, "updated_by": actor_user_id, "updated_at": now_iso}},
    )
    emp = await _get_employee(tenant_id, entry["employee_id"])
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="time_entry_voided", entity_type="time_entry", entity_id=entry_id,
        summary=f"Time entry voided for {emp['name']}: {reason}", severity="warning",
    )
    doc = await db.time_entries.find_one({"id": entry_id, "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})


def is_missed_clockout(entry: dict, now: Optional[datetime] = None) -> bool:
    if entry.get("status") != "open":
        return False
    now = now or utc_now()
    started = datetime.fromisoformat(entry["clock_in_at"])
    return (now - started) > timedelta(hours=MISSED_CLOCKOUT_THRESHOLD_HOURS)


async def team_status(*, tenant_id: str) -> dict:
    open_entries = [serialize_doc(d) async for d in db.time_entries.find({"tenant_id": tenant_id, "status": "open"}, {"_id": 0})]
    on_break = sum(1 for e in open_entries if _active_break(e))
    missed = sum(1 for e in open_entries if is_missed_clockout(e))
    return {
        "open_entries": len(open_entries),
        "clocked_in": len(open_entries) - on_break,
        "on_break": on_break,
        "missed_clock_outs": missed,
    }
