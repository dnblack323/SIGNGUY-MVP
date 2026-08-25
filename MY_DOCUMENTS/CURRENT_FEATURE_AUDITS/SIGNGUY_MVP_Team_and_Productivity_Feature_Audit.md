# SIGNGUY MVP — Team & Productivity Feature Audit

**Repository:** `dnblack323/SIGNGUY-MVP`  
**Audited branch:** `main`  
**Code baseline:** `66c0c49fb6450268ad784c7a5e291257442b3c20`  
**Audit date:** August 16, 2026  
**Scope:** Team & Productivity, including employees, schedules, shared calendar, time off, time clock, timesheets, operational payroll, tasks, communications, announcements, training, equipment, certifications, and the Employee Portal.

This is a repository-level feature audit. A capability is credited only when current code contains a usable interface, working backend behavior, or a clearly wired integration. Backend-only functions, hidden routes, rough technical interfaces, and inactive concepts are identified separately.

## Rating and AI legend

| Score | Classification | Meaning |
|---:|---|---|
| 5 | Standout / advanced | Deep, production-shaped workflow with strong safeguards, history, permissions, and useful end-to-end integration. |
| 4 | Advanced | Substantial and valuable workflow with meaningful edge-case handling; a few completeness or polish gaps remain. |
| 3 | Solid | Real, useful functionality, but the experience is narrower, partially manual, or missing important surfaces. |
| 2 | Basic | Limited or awkward workflow with major omissions or backend-only pieces. |
| 1 | Foundation only | Models, services, or an isolated route exist, but normal users cannot complete the workflow. |
| 0 | Placeholder / absent | Mentioned, reserved, or implied but not implemented as a usable feature. |

**AI labels**

- **No:** deterministic workflow; AI is not involved or required.
- **Optional:** the core feature works without AI and offers a separate AI assistance action.
- **Required:** the feature depends on an AI provider.
- **Planned / inactive:** an AI-shaped idea exists but is not connected to a live model.

## Executive scorecard

| Final category | Usable app score | Backend depth | AI | Summary |
|---|---:|---:|---|---|
| Overview | **3/5 — Solid** | 4/5 | No | Useful employee, time-clock, timesheet, announcement, and payroll snapshot; does not yet summarize the entire Team area. |
| Team / Employees | **4/5 — Advanced** | 4/5 | No | Strong employee lifecycle, audit history, payroll history, and portal-access controls. |
| Schedule | **3/5 — Solid as a consolidated area** | 5/5 | No | Team shifts and shared calendar are advanced, but split across sections; manager time-off review has no staff UI. |
| Time & Attendance | **4/5 — Advanced** | 5/5 | No | Secure clock actions, breaks, corrections, missed-clock detection, weekly review, approval, and overtime summaries. |
| Payroll | **4/5 — Advanced operational ledger** | 5/5 | No | Excellent internal gross-pay ledger with immutable transactions, carryover, and period controls; intentionally not payroll processing. |
| Tasks | **4/5 — Advanced** | 5/5 | No | Canonical task model, list, Kanban, My Tasks, comments, reminders, record handoffs, and Employee Portal tasks. |
| Communications | **3/5 — Solid backend / basic-to-solid UI** | 4/5 | No | Threads, notes, preferences, unread state, announcements, and digest exist; participant entry and digest presentation are rough. |
| Training & Equipment | **5/5 — Standout safety workflow** | 5/5 | No | Equipment access policies, training, quizzes, signoffs, certification matrix, expiration, and authoritative Work Order blocking. |
| Employee Portal | **4/5 — Advanced** | 5/5 | No | Broad self-service portal covering time, schedule, time off, tasks, messages, production, training, certifications, pay, and profile. |
| Productivity Templates | **2/5 in Team** | 4/5 | No | Powerful template foundation exists at `/templates`, but it is not surfaced inside Team & Productivity. |

### Overall assessment

Team & Productivity is one of the most technically mature parts of the MVP. The strongest areas are:

- Certification-aware Work Order assignment and equipment safety enforcement.
- Append-only operational payroll with controlled period transitions.
- Time-clock/timesheet integrity and audited corrections.
- Canonical tasks with both list and Kanban views.
- A properly isolated Employee Portal rather than exposing staff APIs to employees.

The biggest problem is **product organization**, not missing backend code. The finalized Team & Productivity structure contained eight consolidated tabs, but the current navigation displays thirteen separate modules. Schedule functions are split between Shop Operations and Team. Time Clock and Timesheets are separate instead of one Time & Attendance area. Equipment, Training, and Certifications are separate instead of one Training & Equipment area. Messages and Announcements are separate instead of one Communications area.

No Team & Productivity capability requires AI. The daily digest is deterministic, training quizzes are rule-based, and no AI-generated summaries, announcements, schedules, or task plans are active.

## Current navigation versus finalized structure

### Current repository navigation

The current Team & Productivity module row contains:

1. Overview
2. Employees
3. Equipment
4. Training
5. Certifications
6. Tasks
7. Team Schedule
8. Time Clock
9. Timesheets
10. Payroll
11. Messages
12. Announcements
13. Employee Portal

All thirteen routes are registered and reachable in the current main application.

### Final consolidated structure previously established

1. Overview
2. Team
3. Schedule
4. Time & Attendance
5. Payroll
6. Tasks
7. Communications
8. Training & Equipment

The intended grouping is still the better design. It reduces scanning and makes related work feel like one system:

- **Team:** Employees and Employee Portal administration.
- **Schedule:** Shop Calendar, Team Schedule, and Time-Off Requests.
- **Time & Attendance:** Time Clock and Timesheets.
- **Communications:** Messages, Notes, Announcements, Digest, and preferences.
- **Training & Equipment:** Equipment, Training, and Certifications.

Production, Work Orders, the production board, and the production kiosk remain owned by Shop Operations. Employee Portal production access is a self-service window into that operational system, not a reason to move production into Team & Productivity.

## 1. Overview

**Rating: 3/5 — Solid**  
**AI: No**

### Implemented dashboard features

#### Employee status snapshot

- Active employee count.
- Suspended employee count.
- Inactive employee count.
- Terminated employee count.
- Archived employee count.
- Link to employee management.

