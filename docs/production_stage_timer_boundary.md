# Production Stage Timer Boundary (Future Paid Add-On)

Status: PLANNED / RESERVED — not built. No code, routes, collections, or
placeholder data exist for this feature as of EC8 Phase 8c. This document
exists so a future checkpoint can implement the add-on without re-deriving
the boundary rules or accidentally colliding with EC8's Payroll Time Clock.

## 1. Product boundary (LOCKED)

The application has, and will always have, **two distinct time-tracking
concepts**. They must never be merged into one state machine and must never
write directly into each other's collections.

| | Payroll Time Clock (EC8, delivered) | Production Stage Timer (future paid add-on) |
|---|---|---|
| Owns | Whether an Employee is "on the clock" for payroll/Timesheet purposes | Time spent by an Employee on a specific Work Order / Order Item / production stage / Equipment |
| Collections | `time_entries`, `timesheets` | (future) append-only `production_timer_events` or `production_timer_sessions` |
| Domain | EC8 Team & Workflow | Production / Work Order domain |
| Entry points | `/api/time-clock/*`, `/api/portal/employee/time-clock/*` | (future) `/api/production/*`, `/portal/employee/production` |

They **may cross-reference** each other (e.g. "employee clocked in but has
no active production timer" as a manager-facing insight) but a Shift, a
TimeEntry, and a future ProductionTimerSession are three separate records
with three separate lifecycles. No shared "state" field. No auto-conversion
of production time into payroll time without an explicit, tenant-configured
policy (see §5).

## 2. Reserved route

`/portal/employee/production` is a **reserved** Employee Portal route name.
It is not registered in `EmployeePortalApp.jsx`'s `<Routes>` and no nav item
points to it. When the add-on is built, mount it there without needing to
touch the portal shell, `EmployeePortalAuthContext`, or the token/permission
system — the same `require_employee_portal_permission(...)` dependency
pattern from Phase 8c applies unchanged (a new permission string such as
`portal:employee_production` would be added to `PortalPerm` and
`EMPLOYEE_PORTAL_PERMS`/an entitlement-gated grant list, following §5).

## 3. Future Employee Portal integration contract

When built, the Employee Portal production surface must provide:

- List of the employee's own active/assigned Work Orders
- Work Order → stage list (Order Item association preserved per stage)
- Actions: start stage, pause stage, resume stage, stop stage, complete stage
- Live elapsed active time + paused time (client displays a ticking timer
  computed from server timestamps, same pattern as `TimeClockPage.jsx`'s
  `useTicker()` — never a client-only timer that can drift or be spoofed)
- Stage notes field
- "Flag a problem / rework" indicator with a reason
- Equipment association display (read-only from the portal's perspective)
- Manager-override visibility (if a manager corrected the employee's timer,
  the employee sees that a correction happened — never a silent edit)
- Offline/retry behavior: actions must be safely retryable (idempotency key
  per action) since shop-floor connectivity is unreliable
- Duplicate-click protection identical in spirit to Phase 8c's Time Clock
  buttons (disable-while-in-flight)
- Hard rule: an employee can only ever act on **their own** production
  session — never select another employee's identity, never alter another
  employee's session. Backend-enforced exactly like Phase 8c's
  `require_employee_portal_permission` + self-scope pattern.

## 4. Future data model requirements

Append-only sessions/events only — no in-place "current state" document that
gets overwritten. Each event/session record needs:

`employee_id, tenant_id, order_id, order_item_id, work_order_id,
production_stage, equipment_id (nullable), started_at, paused_at,
resumed_at, stopped_at, completed_at, active_duration, paused_duration,
total_elapsed_duration, source, notes, rework_indicator, correction_reason,
corrected_by, audit_history`

Required invariants (backend-authoritative, never frontend-only):

- No duplicate **active** timer for the same (employee, stage) pair
- No overlapping incompatible stage sessions for the same employee
- Strict tenant isolation (same pattern as every other EC8 collection)
- No timer against a Work Order the employee isn't authorized/assigned to
- No silent historical edits — corrections are new audited events, not
  in-place mutations of a past session
- Production time is never auto-treated as payroll time; converting it into
  a payroll adjustment requires an explicit, tenant-configured policy (a
  future Phase 8d/8e concern), never an implicit default

## 5. Commercial rule (LOCKED)

Advanced Production Stage Tracking & Bottleneck Analytics is a
**configurable paid add-on**, gated through the shared plan/feature-
entitlement system — the same mechanism already used for other gated
modules (see `flyout-*` `disabled` pattern in `lib/navigation.js` and the
Feature Access settings page). It must **never** be hardcoded as always-on
in the Employee Portal, and its implementation must not assume it is
bundled into every plan unless a future commercial authority explicitly
says so.

## 6. Required analytics (future scope, not built)

Estimated vs actual time per stage; average time by stage / product
category / employee; wait time between stages; work-in-progress age; queue
length; stalled Work Orders; bottleneck stages; rework frequency; first-pass
completion rate; equipment-related delays; throughput by day/week/month;
production capacity trends.

## 7. Future manager contract (not built)

View all active stage timers; see who is working on what; correct a timer
with a reason (audited); reassign a stage; stop abandoned timers; review
bottlenecks; compare estimated vs actual; configure warning thresholds;
review overrides/corrections.

## 8. Explicit non-goals for this document

This document does not authorize starting implementation. No timer
collections, no production stage models, no `/api/production/*` routes, and
no `/portal/employee/production` page exist yet. See
`/app/memory/PRD.md` (Backlog) for scheduling status.
