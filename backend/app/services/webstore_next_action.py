"""One next action per Webstore, shared by staff and the owner portal (Phase 3).

Read model only: computing the next action never writes. The order is the
Phase 2 customer journey first (packet → questionnaire → review), then the
existing launch gates (``webstore_launch_readiness``), then the live stages.

``sync_next_action_side_effects`` is called after changes (never on reads):
when the next action belongs to the shop it keeps exactly one open Task for
it, keyed so retries and reloads never duplicate, and closes the task once
the action moves on (D3-6).
"""
from __future__ import annotations

import asyncio
import logging
import re
import secrets
from datetime import timedelta
from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from .webstore_context import db, serialize_doc, utc_now
from .webstore_stage import stage_of, stage_view

logger = logging.getLogger(__name__)

TASK_TYPE = "webstore_next_action"
SYNC_LEASE = timedelta(seconds=30)
SYSTEM_ACTOR = {"id": "system", "email": "system", "role": "owner"}
SNAPSHOT_VERSION = 2
INFORMATIONAL_ACTIONS = frozenset({"none", "monitor_orders"})

# gate key -> (actor, tab, staff text); owner text comes from the gate's owner wording.
GATE_ACTIONS: dict[str, tuple[str, str, str]] = {
    "entitlement": ("shop", "overview", "Turn on the Webstores feature for this shop"),
    "owner_authorized": ("shop", "setup", "Give the store owner portal access"),
    "store_identity": ("shop", "setup", "Complete the store details"),
    "questionnaire_complete": ("owner", "setup", "Waiting for the owner's questionnaire"),
    "included_products_ready": ("shop", "products", "Build the products and mockups"),
    "branding_preview_complete": ("shop", "storefront", "Finish the storefront branding"),
    "packet_generated": ("shop", "review-launch", "Create the launch packet"),
    "packet_delivered": ("shop", "review-launch", "Send the launch packet to the owner"),
    "change_requests_resolved": ("shop", "review-launch", "Respond to the owner's change requests"),
    "packet_approved": ("owner", "review-launch", "Waiting for the owner to approve the launch packet"),
    "terms_current": ("owner", "review-launch", "Waiting for the owner to accept the terms"),
    "type_requirements": ("shop", "setup", "Complete the store-type details"),
    "payment_ready": ("shop", "review-launch", "Finish payment setup before publishing"),
}
GATE_ORDER = list(GATE_ACTIONS)
# The Phase 2 journey (packet, questionnaire, review) only applies before the owner reviews the store.
JOURNEY_STAGES = frozenset({"draft", "intake_pending", "setup_in_progress"})
OWNER_IDLE_TEXT = "Nothing is needed from you right now — the shop is working on your store."


def _action(key: str, actor: str, staff_text: str, owner_text: str, tab: str, occurrence: Any = "", blockers=None) -> dict[str, Any]:
    return {"key": key, "actor": actor, "staff_text": staff_text, "owner_text": owner_text, "tab": tab,
            "occurrence": str(occurrence or ""), "blockers": blockers or []}


async def _owner_can_reach_portal(store: dict) -> bool:
    """An active owner assignment, or an owner invitation that is still open."""
    tenant_id, webstore_id = store["tenant_id"], store["id"]
    now = utc_now().isoformat()
    async for assignment in db.webstore_access_assignments.find(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "role": "owner", "status": {"$in": ["active", "invited"]}},
        {"_id": 0, "status": 1, "invitation_id": 1},
    ):
        if assignment.get("status") == "active":
            return True
        invite = await db.webstore_invitations.find_one(
            {"tenant_id": tenant_id, "id": assignment.get("invitation_id")}, {"_id": 0, "status": 1, "expires_at": 1}
        ) if assignment.get("invitation_id") else None
        if invite and invite.get("status") not in {"expired", "revoked"} and str(invite.get("expires_at") or "") > now:
            return True
    return False


async def _journey_action(store: dict) -> Optional[dict[str, Any]]:
    action = await _journey_step(store)
    if action and action["actor"] == "owner" and not await _owner_can_reach_portal(store):
        return _action("owner_access", "shop", "Re-send the owner's portal invitation (it expired or was revoked)",
                       "The shop is setting up your access.", "setup")
    return action


