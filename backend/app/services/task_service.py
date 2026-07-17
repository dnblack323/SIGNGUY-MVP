"""EC12 Phase 12A - canonical shared task service."""
from __future__ import annotations

from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.task import Task, TaskComment, TaskReminderRecord
from .activity import record_activity_with_audit
from . import notifications


class TaskError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


TASK_STATUSES = {"not_started", "in_progress", "waiting", "blocked", "completed", "canceled"}
TASK_PRIORITIES = {"low", "normal", "high", "rush"}
STAFF_VISIBILITIES = {"internal", "staff", "employee"}
COMMENT_VISIBILITIES = {"internal", "employee"}

TRANSITIONS: dict[str, set[str]] = {
    "not_started": {"in_progress", "canceled"},
    "in_progress": {"waiting", "blocked", "completed", "canceled"},
    "waiting": {"in_progress", "blocked", "canceled"},
    "blocked": {"in_progress", "waiting", "canceled"},
    "completed": {"in_progress"},
    "canceled": {"in_progress"},
}

RELATION_COLLECTIONS = {
    "customer_id": "customers",
    "order_id": "orders",
    "order_item_id": "order_items",
    "work_order_id": "work_orders",
    "production_stage_id": "production_stage_instances",
}

SOURCE_TYPE_TO_FIELD = {
    "customer": "customer_id",
    "order": "order_id",
    "order_item": "order_item_id",
    "work_order": "work_order_id",
    "production_stage": "production_stage_id",
    "employee": "assigned_employee_id",
    "user": "assigned_user_id",
}

MUTABLE_FIELDS = {
    "title", "description", "priority", "task_type", "source_type", "source_id",
    "customer_id", "order_id", "order_item_id", "work_order_id", "production_stage_id",
    "due_at", "start_at", "visibility", "employee_visible", "internal_only",
}


def _now() -> str:
    return utc_now().isoformat()


def _query(tenant_id: str, task_id: str) -> dict[str, Any]:
    return {"tenant_id": tenant_id, "id": task_id}


def _clean_task(doc: dict | None) -> dict | None:
    return serialize_doc(doc) if doc else None


def _public_employee_task(doc: dict) -> dict:
    allowed = {
        "id", "title", "description", "status", "priority", "task_type",
        "source_type", "source_id", "customer_id", "order_id", "order_item_id",
        "work_order_id", "production_stage_id", "assigned_employee_id", "due_at",
        "start_at", "completed_at", "employee_visible", "created_at", "updated_at",
    }
    out = {k: doc.get(k) for k in allowed if k in doc}
    out["allowed_actions"] = _employee_actions(doc)
    return out


def _employee_actions(doc: dict) -> list[str]:
    status = doc.get("status")
    actions: list[str] = []
    if status == "not_started":
        actions.append("start")
    if status in {"in_progress", "waiting", "blocked"}:
        if status != "in_progress":
            actions.append("resume")
        if status != "waiting":
            actions.append("wait")
        if status != "blocked":
            actions.append("block")
        if status == "in_progress":
            actions.append("complete")
    return actions


async def _get_task(tenant_id: str, task_id: str, *, include_archived: bool = False) -> dict:
    q = _query(tenant_id, task_id)
    if not include_archived:
        q["archived_at"] = None
    doc = await db.tasks.find_one(q, {"_id": 0})
    if not doc:
        raise TaskError("task_not_found", "Task not found", 404)
    return doc


async def _require_user(tenant_id: str, user_id: str) -> dict:
    doc = await db.users.find_one({"tenant_id": tenant_id, "id": user_id, "is_active": True}, {"_id": 0})
    if not doc:
        raise TaskError("assignee_user_not_found", "Assigned user is not active in this tenant", 404)
    return doc


async def _require_employee(tenant_id: str, employee_id: str) -> dict:
    doc = await db.employees.find_one({"tenant_id": tenant_id, "id": employee_id, "status": "active"}, {"_id": 0})
    if not doc:
        raise TaskError("assignee_employee_not_found", "Assigned employee is not active in this tenant", 404)
    return doc


async def _validate_assignments(tenant_id: str, payload: dict) -> tuple[Optional[dict], Optional[dict]]:
    user = None
    employee = None
    if payload.get("assigned_user_id"):
        user = await _require_user(tenant_id, payload["assigned_user_id"])
    if payload.get("assigned_employee_id"):
        employee = await _require_employee(tenant_id, payload["assigned_employee_id"])
    if user and employee and employee.get("linked_user_id") != user["id"]:
        raise TaskError("unsafe_dual_assignment", "A task may be assigned to both user and employee only when they are linked", 400)
    return user, employee


