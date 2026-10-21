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

import logging
from typing import Any, Optional

from .webstore_context import db, serialize_doc, utc_now
from .webstore_stage import stage_of, stage_view

logger = logging.getLogger(__name__)

TASK_TYPE = "webstore_next_action"
SYSTEM_ACTOR = {"id": "system", "email": "system", "role": "owner"}

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
OWNER_IDLE_TEXT = "Nothing is needed from you right now — the shop is working on your store."


def _action(key: str, actor: str, staff_text: str, owner_text: str, tab: str, occurrence: Any = "", blockers=None) -> dict[str, Any]:
    return {"key": key, "actor": actor, "staff_text": staff_text, "owner_text": owner_text, "tab": tab,
            "occurrence": str(occurrence or ""), "blockers": blockers or []}


async def _journey_action(store: dict) -> Optional[dict[str, Any]]:
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
    if stage == "closed":
        return _action("review_closed_orders", "shop", "Ordering closed — finish production and fulfillment", "Ordering has closed.", "overview")
    if stage == "paused":
        return _action("resume_store", "shop", "Store is paused — resume or close it", "Your store is paused.", "review-launch")
    if stage == "live":
        return _action("monitor_orders", "shop", "Store is live — watch orders and production", "Your store is live.", "overview")
    journey = await _journey_action(store)
    if journey:
        return journey
    if readiness is None:
        from .webstore_launch_readiness import _compat_launch_readiness

        readiness = await _compat_launch_readiness({**SYSTEM_ACTOR, "tenant_id": store["tenant_id"]}, store["id"])
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
    return {"stage": stage_view(store), "next_action": {k: action[k] for k in ("key", "actor", "staff_text", "tab", "blockers")},
            "assignee_user_id": store.get("assignee_user_id")}


def owner_view(store: dict, action: dict) -> dict[str, Any]:
    """Owner-safe: no staff blockers, and shop work shows as 'nothing needed from you'."""
    view = stage_view(store)
    return {
        "stage": {"key": view["key"], "label": view["owner_label"]},
        "next_action": {
            "key": action["key"] if action["actor"] == "owner" else "shop_working",
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


async def sync_next_action_side_effects(tenant_id: str, webstore_id: str) -> Optional[dict[str, Any]]:
    """Keep exactly one open Task for the shop's next action. Best effort: never breaks the caller."""
    try:
        store = await db.webstores.find_one({"tenant_id": tenant_id, "id": webstore_id}, {"_id": 0})
        if not store:
            return None
        store = serialize_doc(store)
        action = await compute_next_action(store)
        wanted = task_key(store, action) if action["actor"] == "shop" and action["key"] != "none" else None
        now = utc_now().isoformat()
        async for task in db.tasks.find(
            {"tenant_id": tenant_id, "webstore_id": webstore_id, "task_type": TASK_TYPE, "status": {"$nin": ["completed", "canceled"]}},
            {"_id": 0, "id": 1, "idempotency_key": 1, "status": 1},
        ):
            if task.get("idempotency_key") != wanted:
                await db.tasks.update_one(
                    {"tenant_id": tenant_id, "id": task["id"]},
                    {"$set": {"status": "completed", "completed_at": now, "updated_at": now},
                     "$push": {"status_history": {"from": task.get("status"), "to": "completed", "at": now, "actor_user_id": "system",
                                                  "reason": "Webstore next action moved on"}}},
                )
        if wanted:
            from .task_service import create_task

            task = await create_task(tenant_id=tenant_id, actor_user_id="system", actor_email="system", payload={
                "title": f"{store.get('name')}: {action['staff_text']}",
                "description": "Created from the Webstore's next action. It closes automatically when the step is done.",
                "task_type": TASK_TYPE,
                "source_type": "webstore",
                "source_id": webstore_id,
                "assigned_user_id": store.get("assignee_user_id"),
                "visibility": "staff",
                "idempotency_key": wanted,
            })
            fixes: dict[str, Any] = {}
            if task.get("status") in {"completed", "canceled"}:
                fixes["status"] = "not_started"  # the same step is pending again
            if task.get("assigned_user_id") != store.get("assignee_user_id"):
                fixes["assigned_user_id"] = store.get("assignee_user_id")
            if fixes:
                await db.tasks.update_one(
                    {"tenant_id": tenant_id, "id": task["id"]},
                    {"$set": {**fixes, "updated_at": now},
                     "$push": {"status_history": {"from": task.get("status"), "to": fixes.get("status", task.get("status")), "at": now,
                                                  "actor_user_id": "system", "reason": "Webstore next action is pending"}}},
                )
        return action
    except Exception:  # noqa: BLE001 - side effects must never fail the user's action
        logger.exception("Webstore next-action sync failed for %s", webstore_id)
        return None


__all__ = ["staff_next_action", "owner_next_action", "with_derived_state", "compute_next_action", "staff_view", "owner_view", "task_key", "sync_next_action_side_effects", "TASK_TYPE"]
