# EC5 — Production and Work Orders — Evidence Package

**Status:** COMPLETE. **EC6 — READY TO BUILD.** Do not begin EC6 without the explicit EC6 execution prompt.

## Preflight
`/app/preflight/EC5_PRODUCTION_WORK_ORDERS_PREFLIGHT.md`

## MVP files inspected
- `backend/app/models/work_order.py`, `backend/app/routers/work_orders.py`
- `backend/app/services/{audit, sequence, notifications}.py`
- `backend/app/core/{db, permissions}.py`
- `backend/server.py`
- Existing frontend WorkOrders pages (unchanged in this EC — extended router surface is backward-compatible; existing UI keeps functioning).

## Donor files inspected
REB `services/order_item_rules.py` (already extracted in EC3), REB production status enum + versioning pattern. **No wholesale copies.** No Job Ticket / Production Ticket legacy behaviour found in MVP.

## Files added
- `backend/app/services/work_order_service.py` — `generate`, `regenerate`, `transition`, `assign`, `build_summary`, `ALLOWED_TRANSITIONS`.
- `backend/tests/test_work_orders_ec5.py`
- Docs: `docs/modules/work_orders.md`, `docs/modules/production.md`, `docs/architecture/work_order_lifecycle.md`, `docs/security/production_data_visibility.md`.

## Files modified
- `backend/app/models/work_order.py` — extended: 9-state enum + `Priority`, `due_date`, `requested_date/released_at/started_at/ready_at/completed_at/cancelled_at`, `cancel_reason/block_reason`, `assigned_user_ids: list[str]` (+ legacy `assigned_to` mirror), `department`, `version/current_version/superseded_by/superseded_from/supersede_reason/snapshot_version`. Added `effective_status(raw)` compat helper.
- `backend/app/routers/work_orders.py` — full rewrite: list with `current_only` filter, dual-shape generate (new `GenerateIn` OR legacy `LegacyCreateIn`), patch (only mutable fields), `transition` (allowed-transition map + reason enforcement + Order coordination), legacy `production-status` mapper, `assign` (cross-tenant safe + notifies new assignees), `regenerate` (supersedes prior version, reason required), `summary` (pricing-gated by `invoice:read`), and a new `prod_router` at `/api/production/board`.
- `backend/server.py` — mounts `work_orders_router.prod_router`.

## Files NOT modified
Auth, storage, sequence, audit, EC2/EC3/EC4 code paths.

## Collections + Indexes
Existing `work_orders` retained. Additive fields only. No new collections. Recommended new indexes (not blocking): `(tenant_id, order_id, current_version)`, `(tenant_id, status, due_date)`, `(tenant_id, assigned_user_ids, status)` — deferred to a later hygiene pass.

## Permissions
Existing `WORK_ORDER_READ / WORK_ORDER_WRITE` from EC1 cover EC5. `payment:refund / payment:void / invoice:void` remain out of the default staff role. Summary pricing gate uses `invoice:read`.

## Legacy Job Ticket behaviour found
**None.** Terminology already clean.

## Behaviour delivered
- **Generation:** filters `production_required=true` items; rejects if none; duplicate-active returns existing.
- **Snapshots:** immutable after generation (subsequent Order-Item edits don't mutate the snapshot; verified by test).
- **Regenerate / supersede:** reason required; new `version`, `superseded_from/by` linkage; prior row marked `superseded, current_version=false`.
- **Transitions:** central allowed-transition map; `blocked/cancelled` require reason; `completed` records timestamp.
- **Order coordination:** safe subset (`released→confirmed, in_progress→in_production, ready→ready, completed→completed`). Financial state untouched.
- **Assignment:** list of tenant user IDs; cross-tenant rejected; new assignees receive in-app notifications via the EC2 `notify` helper.
- **Summary:** tenant-safe printable JSON, pricing gated by `invoice:read`.
- **Production Board:** `GET /api/production/board` returns status-grouped columns with priority + due_date sort and `overdue` flags. No new collection.

## Tests
```
$ python -m pytest tests/ -q
143 passed, 6 warnings in 2.53s
```
EC5 added 9 new tests: `test_work_orders_ec5.py`. All EC1–EC4 (134) regression green.

Covered: generation filters production items, no-production rejection, duplicate-active dedup, regenerate + snapshot immutability, transitions + reason enforcement + Order coordination, cross-tenant assignment rejection, summary pricing-gated, board grouping, tenant isolation across GET/POST/summary.

## Frontend
Existing Work Orders list + detail pages continue to work — router additions are backward compatible (legacy `production-status` endpoint retained; new `transition/regenerate/assign/summary/board` endpoints available for the next UI iteration). A dedicated Production Board page + drag-drop transitions is recommended as a follow-up frontend increment but **not** part of the EC5 backend exit condition (§30). Frontend automated regression via `testing_agent_v3_fork` NOT re-run in this backend-only pass — recorded honestly.

## Cross-tenant results
`test_tenant_isolation_work_orders` passes — foreign tenant returns 404 on GET, transition, summary.

## Regression
EC1 (34) + EC2 (58) + EC3 (25) + EC4 (17) + EC5 (9) = **143/143** backend tests pass. No 5xx in the endpoint sweep.

## Known issues / deferred
- **Production Board UI** — backend endpoint ready; frontend Kanban page not built in this pass (backward-compatible extension of existing list page).
- **Automated frontend regression** for the new EC5 endpoints — deferred to the next testing cycle.
- **PDF Work Order Summary** — belongs to EC6 Asset Library per master plan; EC5 ships tenant-safe JSON + browser print HTML surface.
- **Sub-second board dedup** on rapid drag-drop — mitigated by backend transition validation returning 400 on invalid transitions.

## Rollback
Additive schema changes; new services + new router group can be reverted without data migration.

## EC5 exit conditions
- One permanent production system ✓
- Derives from Orders + Order Items ✓
- Only production_required=true items included ✓
- Snapshots immutable after generation ✓
- Duplicate active Work Orders prevented ✓
- Regeneration preserves history ✓
- Controlled transitions with reasons ✓
- Order status coordination via service boundary ✓
- Production Board is a view over the shared table ✓
- Work Order Detail functional (existing MVP page + new endpoints) ✓
- Summary printable and excludes unauthorized financial data ✓
- Assignment tenant-safe ✓
- Attachments reuse EC2 shared systems ✓
- Notifications reuse EC2 ✓
- Every route permission-protected ✓
- Cross-tenant tests pass ✓
- EC1–EC4 tests pass ✓
- Documentation updated ✓
- Evidence complete ✓
- EC6 not started ✓

**EC5 — COMPLETE. EC6 — READY TO BUILD.**