#### Live attendance snapshot

- Clocked-in count.
- On-break count.
- Open-entry count.
- Likely missed clock-out count.
- Thirty-second refresh behavior for current clock status.

#### Timesheet attention

- Count of timesheets awaiting review.
- Direct link to Timesheets review.
- Compact empty state when nothing needs review.

#### Payroll snapshot

- Permission-gated current pay-period card.
- Start and end dates.
- Friday payday.
- Remaining balance.
- Current payroll status.
- Direct link to Payroll.

#### Announcements

- Up to the current active announcements returned by the dashboard service.
- Published-time display.
- Direct link to all announcements.

### Backend data available but not fully displayed

The dashboard backend has scheduling snapshot fields such as:

- Employees scheduled today.
- Scheduled employees not clocked in.
- Unpublished draft schedules.
- Overridden scheduling conflicts.

The current `TeamDashboardPage` does not display those scheduling fields.

### Missing dashboard coverage

- No shifts-today or absence/conflict panel.
- No pending time-off requests.
- No Tasks summary or overdue-task attention.
- No unread-message count.
- No daily-digest preview.
- No training due/overdue/pending-signoff summary.
- No expiring certification summary.
- No equipment access or maintenance attention.
- No employee portal invitation/activation attention.
- No quick actions for the full Team workflow.

### Assessment

The dashboard is compact and useful, but it represents roughly half of the final Team & Productivity area. It should remain compact; the correction is to add a small attention queue or a few combined cards, not to create a giant dashboard.

## 2. Team / Employees

**Rating: 4/5 — Advanced**  
**AI: No**

### Employee directory

- Search by employee name or email.
- Employee list with:
  - Name
  - Role/title
  - Contact information
  - Hourly rate
  - Employment status
- Direct navigation to employee detail.
- Permission-gated employee creation.

### Employee creation

- Name.
- Email.
- Phone.
- Role/title.
- Hourly rate.
- Internal notes.
- Default hourly rate begins at 1,500 cents, corresponding to the shop’s established $15/hour baseline.

### Important creation-form UX issue

The form asks for **Hourly rate (cents)** and defaults to `1500`. That is technically correct for storage but poor user-facing design. Shop owners should enter `$15.00`, not mentally convert dollars into cents. The detail page repeats the same cents-based input.

### Employee detail

- Name.
- Role/title.
- Email.
- Phone.
- Hourly rate.
- Hire date.
- Emergency contact name.
- Emergency contact phone.
- Internal notes.
- Edit and save.

### Employment lifecycle

Statuses:

- Active
- Suspended
- Inactive
- Terminated
- Archived

Controls and safeguards:

- Status changes require a reason.
- No-op transitions are rejected.
- Termination date is set automatically when applicable.
- Employee records are never hard-deleted.
- Embedded status history preserves the before/after status, reason, actor, and time.
- Tenant-wide audit/activity events are also recorded.

### Employee and staff-user separation

- Employee is a workforce record.
- User is an authenticated staff account.
- An employee can optionally link to a staff user.
- Linked users must belong to the same tenant.
- A user cannot be linked to multiple employee records.
- No separate generic “employee” staff-login role was invented.

### Payroll history on employee detail

- Pay-period date range.
- Regular time.
- Overtime.
- Gross pay.
- Amount paid.
- Remaining balance.
- Pay-period status.
- Permission-gated access.

### Activity history

- Employee audit timeline.
- Employee changes and status transitions are recorded.

### Employee Portal access management

From employee detail and the dedicated portal-access page:

- Invite employee.
- Resend invitation.
- See active/suspended portal status.
- See last login or never-signed-in state.
- Suspend access.
- Reactivate a suspended identity by re-inviting.
- Idempotent invitation behavior avoids duplicate portal identities.

### Employee Portal identity safeguards

- Employee and customer portals share one proven portal-identity architecture but use a strict `portal_type` discriminator.
- Employee tokens and customer tokens are rejected from each other’s routes.
- Employee activity status is rechecked on every portal request.
- Employee Portal identity is unique per employee.
- Employee and customer portal tokens use separate browser storage keys, allowing both portal sessions to coexist.

### Limitations and missing UI

- No staff-side profile-photo upload in the employee detail page.
- No visible linked-user selector or account-link management in the employee forms.
- Structured availability blocks exist in backend and Employee Portal profile behavior but are not managed from the current employee detail UI.
- No employee documents, forms, disciplinary records, evaluations, goals, or HR document workflows.
- No onboarding checklist per employee.
- Hourly rate is entered in cents rather than dollars.
- Sensitive employee/pay data is deliberately limited to owner/admin-style permissions, which is correct but should be verified against every future role preset.

## 3. Schedule

**Consolidated-area rating: 3/5 — Solid**  
**Team Schedule: 4/5 — Advanced**  
**Shared Shop Calendar: 4/5 — Advanced**  
**Manager Time-Off UI: 1/5 — Backend only**  
**AI: No**

The schedule foundation is technically deep, but its capabilities are split across Team & Productivity, Shop Operations, and the Employee Portal.

### A. Team Schedule

#### Weekly scheduling

- Saturday-through-Friday weekly grid.
- Previous and next week navigation.
- Filter by employee.
- Add shift.
- Edit shift.
- Cancel shift without deleting history.
- Shift title.
- Location.
- Notes.
- Start and end time.
- Assigned employee.
- Copy the entire week to the next week.

#### Draft and publish workflow

- One authoritative weekly schedule per tenant.
- Draft status.
- Publish schedule.
- Published version number.
- Draft shifts are hidden from Employee Portal employees.
- Publishing notifies employees.
- Post-publish edits send targeted shift-added/changed/canceled notifications.
- Republish notifies affected employees.
- Republishing without changes is rejected to prevent duplicate notification noise.

#### Shift conflict controls

Hard-blocked conditions:

- Exact duplicate shift.
- Overlapping shift for the same employee.
- Invalid start/end range.
- Inactive employee.
- Cross-tenant employee.

Soft warning:

- Shift conflicts with an employee’s structured unavailable time.

Override behavior:

- Availability conflict can be overridden.
- Override requires a reason.
- Override reason is stored and audited.
- The UI displays an override badge on affected shifts.

#### Batch/service capabilities

- Copy shift.
- Copy day.
- Copy week.
- Assign multiple employees.
- Batch operations skip conflicting rows rather than failing the entire batch.

#### Limitations

- UI only exposes copy week, not the full copy-day/multi-employee service depth.
- No unassigned/open-shift concept.
- No employee shift-swap or shift-pickup workflow.
- No recurring-shift builder.
- No labor-budget overlay.
- No printable schedule.
- Date/time inputs are functional native controls, not a polished scheduling picker.
- The page shows create/edit/publish controls to users who can read the schedule; backend permission enforcement still protects writes, but the UI should hide actions unless `schedule:manage` is present.

### B. Shared Shop Calendar

The shared calendar is routed at `/shop-schedule` and currently appears under Shop Operations, even though the finalized Team Schedule area was intended to be its canonical home.

#### Calendar views

- Calendar view.
- Agenda view.
- Appointments view.
- Employee filters.
- Event-type filters.
- Search.

#### Unified calendar feed

One normalized feed combines:

- Stored appointments.
- Employee shifts.
- Approved absences.
- Task due dates.
- Production-stage due dates.

Projected items are not copied into duplicate calendar records. That is a strong architecture decision: the calendar remains a view of source systems rather than becoming a conflicting second database.

#### Appointment types

- Consultation.
- Site survey.
- Vehicle drop-off.
- Vehicle pickup.
- Installation.
- Customer meeting.
- Production milestone.
- Custom.

#### Appointment fields and links

- Title.
- Type.
- Date and time.
- Timezone.
- Primary employee.
- Additional assigned crew.
- Reserved equipment.
- Reserved vehicles.
- Reserved bays/work areas.
- Customer.
- Order.
- Work Order.
- Location.
- Description.
- Visibility.

#### Resource-aware availability

- Searchable people and resource selectors.
- Multiple crew members.
- Equipment reservations.
- Vehicle reservations.
- Bay/work-area reservations.
- Live availability check.
- Conflict display naming the resource, conflicting event, and time.
- Manager conflict override with required reason.
- Audited overrides.

#### Conflict detection covers

- Employee appointment overlap.
- Employee shift overlap.
- Approved absence overlap.
- Same-location overlap.
- Same-customer overlap where linked.
- Reserved equipment, vehicle, and resource conflicts in the current resource-aware page.

#### Calendar privacy safeguards

Calendar projections exclude:

- Payroll.
- Pay rates.
- Private absence reasons.
- Pricing.
- Profit and margin.
- Internal notes.
- Raw file paths.

#### Missing schedule/calendar features

- No Google Calendar sync.
- No Outlook sync.
- No two-way external-calendar conflict handling.
- No recurring appointments.
- No customer self-booking.
- No automatic appointment confirmation/reminder delivery workflow.
- No drag-and-drop calendar rescheduling.
- Calendar placement is split between Shop Operations and Team instead of one canonical Team Schedule workspace with contextual links from Shop Operations.

### C. Time-Off Requests

#### Employee Portal features

- Submit time-off request.
- Request types:
  - Vacation
  - Sick
  - Personal
  - Bereavement
  - Jury duty
  - Unpaid
  - Other
- Date, start time, and end time.
- General reason.
- Private reason.
- Status filters.
- Request statuses:
  - Pending
  - Clarification requested
  - Approved
  - Denied
  - Canceled
- Respond to manager clarification request.
- Cancel pending, clarification-requested, or approved request.
- View manager note.
- Preserve request history.

#### Manager backend features

- List requests.
- View request detail.
- Approve.
- Deny.
- Request clarification.
- Conflict information from existing shifts.
- Approved absence projection into the shared calendar.
- Does not automatically alter or delete conflicting shifts.
- Private reasons stay out of broad calendar views.

#### Critical availability gap

There is no routed staff page for managers to review, approve, deny, or request clarification. The employee can submit a request, but the manager-facing half currently requires direct API use. This is the most important incomplete workflow in Team & Productivity.

## 4. Time & Attendance

**Rating: 4/5 — Advanced**  
**Backend depth: 5/5**  
**AI: No**

### A. Time Clock

#### Employee self-service

- Live local clock display.
- Clock in.
- Optional Work Order ID at clock-in.
- Optional notes at clock-in.
- Live elapsed worked time.
- Start break.
- End break.
- Clock out.
- Prevent clock-out while a break is still open.
- Current state: not clocked in, clocked in, or on break.
- Thirty-second server refresh plus local elapsed-time ticker.

#### Manager controls

- Team Time Clock list.
- See active employee clock state.
- Clock an employee in.
- Start/end an employee break.
- Clock an employee out.

#### Integrity controls

- Only one open entry per employee through a database-level partial unique index.
- Overlapping-entry prevention.
- Cross-tenant isolation.
- Employee self-scope.
- Manager-only control of another employee’s time.
- Work minutes and break minutes stored and derived consistently.
- Open/completed/void lifecycle.

#### Corrections and voids

- Correct clock-in time.
- Correct clock-out time.
- Correction requires a reason.
- Original values remain preserved in correction history.
- Backend void requires a reason and preserves history.
- Timesheet aggregates refresh after time-entry changes.

#### Limitations

- Staff clock-in uses a raw Work Order ID rather than a search/selector.
- No geofence, IP restriction, device restriction, photo clock-in, or kiosk-mode time clock.
- No automatic reminder to clock in/out despite missed-clock calculations.
- Manager entry correction lives under Timesheets, not the Time Clock page.

### B. Timesheets

#### Period behavior

- Saturday-through-Friday work week.
- Weekly employee timesheet.
- Backend daily, weekly, and monthly summary services.
- Current staff UI focuses on weekly view.
- Previous and next week navigation.

#### Summary values

- Worked time.
- Break time.
- Regular time.
- Overtime time.
- Estimated gross pay using current/live rate.
- Incomplete-entry count.
- Likely missed-clock-out count.

#### Entry detail