async def _journey_step(store: dict) -> Optional[dict[str, Any]]:
    """The Phase 2 steps before the launch gates apply."""
    tenant_id, webstore_id = store["tenant_id"], store["id"]
    if not int((store.get("information_packet") or {}).get("sent_count") or 0):
        return _action("send_information_packet", "shop", "Send the information packet", "The shop is preparing your welcome packet.", "setup")
    latest = await db.webstore_questionnaire_submissions.find_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "revision": {"$ne": None}}, {"_id": 0, "status": 1, "revision": 1},
        sort=[("revision", -1)],
    )
    if not latest:
        return _action("owner_complete_questionnaire", "owner", "Waiting for the owner's questionnaire", "Complete your store questionnaire.", "setup")
    if latest.get("status") == "returned_for_changes":
        return _action("owner_update_questionnaire", "owner", "Waiting for the owner to update the questionnaire",
                       "The shop asked for changes to your questionnaire.", "setup", latest.get("revision"))
    if latest.get("status") == "submitted":
        return _action("review_questionnaire", "shop", f"Review questionnaire revision {latest.get('revision')}",
                       "The shop is reviewing your answers.", "setup", latest.get("revision"))
    return None


async def compute_next_action(store: dict, readiness: Optional[dict] = None) -> dict[str, Any]:
    stage = stage_of(store)
    if stage == "archived":
        return _action("none", "none", "Archived", "This store is archived.", "overview")
    if stage == "closed" and store.get("status") == "completed":
        return _action("none", "none", "Completed — prepare a relaunch or archive when ready", "This store is complete.", "overview")
    if stage == "closed" and store.get("status") != "relaunch_ready":
        return _action("review_closed_orders", "shop", "Ordering closed — finish production and fulfillment", "Ordering has closed.", "overview")
    if stage == "paused":
        return _action("resume_store", "shop", "Store is paused — resume or close it", "Your store is paused.", "review-launch")
    if stage == "live":
        return _action("monitor_orders", "shop", "Store is live — watch orders and production", "Your store is live.", "overview")
    journey = await _journey_action(store) if stage in JOURNEY_STAGES else None
    if journey:
        return journey
    if readiness is None:
        from .webstore_launch_readiness import _compat_launch_readiness

        readiness = await _compat_launch_readiness({**SYSTEM_ACTOR, "tenant_id": store["tenant_id"]}, store["id"], ensure_slug=False)
    gates = {gate["key"]: gate for gate in readiness.get("gates") or []}
    blockers = [
        {"key": key, "reason": gate.get("reason"), "owner_wording": gate.get("owner_wording")}
        for key, gate in gates.items() if gate.get("blocking") or (key == "payment_ready" and gate.get("state") != "ready")
    ]
    for key in GATE_ORDER:
        gate = gates.get(key)
        if not gate:
            continue
        failing = gate.get("blocking") or (key == "payment_ready" and gate.get("state") != "ready")
        if not failing:
            continue
        actor, tab, staff_text = GATE_ACTIONS[key]
        if key == "type_requirements":
            staff_text = gate.get("reason") or staff_text
        packet = readiness.get("current_packet") or {}
        return _action(key, actor, staff_text, gate.get("owner_wording") or OWNER_IDLE_TEXT, tab, packet.get("version") or store.get("stage_changed_at"), blockers)
    return _action("publish", "shop", "Ready to publish", "Your store is ready to open.", "review-launch", store.get("stage_changed_at"))


def staff_view(store: dict, action: dict) -> dict[str, Any]:
    return {"stage": stage_view(store), "next_action": {**{k: action[k] for k in ("key", "actor", "staff_text", "tab", "blockers")},
                                                      "requires_staff_task": requires_staff_task(action)},
            "assignee_user_id": store.get("assignee_user_id")}


def owner_view(store: dict, action: dict) -> dict[str, Any]:
    """Owner-safe: no staff blockers, and shop work shows as 'nothing needed from you'."""
    view = stage_view(store)
    return {
        "stage": {"key": view["key"], "label": view["owner_label"],
                  "path": [{"key": step["key"], "label": step["owner_label"]} for step in view["path"]]},
        "next_action": {
            "key": action["key"] if action["actor"] in {"owner", "none"} else "shop_working",
            "for_you": action["actor"] == "owner",
            "text": action["owner_text"] if action["actor"] in {"owner", "none"} or view["key"] in {"live", "closed", "paused", "archived"} else OWNER_IDLE_TEXT,
        },
    }