async def _require_relation(tenant_id: str, field: str, record_id: str) -> dict:
    coll = RELATION_COLLECTIONS[field]
    doc = await db[coll].find_one({"tenant_id": tenant_id, "id": record_id}, {"_id": 0})
    if not doc:
        raise TaskError("linked_record_not_found", f"{field} does not belong to this tenant", 404)
    return doc


async def validate_linked_records(tenant_id: str, payload: dict) -> dict[str, dict]:
    refs: dict[str, dict] = {}
    source_type = payload.get("source_type")
    source_id = payload.get("source_id")
    if source_type or source_id:
        if not (source_type and source_id):
            raise TaskError("invalid_source", "source_type and source_id must be provided together", 400)
        field = SOURCE_TYPE_TO_FIELD.get(source_type)
        if not field:
            raise TaskError("unsupported_source_type", f"Unsupported task source_type: {source_type}", 400)
        if field in RELATION_COLLECTIONS:
            payload.setdefault(field, source_id)

    for field in RELATION_COLLECTIONS:
        record_id = payload.get(field)
        if record_id:
            refs[field] = await _require_relation(tenant_id, field, record_id)

    if refs.get("order_item_id") and payload.get("order_id") and refs["order_item_id"].get("order_id") != payload["order_id"]:
        raise TaskError("link_mismatch", "order_item_id does not belong to order_id", 400)
    if refs.get("work_order_id") and payload.get("order_id") and refs["work_order_id"].get("order_id") != payload["order_id"]:
        raise TaskError("link_mismatch", "work_order_id does not belong to order_id", 400)
    if refs.get("production_stage_id"):
        stage = refs["production_stage_id"]
        for field in ("order_id", "order_item_id", "work_order_id"):
            if payload.get(field) and stage.get(field) != payload[field]:
                raise TaskError("link_mismatch", f"production_stage_id does not belong to {field}", 400)
    return refs


def _normalize_payload(payload: dict) -> dict:
    out = {k: v for k, v in payload.items() if v is not None}
    if "title" in out:
        out["title"] = str(out["title"]).strip()
        if not out["title"]:
            raise TaskError("title_required", "Task title is required", 400)
    if "status" in out and out["status"] not in TASK_STATUSES:
        raise TaskError("invalid_status", "Invalid task status", 400)
    if "priority" in out and out["priority"] not in TASK_PRIORITIES:
        raise TaskError("invalid_priority", "Invalid task priority", 400)
    if "visibility" in out and out["visibility"] not in STAFF_VISIBILITIES:
        raise TaskError("invalid_visibility", "Invalid task visibility", 400)
    if out.get("employee_visible"):
        out["visibility"] = "employee"
        out["internal_only"] = False
    if out.get("visibility") != "employee":
        out["employee_visible"] = False
    if out.get("internal_only"):
        out["employee_visible"] = False
        out["visibility"] = "internal"
    return out


async def create_task(*, tenant_id: str, actor_user_id: str, actor_email: str, payload: dict) -> dict:
    data = _normalize_payload(payload)
    if data.get("idempotency_key"):
        existing = await db.tasks.find_one({"tenant_id": tenant_id, "idempotency_key": data["idempotency_key"]}, {"_id": 0})
        if existing:
            return _clean_task(existing) or {}
    await validate_linked_records(tenant_id, data)
    await _validate_assignments(tenant_id, data)
    task = Task(
        tenant_id=tenant_id,
        title=data["title"],
        created_by_user_id=actor_user_id,
        **{k: v for k, v in data.items() if k != "title"},
    )
    doc = prepare_for_mongo(task.model_dump())
    try:
        await db.tasks.insert_one(doc)
    except DuplicateKeyError:
        if data.get("idempotency_key"):
            existing = await db.tasks.find_one({"tenant_id": tenant_id, "idempotency_key": data["idempotency_key"]}, {"_id": 0})
            if existing:
                return _clean_task(existing) or {}
        raise
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="tasks", action="task.created", entity_type="task", entity_id=task.id,
        summary=f"Task created: {task.title}",
        metadata={"status": task.status, "priority": task.priority},
    )
    await _best_effort_assignment_notify(tenant_id, task.model_dump(), actor_user_id=actor_user_id)
    return _clean_task(doc) or {}