- Work date.
- Clock-in and clock-out times.
- Worked minutes.
- Break minutes.
- Current entry state.
- Correction count.
- Manager correction action.

#### Review workflow

- My Timesheet.
- Team Review.
- Pending-review list.
- Select employee.
- Approve.
- Reject with required reason.
- Reopen with audit reason.
- Review-history foundation.

#### Limitations and defects

- The visible Timesheet **Export** button is disabled.
- Its tooltip still says export will be available when Payroll lands, even though Payroll is already implemented. This is stale product state.
- The backend has payroll/report exports, but there is no usable timesheet export action on this page.
- Daily and monthly totals are described in the page subtitle/backend but not exposed as selectable UI modes.
- No clear employee Submit Timesheet action is present; weekly records appear in pending/review behavior without a polished employee-submission step.
- Status pills reuse announcement/employee color mappings rather than a dedicated timesheet status design.
- No printable weekly timesheet.
- No manager bulk approval.

## 5. Payroll

**Rating: 4/5 — Advanced operational payroll ledger**  
**Backend depth: 5/5**  
**AI: No**

### Scope boundary

This is correctly presented as an internal gross-pay ledger, not a payroll processor, tax system, or bank. It handles hours, estimated earnings, advances, payments, adjustments, and carryover.

### Pay-period rules

- Saturday-through-Friday week.
- Friday payday.
- One authoritative tenant pay period per week.
- Previous/next period navigation.
- Pay-period history.

### Period states and controlled actions

States include:

- Open
- Review
- Approved
- Partially paid
- Paid
- Closed
- Voided

Actions:

- Recalculate.
- Approve.
- Reopen with required reason.
- Close.
- Void with required reason.
- Closing with unpaid balance or warnings requires an override reason.
- Closing carries unpaid balance forward.
- Voiding a period reverses its transactions with offsetting rows rather than deleting history.

### Payroll calculation snapshot

- Employee count.
- Regular minutes.
- Overtime minutes.
- Regular earnings.
- Overtime earnings.
- Gross pay.
- Total paid.
- Remaining balance.
- Warning count.
- Rate snapshot preserves historical rate even when the employee’s rate changes later.
- Earnings lock after approval unless the period is deliberately reopened.

### Overtime settings

- Enable/disable overtime estimate.
- Weekly threshold in hours.
- Overtime multiplier.
- Explicit statement that the calculation is an internal estimate and does not include withholding.

### Append-only employee ledger

Manual transaction types:

- Advance.
- Payment.
- Adjustment.
- Advance repayment.

Automatic/system types also support earnings, overtime earnings, carryover, corrections, and void offsets.

Transaction fields:

- Employee.
- Pay period.
- Type.
- Amount.
- Effective date.
- Reference.
- Actor/audit information.

Ledger behavior:

- Integer-cent storage.
- Append-only historical rows.
- Voiding creates an offsetting entry and marks the original as voided.
- No mutable “amount paid” field that can silently drift.
- Idempotency safeguards for transaction insertion.
- Advance balance is derived from ledger activity.
- Carryover is a traceable typed transaction.

### Payroll page

Tabs:

- Pay Periods.
- Employee Ledger.
- Settings.

Pay Periods features:

- Current period summary.
- Snapshot table.
- Warning indicators.
- Open employee ledger directly from a snapshot.
- Historical period list.

Employee Ledger features:

- Select employee.
- Optional pay-period filter.
- Record transaction when a specific period is selected.
- Reference field clearly warns against storing bank information.
- Void eligible transactions.

### Employee payroll views

- Payroll history on employee detail.
- Employee Portal My Pay.
- Employee self-scope enforced by portal identity.
- Sensitive internal rates/notes are stripped from Employee Portal responses.

### Reports and exports

- Backend payroll CSV export exists.
- Team/labor reports include time and payroll-shaped datasets in the reporting system.
- Payroll financial totals can be surfaced in Business & Finance reporting without moving payroll operations out of Team & Productivity.

### Limitations

- No visible payroll-export button in the current Payroll page despite backend export support.
- No formatted pay-stub PDF.
- No ACH or direct deposit.
- No bank account or Social Security number storage.
- No withholding or statutory deduction engine.
- No employer-tax calculation.
- No payroll tax deposits or filing.
- No W-2 generation.
- No 1099 generation.
- No accounting-system sync.
- Advances and payments are manually recorded.
- Overtime logic is an internal configurable estimate, not jurisdiction-aware compliance payroll.

### Permission mismatch to fix

- Navigation exposes Payroll to `payroll:read`.
- The main Pay Periods tab only loads when the user has `payroll:manage` and otherwise displays No Access.
- Read-only payroll users therefore see a navigation item but cannot use the primary page as expected.
- Payroll Settings is rendered within the same page and relies heavily on backend write enforcement; the UI should explicitly gate viewing/editing according to read/manage permissions.

## 6. Tasks

**Rating: 4/5 — Advanced**  
**Backend depth: 5/5**  
**AI: No**

### Canonical task model

- One task system shared by staff and Employee Portal.
- Tenant-scoped.
- Title.
- Description.
- Priority.
- Task type.
- Source metadata.
- Assigned staff user.
- Assigned employee.
- Due date.
- Start/completion/archive timestamps.
- Visibility and employee-visible controls.
- Idempotency key.
- Version and history arrays.
- Minimal recurrence/reminder fields.

### Statuses

- Not started.
- In progress.
- Waiting.
- Blocked.
- Completed.
- Canceled.

### Controlled transitions

- Start.
- Wait.
- Block.
- Resume.
- Complete.
- Cancel.
- Protected reopen from completed/canceled.
- Archive.
- Restore.
- Kanban movement calls the same backend transition actions rather than writing arbitrary status values.

### Priority levels

- Low.
- Normal.
- High.
- Rush.

### Linked-record support

- Customer.
- Quote.
- Order.
- Order Item.
- Work Order.
- Invoice.
- Production Stage.

Safeguards:

- Server validates linked record existence and tenant ownership.
- A task link does not grant permission to the linked record.
- Reusable task-handoff button exists on Customer, Order, and Work Order detail.
- Handoff creation uses source metadata and idempotency without mutating the source record.

### Assignments

