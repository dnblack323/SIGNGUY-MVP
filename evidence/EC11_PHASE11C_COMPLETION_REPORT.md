# EC11 Phase 11C Completion Report

**Phase:** EC11 Phase 11C - Work Order and Order Item Production Stage Integration  
**Status:** COMPLETE  
**Date:** 2026-07-16  
**Branch:** `codex-branch`

## Existing Systems Reused

- Phase 11A `ProductionWorkflowDefinition` and workflow resolver
- Phase 11B normalized production timeline projection
- Existing Orders, Order Items, and Work Orders
- Existing Work Order `items_snapshot` and production-required flags
- Existing Employee records and linked User model
- Existing Work Order assignment eligibility logic from `certification_service.check_work_order_assignment`
- Existing Equipment/Certification rules
- Existing audit service
- Existing notification service
- Existing permission architecture

No second Work Order model, workflow engine, employee assignment system, audit system, timer system, payroll ledger, or analytics subsystem was created.

## Workflow Instance Architecture

Phase 11C adds frozen live workflow instances in `production_workflow_instances`.

Each instance is tied to:

- `tenant_id`
- `order_id`
- `order_item_id`
- `work_order_id`
- `source_workflow_id`
- `source_workflow_version`
- `source_type`
- `created_by_user_id`
- `status`
- `resolution_source`
- snapshot of stage definitions

Generation is idempotent per `(tenant_id, work_order_id, order_item_id)`.

## Stage Instance Contract

Phase 11C adds live stage instances in `production_stage_instances`.

Stage instances preserve:

- stage identity and workflow instance identity
- tenant/order/order item/work order linkage
- stage key/name/description snapshots
- sequence and required/skip settings
- canonical status
- assignment fields
- due/start/completion/skip/block/wait/reopen fields
- proof gate snapshot
- equipment and certification requirement references
- customer/employee visibility flags
- production notes
- append-only action history

Excluded by design:

- pause sessions
- accumulated timer seconds
- labor contribution rows
- payroll fields
- throughput analytics fields

## Workflow Resolution and Override Behavior

Resolution precedence:

1. Order Item workflow override snapshot
2. category workflow
3. tenant default workflow
4. manual/no-workflow fallback

Order Item overrides are stored in `order_item_workflow_overrides`, scoped by tenant/order item, and freeze the copied workflow/stage snapshot. Once live stages are generated for the item, the override is locked and cannot be edited.

## Generation and Idempotency

`POST /api/work-orders/{work_order_id}/stages/generate`:

- creates instances only for production-required items
- skips non-production or archived items
- preserves manual/no-workflow state without crashing
- creates no duplicate workflow instances
- creates no duplicate stage instances
- does not mutate Quote, Order financial fields, Order Item pricing, or pricing snapshots

## Stage Lifecycle and Transitions

Backend-controlled actions were added:

- assign
- unassign
- start
- wait
- block
- resume
- complete
- skip
- reopen
- update due date
- add production note

Canonical statuses:

- `not_started`
- `in_progress`
- `waiting`
- `blocked`
- `completed`
- `skipped`

Arbitrary status PATCH is not available.

## Assignment and Eligibility

Stage assignment uses existing Employee records and reuses existing Work Order assignment eligibility logic. It validates:

- active employee
- same tenant
- linked user where eligibility requirements must be evaluated
- equipment requirements
- certification requirements
- hard blocks
- warning overrides with reason

Assignment emits audit/timeline events and best-effort notifications through the existing notification service.

## Gates

Implemented:

- prior required stage completion gate
- proof/approval gate using existing `proofs`, `proof_versions`, and `approvals`

Missing gates return explicit blocked errors. Proof approval logic was not rebuilt.

## Reopen

Reopen is restricted to owner/admin/production-manager roles, requires a reason, and only applies to completed or skipped stages. Original completion/skip timestamps and history are preserved.

## Timeline and Audit Events

Audit/timeline projection supports:

- workflow resolved
- workflow instance created
- item override created/changed
- stage assigned/unassigned
- stage started
- stage waiting
- stage blocked
- stage resumed
- stage completed
- stage skipped
- stage reopened
- due date changed
- production note added

No custom timeline storage was created.

## Notifications

Best-effort existing notifications are used for:

- stage assignment
- stage blocked
- due date changed

Notification failure does not roll back the stage action.

## Frontend Stage Panel

Added compact Work Order detail Stages tab:

- workflow resolution preview
- workflow selection before generation
- item workflow override creation
- stage-name/order override before generation
- stage generation
- stage sequence/status/assignee/due/blocker/note display
- stage action buttons based on state and permission
- assignment controls
- due date updates
- notes

No Production Board redesign, Employee Portal production page, kiosk, timer UI, or analytics UI was added.

## Permissions and Tenant Isolation

Implemented server-side:

- staff read via `work_order:read`
- stage actions via `work_order:write`
- assign/skip/reopen/due-date manager actions restricted to owner/admin/production-manager role
- tenant isolation on every source lookup
- customer and employee portal tokens denied by existing staff-route auth
- read-only roles cannot access protected staff endpoints

## Targeted Test Result

Targeted backend test file added:

- `backend/tests/test_ec11_phase11c_production_stages.py`

Local execution:

- `python -m compileall backend/app backend/tests/test_ec11_phase11c_production_stages.py` - PASSED
- `python -m pytest backend/tests/test_ec11_phase11c_production_stages.py` - NOT RUNNABLE locally; default Python is LibreOffice embedded Python without `pytest`
- `C:\Users\thesi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest backend/tests/test_ec11_phase11c_production_stages.py` - NOT RUNNABLE locally; bundled Python also lacks `pytest`

GitHub Actions is the authoritative MongoDB-backed backend execution environment.

## Frontend Build Result

Local production build:

- `CI=true GENERATE_SOURCEMAP=false REACT_APP_BACKEND_URL=https://placeholder.invalid yarn.cmd build` from `frontend/` - PASSED

## Known Gaps

Carried forward to later authorized phases:

- Phase 11D is NOT STARTED
- advanced timer/session behavior is NOT STARTED
- payroll integration is NOT STARTED
- kiosk mode is NOT STARTED
- Employee Portal production actions are NOT STARTED
- Production Board redesign is NOT STARTED
- advanced production analytics / bottleneck analytics phases 11G and 11H remain NOT AUTHORIZED
- EC12 is NOT STARTED

## Safety Confirmation

Phase 11C did not mutate:

- Quote records
- Order financial fields
- Order Item price fields
- pricing snapshots
- invoices
- payments
- payroll
- timer sessions

Phase 11C did not add:

- testing_agent execution
- broad backend regression execution
- broad frontend regression execution
- browser automation
- screenshots
- advanced timer code
- analytics code
