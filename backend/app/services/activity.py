"""EC2 — Activity feed service.

Sits alongside (not replacing) `services/audit.py`. `record_activity` writes an
ActivityEvent row. `record_activity_with_audit` is a convenience helper that
records the underlying audit row first then the activity row that links to it,
guaranteeing the two stay in sync when a caller wants both.
"""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc
from ..models.activity import ActivityEvent
from .audit import record_audit


async def record_activity(
    *,
    tenant_id: str,
    module: str,
    action: str,
    summary: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    actor_user_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    audit_event_id: Optional[str] = None,
    severity: str = "info",
    metadata: Optional[dict[str, Any]] = None,
) -> ActivityEvent:
    evt = ActivityEvent(
        tenant_id=tenant_id,
        module=module,
        action=action,
        summary=summary,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        audit_event_id=audit_event_id,
        severity=severity,  # type: ignore[arg-type]
        metadata=metadata,
    )
    await db.activity_events.insert_one(prepare_for_mongo(evt.model_dump()))
    return evt


async def record_activity_with_audit(
    *,
    tenant_id: str,
    actor_user_id: str,
    actor_email: str,
    module: str,
    action: str,
    entity_type: str,
    entity_id: str,
    summary: str,
    severity: str = "info",
    diff: Optional[dict[str, Any]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> tuple[str, ActivityEvent]:
    """Write audit row + activity row atomically-in-code (best-effort ordering)."""
    audit_evt = await record_audit(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        diff=diff,
    )
    activity = await record_activity(
        tenant_id=tenant_id,
        module=module,
        action=action,
        summary=summary,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        audit_event_id=audit_evt.id,
        severity=severity,
        metadata=metadata,
    )
    return audit_evt.id, activity


async def list_activity(
    *,
    tenant_id: str,
    module: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
) -> dict[str, Any]:
    q: dict[str, Any] = {"tenant_id": tenant_id}
    if module:
        q["module"] = module
    if entity_type:
        q["entity_type"] = entity_type
    if entity_id:
        q["entity_id"] = entity_id
    if severity:
        q["severity"] = severity
    total = await db.activity_events.count_documents(q)
    cursor = (
        db.activity_events.find(q, {"_id": 0})
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
