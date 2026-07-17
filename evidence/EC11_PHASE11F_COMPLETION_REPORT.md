# EC11 Phase 11F Completion Report

Phase 11F: Shop-Floor Production Kiosk Mode

Status: COMPLETE (2026-07-17)

EC11 status: IN PROGRESS. Phases 11G and 11H remain NOT AUTHORIZED. Phase 11I is NOT STARTED. EC12 is NOT STARTED.

## Existing Systems Reused

Phase 11F reused the existing:

- Employee records
- Employee Portal identity records
- EC8 Time Clock and Timesheet refresh services
- Phase 11C production stage action services
- Phase 11D production board projection/current-stage logic
- Work Orders, Orders, Order Items, Customers, and Employees
- tenant settings service
- existing audit, notification, permission, and tenant-scoping patterns

No duplicate employee identity system, production stage engine, time clock, global settings system, audit stream, notification stream, production timer subsystem, payroll subsystem, or analytics subsystem was created.

## Kiosk Authentication Architecture

Added `ProductionKioskDeviceSession` and `ProductionKioskSupervisorOverride` records:

- device sessions are tenant-bound and created by staff activation
- device tokens are generated once and stored only as SHA-256 hashes
- device sessions track label, activation actor, expiration, last activity, status, and revocation
- employee sub-sessions are short-lived and stored only as token hashes
- supervisor override tokens are one-time, action-specific, short-lived, and stored only as hashes

Kiosk routes use explicit kiosk headers:

- `X-Kiosk-Device-Token`
- `X-Kiosk-Employee-Token`

Staff JWTs and portal JWTs do not satisfy kiosk employee-session routes.

## Device And Employee Sessions

Staff managers can:

- activate a kiosk device
- list kiosk sessions
- revoke kiosk sessions
- configure kiosk settings
- set employee kiosk PIN credentials

Employee kiosk sign-in:

- requires an existing active Employee record
- requires an existing active Employee Portal identity
- verifies a stored bcrypt PIN hash
- never returns PIN hashes or token hashes
- rate-limits repeated failed identification attempts
- clears employee session fields on switch/end

## Safe Work Contract

The kiosk work view returns only operational production fields:

- work/order/item display identifiers
- customer name only when configured visible
- stage/workflow name and status
- assignee display
- priority, due, overdue, blocked, waiting, and progress state
- proof/eligibility summary
- backend-derived action list

The kiosk contract does not expose unit prices, pricing snapshots, pay rates, payroll fields, costs, profit, margins, raw storage paths, raw audit metadata, or internal-only fields.

## Work Views

`/kiosk/production` supports:

- current task
- assigned tasks
- ready for me
- shop queue
- blocked/waiting
- recently completed by me
- separate Time Clock panel labeled as work shift time

Shop queue visibility is tenant-configurable:

- `assigned_only`
- `assigned_plus_ready_for_role`
- `full_safe_production_queue`

## Employee Actions

Employee kiosk actions are assigned-only by default:

- start
- resume
- wait with reason
- block with reason
- complete
- add production note

The kiosk does not expose skip, reopen, assignment changes, due-date edits, or manager queue mutations as normal employee actions.

## Supervisor Override

Supervisor override is:

- staff-manager authenticated
- reason-required
- action-specific
- stage-specific
- employee-session-specific
- one-time use
- short-lived
- audited with supervisor, employee, action, stage, reason, and kiosk session context

The override does not create a full staff session in kiosk mode.

## Time Clock Separation

The kiosk Time Clock panel delegates to EC8 Time Clock services. Time Clock writes remain separate from production stage status:

- clock in/out creates/updates TimeEntry records only
- production start/complete does not clock the employee in or out
- no production timer sessions or production timer events were added
- kiosk Time Clock uses the existing `self` source contract and records a kiosk actor id for auditability

## Configuration

Added tenant settings namespace `production_kiosk` with:

- kiosk enabled
- device session expiration
- employee idle timeout
- PIN enabled
- shop queue visibility
- customer name visibility
- artwork/document visibility flag
- Time Clock panel enabled
- supervisor override enabled
- allowed basic employee actions
- device labels

