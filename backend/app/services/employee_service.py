"""EC8 phase 8a — Employee service (single authoritative Employee model).

Router calls this; router never touches `db.employees` directly for
mutations so every write is guaranteed to go through the same audit path.
"""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.employee import Employee
from .activity import record_activity_with_audit


class EmployeeError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def _assert_linked_user_available(tenant_id: str, linked_user_id: str, exclude_employee_id: Optional[str] = None) -> None:
    user = await db.users.find_one({"id": linked_user_id, "tenant_id": tenant_id})
    if not user:
        raise EmployeeError(404, "linked_user_id does not belong to this tenant")
    q: dict[str, Any] = {"tenant_id": tenant_id, "linked_user_id": linked_user_id}
    if exclude_employee_id:
        q["id"] = {"$ne": exclude_employee_id}
    existing = await db.employees.find_one(q, {"_id": 0, "id": 1})
    if existing:
        raise EmployeeError(409, "That user is already linked to another employee record")


async def create_employee(*, tenant_id: str, actor_user_id: str, actor_email: str, payload: dict) -> dict:
    if payload.get("linked_user_id"):
        await _assert_linked_user_available(tenant_id, payload["linked_user_id"])
    doc = Employee(tenant_id=tenant_id, **payload).model_dump()
    await db.employees.insert_one(prepare_for_mongo(dict(doc)))
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="employee.create", entity_type="employee", entity_id=doc["id"],
        summary=f"Employee '{doc['name']}' created",
    )
    doc.pop("_id", None)
    return serialize_doc(doc)


async def list_employees(*, tenant_id: str, status: Optional[str] = None, q: Optional[str] = None) -> list[dict]:
    filt: dict[str, Any] = {"tenant_id": tenant_id}
    if status:
        filt["status"] = status
    if q:
        filt["$or"] = [{"name": {"$regex": q, "$options": "i"}},
                       {"email": {"$regex": q, "$options": "i"}}]
    cur = db.employees.find(filt, {"_id": 0}).sort("name", 1)
    return [serialize_doc(d) async for d in cur]


async def get_employee(*, tenant_id: str, employee_id: str) -> dict:
    doc = await db.employees.find_one({"id": employee_id, "tenant_id": tenant_id}, {"_id": 0})
    if not doc:
        raise EmployeeError(404, "Employee not found")
    return serialize_doc(doc)


async def get_employee_by_linked_user(*, tenant_id: str, user_id: str) -> Optional[dict]:
    doc = await db.employees.find_one({"tenant_id": tenant_id, "linked_user_id": user_id}, {"_id": 0})
    return serialize_doc(doc) if doc else None


