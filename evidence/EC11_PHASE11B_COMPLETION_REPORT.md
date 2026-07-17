# EC11 Phase 11B Completion Report

**Phase:** EC11 Phase 11B - Production Timeline and Event History Foundation  
**Status:** COMPLETE  
**Date:** 2026-07-16  
**Branch:** `codex-branch`

## Scope Completed

Phase 11B added a canonical read-only production timeline/history layer across:

- Orders
- Order Items
- Work Orders

The timeline projects existing authoritative records rather than creating a second general audit system or a new event collection.

## Backend

Added staff-only timeline endpoints:

- `GET /api/orders/{order_id}/timeline`
- `GET /api/orders/{order_id}/items/{item_id}/timeline`
- `GET /api/work-orders/{work_order_id}/timeline`

The service projects existing source records from:

- `orders`
- `order_items`
- `work_orders`
- `proofs`
- `proof_versions`
- `approvals`
- `attachments`
- `files`
- `invoices`
- `payments`
- `audit_events`

Supported normalized timeline fields include:

- deterministic `id`
- tenant and source identifiers
- order, order item, and work order linkage
- event type/category
- actor fields
- title
- customer-safe summary
- internal summary
- occurrence timestamp
- status transition fields where known
- related file/proof/invoice/payment/workflow identifiers
- allowlisted metadata
- frontend link contract
- visibility label

Supported retrieval/filter behavior:

- order timeline
- order item timeline
- work order timeline
- newest-first default sorting
- ascending sorting
- pagination by `limit` and `offset`
- `event_category`
- `event_type`
- `date_from`
- `date_to`
- `actor`
- `visibility`

## Deduplication

The Phase 11B service uses deterministic event identity and source priority:

1. Direct domain records are preferred for lifecycle facts.
2. Audit records fill transition/update facts and actor context.
3. Activity feed records are reserved as lowest-priority display facts.

Singleton lifecycle events are deduped by:

- `source_type`
- `source_id`
- `event_type`

Transition/update events additionally include timestamp/status sequence so repeated legitimate status changes are not collapsed.

## Frontend

Added a compact reusable `ProductionTimeline` component and wired it into:

- Order detail Activity tab
- Work Order detail Activity tab

The UI includes:

- newest-first list
- category filter
- event icons
- actor/timestamp/visibility display
- title and internal summary
- related links
- loading state
- empty state
- error state
- previous/next pagination

The existing pages were not redesigned.

## Security and Isolation

Confirmed by implementation and targeted test coverage:

- Staff routes require `order:read` or `work_order:read`.
- Portal tokens are rejected by existing staff-route auth before timeline access.
- Tenant ownership is checked before returning timeline records.
- Order Item timeline access verifies the item belongs to the requested order.
- Timeline visibility labels do not create a customer/public timeline endpoint.
- Timeline access does not grant related record access; it only returns identifiers and safe links.

## Customer-Safe Filtering

Timeline events expose:

- `customer_safe_summary`
- `internal_summary`
- `visibility`

Metadata is allowlisted. Raw source documents are never returned.

Excluded from timeline projection:

- raw storage paths
- internal cost fields
- profit
- margins
- pricing snapshots
- arbitrary raw metadata payloads

## Media Access

File events project safe file metadata only:

- filename
- mime type
- size
- visibility
- related file id

Raw object storage keys are not exposed.

## Mutation Guardrails

Phase 11B is read-only.

No endpoint was added to mutate:

- Quotes
- Orders
- Order Items
- Work Orders
- Proofs
- Invoices
- Payments
- pricing snapshots
- payroll
- production completion state

No live Work Order stage, stage timer, kiosk, Employee Portal production page, bottleneck analytics, or advanced tracking feature was started.

## Tests and Validation

Local commands:

- `python -m compileall backend/app backend/tests/test_ec11_phase11b_production_timeline.py` - PASSED
- `python -m pytest backend/tests/test_ec11_phase11b_production_timeline.py` - NOT RUNNABLE locally; default Python is LibreOffice embedded Python without `pytest`
- `C:\Users\thesi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest backend/tests/test_ec11_phase11b_production_timeline.py` - NOT RUNNABLE locally; bundled Python also lacks `pytest`
- `CI=true GENERATE_SOURCEMAP=false REACT_APP_BACKEND_URL=https://placeholder.invalid yarn.cmd build` from `frontend/` - PASSED
- `git diff --check` - PASSED with existing CRLF normalization warnings only

Targeted backend test file added:

- `backend/tests/test_ec11_phase11b_production_timeline.py`

Coverage includes:

- order timeline projection
- order item timeline projection
- work order timeline projection
- newest-first sorting
- pagination
- event type filtering
- category filtering
- date filtering
- actor filtering
- proof approval/revision projection
- artwork/file projection without raw storage paths
- work order assignment/status projection
- invoice/payment projection
- duplicate source events appearing once
- deterministic source identity behavior
- visibility filtering
- customer-safe field filtering
- tenant isolation
- staff read access
- portal token denial
- no live stage, pricing snapshot, payroll, or payment mutation side effects

GitHub Actions is the authoritative MongoDB-backed backend execution environment for this repository.

## Files Changed

- `backend/app/services/production_timeline_service.py`
- `backend/app/routers/production_timeline.py`
- `backend/server.py`
- `backend/tests/test_ec11_phase11b_production_timeline.py`
- `frontend/src/components/production/ProductionTimeline.jsx`
- `frontend/src/pages/OrderDetailPage.jsx`
- `frontend/src/pages/WorkOrderDetailPage.jsx`
- `memory/PRD.md`
- `memory/progress_register.md`
- `memory/checkpoint_reference_table.md`
- `evidence/EC11_PHASE11B_COMPLETION_REPORT.md`

## Carry Forward

- Phase 11C is NOT STARTED.
- Live production stages are NOT STARTED.
- Stage timers are NOT STARTED.
- Kiosk mode is NOT STARTED.
- Employee Portal production interfaces are NOT STARTED.
- Advanced production analytics / bottleneck analytics phases 11G and 11H remain NOT AUTHORIZED.
- EC12 is NOT STARTED.