async def list_tasks(
    *,
    tenant_id: str,
    status: Optional[str] = None,
    assigned_user_id: Optional[str] = None,
    assigned_employee_id: Optional[str] = None,
    priority: Optional[str] = None,
    task_type: Optional[str] = None,
    customer_id: Optional[str] = None,
    order_id: Optional[str] = None,
    work_order_id: Optional[str] = None,
    due_from: Optional[str] = None,
    due_to: Optional[str] = None,
    q: Optional[str] = None,
    include_archived: bool = False,
    limit: int = 100,
    skip: int = 0,
) -> dict:
    filt: dict[str, Any] = {"tenant_id": tenant_id}
    if not include_archived:
        filt["archived_at"] = None
    if status:
        filt["status"] = status
    if assigned_user_id:
        filt["assigned_user_id"] = assigned_user_id
    if assigned_employee_id:
        filt["assigned_employee_id"] = assigned_employee_id
    if priority:
        filt["priority"] = priority
    if task_type:
        filt["task_type"] = task_type
    if customer_id:
        filt["customer_id"] = customer_id
    if order_id:
        filt["order_id"] = order_id
    if work_order_id:
        filt["work_order_id"] = work_order_id
    if due_from or due_to:
        due_filter: dict[str, Any] = {}
        if due_from:
            due_filter["$gte"] = due_from
        if due_to:
            due_filter["$lte"] = due_to
        filt["due_at"] = due_filter
    if q:
        filt["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
        ]
    total = await db.tasks.count_documents(filt)
    cursor = db.tasks.find(filt, {"_id": 0}).sort([("due_at", 1), ("created_at", -1)]).skip(skip).limit(min(limit, 200))
    return {"items": [_clean_task(d) async for d in cursor], "total": total, "limit": min(limit, 200), "skip": skip}


async def get_task(*, tenant_id: str, task_id: str, include_archived: bool = False) -> dict:
    return _clean_task(await _get_task(tenant_id, task_id, include_archived=include_archived)) or {}


async def update_task(*, tenant_id: str, task_id: str, actor_user_id: str, actor_email: str, updates: dict) -> dict:
    existing = await _get_task(tenant_id, task_id, include_archived=True)
    data = _normalize_payload({k: v for k, v in updates.items() if k in MUTABLE_FIELDS and v is not None})
    if not data:
        raise TaskError("no_updates", "No allowed task updates provided", 400)
    merged = {**existing, **data}
    await validate_linked_records(tenant_id, merged)
    set_doc = {**data, "updated_at": _now(), "version": int(existing.get("version", 1)) + 1}
    await db.tasks.update_one(_query(tenant_id, task_id), {"$set": set_doc})
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="tasks", action="task.updated", entity_type="task", entity_id=task_id,
        summary=f"Task updated: {existing.get('title')}",
        diff={"before": {k: existing.get(k) for k in data}, "after": data},
    )
    return await get_task(tenant_id=tenant_id, task_id=task_id, include_archived=True)


async def assign_task(
    *,
    tenant_id: str,
    task_id: str,
    actor_user_id: str,
    actor_email: str,
    assigned_user_id: Optional[str] = None,
    assigned_employee_id: Optional[str] = None,
) -> dict:
    existing = await _get_task(tenant_id, task_id, include_archived=True)
    data = {"assigned_user_id": assigned_user_id, "assigned_employee_id": assigned_employee_id}
    await _validate_assignments(tenant_id, data)
    now = _now()
    history = {
        "from_user_id": existing.get("assigned_user_id"),
        "to_user_id": assigned_user_id,
        "from_employee_id": existing.get("assigned_employee_id"),
        "to_employee_id": assigned_employee_id,
        "actor_user_id": actor_user_id,
        "at": now,
    }
    await db.tasks.update_one(
        _query(tenant_id, task_id),
        {"$set": {**data, "updated_at": now, "version": int(existing.get("version", 1)) + 1}, "$push": {"assignment_history": history}},
    )
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="tasks", action="task.assignment_changed", entity_type="task", entity_id=task_id,
        summary=f"Task reassigned: {existing.get('title')}",
        diff={"before": {"assigned_user_id": existing.get("assigned_user_id"), "assigned_employee_id": existing.get("assigned_employee_id")}, "after": data},
    )
    updated = await get_task(tenant_id=tenant_id, task_id=task_id, include_archived=True)
    await _best_effort_assignment_notify(tenant_id, updated, actor_user_id=actor_user_id)
    return updated