## Route And Layout

Backend routes added under `/api/production-kiosk`.

Frontend route added at `/kiosk/production` outside the standard staff `AppShell`, with a staff navigation entry to open it. The kiosk route does not render the staff sidebar or the full Employee Portal UI.

## Offline Behavior

No offline sync or replay queue was added. The frontend detects browser offline state, shows a disconnected state, disables mutations while offline, and refreshes after reconnect/user refresh.

## Permissions And Tenant Isolation

Kiosk management is owner/admin/production-manager scoped. Kiosk device sessions are tenant-bound. Employee sub-sessions resolve tenant and employee from the kiosk session plus the existing Employee and Portal Identity records.

Cross-tenant stage and employee access remains blocked by tenant-scoped service calls.

## Audit, Timeline, And Notifications

Stage actions delegate to Phase 11C services, so existing audit and production timeline behavior remains authoritative.

Kiosk-specific audits were added for:

- device activation
- device revocation
- config update
- employee credential setup
- employee identification
- employee session cleared
- supervisor override created
- supervisor override consumed

## CI Failure Cause And Fix

First backend CI failures were in new Phase 11F tests:

- the supervisor-override fixture used a role-restricted unassigned stage, which correctly triggered existing Phase 11C assignment eligibility checks for an employee without a linked staff user
- the kiosk Time Clock service initially attempted to use `source="kiosk"`, but EC8 `TimeEntry.source` is intentionally limited to `self` or `admin`
- the employee-session-clear response still returned cleared employee fields as `null`

Fixes:

- targeted the supervisor-override fixture to an unrestricted ready stage
- reused EC8 `source="self"` while preserving the kiosk actor id/email
- returned the device session with employee fields omitted after switch/end

No broader regression or unrelated code change was made for these CI fixes.

## Targeted Validation

Local validation:

- `python -m compileall backend/app/services/production_kiosk_service.py backend/app/routers/production_kiosk.py backend/app/models/production_kiosk.py backend/app/services/production_board_service.py` - PASSED
- `python -m compileall backend/tests/test_ec11_phase11f_production_kiosk_mode.py` - PASSED
- `npm.cmd test -- --watchAll=false` from `frontend/` - PASSED, 7 suites / 29 tests
- `npm.cmd run build` from `frontend/` - PASSED

Local targeted backend pytest was not runnable because local Python runtimes lack `pytest`, and the local environment lacks the MongoDB-backed backend test service used by CI.

GitHub Actions run `29550643075` passed:

- `backend-tests`
- `frontend-tests`
- `frontend-build`

## Files Changed

- `backend/app/core/db.py`
- `backend/app/models/production_kiosk.py`
- `backend/app/routers/production_kiosk.py`
- `backend/app/services/production_board_service.py`
- `backend/app/services/production_kiosk_service.py`
- `backend/app/services/settings.py`
- `backend/server.py`
- `backend/tests/test_ec11_phase11f_production_kiosk_mode.py`
- `frontend/src/App.js`
- `frontend/src/lib/navigation.js`
- `frontend/src/pages/ProductionKioskPage.jsx`
- `memory/PRD.md`
- `memory/progress_register.md`
- `memory/checkpoint_reference_table.md`
- `evidence/EC11_PHASE11F_COMPLETION_REPORT.md`

## Safety Confirmation

Phase 11F did not mutate or create:

- Quote records
- Order financial records
- Order Item pricing records
- pricing snapshots
- payroll records from production actions
- production timer sessions
- production timer events
- advanced analytics records

Phase 11F did not add:

- a second employee identity system
- a duplicate production stage engine
- payroll-stage coupling
- production timers
- advanced analytics
- universal manager mode
- a full Employee Portal UI inside the kiosk

Phase 11F did not run `testing_agent`, broad local backend regression, browser automation, or screenshots.

## Known Gaps Carried Forward

- Phases 11G and 11H remain NOT AUTHORIZED.
- Phase 11I is NOT STARTED.
- EC12 is NOT STARTED.
- Advanced production tracking / bottleneck analytics remains reserved for its authorized scope.