async def staff_next_action(user: dict, webstore_id: str) -> dict[str, Any]:
    from .webstore_shared_access import _require_staff_perm
    from .webstore_shared_repository import _get_store
    from ..core.permissions import Perm

    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _get_store(user["tenant_id"], webstore_id)
    return {"webstore_id": webstore_id, **staff_view(store, await compute_next_action(store))}


async def owner_next_action(identity: dict, webstore_id: str) -> dict[str, Any]:
    from .webstore_shared_access import _owner_portal_store

    store = await _owner_portal_store(identity, webstore_id)
    return {"webstore_id": webstore_id, **owner_view(store, await compute_next_action(store))}


async def with_derived_state(store: dict) -> dict:
    """Read projection: stage and setup state are derived, never stored by readers."""
    from .webstore_setup_progress import compute_setup_state

    return {**store, "stage": stage_of(store), "setup_state": await compute_setup_state(store)}


def task_key(store: dict, action: dict) -> str:
    return f"webstore:{store['id']}:next:{action['key']}:{action['occurrence']}"


def requires_staff_task(action: dict) -> bool:
    return action["actor"] == "shop" and action["key"] not in INFORMATIONAL_ACTIONS


def generated_task_query(tenant_id: str, webstore_id: str) -> dict:
    # The generated key survives a manual source/type edit. Keep the legacy
    # relation match as well so obsolete rows still close through task_service.
    return {"tenant_id": tenant_id, "$or": [
        {"idempotency_key": {"$regex": "^webstore:" + re.escape(webstore_id) + ":next:"}},
        {"webstore_id": webstore_id, "task_type": TASK_TYPE},
    ]}


def canonical_task_metadata(store: dict, action: dict) -> dict:
    return {"title": f"{store.get('name')}: {action['staff_text']}", "task_type": TASK_TYPE,
            "source_type": "webstore", "source_id": store["id"], "webstore_id": store["id"], "visibility": "staff"}


def list_snapshot(action: dict, stage: str, setup_state: str, gates: str) -> dict[str, Any]:
    """The compact next action stored on the Webstore for the list (written by sync only)."""
    return {k: action[k] for k in ("key", "actor", "staff_text", "tab", "blockers", "occurrence")} | {
        "stage": stage, "setup_state": setup_state, "gates": gates, "version": SNAPSHOT_VERSION,
    }


async def sync_snapshot(store: dict, action: dict) -> dict:
    from .webstore_setup_progress import compute_setup_state

    return {**list_snapshot(action, stage_of(store), await compute_setup_state(store), await external_gates(store)),
            "source_updated_at": str(store.get("updated_at") or ""), "assignee_user_id": store.get("assignee_user_id"),
            "store_name": store.get("name")}


async def external_gates(store: dict, *, payment: Optional[dict] = None, entitlements: Optional[dict] = None) -> str:
    """Fingerprint of the gates that change outside Webstore routes (subscription entitlement,
    payment provider). A snapshot taken under different values is stale."""
    from .entitlements import has_entitlement
    from .webstore_constants import WEBSTORES_FEATURE_KEY
    from .webstore_launch_state import _payment_readiness

    key = store.get("entitlement_feature_key") or WEBSTORES_FEATURE_KEY
    cache = entitlements if entitlements is not None else {}
    if key not in cache:
        cache[key] = await has_entitlement(tenant_id=store["tenant_id"], feature_key=key)
    payment = payment or await _payment_readiness(store)
    return f"{key}={int(cache[key])};payment={payment.get('state')}"


async def _active_assignee(tenant_id: str, store: dict) -> Optional[str]:
    user_id = store.get("assignee_user_id")
    if user_id and await db.users.find_one({"tenant_id": tenant_id, "id": user_id, "is_active": True}, {"_id": 1}):
        return user_id
    return None  # an assignee who left the shop never blocks the task


