# EC5 — Production and Work Orders — PREFLIGHT

**Authority:** master build plan. Prereq: EC0-EC4 COMPLETE.

## 1. MVP files inspected
- `backend/app/models/work_order.py` — single `WorkOrder{tenant_id, number, order_id, customer_id, production_status, assigned_to, production_instructions, internal_notes, items_snapshot[]}`. `ProductionStatus = {not_started, in_progress, on_hold, completed}`. No priority, due date, versioning.
- `backend/app/routers/work_orders.py` — list/create/get/patch/production-status. Already filters `production_required=true` (EC3 fix). No duplicate-active guard, no supersede, no summary endpoint, no board endpoint.
- `frontend/src/pages/WorkOrders*.jsx` — list + detail exist.

## 2. Legacy job-ticket behaviour found
None. Terminology already conforms to Order / Work Order.

## 3. Donor evidence used (behavioural extraction only)
- REB Work Order status enum → adopt `draft/released/queued/in_progress/blocked/ready/completed/cancelled/superseded`.
- REB versioning pattern → `version, current_version, superseded_by, superseded_from`.

## 4. Classification
| Element | Class |
|---|---|
| Existing `production_status` enum | REBUILD (extend to 9-state enum) |
| Existing `items_snapshot: list[dict]` | KEEP MVP (already immutable-in-practice) |
| Existing `assigned_to: str` | REBUILD → `assigned_user_ids: list[str]` |
| No priority field | ADD |
| No due_date | ADD |
| No versioning | ADD |
| No summary endpoint | ADD |
| No board endpoint | ADD |
| No supersede/regenerate | ADD |
| No duplicate-active guard | ADD |

## 5. Schema additions (additive)
- `priority: low/normal/high/rush = normal`
- `due_date: str | None`
- `requested_date, released_at, started_at, ready_at, completed_at, cancelled_at`
- `cancel_reason, block_reason`
- `assigned_user_ids: list[str] = []`
- `department: str | None`
- `version: int = 1, current_version: bool = True`
- `superseded_by: str | None, superseded_from: str | None, supersede_reason: str | None`
- `snapshot_version: int = 1`
- Extended status enum (backwards compat via read-time map: `not_started→released`, `in_progress→in_progress`, `on_hold→blocked`, `completed→completed`)

## 6. Files to add/modify
**Modify:** `models/work_order.py`, `routers/work_orders.py`, `core/db.py` (indexes), `core/permissions.py` (verify WORK_ORDER perms already cover EC5 needs — they do).
**Add:** `services/work_order_service.py`, `services/work_order_summary.py`, `routers/production.py` (board), `tests/test_work_orders_ec5.py`. Docs under `/app/docs/`.

## 7. Rules
- One active Work Order per Order (unique compound `(tenant_id, order_id, current_version=True)` guard via find_one_and_update).
- Regenerate creates a new version, marks prior `current_version=False, superseded_by=new_id`. Reason required.
- Snapshot fields immutable after `released`.
- Board endpoint groups Work Orders by status (view over the `work_orders` collection — no new collection).
- Summary endpoint returns tenant-safe production data only (excludes `unit_price_cents` unless caller has explicit `invoice:read` or `pricing:read` permission).
- Compatibility: existing rows read via a `_effective_status()` helper that maps old enum → new enum.

## 8. Test plan
- Generation rejects Order with no production-required items.
- Duplicate active generation returns existing WO with `already_exists=true`.
- Regenerate marks old `current_version=False`, creates new version.
- Snapshot immutable — modifying source Order Item after release doesn't mutate snapshot.
- Transitions enforced (invalid → 400, blocked/cancelled require reason).
- Assignment across tenants rejected.
- Summary excludes `unit_price_cents` from response.

## 9. Compatibility
Additive. Read-time enum map covers all legacy statuses. No migration required.

## 10. Rollback
Revert new files + additive lines in model/router/db.py.

Sign-off: preflight complete. Proceeding.
