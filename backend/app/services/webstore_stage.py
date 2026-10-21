"""The single Webstore stage (Phase 3, decision D3-1).

``stage`` is the coarse journey every screen agrees on; it reuses the existing
10-state launch lifecycle. The detailed legacy ``status`` is kept as a
compatibility field (D3-3). Both are written only by ``apply_store_status``,
which also records the lifecycle event. Old records without ``stage`` get it
derived on read (no data migration).
"""
from __future__ import annotations

from typing import Any, Optional

from .webstore_context import (
    INTERNAL_STATUS_TO_PHASE6,
    PHASE6_LIFECYCLE_STATES,
    WebstoreError,
    db,
    serialize_doc,
    utc_now,
)
from .webstore_shared_audit import _record_lifecycle_event
from .webstore_shared_lifecycle import _validate_status_change

STAGES = tuple(PHASE6_LIFECYCLE_STATES)
STAGE_LABELS: dict[str, dict[str, str]] = {
    "draft": {"staff": "Request received", "owner": "Request received"},
    "intake_pending": {"staff": "Waiting on owner", "owner": "Complete your questionnaire"},
    "setup_in_progress": {"staff": "Setting up", "owner": "We're preparing your store"},
    "owner_review": {"staff": "Owner approval", "owner": "Review and approve your store"},
    "payment_setup_pending": {"staff": "Payment setup", "owner": "Payment setup in progress"},
    "ready_to_launch": {"staff": "Ready to publish", "owner": "Your store is ready"},
    "live": {"staff": "Live", "owner": "Live"},
    "paused": {"staff": "Paused", "owner": "Paused"},
    "closed": {"staff": "Closed", "owner": "Ordering closed"},
    "archived": {"staff": "Archived", "owner": "Archived"},
}
# D3-2: placeholder statuses for unbuilt AI steps are no longer written (still readable on old records).
RETIRED_STATUSES = frozenset({"ai_setup_ready", "ai_product_suggestions_ready", "artwork_needs_review", "mockups_generated", "mockups_approved"})


def stage_of(store: dict) -> str:
    stage = store.get("stage")
    if stage in STAGE_LABELS:
        return stage
    return INTERNAL_STATUS_TO_PHASE6.get(store.get("status") or "draft", "draft")


def stage_view(store: dict) -> dict[str, Any]:
    stage = stage_of(store)
    return {"key": stage, "staff_label": STAGE_LABELS[stage]["staff"], "owner_label": STAGE_LABELS[stage]["owner"],
            "changed_at": store.get("stage_changed_at")}


async def apply_store_status(
    *,
    tenant_id: str,
    webstore_id: str,
    status: str,
    source: str,
    actor_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    reason: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
    validate: bool = True,
    only_from: Optional[set[str]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> Optional[dict]:
    """The only writer of a Webstore's ``status`` and ``stage``.

    ``validate`` applies the staff transition rules (route-driven changes);
    system corrections pass ``validate=False`` exactly as they did before.
    ``only_from`` makes the change conditional (no-op unless the current
    status is in the set); ``extra`` fields are still written on a no-op.
    """
    if status in RETIRED_STATUSES:
        raise WebstoreError("retired_webstore_status", f"{status} is no longer used", 400)
    store = await db.webstores.find_one({"tenant_id": tenant_id, "id": webstore_id}, {"_id": 0})
    if not store:
        raise WebstoreError("webstore_not_found", "Webstore not found", 404)
    current = store.get("status") or "draft"
    now = utc_now().isoformat()
    updates: dict[str, Any] = {**(extra or {}), "updated_at": now}
    changing = status != current and (only_from is None or current in only_from)
    if changing:
        if validate:
            _validate_status_change(current, status)
        from_stage, to_stage = stage_of(store), INTERNAL_STATUS_TO_PHASE6.get(status, "draft")
        updates.update({"status": status, "stage": to_stage})
        if to_stage != from_stage or not store.get("stage_changed_at"):
            updates["stage_changed_at"] = now
    elif not store.get("stage"):
        updates["stage"] = stage_of(store)
    await db.webstores.update_one({"tenant_id": tenant_id, "id": webstore_id}, {"$set": updates})
    if changing:
        await _record_lifecycle_event(
            tenant_id=tenant_id, webstore_id=webstore_id, from_status=current, to_status=status,
            from_state=stage_of(store), to_state=updates["stage"], actor_id=actor_id, actor_email=actor_email,
            reason=reason, metadata={**(metadata or {}), "source": source},
        )
    updated = await db.webstores.find_one({"tenant_id": tenant_id, "id": webstore_id}, {"_id": 0})
    return serialize_doc(updated) if updated else None


__all__ = ["STAGES", "STAGE_LABELS", "RETIRED_STATUSES", "stage_of", "stage_view", "apply_store_status"]
