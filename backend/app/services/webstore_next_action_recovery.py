"""Recover derived Webstore tasks through the existing serialized sync.

Called after external gate writes and by an authorized staff POST. GET readers
remain read-only. No scheduler, queue, lifecycle or task store is introduced.
"""
from __future__ import annotations

import logging
import re

from .webstore_context import db, serialize_doc, utc_now
from .webstore_next_action import (
    TASK_TYPE, compute_next_action, requires_staff_task, sync_next_action_side_effects,
    sync_snapshot, task_key,
)

logger = logging.getLogger(__name__)


async def reconcile_after_gate_change(tenant_id: str, *, webstore_id: str | None = None) -> None:
    """A projection outage must not turn a successful entitlement/provider write into an error."""
    try:
        await reconcile_next_actions(tenant_id, webstore_id=webstore_id)
    except Exception:
        logger.exception("Webstore task recovery unavailable for tenant %s", tenant_id)


async def reconcile_next_actions(tenant_id: str, *, webstore_id: str | None = None) -> dict[str, int]:
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
    async for raw in db.webstores.find(query, {"_id": 0}):
        result["checked"] += 1
        store = serialize_doc(raw)
        try:
            action = await compute_next_action(store)
            expected = await sync_snapshot(store, action)
            lock = await db.webstore_next_action_locks.find_one(
                {"tenant_id": tenant_id, "webstore_id": store["id"]}, {"_id": 0},
            ) or {}
            tasks = [t async for t in db.tasks.find(
                {"tenant_id": tenant_id, "webstore_id": store["id"], "task_type": TASK_TYPE,
                 "status": {"$nin": ["completed", "canceled"]}}, {"_id": 0},
            )]
            if requires_staff_task(action):
                prefix = task_key(store, action)
                correct_tasks = len(tasks) == 1 and re.match(
                    "^" + re.escape(prefix) + "(?:$|:after:)", tasks[0].get("idempotency_key") or "",
                ) and not tasks[0].get("archived_at")
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