- Assign to active staff user.
- Assign to active employee.
- Assign to both only when the employee is linked to that exact staff user.
- Reject inactive or cross-tenant assignees.
- Reassignment history and notification.
- Duplicate same-assignee reassignment is idempotent.

### List view

- Search.
- Status filter.
- Priority filter.
- Assignee filter.
- Task-type filter.
- Linked-entity filter.
- Due range.
- Overdue.
- Unassigned.
- Archived.
- Created-by.
- Pagination.
- Sorting by due date, priority, newest, oldest, recently updated, assignee, and title.
- Quick lifecycle actions.
- Focused detail panel.

### System views

- All Active.
- My Tasks.
- Due Today.
- Overdue.
- Unassigned.
- Blocked.
- Waiting.
- Completed Recently.

### Kanban

- Not Started column.
- In Progress column.
- Waiting column.
- Blocked column.
- Completed column.
- Canceled tasks hidden by default.
- Drag and drop.
- Optimistic movement.
- Rollback on failure.
- Refresh from authoritative backend state.
- Prevent duplicate pending movement.

### My Tasks

- Staff-user-scoped My Tasks.
- Due today count.
- Overdue count.
- Upcoming count.
- Blocked count.
- Waiting count.
- Completed recently count.

### Comments

- Internal comments.
- Employee-visible comments.
- Comment editing.
- Comment changes are audited.
- Comment bodies are not copied into broad audit metadata.
- Comments are deliberately not treated as a parallel message-thread system.

### Reminders and notifications

- Assignment and reassignment notifications.
- Status-change notifications.
- Due-date-change notifications.
- Due reminders.
- Overdue reminders.
- Idempotent reminder records prevent duplicate generation.
- Notification failure does not roll back task state.

### Employee Portal My Tasks

- Only assigned, employee-visible tasks.
- Current, due today, overdue, waiting, blocked, and completed-recently filters.
- View detail.
- Start.
- Wait.
- Block.
- Resume.
- Complete.
- Add employee-visible comments.
- Employee cannot reassign, change priority, archive, or access staff routes.

### Limitations

- User-created saved views are not implemented.
- Fully customizable Kanban boards are not implemented.
- No checklist/subtask experience in the current task page despite task-checklist template types existing.
- Recurrence fields exist, but there is no recurring-task scheduler.
- Due/overdue reminder generation has no background worker or daily scheduler.
- No daily task digest delivery worker.
- Task form exposes linked record IDs as technical fields instead of searchable selectors.
- No attachments on tasks.
- No task dependencies.
- No workload/capacity planning.
- No time estimate versus actual comparison.
- No AI task creation, task breakdown, summarization, or prioritization.

## 7. Communications

**Rating: 3/5 — Solid backend, rough UI**  
**Backend depth: 4/5**  
**AI: No**

### Communications workspace tabs

- Inbox.
- Notes.
- Announcements.
- Digest.
- Preferences.

### A. Message threads

#### Backend capabilities

- Direct and group thread types.
- Staff-user participants.
- Employee participants.
- Same-tenant active-participant validation.
- Internal or employee-visible visibility.
- Participant membership enforcement.
- Thread list.
- Thread messages.
- Replies.
- Add/remove participant foundation.
- Per-identity read state.
- Unread counts and badge count.
- Employee Portal self-scoped thread access.
- Customer Portal tokens rejected.
- Audit/activity around communication records.

#### Staff UI

- Create a thread.
- Thread title.
- Staff participants.
- Employee participants.
- First message.
- Thread list.
- Unread badge.
- Thread detail.
- Reply.

#### Major UI weakness

Participants are entered as **comma-separated staff user IDs and employee IDs**. This is not acceptable production UX. It should use searchable people pickers with names, roles, and clear visibility rules.

### B. Internal notes

- Shared canonical notes collection.
- Title.
- Body.
- Visibility.
- Optional Task link.
- Optional Order link.
- Optional Work Order link.
- Tenant validation.
- Notes do not create module-local duplicate note systems.
- Staff notes list.

Limitations:

- Links use raw IDs.
- No edit/archive actions in the visible Notes page.
- No author/date prominence in the current list.
- No attachments.
- No rich text or mentions.

### C. Announcements

#### Backend

- Draft, published, and expired states.
- Audience all or selected employees.
- Publish/expire window foundation.
- Optional acknowledgement concept in the model/preflight design.
- Publish notification to linked users.
- Employee Portal audience filtering.

#### Staff UI

- Create draft.
- Title.
- Message body.
- Publish draft.
- Status.
- Drafted/published relative time.
- Active announcements on Team Overview.
- Employee Portal announcements list.

#### Announcement UI limitations

- Creation always sets audience to all.
- No selected-employee audience picker.
- No publish-at or expire-at scheduling UI.
- No acknowledgement-required option or acknowledgement tracking UI.
- No edit/archive action in the visible page.
- The Communications Announcements tab only explains that announcements are managed on the separate page; it does not embed or manage them.

### D. Daily Digest

#### Backend

- Derived from source systems rather than duplicating tasks/calendar/messages.
- Can include task, message, appointment, schedule, and operational attention sections.
- Respects communication preferences and quiet-hour concepts.
- Excludes payroll, pricing, profit, margin, and private notes.
- Digest preview/generation records.
- Employee Portal digest preview.

#### Staff UI

- Digest preview tab.
- Current implementation displays raw JSON inside a code-style block.

#### Employee Portal UI

- Compact Today card with tasks due, unread messages, and upcoming appointments.

#### Digest limitations

- No background generation/delivery worker.
- No production email-delivery workflow.
- No AI-generated prose or prioritization.
- Staff preview is technical rather than a polished daily brief.

### E. Communication preferences

- In-app messages.
- Task notifications.
- Schedule changes.
- Time-off decisions.
- Appointment reminders.
- Announcements.
- Daily digest.
- Email delivery preference.
- Digest time.
- Quiet-hours start.
- Employee Portal preferences and quiet hours.

Limitations:

- Quiet-hours UI exposes only a start value in the staff page excerpt rather than a polished full range editor.
- Preference saves occur on checkbox toggles/field blur with limited confirmation.

