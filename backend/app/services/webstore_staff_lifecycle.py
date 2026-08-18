"""Staff Webstore lifecycle status transitions and lifecycle event reads."""
from __future__ import annotations

from .webstore_shared import *
from .webstore_launch import _compat_launch_readiness, launch_readiness


async def set_webstore_status(user: dict, webstore_id: str, status: str, reason: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE if status in {"live", "launch_ready", "scheduled", "paused", "closed", "archived"} else Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    _validate_status_change(store.get("status", "draft"), status)
    if status == "scheduled":
        raise WebstoreError(
            "webstore_scheduling_deferred",
            "Webstore scheduling is handled after the public storefront checkpoint.",
            409,
        )
    if status in {"launch_ready", "scheduled", "live"}:
        readiness = await _compat_launch_readiness(user, webstore_id)
        if not readiness["ready"]:
            raise WebstoreError("launch_gates_failed", "Webstore launch gates are not satisfied", 409)
    updates: dict[str, Any] = {"status": status}
    if status == "live":
        updates["launched_at"] = _now_iso()
        updates["checkout_enabled"] = bool(readiness["payment_readiness"]["provider_authority"])
    elif status == "launch_ready":
        updates["checkout_enabled"] = False
    elif status == "scheduled":
        updates["checkout_enabled"] = False
        updates["scheduled_at"] = _now_iso()
    elif status == "paused":
        updates["checkout_enabled"] = False
    elif status == "closed":
        updates["closed_at"] = _now_iso()
        updates["checkout_enabled"] = False
    elif status == "archived":
        updates["archived_at"] = _now_iso()
        updates["checkout_enabled"] = False
    updated = await stores_repo.update(tenant_id=user["tenant_id"], entity_id=webstore_id, updates=updates)
    from_state = _phase6_state_for_status(store.get("status", "draft"))
    to_state = _phase6_state_for_status(status)
    await _record_lifecycle_event(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        from_status=store.get("status"),
        to_status=status,
        from_state=from_state,
        to_state=to_state,
        actor_id=user["id"],
        actor_email=user.get("email"),
        reason=reason,
        metadata={"source": "status_route"},
    )
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action=f"webstore.status.{status}",
        entity_type="webstore",
        entity_id=webstore_id,
        summary=f"Webstore status changed from {store.get('status')} to {status}",
        metadata={"from": store.get("status"), "to": status, "reason": reason},
    )
    return updated or {}


async def relaunch_webstore(user: dict, webstore_id: str, reason: Optional[str] = None) -> dict:
    """Re-check current launch evidence before reopening a completed store."""
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    store = await _get_store(user["tenant_id"], webstore_id)
    current_status = store.get("status", "draft")
    if current_status not in {"closed", "completed", "relaunch_ready"}:
        raise WebstoreError(
            "invalid_relaunch_status",
            "Only closed or completed Webstores can be relaunched",
            409,
        )
    close_at = store.get("deadline_at") or store.get("intended_close_at")
    if close_at:
        try:
            close_time = datetime.fromisoformat(str(close_at).replace("Z", "+00:00"))
            if close_time.tzinfo and close_time <= datetime.now(timezone.utc):
                raise WebstoreError(
                    "relaunch_deadline_passed",
                    "Update the Webstore closing date before relaunching it",
                    409,
                )
        except ValueError:
            pass
    readiness = await _compat_launch_readiness(user, webstore_id)
    if not readiness["ready"]:
        raise WebstoreError(
            "launch_gates_failed",
            "Current catalog, branding, approval, payment, and date gates must pass before relaunch",
            409,
        )
    if current_status != "relaunch_ready":
        _validate_status_change(current_status, "relaunch_ready")
    updated = await stores_repo.update(
        tenant_id=user["tenant_id"],
        entity_id=webstore_id,
        updates={
            "status": "relaunch_ready",
            "checkout_enabled": False,
            "relaunch_requested_at": _now_iso(),
        },
    )
    await _record_lifecycle_event(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        from_status=current_status,
        to_status="relaunch_ready",
        from_state=_phase6_state_for_status(current_status),
        to_state="closed",
        actor_id=user["id"],
        actor_email=user.get("email"),
        reason=reason,
        metadata={"source": "relaunch_route", "readiness_rechecked": True},
    )
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.relaunch.requested",
        entity_type="webstore",
        entity_id=webstore_id,
        summary="Webstore relaunch readiness passed",
        metadata={"from_status": current_status, "to_status": "relaunch_ready"},
    )
    return {"webstore": updated or {}, "readiness": readiness, "lifecycle_state": "closed"}


async def transition_webstore_lifecycle(user: dict, webstore_id: str, lifecycle_state: str, reason: Optional[str] = None) -> dict:
    requested_state = (lifecycle_state or "").strip().lower().replace("-", "_")
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE if requested_state in {"ready_to_launch", "live", "closed", "archived"} else Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    current_state = _phase6_state_for_status(store.get("status", "draft"))
    target_status = PHASE6_TO_INTERNAL_STATUS[requested_state]
    _validate_status_change(store.get("status", "draft"), target_status)
    if requested_state in {"ready_to_launch", "live"}:
        readiness = await _compat_launch_readiness(user, webstore_id)
        if not readiness["ready"]:
            raise WebstoreError("launch_gates_failed", "Webstore launch gates are not satisfied", 409)
    updates: dict[str, Any] = {"status": target_status}
    if target_status == "live":
        updates["launched_at"] = _now_iso()
        updates["checkout_enabled"] = bool(readiness["payment_readiness"]["provider_authority"])
    elif target_status in {"launch_ready", "approved"}:
        updates["checkout_enabled"] = False
    elif target_status == "closed":
        updates["closed_at"] = _now_iso()
        updates["checkout_enabled"] = False
    elif target_status == "archived":
        updates["archived_at"] = _now_iso()
        updates["checkout_enabled"] = False
    updated = await stores_repo.update(tenant_id=user["tenant_id"], entity_id=webstore_id, updates=updates)
    event = await _record_lifecycle_event(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        from_status=store.get("status"),
        to_status=target_status,
        from_state=current_state,
        to_state=requested_state,
        actor_id=user["id"],
        actor_email=user.get("email"),
        reason=reason,
        metadata={"source": "phase6_lifecycle_route"},
    )
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal_webstore_owner",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.lifecycle.transitioned",
        entity_type="webstore",
        entity_id=webstore_id,
        summary=f"Webstore lifecycle changed from {current_state} to {requested_state}",
        metadata={"from_state": current_state, "to_state": requested_state, "from_status": store.get("status"), "to_status": target_status, "reason": reason},
    )
    return {"webstore": updated or {}, "lifecycle_state": requested_state, "event": event}


async def list_lifecycle_events(user: dict, webstore_id: str, *, limit: int = 30) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _get_store(user["tenant_id"], webstore_id)
    safe_limit = max(1, min(limit, 100))
    items = [
        serialize_doc(doc)
        async for doc in db.webstore_lifecycle_events.find(
            {"tenant_id": user["tenant_id"], "webstore_id": store["id"]},
            {"_id": 0},
        ).sort([("created_at", -1)]).limit(safe_limit)
    ]
    return {"items": items}

__all__ = ['set_webstore_status', 'relaunch_webstore', 'transition_webstore_lifecycle', 'list_lifecycle_events']