async def _auto_complete(tenant_id: str, task: dict, now: str) -> None:
    from .task_service import transition_task

    # Through the task service so the completion is audited and the assignee is told.
    await transition_task(tenant_id=tenant_id, task_id=task["id"], target="completed", actor_user_id="system", actor_email="system",
                          reason="Webstore next action moved on", system_complete=True)


async def _sync_once(tenant_id: str, webstore_id: str, lock: dict) -> Optional[dict[str, Any]]:
    store = await db.webstores.find_one({"tenant_id": tenant_id, "id": webstore_id}, {"_id": 0})
    if not store:
        return None
    store = serialize_doc(store)
    gates_before = await external_gates(store)
    action = await compute_next_action(store)
    wanted = task_key(store, action) if requires_staff_task(action) else None
    now = utc_now().isoformat()
    if wanted:
        from .task_service import assign_task, create_task, restore_task, update_task

        assignee = await _active_assignee(tenant_id, store)
        # A recurring condition gets a new occurrence. Completed/canceled rows
        # retain their completion timestamps and history instead of being reopened.
        previous = await db.tasks.find_one(
            {"tenant_id": tenant_id, "idempotency_key": {"$regex": "^" + re.escape(wanted) + "(?:$|:after:)"}},
            {"_id": 0}, sort=[("created_at", -1), ("id", -1)],
        )
        if previous:
            wanted = previous["idempotency_key"]
            if previous.get("status") in {"completed", "canceled"}:
                wanted += ":after:" + previous["id"]
        await _renew_lease(lock)
        task = await create_task(tenant_id=tenant_id, actor_user_id="system", actor_email="system", payload={
            "title": f"{store.get('name')}: {action['staff_text']}",
            "description": "Created from the Webstore's next action. It closes automatically when the step is done.",
            "task_type": TASK_TYPE,
            "source_type": "webstore",
            "source_id": webstore_id,
            "assigned_user_id": assignee,
            "visibility": "staff",
            "idempotency_key": wanted,
        })
        if task.get("archived_at"):
            # Archived by hand while the step is still pending: bring it back (one visible task).
            await _renew_lease(lock)
            task = await restore_task(tenant_id=tenant_id, task_id=task["id"], actor_user_id="system", actor_email="system")
        # A reused task is put back to its generated form (renamed store, or source/type edited by hand).
        canonical = canonical_task_metadata(store, action)
        drift = {k: v for k, v in canonical.items() if task.get(k) != v}
        if drift:
            if {"source_type", "source_id", "webstore_id"} & drift.keys():
                drift.update(source_type="webstore", source_id=webstore_id)
            await _renew_lease(lock)
            task = await update_task(tenant_id=tenant_id, task_id=task["id"], actor_user_id="system", actor_email="system", updates=drift)
        if task.get("assigned_user_id") != assignee or task.get("assigned_employee_id"):
            await _renew_lease(lock)
            await assign_task(tenant_id=tenant_id, task_id=task["id"], actor_user_id="system", actor_email="system", assigned_user_id=assignee)
    # Close superseded tasks only after the replacement exists, so a failure never leaves none.
    async for task in db.tasks.find(
        {**generated_task_query(tenant_id, webstore_id), "status": {"$nin": ["completed", "canceled"]},
         "idempotency_key": {"$ne": wanted}},
        {"_id": 0, "id": 1, "status": 1, "version": 1, "archived_at": 1},
    ):
        if task.get("archived_at"):
            from .task_service import restore_task
            await _renew_lease(lock)
            await restore_task(tenant_id=tenant_id, task_id=task["id"], actor_user_id="system", actor_email="system")
        await _renew_lease(lock)
        await _auto_complete(tenant_id, task, now)
    # Only a completed synchronization is a reusable success snapshot. A crash
    # before this point leaves the prior snapshot for the recovery path to detect.
    snapshot = await sync_snapshot(store, action)
    if snapshot["gates"] != gates_before:
        raise RuntimeError("Webstore gates changed during synchronization; retry")
    await _renew_lease(lock)
    await db.webstores.update_one({"tenant_id": tenant_id, "id": webstore_id}, {"$set": {"next_action_snapshot": snapshot}})
    return action