async def transition_task(
    *,
    tenant_id: str,
    task_id: str,
    target: str,
    actor_user_id: str,
    actor_email: str,
    actor_employee_id: Optional[str] = None,
    reason: Optional[str] = None,
    allow_employee: bool = False,
    allow_reopen: bool = False,
) -> dict:
    if target not in TASK_STATUSES:
        raise TaskError("invalid_status", "Invalid task status", 400)
    existing = await _get_task(tenant_id, task_id)
    if allow_employee and existing.get("assigned_employee_id") != actor_employee_id:
        raise TaskError("employee_scope_denied", "Task is not assigned to this employee", 403)
    current = existing["status"]
    if current == target and target == "completed":
        return _clean_task(existing) or {}
    if current in {"completed", "canceled"} and target == "in_progress" and not allow_reopen:
        raise TaskError("reopen_action_required", "Completed or canceled tasks must be reopened through the reopen action", 400)
    if target not in TRANSITIONS.get(current, set()):
        raise TaskError("invalid_transition", f"Cannot transition task from {current} to {target}", 400)
    now = _now()
    set_doc: dict[str, Any] = {"status": target, "updated_at": now, "version": int(existing.get("version", 1)) + 1}
    if target == "in_progress" and current == "not_started":
        set_doc["start_at"] = existing.get("start_at") or now
    if target == "waiting":
        set_doc["waiting_reason"] = reason
    if target == "blocked":
        set_doc["block_reason"] = reason
    if target == "canceled":
        set_doc["cancel_reason"] = reason
    if target == "completed":
        set_doc.update({
            "completed_at": existing.get("completed_at") or now,
            "completed_by_user_id": None if actor_user_id.startswith("portal:") else actor_user_id,
            "completed_by_employee_id": actor_employee_id,
        })
    if current in {"completed", "canceled"} and target == "in_progress":
        set_doc.update({"completed_at": None, "completed_by_user_id": None, "completed_by_employee_id": None, "reopen_reason": reason})
    history = {"from": current, "to": target, "actor_user_id": actor_user_id, "actor_employee_id": actor_employee_id, "reason": reason, "at": now}
    update: dict[str, Any] = {"$set": set_doc, "$push": {"status_history": history}}
    if target == "completed":
        update["$push"]["completion_history"] = {
            "completed_at": set_doc["completed_at"],
            "completed_by_user_id": set_doc["completed_by_user_id"],
            "completed_by_employee_id": actor_employee_id,
            "at": now,
        }
    await db.tasks.update_one(_query(tenant_id, task_id), update)
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="tasks", action=f"task.{_action_for_status(target, current)}", entity_type="task", entity_id=task_id,
        summary=f"Task status changed: {existing.get('title')} ({current} -> {target})",
        metadata={"from": current, "to": target},
    )
    updated = await get_task(tenant_id=tenant_id, task_id=task_id)
    await _best_effort_status_notify(tenant_id, updated, target=target, actor_user_id=actor_user_id)
    return updated


def _action_for_status(target: str, previous: str) -> str:
    if target == "in_progress" and previous in {"completed", "canceled"}:
        return "reopened"
    return {
        "in_progress": "started",
        "waiting": "waiting",
        "blocked": "blocked",
        "completed": "completed",
        "canceled": "canceled",
    }.get(target, "status_changed")


async def archive_task(*, tenant_id: str, task_id: str, actor_user_id: str, actor_email: str) -> dict:
    existing = await _get_task(tenant_id, task_id, include_archived=True)
    if existing.get("archived_at"):
        return _clean_task(existing) or {}
    now = _now()
    await db.tasks.update_one(_query(tenant_id, task_id), {"$set": {"archived_at": now, "updated_at": now, "version": int(existing.get("version", 1)) + 1}})
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="tasks", action="task.archived", entity_type="task", entity_id=task_id,
        summary=f"Task archived: {existing.get('title')}",
    )
    return await get_task(tenant_id=tenant_id, task_id=task_id, include_archived=True)


async def restore_task(*, tenant_id: str, task_id: str, actor_user_id: str, actor_email: str) -> dict:
    existing = await _get_task(tenant_id, task_id, include_archived=True)
    now = _now()
    await db.tasks.update_one(_query(tenant_id, task_id), {"$set": {"archived_at": None, "updated_at": now, "version": int(existing.get("version", 1)) + 1}})
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="tasks", action="task.restored", entity_type="task", entity_id=task_id,
        summary=f"Task restored: {existing.get('title')}",
    )
    return await get_task(tenant_id=tenant_id, task_id=task_id, include_archived=True)


