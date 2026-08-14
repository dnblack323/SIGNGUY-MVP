"""EC12 Phase 12D - shared calendar and appointment service."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.calendar import CalendarEvent
from ..models.schedulable_resource import SchedulableResource
from .activity import record_activity_with_audit
from . import notifications, time_off_service


class CalendarError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400, *, metadata: Optional[dict] = None):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        self.metadata = metadata or {}
        super().__init__(detail)


def _parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _overlaps(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    return _parse_dt(a_start) < _parse_dt(b_end) and _parse_dt(b_start) < _parse_dt(a_end)


def _clean_ids(values: Any) -> list[str]:
    if not values:
        return []
    if isinstance(values, str):
        values = [values]
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _assignment_ids(payload: dict, existing: Optional[dict] = None) -> dict[str, list[str]]:
    existing = existing or {}
    employee_ids = _clean_ids(payload["assigned_employee_ids"] if "assigned_employee_ids" in payload else existing.get("assigned_employee_ids"))
    primary_employee = payload["employee_id"] if "employee_id" in payload else (None if "assigned_employee_ids" in payload else existing.get("employee_id"))
    if primary_employee and primary_employee not in employee_ids:
        employee_ids.insert(0, primary_employee)
    equipment_ids = _clean_ids(payload["reserved_equipment_ids"] if "reserved_equipment_ids" in payload else existing.get("reserved_equipment_ids"))
    vehicle_ids = _clean_ids(payload["reserved_vehicle_ids"] if "reserved_vehicle_ids" in payload else existing.get("reserved_vehicle_ids"))
    resource_ids = _clean_ids(payload["reserved_resource_ids"] if "reserved_resource_ids" in payload else existing.get("reserved_resource_ids"))
    return {
        "assigned_employee_ids": employee_ids,
        "reserved_equipment_ids": equipment_ids,
        "reserved_vehicle_ids": vehicle_ids,
        "reserved_resource_ids": resource_ids,
    }


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


async def _validate_assignments(tenant_id: str, assignments: dict[str, list[str]]) -> dict[str, list[dict]]:
    summary: dict[str, list[dict]] = {"employees": [], "equipment": [], "vehicles": [], "resources": []}
    for employee_id in assignments["assigned_employee_ids"]:
        emp = await db.employees.find_one({"tenant_id": tenant_id, "id": employee_id}, {"_id": 0})
        if not emp:
            raise CalendarError("linked_record_not_found", "assigned_employee_ids contains an Employee that was not found", 404)
        if emp.get("status") != "active":
            raise CalendarError("inactive_employee", "Inactive employee cannot be assigned to appointment", 400)
        summary["employees"].append({
            "id": emp["id"],
            "name": emp.get("name"),
            "role_label": emp.get("role_label"),
            "availability_warning_count": 0,
        })
    for equipment_id in assignments["reserved_equipment_ids"]:
        eq = await db.equipment.find_one({"tenant_id": tenant_id, "id": equipment_id}, {"_id": 0})
        if not eq:
            raise CalendarError("linked_record_not_found", "reserved_equipment_ids contains Equipment that was not found", 404)
        if eq.get("category") == "vehicle":
            raise CalendarError("resource_type_mismatch", "Vehicle equipment must be reserved through reserved_vehicle_ids", 400)
        if eq.get("status") != "active":
            raise CalendarError("inactive_resource", "Inactive equipment cannot be reserved", 400)
        summary["equipment"].append({
            "id": eq["id"],
            "name": eq.get("name"),
            "category": eq.get("category"),
            "status": eq.get("status"),
        })
    for vehicle_id in assignments["reserved_vehicle_ids"]:
        vehicle = await db.equipment.find_one({"tenant_id": tenant_id, "id": vehicle_id}, {"_id": 0})
        if not vehicle:
            raise CalendarError("linked_record_not_found", "reserved_vehicle_ids contains Equipment that was not found", 404)
        if vehicle.get("category") != "vehicle":
            raise CalendarError("resource_type_mismatch", "reserved_vehicle_ids must reference Equipment records with category vehicle", 400)
        if vehicle.get("status") != "active":
            raise CalendarError("inactive_resource", "Inactive vehicle cannot be reserved", 400)
        summary["vehicles"].append({
            "id": vehicle["id"],
            "name": vehicle.get("name"),
            "category": vehicle.get("category"),
            "status": vehicle.get("status"),
        })
    for resource_id in assignments["reserved_resource_ids"]:
        resource = await db.schedulable_resources.find_one({"tenant_id": tenant_id, "id": resource_id}, {"_id": 0})
        if not resource:
            raise CalendarError("linked_record_not_found", "reserved_resource_ids contains a shop resource that was not found", 404)
        if resource.get("status") != "active":
            raise CalendarError("inactive_resource", "Inactive shop resource cannot be reserved", 400)
        summary["resources"].append({
            "id": resource["id"],
            "name": resource.get("name"),
            "resource_type": resource.get("resource_type"),
            "capacity": resource.get("capacity"),
            "location": resource.get("location"),
        })
    return summary


def _assignment_diff(before: dict, after: dict) -> dict:
    out: dict[str, dict[str, list[str]]] = {}
    for key in ("assigned_employee_ids", "reserved_equipment_ids", "reserved_vehicle_ids", "reserved_resource_ids"):
        old = set(_clean_ids(before.get(key)))
        new = set(_clean_ids(after.get(key)))
        added = sorted(new - old)
        removed = sorted(old - new)
        if added or removed:
            out[key] = {"added": added, "removed": removed}
    return out


def _safe_event(doc: dict) -> dict:
    hidden = {"description_internal", "conflict_overrides"}
    return {k: v for k, v in serialize_doc(doc).items() if k not in hidden}


async def _employee_name(tenant_id: str, employee_id: Optional[str]) -> Optional[str]:
    if not employee_id:
        return None
    emp = await db.employees.find_one({"tenant_id": tenant_id, "id": employee_id}, {"_id": 0, "name": 1})
    return emp.get("name") if emp else None


def _conflict_entry(*, resource_type: str, resource_id: Optional[str], resource_name: Optional[str],
                    event: dict, reason: str) -> dict[str, Any]:
    return {
        "resource_type": resource_type,
        "resource_id": resource_id,
        "resource_name": resource_name,
        "source_type": event.get("source_type") or "calendar_event",
        "source_id": event["id"],
        "conflicting_event_id": event["id"],
        "title": event.get("title") or event.get("display_title"),
        "start_at": event.get("start_at"),
        "end_at": event.get("end_at"),
        "reason": reason,
        "kind": reason,
    }


async def _resource_names(tenant_id: str, assignments: dict[str, list[str]]) -> dict[str, dict[str, str]]:
    names = {"employee": {}, "equipment": {}, "vehicle": {}, "resource": {}}
    if assignments["assigned_employee_ids"]:
        async for emp in db.employees.find({"tenant_id": tenant_id, "id": {"$in": assignments["assigned_employee_ids"]}}, {"_id": 0, "id": 1, "name": 1}):
            names["employee"][emp["id"]] = emp.get("name") or emp["id"]
    equipment_ids = assignments["reserved_equipment_ids"] + assignments["reserved_vehicle_ids"]
    if equipment_ids:
        async for eq in db.equipment.find({"tenant_id": tenant_id, "id": {"$in": equipment_ids}}, {"_id": 0, "id": 1, "name": 1, "category": 1}):
            bucket = "vehicle" if eq.get("category") == "vehicle" else "equipment"
            names[bucket][eq["id"]] = eq.get("name") or eq["id"]
    if assignments["reserved_resource_ids"]:
        async for res in db.schedulable_resources.find({"tenant_id": tenant_id, "id": {"$in": assignments["reserved_resource_ids"]}}, {"_id": 0, "id": 1, "name": 1}):
            names["resource"][res["id"]] = res.get("name") or res["id"]
    return names


async def check_conflicts(*, tenant_id: str, start_at: str, end_at: str,
                          employee_id: Optional[str] = None,
                          assigned_employee_ids: Optional[list[str]] = None,
                          reserved_equipment_ids: Optional[list[str]] = None,
                          reserved_vehicle_ids: Optional[list[str]] = None,
                          reserved_resource_ids: Optional[list[str]] = None,
                          location: Optional[str] = None,
                          customer_id: Optional[str] = None,
                          event_id: Optional[str] = None) -> list[dict[str, Any]]:
    if not start_at or not end_at or _parse_dt(end_at) <= _parse_dt(start_at):
        raise CalendarError("invalid_range", "Calendar event end must be after start", 400)
    conflicts: list[dict[str, Any]] = []
    base: dict[str, Any] = {"tenant_id": tenant_id, "status": {"$nin": ["canceled", "completed"]}, "archived_at": None}
    if event_id:
        base["id"] = {"$ne": event_id}
    assignments = _assignment_ids({
        "employee_id": employee_id,
        "assigned_employee_ids": assigned_employee_ids,
        "reserved_equipment_ids": reserved_equipment_ids,
        "reserved_vehicle_ids": reserved_vehicle_ids,
        "reserved_resource_ids": reserved_resource_ids,
    })
    names = await _resource_names(tenant_id, assignments)
    for assigned_employee_id in assignments["assigned_employee_ids"]:
        employee_filter = {
            **base,
            "$or": [
                {"employee_id": assigned_employee_id},
                {"assigned_employee_ids": assigned_employee_id},
            ],
        }
        async for ev in db.calendar_events.find(employee_filter, {"_id": 0}):
            if _overlaps(start_at, end_at, ev["start_at"], ev["end_at"]):
                conflicts.append(_conflict_entry(
                    resource_type="employee", resource_id=assigned_employee_id,
                    resource_name=names["employee"].get(assigned_employee_id),
                    event=ev, reason="employee_appointment_overlap",
                ))
        async for shift in db.shifts.find({"tenant_id": tenant_id, "employee_id": assigned_employee_id, "status": {"$ne": "cancelled"}}, {"_id": 0}):
            if _overlaps(start_at, end_at, shift["start_at"], shift["end_at"]):
                conflicts.append(_conflict_entry(
                    resource_type="employee", resource_id=assigned_employee_id,
                    resource_name=names["employee"].get(assigned_employee_id),
                    event={**shift, "source_type": "shift", "title": shift.get("title") or "Shift"},
                    reason="employee_shift_overlap",
                ))
        for absence in await time_off_service.approved_absence_overlays(tenant_id=tenant_id, start_at=start_at, end_at=end_at, employee_id=assigned_employee_id):
            conflicts.append(_conflict_entry(
                resource_type="employee", resource_id=assigned_employee_id,
                resource_name=names["employee"].get(assigned_employee_id),
                event={**absence, "id": absence["source_id"]},
                reason="approved_absence",
            ))
    for equipment_id in assignments["reserved_equipment_ids"]:
        async for ev in db.calendar_events.find({**base, "reserved_equipment_ids": equipment_id}, {"_id": 0}):
            if _overlaps(start_at, end_at, ev["start_at"], ev["end_at"]):
                conflicts.append(_conflict_entry(
                    resource_type="equipment", resource_id=equipment_id,
                    resource_name=names["equipment"].get(equipment_id),
                    event=ev, reason="equipment_reservation_overlap",
                ))
    for vehicle_id in assignments["reserved_vehicle_ids"]:
        async for ev in db.calendar_events.find({**base, "reserved_vehicle_ids": vehicle_id}, {"_id": 0}):
            if _overlaps(start_at, end_at, ev["start_at"], ev["end_at"]):
                conflicts.append(_conflict_entry(
                    resource_type="vehicle", resource_id=vehicle_id,
                    resource_name=names["vehicle"].get(vehicle_id),
                    event=ev, reason="vehicle_reservation_overlap",
                ))
    for resource_id in assignments["reserved_resource_ids"]:
        async for ev in db.calendar_events.find({**base, "reserved_resource_ids": resource_id}, {"_id": 0}):
            if _overlaps(start_at, end_at, ev["start_at"], ev["end_at"]):
                conflicts.append(_conflict_entry(
                    resource_type="resource", resource_id=resource_id,
                    resource_name=names["resource"].get(resource_id),
                    event=ev, reason="shop_resource_reservation_overlap",
                ))
    if location:
        async for ev in db.calendar_events.find({**base, "location": location}, {"_id": 0}):
            if _overlaps(start_at, end_at, ev["start_at"], ev["end_at"]):
                conflicts.append(_conflict_entry(
                    resource_type="location", resource_id=location, resource_name=location,
                    event=ev, reason="location_overlap",
                ))
    if customer_id:
        async for ev in db.calendar_events.find({**base, "customer_id": customer_id}, {"_id": 0}):
            if _overlaps(start_at, end_at, ev["start_at"], ev["end_at"]):
                conflicts.append(_conflict_entry(
                    resource_type="customer", resource_id=customer_id, resource_name=None,
                    event=ev, reason="customer_overlap",
                ))
    return conflicts


async def create_event(*, tenant_id: str, actor_user_id: str, actor_email: str, payload: dict) -> dict:
    await _validate_links(tenant_id, payload)
    assignments = _assignment_ids(payload)
    assignment_summary = await _validate_assignments(tenant_id, assignments)
    conflicts = await check_conflicts(
        tenant_id=tenant_id,
        start_at=payload["start_at"],
        end_at=payload["end_at"],
        employee_id=payload.get("employee_id"),
        **assignments,
        location=payload.get("location"),
        customer_id=payload.get("customer_id"),
    )
    override_reason = payload.get("conflict_override_reason")
    if conflicts and not override_reason:
        raise CalendarError("conflict", "Calendar conflict requires manager override reason", 409, metadata={"conflicts": conflicts})
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
        employee_id=payload.get("employee_id") or (assignments["assigned_employee_ids"][0] if assignments["assigned_employee_ids"] else None),
        assigned_employee_ids=assignments["assigned_employee_ids"],
        reserved_equipment_ids=assignments["reserved_equipment_ids"],
        reserved_vehicle_ids=assignments["reserved_vehicle_ids"],
        reserved_resource_ids=assignments["reserved_resource_ids"],
        assignment_summary=assignment_summary,
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
        summary=f"Calendar event created: {clean['title']}",
        metadata={"conflict_count": len(conflicts), "assignments": assignments},
    )
    if conflicts:
        await record_activity_with_audit(
            tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
            module="calendar", action="calendar_event.conflict_override", entity_type="calendar_event", entity_id=clean["id"],
            summary=f"Calendar conflict overridden: {clean['title']}", severity="warning",
            metadata={"conflict_count": len(conflicts), "conflicts": conflicts},
        )
    await _notify_event_assignment(tenant_id, clean, kind="calendar.assigned", title=f"Appointment assigned: {clean['title']}")
    return {**_safe_event(clean), "conflicts": conflicts}


async def list_events(*, tenant_id: str, start_at: str, end_at: str,
                      event_type: Optional[str] = None, employee_id: Optional[str] = None,
                      equipment_id: Optional[str] = None, vehicle_id: Optional[str] = None,
                      resource_id: Optional[str] = None, attention: Optional[str] = None,
                      customer_id: Optional[str] = None, order_id: Optional[str] = None,
                      work_order_id: Optional[str] = None, status: Optional[str] = None,
                      source_type: Optional[str] = None, visibility: Optional[str] = None,
                      limit: int = 200, skip: int = 0) -> dict:
    filt: dict[str, Any] = {"tenant_id": tenant_id, "archived_at": None}
    if event_type:
        filt["event_type"] = event_type
    if employee_id:
        filt["$or"] = [{"employee_id": employee_id}, {"assigned_employee_ids": employee_id}]
    if equipment_id:
        filt["reserved_equipment_ids"] = equipment_id
    if vehicle_id:
        filt["reserved_vehicle_ids"] = vehicle_id
    if resource_id:
        filt["reserved_resource_ids"] = resource_id
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
    items = [i for i in stored + projections if _feed_match(
        i, event_type=event_type, employee_id=employee_id, equipment_id=equipment_id,
        vehicle_id=vehicle_id, resource_id=resource_id, attention=attention,
        customer_id=customer_id, order_id=order_id, work_order_id=work_order_id,
        status=status, source_type=source_type, visibility=visibility,
    )]
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
            "assigned_employee_ids": [shift.get("employee_id")] if shift.get("employee_id") else [],
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
            "assigned_employee_ids": [task.get("assigned_employee_id")] if task.get("assigned_employee_id") else [],
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
            "assigned_employee_ids": [stage.get("assigned_employee_id")] if stage.get("assigned_employee_id") else [],
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
        if key == "employee_id" and value not in _clean_ids(item.get("assigned_employee_ids") or item.get("employee_id")):
            return False
        if key == "equipment_id" and value not in _clean_ids(item.get("reserved_equipment_ids")):
            return False
        if key == "vehicle_id" and value not in _clean_ids(item.get("reserved_vehicle_ids")):
            return False
        if key == "resource_id" and value not in _clean_ids(item.get("reserved_resource_ids")):
            return False
        if key == "attention" and value == "conflicts" and not item.get("conflicts"):
            return False
        if key in {"employee_id", "equipment_id", "vehicle_id", "resource_id", "attention"}:
            continue
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
    assignments = _assignment_ids(clean, existing)
    assignment_summary = await _validate_assignments(tenant_id, assignments)
    start_at = clean.get("start_at", existing["start_at"])
    end_at = clean.get("end_at", existing["end_at"])
    employee_id = clean.get("employee_id", assignments["assigned_employee_ids"][0] if assignments["assigned_employee_ids"] else None)
    location = clean.get("location", existing.get("location"))
    customer_id = clean.get("customer_id", existing.get("customer_id"))
    conflicts = await check_conflicts(
        tenant_id=tenant_id, start_at=start_at, end_at=end_at, employee_id=employee_id,
        assigned_employee_ids=assignments["assigned_employee_ids"],
        reserved_equipment_ids=assignments["reserved_equipment_ids"],
        reserved_vehicle_ids=assignments["reserved_vehicle_ids"],
        reserved_resource_ids=assignments["reserved_resource_ids"],
        location=location, customer_id=customer_id, event_id=event_id,
    )
    override_reason = clean.pop("conflict_override_reason", None)
    if conflicts and not override_reason:
        raise CalendarError("conflict", "Calendar conflict requires manager override reason", 409, metadata={"conflicts": conflicts})
    now = utc_now().isoformat()
    assignment_updates = {
        **assignments,
        "employee_id": employee_id,
        "assignment_summary": assignment_summary,
    }
    clean.update(assignment_updates)
    clean.update({"updated_at": now, "version": int(existing.get("version", 1)) + 1})
    if action == "rescheduled":
        clean["status"] = "rescheduled"
    await db.calendar_events.update_one({"tenant_id": tenant_id, "id": event_id}, {"$set": prepare_for_mongo(clean)})
    history = {"action": action, "actor_user_id": actor_user_id, "at": now}
    if "start_at" in payload or "end_at" in payload:
        history["from"] = {"start_at": existing.get("start_at"), "end_at": existing.get("end_at")}
        history["to"] = {"start_at": start_at, "end_at": end_at}
    assignment_diff = _assignment_diff(existing, assignments)
    if assignment_diff:
        history["assignment_diff"] = assignment_diff
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
        summary=f"Calendar event {action}: {updated['title']}",
        metadata={"conflict_count": len(conflicts), "assignment_diff": assignment_diff},
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
    user_ids = _clean_ids(event.get("assigned_user_id"))
    employee_ids = _clean_ids(event.get("assigned_employee_ids") or event.get("employee_id"))
    if employee_ids:
        async for emp in db.employees.find({"tenant_id": tenant_id, "id": {"$in": employee_ids}}, {"_id": 0, "linked_user_id": 1}):
            if emp.get("linked_user_id") and emp["linked_user_id"] not in user_ids:
                user_ids.append(emp["linked_user_id"])
    for user_id in user_ids:
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
        employee_ids = _clean_ids(item.get("assigned_employee_ids") or item.get("employee_id"))
        if employee_ids and employee_id not in employee_ids:
            continue
        allowed.append(item)
    return {"items": allowed, "total": len(allowed)}


async def list_schedulable_resources(*, tenant_id: str, status: Optional[str] = None,
                                     resource_type: Optional[str] = None) -> dict:
    filt: dict[str, Any] = {"tenant_id": tenant_id}
    if status:
        filt["status"] = status
    if resource_type:
        filt["resource_type"] = resource_type
    items = [serialize_doc(d) async for d in db.schedulable_resources.find(filt, {"_id": 0}).sort("name", 1)]
    return {"items": items, "total": len(items)}


async def create_schedulable_resource(*, tenant_id: str, actor_user_id: str, actor_email: str,
                                      payload: dict) -> dict:
    doc = SchedulableResource(
        tenant_id=tenant_id,
        name=payload["name"],
        resource_type=payload.get("resource_type") or "work_area",
        status=payload.get("status") or "active",
        capacity=payload.get("capacity"),
        location=payload.get("location"),
        description=payload.get("description"),
        created_by=actor_user_id,
        updated_by=actor_user_id,
    ).model_dump()
    await db.schedulable_resources.insert_one(prepare_for_mongo(dict(doc)))
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="calendar", action="schedulable_resource.created",
        entity_type="schedulable_resource", entity_id=doc["id"],
        summary=f"Schedulable resource created: {doc['name']}",
    )
    return serialize_doc(doc)


async def update_schedulable_resource(*, tenant_id: str, resource_id: str, actor_user_id: str,
                                      actor_email: str, payload: dict) -> dict:
    existing = await db.schedulable_resources.find_one({"tenant_id": tenant_id, "id": resource_id}, {"_id": 0})
    if not existing:
        raise CalendarError("not_found", "Schedulable resource not found", 404)
    updates = {k: v for k, v in payload.items() if v is not None}
    if not updates:
        raise CalendarError("no_updates", "No updates", 400)
    updates.update({"updated_at": utc_now().isoformat(), "updated_by": actor_user_id})
    await db.schedulable_resources.update_one({"tenant_id": tenant_id, "id": resource_id}, {"$set": prepare_for_mongo(updates)})
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="calendar", action="schedulable_resource.updated",
        entity_type="schedulable_resource", entity_id=resource_id,
        summary=f"Schedulable resource updated: {existing['name']}",
        diff={"before": {k: existing.get(k) for k in updates}, "after": updates},
    )
    return serialize_doc(await db.schedulable_resources.find_one({"tenant_id": tenant_id, "id": resource_id}, {"_id": 0}))


async def archive_schedulable_resource(*, tenant_id: str, resource_id: str, actor_user_id: str,
                                       actor_email: str) -> dict:
    return await update_schedulable_resource(
        tenant_id=tenant_id, resource_id=resource_id, actor_user_id=actor_user_id,
        actor_email=actor_email, payload={"status": "archived"},
    )


async def availability(*, tenant_id: str, payload: dict) -> dict:
    start_at = payload.get("start_at")
    end_at = payload.get("end_at")
    if not start_at or not end_at or _parse_dt(end_at) <= _parse_dt(start_at):
        raise CalendarError("invalid_range", "Availability end must be after start", 400)
    assignments = _assignment_ids(payload)
    await _validate_assignments(tenant_id, assignments)
    conflicts = await check_conflicts(
        tenant_id=tenant_id, start_at=start_at, end_at=end_at,
        employee_id=payload.get("employee_id"),
        assigned_employee_ids=assignments["assigned_employee_ids"],
        reserved_equipment_ids=assignments["reserved_equipment_ids"],
        reserved_vehicle_ids=assignments["reserved_vehicle_ids"],
        reserved_resource_ids=assignments["reserved_resource_ids"],
        location=payload.get("location"),
        customer_id=payload.get("customer_id"),
        event_id=payload.get("event_id"),
    )
    warnings: list[dict[str, Any]] = []
    employees = []
    employee_ids = assignments["assigned_employee_ids"]
    employee_filter: dict[str, Any] = {"tenant_id": tenant_id, "status": "active"}
    if employee_ids:
        employee_filter["id"] = {"$in": employee_ids}
    async for emp in db.employees.find(employee_filter, {"_id": 0}).sort("name", 1):
        employee_conflicts = [c for c in conflicts if c.get("resource_type") == "employee" and c.get("resource_id") == emp["id"]]
        availability_blocks = emp.get("availability_blocks") or []
        if availability_blocks:
            warnings.append({
                "resource_type": "employee",
                "resource_id": emp["id"],
                "resource_name": emp.get("name"),
                "reason": "availability_blocks_present",
                "message": "Employee has availability notes to review.",
            })
        employees.append({
            "id": emp["id"],
            "name": emp.get("name"),
            "role_label": emp.get("role_label"),
            "status": "conflicting" if employee_conflicts else "available",
            "warnings": [w for w in warnings if w.get("resource_id") == emp["id"]],
            "conflicts": employee_conflicts,
        })
    equipment = []
    equipment_filter: dict[str, Any] = {"tenant_id": tenant_id, "category": {"$ne": "vehicle"}}
    if assignments["reserved_equipment_ids"]:
        equipment_filter["id"] = {"$in": assignments["reserved_equipment_ids"]}
    async for eq in db.equipment.find(equipment_filter, {"_id": 0}).sort("name", 1):
        eq_conflicts = [c for c in conflicts if c.get("resource_type") == "equipment" and c.get("resource_id") == eq["id"]]
        status = "inactive" if eq.get("status") != "active" else ("conflicting" if eq_conflicts else "available")
        equipment.append({"id": eq["id"], "name": eq.get("name"), "category": eq.get("category"), "status": status, "conflicts": eq_conflicts})
    vehicles = []
    vehicle_filter: dict[str, Any] = {"tenant_id": tenant_id, "category": "vehicle"}
    if assignments["reserved_vehicle_ids"]:
        vehicle_filter["id"] = {"$in": assignments["reserved_vehicle_ids"]}
    async for vehicle in db.equipment.find(vehicle_filter, {"_id": 0}).sort("name", 1):
        vehicle_conflicts = [c for c in conflicts if c.get("resource_type") == "vehicle" and c.get("resource_id") == vehicle["id"]]
        status = "inactive" if vehicle.get("status") != "active" else ("conflicting" if vehicle_conflicts else "available")
        vehicles.append({"id": vehicle["id"], "name": vehicle.get("name"), "category": vehicle.get("category"), "status": status, "conflicts": vehicle_conflicts})
    resources = []
    resource_filter: dict[str, Any] = {"tenant_id": tenant_id}
    if assignments["reserved_resource_ids"]:
        resource_filter["id"] = {"$in": assignments["reserved_resource_ids"]}
    async for resource in db.schedulable_resources.find(resource_filter, {"_id": 0}).sort("name", 1):
        resource_conflicts = [c for c in conflicts if c.get("resource_type") == "resource" and c.get("resource_id") == resource["id"]]
        status = "inactive" if resource.get("status") != "active" else ("conflicting" if resource_conflicts else "available")
        resources.append({
            "id": resource["id"], "name": resource.get("name"), "resource_type": resource.get("resource_type"),
            "capacity": resource.get("capacity"), "location": resource.get("location"),
            "status": status, "conflicts": resource_conflicts,
        })
    return {
        "employees": employees,
        "equipment": equipment,
        "vehicles": vehicles,
        "resources": resources,
        "conflicts": conflicts,
        "warnings": warnings,
        "summary": {
            "available_employees": sum(1 for item in employees if item["status"] == "available"),
            "assigned_employees": len(employee_ids),
            "reserved_equipment": len(assignments["reserved_equipment_ids"]),
            "reserved_vehicles": len(assignments["reserved_vehicle_ids"]),
            "available_resources": sum(1 for item in resources if item["status"] == "available"),
            "conflict_count": len(conflicts),
            "warning_count": len(warnings),
        },
    }