async def _sync_with_retry(tenant_id: str, webstore_id: str, lock: dict) -> Optional[dict[str, Any]]:
    for attempt in range(3):
        try:
            await _renew_lease(lock)
            action = await _sync_once(tenant_id, webstore_id, lock)
            await db.webstore_next_action_locks.update_one(lock, {"$unset": {"failed_at": "", "error": ""}})
            return action
        except _LeaseLost:
            raise  # a superseded holder must never retry writes
        except Exception as exc:  # noqa: BLE001 - transient failures are retried; the last one is recorded
            if attempt == 2:
                await db.webstore_next_action_locks.update_one(
                    lock, {"$set": {"failed_at": utc_now().isoformat(), "error": type(exc).__name__}}
                )
                raise
            await asyncio.sleep(0.2 * (attempt + 1))
    return None


class _LeaseLost(RuntimeError):
    pass


async def _renew_lease(lock: dict) -> None:
    now = utc_now()
    renewed = await db.webstore_next_action_locks.update_one(
        {**lock, "until": {"$gt": now.isoformat()}},
        {"$set": {"until": (now + SYNC_LEASE).isoformat()}},
    )
    if not renewed.matched_count:
        raise _LeaseLost("Webstore synchronization lease expired or changed owner")


async def _sync_with_lease(tenant_id: str, webstore_id: str, lock: dict) -> Optional[dict[str, Any]]:
    async def keep_lease():
        while True:
            await asyncio.sleep(SYNC_LEASE.total_seconds() / 3)
            await _renew_lease(lock)

    # Keep ownership while task auditing/notifications await I/O. Losing it
    # cancels outstanding work; every subsequent mutation also renews/checks it.
    work = asyncio.create_task(_sync_with_retry(tenant_id, webstore_id, lock))
    renewal = asyncio.create_task(keep_lease())
    try:
        done, _ = await asyncio.wait({work, renewal}, return_when=asyncio.FIRST_COMPLETED)
        if renewal in done:
            renewal.result()
        return work.result()
    finally:
        work.cancel()
        renewal.cancel()
        await asyncio.gather(work, renewal, return_exceptions=True)


async def _acquire(lock: dict, owner: str) -> bool:
    now = utc_now()
    try:
        await db.webstore_next_action_locks.update_one(
            {**lock, "until": {"$lt": now.isoformat()}},
            {"$set": {"until": (now + SYNC_LEASE).isoformat(), "owner": owner}, "$unset": {"pending": ""}},
            upsert=True,
        )
        return True
    except DuplicateKeyError:  # another sync holds an unexpired lease
        return False


async def sync_next_action_side_effects(tenant_id: str, webstore_id: str) -> Optional[dict[str, Any]]:
    """Keep exactly one open Task for the shop's next action. Best effort: never breaks the caller.

    Syncs for one Webstore are serialized with a short lease. A sync that finds
    the lease taken marks the Webstore pending, and the holder runs once more
    before releasing, so the last change always wins.
    """
    # Tenant-scoped lock: the structured _id cannot collide across tenants, and every query filters by tenant.
    lock = {"_id": {"tenant_id": tenant_id, "webstore_id": webstore_id}, "tenant_id": tenant_id, "webstore_id": webstore_id}
    action = None
    owner = secrets.token_hex(16)
    owned_lock = {**lock, "owner": owner}
    try:
        for _ in range(5):
            if not await _acquire(lock, owner):
                await db.webstore_next_action_locks.update_one(lock, {"$set": {"pending": True}})
                if not await _acquire(lock, owner):
                    return action  # the holder will see "pending" and run again
            try:
                action = await _sync_with_lease(tenant_id, webstore_id, owned_lock)
            finally:
                released = await db.webstore_next_action_locks.find_one_and_update(
                    owned_lock, {"$set": {"until": ""}},
                )
            if not (released or {}).get("pending"):
                return action
        return action
    except Exception:  # noqa: BLE001 - side effects must never fail the user's action
        logger.exception("Webstore next-action sync failed for %s", webstore_id)
        return None


__all__ = ["external_gates", "list_snapshot", "staff_next_action", "owner_next_action", "with_derived_state", "compute_next_action", "staff_view", "owner_view", "task_key", "sync_next_action_side_effects", "TASK_TYPE"]
