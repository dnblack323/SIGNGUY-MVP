# EC8 Evidence — Phase 8a (Employees & Team Foundation)

**Status: EC8 — IN PROGRESS.** Phase 8a complete and tested. Phases 8b–8f not started. EC8 as a whole is NOT complete. EC9 has not begun.

## Files added
- `backend/app/models/employee.py` — `Employee` model (statuses: active/suspended/inactive/terminated/archived; `linked_user_id` optional pointer to `User`; no sensitive payroll fields per owner directive).
- `backend/app/models/announcement.py` — `Announcement` model (audience all/selected, draft→published→expired).
- `backend/app/services/employee_service.py` — CRUD, linked-user validation (same tenant + no double-link, unique partial index `(tenant_id, linked_user_id)`), status transitions (audited, reason required, rejects no-op transitions, auto-sets `termination_date`), `status_counts`.
- `backend/app/services/announcement_service.py` — CRUD, publish (in-app notify via existing `services/notifications.py` to audience employees who have a `linked_user_id`), `active_announcements`.
- `backend/app/routers/employees.py` — `/api/employees` (list, create, get, patch, `/status-counts`, `/{id}/status`).
- `backend/app/routers/announcements.py` — `/api/announcements` (list, create, `/{id}/publish`).
- `backend/app/routers/team_dashboard.py` — `GET /api/team/dashboard` (compact: status counts + active announcements only — no placeholder widgets for unbuilt Phase 8b–8e features).
- `backend/tests/test_ec8_employees.py` (11 tests), `backend/tests/test_ec8_team_foundation.py` (5 tests) — main-agent authored, targeted to Phase 8a.
- `backend/tests/test_ec8_api_spotcheck.py` (14 tests) — added by `testing_agent_v4_fork` during review.
- Frontend: `pages/TeamDashboardPage.jsx` (`/team`), `pages/EmployeesPage.jsx` (`/team/employees`), `pages/EmployeeDetailPage.jsx` (`/team/employees/:id`), `pages/AnnouncementsPage.jsx` (`/team/announcements`).

