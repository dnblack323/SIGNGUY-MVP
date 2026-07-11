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
EC5 frontend delivered in-full (iteration 7 + 8 automated `testing_agent_v3_fork` runs, 100% pass on iteration 8):

- **Production Board (`/work-orders/board`)** — Kanban with 7 columns over `GET /api/production/board`, HTML5 drag-and-drop between columns (`work_order:write` gated), inline reason-required modal for `blocked`/`cancelled` drops, priority/assignee filters, overdue chips + assignee chips + item counts.
- **Work Order Detail rebuilt** — 9-state status pill + priority pill, `v{n}` version badge, allowed-transitions-only sidebar buttons, reason-required modal for blocked/cancelled, per-status `wo-transition-{state}` testids. Superseded banner (v1 side) + "regenerated from earlier version" banner (new side) with links across the version chain.
- **Generate Work Order UX** — `GenerateWorkOrderDialog` on Order Detail collects priority / due date / instructions / internal notes / assignees; graceful `already_exists=true` handling.
- **Regenerate / Supersede UX** — button on both Work Order Detail header (disabled on terminal / superseded rows) AND Order Detail (when active current-version WO exists). Reason-required modal calls `/regenerate`; user is redirected to the new version.
- **Assignment UI** — `AssignDialog` multi-select over `/users`; server-side notifications via EC2 helper.
- **Printable Summary** — `PrintSummaryDialog` opens from the WO detail header, injects scoped `@media print` CSS to isolate the print region, and calls `window.print()`. Pricing columns render only when the caller carries `invoice:read`.
- **Work Orders list** — 9-state filters (`wo-filter-{state}`), `current_only` toggle (default on), priority + due + version chips inline.
- **Sidebar** — Production Board link added under Shop Operations flyout (`flyout-production-board`).
- **Permissions** — all UI controls gated on `/auth/me` payload (`work_order:read`, `work_order:write`, `invoice:read`) — no hardcoded role strings.
- **A11y** — DialogDescription added on Generate / Regenerate / TransitionReason / Assign / Print / Board reason dialogs (Radix aria warnings cleared).

## Automated frontend regression
`testing_agent_v3_fork` iteration 7 → 8:
- Iteration 7: functional coverage of all 8 review flows; found 5 issues (1 backend summary permissions gap, 1 regen redirect wiring, 3 cosmetic/a11y). All fixed.
- Iteration 8: 100% pass on all 5 fixes + regression flows. No new issues.
- Report files: `/app/test_reports/iteration_7.json`, `/app/test_reports/iteration_8.json`.

## Backend adjustment during EC5 corrections
- `GET /api/work-orders/{id}/summary` now derives permissions from the caller's `role` when the auth dependency does not expose an explicit `permissions` list (tests can still override via a `permissions` field on the dependency-overridden user). Owner role now correctly receives `unit_price_cents` on summary items. All 143 backend tests remain green after the fix.

## Cross-tenant results
`test_tenant_isolation_work_orders` passes — foreign tenant returns 404 on GET, transition, summary.

## Regression
EC1 (34) + EC2 (58) + EC3 (25) + EC4 (17) + EC5 (9) = **143/143** backend tests pass. No 5xx in the endpoint sweep.

## Known issues / deferred
- **PDF Work Order Summary** — belongs to EC6 Asset Library per master plan; EC5 ships tenant-safe JSON + `window.print()` HTML surface via `PrintSummaryDialog`.
- **Board card polish (real-time refetch on drag conflicts)** — mitigated by backend transition validation returning 400 on invalid transitions; drag conflicts surface as toasts.

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
