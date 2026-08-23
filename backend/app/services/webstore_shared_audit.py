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
    activity = WebstoreActivity(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        metadata=metadata or {},
    ).model_dump()
    await db.webstore_activity_events.insert_one(prepare_for_mongo(activity))
    await record_activity_with_audit(
        tenant_id=tenant_id,
        actor_user_id=actor_id or actor_type,
        actor_email=actor_email or actor_type,
        module="webstores",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        metadata={"webstore_id": webstore_id, **(metadata or {})},
    )


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
