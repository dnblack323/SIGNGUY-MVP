"""EC12 Phase 12C - tenant-scoped time-off workflow service."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.time_off import TimeOffRequest
from .activity import record_activity_with_audit
from . import notifications


class TimeOffError(Exception):
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


async def _get_request(tenant_id: str, request_id: str) -> dict:
    doc = await db.time_off_requests.find_one({"tenant_id": tenant_id, "id": request_id}, {"_id": 0})
    if not doc:
        raise TimeOffError("not_found", "Time-off request not found", 404)
    return serialize_doc(doc)


async def _get_employee(tenant_id: str, employee_id: str, *, require_active: bool = False) -> dict:
    emp = await db.employees.find_one({"tenant_id": tenant_id, "id": employee_id}, {"_id": 0})
    if not emp:
        raise TimeOffError("employee_not_found", "Employee not found", 404)
    if require_active and emp.get("status") != "active":
        raise TimeOffError("inactive_employee", "Inactive employees cannot submit time-off requests", 400)
    return emp


def _public_request(doc: dict, *, include_private: bool = False, include_manager: bool = True) -> dict:
    hidden = set()
    if not include_private:
        hidden.add("private_reason")
    if not include_manager:
        hidden.update({"manager_note", "reviewed_by_user_id"})
    return {k: v for k, v in serialize_doc(doc).items() if k not in hidden}


async def _append_history(tenant_id: str, request_id: str, entry: dict) -> None:
    await db.time_off_requests.update_one(
        {"tenant_id": tenant_id, "id": request_id},
        {"$push": {"history": entry}},
    )


async def _notify_employee(tenant_id: str, request: dict, *, kind: str, title: str, body: Optional[str] = None) -> None:
    employee = await db.employees.find_one(
        {"tenant_id": tenant_id, "id": request.get("employee_id")}, {"_id": 0, "linked_user_id": 1},
    )
    if not employee or not employee.get("linked_user_id"):
        return
    try:
        await notifications.notify(
            tenant_id=tenant_id,
            recipient_user_id=employee["linked_user_id"],
            module="time_off",
            kind=kind,
            title=title,
            body=body,
            entity_type="time_off_request",
            entity_id=request["id"],
            link="/portal/employee/time-off",
        )
    except Exception:
        pass


async def _notify_managers(tenant_id: str, request: dict, *, kind: str, title: str, body: Optional[str] = None) -> None:
    try:
        await notifications.notify_tenant_owners(
            tenant_id=tenant_id,
            module="time_off",
            kind=kind,
            title=title,
            body=body,
            entity_type="time_off_request",
            entity_id=request["id"],
            link="/shop-schedule",
        )
    except Exception:
        pass


async def _shift_conflicts(tenant_id: str, employee_id: str, start_at: str, end_at: str) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    async for shift in db.shifts.find(
        {"tenant_id": tenant_id, "employee_id": employee_id, "status": {"$ne": "cancelled"}},
        {"_id": 0},
    ):
        if _overlaps(start_at, end_at, shift["start_at"], shift["end_at"]):
            conflicts.append({
                "source_type": "shift",
                "source_id": shift["id"],
                "start_at": shift["start_at"],
                "end_at": shift["end_at"],
                "title": shift.get("title"),
                "status": shift.get("status"),
            })
    return conflicts


async def list_conflicts(*, tenant_id: str, employee_id: str, start_at: str, end_at: str) -> dict:
    await _get_employee(tenant_id, employee_id)
    existing_requests = []
    async for req in db.time_off_requests.find(
        {
            "tenant_id": tenant_id,
            "employee_id": employee_id,
            "status": {"$in": ["pending", "clarification_requested", "approved"]},
        },
        {"_id": 0},
    ):
        if _overlaps(start_at, end_at, req["start_at"], req["end_at"]):
            existing_requests.append({
                "source_type": "time_off_request",
                "source_id": req["id"],
                "start_at": req["start_at"],
                "end_at": req["end_at"],
                "status": req["status"],
            })
    shifts = await _shift_conflicts(tenant_id, employee_id, start_at, end_at)
    return {"items": existing_requests + shifts}


async def create_request(*, tenant_id: str, employee_id: str, payload: dict,
                         actor_employee_id: str, actor_email: str) -> dict:
    if employee_id != actor_employee_id:
        raise TimeOffError("self_scope", "Employees may submit only their own time-off requests", 403)
    await _get_employee(tenant_id, employee_id, require_active=True)
    start_at, end_at = payload.get("start_at"), payload.get("end_at")
    if not start_at or not end_at or _parse_dt(end_at) <= _parse_dt(start_at):
        raise TimeOffError("invalid_range", "Time-off end must be after start", 400)
    conflicts = await list_conflicts(tenant_id=tenant_id, employee_id=employee_id, start_at=start_at, end_at=end_at)
    now = utc_now().isoformat()
    history = [{
        "action": "created",
        "actor_employee_id": actor_employee_id,
        "at": now,
        "conflict_count": len(conflicts["items"]),
    }]
    doc = TimeOffRequest(
        tenant_id=tenant_id,
        employee_id=employee_id,
        requested_by_employee_id=actor_employee_id,
        request_type=payload.get("request_type") or "other",
        start_at=start_at,
        end_at=end_at,
        all_day=bool(payload.get("all_day", False)),
        reason=payload.get("reason"),
        private_reason=payload.get("private_reason"),
        history=history,
    ).model_dump()
    await db.time_off_requests.insert_one(prepare_for_mongo(dict(doc)))
    clean = serialize_doc(doc)
    await record_activity_with_audit(
        tenant_id=tenant_id,
        actor_user_id=f"portal:{actor_employee_id}",
        actor_email=actor_email,
        module="team",
        action="time_off.request_created",
        entity_type="time_off_request",
        entity_id=clean["id"],
        summary="Time-off request submitted",
        metadata={"employee_id": employee_id, "start_at": start_at, "end_at": end_at, "conflict_count": len(conflicts["items"])},
    )
    await _notify_managers(tenant_id, clean, kind="time_off.submitted", title="Time-off request submitted")
    return {**_public_request(clean, include_private=True, include_manager=False), "conflicts": conflicts["items"]}


async def list_requests(*, tenant_id: str, employee_id: Optional[str] = None, status: Optional[str] = None,
                        include_private: bool = False, limit: int = 100, skip: int = 0) -> dict:
    filt: dict[str, Any] = {"tenant_id": tenant_id}
    if employee_id:
        filt["employee_id"] = employee_id
    if status:
        filt["status"] = status
    total = await db.time_off_requests.count_documents(filt)
    cursor = db.time_off_requests.find(filt, {"_id": 0}).sort("start_at", -1).skip(skip).limit(min(limit, 200))
    return {"items": [_public_request(d, include_private=include_private) async for d in cursor], "total": total, "limit": limit, "skip": skip}


async def get_request(*, tenant_id: str, request_id: str, include_private: bool = False) -> dict:
    return _public_request(await _get_request(tenant_id, request_id), include_private=include_private)


async def employee_get_request(*, tenant_id: str, employee_id: str, request_id: str) -> dict:
    doc = await _get_request(tenant_id, request_id)
    if doc.get("employee_id") != employee_id:
        raise TimeOffError("self_scope", "This request belongs to another employee", 403)
    return _public_request(doc, include_private=True, include_manager=True)


async def _manager_action(*, tenant_id: str, request_id: str, action: str, actor_user_id: str,
                          actor_email: str, note: Optional[str] = None) -> dict:
    doc = await _get_request(tenant_id, request_id)
    current = doc["status"]
    now = utc_now().isoformat()
    updates: dict[str, Any] = {"reviewed_by_user_id": actor_user_id, "updated_at": now, "version": int(doc.get("version", 1)) + 1}
    if action == "approve":
        if current == "approved":
            return _public_request(doc, include_private=True)
        if current not in {"pending", "clarification_requested"}:
            raise TimeOffError("invalid_transition", f"Cannot approve request from {current}", 400)
        updates.update({"status": "approved", "approved_at": now, "manager_note": note})
        history_action = "approved"
    elif action == "deny":
        if current == "denied":
            return _public_request(doc, include_private=True)
        if current not in {"pending", "clarification_requested"}:
            raise TimeOffError("invalid_transition", f"Cannot deny request from {current}", 400)
        if not (note and note.strip()):
            raise TimeOffError("note_required", "A denial note is required", 400)
        updates.update({"status": "denied", "denied_at": now, "manager_note": note})
        history_action = "denied"
    elif action == "clarify":
        if current == "clarification_requested":
            return _public_request(doc, include_private=True)
        if current != "pending":
            raise TimeOffError("invalid_transition", f"Cannot request clarification from {current}", 400)
        if not (note and note.strip()):
            raise TimeOffError("note_required", "A clarification note is required", 400)
        updates.update({"status": "clarification_requested", "clarification_requested_at": now, "manager_note": note})
        history_action = "clarification_requested"
    else:
        raise TimeOffError("unknown_action", "Unknown time-off action", 400)
    await db.time_off_requests.update_one({"tenant_id": tenant_id, "id": request_id}, {"$set": prepare_for_mongo(updates)})
    await _append_history(tenant_id, request_id, {"action": history_action, "actor_user_id": actor_user_id, "at": now})
    updated = await _get_request(tenant_id, request_id)
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action=f"time_off.{history_action}", entity_type="time_off_request", entity_id=request_id,
        summary=f"Time-off request {history_action}", metadata={"from": current, "to": updated["status"]},
    )
    await _notify_employee(tenant_id, updated, kind=f"time_off.{history_action}", title=f"Time-off request {history_action.replace('_', ' ')}")
    return _public_request(updated, include_private=True)


async def approve_request(**kwargs) -> dict:
    return await _manager_action(action="approve", **kwargs)


async def deny_request(**kwargs) -> dict:
    return await _manager_action(action="deny", **kwargs)


async def request_clarification(**kwargs) -> dict:
    return await _manager_action(action="clarify", **kwargs)


async def respond_to_clarification(*, tenant_id: str, request_id: str, employee_id: str,
                                   actor_email: str, response: str, private_reason: Optional[str] = None) -> dict:
    doc = await _get_request(tenant_id, request_id)
    if doc["employee_id"] != employee_id:
        raise TimeOffError("self_scope", "This request belongs to another employee", 403)
    if doc["status"] != "clarification_requested":
        raise TimeOffError("invalid_transition", "Request is not waiting for clarification", 400)
    if not response.strip():
        raise TimeOffError("response_required", "Clarification response is required", 400)
    now = utc_now().isoformat()
    updates = {"status": "pending", "reason": response, "updated_at": now, "version": int(doc.get("version", 1)) + 1}
    if private_reason is not None:
        updates["private_reason"] = private_reason
    await db.time_off_requests.update_one({"tenant_id": tenant_id, "id": request_id}, {"$set": prepare_for_mongo(updates)})
    await _append_history(tenant_id, request_id, {"action": "clarified", "actor_employee_id": employee_id, "at": now})
    updated = await _get_request(tenant_id, request_id)
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=f"portal:{employee_id}", actor_email=actor_email,
        module="team", action="time_off.clarified", entity_type="time_off_request", entity_id=request_id,
        summary="Time-off request clarified",
    )
    await _notify_managers(tenant_id, updated, kind="time_off.clarified", title="Time-off request clarified")
    return _public_request(updated, include_private=True)


async def cancel_request(*, tenant_id: str, request_id: str, employee_id: str, actor_email: str,
                         reason: Optional[str] = None) -> dict:
    doc = await _get_request(tenant_id, request_id)
    if doc["employee_id"] != employee_id:
        raise TimeOffError("self_scope", "This request belongs to another employee", 403)
    if doc["status"] == "canceled":
        return _public_request(doc, include_private=True)
    if doc["status"] == "denied":
        raise TimeOffError("invalid_transition", "Denied requests cannot be canceled", 400)
    now = utc_now().isoformat()
    await db.time_off_requests.update_one(
        {"tenant_id": tenant_id, "id": request_id},
        {"$set": {"status": "canceled", "canceled_at": now, "manager_note": doc.get("manager_note"), "updated_at": now, "version": int(doc.get("version", 1)) + 1}},
    )
    await _append_history(tenant_id, request_id, {"action": "canceled", "actor_employee_id": employee_id, "at": now, "reason": reason})
    updated = await _get_request(tenant_id, request_id)
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=f"portal:{employee_id}", actor_email=actor_email,
        module="team", action="time_off.canceled", entity_type="time_off_request", entity_id=request_id,
        summary="Time-off request canceled", metadata={"was_approved": doc["status"] == "approved"},
    )
    await _notify_managers(tenant_id, updated, kind="time_off.canceled", title="Time-off request canceled")
    return _public_request(updated, include_private=True)


async def approved_absence_overlays(*, tenant_id: str, start_at: str, end_at: str,
                                    employee_id: Optional[str] = None,
                                    include_private: bool = False) -> list[dict]:
    filt: dict[str, Any] = {"tenant_id": tenant_id, "status": "approved"}
    if employee_id:
        filt["employee_id"] = employee_id
    items = []
    async for req in db.time_off_requests.find(filt, {"_id": 0}).sort("start_at", 1):
        if not _overlaps(start_at, end_at, req["start_at"], req["end_at"]):
            continue
        title = "Approved absence"
        emp = await db.employees.find_one({"tenant_id": tenant_id, "id": req["employee_id"]}, {"_id": 0, "name": 1})
        if emp:
            title = f"{emp.get('name')} - approved absence"
        item = {
            "id": f"absence:{req['id']}",
            "source_type": "time_off_request",
            "source_id": req["id"],
            "event_type": "absence",
            "title": title,
            "start_at": req["start_at"],
            "end_at": req["end_at"],
            "all_day": req.get("all_day", False),
            "status": "approved",
            "employee_id": req["employee_id"],
            "visibility": "staff",
            "color": "amber",
            "allowed_actions": [],
        }
        if include_private:
            item["reason"] = req.get("reason")
        items.append(item)
    return items
