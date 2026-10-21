"""Focused Webstore shared helpers."""
from __future__ import annotations

from .webstore_context import *

async def _audit(
    *,
    tenant_id: str,
    webstore_id: str,
    actor_type: str,
    action: str,
    entity_type: str,
    entity_id: str,
    summary: str,
    actor_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """The one Webstore history writer: the shared activity + audit trail (Phase 3, W3)."""
    await record_activity_with_audit(
        tenant_id=tenant_id,
        actor_user_id=actor_id or actor_type,
        actor_email=actor_email or actor_type,
        module="webstores",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        metadata={**(metadata or {}), "webstore_id": webstore_id, "actor_type": actor_type},
    )


LEGACY_ACTOR_TYPES = frozenset({"staff", "system", "public", "portal_webstore_owner", "webstore_owner", "webstore_manager", "stripe"})


async def webstore_activity_feed(tenant_id: str, webstore_id: str, *, limit: int = 30, actions: Optional[list[str]] = None) -> list[dict[str, Any]]:
    """The Webstore's history, read from shared activity, in the item shape the UI already uses."""
    query: dict[str, Any] = {"tenant_id": tenant_id, "module": "webstores", "metadata.webstore_id": webstore_id}
    if actions:
        query["action"] = {"$in": actions}
    docs = [doc async for doc in db.activity_events.find(query, {"_id": 0}).sort([("created_at", -1)]).limit(max(1, min(limit, 200)))]
    legacy_types: dict[str, str] = {}
    if any(not (doc.get("metadata") or {}).get("actor_type") for doc in docs):
        # Rows written before Phase 3 kept the actor type only in the retained (read-only) legacy collection.
        async for row in db.webstore_activity_events.find(
            {"tenant_id": tenant_id, "webstore_id": webstore_id, "actor_id": {"$ne": None}}, {"_id": 0, "actor_id": 1, "actor_type": 1}
        ):
            legacy_types.setdefault(str(row["actor_id"]), row.get("actor_type"))
    items = []
    for doc in docs:
        meta = doc.get("metadata") or {}
        actor = str(doc.get("actor_user_id") or "")
        items.append(serialize_doc({
            "id": doc.get("id"),
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            # Old rows without an actor id stored the actor type itself as the actor.
            "actor_type": meta.get("actor_type") or legacy_types.get(actor) or (actor if actor in LEGACY_ACTOR_TYPES else None),
            "actor_id": doc.get("actor_user_id"),
            "actor_email": doc.get("actor_email"),
            "action": doc.get("action"),
            "entity_type": doc.get("entity_type"),
            "entity_id": doc.get("entity_id"),
            "summary": doc.get("summary"),
            "metadata": {k: v for k, v in meta.items() if k not in {"webstore_id", "actor_type"}},
            "created_at": doc.get("created_at"),
        }))
    return items


async def _record_lifecycle_event(
    *,
    tenant_id: str,
    webstore_id: str,
    from_status: Optional[str],
    to_status: str,
    from_state: Optional[str],
    to_state: str,
    actor_id: Optional[str],
    actor_email: Optional[str],
    reason: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    event = WebstoreLifecycleEvent(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        from_status=from_status,
        to_status=to_status,
        from_state=from_state,
        to_state=to_state,
        actor_id=actor_id,
        actor_email=actor_email,
        reason=reason,
        metadata=metadata or {},
    ).model_dump()
    await db.webstore_lifecycle_events.insert_one(prepare_for_mongo(event))
    return serialize_doc(event)

__all__ = [name for name in globals() if not name.startswith("__")]
