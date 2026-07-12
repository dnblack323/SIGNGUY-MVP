# EC8 Evidence — Phase 8a (Employees & Team Foundation) + Phase 8b (Time Clock & Timesheets) + Phase 8c (Scheduling & Employee Portal) + Phase 8d (Payroll) + Phase 8e (Equipment/Training/Certification) + Phase 8f (Final Closure)

**Status: EC8 — DELIVERED / CLOSED (2026-07).** Phases 8a, 8b, 8c, 8d, 8e, 8f all DELIVERED. EC8 as a whole is COMPLETE. EC9 has not begun.

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

---

## Phase 8c — Scheduling & Employee Portal

### Files added
- `backend/app/models/schedule.py` — `Schedule` (one per tenant per Saturday–Friday week; `status` draft/published/archived; `version`; `published_at/by`; `last_notified_at` watermark for idempotent republish notifications).
- `backend/app/models/shift.py` — `Shift` (single authoritative assignment record; `status` scheduled/cancelled/completed; `conflict_override_reason`; opaque `work_order_id`/`order_id` links only — never resolved to full objects for the portal).
- `backend/app/services/schedule_service.py` — hard-conflict checks (duplicate, overlap, invalid start/end, inactive/cross-tenant employee), availability-warning check (soft, overridable with a reason, audited as `schedule_conflict_overridden`), `create/update/cancel_shift`, `copy_shift/copy_day/copy_week/assign_multiple_employees` (all skip-on-conflict, not hard-fail-the-batch), `publish_schedule` (idempotent no-op if already published), `republish_schedule` (400 if no shift changes since last publish — the idempotency guard), `today_snapshot` (compact Team Dashboard scheduling counters).
- `backend/app/services/employee_portal_service.py` — staff-side invite/suspend (additive on the EC6 `create_portal_identity`/`mint_magic_link_token`/`send_email`, no parallel invitation system); idempotent invite (existing active identity reused, disabled identity reactivated).
- `backend/app/routers/schedule.py` — `/api/schedules/*` (get-or-create week, get, shifts/assign/copy-day/copy-week/publish/republish/archive) + `/api/schedule-shifts/*` (list/patch/cancel/copy), gated `schedule:read`/`schedule:manage`.
- `backend/app/routers/employee_portal_admin.py` — `/api/employee-portal/*` (list, status, invite, suspend), gated `employee:read`/`employee:manage`.
- `backend/app/routers/portal_employee.py` — `/api/portal/employee/*` (dashboard, time-clock/* thin wrappers over Phase 8b's `time_clock_service`, schedule/today+week published-only, timesheet/summary+weekly self-scoped with payroll-rate-derived fields stripped, announcements filtered by audience/targeting, tasks placeholder, profile get/patch).
- `backend/app/routers/dev_tools.py` — added dev-only `POST /api/dev-tools/mint-employee-portal-login` (same guard pattern as Phase 8b's `ensure-dev-employee`) — mints a raw, usable magic-link token bypassing SendGrid for E2E verification without a real inbox.
- Frontend: `pages/TeamSchedulePage.jsx` (`/team/schedule` — week grid, Add/Edit Shift dialog with inline availability-conflict override flow, cancel, copy-to-next-week, publish/republish), `pages/EmployeePortalAccessPage.jsx` (`/team/employee-portal` — invite/resend/suspend list).
- Frontend: `portal/employee/employeePortalApi.js`, `EmployeePortalAuthContext.jsx`, `EmployeePortalApp.jsx` — a **separate** Employee Portal shell at `/portal/employee/*` with its own `localStorage` token key (`sg_employee_portal_token`, distinct from the Customer Portal's `sg_portal_token`) so both portal sessions can coexist in one browser. Pages: Dashboard, Time Clock, My Schedule, My Timesheet, Announcements, Profile. "My Tasks" nav rendered as a disabled `<span>` (not a `<Link>`) — no Task system exists yet.
- `backend/tests/test_ec8c_schedule.py` (13 tests), `backend/tests/test_ec8c_employee_portal.py` (10 tests) — 23 targeted tests, all main-agent authored.

### Files changed
- `backend/app/models/portal_identity.py` — added `portal_type` (`"customer"|"employee"`, default `"customer"` for backward compatibility), `employee_id` (nullable), `EMPLOYEE_PORTAL_PERMS` constant. `customer_id` made nullable. Existing `PORTAL_PERMS`/preset-bundle logic for customers is completely untouched.
- `backend/app/services/portal_identity.py` — `create_portal_identity()` gained optional `portal_type`/`employee_id` kwargs (default behavior for existing customer callers unchanged); `issue_portal_jwt()` now forwards `portal_type`/`employee_id` into the token.
- `backend/app/core/portal_security.py` — `create_portal_token()` gained optional `portal_type` (default `"customer"`) and `employee_id` kwargs; `customer_id` made optional. Existing customer call sites unaffected.
- `backend/app/deps_portal.py` — `get_current_portal_identity()` is now portal-type-aware: resolves the identity by `id`+`tenant_id`+`status=active` first, then compares the **stored doc's** `portal_type` (defaulting missing/legacy field to `"customer"`) against the **token's** `portal_type` claim, and checks `customer_id`/`employee_id` accordingly — this keeps every pre-existing Customer Portal identity working with zero migration. Added `require_employee_portal_permission()` — defense-in-depth guard that (a) hard-rejects non-employee-typed identities even if permission strings somehow matched, and (b) re-checks the linked `Employee.status == "active"` on every single request (not just at invite time), auditing `employee_portal_access_denied` on failure.
- `backend/app/routers/portal_auth.py` — login/magic-link-verify now record `employee_portal_login`/`employee_portal_activated` (first-login only) instead of the generic `portal.login`/`portal.magic_link_login` action name when `identity.portal_type == "employee"`; customer-identity audit action names are unchanged.
- `backend/app/services/employee_service.py` — added `add_availability_block`/`remove_availability_block` (structured `Employee.availability_blocks`, feeds the schedule conflict-warning check; the old free-text `availability` field is left in place, unreferenced by new code).
- `backend/app/models/employee.py` — added `availability_blocks: list[dict]` field.
- `backend/app/routers/employees.py` — added `/{id}/availability` POST/DELETE (manager-only).
- `backend/app/routers/team_dashboard.py` — `GET /api/team/dashboard` gained a compact `scheduling` sub-object (`employees_scheduled_today`, `scheduled_not_clocked_in`, `unpublished_draft_schedules`, `conflicts_overridden`) — no full calendar widget added, per the owner's "Team Schedule page owns the detailed grid" instruction.
- `backend/app/core/db.py` — indexes for `schedules` (unique `id`; unique `(tenant_id, period_start)`; `(tenant_id, status)`), `shifts` (unique `id`; `(tenant_id, schedule_id)`; `(tenant_id, employee_id, shift_date)`; `(tenant_id, employee_id, start_at, end_at)`), and a unique **partial** index on `portal_identities` — `(tenant_id, employee_id)` where `portal_type == "employee"` — guaranteeing at most one Employee Portal identity per Employee without touching the existing customer-side unique `(tenant_id, email)` index.
- `backend/server.py` — registered `schedule` (both sub-routers), `employee_portal_admin`, `portal_employee` routers.
- `frontend/src/lib/navigation.js` — enabled `flyout-team-schedule` and `flyout-employee-portal` (removed `disabled: true`). All other Team & Workflow entries (Payroll, Equipment Training, Certifications, Tasks & Kanban) remain disabled — out of Phase 8c scope.
- `frontend/src/App.js` — added `/team/schedule`, `/team/employee-portal`, and `/portal/employee/*` (mounted **before** the existing `/portal/*` wildcard so React Router's path-ranking resolves it correctly; verified no Customer Portal route regression).
- `frontend/src/pages/EmployeeDetailPage.jsx` — added an "Employee Portal access" card (invite/resend/suspend), gated behind `employee:manage`, alongside the existing status-history card.

### Additive Employee Portal identity architecture (no second identity/token system)
Exactly one `portal_identities` collection, exactly one JWT scheme (`sub_scope="portal"`), distinguished by a `portal_type` discriminator. An Employee Portal token carries `portal_type="employee"` + `employee_id` (both `null` on customer tokens, and `customer_id` is `null` on employee tokens) — `get_current_portal_identity` cross-checks the **stored identity document's** type against the **token's claimed** type on every request, so a customer token can never satisfy an employee route (or vice versa) even if the underlying JWT secret/algorithm/verification code path is 100% shared. Verified directly:
- `test_employee_token_cannot_access_customer_portal_and_vice_versa` (pytest) — employee token → `GET /api/portal/quotes` → 403; customer token → `GET /api/portal/employee/dashboard` → 403.
- Manual curl during this session: minted a legacy-style (no `portal_type` field, simulating a pre-8c document) customer identity's magic link → verified login still succeeds and `GET /api/portal/quotes` still works unchanged; then created a brand-new employee identity and confirmed cross-403 both directions.

### Conflict detection and override
Hard blocks (409/400, never bypassable): exact duplicate shift, overlapping shift for the same employee, invalid start/end, inactive employee, cross-tenant employee. Soft warning (409 with a machine-parseable `availability_conflict:<message>` detail, resubmit with `override_reason` to proceed): shift falls inside an employee's structured `availability_blocks` "unavailable" window. Every override is separately audited as `schedule_conflict_overridden` with the reason text, in addition to the normal `shift_created`/`shift_updated` audit entry.

### Draft/publish workflow
A `Schedule` is a single row per tenant per week; employees never see it via `/api/portal/employee/schedule/*` until `status` flips to `published` (`published_only=True` filter joins on `db.schedules` with `status="published"`). Publishing is idempotent (second call on an already-published schedule is a silent no-op — no duplicate notifications). Editing shifts after publish does **not** revert the schedule to draft; each individual post-publish create/update/cancel fires its own targeted notification (`shift.added`/`shift.changed`/`shift.cancelled`) to just that employee. A separate `republish` action bumps `version` and re-notifies every employee with a shift changed since the last publish/republish — but only if at least one shift actually changed (`400` otherwise), which is the mechanism verified by `test_publish_draft_hidden_then_visible_and_republish_requires_change`.

### Notifications
Reuses `services/notifications.py` (in-app, only if the Employee happens to have a `linked_user_id`) and `services/email.py` (SendGrid, keyed to `Employee.email`) — no parallel messaging system. No SMS was added (out of scope for this phase).

### Dev fixture — `POST /api/dev-tools/mint-employee-portal-login` (development-only, mirrors Phase 8b's `ensure-dev-employee` guard)
SendGrid is configured with a real key in this environment but the dev-login-provisioned owner's email (`dev@signguy-dev.example.com`) is not a real inbox, so E2E-verifying the actual magic-link click-through required a way to obtain a usable raw token without waiting on email delivery. This endpoint mints a fresh, unconsumed magic-link token for an existing Employee Portal identity and returns the raw token directly — refuses outside `ENV=development`+`AUTH_DEV_BYPASS=true`, reuses the exact same `mint_magic_link_token` the real invite flow uses (no parallel token logic).

### Targeted tests run (Phase 8c)
- `backend/tests/test_ec8c_schedule.py` — 13/13 passing (create/edit/cancel shift, duplicate+overlap hard-block, invalid start/end, inactive/cross-tenant employee rejection, availability warning + authorized override, copy-with-skip-on-duplicate idempotency, multi-employee assign, copy-day, publish→draft-hidden→published-visible→idempotent-republish-guard→version-bump-on-change, schedule:read permission boundary).
- `backend/tests/test_ec8c_employee_portal.py` — 10/10 passing (idempotent invite, magic-link activation + untouched pre-existing customer identity, bidirectional cross-portal-type 403, self-scope with no arbitrary employee_id acceptance, suspended-identity 401, inactive-Employee-live-denial 403 with audit record, expired-invitation 401, cross-tenant-token 401, draft-hidden/published-visible via the portal endpoint, announcement targeting).
- Full 8b + 8a + EC6 regression re-run in the same session: `test_ec8b_time_clock.py`, `test_ec8b_timesheets.py`, `test_ec8_employees.py`, `test_ec8_team_foundation.py`, `test_ec6_portal_docs.py`, `test_ec6_portal_payment.py` — all green, **73/73 total** including the 23 new Phase 8c tests. Zero regressions from the additive `PortalIdentity`/`deps_portal.py`/`portal_security.py` changes.
- `testing_agent_v4_fork` iteration_12 (full feature matrix) → found 2 CRITICAL frontend bugs (Edit Shift dialog didn't prefill Start/End time inputs, causing a crash on Save; Employee Portal magic-link verify page double-fired the verify call, burning the single-use token on the first of two identical requests) + 2 LOW cosmetic issues (stray "0" after clock-in time; Badge-inside-`<p>` HTML nesting warnings). Both CRITICAL bugs fixed same-session (dedicated `to24hTime()` prefill helper; `useRef` double-invoke guard on the verify page's effect) and LOW issues fixed (`!!()` boolean coercion; Badge wrappers moved from `<p>` to `<div>`).
- `testing_agent_v4_fork` iteration_13 (fix-verification retest, frontend-only) → **100% pass, zero remaining issues.** Both critical fixes and both low fixes confirmed working via real browser click-through (no localStorage-injection workaround needed this time); light regression sanity on Add Shift/Publish/Republish/Employee Portal Access admin/Customer Portal login all unaffected.

### Known limitations (Phase 8c)
- "My Tasks" is a documented boundary/placeholder only (`{"available": false, "items": []}`) — no Task system exists anywhere in this codebase yet, per the same finding from Phase 8a.
- Team Schedule's Add/Edit Shift dialog uses native `<input type="date">`/`<input type="time">` instead of the shadcn Calendar/time picker (cosmetic, flagged LOW by testing agent, not fixed — consistent with the same previously-accepted cosmetic deferral on Employee Detail's Hire date field from Phase 8a).
- Employee self-editable availability requests are deferred (owner explicitly allowed postponing this); only manager-side availability CRUD exists this phase.
- "Open shifts today" (unassigned shift) Team Dashboard card was intentionally omitted — the `Shift` model requires an `employee_id` at creation time; there is no "unassigned shift" concept to count.
- Advanced Production Stage Tracking & Bottleneck Analytics (owner-locked future paid add-on, explicitly out of EC8 scope) is documented at `/app/docs/production_stage_timer_boundary.md` — reserved route `/portal/employee/production` is NOT wired into `EmployeePortalApp.jsx`, no timer collections/models/routes exist.

## Remaining Phase 8d scope (delivered — see detail below)

---

## Phase 8d — Payroll

### Scope boundary (LOCKED)
Internal workforce gross-pay ledger only — explicitly NOT a payroll-processing, tax-filing, or banking service. No ACH/direct deposit, no SSN/bank storage, no tax withholding/statutory deductions, no W-2/1099 generation. Overtime math is a configurable internal estimate, never represented as legal/compliance payroll.

### Files added
- `backend/app/models/pay_period.py` — `PayPeriod` (one per tenant per Saturday–Friday week; payday = end_date/Friday; unique `(tenant_id, start_date)`).
- `backend/app/models/payroll_snapshot.py` — `PayrollSnapshot` (one per period × employee; a read model recomputed from the ledger).
- `backend/app/models/payroll_transaction.py` — `PayrollTransaction` (append-only ledger; corrections/voids add an offsetting row and flip `voided=True` on the original — never mutate historical `amount_cents`).
- `backend/app/services/payroll_service.py` — period open/close, snapshot recompute from `TimeEntry`/`Timesheet` (Phase 8b) hours × `Employee.hourly_rate_cents`, manual adjustment/advance transactions, void (reason-required), `_refresh_period_financial_status` (financial status is always derived from the ledger, never set directly by a caller).
- `backend/app/routers/payroll.py` — `/api/payroll/*` (periods list/get/open/close, snapshots, transactions add/void, `/export` CSV).
- `backend/app/routers/portal_employee.py` — added `/portal/employee/pay` (self-scoped, payroll-rate/internal-note fields stripped).
- `backend/tests/test_ec8d_payroll.py` — 13 targeted tests.
- Frontend: `pages/PayrollPage.jsx` (`/team/payroll` — periods list, snapshot table, add/void transaction dialogs with reason-required void, CSV export), `portal/employee/MyPayPage.jsx` (`/portal/employee/pay`).

### Files changed
- `backend/app/core/permissions.py` — `payroll:self/read/manage/export` (already added to the canonical EC8 permission catalog in Phase 8a preflight; wired to enforcement in Phase 8d routers).
- `backend/server.py` — registered `payroll` router.
- `frontend/src/lib/navigation.js` — enabled `flyout-payroll`.
- `frontend/src/App.js` — added `/team/payroll` and `/portal/employee/pay`.
- `frontend/src/portal/employee/EmployeePortalApp.jsx` — added "My Pay" nav link + Dashboard pay summary card.

### Targeted tests run (Phase 8d)
- `backend/tests/test_ec8d_payroll.py` — **13/13 passing.**
- Full EC0–EC7 + Phase 8a/8b/8c regression and `testing_agent_v4_fork` intentionally **NOT run** — reserved for Phase 8f per the owner's credit-conservation instruction.

### Known limitations (Phase 8d)
- No ACH/direct deposit, tax withholding, or W-2/1099 generation (explicitly out of scope, LOCKED).
- Advances/adjustments are manual ledger entries only — no external accounting-system sync.

---

## Phase 8e — Equipment, Training, Certification & Work Order Access Enforcement

### Scope
Track Equipment (machines/safety-sensitive assets), assign bounded Training (reading/video/sop_review/quiz/practical_demonstration/manager_signoff/retraining) with quizzes and practical-signoff workflows, issue/renew/revoke per-Equipment Certifications per Employee, and enforce all of this at Work Order assignment time (hard block / warn-with-override / advisory role match).

### Files added
- `backend/app/models/equipment.py`, `training_definition.py`, `training_assignment.py`, `quiz_attempt.py`, `practical_signoff.py`, `certification.py`.
- `backend/app/services/equipment_service.py` — CRUD, archive, `equipment_detail` (composite: equipment + linked documents + required Training + pending Training assignments + Certifications + active/expiring counts).
- `backend/app/services/training_service.py` — Training Definition CRUD/archive (with quiz question authoring), Assignment lifecycle (`assign → start → complete | quiz → (pending_signoff) → signoff | fail | cancel`), quiz scoring against `passing_score` (attempt history preserved, never overwritten — a passing retry after a prior failed attempt correctly re-opens the assignment rather than hitting a terminal-status guard), `list_assignments`/`list_certifications` enriched with denormalized `training_title`/`equipment_name` for list UIs (both manager and portal).
- `backend/app/services/certification_service.py` — issue/renew/revoke (revoke reason required, permanent history retained), `effective_status` (auto-expiry by date), `expires_soon` window flag, `check_work_order_assignment` (the enforcement decision engine — see below), Employee × Equipment matrix builder.
- `backend/app/routers/equipment.py`, `training.py`, `certification.py` — `/api/equipment/*`, `/api/training/definitions/*` + `/api/training/assignments/*` (+ self-service `/start`, `/quiz`, `/complete`, `/signoff`, `/fail`, `/cancel`), `/api/certifications/*` (+ `/matrix`, `/{id}/renew`, `/{id}/revoke`).
- `backend/app/routers/portal_employee.py` — added self-scoped `/portal/employee/training/assignments` (+ `/{id}`, `/{id}/start`, `/{id}/quiz`, `/{id}/complete`) and `/portal/employee/certifications` — never accepts an Employee ID from the client; always resolves from the authenticated portal identity. Strips quiz `correct_index`, manager notes, and override/audit detail from every portal-facing response.
- `backend/tests/test_ec8e_equipment_training.py` — 15 targeted tests (Equipment CRUD/archive, Training Definition + quiz authoring, Assignment lifecycle incl. quiz retry-after-fail, practical signoff, Certification issue/renew/revoke/expiry, matrix, Work Order enforcement — no-cert hard block, expired/override-allowed warning + override success, cross-tenant assignee rejection, advisory role-mismatch warning-only).
- Frontend (manager, under **Team & Workflow**): `pages/EquipmentPage.jsx` (`/team/equipment`), `pages/EquipmentDetailPage.jsx` (`/team/equipment/:id` — Overview/Training/Certifications tabs), `pages/TrainingPage.jsx` (`/team/training` — Definitions tab incl. quiz builder, Assignments tab), `pages/CertificationsPage.jsx` (`/team/certifications` — Employee × Equipment Matrix tab + All Certifications tab), plus `components/training/{TrainingDefinitionDialog,AssignTrainingDialog,AssignmentDetailDialog}.jsx` and `components/certifications/{IssueCertificationDialog,RevokeCertificationDialog}.jsx`.
- Frontend (Employee Portal): `portal/employee/MyTrainingPage.jsx` (`/portal/employee/training`), `portal/employee/MyTrainingAssignmentDetailPage.jsx` (`/portal/employee/training/:assignmentId` — quiz-taking UI, materials, signoff/completion state), `portal/employee/MyCertificationsPage.jsx` (`/portal/employee/certifications` — read-only, renewal-needed flag).
- Frontend (Work Order integration): `components/work-orders/RequirementsDialog.jsx` (manager sets `required_equipment_ids`/`required_role` on a Work Order).

### Files changed
- `backend/app/services/work_order_service.py` / `backend/app/routers/work_orders.py` — `assign()` now runs `certification_service.check_work_order_assignment` against every proposed assignee before persisting; returns `409 {"message": "assignment_blocked"|"assignment_warning_override_required", "check": {...}}` on failure so the exact backend decision (per-user `blocked[]`/`warnings[]` with `code`+`message`+`equipment_id`) reaches the frontend unmodified — the frontend never re-implements the enforcement rule, it only renders `check.results`.
- `backend/app/services/training_service.py` (`list_assignments`) / `certification_service.py` (`list_certifications`) — additive `training_title`/`training_type` and `equipment_name` batch-join enrichment (small, directly-frontend-motivated backend adjustment; verified additive/non-breaking by re-running the full targeted suite after each change).
- `backend/app/services/employee_portal_service.py` (`invite_employee`) — re-inviting an Employee (active or reactivating a disabled identity) now always re-syncs `permissions` to the current `EMPLOYEE_PORTAL_PERMS` set. **Bug found and fixed this phase:** pre-existing Employee Portal identities created before the Training/Certification permissions existed had stale `permissions` arrays and would have gotten silently 403'd on the new self-service endpoints; re-invite now heals this without a separate migration script.
- `frontend/src/components/common/StatusPill.jsx` — added `equipment_status`, `access_policy`, `certification`, `training_assignment` color maps (reused the existing badge pattern, no new component).
- `frontend/src/pages/WorkOrderDetailPage.jsx` — added an "Assignment requirements" card (read-only badges + Edit dialog) and wired `RequirementsDialog`.
- `frontend/src/components/work-orders/GenerateWorkOrderDialog.jsx` (`AssignDialog`) — renders `check.results` per assignee (blocked = rose, non-overridable; warning = amber, override-reason-gated); `Save` is disabled while any assignee is hard-blocked; `Assign anyway` only appears when every flagged item is override-eligible and a reason has been entered.
- `frontend/src/lib/navigation.js` — enabled `flyout-equipment` (`equipment:read`), `flyout-training` (`training:manage`), `flyout-certifications` (`certification:read`).
- `frontend/src/App.js` — added `/team/equipment(+/:id)`, `/team/training`, `/team/certifications`, `/portal/employee/training(+/:assignmentId)`, `/portal/employee/certifications`.
- `frontend/src/portal/employee/EmployeePortalApp.jsx` — added "My Training"/"My Certifications" nav links + Dashboard cards (Training due/overdue/pending-signoff counts, Certifications expiring-soon/expired counts, both derived client-side from the existing self-scoped list endpoints — no new aggregate endpoint added).

### Work Order enforcement decision engine
`check_work_order_assignment` evaluates, per proposed assignee, every `Equipment` in the Work Order's `required_equipment_ids`:
- `access_policy=no_required` / `recommended` → never blocks or warns.
- `required_no_override` + no valid (active, unexpired, unrevoked) Certification → **hard block** (`certification_missing`/`certification_expired`/`certification_revoked`), not overridable.
- `required_override_allowed` + no valid Certification → **warning**, assignable only with a non-empty `override_reason` (persisted on the assignment audit trail).
- `required_role` mismatch → **advisory warning only**, never blocks, never requires an override reason (it does not gate on Certification data).
Verified end-to-end via both the pytest suite and live curl during this session:
- No-cert + `required_no_override` Equipment → `409 assignment_blocked`.
- Expired-cert + `required_override_allowed` Equipment → `409 assignment_warning_override_required`; resubmission with `override_reason` → `200`.
- Frontend `AssignDialog` screenshot-verified rendering both the block reason (rose, non-overridable) and the warning reason (amber, override-reason-gated) for the same multi-requirement Work Order in one dialog.

### Targeted tests run (Phase 8e)
- `backend/tests/test_ec8e_equipment_training.py` — **15/15 passing** (6 initially failed on stale test-fixture Quote API shape + a real quiz-retry-after-fail bug in `training_service.py`; both root-caused and fixed, then verified green).
- Re-ran `backend/tests/test_work_orders_ec5.py` + `backend/tests/test_quotes_ec3.py` after the Work Order/training/certification service changes — both green, no regressions.
- Manual curl E2E (documented above) for the hard-block and warning-override Work Order assignment paths, plus the Employee Portal permission-backfill fix.
- Frontend smoke: Certification Matrix (`/team/certifications`), Employee Portal My Training list + assignment detail + quiz-taking form (`/portal/employee/training`), Work Order Detail "Assignment requirements" card + `AssignDialog` block/warning rendering — all screenshot-verified with real seeded data.
- Full EC0–EC7 + Phase 8a–8d regression and `testing_agent_v4_fork` intentionally **NOT run** — reserved for Phase 8f per the owner's explicit credit-conservation instruction for this phase.

### Known limitations (Phase 8e)
- Equipment/Training Definition "linked documents" are surfaced read-only (equipment detail Overview tab, portal assignment detail "Materials" list) — no manager-facing link/unlink UI was built this phase (not explicitly requested; avoids inventing scope beyond the given plan).
- Employee Portal document "Materials" list shows titles only (no download/view action) — no new portal-facing file-download endpoint was added; wiring a safe self-scoped download path is deferred.
- `required_role` on a Work Order is advisory-only by design (never blocks) — this was an explicit design choice in `check_work_order_assignment`, not a gap.

## Remaining Phase 8f scope (delivered — see detail below)

---

## Phase 8f — Final EC8 Closure (Full Regression)

### Scope
Full backend regression (all EC0–EC8 targeted suites, not just Phase 8e), full frontend regression via `testing_agent_v4` (first time Phase 8e gets automated UI coverage), verified defect fixes, and formal EC8 closure. No new features in scope for this phase.

### Backend regression
- `python -m pytest backend/tests/` (all suites, `REACT_APP_BACKEND_URL` exported for `test_ec8_api_spotcheck.py`) — **312/312 passing**, zero failures.
- `python -m app.core.terminology_guard /app` — **OK**.
- Confirmed no regression in EC0–EC7 or Phase 8a–8d from the Phase 8e service edits (`work_order_service.py` assign(), `training_service.py`/`certification_service.py` list-enrichment, `employee_portal_service.py` permission-resync).

### Frontend regression — `testing_agent_v4`, iteration_15 (full pass)
Full EC0–EC7 + Phase 8a–8e frontend regression, first automated UI coverage for Phase 8e. Result: 3 issues found, all in Phase 8e UI (nothing else regressed):
1. **CRITICAL** — `POST /portal/employee/training/assignments/{id}/quiz` returned `500` on every submission. RCA: `training_service.py` line ~271 did `q["id"]` (unsafe bracket access) against quiz-question dicts that have no schema enforcement (`quiz_questions: list[dict]`); any question created without a client-supplied `id` (e.g. via raw API/curl, as happened with the dev-seeded "Laminator Safety Quiz") had no `id` key at all, so this crashed on every attempt — a 100% blocker on the entire quiz-taking flow (score/pass-fail/attempt-history/retry-after-fail could never be exercised).
2. **MEDIUM** — Certifications Matrix "Issue" dialog didn't refresh after a successful issue; matrix cell + dialog kept showing stale "Missing" until a manual page reload (data was persisted correctly server-side — display-only bug).
3. **LOW** — Missing `DialogTitle` in the loading-state branch of `AssignmentDetailDialog.jsx` (Training) triggered a Radix a11y console warning.

### Fixes applied
- `backend/app/services/training_service.py` — added `_backfill_quiz_question_ids()` (assigns a server-side `uuid4` to any quiz question missing an `id`, called from both `create_training_definition` and `update_training_definition`) so every stored quiz question is guaranteed a stable identifier regardless of how the definition was created; changed the unsafe `q["id"]` lookup in `submit_quiz_attempt` to a defensive `q.get("id")`.
- `frontend/src/pages/CertificationsPage.jsx` — decoupled the Matrix tab's Issue/Renew target from the `ManageCertDialog` display state (`issueTarget` vs `cell`) so clicking "Renew"/"Issue" closes the stale overlay immediately instead of leaving it open on top of the freshly-refetched matrix.
- `frontend/src/components/training/AssignmentDetailDialog.jsx` — added `DialogHeader`+`DialogTitle` to the loading-state branch.
- Repaired the one pre-existing dev-seed Training Definition ("Laminator Safety Quiz", created via curl during Phase 8e smoke testing without a question `id`) via a `PATCH` that triggers the new backfill, so the fix could be exercised end-to-end without leaving broken sandbox data behind.

### Verification of fixes
- Backend regression re-run post-fix — **312/312 passing**, no new failures.
- Live curl E2E (main agent): fresh assignment, wrong-answer attempt → `200 {"score":0,"passed":false,"attempt_number":1}`, assignment status `failed`; correct retry → `200 {"score":100,"passed":true,"attempt_number":2}` (no `409`), assignment status transitioned to `completed`, both attempts preserved in `quiz_attempts` history — confirms the retry-after-fail fix from Phase 8e works end-to-end once the `id` bug was removed.
- `testing_agent_v4`, iteration_16 (focused retest): all 3 fixes **confirmed working live in the browser** — quiz fail→retry→pass flow via My Training UI (toasts, status transitions, attempt history all correct, no 500/409), Certifications Matrix issue-then-live-refresh with no reload needed, Training assignment dialog no longer emits the DialogTitle warning. Re-verified Work Order `AssignDialog` block/warning rendering and a 13-page EC0–EC7 smoke pass — zero regressions, zero console errors. `retest_needed: false`.
- One FYI-only, non-blocking, out-of-scope observation remains: `AssignmentDetailDialog.jsx` still emits an unrelated low-priority Radix "missing `DialogDescription`" a11y warning (distinct from the fixed `DialogTitle` warning). Not a functional defect; left as-is per the owner's "do not add optional features" instruction for this phase — candidate for a future a11y polish pass only.

### Final EC8 Phase 8e/8f test tally
- Backend: **312/312** pytest passing (full suite, all EC0–EC8 targeted tests) + terminology guard OK.
- Frontend: **2 full `testing_agent_v4` passes** (iteration_15 full regression, iteration_16 focused retest) — 100% pass on retest, 0 open defects, 1 non-blocking FYI item logged.

## EC8 Closure Statement
EC8 (Team, Scheduling, Time, Payroll, Employee Portal, Equipment Training & Certification) is **DELIVERED / CLOSED** as of this Phase 8f pass. All six phases (8a–8f) are complete, tested, and verified with zero open blocking defects. Per the owner's explicit instruction, no new checkpoint (EC9 or otherwise) begins following this closure.