## Files changed
- `backend/app/core/permissions.py` — canonical EC8 permission rename (approved gate decision #6). Removed (unused, zero consumers, verified by grep before removal): `EMPLOYEE_WRITE`, `EMPLOYEE_ADMIN`, `TIME_CLOCK_READ`, `TIME_CLOCK_WRITE`, `TIMESHEET_APPROVE`, `PAYROLL_WRITE`, `PAYROLL_ADMIN`, `PORTAL_EMPLOYEE_PAYSLIP_VIEW`. Added canonical set: `employee:read/manage`, `schedule:read/manage`, `timeclock:self/manage`, `timesheet:self/read/manage`, `payroll:self/read/manage/export`, `equipment:read/manage`, `training:self/manage`, `certification:read/manage`, plus portal-side `portal:employee_pay_view`, `portal:employee_schedule_view`, `portal:employee_training_view`, `portal:employee_certification_view`. `STAFF_PERMS` intentionally NOT extended with any of these (owner/admin only, by design — sensitive HR data).
- `backend/app/core/db.py` — indexes for `employees` (unique `id`; `(tenant_id, status, name)`; unique partial `(tenant_id, linked_user_id)` where present) and `announcements` (unique `id`; `(tenant_id, status, published_at)`).
- `backend/server.py` — registered the 3 new routers.
- `frontend/src/lib/navigation.js` — enabled `flyout-team-overview`, `flyout-employees`, `flyout-announcements` (removed `disabled: true`); fixed two stale permission strings (`time_clock:read`→`timeclock:manage`, `employee:admin`→`employee:manage`) on still-disabled future entries. All other Team & Workflow entries (Tasks & Kanban, Team Schedule, Time Clock, Timesheets, Payroll, Messages & Notes, Employee Portal) remain `disabled: true` — Phase 8b+ scope, not built.
- `frontend/src/App.js` — added routes `/team`, `/team/employees`, `/team/employees/:id`, `/team/announcements`.
- `frontend/src/components/common/StatusPill.jsx` — added `employee` and `announcement` status color maps.

## Employee model and relationships
`Employee` is a workforce/HR record, distinct from `User` (system login, role owner/admin/staff). `linked_user_id` is an optional, one-directional pointer to an existing `User` in the same tenant; enforced unique per user (a `User` can back at most one `Employee`). Employees are never hard-deleted; `status_history` is an append-only audit trail embedded on the document (`{from, to, reason, actor_user_id, at}`), in addition to the tenant-wide `audit_events`/`activity_events` records.

## Employee/User linkage behavior
- Creating/updating an Employee with `linked_user_id` validates the target `User` belongs to the same tenant (404 if not) and is not already linked to a different Employee (409 if so).
- No login role named "employee" was introduced — `User.role` remains `owner|admin|staff` (unchanged).

## Team Dashboard foundation
`GET /api/team/dashboard` returns employee status counts + up to 5 active (published, not expired) announcements. Deliberately excludes Time Clock/Timesheet/Payroll/Certification widgets — those phases don't exist yet; no empty placeholder sections were added, per the owner's "keep it compact" instruction.

## Announcement behavior
Draft → Publish. Publish delivers an in-app `Notification` (existing `services/notifications.py`) only to audience employees who currently have a `linked_user_id` — most employees will not yet have one until Phase 8c (Employee Portal). This is a **known, intentional Phase 8a limitation**, not a bug — confirmed by the testing agent's review.

## Existing Task integration
No Tasks system exists anywhere in this codebase (confirmed by source inspection during preflight — only unused `Perm.TASK_READ`/`TASK_WRITE` enum placeholders exist, no model/router/service). Per the owner's correction (#5), EC8 does not own or build Tasks. Phase 8a therefore does **not** include a Tasks widget on the Team Dashboard or Employee Detail page — there is nothing to integrate with yet. No `employee_tasks`/`team_tasks`/second Task API was created. This will be revisited once a Tasks system exists (ownership TBD, outside EC8 per the owner's explicit instruction).

## Audit/activity behavior
Every Employee create/update/status-change and every Announcement create/publish calls `services/activity.py::record_activity_with_audit()` (writes both an `audit_events` row and an `activity_events` row). Verified via `test_status_transition_records_audit_and_history`.

## Targeted tests run
- `backend/tests/test_ec8_employees.py` — 11/11 passing.
- `backend/tests/test_ec8_team_foundation.py` — 5/5 passing (includes a permission-catalog regression test asserting the superseded values are actually gone).
- `backend/tests/test_ec8_api_spotcheck.py` (testing agent) — 14/14 passing, includes EC0–EC7 spot-check (Customers/Orders/Inventory endpoints) confirming no regression from the `Perm` enum rename.
- Directly-affected existing suites re-run (not full regression): `test_permissions_scope.py`, `test_ec2_permissions.py` — both green.
- `testing_agent_v4_fork` iteration_11: 100% pass, zero bugs. One non-blocking cosmetic note (native `<input type="date">` vs. shadcn Calendar on Employee Detail's Hire date field) — logged to backlog, not fixed (optional polish, not requested).
- Full EC0–EC7 regression and full frontend suite intentionally NOT run — reserved for Phase 8f per the owner's credit-conservation instruction.

## Known limitations (Phase 8a)
- Announcement in-app delivery only reaches employees with a linked staff login (see above).
- No Tasks integration yet (Tasks system doesn't exist in this codebase).
- Optional cosmetic polish: Hire date field uses a native date input instead of the shadcn Calendar component (not fixed, non-blocking).
- Employee Portal, Time Clock, Timesheets, Team Schedule, Payroll, Equipment/Training/Certification are all NOT built — Phase 8b onward.

## Remaining Phase 8b scope (not started)
Time Clock (clock in/out, breaks, duplicate/overlap prevention, manual correction history, missed-clock handling) + Timesheets (daily/weekly/monthly, approval foundation) — per the approved phasing, next only on explicit owner authorization.