### F. Missing communication features

- No customer participation in internal threads.
- No combined manager view of employee and customer communications.
- No SMS sending.
- No MMS.
- No voice messages, transcription, or calling.
- No email-thread synchronization.
- No attachments.
- No @mentions or reactions.
- No message search in the visible workspace.
- No pinned threads.
- No read receipts beyond internal read-state/unread counts.
- No scheduled messages.
- No AI reply drafting, summarization, or digest generation.

## 8. Training & Equipment

**Overall rating: 5/5 — Standout safety workflow**  
**Equipment management: 4/5**  
**Training: 4/5**  
**Certification enforcement: 5/5**  
**AI: No**

This is the most differentiated Team & Productivity capability because certification status is not merely reported—it authoritatively controls safety-sensitive Work Order assignments.

### A. Equipment

#### Equipment categories

- Printer.
- Laminator.
- Plotter.
- Cutter.
- Heat press.
- Embroidery machine.
- Lift.
- Vehicle.
- Specialty tool.
- Other.

#### Equipment statuses

- Active.
- Inactive.
- Maintenance.
- Retired.
- Archived.

#### Access policies

- No certification required.
- Recommended; never blocks.
- Certification required; manager override allowed.
- Certification required; no override, hard block.

#### Equipment fields and controls

- Name.
- Category.
- Location.
- Status.
- Access policy.
- Safety-sensitive flag.
- Description.
- Safety notes.
- Archive.
- Status filter.
- Linked documents display.
- Required training display.
- Pending training assignments.
- Active and expiring certification information.
- Equipment detail tabs for Overview, Training, and Certifications.

#### Equipment limitations

- Linked documents are read-only in the equipment page.
- No manager UI to link/unlink documents.
- No maintenance schedule, service log, downtime tracking, calibration, meter reading, warranty, parts, or inspection checklist.
- No equipment reservation calendar directly on equipment detail, although the shared calendar can reserve equipment.

### B. Training Definitions

Training types:

- Reading.
- Video.
- SOP review.
- Quiz.
- Practical demonstration.
- Manager signoff.
- Retraining.

Definition fields:

- Title.
- Description.
- Optional linked equipment.
- Training type.
- Practical-signoff requirement.
- Passing score for quizzes.
- Quiz questions.
- Two to five answer choices per question.
- Correct answer designation.
- Edit.
- Archive.
- Active/inactive status.

### C. Training Assignments

- Assign training to employee.
- Select definition.
- Due date.
- Manager notes hidden from employee.
- Status filtering.
- Statuses:
  - Not started
  - In progress
  - Pending signoff
  - Completed
  - Failed
  - Expired
  - Canceled
- Overdue display.
- Latest score.
- Start.
- Complete.
- Quiz attempt.
- Mark failed.
- Cancel.
- Practical signoff.
- Pass/fail signoff result.
- Signoff notes.

### D. Quiz behavior

- Server-backed scoring.
- Configurable passing score.
- Stable question IDs.
- Employee never receives correct-answer index in advance.
- Preserve every attempt.
- Show attempt number, score, result, and completion time.
- Failed employee can retry.
- Passing retry correctly completes the assignment.
- Quiz bugs found during testing were corrected and retested through fail → retry → pass.

### E. Practical signoff

- No self-certification when signoff is required.
- Employee completes the employee-controlled portion.
- Assignment moves to pending signoff.
- Manager records pass/fail result.
- Notes and signoff history are preserved.

### F. Certifications

- Employee × Equipment matrix.
- All-certifications list.
- Issue certification.
- Renew certification.
- Revoke certification.
- Revocation reason required.
- Issue date.
- Expiration date or never expires.
- Restrictions.
- Expiring-soon indicator.
- Effective expiration calculated at read time; qualification does not depend on a background job running.
- Permanent certification history.
- Status filters.

### G. Work Order safety enforcement

#### Work Order requirements

- Required equipment IDs.
- Required role.
- Manager requirement editor on Work Order detail.

#### Assignment decision engine

For each proposed employee and required equipment:

- No-required/recommended equipment never blocks.
- Missing, expired, or revoked certification under no-override policy creates a hard block.
- Missing, expired, or revoked certification under override-allowed policy creates a warning requiring a manager reason.
- Required-role mismatch is advisory only.
- Cross-tenant assignees are rejected.

#### Authoritative enforcement

- Decision occurs in backend Work Order assignment service.
- Frontend renders the backend decision rather than reimplementing rules.
- Hard-blocked employee cannot be saved.
- “Assign anyway” appears only for override-eligible warnings.
- Override requires reason.
- Reason and certification gap are audited.

This is a 5/5 feature because it connects employee records, equipment policy, training, certifications, expiration, Work Orders, permissions, and audit history into one real safety control.

### H. Employee Portal training and certifications

- My Training list.
- Training detail.
- Materials list.
- Quiz-taking interface.
- Completion and signoff state.
- My Certifications read-only list.
- Renewal-needed/expiration indicators.
- Self-scoped API access.
- Correct-answer keys, manager notes, and override/audit details stripped from employee responses.

### Limitations

- Training materials show titles but have no employee-safe view/download action.
- No manager document link/unlink UI.
- No learning paths or prerequisite chains.
- No automatic retraining schedule.
- No recurring certification reminder worker described as production-complete.
- No external course provider integration.
- No e-signature for training acknowledgement or practical signoff.
- No voice/video capture for demonstrations.
- Certification action buttons are visible from a page gated by `certification:read`; UI should additionally hide issue/renew/revoke controls without `certification:manage`, even though backend enforcement remains authoritative.

## 9. Employee Portal

**Rating: 4/5 — Advanced**  
**Backend/security depth: 5/5**  
**AI: No**

### Portal administration

- Invite active employees.
- Resend invitation.
- Magic-link activation/login architecture.
- Suspend access.
- Reactivate by re-invite.
- Last-login status.
- One portal identity per employee.
- Portal permission resync when re-inviting older identities.

### Employee Portal areas

- Home.
- Time Clock.
- My Schedule.
- My Time Off.
- My Tasks.
- Messages.
- Announcements.
- Production.
- My Training.
- My Certifications.
- My Pay.
- Profile & Preferences.

