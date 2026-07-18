"""EC12 Phase 12E - shared communication, notes, preferences, and digest service."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.communication import CommunicationPreference, DailyDigest, InternalNote, MessageReadState, MessageThread, ThreadMessage
from .activity import record_activity_with_audit
from . import notifications


class CommunicationError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


THREAD_TYPES = {
    "direct", "group", "team", "task_discussion", "order_discussion",
    "work_order_discussion", "production_discussion", "appointment_discussion",
    "announcement_discussion",
}
THREAD_VISIBILITIES = {"internal", "employee_visible"}
NOTE_VISIBILITIES = {"internal", "employee_visible", "private_to_author", "manager_only"}
LINK_COLLECTIONS = {
    "customer_id": "customers",
    "order_id": "orders",
    "order_item_id": "order_items",
    "work_order_id": "work_orders",
    "production_stage_id": "production_stage_instances",
    "task_id": "tasks",
    "calendar_event_id": "calendar_events",
    "announcement_id": "announcements",
    "employee_id": "employees",
}
THREAD_LINK_BY_TYPE = {
    "task_discussion": "task_id",
    "order_discussion": "order_id",
    "work_order_discussion": "work_order_id",
    "production_discussion": "production_stage_id",
    "appointment_discussion": "calendar_event_id",
    "announcement_discussion": "announcement_id",
}
STAFF_DIGEST_STATUSES = {"not_started", "in_progress", "waiting", "blocked"}


def _now() -> str:
    return utc_now().isoformat()


def _digest_day(value: str) -> date:
    text = str(value or "").strip()
    if not text:
        return utc_now().date()
    if "T" in text:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    return date.fromisoformat(text[:10])


def _actor_user(user: dict) -> tuple[str, str]:
    return user["id"], user.get("email") or "staff"


def _identity_key(*, user_id: Optional[str] = None, employee_id: Optional[str] = None) -> tuple[str, str]:
    if user_id:
        return "user", user_id
    if employee_id:
        return "employee", employee_id
    raise CommunicationError("identity_required", "A user or employee identity is required", 400)


def _thread_public(doc: dict, *, identity_type: str, identity_id: str) -> dict:
    out = serialize_doc(doc)
    return out or {}


async def _require_user(tenant_id: str, user_id: str) -> dict:
    doc = await db.users.find_one({"tenant_id": tenant_id, "id": user_id, "is_active": True}, {"_id": 0})
    if not doc:
        raise CommunicationError("participant_user_not_found", "Participant user is not active in this tenant", 404)
    return doc


async def _require_employee(tenant_id: str, employee_id: str) -> dict:
    doc = await db.employees.find_one({"tenant_id": tenant_id, "id": employee_id, "status": "active"}, {"_id": 0})
    if not doc:
        raise CommunicationError("participant_employee_not_found", "Participant employee is not active in this tenant", 404)
    return doc


async def _validate_participants(tenant_id: str, payload: dict) -> None:
    seen_users = set(payload.get("participant_user_ids") or [])
    seen_employees = set(payload.get("participant_employee_ids") or [])
    for uid in seen_users:
        await _require_user(tenant_id, uid)
    for eid in seen_employees:
        await _require_employee(tenant_id, eid)
    payload["participant_user_ids"] = sorted(seen_users)
    payload["participant_employee_ids"] = sorted(seen_employees)


async def _require_link(tenant_id: str, field: str, record_id: str) -> dict:
    coll = LINK_COLLECTIONS[field]
    doc = await db[coll].find_one({"tenant_id": tenant_id, "id": record_id}, {"_id": 0})
    if not doc:
        raise CommunicationError("linked_record_not_found", f"{field} does not belong to this tenant", 404)
    return doc


async def _validate_links(tenant_id: str, payload: dict, *, for_note: bool = False) -> dict[str, dict]:
    refs: dict[str, dict] = {}
    for field in LINK_COLLECTIONS:
        if field == "employee_id" and not for_note:
            continue
        record_id = payload.get(field)
        if record_id:
            refs[field] = await _require_link(tenant_id, field, record_id)
    if payload.get("thread_type") in THREAD_LINK_BY_TYPE:
        required_field = THREAD_LINK_BY_TYPE[payload["thread_type"]]
        if not payload.get(required_field):
            raise CommunicationError("linked_record_required", f"{payload['thread_type']} requires {required_field}", 400)
    if refs.get("order_item_id") and payload.get("order_id") and refs["order_item_id"].get("order_id") != payload["order_id"]:
        raise CommunicationError("link_mismatch", "order_item_id does not belong to order_id", 400)
    if refs.get("work_order_id") and payload.get("order_id") and refs["work_order_id"].get("order_id") != payload["order_id"]:
        raise CommunicationError("link_mismatch", "work_order_id does not belong to order_id", 400)
    if refs.get("production_stage_id"):
        stage = refs["production_stage_id"]
        for field in ("order_id", "order_item_id", "work_order_id"):
            if payload.get(field) and stage.get(field) != payload[field]:
                raise CommunicationError("link_mismatch", f"production_stage_id does not belong to {field}", 400)
    return refs


async def _get_thread(tenant_id: str, thread_id: str, *, include_archived: bool = False) -> dict:
    q: dict[str, Any] = {"tenant_id": tenant_id, "id": thread_id}
    if not include_archived:
        q["archived_at"] = None
    doc = await db.message_threads.find_one(q, {"_id": 0})
    if not doc:
        raise CommunicationError("thread_not_found", "Message thread not found", 404)
    return doc


def _is_participant(thread: dict, *, identity_type: str, identity_id: str) -> bool:
    if identity_type == "user":
        return identity_id in (thread.get("participant_user_ids") or [])
    return identity_id in (thread.get("participant_employee_ids") or [])


async def _require_thread_access(tenant_id: str, thread_id: str, *, identity_type: str, identity_id: str, manage: bool = False) -> dict:
    thread = await _get_thread(tenant_id, thread_id)
    if identity_type == "employee" and thread.get("visibility") != "employee_visible":
        raise CommunicationError("thread_forbidden", "Thread is not visible to this employee", 403)
    if not manage and not _is_participant(thread, identity_type=identity_type, identity_id=identity_id):
        raise CommunicationError("thread_forbidden", "You are not a participant in this thread", 403)
    return thread


async def _unread_count(tenant_id: str, thread_id: str, *, identity_type: str, identity_id: str) -> int:
    state = await db.message_read_states.find_one(
        {"tenant_id": tenant_id, "thread_id": thread_id, "identity_type": identity_type, "identity_id": identity_id},
        {"_id": 0},
    )
    q: dict[str, Any] = {"tenant_id": tenant_id, "thread_id": thread_id, "archived_at": None}
    if state and state.get("last_read_at"):
        last_read = state["last_read_at"]
        if isinstance(last_read, str):
            try:
                last_read = datetime.fromisoformat(last_read.replace("Z", "+00:00"))
            except ValueError:
                last_read = None
        if last_read:
            q["created_at"] = {"$gt": last_read}
    return await db.thread_messages.count_documents(q)


async def list_threads(
    *, tenant_id: str, identity_type: str, identity_id: str, thread_type: Optional[str] = None,
    q: Optional[str] = None, include_archived: bool = False, limit: int = 100, skip: int = 0,
) -> dict:
    filt: dict[str, Any] = {"tenant_id": tenant_id}
    if not include_archived:
        filt["archived_at"] = None
    if identity_type == "user":
        filt["participant_user_ids"] = identity_id
    else:
        filt["participant_employee_ids"] = identity_id
        filt["visibility"] = "employee_visible"
    if thread_type:
        if thread_type not in THREAD_TYPES:
            raise CommunicationError("invalid_thread_type", "Unsupported thread type", 400)
        filt["thread_type"] = thread_type
    if q:
        filt["$or"] = [{"title": {"$regex": q, "$options": "i"}}]
    total = await db.message_threads.count_documents(filt)
    cur = db.message_threads.find(filt, {"_id": 0}).sort("last_message_at", -1).skip(skip).limit(limit)
    items = []
    async for doc in cur:
        out = _thread_public(doc, identity_type=identity_type, identity_id=identity_id)
        out["unread_count"] = await _unread_count(tenant_id, doc["id"], identity_type=identity_type, identity_id=identity_id)
        items.append(out)
    unread_total = sum(i["unread_count"] for i in items)
    return {"items": items, "total": total, "unread_total": unread_total}


async def create_thread(*, tenant_id: str, actor_user_id: Optional[str] = None, actor_employee_id: Optional[str] = None,
                        actor_email: str = "system", payload: dict) -> dict:
    if payload.get("thread_type") not in THREAD_TYPES:
        raise CommunicationError("invalid_thread_type", "Unsupported thread type", 400)
    if payload.get("visibility") not in THREAD_VISIBILITIES:
        raise CommunicationError("invalid_visibility", "Unsupported thread visibility", 400)
    if actor_user_id:
        payload.setdefault("participant_user_ids", [])
        if actor_user_id not in payload["participant_user_ids"]:
            payload["participant_user_ids"].append(actor_user_id)
    if actor_employee_id:
        payload.setdefault("participant_employee_ids", [])
        if actor_employee_id not in payload["participant_employee_ids"]:
            payload["participant_employee_ids"].append(actor_employee_id)
    await _validate_participants(tenant_id, payload)
    await _validate_links(tenant_id, payload)
    doc = MessageThread(
        tenant_id=tenant_id,
        created_by_user_id=actor_user_id,
        created_by_employee_id=actor_employee_id,
        last_message_at=_now(),
        **payload,
    ).model_dump()
    await db.message_threads.insert_one(prepare_for_mongo(dict(doc)))
    await _ensure_read_state(tenant_id=tenant_id, thread_id=doc["id"], identity_type="user" if actor_user_id else "employee", identity_id=actor_user_id or actor_employee_id or "")
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id or f"employee:{actor_employee_id}",
        actor_email=actor_email, module="team", action="message.thread_created",
        entity_type="message_thread", entity_id=doc["id"], summary=f"Message thread created: {doc['title']}",
        metadata={"thread_type": doc["thread_type"], "visibility": doc["visibility"]},
    )
    return serialize_doc(doc)


async def add_participants(*, tenant_id: str, thread_id: str, actor_user_id: str, actor_email: str,
                           participant_user_ids: list[str], participant_employee_ids: list[str]) -> dict:
    thread = await _require_thread_access(tenant_id, thread_id, identity_type="user", identity_id=actor_user_id, manage=True)
    payload = {
        "participant_user_ids": list(set((thread.get("participant_user_ids") or []) + participant_user_ids)),
        "participant_employee_ids": list(set((thread.get("participant_employee_ids") or []) + participant_employee_ids)),
    }
    await _validate_participants(tenant_id, payload)
    now = _now()
    await db.message_threads.update_one({"tenant_id": tenant_id, "id": thread_id}, {"$set": {**payload, "updated_at": now}})
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="message.participants_changed", entity_type="message_thread", entity_id=thread_id,
        summary="Message thread participants changed",
    )
    return await get_thread(tenant_id=tenant_id, thread_id=thread_id, identity_type="user", identity_id=actor_user_id, manage=True)


async def get_thread(*, tenant_id: str, thread_id: str, identity_type: str, identity_id: str, manage: bool = False) -> dict:
    thread = await _require_thread_access(tenant_id, thread_id, identity_type=identity_type, identity_id=identity_id, manage=manage)
    out = _thread_public(thread, identity_type=identity_type, identity_id=identity_id)
    out["unread_count"] = await _unread_count(tenant_id, thread_id, identity_type=identity_type, identity_id=identity_id)
    return out


async def list_messages(*, tenant_id: str, thread_id: str, identity_type: str, identity_id: str, limit: int = 100, skip: int = 0) -> dict:
    await _require_thread_access(tenant_id, thread_id, identity_type=identity_type, identity_id=identity_id)
    filt = {"tenant_id": tenant_id, "thread_id": thread_id, "archived_at": None}
    if identity_type == "employee":
        filt["visibility"] = "employee_visible"
    total = await db.thread_messages.count_documents(filt)
    cur = db.thread_messages.find(filt, {"_id": 0}).sort("created_at", 1).skip(skip).limit(limit)
    return {"items": [serialize_doc(d) async for d in cur], "total": total}


async def send_message(*, tenant_id: str, thread_id: str, body: str, actor_user_id: Optional[str] = None,
                       actor_employee_id: Optional[str] = None, actor_email: str = "system",
                       idempotency_key: Optional[str] = None) -> dict:
    identity_type, identity_id = _identity_key(user_id=actor_user_id, employee_id=actor_employee_id)
    thread = await _require_thread_access(tenant_id, thread_id, identity_type=identity_type, identity_id=identity_id)
    visibility = "employee_visible" if thread.get("visibility") == "employee_visible" else "internal"
    if not body or not body.strip():
        raise CommunicationError("body_required", "Message body is required", 400)
    if idempotency_key:
        existing = await db.thread_messages.find_one(
            {"tenant_id": tenant_id, "thread_id": thread_id, "idempotency_key": idempotency_key}, {"_id": 0}
        )
        if existing:
            return serialize_doc(existing)
    now = _now()
    doc = ThreadMessage(
        tenant_id=tenant_id, thread_id=thread_id, sender_user_id=actor_user_id,
        sender_employee_id=actor_employee_id, body=body.strip(), visibility=visibility,
        idempotency_key=idempotency_key,
    ).model_dump()
    try:
        await db.thread_messages.insert_one(prepare_for_mongo(dict(doc)))
    except DuplicateKeyError:
        existing = await db.thread_messages.find_one(
            {"tenant_id": tenant_id, "thread_id": thread_id, "idempotency_key": idempotency_key}, {"_id": 0}
        )
        if existing:
            return serialize_doc(existing)
        raise
    await db.message_threads.update_one({"tenant_id": tenant_id, "id": thread_id}, {"$set": {"last_message_at": now, "updated_at": now}})
    await mark_thread_read(tenant_id=tenant_id, thread_id=thread_id, identity_type=identity_type, identity_id=identity_id)
    for uid in thread.get("participant_user_ids") or []:
        if uid != actor_user_id:
            await notifications.notify(
                tenant_id=tenant_id, recipient_user_id=uid, module="team", kind="message.new",
                title=thread.get("title") or "New message", body="A new internal message was posted.",
                entity_type="message_thread", entity_id=thread_id, link="/team/messages",
            )
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id or f"employee:{actor_employee_id}",
        actor_email=actor_email, module="team", action="message.sent",
        entity_type="message_thread", entity_id=thread_id, summary="Message sent",
    )
    return serialize_doc(doc)


async def _ensure_read_state(*, tenant_id: str, thread_id: str, identity_type: str, identity_id: str) -> None:
    if not identity_id:
        return
    await db.message_read_states.update_one(
        {"tenant_id": tenant_id, "thread_id": thread_id, "identity_type": identity_type, "identity_id": identity_id},
        {"$setOnInsert": prepare_for_mongo(MessageReadState(
            tenant_id=tenant_id, thread_id=thread_id, identity_type=identity_type, identity_id=identity_id,
        ).model_dump())},
        upsert=True,
    )


async def mark_thread_read(*, tenant_id: str, thread_id: str, identity_type: str, identity_id: str) -> dict:
    await _require_thread_access(tenant_id, thread_id, identity_type=identity_type, identity_id=identity_id)
    last = await db.thread_messages.find_one(
        {"tenant_id": tenant_id, "thread_id": thread_id, "archived_at": None},
        {"_id": 0}, sort=[("created_at", -1)],
    )
    now_dt = utc_now()
    await db.message_read_states.update_one(
        {"tenant_id": tenant_id, "thread_id": thread_id, "identity_type": identity_type, "identity_id": identity_id},
        {"$set": {"last_read_at": now_dt, "last_read_message_id": last.get("id") if last else None, "updated_at": now_dt},
         "$setOnInsert": {"id": MessageReadState(tenant_id=tenant_id, thread_id=thread_id, identity_type=identity_type, identity_id=identity_id).id,
                          "tenant_id": tenant_id, "thread_id": thread_id, "identity_type": identity_type, "identity_id": identity_id,
                          "created_at": now_dt}},
        upsert=True,
    )
    return {"ok": True, "unread_count": 0}


async def archive_thread(*, tenant_id: str, thread_id: str, actor_user_id: str, actor_email: str) -> dict:
    await _require_thread_access(tenant_id, thread_id, identity_type="user", identity_id=actor_user_id)
    now = _now()
    await db.message_threads.update_one({"tenant_id": tenant_id, "id": thread_id}, {"$set": {"archived_at": now, "updated_at": now}})
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email, module="team",
        action="message.thread_archived", entity_type="message_thread", entity_id=thread_id, summary="Message thread archived",
    )
    return {"ok": True, "archived_at": now}


async def create_note(*, tenant_id: str, actor_user_id: Optional[str] = None, actor_employee_id: Optional[str] = None,
                      actor_email: str = "system", payload: dict) -> dict:
    if payload.get("visibility") not in NOTE_VISIBILITIES:
        raise CommunicationError("invalid_note_visibility", "Unsupported note visibility", 400)
    await _validate_links(tenant_id, payload, for_note=True)
    doc = InternalNote(tenant_id=tenant_id, author_user_id=actor_user_id, author_employee_id=actor_employee_id, **payload).model_dump()
    await db.internal_notes.insert_one(prepare_for_mongo(dict(doc)))
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id or f"employee:{actor_employee_id}", actor_email=actor_email,
        module="team", action="note.created", entity_type="internal_note", entity_id=doc["id"],
        summary="Internal note created", metadata={"visibility": doc["visibility"], "pinned": doc["pinned"]},
    )
    return serialize_doc(doc)


def _note_filter_for_identity(*, tenant_id: str, identity_type: str, identity_id: str, include_archived: bool) -> dict:
    filt: dict[str, Any] = {"tenant_id": tenant_id}
    if not include_archived:
        filt["archived_at"] = None
    if identity_type == "employee":
        filt["$or"] = [
            {"visibility": "employee_visible"},
            {"visibility": "private_to_author", "author_employee_id": identity_id},
        ]
    else:
        filt["$or"] = [
            {"visibility": {"$in": ["internal", "employee_visible", "manager_only"]}},
            {"visibility": "private_to_author", "author_user_id": identity_id},
        ]
    return filt


async def list_notes(*, tenant_id: str, identity_type: str, identity_id: str, linked: dict | None = None,
                     include_archived: bool = False, limit: int = 100, skip: int = 0) -> dict:
    filt = _note_filter_for_identity(tenant_id=tenant_id, identity_type=identity_type, identity_id=identity_id, include_archived=include_archived)
    for field in LINK_COLLECTIONS:
        if linked and linked.get(field):
            filt[field] = linked[field]
    total = await db.internal_notes.count_documents(filt)
    cur = db.internal_notes.find(filt, {"_id": 0}).sort([("pinned", -1), ("created_at", -1)]).skip(skip).limit(limit)
    return {"items": [serialize_doc(d) async for d in cur], "total": total}


async def edit_note(*, tenant_id: str, note_id: str, actor_user_id: str, actor_email: str, updates: dict) -> dict:
    note = await db.internal_notes.find_one({"tenant_id": tenant_id, "id": note_id, "archived_at": None}, {"_id": 0})
    if not note:
        raise CommunicationError("note_not_found", "Note not found", 404)
    if note.get("visibility") == "private_to_author" and note.get("author_user_id") != actor_user_id:
        raise CommunicationError("note_forbidden", "Private note is visible only to its author", 403)
    allowed = {k: v for k, v in updates.items() if k in {"title", "body", "visibility", "pinned"}}
    if "visibility" in allowed and allowed["visibility"] not in NOTE_VISIBILITIES:
        raise CommunicationError("invalid_note_visibility", "Unsupported note visibility", 400)
    allowed["edited_at"] = _now()
    allowed["updated_at"] = allowed["edited_at"]
    await db.internal_notes.update_one({"tenant_id": tenant_id, "id": note_id}, {"$set": allowed})
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="note.edited", entity_type="internal_note", entity_id=note_id, summary="Internal note edited",
        metadata={k: v for k, v in allowed.items() if k not in {"body", "title"}},
    )
    return serialize_doc(await db.internal_notes.find_one({"tenant_id": tenant_id, "id": note_id}, {"_id": 0}))


async def archive_note(*, tenant_id: str, note_id: str, actor_user_id: str, actor_email: str) -> dict:
    note = await db.internal_notes.find_one({"tenant_id": tenant_id, "id": note_id, "archived_at": None}, {"_id": 0})
    if not note:
        raise CommunicationError("note_not_found", "Note not found", 404)
    now = _now()
    await db.internal_notes.update_one({"tenant_id": tenant_id, "id": note_id}, {"$set": {"archived_at": now, "updated_at": now}})
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="note.archived", entity_type="internal_note", entity_id=note_id, summary="Internal note archived",
    )
    return {"ok": True, "archived_at": now}


async def get_preferences(*, tenant_id: str, identity_type: str, identity_id: str) -> dict:
    doc = await db.communication_preferences.find_one(
        {"tenant_id": tenant_id, "identity_type": identity_type, "identity_id": identity_id}, {"_id": 0}
    )
    if doc:
        return serialize_doc(doc)
    pref = CommunicationPreference(tenant_id=tenant_id, identity_type=identity_type, identity_id=identity_id).model_dump()
    await db.communication_preferences.insert_one(prepare_for_mongo(dict(pref)))
    return serialize_doc(pref)


async def update_preferences(*, tenant_id: str, identity_type: str, identity_id: str, updates: dict,
                             actor_user_id: Optional[str] = None, actor_employee_id: Optional[str] = None,
                             actor_email: str = "system") -> dict:
    allowed_keys = {
        "in_app_messages", "task_notifications", "schedule_changes", "time_off_decisions",
        "appointment_reminders", "announcements", "daily_digest", "email_delivery",
        "digest_time", "digest_frequency", "quiet_hours",
    }
    clean = {k: v for k, v in updates.items() if k in allowed_keys}
    if "quiet_hours" in clean:
        qh = clean["quiet_hours"] or {}
        clean["quiet_hours"] = {
            "enabled": bool(qh.get("enabled", False)),
            "start_time": str(qh.get("start_time") or "18:00")[:5],
            "end_time": str(qh.get("end_time") or "07:00")[:5],
            "timezone": str(qh.get("timezone") or "UTC"),
            "allow_critical": bool(qh.get("allow_critical", True)),
            "weekends": bool(qh.get("weekends", True)),
        }
    clean["updated_at"] = utc_now()
    base = CommunicationPreference(tenant_id=tenant_id, identity_type=identity_type, identity_id=identity_id).model_dump()
    for key in clean:
        base.pop(key, None)
    await db.communication_preferences.update_one(
        {"tenant_id": tenant_id, "identity_type": identity_type, "identity_id": identity_id},
        {"$set": prepare_for_mongo(clean), "$setOnInsert": prepare_for_mongo(base)},
        upsert=True,
    )
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id or f"employee:{actor_employee_id}", actor_email=actor_email,
        module="team", action="communication.preferences_changed", entity_type="communication_preference",
        entity_id=f"{identity_type}:{identity_id}", summary="Communication preferences changed",
        metadata={k: v for k, v in clean.items() if k != "quiet_hours"},
    )
    return await get_preferences(tenant_id=tenant_id, identity_type=identity_type, identity_id=identity_id)


async def _announcement_items(tenant_id: str, *, employee_id: Optional[str], limit: int = 5) -> list[dict]:
    today = _now()
    filt: dict[str, Any] = {"tenant_id": tenant_id, "status": "published", "$or": [{"expires_at": None}, {"expires_at": {"$gt": today}}]}
    if employee_id:
        filt["$and"] = [{"$or": [{"audience": "all"}, {"employee_ids": employee_id}]}]
    cur = db.announcements.find(filt, {"_id": 0}).sort("published_at", -1).limit(limit)
    return [{"id": a["id"], "title": a["title"], "published_at": a.get("published_at")} async for a in cur]


async def build_digest_sections(*, tenant_id: str, recipient_type: str, recipient_id: str, digest_date: str) -> dict:
    start_day = _digest_day(digest_date)
    start = start_day.isoformat()
    end = (start_day + timedelta(days=1)).isoformat()
    sections: dict[str, Any] = {}
    task_filter: dict[str, Any] = {"tenant_id": tenant_id, "status": {"$in": list(STAFF_DIGEST_STATUSES)}, "archived_at": None}
    if recipient_type == "employee":
        task_filter.update({"assigned_employee_id": recipient_id, "employee_visible": True})
    else:
        task_filter["assigned_user_id"] = recipient_id
    due_today = await db.tasks.count_documents({**task_filter, "due_at": {"$regex": f"^{start}"}})
    overdue = await db.tasks.count_documents({**task_filter, "due_at": {"$lt": start}})
    blocked = await db.tasks.count_documents({**task_filter, "status": "blocked"})
    sections["tasks"] = {"due_today": due_today, "overdue": overdue, "blocked": blocked}
    if recipient_type == "employee":
        cal_filter = {"tenant_id": tenant_id, "employee_id": recipient_id, "status": {"$nin": ["canceled", "cancelled", "archived"]}, "start_at": {"$gte": start, "$lt": end}}
    else:
        cal_filter = {"tenant_id": tenant_id, "status": {"$nin": ["canceled", "cancelled", "archived"]}, "start_at": {"$gte": start, "$lt": end}}
    sections["appointments"] = {"upcoming": await db.calendar_events.count_documents(cal_filter)}
    identity_type, identity_id = recipient_type, recipient_id
    thread_filter = {"tenant_id": tenant_id, "archived_at": None}
    if identity_type == "user":
        thread_filter["participant_user_ids"] = identity_id
    else:
        thread_filter["participant_employee_ids"] = identity_id
        thread_filter["visibility"] = "employee_visible"
    unread = 0
    async for thread in db.message_threads.find(thread_filter, {"_id": 0, "id": 1}):
        unread += await _unread_count(tenant_id, thread["id"], identity_type=identity_type, identity_id=identity_id)
    sections["messages"] = {"unread": unread}
    sections["announcements"] = {"items": await _announcement_items(tenant_id, employee_id=recipient_id if recipient_type == "employee" else None)}
    return sections


async def preview_digest(*, tenant_id: str, recipient_type: str, recipient_id: str, digest_date: Optional[str] = None) -> dict:
    digest_date = digest_date or utc_now().date().isoformat()
    sections = await build_digest_sections(tenant_id=tenant_id, recipient_type=recipient_type, recipient_id=recipient_id, digest_date=digest_date)
    return {"tenant_id": tenant_id, "recipient_type": recipient_type, "recipient_id": recipient_id, "digest_date": digest_date, "status": "preview", "sections": sections}


async def generate_digest(*, tenant_id: str, recipient_type: str, recipient_id: str, digest_date: Optional[str] = None) -> dict:
    digest_date = digest_date or utc_now().date().isoformat()
    existing = await db.daily_digests.find_one(
        {"tenant_id": tenant_id, "recipient_type": recipient_type, "recipient_id": recipient_id, "digest_date": digest_date}, {"_id": 0}
    )
    if existing:
        return serialize_doc(existing)
    sections = await build_digest_sections(tenant_id=tenant_id, recipient_type=recipient_type, recipient_id=recipient_id, digest_date=digest_date)
    doc = DailyDigest(tenant_id=tenant_id, recipient_type=recipient_type, recipient_id=recipient_id, digest_date=digest_date, sections=sections).model_dump()
    try:
        await db.daily_digests.insert_one(prepare_for_mongo(dict(doc)))
    except DuplicateKeyError:
        existing = await db.daily_digests.find_one(
            {"tenant_id": tenant_id, "recipient_type": recipient_type, "recipient_id": recipient_id, "digest_date": digest_date}, {"_id": 0}
        )
        if existing:
            return serialize_doc(existing)
        raise
    return serialize_doc(doc)


async def mark_digest_delivered(*, tenant_id: str, digest_id: str, recipient_type: str, recipient_id: str, delivery_channel: str = "in_app") -> dict:
    digest = await db.daily_digests.find_one(
        {"tenant_id": tenant_id, "id": digest_id, "recipient_type": recipient_type, "recipient_id": recipient_id}, {"_id": 0}
    )
    if not digest:
        raise CommunicationError("digest_not_found", "Digest not found", 404)
    if digest.get("delivered_at"):
        return serialize_doc(digest)
    now = _now()
    await db.daily_digests.update_one(
        {"tenant_id": tenant_id, "id": digest_id},
        {"$set": {"status": "delivered", "delivered_at": now, "delivery_channel": delivery_channel, "updated_at": now}},
    )
    return serialize_doc(await db.daily_digests.find_one({"tenant_id": tenant_id, "id": digest_id}, {"_id": 0}))


async def unread_badge(*, tenant_id: str, identity_type: str, identity_id: str) -> dict:
    data = await list_threads(tenant_id=tenant_id, identity_type=identity_type, identity_id=identity_id, limit=200)
    return {"unread_total": data["unread_total"], "thread_count": data["total"]}
