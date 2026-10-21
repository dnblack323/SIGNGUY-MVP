"""Webstore messages (Phase 3, W5 / D3-8): one shop <-> owner thread per Webstore.

Reuses the shared ``message_threads`` / ``thread_messages`` records with
``thread_type="webstore_discussion"`` and ``webstore_id``. Access follows the
Webstore, not thread participants: staff need Webstore permissions (and their
store assignment scope); the owner needs an active portal assignment. Every
message in this thread is shared with the owner, so staff-only notes stay in
notes. Notifications are in-app only; no email is sent.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.permissions import Perm
from ..models.communication import MessageThread, ThreadMessage
from .webstore_context import WebstoreError, db, prepare_for_mongo, serialize_doc, utc_now
from .webstore_shared_access import _owner_portal_store, _require_staff_perm, _require_webstore_assignment_scope
from .webstore_shared_audit import _audit
from .webstore_shared_repository import _get_store

THREAD_TYPE = "webstore_discussion"
MAX_BODY = 5000
# Per-portal-identity send limit, like the customer portal's message form.
_OWNER_SEND_WINDOW = 300
_OWNER_SEND_MAX = 10
_OWNER_SEND_BUCKET: dict[str, list[float]] = {}


def _clean_body(body: Any) -> str:
    text = str(body or "").strip()
    if not text:
        raise WebstoreError("message_required", "Write a message first", 400)
    if len(text) > MAX_BODY:
        raise WebstoreError("message_too_long", f"Messages are limited to {MAX_BODY} characters", 400)
    return text


def _owner_rate(identity_id: str) -> None:
    now = time.time()
    bucket = [t for t in _OWNER_SEND_BUCKET.get(identity_id, []) if now - t < _OWNER_SEND_WINDOW]
    if len(bucket) >= _OWNER_SEND_MAX:
        raise WebstoreError("message_rate_limited", "Too many messages. Try again in a few minutes.", 429)
    _OWNER_SEND_BUCKET[identity_id] = [*bucket, now]


async def _thread(tenant_id: str, store: dict, *, create: bool) -> Optional[dict]:
    query = {"tenant_id": tenant_id, "webstore_id": store["id"], "thread_type": THREAD_TYPE}
    found = await db.message_threads.find_one(query, {"_id": 0})
    if found or not create:
        return found
    thread = MessageThread(tenant_id=tenant_id, thread_type=THREAD_TYPE, title=f"{store.get('name')} messages", webstore_id=store["id"]).model_dump()
    try:
        await db.message_threads.insert_one(prepare_for_mongo(thread))
    except DuplicateKeyError:  # created concurrently; one thread per Webstore
        pass
    return await db.message_threads.find_one(query, {"_id": 0})


async def _messages(tenant_id: str, thread: Optional[dict], *, viewer: str, shop_name: str) -> list[dict[str, Any]]:
    if not thread:
        return []
    staff_names: dict[str, str] = {}
    items = []
    async for doc in db.thread_messages.find(
        {"tenant_id": tenant_id, "thread_id": thread["id"], "archived_at": None}, {"_id": 0}
    ).sort([("created_at", 1)]).limit(500):
        from_owner = bool(doc.get("sender_portal_identity_id"))
        if from_owner:
            name = "Store owner"
        elif viewer == "owner":
            name = shop_name  # owners see the shop, not individual staff accounts
        else:
            user_id = doc.get("sender_user_id") or ""
            if user_id not in staff_names:
                user = await db.users.find_one({"tenant_id": tenant_id, "id": user_id}, {"_id": 0, "name": 1, "email": 1})
                staff_names[user_id] = (user or {}).get("name") or (user or {}).get("email") or "Shop"
            name = staff_names[user_id]
        items.append({"id": doc["id"], "body": doc["body"], "created_at": doc.get("created_at"),
                      "from": "owner" if from_owner else "shop", "sender_name": name})
    return items


async def _post(tenant_id: str, store: dict, body: str, *, user_id: Optional[str] = None, portal_identity_id: Optional[str] = None) -> dict:
    thread = await _thread(tenant_id, store, create=True)
    message = ThreadMessage(tenant_id=tenant_id, thread_id=thread["id"], sender_user_id=user_id,
                            sender_portal_identity_id=portal_identity_id, body=body).model_dump()
    await db.thread_messages.insert_one(prepare_for_mongo(message))
    await db.message_threads.update_one({"tenant_id": tenant_id, "id": thread["id"]},
                                        {"$set": {"last_message_at": message["created_at"], "updated_at": utc_now().isoformat()}})
    return serialize_doc(message)


async def _shop_name(tenant_id: str) -> str:
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0, "name": 1})
    return (tenant or {}).get("name") or "The shop"


async def staff_messages(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    await _require_webstore_assignment_scope(user, webstore_id)
    store = await _get_store(user["tenant_id"], webstore_id)
    thread = await _thread(user["tenant_id"], store, create=False)
    return {"webstore_id": webstore_id, "items": await _messages(user["tenant_id"], thread, viewer="shop", shop_name="")}


async def staff_send(user: dict, webstore_id: str, body: Any) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    await _require_webstore_assignment_scope(user, webstore_id)
    store = await _get_store(user["tenant_id"], webstore_id)
    text = _clean_body(body)
    message = await _post(user["tenant_id"], store, text, user_id=user["id"])
    await _audit(tenant_id=user["tenant_id"], webstore_id=webstore_id, actor_type="staff", actor_id=user["id"], actor_email=user.get("email"),
                 action="webstore.message_sent", entity_type="webstore_message", entity_id=message["id"],
                 summary="Shop sent the owner a message", metadata={"from": "shop"})
    return await staff_messages(user, webstore_id)


async def owner_messages(identity: dict, webstore_id: str) -> dict:
    store = await _owner_portal_store(identity, webstore_id)
    thread = await _thread(identity["tenant_id"], store, create=False)
    items = await _messages(identity["tenant_id"], thread, viewer="owner", shop_name=await _shop_name(identity["tenant_id"]))
    return {"webstore_id": webstore_id, "items": items}


async def owner_send(identity: dict, webstore_id: str, body: Any) -> dict:
    store = await _owner_portal_store(identity, webstore_id)
    text = _clean_body(body)
    _owner_rate(identity["id"])
    message = await _post(identity["tenant_id"], store, text, portal_identity_id=identity["id"])
    await _audit(tenant_id=identity["tenant_id"], webstore_id=webstore_id, actor_type="portal_webstore_owner", actor_id=identity["id"],
                 actor_email=identity.get("email"), action="webstore.message_received", entity_type="webstore_message",
                 entity_id=message["id"], summary="Store owner sent a message", metadata={"from": "owner"})
    await _notify_shop(identity["tenant_id"], store)
    return await owner_messages(identity, webstore_id)


async def _notify_shop(tenant_id: str, store: dict) -> None:
    """In-app notice to the store's assignee, or the shop owners when unassigned."""
    from .notifications import notify, notify_tenant_owners

    fields = {"tenant_id": tenant_id, "module": "webstores", "kind": "webstore.message_received",
              "title": f"New message from {store.get('name')} owner", "entity_type": "webstore", "entity_id": store["id"],
              "link": f"/webstores/{store['id']}"}
    assignee = store.get("assignee_user_id")
    if assignee and await db.users.find_one({"tenant_id": tenant_id, "id": assignee, "is_active": True}, {"_id": 1}):
        await notify(recipient_user_id=assignee, **fields)
    else:
        await notify_tenant_owners(**fields)


__all__ = ["staff_messages", "staff_send", "owner_messages", "owner_send", "THREAD_TYPE"]