### Home dashboard

- Employee identity/profile summary.
- Time-clock state.
- Schedule information.
- Pay summary.
- Training due/overdue/pending-signoff counts.
- Certification expiring/expired counts.
- Announcements and other self-service attention from connected modules.

### My Schedule

- Published shifts only.
- Date, start/end time, title, location, and status.
- Calendar overlays for assigned appointments, absences, and due dates.
- Draft schedule is not exposed.

### My Time Off

- Full request, filter, clarification response, and cancellation behavior described in Schedule.

### My Timesheet

- Week range.
- Worked time.
- Break time.
- Status.
- Does not expose another employee’s records.

### Messages and digest

- Employee-visible participant threads only.
- Thread detail.
- Replies.
- Unread count.
- Daily snapshot of task, message, and appointment attention.
- Communication preferences and quiet hours.

### My Pay

- Self-scoped pay information.
- Pay-period data and payment/balance history.
- Internal rate fields and manager notes removed from employee response.

### Profile & Preferences

- Preferred name.
- Contact email.
- Phone.
- Profile-image file reference.
- Availability notes.
- Structured availability blocks.
- Timezone.
- Emergency contact fields.
- Communication preferences.
- Quiet hours.

Protected fields cannot be self-edited:

- Employment status.
- Pay rate.
- Role/permissions.
- Linked staff user.
- Activation state.

### Production access

- Current production task.
- Assigned production tasks.
- Visible shop queue.
- Production task actions through self-scoped routes.
- Search shop queue.
- Compact Time Clock card.

Production ownership remains in Shop Operations; the portal provides the employee-facing execution surface.

### Security strengths

- Employee identity comes from the portal token, never a client-supplied employee ID.
- Inactive employee is denied on every request.
- Customer and employee portal tokens cannot cross-access.
- Staff endpoints reject portal tokens.
- Profile images must reference tenant-owned files; inline base64 is rejected.
- Private and sensitive fields are explicitly removed from portal responses.

### Limitations

- No separate polished password-recovery UI was added to the Employee Portal.
- No employee-accessible training-material download.
- No shift-swap or availability-approval workflow.
- No employee timesheet submission/correction-request workflow.
- No pay-stub PDF.
- No document center, handbook acknowledgement, or e-signature.
- No mobile push notifications.
- No native mobile app/offline behavior.

## 10. Productivity Templates

**Rating inside Team & Productivity: 2/5 — Related capability is hidden elsewhere**  
**Backend depth: 4/5**  
**AI: No**

A broad template system exists at `/templates`, but it is not listed in Team & Productivity navigation.

### Team/productivity template types

- Task.
- Task checklist.
- Appointment.
- Appointment confirmation.
- Appointment reminder.
- Message.
- Announcement.
- Note.
- Daily digest.
- Email.
- SMS content.
- Support response.
- Bug response.
- Feature-request response.
- Time-off response.

### Template capabilities

- Platform master templates.
- Tenant-owned copies.
- Starter templates and starter packs.
- Install template.
- Install pack.
- Edit tenant copy.
- Duplicate.
- Preview.
- Validate placeholders.
- Archive and restore.
- Source version tracking.
- Source-update available indicator.
- Compare with newer source.
- Install a newer source as a separate copy without overwriting tenant edits.
- Allowlisted placeholders.
- Channel-specific validation and rendering.
- Secret-like and unsafe content rejection.

### Important boundaries

- Rendering produces editable output.
- It does not automatically send.
- SMS bodies can be stored and validated, but there is no SMS delivery path.
- Applying a template does not mutate the linked task, appointment, communication, support, bug, feature, or time-off source record.
- No AI generation is required.

### Limitations

- No template picker is integrated into the current Team task, announcement, communication, or time-off forms.
- No automatic appointment reminders.
- No automated message/email/SMS campaigns.
- No template marketplace or paid Template Vault.
- The route is not discoverable from the Team area.

## 11. AI dependency and special-media map

| Feature | AI status | Current behavior |
|---|---|---|
| Overview | No | Deterministic aggregations. |
| Employees | No | CRUD, status, payroll, and portal controls use ordinary business rules. |
| Team Schedule | No | Conflict checks and copy/publish behavior are deterministic. |
| Shared Calendar | No | Feed projection and availability are deterministic. |
| Time Off | No | Workflow and conflict display are deterministic. |
| Time Clock & Timesheets | No | Time calculations and approvals are deterministic. |
| Payroll | No | Ledger and pay estimates use stored time/rates/settings. |
| Tasks | No | Status, Kanban, reminders, and filters are deterministic. |
| Communications | No | Threads, notes, preferences, unread state, and digest are deterministic. |
| Training & quizzes | No | Quiz scoring and signoff use explicit rules. |
| Certifications | No | Expiration and Work Order qualification checks use explicit policy. |
| Employee Portal | No | Self-scope and portal experiences do not require AI. |
| Templates | No | Placeholder validation/rendering is deterministic. |

### AI features not implemented here

- AI schedule generation.
- AI labor forecasting.
- AI task breakdown or prioritization.
- AI announcement/message drafting.
- AI conversation summaries.
- AI daily-digest prose.
- AI training-course generation.
- AI quiz generation or grading.
- AI payroll anomaly detection.

### Voice, signature, and rich-media status

- No voice messaging.
- No call recording or transcription.
- No training video capture workflow.
- No employee e-signatures.
- No signed policy acknowledgements.
- No biometric time clock.
- No photo-based clock-in.

## 12. Features that are not complete or not implemented

The following should not be presented as finished Team & Productivity features:

- Consolidated eight-tab Team navigation.
- Manager Time-Off Requests page.
- Timesheet export from the Timesheets page.
- Read-only payroll experience matching `payroll:read` navigation.
- Production payroll processing, withholding, direct deposit, filing, W-2s, or 1099s.
- Automatic recurring tasks.
- Background task reminder worker.
- User-created task saved views.
- Custom Kanban board configuration.
- Task checklists/subtasks in the main task UI.
- Communication participant picker.
- Polished staff daily digest.
- Digest email-delivery worker.
- SMS/MMS sending.
- Attachments in messages/tasks.
- Unified internal and customer communications inbox.
- Google/Outlook calendar sync.
- Recurring shifts or appointments.
- Shift swaps/open shifts.
- Training-material download in Employee Portal.
- Equipment maintenance/service management.
- Employee document center and acknowledgements.
- E-signatures.
- Any AI-powered Team workflow.

