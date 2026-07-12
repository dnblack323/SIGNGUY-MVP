# EC8 Evidence — Phase 8a (Employees & Team Foundation) + Phase 8b (Time Clock & Timesheets)

**Status: EC8 — IN PROGRESS.** Phase 8a DELIVERED. Phase 8b DELIVERED. Phases 8c–8f not started. EC8 as a whole is NOT complete. EC9 has not begun.

---

## Phase 8a — Employees & Team Foundation

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

## Remaining Phase 8b scope (delivered — see full detail below)

---

## Phase 8b — Time Clock & Timesheets

### Files added
- `backend/app/models/time_entry.py` — `TimeEntry` (minute-based, `status` open/completed/void, `breaks` list, `corrections` audit list, `source` self/admin).
- `backend/app/models/timesheet.py` — `Timesheet` (daily/weekly aggregation, `status` pending/submitted/approved/rejected, `review_history`).
- `backend/app/core/time_period_utils.py` — Saturday–Friday week-boundary math using `tenant_timezone`.
- `backend/app/services/time_clock_service.py` — clock-in/out, break start/end, overlap + duplicate-open-entry prevention, admin correction (reason-required), void (reason-required), `team_status`.
- `backend/app/services/timesheet_service.py` — `period_summary` (daily/weekly/monthly), `get_or_create_weekly_timesheet`, approve/reject/reopen, `refresh_after_time_entry_change` (recomputes aggregates whenever a `TimeEntry` changes).
- `backend/app/routers/time_clock.py` — `/api/time-clock/*` (self: `/me`, `/clock-in`, `/clock-out`, `/break-start`, `/break-end`, `/entries`; admin: `/team-status`, `/{employee_id}/status`, `/{employee_id}/clock-in|out|break-start|break-end`, `/entries/all`, `/entries/{id}/correct`, `/entries/{id}/void`).
- `backend/app/routers/timesheets.py` — `/api/timesheets/*` (`/summary`, `/weekly`, list, `/pending-review`, `/{id}/approve|reject|reopen`).
- `backend/tests/test_ec8b_time_clock.py`, `backend/tests/test_ec8b_timesheets.py` — 17 targeted tests (tenant isolation, self-vs-manager scope, duplicate/overlap prevention, Sat–Fri week boundary).
- Frontend: `pages/TimeClockPage.jsx` (`/team/time-clock`), `pages/TimesheetsPage.jsx` (`/team/timesheets`).
- `backend/app/routers/dev_tools.py` — **dev-only, idempotent** fixture: `POST /api/dev-tools/ensure-dev-employee` links the `dev-login` auto-provisioned Owner `User` to an `Employee` record (see "Dev fixture" below).

### Files changed
- `backend/server.py` — registered `time_clock`, `timesheets`, and `dev_tools` routers.
- `frontend/src/lib/navigation.js` — enabled `flyout-time-clock`, `flyout-timesheets`.
- `frontend/src/App.js` — added routes `/team/time-clock`, `/team/timesheets`.

### Dev fixture — `POST /api/dev-tools/ensure-dev-employee` (development-only blocker fix)
**Problem:** `dev-login` auto-provisions a Dev Shop tenant + Owner `User` but never an `Employee`. Time Clock/Timesheet self-endpoints resolve the acting employee via `Employee.linked_user_id`, so the dev owner got `400/404 "No employee record is linked to your account"` on every clock action — blocking manual verification in a preview environment that may reset its data.

**Fix (narrowly scoped, dev-only):**
- New endpoint refuses outside `ENV=development` + `AUTH_DEV_BYPASS=true` (identical guard pattern to `auth.py`'s existing `/auth/_dev/last-reset-token` and `/auth/dev-config` — disabled in production even if the bypass flag were somehow set there).
- **Idempotent**: looks up an existing `Employee` by `linked_user_id` first; only calls `employee_service.create_employee` (the same Phase 8a creation path used by the real Employees API — no parallel creation logic) if none exists. Verified by calling it twice in a row — second call returned `"created": false` with the identical employee `id`.
- Does **not** modify `dev-login` or any production auth/identity-provisioning code. Normal login still never creates an Employee record. Payroll-domain creation stays fully separate from auth.

**Verified (curl, this session):**
1. `POST /api/dev-login` → Dev Shop Owner token.
2. `POST /api/dev-tools/ensure-dev-employee` (call #1) → `created: true`, new Employee `299a45ee-...` (`role_label: "Owner/Admin"`, `status: "active"`).
3. `POST /api/dev-tools/ensure-dev-employee` (call #2) → `created: false`, same Employee `id` — **no duplicate created**.
4. Full self clock cycle on that employee: `GET /time-clock/me` (null) → `POST /clock-in` (200, `status: open`) → `POST /break-start` → `POST /break-end` → `POST /clock-out` (200, `status: completed`) → `GET /time-clock/me` (`active_entry: null`).
5. `GET /timesheets/summary?period=daily&date=2026-07-12` → 200.
6. `GET /timesheets/weekly?week_start=2026-07-11` → 200, `week_end: 2026-07-17` confirming the Saturday→Friday boundary.
7. Re-ran targeted pytest: `test_ec8b_time_clock.py` + `test_ec8b_timesheets.py` → **17/17 passing** (includes `test_employee_cannot_manage_another_employee` [403], `test_tenant_isolation_on_entries`, `test_self_view_and_other_employee_privacy` [403] — the isolation/self-access boundary is covered here, not re-derived via curl).
8. UI smoke: `/team/time-clock` renders with real data — "Dev Owner" card shows live clock state, "Team Time Clock" panel lists employees.

### Targeted tests run (Phase 8b)
- `backend/tests/test_ec8b_time_clock.py` + `backend/tests/test_ec8b_timesheets.py` — **17/17 passing.**
- Full EC0–EC7 regression and `testing_agent_v4_fork` intentionally **NOT run** — reserved for Phase 8f per the owner's credit-conservation instruction.

### Known limitations (Phase 8b)
- Payroll gross-pay figures (`estimated_gross_cents`) are computed from `Employee.hourly_rate_cents` but there is no payroll export/ledger yet — that's Phase 8d.
- Missed-clock detection exists as a count (`missed_clock_count`) on the timesheet summary; no notification/reminder system yet.

## Remaining Phase 8c scope (not started)
Scheduling and Employee Portal — per the approved phasing, next only on explicit owner authorization.
