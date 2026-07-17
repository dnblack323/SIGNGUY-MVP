"""EC12 Phase 12D - shared calendar and appointment service."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.calendar import CalendarEvent
from .activity import record_activity_with_audit
from . import notifications, time_off_service


class CalendarError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _overlaps(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    return _parse_dt(a_start) < _parse_dt(b_end) and _parse_dt(b_start) < _parse_dt(a_end)


async def _get_event(tenant_id: str, event_id: str) -> dict:
    doc = await db.calendar_events.find_one({"tenant_id": tenant_id, "id": event_id}, {"_id": 0})
    if not doc:
        raise CalendarError("not_found", "Calendar event not found", 404)
    return serialize_doc(doc)


async def _validate_links(tenant_id: str, payload: dict) -> None:
    collections = {
        "customer_id": "customers",
        "order_id": "orders",
        "order_item_id": "order_items",
        "work_order_id": "work_orders",
        "production_stage_id": "production_stage_instances",
        "employee_id": "employees",
        "assigned_user_id": "users",
    }
    for field, coll in collections.items():
        value = payload.get(field)
        if not value:
            continue
        doc = await db[coll].find_one({"tenant_id": tenant_id, "id": value}, {"_id": 0})
        if not doc:
            raise CalendarError("linked_record_not_found", f"{field} not found", 404)
        if field == "employee_id" and doc.get("status") != "active":
            raise CalendarError("inactive_employee", "Inactive employee cannot be assigned to appointment", 400)


def _safe_event(doc: dict) -> dict:
    hidden = {"description_internal", "conflict_overrides"}
    return {k: v for k, v in serialize_doc(doc).items() if k not in hidden}


async def _employee_name(tenant_id: str, employee_id: Optional[str]) -> Optional[str]:
    if not employee_id:
        return None
    emp = await db.employees.find_one({"tenant_id": tenant_id, "id": employee_id}, {"_id": 0, "name": 1})
    return emp.get("name") if emp else None


async def check_conflicts(*, tenant_id: str, start_at: str, end_at: str,
                          employee_id: Optional[str] = None,
                          location: Optional[str] = None,
                          customer_id: Optional[str] = None,
                          event_id: Optional[str] = None) -> list[dict[str, Any]]:
    if not start_at or not end_at or _parse_dt(end_at) <= _parse_dt(start_at):
        raise CalendarError("invalid_range", "Calendar event end must be after start", 400)
    conflicts: list[dict[str, Any]] = []
    base: dict[str, Any] = {"tenant_id": tenant_id, "status": {"$nin": ["canceled"]}, "archived_at": None}
    if event_id:
        base["id"] = {"$ne": event_id}
    if employee_id:
        async for ev in db.calendar_events.find({**base, "employee_id": employee_id}, {"_id": 0}):
            if _overlaps(start_at, end_at, ev["start_at"], ev["end_at"]):
                conflicts.append({"source_type": "calendar_event", "source_id": ev["id"], "kind": "employee_appointment_overlap", "title": ev.get("title")})
        async for shift in db.shifts.find({"tenant_id": tenant_id, "employee_id": employee_id, "status": {"$ne": "cancelled"}}, {"_id": 0}):
            if _overlaps(start_at, end_at, shift["start_at"], shift["end_at"]):
                conflicts.append({"source_type": "shift", "source_id": shift["id"], "kind": "employee_shift_overlap", "title": shift.get("title") or "Shift"})
        for absence in await time_off_service.approved_absence_overlays(tenant_id=tenant_id, start_at=start_at, end_at=end_at, employee_id=employee_id):
            conflicts.append({"source_type": absence["source_type"], "source_id": absence["source_id"], "kind": "approved_absence", "title": absence["title"]})
    if location:
        async for ev in db.calendar_events.find({**base, "location": location}, {"_id": 0}):
            if _overlaps(start_at, end_at, ev["start_at"], ev["end_at"]):
                conflicts.append({"source_type": "calendar_event", "source_id": ev["id"], "kind": "location_overlap", "title": ev.get("title")})
    if customer_id:
        async for ev in db.calendar_events.find({**base, "customer_id": customer_id}, {"_id": 0}):
            if _overlaps(start_at, end_at, ev["start_at"], ev["end_at"]):
                conflicts.append({"source_type": "calendar_event", "source_id": ev["id"], "kind": "customer_overlap", "title": ev.get("title")})
    return conflicts


async def create_event(*, tenant_id: str, actor_user_id: str, actor_email: str, payload: dict) -> dict:
    await _validate_links(tenant_id, payload)
    conflicts = await check_conflicts(
        tenant_id=tenant_id,
        start_at=payload["start_at"],
        end_at=payload["end_at"],
        employee_id=payload.get("employee_id"),
        location=payload.get("location"),
        customer_id=payload.get("customer_id"),
    )
    override_reason = payload.get("conflict_override_reason")
    if conflicts and not override_reason:
        raise CalendarError("conflict", "Calendar conflict requires manager override reason", 409)
    now = utc_now().isoformat()
    history = [{"action": "created", "actor_user_id": actor_user_id, "at": now, "conflict_count": len(conflicts)}]
    overrides = []
    if conflicts:
        overrides.append({"reason": override_reason, "actor_user_id": actor_user_id, "at": now, "conflicts": conflicts})
    doc = CalendarEvent(
        tenant_id=tenant_id,
        event_type=payload.get("event_type") or "custom",
        title=payload["title"],
        description=payload.get("description"),
        start_at=payload["start_at"],
        end_at=payload["end_at"],
        all_day=bool(payload.get("all_day", False)),
        timezone=payload.get("timezone"),
        location=payload.get("location"),
        customer_id=payload.get("customer_id"),
        order_id=payload.get("order_id"),
        order_item_id=payload.get("order_item_id"),
        work_order_id=payload.get("work_order_id"),
        production_stage_id=payload.get("production_stage_id"),
        employee_id=payload.get("employee_id"),
        assigned_user_id=payload.get("assigned_user_id"),
        created_by_user_id=actor_user_id,
        visibility=payload.get("visibility") or "staff",
        reminder_policy=payload.get("reminder_policy") or {},
        recurrence_rule=payload.get("recurrence_rule"),
        source_id=None,
        history=history,
        conflict_overrides=overrides,
    ).model_dump()
    await db.calendar_events.insert_one(prepare_for_mongo(dict(doc)))
    clean = serialize_doc(doc)
    await db.calendar_events.update_one({"tenant_id": tenant_id, "id": clean["id"]}, {"$set": {"source_id": clean["id"]}})
    clean["source_id"] = clean["id"]
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="calendar", action="calendar_event.created", entity_type="calendar_event", entity_id=clean["id"],
        summary=f"Calendar event created: {clean['title']}", metadata={"conflict_count": len(conflicts)},
    )
    if conflicts:
        await record_activity_with_audit(
            tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
            module="calendar", action="calendar_event.conflict_override", entity_type="calendar_event", entity_id=clean["id"],
            summary=f"Calendar conflict overridden: {clean['title']}", severity="warning",
            metadata={"conflict_count": len(conflicts)},
        )
    await _notify_event_assignment(tenant_id, clean, kind="calendar.assigned", title=f"Appointment assigned: {clean['title']}")
    return {**_safe_event(clean), "conflicts": conflicts}


async def list_events(*, tenant_id: str, start_at: str, end_at: str,
                      event_type: Optional[str] = None, employee_id: Optional[str] = None,
                      customer_id: Optional[str] = None, order_id: Optional[str] = None,
                      work_order_id: Optional[str] = None, status: Optional[str] = None,
                      source_type: Optional[str] = None, visibility: Optional[str] = None,
                      limit: int = 200, skip: int = 0) -> dict:
    filt: dict[str, Any] = {"tenant_id": tenant_id, "archived_at": None}
    if event_type:
        filt["event_type"] = event_type
    if employee_id:
        filt["employee_id"] = employee_id
    if customer_id:
        filt["customer_id"] = customer_id
    if order_id:
        filt["order_id"] = order_id
    if work_order_id:
        filt["work_order_id"] = work_order_id
    if status:
        filt["status"] = status
    if source_type:
        filt["source_type"] = source_type
    if visibility:
        filt["visibility"] = visibility
    stored = []
    async for ev in db.calendar_events.find(filt, {"_id": 0}).sort("start_at", 1).skip(skip).limit(min(limit, 500)):
        if _overlaps(start_at, end_at, ev["start_at"], ev["end_at"]):
            stored.append(_normalize_stored_event(ev))
    projections = await _projected_items(tenant_id=tenant_id, start_at=start_at, end_at=end_at, employee_id=employee_id)
    items = [i for i in stored + projections if _feed_match(i, event_type=event_type, employee_id=employee_id, customer_id=customer_id, order_id=order_id, work_order_id=work_order_id, status=status, source_type=source_type, visibility=visibility)]
    items.sort(key=lambda i: (i.get("start_at") or "", i.get("title") or ""))
    return {"items": items[:limit], "total": len(items), "limit": limit, "skip": skip}


def _normalize_stored_event(ev: dict) -> dict:
    return {
        **_safe_event(ev),
        "id": f"calendar_event:{ev['id']}",
        "source_type": "calendar_event",
        "source_id": ev["id"],
        "display_title": ev.get("title"),
        "color": _color_for_event(ev.get("event_type")),
        "allowed_actions": ["update", "reschedule", "cancel", "archive", "assign"],
    }


def _color_for_event(event_type: Optional[str]) -> str:
    return {
        "installation": "emerald",
        "site_survey": "sky",
        "vehicle_dropoff": "violet",
        "vehicle_pickup": "violet",
        "production_milestone": "orange",
        "internal_meeting": "slate",
    }.get(event_type or "", "blue")


async def _projected_items(*, tenant_id: str, start_at: str, end_at: str, employee_id: Optional[str] = None) -> list[dict]:
    items: list[dict] = []
    shift_filter: dict[str, Any] = {"tenant_id": tenant_id, "status": {"$ne": "cancelled"}}
    if employee_id:
        shift_filter["employee_id"] = employee_id
    async for shift in db.shifts.find(shift_filter, {"_id": 0}).sort("start_at", 1):
        if not _overlaps(start_at, end_at, shift["start_at"], shift["end_at"]):
            continue
        items.append({
            "id": f"shift:{shift['id']}",
            "source_type": "shift",
            "source_id": shift["id"],
            "event_type": "shift",
            "title": shift.get("title") or "Shift",
            "display_title": shift.get("title") or "Shift",
            "start_at": shift["start_at"],
            "end_at": shift["end_at"],
            "status": shift.get("status"),
            "employee_id": shift.get("employee_id"),
            "work_order_id": shift.get("work_order_id"),
            "order_id": shift.get("order_id"),
            "location": shift.get("location"),
            "visibility": "employee",
            "color": "green",
            "allowed_actions": [],
        })
    items.extend(await time_off_service.approved_absence_overlays(tenant_id=tenant_id, start_at=start_at, end_at=end_at, employee_id=employee_id))
    task_filter: dict[str, Any] = {"tenant_id": tenant_id, "due_at": {"$ne": None}, "archived_at": None, "status": {"$nin": ["completed", "canceled"]}}
    if employee_id:
        task_filter["assigned_employee_id"] = employee_id
    async for task in db.tasks.find(task_filter, {"_id": 0}).sort("due_at", 1).limit(300):
        due = task.get("due_at")
        if not due:
            continue
        task_end = (_parse_dt(due) + timedelta(minutes=30)).isoformat()
        if not _overlaps(start_at, end_at, due, task_end):
            continue
        items.append({
            "id": f"task:{task['id']}",
            "source_type": "task",
            "source_id": task["id"],
            "event_type": "task_due",
            "title": f"Task due: {task.get('title')}",
            "display_title": f"Task due: {task.get('title')}",
            "start_at": due,
            "end_at": task_end,
            "status": task.get("status"),
            "employee_id": task.get("assigned_employee_id"),
            "customer_id": task.get("customer_id"),
            "order_id": task.get("order_id"),
            "work_order_id": task.get("work_order_id"),
            "production_stage_id": task.get("production_stage_id"),
            "visibility": "employee" if task.get("employee_visible") else "staff",
            "color": "purple",
            "allowed_actions": [],
        })
    stage_filter: dict[str, Any] = {"tenant_id": tenant_id, "due_at": {"$ne": None}, "status": {"$nin": ["completed", "skipped"]}}
    if employee_id:
        stage_filter["assigned_employee_id"] = employee_id
    async for stage in db.production_stage_instances.find(stage_filter, {"_id": 0}).sort("due_at", 1).limit(300):
        due = stage.get("due_at")
        if not due:
            continue
        stage_end = (_parse_dt(due) + timedelta(hours=1)).isoformat()
        if not _overlaps(start_at, end_at, due, stage_end):
            continue
        items.append({
            "id": f"production_stage:{stage['id']}",
            "source_type": "production_stage",
            "source_id": stage["id"],
            "event_type": "production_milestone",
            "title": f"Production: {stage.get('stage_name')}",
            "display_title": f"Production: {stage.get('stage_name')}",
            "start_at": due,
            "end_at": stage_end,
            "status": stage.get("status"),
            "employee_id": stage.get("assigned_employee_id"),
            "assigned_user_id": stage.get("assigned_user_id"),
            "order_id": stage.get("order_id"),
            "order_item_id": stage.get("order_item_id"),
            "work_order_id": stage.get("work_order_id"),
            "production_stage_id": stage.get("id"),
            "visibility": "employee" if stage.get("employee_visible", True) else "staff",
            "color": "orange",
            "allowed_actions": [],
        })
    return items


def _feed_match(item: dict, **filters) -> bool:
    for key, value in filters.items():
        if not value:
            continue
        if key == "event_type" and item.get("event_type") != value:
            return False
        if key != "event_type" and item.get(key) != value:
            return False
    return True


async def get_event(*, tenant_id: str, event_id: str) -> dict:
    return _safe_event(await _get_event(tenant_id, event_id))


async def update_event(*, tenant_id: str, event_id: str, actor_user_id: str, actor_email: str,
                       payload: dict, action: str = "updated") -> dict:
    existing = await _get_event(tenant_id, event_id)
    clean = {k: v for k, v in payload.items() if v is not None}
    await _validate_links(tenant_id, clean)
    start_at = clean.get("start_at", existing["start_at"])
    end_at = clean.get("end_at", existing["end_at"])
    employee_id = clean.get("employee_id", existing.get("employee_id"))
    location = clean.get("location", existing.get("location"))
    customer_id = clean.get("customer_id", existing.get("customer_id"))
    conflicts = await check_conflicts(
        tenant_id=tenant_id, start_at=start_at, end_at=end_at, employee_id=employee_id,
        location=location, customer_id=customer_id, event_id=event_id,
    )
    override_reason = clean.pop("conflict_override_reason", None)
    if conflicts and not override_reason:
        raise CalendarError("conflict", "Calendar conflict requires manager override reason", 409)
    now = utc_now().isoformat()
    clean.update({"updated_at": now, "version": int(existing.get("version", 1)) + 1})
    if action == "rescheduled":
        clean["status"] = "rescheduled"
    await db.calendar_events.update_one({"tenant_id": tenant_id, "id": event_id}, {"$set": prepare_for_mongo(clean)})
    history = {"action": action, "actor_user_id": actor_user_id, "at": now}
    if "start_at" in payload or "end_at" in payload:
        history["from"] = {"start_at": existing.get("start_at"), "end_at": existing.get("end_at")}
        history["to"] = {"start_at": start_at, "end_at": end_at}
    await db.calendar_events.update_one({"tenant_id": tenant_id, "id": event_id}, {"$push": {"history": history}})
    if conflicts:
        await db.calendar_events.update_one(
            {"tenant_id": tenant_id, "id": event_id},
            {"$push": {"conflict_overrides": {"reason": override_reason, "actor_user_id": actor_user_id, "at": now, "conflicts": conflicts}}},
        )
    updated = await _get_event(tenant_id, event_id)
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="calendar", action=f"calendar_event.{action}", entity_type="calendar_event", entity_id=event_id,
        summary=f"Calendar event {action}: {updated['title']}", metadata={"conflict_count": len(conflicts)},
    )
    await _notify_event_assignment(tenant_id, updated, kind=f"calendar.{action}", title=f"Appointment {action}: {updated['title']}")
    return {**_safe_event(updated), "conflicts": conflicts}


async def reschedule_event(**kwargs) -> dict:
    return await update_event(action="rescheduled", **kwargs)


async def cancel_event(*, tenant_id: str, event_id: str, actor_user_id: str, actor_email: str,
                       reason: Optional[str] = None) -> dict:
    existing = await _get_event(tenant_id, event_id)
    if existing.get("status") == "canceled":
        return _safe_event(existing)
    now = utc_now().isoformat()
    await db.calendar_events.update_one(
        {"tenant_id": tenant_id, "id": event_id},
        {"$set": {"status": "canceled", "updated_at": now, "version": int(existing.get("version", 1)) + 1},
         "$push": {"history": {"action": "canceled", "actor_user_id": actor_user_id, "at": now, "reason": reason}}},
    )
    updated = await _get_event(tenant_id, event_id)
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="calendar", action="calendar_event.canceled", entity_type="calendar_event", entity_id=event_id,
        summary=f"Calendar event canceled: {updated['title']}",
    )
    await _notify_event_assignment(tenant_id, updated, kind="calendar.canceled", title=f"Appointment canceled: {updated['title']}")
    return _safe_event(updated)


async def archive_event(*, tenant_id: str, event_id: str, actor_user_id: str, actor_email: str) -> dict:
    return await _archive_restore(tenant_id=tenant_id, event_id=event_id, actor_user_id=actor_user_id, actor_email=actor_email, archive=True)


async def restore_event(*, tenant_id: str, event_id: str, actor_user_id: str, actor_email: str) -> dict:
    return await _archive_restore(tenant_id=tenant_id, event_id=event_id, actor_user_id=actor_user_id, actor_email=actor_email, archive=False)


async def _archive_restore(*, tenant_id: str, event_id: str, actor_user_id: str, actor_email: str, archive: bool) -> dict:
    existing = await _get_event(tenant_id, event_id)
    now = utc_now().isoformat()
    await db.calendar_events.update_one(
        {"tenant_id": tenant_id, "id": event_id},
        {"$set": {"archived_at": now if archive else None, "updated_at": now, "version": int(existing.get("version", 1)) + 1},
         "$push": {"history": {"action": "archived" if archive else "restored", "actor_user_id": actor_user_id, "at": now}}},
    )
    updated = await _get_event(tenant_id, event_id)
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="calendar", action=f"calendar_event.{'archived' if archive else 'restored'}",
        entity_type="calendar_event", entity_id=event_id, summary=f"Calendar event {'archived' if archive else 'restored'}: {updated['title']}",
    )
    return _safe_event(updated)


async def _notify_event_assignment(tenant_id: str, event: dict, *, kind: str, title: str) -> None:
    user_id = event.get("assigned_user_id")
    if not user_id and event.get("employee_id"):
        emp = await db.employees.find_one({"tenant_id": tenant_id, "id": event["employee_id"]}, {"_id": 0, "linked_user_id": 1})
        user_id = emp.get("linked_user_id") if emp else None
    if not user_id:
        return
    try:
        await notifications.notify(
            tenant_id=tenant_id, recipient_user_id=user_id, module="calendar", kind=kind,
            title=title, body=f"{event.get('start_at')} - {event.get('end_at')}",
            entity_type="calendar_event", entity_id=event["id"], link="/shop-schedule",
        )
    except Exception:
        pass


async def employee_feed(*, tenant_id: str, employee_id: str, start_at: str, end_at: str) -> dict:
    feed = await list_events(tenant_id=tenant_id, start_at=start_at, end_at=end_at, employee_id=employee_id)
    allowed = []
    for item in feed["items"]:
        if item.get("visibility") == "staff":
            continue
        if item.get("employee_id") and item["employee_id"] != employee_id:
            continue
        allowed.append(item)
    return {"items": allowed, "total": len(allowed)}