## 13. Permission and UI consistency findings

Backend permission enforcement is generally strong, but several frontend surfaces should be corrected so read-only users do not see controls they cannot successfully use.

### Payroll

- Navigation requires `payroll:read`.
- Primary Pay Period view requires `payroll:manage` in the page logic.
- Settings and ledger presentation should be separated into read and manage capabilities.

### Team Schedule

- Navigation requires `schedule:read`.
- Add, edit, cancel, copy, publish, and republish controls are rendered without an explicit `schedule:manage` UI check.
- Backend still blocks unauthorized writes, but the user experience is misleading.

### Certifications

- Page access checks `certification:read`.
- Issue, renew, and revoke controls should be gated by `certification:manage` in the UI.

### Announcements

- Navigation has no explicit permission requirement.
- Creation/publish actions depend on employee-management permission in the page, while backend announcement permissions were later formalized separately.
- Navigation and page permissions should use the same canonical `announcement:*` contract.

### Time Clock and Timesheets

- The combined future Time & Attendance tab should route users to the correct self or manager surface based on `timeclock:*` and `timesheet:*` permissions.

## 14. Highest-value corrections

1. Consolidate the thirteen navigation items into the eight finalized Team & Productivity tabs.
2. Build the manager Time-Off Requests page using the already-complete backend.
3. Move the shared Shop Calendar into the Schedule workspace while keeping contextual Shop Operations links.
4. Enable real timesheet export and remove the stale “when Payroll lands” tooltip.
5. Replace cents-based hourly-rate inputs with dollar inputs while continuing to store integer cents.
6. Replace raw IDs in messages, notes, tasks, and Time Clock with searchable entity selectors.
7. Align read/manage UI gating for Payroll, Team Schedule, Certifications, and Announcements.
8. Upgrade Communications with real people pickers, message search, attachments, and a readable digest.
9. Surface tasks, unread messages, pending time off, training, certification, and schedule attention on the compact Team Overview.
10. Add safe employee access to training documents and policy acknowledgements.

## 15. Strongest features by advancement

### Standout / 5-level capabilities

- Certification-aware Work Order assignment with hard block, overrideable warning, audited override, and live expiration/revocation checks.
- Append-only payroll transaction architecture and controlled period void/reopen/close behavior.
- Employee/customer portal type isolation and employee self-scope.
- Time-entry integrity through duplicate-open and overlap prevention plus preserved corrections.

### Advanced / 4-level capabilities

- Employee lifecycle and portal administration.
- Weekly Team Schedule with draft/publish/republish and availability conflicts.
- Resource-aware shared calendar.
- Time Clock and timesheet review.
- Operational payroll page.
- Task List, Kanban, My Tasks, comments, and module handoffs.
- Training definitions, quizzes, assignments, and practical signoff.
- Employee Portal breadth.

### Solid / 3-level capabilities

- Team Overview.
- Announcements.
- Communications staff interface.
- Time-off employee experience when considered separately from missing manager UI.

### Basic or hidden capabilities

- Manager time-off review UI.
- Team-accessible productivity templates.
- Automated digest/reminder delivery.

## 16. Principal code evidence

The audit was grounded primarily in current navigation/router code, page implementations, backend models/services/routers, tests, and completion evidence, including:

- `frontend/src/lib/navigation.js`
- `frontend/src/App.js`
- `frontend/src/pages/TeamDashboardPage.jsx`
- `frontend/src/pages/EmployeesPage.jsx`
- `frontend/src/pages/EmployeeDetailPage.jsx`
- `frontend/src/pages/EmployeePortalAccessPage.jsx`
- `frontend/src/pages/TeamSchedulePage.jsx`
- `frontend/src/pages/ShopSchedulePage.jsx`
- `frontend/src/pages/TimeClockPage.jsx`
- `frontend/src/pages/TimesheetsPage.jsx`
- `frontend/src/pages/PayrollPage.jsx`
- `frontend/src/pages/TasksPage.jsx`
- `frontend/src/pages/CommunicationsPage.jsx`
- `frontend/src/pages/AnnouncementsPage.jsx`
- `frontend/src/pages/EquipmentPage.jsx`
- `frontend/src/pages/EquipmentDetailPage.jsx`
- `frontend/src/pages/TrainingPage.jsx`
- `frontend/src/pages/CertificationsPage.jsx`
- `frontend/src/components/training/TrainingDefinitionDialog.jsx`
- `frontend/src/components/training/AssignTrainingDialog.jsx`
- `frontend/src/components/training/AssignmentDetailDialog.jsx`
- `frontend/src/portal/employee/EmployeePortalApp.jsx`
- Employee, schedule, time clock, timesheet, payroll, task, calendar, time-off, communication, announcement, equipment, training, certification, and portal backend code.
- `evidence/EC8_evidence.md`
- `evidence/EC12_PHASE12A_COMPLETION_REPORT.md` through the applicable EC12 phase reports.

Historical verification evidence records a complete EC8 backend regression of 312 passing tests at EC8 closure, followed by focused browser verification and later passing EC12 CI for tasks, time off, calendar, communications, Employee Portal completion, and productivity templates. This report still rates the feature state from current code, not from completion labels alone.

## Final verdict

Team & Productivity is an **advanced MVP area with one standout safety feature and several highly credible operational systems**. It is not merely a set of employee forms. Time, pay, scheduling, tasks, training, certifications, communications, and portal access share real security, audit, and lifecycle controls.

The next work should focus on finishing the product experience around the code already present. A manager Time-Off page, consolidated navigation, correct permission-aware controls, timesheet/payroll exports, and nontechnical people/entity selectors would deliver more value than adding another major Team subsystem.

No AI work is necessary to make this area launch-ready. The unfinished work is ordinary product completion, usability, and integration.
