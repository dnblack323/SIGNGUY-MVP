"""EC2 — In-app notification service (staff-only)."""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.notification import Notification


async def notify(
    *,
    tenant_id: str,
    recipient_user_id: str,
    module: str,
    kind: str,
    title: str,
    body: Optional[str] = None,
    severity: str = "info",
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    link: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> Notification:
    n = Notification(
        tenant_id=tenant_id,
        recipient_user_id=recipient_user_id,
        module=module,
        kind=kind,
        title=title,
        body=body,
        severity=severity,  # type: ignore[arg-type]
        entity_type=entity_type,
        entity_id=entity_id,
        link=link,
        metadata=metadata,
    )
    await db.notifications.insert_one(prepare_for_mongo(n.model_dump()))
    return n


async def notify_tenant_owners(
    *,
    tenant_id: str,
    module: str,
    kind: str,
    title: str,
    body: Optional[str] = None,
    severity: str = "info",
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    link: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> int:
    """Fan-out helper — deliver to every owner/admin in the tenant."""
    count = 0
    cursor = db.users.find(
        {"tenant_id": tenant_id, "is_active": True, "role": {"$in": ["owner", "admin"]}},
        {"_id": 0, "id": 1},
    )
    async for u in cursor:
        await notify(
            tenant_id=tenant_id,
            recipient_user_id=u["id"],
            module=module,
            kind=kind,
            title=title,
            body=body,
            severity=severity,
            entity_type=entity_type,
            entity_id=entity_id,
            link=link,
            metadata=metadata,
        )
        count += 1
    return count


async def list_for_user(
    *,
    tenant_id: str,
    user_id: str,
    status: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
) -> dict[str, Any]:
    q: dict[str, Any] = {"tenant_id": tenant_id, "recipient_user_id": user_id}
    if status:
        q["status"] = status
    total = await db.notifications.count_documents(q)
    cursor = (
        db.notifications.find(q, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    return {
        "items": [serialize_doc(d) async for d in cursor],
        "total": total,
        "limit": limit,
        "skip": skip,
    }


async def unread_count(*, tenant_id: str, user_id: str) -> int:
    return await db.notifications.count_documents(
        {"tenant_id": tenant_id, "recipient_user_id": user_id, "status": "unread"}
    )


async def mark_read(*, tenant_id: str, user_id: str, notification_id: str) -> bool:
    now = utc_now().isoformat()
    res = await db.notifications.update_one(
        {
            "id": notification_id,
            "tenant_id": tenant_id,
            "recipient_user_id": user_id,
            "status": "unread",
        },
        {"$set": {"status": "read", "read_at": now, "updated_at": now}},
    )
    return res.matched_count > 0


async def mark_many_read(*, tenant_id: str, user_id: str, ids: list[str]) -> int:
    if not ids:
        return 0
    now = utc_now().isoformat()
    res = await db.notifications.update_many(
        {
            "id": {"$in": ids},
            "tenant_id": tenant_id,
            "recipient_user_id": user_id,
            "status": "unread",
        },
        {"$set": {"status": "read", "read_at": now, "updated_at": now}},
    )
    return res.modified_count


async def dismiss(*, tenant_id: str, user_id: str, notification_id: str) -> bool:
    now = utc_now().isoformat()
    res = await db.notifications.update_one(
        {
            "id": notification_id,
            "tenant_id": tenant_id,
            "recipient_user_id": user_id,
        },
        {"$set": {"status": "dismissed", "dismissed_at": now, "updated_at": now}},
    )
    return res.matched_count > 0
