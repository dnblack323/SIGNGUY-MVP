"""EC8 phase 8a — Announcement service.

Delivery reuses `services/notifications.py` (in-app, staff `User` recipients
only) — NOT a second messaging system. An Announcement's audience is
Employee IDs; in-app delivery only reaches employees who currently have a
`linked_user_id` (a staff login). Employees without a login, or the future
Employee Portal, will see announcements only in the Announcements list until
Phase 8c wires portal-side delivery. This limitation is intentional for
Phase 8a and documented in the EC8 evidence file — it is not a bug.
"""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.announcement import Announcement
from .activity import record_activity_with_audit
from .notifications import notify


class AnnouncementError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def create_announcement(*, tenant_id: str, actor_user_id: str, actor_email: str, payload: dict) -> dict:
    doc = Announcement(tenant_id=tenant_id, created_by=actor_user_id, **payload).model_dump()
    await db.announcements.insert_one(prepare_for_mongo(dict(doc)))
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="announcement.create", entity_type="announcement", entity_id=doc["id"],
        summary=f"Announcement '{doc['title']}' created ({doc['status']})",
    )
    doc.pop("_id", None)
    return serialize_doc(doc)


async def list_announcements(*, tenant_id: str, status: Optional[str] = None) -> list[dict]:
    filt: dict[str, Any] = {"tenant_id": tenant_id}
    if status:
        filt["status"] = status
    cur = db.announcements.find(filt, {"_id": 0}).sort("created_at", -1)
    return [serialize_doc(d) async for d in cur]


async def publish_announcement(*, tenant_id: str, announcement_id: str, actor_user_id: str, actor_email: str) -> dict:
    doc = await db.announcements.find_one({"id": announcement_id, "tenant_id": tenant_id}, {"_id": 0})
    if not doc:
        raise AnnouncementError(404, "Announcement not found")
    if doc["status"] == "published":
        raise AnnouncementError(400, "Announcement already published")
    now = utc_now().isoformat()
    await db.announcements.update_one(
        {"id": announcement_id, "tenant_id": tenant_id},
        {"$set": {"status": "published", "published_at": now, "updated_at": now}},
    )
    # Deliver in-app to any audience employee who currently has a staff login.
    if doc["audience"] == "all":
        target_filt: dict[str, Any] = {"tenant_id": tenant_id, "status": "active", "linked_user_id": {"$ne": None}}
    else:
        target_filt = {"tenant_id": tenant_id, "id": {"$in": doc.get("employee_ids", [])}, "linked_user_id": {"$ne": None}}
    delivered = 0
    async for emp in db.employees.find(target_filt, {"_id": 0, "linked_user_id": 1}):
        await notify(
            tenant_id=tenant_id, recipient_user_id=emp["linked_user_id"], module="team",
            kind="announcement.published", title=doc["title"], body=doc["body"],
            entity_type="announcement", entity_id=announcement_id, link="/team/announcements",
        )
        delivered += 1
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="announcement.publish", entity_type="announcement", entity_id=announcement_id,
        summary=f"Announcement '{doc['title']}' published ({delivered} in-app notification(s) sent)",
    )
    result = await db.announcements.find_one({"id": announcement_id, "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(result or {})


async def active_announcements(*, tenant_id: str, limit: int = 5) -> list[dict]:
    now = utc_now().isoformat()
    filt = {"tenant_id": tenant_id, "status": "published",
            "$or": [{"expires_at": None}, {"expires_at": {"$gt": now}}]}
    cur = db.announcements.find(filt, {"_id": 0}).sort("published_at", -1).limit(limit)
    return [serialize_doc(d) async for d in cur]
