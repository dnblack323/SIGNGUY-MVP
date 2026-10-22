"""Recover derived Webstore tasks through the existing serialized sync.

Called after external gate writes and by an authorized staff POST. GET readers
remain read-only. No scheduler, queue, lifecycle or task store is introduced.
"""
from __future__ import annotations

import asyncio
import logging
import re

from .webstore_context import db, serialize_doc, utc_now
from .webstore_next_action import (
    _active_assignee, canonical_task_metadata, compute_next_action, generated_task_query,
    requires_staff_task, sync_next_action_side_effects, sync_snapshot, task_key,
)
from .webstore_stage import stage_of

logger = logging.getLogger(__name__)
GATE_RECOVERY_TIMEOUT_SECONDS = 1.0
GATE_RECOVERY_MAX_STORES = 25


async def reconcile_after_gate_change(tenant_id: str, *, webstore_id: str | None = None) -> None:
    """A projection outage must not turn a successful entitlement/provider write into an error."""
    try:
        # Billing webhooks await this hook: never let a large tenant/history or
        # slow task service hold acknowledgement for a full recovery scan.
        # Incomplete work retains its stale snapshot for staff entry/Refresh.
        async with asyncio.timeout(GATE_RECOVERY_TIMEOUT_SECONDS):
            await reconcile_next_actions(tenant_id, webstore_id=webstore_id, gate_change=True)
    except TimeoutError:
        logger.warning("Webstore gate recovery budget reached for tenant %s; staff recovery remains available", tenant_id)
    except Exception:
        logger.exception("Webstore task recovery unavailable for tenant %s", tenant_id)


async def reconcile_next_actions(tenant_id: str, *, webstore_id: str | None = None, gate_change: bool = False) -> dict[str, int]:
    """Retry stale/failed/interrupted projections for exactly one tenant.

    Repeated calls are safe: existing task keys and per-store leases arbitrate
    writes. A still-running lease is left pending rather than reported repaired.
    A process killed before its snapshot write is detected by projection/task
    mismatch, and an expired unreleased lease is also a recovery candidate.
    """
    result = {"checked": 0, "recovered": 0, "pending": 0, "failed": 0}
    query = {"tenant_id": tenant_id}
    if webstore_id is not None:
        query["id"] = webstore_id
    if gate_change:
        from .webstore_context import INTERNAL_STATUS_TO_PHASE6

        query["status"] = {"$nin": [status for status, stage in INTERNAL_STATUS_TO_PHASE6.items()
                                      if stage in {"live", "paused", "closed", "archived"}]}
    cursor = db.webstores.find(query, {"_id": 0})
    if gate_change:
        cursor = cursor.limit(GATE_RECOVERY_MAX_STORES)
    async for raw in cursor:
        if gate_change and stage_of(raw) in {"live", "paused", "closed", "archived"}:
            continue
        result["checked"] += 1
        store = serialize_doc(raw)
        try:
            action = await compute_next_action(store)
            expected = await sync_snapshot(store, action)
            lock = await db.webstore_next_action_locks.find_one(
                {"tenant_id": tenant_id, "webstore_id": store["id"]}, {"_id": 0},
            ) or {}
            tasks = [t async for t in db.tasks.find(
                {**generated_task_query(tenant_id, store["id"]),
                 "status": {"$nin": ["completed", "canceled"]}}, {"_id": 0},
            )]
            if requires_staff_task(action):
                prefix = task_key(store, action)
                canonical = {**canonical_task_metadata(store, action),
                             "assigned_user_id": await _active_assignee(tenant_id, store), "assigned_employee_id": None}
                correct_tasks = len(tasks) == 1 and re.match(
                    "^" + re.escape(prefix) + "(?:$|:after:)", tasks[0].get("idempotency_key") or "",
                ) and not tasks[0].get("archived_at") and all(tasks[0].get(k) == v for k, v in canonical.items())
            else:
                correct_tasks = not tasks
            if (store.get("next_action_snapshot") == expected and correct_tasks
                    and not lock.get("failed_at") and not lock.get("pending") and not lock.get("until")):
                continue
            action = await sync_next_action_side_effects(tenant_id, store["id"])
            lock = await db.webstore_next_action_locks.find_one(
                {"tenant_id": tenant_id, "webstore_id": store["id"]}, {"_id": 0},
            ) or {}
            if lock.get("failed_at"):
                result["failed"] += 1
            elif action is None or lock.get("pending") or str(lock.get("until") or "") > utc_now().isoformat():
                result["pending"] += 1
            else:
                result["recovered"] += 1
        except Exception:  # one broken projection cannot block billing or the remaining stores
            logger.exception("Webstore task recovery failed for tenant %s store %s", tenant_id, store["id"])
            result["failed"] += 1
    return result