async def add_comment(
    *,
    tenant_id: str,
    task_id: str,
    actor_user_id: Optional[str],
    actor_email: str,
    author_employee_id: Optional[str] = None,
    body: str,
    visibility: str = "internal",
    employee_scope: bool = False,
) -> dict:
    task = await _get_task(tenant_id, task_id)
    if employee_scope:
        if task.get("assigned_employee_id") != author_employee_id or not task.get("employee_visible"):
            raise TaskError("employee_scope_denied", "Task is not visible to this employee", 403)
        visibility = "employee"
    if visibility not in COMMENT_VISIBILITIES:
        raise TaskError("invalid_comment_visibility", "Invalid comment visibility", 400)
    clean_body = str(body or "").strip()
    if not clean_body:
        raise TaskError("comment_body_required", "Comment body is required", 400)
    comment = TaskComment(
        tenant_id=tenant_id, task_id=task_id, author_user_id=actor_user_id,
        author_employee_id=author_employee_id, body=clean_body, visibility=visibility,  # type: ignore[arg-type]
    )
    doc = prepare_for_mongo(comment.model_dump())
    await db.task_comments.insert_one(doc)
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id or f"employee:{author_employee_id}", actor_email=actor_email,
        module="tasks", action="task.comment_added", entity_type="task", entity_id=task_id,
        summary=f"Comment added to task: {task.get('title')}",
        metadata={"comment_id": comment.id, "visibility": visibility},
    )
    return serialize_doc(doc) or {}


async def edit_comment(
    *,
    tenant_id: str,
    task_id: str,
    comment_id: str,
    actor_user_id: str,
    actor_email: str,
    body: str,
) -> dict:
    await _get_task(tenant_id, task_id, include_archived=True)
    existing = await db.task_comments.find_one({"tenant_id": tenant_id, "task_id": task_id, "id": comment_id}, {"_id": 0})
    if not existing:
        raise TaskError("comment_not_found", "Comment not found", 404)
    clean_body = str(body or "").strip()
    if not clean_body:
        raise TaskError("comment_body_required", "Comment body is required", 400)
    now = _now()
    await db.task_comments.update_one(
        {"tenant_id": tenant_id, "task_id": task_id, "id": comment_id},
        {"$set": {"body": clean_body, "edited_at": now, "updated_at": now}},
    )
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="tasks", action="task.comment_edited", entity_type="task", entity_id=task_id,
        summary="Task comment edited",
        metadata={"comment_id": comment_id},
    )
    doc = await db.task_comments.find_one({"tenant_id": tenant_id, "task_id": task_id, "id": comment_id}, {"_id": 0})
    return serialize_doc(doc) or {}


async def list_comments(*, tenant_id: str, task_id: str, employee_visible_only: bool = False) -> list[dict]:
    await _get_task(tenant_id, task_id, include_archived=True)
    q: dict[str, Any] = {"tenant_id": tenant_id, "task_id": task_id, "archived_at": None}
    if employee_visible_only:
        q["visibility"] = "employee"
    cursor = db.task_comments.find(q, {"_id": 0}).sort("created_at", 1)
    return [serialize_doc(d) async for d in cursor]


async def update_reminder_policy(*, tenant_id: str, task_id: str, actor_user_id: str, actor_email: str, reminder_policy: dict) -> dict:
    existing = await _get_task(tenant_id, task_id)
    now = _now()
    await db.tasks.update_one(
        _query(tenant_id, task_id),
        {"$set": {"reminder_policy": reminder_policy or {}, "updated_at": now, "version": int(existing.get("version", 1)) + 1}},
    )
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="tasks", action="task.reminder_policy_changed", entity_type="task", entity_id=task_id,
        summary=f"Reminder policy changed for task: {existing.get('title')}",
        metadata={"keys": sorted((reminder_policy or {}).keys())},
    )
    return await get_task(tenant_id=tenant_id, task_id=task_id)


