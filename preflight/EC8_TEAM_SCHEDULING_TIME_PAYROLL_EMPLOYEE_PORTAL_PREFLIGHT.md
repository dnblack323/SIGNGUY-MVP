# EC8 — Team, Scheduling, Time, Payroll, Employee Portal, Equipment Training & Certification — PREFLIGHT

**Authority:** `/app/SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md` §30A.9 (EC8 base) + Part 13 (Payroll rules) + owner directive (this preflight) adding Equipment/Training/Certification as owner-locked permanent EC8 scope.
**Prereqs:** EC0–EC7 COMPLETE. EC3.1 and EC6.3 remain REQUIRED — SCHEDULED (not touched here, not absorbed into EC8).
**Repository:** `dnblack323/SIGNGUY-MVP` (permanent). No donor repo present in this environment — REB/FEB/ORIG are referenced only through the master plan's own documentation (Part 7A, Part 8.4, Part 13) as behavioral evidence. No donor source files were found on disk to inspect directly; the plan's written evidence is treated as the donor signal.
**Mode:** Documentation-only. No implementation code written. No full test suite run.

---

## 1. Feature purpose

**Who uses EC8:**
- **Tenant owner/admin/manager (staff, internal):** manage employee records, build schedules, review/correct time, run payroll, manage equipment + training + certification, review the Team Dashboard.
- **Employee (portal-facing, external to staff app):** clock in/out, view own schedule, view own timesheet, view own pay (never another employee's), complete assigned training, view own certifications, see announcements/reminders.
- **Order/Work Order flow (system-facing):** Work Order assignment consults employee certification/equipment qualification before allowing an assignment for safety-sensitive equipment.

**Problems EC8 solves:**
- Today there is no record of who works for the shop, no time tracking, no payroll, no scheduling, and no way to gate equipment use behind training/certification. All Team & Workflow sidebar entries exist only as disabled "SOON" placeholders (see §2).
- EC8 gives the shop an internal, auditable workforce system: who's on the clock, what they're owed, when they're scheduled, and whether they're qualified to run a given piece of equipment or be assigned to a Work Order that requires it.

**Internal vs portal-facing behavior:**
- Internal (staff) surfaces are permission-gated the same way every other EC1–EC7 module is (backend-authoritative `Perm` checks via `require_permission`).
- Portal-facing (Employee Portal) surfaces reuse the EC6 portal-auth foundation (`sub_scope="portal"` JWT, magic-link, separate login) but require the Portal Identity model to be **extended**, not duplicated (see §4, §6). Employee Portal permissions are strictly self-scoped (`*:self`) — an employee identity must never be able to fetch another employee's time, pay, or schedule data, enforced backend-side, not just hidden in the UI.

**What belongs in EC8:**
Employees, roles/access linkage for employees, employee scheduling, Time Clock, Timesheets, Pay Periods, Payroll Transactions (earnings/advances/payments/carryover/adjustments), Employee Portal, Team announcements/reminders, Equipment records, Equipment training, Equipment certification, Equipment access control, Work Order↔certification compatibility checks, and Team/payroll reporting (via the existing EC7 report/export foundation).

**What does not belong in EC8:**
- Tax filing, tax withholding calculation, or payroll-provider integration (explicitly out of scope — internal gross-pay/hours ledger only, per owner instruction).
- A second messaging system (reuse EC2 Notifications + Email — see §6.9).
- A second report builder or CSV exporter (reuse EC7 `reports_service.py` / `csv_export.py` — see §6.12).
- A second portal-identity/authentication system (extend EC6 `PortalIdentity` + portal JWT — see §4, §6.7).
- Wrap Lab, Webstores, AI Credits, Billing (EC9–EC13 — untouched).
- Reopening EC3.1 or EC6.3 (both remain separately scheduled).

---

## 2. Existing source map

**Backend — searched `backend/app/models`, `backend/app/routers`, `backend/app/services`, `backend/app/core`:**
- **No** `employee.py`, `payroll.py`, `timesheet.py`, `time_entry.py`, `schedule.py`, `equipment.py`, `training.py`, or `certification.py` model exists.
- **No** `employees.py`, `payroll.py`, `timeclock.py`, `timesheets.py`, `schedule.py`, `equipment.py`, `employee_portal.py` router exists.
- **No** corresponding service files exist.
- **No** collections/indexes for any of the above are registered in `core/db.py::ensure_indexes()` (full list inspected — 40+ `create_index` calls, none touch employee/payroll/schedule/equipment).
- **Partially scaffolded (unused) in `core/permissions.py`:** the `Perm` enum already declares `EMPLOYEE_READ`, `EMPLOYEE_WRITE`, `EMPLOYEE_ADMIN`, `TASK_READ`, `TASK_WRITE`, `SCHEDULE_READ`, `SCHEDULE_WRITE`, `TIME_CLOCK_READ`, `TIME_CLOCK_WRITE`, `TIMESHEET_READ`, `TIMESHEET_APPROVE`, `PAYROLL_READ`, `PAYROLL_WRITE`, `PAYROLL_ADMIN` (lines 106–119) and `PortalPerm` declares `PORTAL_EMPLOYEE_VIEW`, `PORTAL_EMPLOYEE_TIME_CLOCK`, `PORTAL_EMPLOYEE_TIMESHEET_VIEW`, `PORTAL_EMPLOYEE_PAYSLIP_VIEW` (lines 168–171). **None of these are wired to any route, any role map, or any enforcement.** `STAFF_PERMS` (the default "staff" role) does not include any of them — only `owner`/`admin` implicitly get them today (because `OWNER_ADMIN_PERMS = [p.value for p in Perm]` grants everything). This is a real gap and a naming mismatch against the owner's proposed permission set (§ "Problems found" and §"Permissions").
- **No `equipment:*`, `training:*`, `certification:*`, `timeclock:self`, `timesheet:self`, `payroll:self`, `payroll:export`, or `schedule:manage`/`employee:manage`/`payroll:manage` permission strings exist anywhere.** The owner's proposed permission set uses a different verb convention (`:manage` vs. the existing `:write`/`:admin`) — this must be resolved, not duplicated (two verbs for the same concept is exactly the "duplicate permission synonym" the owner told us to avoid).
- **`models/portal_identity.py` (EC6) is hard-wired to Customer portal use:** `customer_id: str` is a **required** field, `PORTAL_PERMS` and `PRESET_BUNDLES` are customer-shaped ("billing_only", "approver_only"), and `core/db.py` indexes `portal_identities` on `(tenant_id, customer_id)`. There is no `employee_id` field and no `portal_type` discriminator. **Employee Portal cannot use this model unmodified** — it needs additive extension (optional `employee_id`, a `portal_type: Literal["customer","employee"]` discriminator, and an employee-shaped preset bundle), not a second portal-identity collection. The underlying JWT layer (`core/portal_security.py`, `deps_portal.py`) is generic (`sub_scope="portal"`, no hardcoded customer concept) and **is** directly reusable as-is.
- **`models/user.py::Role`** is `Literal["owner", "admin", "staff"]` — there is no "employee" login role, and there must not be one. An `Employee` record is a **workforce/HR record**, distinct from a `User` (system login account). Some employees will have no `User` at all (hourly staff with no system login, portal-only or no-login); some employees will optionally link to an existing `User` (e.g., an owner who is also tracked for payroll). This link is one-directional and optional (`Employee.linked_user_id`), never the reverse.
- **Reusable service patterns already proven in EC1–EC7** (to be called, not re-implemented):
  - `services/audit.py::record_audit()` / `list_audit()` — append-only audit trail, same pattern EC8 payroll adjustments/corrections must use.
  - `services/activity.py::record_activity()` / `record_activity_with_audit()` — tenant activity feed.
  - `services/notifications.py::notify()` / `notify_tenant_owners()` / `list_for_user()` / `mark_read()` — in-app notification primitives EC8 announcements/reminders must call, not re-build.
  - `services/email.py` — outbound email (SendGrid) for reminders/announcements that should also email.
  - `services/csv_export.py::build_csv()` — formula-injection-safe CSV builder (cents→dollars, bool→yes/no), already capped at 25,000 rows. EC8 payroll/timesheet/schedule exports must call this, not write a second CSV writer.
  - `services/reports_service.py::list_reports_for_user()` / `run_report()` / `list_datasets_for_user()` / `run_custom_report()` — the EC7 curated-report + custom-report-builder registry. EC8 adds new report/dataset *definitions* into this same registry; it does not start a second report engine.
  - `services/sequence.py` — race-safe per-tenant numbering, reusable for Pay Period numbers if a human-facing sequence is wanted.
  - `models/base.py::BaseDoc` — every EC8 model extends this (`id`, `created_at`, `updated_at`), consistent with all 33 existing models.
  - `deps.py::require_permission` — the same backend-authoritative permission dependency every EC1–EC7 router uses; EC8 routers use it identically.
  - **Repository-class pattern (Decision 3):** no module from EC1–EC7 actually adopted a formal repository class — all use router → service → direct Motor/`db[coll]` calls. Decision 3 permits (does not mandate) repository classes for *new* modules. EC8 is new, so this is a genuine open choice, flagged in the ask_human gate rather than decided unilaterally.

**Frontend — searched `frontend/src/pages`, `frontend/src/lib/navigation.js`, `frontend/src/portal`:**
- `lib/navigation.js` already declares the full **Team & Workflow** flyout (`Overview`, `Employees`, `Tasks & Kanban`, `Team Schedule`, `Time Clock`, `Timesheets`, `Payroll`, `Messages & Notes`, `Announcements`, `Employee Portal`) — **every single entry has `disabled: true`** and no `to` route resolves to a real page. These are UI placeholders only; no page component exists for any of them.
- **No** `frontend/src/pages/Team*.jsx`, `Employee*.jsx`, `TimeClock*.jsx`, `Timesheet*.jsx`, `Payroll*.jsx`, `Schedule*.jsx`, `Equipment*.jsx`, `Training*.jsx`, `Certification*.jsx` files exist.
- `frontend/src/portal/` currently contains only `PortalApp.jsx`, `PortalAuthContext.jsx`, `PortalInvoicePayPage.jsx`, `portalApi.js` — all **Customer**-portal shaped. Employee Portal will sit alongside this (own routes under `/portal/employee/*` or a dedicated `/team-portal/*`, to be decided in §6), reusing the portal shell pattern but not the customer-specific pages.
- Reusable frontend primitives confirmed present and idiomatic to reuse: `components/ui/*` (shadcn), `components/layout/PageHeader.jsx`, `components/common/EmptyState.jsx` / `StatusPill.jsx` / `LoadingSkeleton.jsx`, `components/audit/AuditTimeline.jsx` (for payroll adjustment history), `components/notifications/NotificationBell.jsx` (for reminders/alerts), `components/ui/calendar.jsx` (for scheduling UI).
- No duplicate implementations found (nothing to de-duplicate) — this is a from-scratch build on top of an otherwise clean, non-conflicting codebase.

**Legacy terminology / hidden dependencies:** none found — grep for "job", "worker account", "staff payroll record" returns nothing outside this preflight's own vocabulary guardrails.

---

## 3. Current data models

None of the following collections currently exist. Documented here as the **target** shape (owner-locked requirements § carried forward), since "current" state is empty:

| Model | Tenant ownership | Employee ownership | Key fields | Status values | Relationships | History | Archive | Sensitive fields | Portal visibility |
|---|---|---|---|---|---|---|---|---|---|
| Employee | `tenant_id` | is the owner | id, linked_user_id?, name, contact, role_label, status, hire_date, termination_date, hourly_rate_cents, overtime_policy, availability, default_schedule_id, portal_access(bool), emergency_contact, notes, certifications(derived), created/updated | active, suspended, inactive, terminated, archived, reactivated | → User (optional, 1:0..1); → Certifications, TimeEntries, Shifts, PayrollTransactions | never hard-deleted; `status` transitions are audit events | soft-archive only | hourly_rate_cents, emergency_contact, SSN/bank info (deferred — no fields for these yet, flagged as future decision) | self-view of own non-sensitive fields only |
| TimeEntry | `tenant_id` | `employee_id` | clock_in_at, clock_out_at, break intervals, status (open/closed), work_order_id?, task_id?, notes, device/location meta, correction_of(entry_id)?, corrected_by, correction_reason | open, closed, corrected, void | → Employee, → optional Work Order/Task | corrections preserve original+new (append, never overwrite) | void (not delete) | location/device metadata | employee sees own only |
| Timesheet | `tenant_id` | `employee_id` | pay_period_id, daily rollups, weekly totals, regular_hours, overtime_hours(foundation), approval_status, approved_by, notes, export flag | draft, submitted, approved, locked | → Employee, → Pay Period, ← TimeEntries (derived, not duplicated data) | edit history via audit | locked at pay-period close | — | employee sees own only |
| Shift / Schedule entry | `tenant_id` | `employee_id` | date, start_time, end_time, role/station, status, published(bool), created_by, notes, recurring_source_id? | draft, published, cancelled | → Employee, → Calendar (EC1/EC2 shared calendar if present) | change history via audit | cancel (not delete) | — | employee sees own + team-published view |
| PayPeriod | `tenant_id` | tenant-wide (contains per-employee snapshots, not owned by one employee) | start_date, end_date (Sat–Fri), payday (Fri), status, employee_snapshots[], rate_snapshots[], totals, locked_at, finalized_by | open, review, approved, paid, partially_paid, closed, voided | ← Timesheets, ← PayrollTransactions | immutable once locked; snapshots frozen at lock time | voided (not deleted) | rate snapshots | employee sees only their own slice, never the whole period document |
| PayrollTransaction | `tenant_id` | `employee_id` | pay_period_id, type (earnings/adjustment/advance/repayment/payment/carryover/correction/void), amount_cents, effective_date, reference, notes, created_by | posted, voided | → Employee, → PayPeriod | append-only ledger — corrections are new rows, never edits | void via new offsetting row | amount_cents | employee sees own only |
| Advance | modeled as a `PayrollTransaction.type == "advance"` (see §6 — do **not** create a second "amount owed" field/table) | `employee_id` | amount_cents, issued_date, repayment plan (optional), notes | outstanding, repaid, partially_repaid | → Employee, ← repayment transactions | ledger | n/a | amount_cents | employee sees own only |
| Announcement | `tenant_id` | staff-authored, `audience` = all or selected employee_ids | title, body, publish_at, expires_at, acknowledgement_required(bool), created_by | draft, published, expired | → Employee(s) (audience) | — | expire (not delete) | — | employee sees own audience |
| Reminder | `tenant_id` | staff-authored or system-generated | type (missed_clock_in/out, time_off, cert_expiring, payroll_review), target employee_id?, trigger_at, delivered(bool) | pending, sent, dismissed | → Employee, → Notifications (delivery) | — | dismiss | — | recipient only |
| Equipment | `tenant_id` | tenant-wide asset | name, manufacturer, model, serial_number, category, location, status, safety_sensitive(bool), certification_required(bool), training_material_file_ids[], maintenance_refs, active/archived | active, in_maintenance, retired, archived | → Documents/Files (EC2/EC6 reuse), ← Certifications, ← TrainingAssignments | — | archive (not delete) | — | not portal-visible except read-only training material to assigned employees |
| TrainingAssignment | `tenant_id` | `employee_id` | equipment_id?, type (reading/video/SOP/quiz/practical), due_date, progress, completion_at, quiz_score, attempt_history[], acknowledgement, manager_approval | assigned, in_progress, completed, overdue, failed | → Employee, → Equipment, → Documents (materials) | attempt history retained | — | quiz_score, attempt_history | employee sees own only |
| Certification | `tenant_id` | `employee_id` | equipment_id, status, issued_date, expiration_date, trainer_id, required_score, actual_score, practical_signoff, restrictions, renewal_of(cert_id)?, revoked_reason? | not_started, in_progress, pending_signoff, certified, expired, revoked, failed | → Employee, → Equipment, ← TrainingAssignment | revocation/renewal via audit, never overwritten in place | expire/revoke (not delete) | — | employee sees own only |

**Cross-cutting rule (all models above):** every write goes through `record_audit()`; every collection gets `(tenant_id, id)` uniqueness + the query-shape indexes it needs, per the Data Integrity Rules already LOCKED for this codebase (Part 3.6 of the master plan).

---

## 4. Problems found

Because EC8 is currently unbuilt, most "problems" are **gaps to close during design**, not existing bugs. Documented explicitly so they are designed out from day one rather than discovered mid-build:

- **Duplicate payroll/schedule/Time-Clock systems:** none exist yet — risk is *creating* one later if `Employee Portal` and `Admin Time Clock` are built as two separate data paths instead of one Time Entry model with two entry surfaces. **Design must guarantee a single `TimeEntry` write path regardless of which surface created it.**
- **Confusing navigation:** the sidebar already promises 10 Team & Workflow destinations (`disabled: true` today). Design must map 1:1 onto real routes — no renaming, no consolidating two flyout entries into one page without also updating `navigation.js`.
- **Missing employee portal links:** `PortalIdentity` has no employee concept at all (see §2). If not extended correctly, the natural failure mode is a second, parallel "employee session" table — explicitly forbidden by the owner.
- **Missing backend permissions:** the existing `Perm.EMPLOYEE_*` / `SCHEDULE_*` / `TIME_CLOCK_*` / `TIMESHEET_*` / `PAYROLL_*` values use `:write`/`:admin` verbs, while the owner's requested EC8 permission set (§ Permissions) uses `:manage` and adds `:self` variants that don't exist yet (`timeclock:self`, `timesheet:self`, `payroll:self`) plus entirely new namespaces (`equipment:*`, `training:*`, `certification:*`). **This must be resolved as one decision, not left as two co-existing naming schemes** (see §9 risk "permission-catalog drift").
- **Frontend-only pay visibility risk:** the single highest-severity risk category the owner flagged (Decision 23). Design must enforce `payroll:self` / employee-scoped queries **in the router/service layer**, never rely on the Employee Portal frontend simply "not showing" other employees' data.
- **Incorrect week boundaries:** must be Saturday 00:00 → Friday 23:59:59 in the tenant's configured timezone (not UTC-naive) — a common, easy-to-get-wrong boundary bug. Needs an explicit, tested helper (reuse `core/time_utils.py` if it already contains tenant-timezone helpers — to confirm during implementation).
- **Historical rate recalculation:** the single most owner-emphasized payroll rule. `PayPeriod.rate_snapshots` and `PayrollTransaction.amount_cents` must be frozen at calculation time; changing `Employee.hourly_rate_cents` later must never cascade into closed or open Pay Periods. This must be enforced structurally (snapshot fields), not by convention.
- **Destructive edits / missing audit history:** every `TimeEntry` correction and every `PayrollTransaction` must be append-only with `record_audit()` — no in-place field overwrite on financial or time data.
- **Missing pay-period snapshots / export controls:** exports must go through the existing permission-gated, row-capped `csv_export.build_csv()` — a bespoke export path would bypass the 25k-row cap and formula-injection sanitization already proven safe in EC7.
- **Missed-clock handling gaps:** an employee who forgets to clock out must produce a detectable, correctable, audited state — not an open-ended `clock_out_at: null` that silently accrues hours forever.
- **Inconsistent employee IDs vs. user IDs:** must be resolved by making `Employee.id` authoritative for all EC8 collections, with `linked_user_id` as an optional, one-directional pointer — never using `User.id` as the FK inside Timesheets/PayrollTransactions/etc.
- **Schedule publication gaps:** a `Shift` created as `draft` must never be visible in the Employee Portal or trigger a notification until `published`.
- **Employee privacy leaks:** covered above (frontend-only visibility) plus: Team Dashboard "who is clocked in" must not itself leak another employee's pay/schedule detail beyond presence.
- **Equipment certification gaps / Work Order assignment without qualification checks:** if Work Order assignment is wired before Certification exists, or if the enforcement is added only in the frontend assignment dropdown, the "never rely only on frontend warnings" owner rule is violated. This dependency ordering is captured in the phasing (§ Phasing) — Work Order enforcement is explicitly the *last* EC8 phase (8e), after Certification exists.
- **Legacy terminology:** none present; guardrail (§ Canonical terminology) carried into every model/route name in this document.
- **Unbounded queries / missing indexes / race conditions / duplicate clock-ins / overlapping time entries / duplicate payroll transactions:** all addressed structurally in §6 (unique partial indexes on "one open TimeEntry per employee", idempotency keys on PayrollTransaction writes, pagination on all list endpoints) rather than left as review-time bugs.

---

## 5. Keep / rebuild / remove

### Keep
- `core/permissions.py` **enum mechanism** (the `Perm(str, Enum)` + `PortalPerm(str, Enum)` pattern itself) — keep the mechanism, but see §6 for the specific value changes needed.
- `models/base.py::BaseDoc`, `deps.py::require_permission`, `services/audit.py`, `services/activity.py`, `services/notifications.py`, `services/email.py`, `services/csv_export.py`, `services/reports_service.py`, `services/sequence.py` — keep unchanged, call from new EC8 services.
- `core/portal_security.py` / `deps_portal.py` — keep unchanged; already generic enough for an employee portal scope.
- `components/ui/*`, `PageHeader`, `EmptyState`, `StatusPill`, `LoadingSkeleton`, `AuditTimeline`, `NotificationBell`, `calendar.jsx` — keep, reuse for every new EC8 page.
- `lib/navigation.js` **structure** — keep the Team & Workflow flyout entries and their `testId`s; flip `disabled: true` → real routes as each phase lands (no renaming).

### Rebuild
- `models/portal_identity.py` — rebuild (additive extension): make `customer_id` optional, add `employee_id: Optional[str]`, add `portal_type: Literal["customer","employee"]`, add an employee-shaped preset bundle (e.g. `employee_self`) alongside the existing customer bundles. This is "rebuild with adaptation" of a shared system, **not** a new collection.
- `core/permissions.py` — rebuild the EC8-related permission values: retire or re-point the unused `EMPLOYEE_WRITE`/`EMPLOYEE_ADMIN`/`TIME_CLOCK_WRITE`/`TIMESHEET_APPROVE`/`PAYROLL_WRITE`/`PAYROLL_ADMIN` naming in favor of one consistent EC8 set (see §"Permissions"), add the missing `:self` variants and `equipment:*`/`training:*`/`certification:*` namespaces. Since these values are currently unused by any route, this is a safe, non-breaking rename.
- `lib/navigation.js` Team & Workflow flyout — rebuild only the `disabled`/`to` fields per phase; structure/labels stay.

### Remove or deprecate
- Nothing to remove — there is no existing duplicate or obsolete EC8-domain code. (No action needed here; recorded for completeness per the requested template.)

---

## 6. Proposed EC8 architecture

One authoritative system per concept — no parallel admin/employee data models for the same record (owner-locked rule). Employee Portal reads/writes the **same** collections as staff surfaces, filtered by `employee_id` and permission scope, never a shadow copy.

**6.1 Employee identity**
- New `models/employee.py::Employee(BaseDoc)`: `tenant_id`, `linked_user_id: Optional[str]`, `name`, `email/phone`, `role_label`, `status` (`active|suspended|inactive|terminated|archived`), `hire_date`, `termination_date`, `hourly_rate_cents`, `overtime_policy` (foundation field, no calculation logic required yet), `availability`, `default_schedule_ref`, `portal_access: bool`, `emergency_contact`, `notes`, `created_at/updated_at` (BaseDoc). Certifications are **not** duplicated onto Employee — they're queried live from the `certifications` collection (a `certifications` denormalized summary field is acceptable for list-view performance, refreshed on write, never the source of truth).
- Never hard-deleted. Status transitions (`active→terminated`, `terminated→reactivated`, etc.) are audit events via `record_audit()`.

**6.2 Time Clock → single `time_entries` collection**
- One collection, two write surfaces (Admin Time Clock page, Employee Portal Time Clock page) — both call the **same** service function (`services/timeclock_service.py::clock_in/clock_out/start_break/end_break`).
- Duplicate clock-in prevention: unique partial index `(tenant_id, employee_id)` where `status == "open"` — guarantees at most one open entry per employee at the DB layer, not just app-layer validation.
- Overlapping-entry prevention: service-layer check against existing entries for the employee in the requested window before insert; DB constraint alone can't express interval overlap, so this is enforced in the service with a re-check pattern consistent with EC4's payment idempotency approach.
- Corrections: every admin correction inserts a new entry pointing at `correction_of` and preserves the original row (`status: "corrected"`) rather than mutating it — mirrors the EC4 "controlled void" pattern already proven for Payments.

**6.3 Timesheets**
- Derived/aggregated view over `time_entries` + `pay_period_id`, persisted as a `timesheets` document per `(employee_id, pay_period_id)` once computed, so approval status has somewhere to live. Recomputed only while the pay period is `open`; frozen once the pay period locks.

**6.4 Pay Periods (Sat–Fri, Friday payday)**
- New `models/pay_period.py::PayPeriod(BaseDoc)` — tenant-wide record (not per-employee) per the "explicit record" owner requirement, containing `employee_snapshots` and `rate_snapshots` frozen at generation time. Status machine `open → review → approved → paid|partially_paid → closed`, plus `voided`. Status transitions are backend-only (no arbitrary frontend PATCH of `status` — mirrors the EC5 Work Order controlled-transition pattern already proven in this codebase).
- Week boundary computed via a single shared helper (new `services/pay_period_service.py::period_bounds()`), reused by every consumer — eliminates the "incorrect week boundary" risk class by construction.

**6.5 Payroll Transactions — append-only ledger**
- New `models/payroll_transaction.py::PayrollTransaction(BaseDoc)`: `tenant_id`, `employee_id`, `pay_period_id`, `type` (`earnings|adjustment|advance|repayment|payment|carryover|correction|void`), `amount_cents` (int, signed), `effective_date`, `reference`, `notes`, `created_by`. **No mutable "amount paid" field anywhere** — every balance (advances outstanding, total owed, total paid, carryover) is a computed sum over this ledger, exactly like the owner's instruction. This mirrors the EC4 Payment model's append-only + idempotency-key pattern already proven safe for money.
- Idempotency key on write (tenant_id + reference) prevents duplicate transaction insertion from retried requests, consistent with EC4/EC7 patterns already in the codebase.

**6.6 Advances / Payments / Carryover**
- Modeled as `PayrollTransaction.type` values, not separate tables — advances are `type="advance"` rows offset by later `type="repayment"` rows; carryover is a `type="carryover"` row linking the prior period's unpaid balance into the new period. This directly satisfies "do not create duplicate payroll systems" and "do not store only one mutable amount paid field."

**6.7 Scheduling**
- New `models/shift.py::Shift(BaseDoc)`: `tenant_id`, `employee_id`, `date`, `start_time`, `end_time`, `status` (`draft|published|cancelled`), `created_by`, `notes`, `recurring_source_id?`. Multi-employee builder is a frontend concern over the same collection (batch-create shifts for several `employee_id`s against one date/time range) — no new backend concept required beyond bulk-insert + conflict-check.
- Conflict warnings: service-layer check for overlapping shifts per employee before publish; warning, not hard block (scheduling conflicts are a business judgment call, unlike safety-sensitive equipment — see §"Work Order enforcement").

**6.8 Employee Portal**
- Extend `models/portal_identity.py` per §5. Employee Portal routes live under a new `routers/portal_employee.py` (mirrors the existing `routers/portal_customer.py` shape) reusing `deps_portal.py` dependencies with a `portal_type == "employee"` check added to the existing portal-JWT dependency chain. Frontend: new `frontend/src/portal/employee/` tree parallel to the existing customer portal tree, sharing the portal shell pattern but with its own nav (Dashboard, Time Clock, My Schedule, My Timesheet, My Pay, My Tasks, Announcements, Training, Certifications, Profile).
- `My Pay` reads `PayrollTransaction` + `PayPeriod.rate_snapshots` filtered to `employee_id == current_portal_identity.employee_id` — enforced in the router dependency, not the page component.

**6.9 Announcements / Reminders**
- New `models/announcement.py` (audience: all or selected `employee_ids`, publish/expire window, optional acknowledgement) and reminder generation logic in a new `services/team_reminders_service.py` that calls the **existing** `services/notifications.py::notify()` and `services/email.py` — no second messaging system, per owner instruction.

**6.10 Team Dashboard**
- A read-only aggregation endpoint (`routers/team_dashboard.py`) that queries `time_entries` (who's clocked in, missed clock-in/out), `shift` (scheduled today), `timesheets` (open), `pay_period` (payroll due/balances), `announcements`, `certification` (expiring), `training_assignment` (required/overdue) — no new write model, purely a compact aggregation view (owner explicitly asked for compact, not giant empty sections).

**6.11 Equipment / Training / Certification**
- `models/equipment.py::Equipment(BaseDoc)`, `models/training_assignment.py::TrainingAssignment(BaseDoc)`, `models/certification.py::Certification(BaseDoc)` per the field lists in §3. Training materials (manuals/videos/SOPs) reuse EC2/EC6 Files + Documents (`file_link`/`document_link`) — **no second file-storage path.**
- **Work Order enforcement (owner asked the preflight to recommend warning vs. hard-block vs. override):**
  - **Warning only:** Work Order requires a *skill* or *role* tag with no safety implication (e.g., "vinyl install experience preferred").
  - **Hard block (default-deny) unless overridden:** Work Order requires operation of Equipment flagged `safety_sensitive = true` (e.g., a lift, a vehicle, an industrial laminator) and the assignee has no `certified` Certification for that Equipment, or their Certification is `expired`/`revoked`. This is the recommended default because "equipment-use liability" was explicitly named as a top risk by the owner, and frontend-only warnings were explicitly rejected.
  - **Manager override:** allowed only for hard-blocked assignments, requires a `reason` string, requires a permission distinct from ordinary assignment (proposed `work_order:write` is not enough — override requires `employee:manage` or a dedicated `certification:manage`), and is always written to `record_audit()` with the reason, the overriding user, and the specific certification gap that was overridden.
  - This check lives in the **Work Order assignment service** (existing `services/work_order_service.py`, extended with a certification lookup), not in the frontend assignment dropdown — the frontend may show the same warning/block for UX, but the backend is authoritative, consistent with the "never rely only on frontend warnings" instruction.

**6.12 Reports and exports**
- New report/dataset *definitions* registered into the existing `reports_service.py` registry (`list_reports_for_user`, `run_report`, `run_custom_report`) for: employee hours, weekly timesheet, pay-period, advances, payments, carryover, employee schedule, missed clock, payroll balance, certification matrix, expiring certifications, incomplete training, equipment access. Export path is the existing `csv_export.build_csv()` — no new exporter.

**6.13 Repository-class question (open, flagged for ask_human gate)**
No prior module in this codebase uses formal repository classes despite Decision 3 permitting them for new modules. Two options, either is legitimate:
- (a) Follow the proven EC1–EC7 convention (router → service → direct `db[coll]` calls) for consistency with the rest of the codebase, or
- (b) Introduce the first repository classes here, per Decision 3's literal permission, isolated to the EC8 module only.
This is called out explicitly in the ask_human gate rather than decided unilaterally, since it's a codebase-wide precedent-setting choice, not a routine implementation detail.

---

## 7. Dependencies

| Dependency | How EC8 uses it | Status |
|---|---|---|
| Users & Permissions (EC1) | `Employee.linked_user_id` optional link; `require_permission` dependency reused verbatim; `Perm`/`PortalPerm` enums extended (not replaced) | Ready |
| Audit / Activity (EC1/EC2) | every Employee/TimeEntry/PayrollTransaction/Certification write calls `record_audit()` | Ready |
| Notifications / Email (EC2) | Announcements + Reminders (missed clock, cert expiring, payroll review) call existing `notify()`/`email.py` | Ready |
| Files / Documents (EC2/EC6) | Equipment training materials (manuals/videos/SOPs) stored via existing `file_link`/`document_link` | Ready |
| Settings (EC2) | tenant timezone (for Sat–Fri boundary calc) and default hourly rate baseline ($15/hr) read from tenant Settings namespace | Ready — confirm a `payroll` settings namespace key exists or add one additively |
| Reports (EC7) | EC8 report/export definitions plug into `reports_service.py` registry; CSV export via `csv_export.py` | Ready |
| Portal Authentication (EC6) | `PortalIdentity` extended with `employee_id`/`portal_type`; `core/portal_security.py`/`deps_portal.py` reused unchanged | Ready, needs the additive model change in §6.8 |
| Orders / Work Orders (EC3/EC5) | Work Order assignment consults Certification via an extension to `work_order_service.py`; no change to Order model | Ready — confirms Work Order assignment endpoint exists to extend (`routers/work_orders.py`) |
| Tasks | Owner's spec references "My Tasks" in Employee Portal and Team Dashboard "quick actions" — **no `tasks` collection/model exists yet anywhere in the MVP** (Tasks & Kanban is itself an EC8-owned, not-yet-built module per Part 8.4). This is not a blocking dependency issue — Tasks is built *inside* EC8 phase 8a/8b alongside Employees, not borrowed from an earlier checkpoint. Flagged so it isn't mistaken for a missing external dependency. |
| Calendar | Master plan lists a shared "Calendar" foundation feeding Team Schedule + Appointments; **no dedicated `calendar` model exists yet in the MVP either** — Team Schedule/Shift is being built directly in EC8 as the first calendar-shaped module. Flagged for the same reason as Tasks above; not a blocker, just noted so scheduling isn't assumed to be layering on a pre-existing calendar system that doesn't exist. |

---

## 8. Risks

| Risk | Mitigation designed in §6 |
|---|---|
| Employee pay exposure (wrong employee sees pay data) | Backend-enforced `employee_id` scoping on every portal query; `payroll:self` distinct from `payroll:read`/`payroll:manage` |
| Cross-tenant access | Every EC8 collection carries `tenant_id`; every query filters by it — same discipline as EC1–EC7 |
| Incorrect overtime/hours | Overtime is a *foundation field* only in this preflight (no live calculation logic promised) — avoids shipping a wrong formula |
| Duplicate time entries | Unique partial index: at most one `status="open"` TimeEntry per employee |
| Incorrect pay-period boundaries | Single shared `period_bounds()` helper, tenant-timezone aware, unit-testable in isolation |
| Rate changes rewriting history | `PayPeriod.rate_snapshots` + `PayrollTransaction.amount_cents` frozen at write time; rate change never touches existing rows |
| Advances double-counted | Ledger model (§6.6) — balance is always a computed sum, never a second stored total that can drift |
| Payments double-counted | Same ledger model + idempotency key on transaction insert |
| Carryover errors | Carryover is itself a typed ledger row (`type="carryover"`), auditable and traceable to its source period |
| Payroll export errors | Routed through the already-hardened `csv_export.build_csv()` (formula-injection safe, 25k row cap) |
| Missed-clock handling | Explicit "open entry with no clock-out past shift end" detection feeding Team Dashboard + Reminders, correctable only via audited admin correction |
| Schedule conflicts | Service-layer overlap check before publish; warning (not hard block — a business decision, not a safety one) |
| Certification bypass | Hard-block-by-default for `safety_sensitive` equipment at the Work Order assignment **service** layer, with audited override (§6.11) |
| Equipment-use liability | Same hard-block design; certification expiration/revocation immediately removes qualification (status-driven, not cached) |
| Portal data leaks | `PortalIdentity.portal_type` discriminator + `employee_id` scoping enforced in the portal dependency layer, not per-route ad hoc checks |

---

## 9. Acceptance tests

To be implemented as targeted `backend/tests/test_ec8_*.py` files during the relevant phase (per the "run targeted tests while building, one full validation at checkpoint close" instruction — not run now):

- Tenant isolation: Employee/TimeEntry/PayPeriod/PayrollTransaction/Equipment/Certification never leak across `tenant_id`.
- Employee privacy: employee A's portal token can never read employee B's time/pay/schedule (expect 403/404, not filtered-empty-200).
- Permissions: every EC8 route rejects a token lacking the specific `Perm`/`PortalPerm` required; owner/admin roles retain full access.
- Clock in/out: happy path creates one open→closed `TimeEntry`; break start/end nested correctly.
- Duplicate clock-in prevention: second clock-in attempt while one is open is rejected (not silently creating a second open entry).
- Overlapping time-entry rejection: manually-entered entry overlapping an existing entry for the same employee is rejected.
- Manual edits: admin correction preserves original row, creates a linked corrected row, requires a reason.
- Audit records: every TimeEntry correction, PayrollTransaction, Certification change produces an audit event.
- Saturday–Friday pay-period boundaries: a period generated for a given date always starts Saturday 00:00 and ends Friday 23:59:59 in tenant timezone, verified across a DST transition date if feasible.
- Friday payday behavior: `PayPeriod.payday` always lands on the Friday ending that period.
- Rate snapshots: changing `Employee.hourly_rate_cents` after a PayPeriod is generated does not change that period's `rate_snapshots` or any already-posted `PayrollTransaction.amount_cents`.
- Advances / Payments / Carryover: ledger sums reconcile to the same "balance due" the PayPeriod summary reports; no double count across a repaid advance.
- Payroll totals: `PayPeriod` totals (`total_owed`, `total_paid`, `balance_due`) equal the sum of that period's `PayrollTransaction` rows.
- Exports: CSV export respects the 25k row cap and formula-injection sanitization already proven in EC7's tests; requires `payroll:export` (or the resolved equivalent permission).
- Schedule creation / multi-employee scheduling: batch-creating shifts for several employees on one date succeeds; conflicting shift for one employee in the batch is flagged, not silently dropped.
- Schedule publication: a `draft` shift is invisible to the Employee Portal and generates no notification; publishing makes it visible and notifies.
- Employee Portal access: employee login (magic link, per EC6 pattern) succeeds only for `portal_type="employee"` identities; a customer portal identity cannot access employee routes and vice versa.
- My Pay / My Schedule: return only the authenticated employee's own records.
- Equipment training: assignment, progress, completion, quiz score, and manager approval each produce the expected status transition.
- Certification expiration: a `certified` record automatically reads as not-qualified once `expiration_date` has passed, without a separate cron job needing to have run first (i.e., expiration is evaluated at read time, not just via batch job) — with a batch/reminder job as a secondary reinforcement, not the only mechanism.
- Work Order assignment restrictions: assigning an employee lacking a required certification to a `safety_sensitive`-equipment Work Order is blocked at the API layer (not just hidden in the UI); a permitted override with reason succeeds and is audited.

---

## Permissions (proposed EC8 set)

Resolves the naming mismatch identified in §2/§4 by adopting the owner's proposed verbs as the EC8-forward standard, and retiring the currently-unused, differently-named EC1-scaffolded values (`EMPLOYEE_WRITE`, `EMPLOYEE_ADMIN`, `TIME_CLOCK_WRITE`, `TIMESHEET_APPROVE`, `PAYROLL_WRITE`, `PAYROLL_ADMIN`) since nothing consumes them yet — safe, non-breaking:

`employee:read`, `employee:manage`, `schedule:read`, `schedule:manage`, `timeclock:self`, `timeclock:manage`, `timesheet:self`, `timesheet:read`, `timesheet:manage`, `payroll:self`, `payroll:read`, `payroll:manage`, `payroll:export`, `equipment:read`, `equipment:manage`, `training:self`, `training:manage`, `certification:read`, `certification:manage`.

`TASK_READ`/`TASK_WRITE` (already declared, unused) are kept as-is for the Tasks & Kanban sub-module of EC8 phase 8a — no change needed there.

Portal (employee) permissions, added to `PortalPerm` alongside the existing (unused) `PORTAL_EMPLOYEE_*` values — to be reconciled into a single naming pass in the same pass as the staff-side rename: `portal:employee_view`, `portal:employee_time_clock`, `portal:employee_timesheet_view`, `portal:employee_payslip_view`, plus new `portal:employee_training_view`, `portal:employee_certification_view`, `portal:employee_schedule_view`.

---

## Proposed phasing (adopted from owner's default; no change recommended — source inspection did not surface a reason to reorder)

- **8a — Employees & Team Foundation:** Employee model, list/detail, roles/access linkage, Team Dashboard skeleton, Announcements, permissions, audit. (Tasks & Kanban included here per Part 8.4/13 dependency ordering, since Team Dashboard "quick actions" references tasks.)
- **8b — Time Clock & Timesheets:** clock in/out, breaks, manual corrections, missed-clock alerts, daily/weekly/monthly timesheets, approval, employee self-service (Admin Time Clock ships here as the backup surface; Employee Portal login itself lands in 8c, so 8b's employee-visible pieces are staff-surfaced first, portal-exposed in 8c).
- **8c — Scheduling & Employee Portal:** multi-employee schedule builder, draft/publish, availability, conflict warnings, My Schedule, My Tasks, Employee Portal shell/login/navigation (exposes 8b's Time Clock/Timesheet to the portal at this point).
- **8d — Payroll:** pay periods, rate snapshots, payroll transactions, advances, payments, carryover, My Pay, exports, reports.
- **8e — Equipment Training & Certification:** Equipment, training assignments, quizzes, signoff, certifications, expiration, Work Order assignment enforcement, certification matrix.
- **8f — Full frontend regression & closure:** full EC8 frontend verification, targeted EC1–EC7 regression, backend tests, frontend tests, `testing_agent_v4_fork`, docs, evidence, completion register.

No implementation begins until the ask_human gate below is answered.
