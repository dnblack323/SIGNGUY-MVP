# Work Orders Module (EC5)

**Owner checkpoint:** EC5.

## Model

`backend/app/models/work_order.py::WorkOrder` — lifecycle, priority, due dates, assignment, versioning, immutable item snapshots.

Statuses: `draft, released, queued, in_progress, blocked, ready, completed, cancelled, superseded`. Legacy `not_started/on_hold` map to `released/blocked` on read via `effective_status`.

Priority: `low, normal, high, rush`.

## Endpoints

- `GET /api/work-orders` (filters: production_status, order_id, customer_id, current_only)
- `POST /api/work-orders` (generate from Order; duplicate-active returns existing with `already_exists=true`)
- `GET /api/work-orders/{id}`
- `PATCH /api/work-orders/{id}` (mutable fields only — snapshot commercial content is immutable after release)
- `POST /api/work-orders/{id}/transition` (allowed transitions enforced; blocked + cancelled require reason)
- `POST /api/work-orders/{id}/production-status` (legacy — maps old enum to new)
- `POST /api/work-orders/{id}/assign` (list of tenant user IDs; cross-tenant rejected; new assignees notified)
- `POST /api/work-orders/{id}/regenerate` (reason required; new version created, prior superseded)
- `GET /api/work-orders/{id}/summary` (tenant-safe printable JSON; excludes pricing unless caller has `invoice:read`)
- `GET /api/production/board` (grouped view by status; filters: customer_id, priority, assigned_user_id)

## Rules

- Only `production_required=true` Order Items enter the snapshot.
- No production items → generation rejected (400).
- Duplicate active generation returns the existing `current_version=true` Work Order.
- Snapshot commercial content is immutable after release; source Order edits do not alter the snapshot.
- Regenerate marks the prior version `current_version=false, superseded_by=<new>`; history preserved.
- Transitions coordinate Order operational status through the service (`released→confirmed, in_progress→in_production, ready→ready, completed→completed`). Financial state untouched.