async def generate_reminder(*, tenant_id: str, task_id: str, reminder_kind: str, actor_user_id: str, actor_email: str) -> dict:
    if reminder_kind not in {"due", "overdue"}:
        raise TaskError("invalid_reminder_kind", "Invalid reminder kind", 400)
    task = await _get_task(tenant_id, task_id)
    policy_key = str(task.get("due_at") or "no_due_at")
    existing = await db.task_reminders.find_one(
        {"tenant_id": tenant_id, "task_id": task_id, "reminder_kind": reminder_kind, "policy_key": policy_key}, {"_id": 0}
    )
    if existing:
        return {"created": False, "reminder": serialize_doc(existing)}
    record = TaskReminderRecord(tenant_id=tenant_id, task_id=task_id, reminder_kind=reminder_kind, policy_key=policy_key, sent_at=_now())
    doc = prepare_for_mongo(record.model_dump())
    try:
        await db.task_reminders.insert_one(doc)
    except DuplicateKeyError:
        existing = await db.task_reminders.find_one(
            {"tenant_id": tenant_id, "task_id": task_id, "reminder_kind": reminder_kind, "policy_key": policy_key}, {"_id": 0}
        )
        return {"created": False, "reminder": serialize_doc(existing)}
    error = await _best_effort_task_notify(
        tenant_id, task, kind=f"task.{reminder_kind}_reminder",
        title=f"Task {reminder_kind}: {task['title']}", body=f"Due: {task.get('due_at') or 'not set'}",
    )
    if error:
        await db.task_reminders.update_one({"id": record.id, "tenant_id": tenant_id}, {"$set": {"notification_error": error}})
        doc["notification_error"] = error
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="tasks", action=f"task.{reminder_kind}_reminder_generated", entity_type="task", entity_id=task_id,
        summary=f"{reminder_kind.title()} reminder generated for task: {task.get('title')}",
        metadata={"reminder_id": record.id},
    )
    return {"created": True, "reminder": serialize_doc(doc)}


async def list_employee_tasks(*, tenant_id: str, employee_id: str, status: Optional[str] = None) -> dict:
    filt: dict[str, Any] = {
        "tenant_id": tenant_id,
        "assigned_employee_id": employee_id,
        "employee_visible": True,
        "archived_at": None,
    }
    if status:
        filt["status"] = status
    cursor = db.tasks.find(filt, {"_id": 0}).sort([("due_at", 1), ("created_at", -1)])
    items = [_public_employee_task(d) async for d in cursor]
    return {"available": True, "items": items, "total": len(items)}


async def get_employee_task(*, tenant_id: str, employee_id: str, task_id: str) -> dict:
    task = await _get_task(tenant_id, task_id)
    if task.get("assigned_employee_id") != employee_id or not task.get("employee_visible"):
        raise TaskError("employee_scope_denied", "Task is not visible to this employee", 403)
    return _public_employee_task(task)


async def _best_effort_assignment_notify(tenant_id: str, task: dict, *, actor_user_id: str) -> None:
    await _best_effort_task_notify(
        tenant_id, task, kind="task.assigned", title=f"Task assigned: {task.get('title')}",
        body=task.get("description"),
        skip_user_id=actor_user_id,
    )


async def _best_effort_status_notify(tenant_id: str, task: dict, *, target: str, actor_user_id: str) -> None:
    await _best_effort_task_notify(
        tenant_id, task, kind=f"task.{target}", title=f"Task {target.replace('_', ' ')}: {task.get('title')}",
        body=task.get("description"),
        skip_user_id=actor_user_id,
    )


async def _best_effort_task_notify(
    tenant_id: str,
    task: dict,
    *,
    kind: str,
    title: str,
    body: Optional[str] = None,
    skip_user_id: Optional[str] = None,
) -> Optional[str]:
    recipient_ids = []
    if task.get("assigned_user_id"):
        recipient_ids.append(task["assigned_user_id"])
    if task.get("assigned_employee_id"):
        emp = await db.employees.find_one({"tenant_id": tenant_id, "id": task["assigned_employee_id"]}, {"_id": 0, "linked_user_id": 1})
        if emp and emp.get("linked_user_id"):
            recipient_ids.append(emp["linked_user_id"])
    unique = [rid for rid in dict.fromkeys(recipient_ids) if rid and rid != skip_user_id]
    try:
        for rid in unique:
            await notifications.notify(
                tenant_id=tenant_id, recipient_user_id=rid, module="tasks", kind=kind,
                title=title, body=body, entity_type="task", entity_id=task.get("id"),
                link=f"/team/tasks?task={task.get('id')}",
            )
    except Exception as exc:  # notification failure must never roll back task state
        return str(exc)
    return None