async def update_employee(*, tenant_id: str, employee_id: str, actor_user_id: str, actor_email: str, payload: dict) -> dict:
    existing = await db.employees.find_one({"id": employee_id, "tenant_id": tenant_id}, {"_id": 0})
    if not existing:
        raise EmployeeError(404, "Employee not found")
    upd = {k: v for k, v in payload.items() if v is not None}
    if "linked_user_id" in upd and upd["linked_user_id"] != existing.get("linked_user_id"):
        if upd["linked_user_id"]:
            await _assert_linked_user_available(tenant_id, upd["linked_user_id"], exclude_employee_id=employee_id)
    upd["updated_at"] = utc_now().isoformat()
    await db.employees.update_one({"id": employee_id, "tenant_id": tenant_id}, {"$set": upd})
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="employee.update", entity_type="employee", entity_id=employee_id,
        summary=f"Employee '{existing['name']}' updated", diff={"before": existing, "after": upd},
    )
    doc = await db.employees.find_one({"id": employee_id, "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})


VALID_STATUSES = {"active", "suspended", "inactive", "terminated", "archived"}


async def change_status(*, tenant_id: str, employee_id: str, actor_user_id: str, actor_email: str,
                         new_status: str, reason: str) -> dict:
    if new_status not in VALID_STATUSES:
        raise EmployeeError(400, f"Invalid status: {new_status}")
    existing = await db.employees.find_one({"id": employee_id, "tenant_id": tenant_id}, {"_id": 0})
    if not existing:
        raise EmployeeError(404, "Employee not found")
    if existing["status"] == new_status:
        raise EmployeeError(400, "Employee already has that status")
    now = utc_now().isoformat()
    history_entry = {"from": existing["status"], "to": new_status, "reason": reason,
                      "actor_user_id": actor_user_id, "at": now}
    upd: dict[str, Any] = {"status": new_status, "updated_at": now}
    if new_status == "terminated" and not existing.get("termination_date"):
        upd["termination_date"] = now[:10]
    await db.employees.update_one(
        {"id": employee_id, "tenant_id": tenant_id},
        {"$set": upd, "$push": {"status_history": history_entry}},
    )
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="employee.status_change", entity_type="employee", entity_id=employee_id,
        summary=f"Employee '{existing['name']}' status: {existing['status']} -> {new_status} ({reason})",
        severity="warning" if new_status in {"terminated", "suspended"} else "info",
    )
    doc = await db.employees.find_one({"id": employee_id, "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})


async def status_counts(*, tenant_id: str) -> dict[str, int]:
    counts: dict[str, int] = {s: 0 for s in VALID_STATUSES}
    cursor = db.employees.aggregate([
        {"$match": {"tenant_id": tenant_id}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ])
    async for row in cursor:
        counts[row["_id"]] = row["count"]
    return counts


# ---- EC8 phase 8c — Employee availability (structured; feeds Schedule conflict warnings) ----

VALID_AVAILABILITY_KINDS = {"unavailable", "preferred"}


async def add_availability_block(*, tenant_id: str, employee_id: str, actor_user_id: str, actor_email: str,
                                  block: dict) -> dict:
    import uuid
    if block.get("kind") not in VALID_AVAILABILITY_KINDS:
        raise EmployeeError(400, f"kind must be one of {sorted(VALID_AVAILABILITY_KINDS)}")
    existing = await db.employees.find_one({"id": employee_id, "tenant_id": tenant_id}, {"_id": 0})
    if not existing:
        raise EmployeeError(404, "Employee not found")
    entry = {
        "id": str(uuid.uuid4()),
        "kind": block["kind"],
        "day_of_week": block.get("day_of_week"),
        "date_from": block.get("date_from"),
        "date_to": block.get("date_to"),
        "start_time": block.get("start_time"),
        "end_time": block.get("end_time"),
        "note": block.get("note"),
        "created_at": utc_now().isoformat(),
        "created_by": actor_user_id,
    }
    await db.employees.update_one(
        {"id": employee_id, "tenant_id": tenant_id},
        {"$push": {"availability_blocks": entry}, "$set": {"updated_at": utc_now().isoformat()}},
    )
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="employee.availability_added", entity_type="employee", entity_id=employee_id,
        summary=f"Availability block added for '{existing['name']}' ({entry['kind']})",
    )
    doc = await db.employees.find_one({"id": employee_id, "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})


async def remove_availability_block(*, tenant_id: str, employee_id: str, block_id: str,
                                     actor_user_id: str, actor_email: str) -> dict:
    existing = await db.employees.find_one({"id": employee_id, "tenant_id": tenant_id}, {"_id": 0})
    if not existing:
        raise EmployeeError(404, "Employee not found")
    await db.employees.update_one(
        {"id": employee_id, "tenant_id": tenant_id},
        {"$pull": {"availability_blocks": {"id": block_id}}, "$set": {"updated_at": utc_now().isoformat()}},
    )
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="employee.availability_removed", entity_type="employee", entity_id=employee_id,
        summary=f"Availability block removed for '{existing['name']}'",
    )
    doc = await db.employees.find_one({"id": employee_id, "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})
