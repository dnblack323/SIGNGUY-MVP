# Team & Productivity — Work Outline

This section owns people, their work, schedules, time, pay workflow, qualifications, communication, and employee access. The existing Team & Productivity feature audit is the starting record.

## 1. Confirm what belongs in Team & Productivity

- Keep Employees, Tasks, Team Schedule, Time Clock, Timesheets, Payroll, Messages, Announcements, Training, Certifications, Equipment, and the Employee Portal together.
- Keep operational payroll here because it depends on employee time, advances, adjustments, payments, and carryover.
- Send payroll cost summaries to Business & Finance without moving the employee payroll workflow there.
- Keep production records in Shop Operations while allowing tasks, qualifications, employees, and schedules to connect to them.
- Keep customer communications with customer and Order records; use Team communications for internal work.

## 2. Simplify the module navigation

- Review the current long row of Team & Productivity modules.
- Group related modules where appropriate, such as Training, Certifications, and Equipment.
- Consider internal tabs for Time & Attendance, Payroll, Communications, and Team Management so the top row is not overwhelming.
- Keep important employee self-service destinations easy to reach.
- Make sure Team Schedule is not confused with the all-shop operational schedule.

## 3. Decide internal tabs and ribbons

- Define tabs inside Employees, Tasks, Schedule, Time & Attendance, Payroll, Communications, and Training & Equipment.
- Decide which actions belong in ribbons: Add Employee, Publish Schedule, Clock In, Add Time Entry, Approve Timesheet, Record Advance, Record Payment, Assign Task, Send Announcement, and similar actions.
- Remove duplicate actions and misplaced navigation buttons.
- Show employee self-service actions separately from manager-only actions.

## 4. Update the complete feature audit

- Re-audit every Team & Productivity feature against the newest code.
- Include employee records, permissions, availability, shifts, time off, tasks, Kanban, time entries, timesheets, payroll, advances, payments, carryover, messages, announcements, training, equipment, certifications, and portal access.
- Rate what is truly usable and identify backend-only or disconnected pieces.
- Mark any AI assistance as optional or planned; core employee and payroll work must function without AI.

## 5. Create and correct the Team & Productivity gap list

- Number every real missing or incomplete workflow.
- Separate placement problems, workflow gaps, permission/privacy issues, payroll correctness risks, confusing interface problems, and future features.
- Recheck older findings so completed work is not planned again.
- Group remaining work into employee foundation, scheduling, tasks, timekeeping, payroll, communication, training/equipment, and portal batches.

## 6. Verify gaps against the code

- Inspect pages, APIs, models, services, permissions, tenant filters, history, and tests.
- Confirm employee self-service and manager workflows separately.
- Check whether schedule, time, task, and pay calculations use the same employee records.
- Require evidence before marking payroll or timekeeping work complete.

## 7. Complete the employee foundation

- Employee profiles, roles, departments, employment status, manager relationships, availability, and contact information
- Invitations, account linking, portal access, deactivation, and offboarding
- Permission assignment and restricted employee information
- Employee history and linked schedule, task, time, training, equipment, and payroll records

## 8. Complete tasks and productivity workflows

- Task lists, Kanban, priorities, due dates, recurring work, comments, attachments, and assignments
- Links from tasks to Customers, Orders, Order Items, Work Orders, installs, and internal projects
- Saved views and filters for personal work, department work, overdue work, and manager review
- Clear difference between a Task and a Production stage

## 9. Complete scheduling and time workflows

- Employee shifts, availability, time off, published schedules, and schedule changes
- Team Schedule connection to the all-shop schedule without duplicating events
- Clock in/out, breaks, manual entries, corrections, approvals, and audit history
- Timesheet periods using the approved Saturday-through-Friday work week
- Manager correction rules and employee visibility

## 10. Complete payroll tracking

- Hourly calculations using the approved rates and work week
- Advances, adjustments, payments, carryover, and manual corrections
- Clear weekly payroll status and readable My Pay views
- Restricted manager/admin access and employee self-service access to only their own pay
- Payroll cost summaries for Business & Finance
- Explicit boundary between SignGuy AI's pay tracking and any future tax filing or direct-deposit provider

## 11. Complete communication, training, and equipment

- Internal messages, conversations, announcements, read status, and attachments
- Management visibility without mixing internal messages with customer communication
- Training records, certifications, expiration dates, qualification rules, and reminders
- Equipment assignments, maintenance, availability, and employee qualification checks
- Work Order assignment safeguards when a required certification or equipment qualification is missing

## 12. Complete the Employee Portal

- Employee sign-in and tenant isolation
- My Schedule, My Tasks, Time Clock, My Timesheet, My Pay, Announcements, Messages, and Training
- Mobile-friendly use for employees away from a desk
- Clear manager versus employee capabilities
- Safe account recovery and deactivated-employee handling

## 13. Fix permissions, privacy, and data integrity

- Protect personal information, payroll details, time corrections, and private manager notes.
- Prevent one employee from accessing another employee's restricted records.
- Require reasons and audit history for sensitive edits.
- Test tenant separation across every employee, task, schedule, time, pay, message, training, and equipment endpoint.

## 14. Clean up, test, update the register, and review

- Simplify confusing layouts and oversized pages.
- Refactor large employee, scheduling, task, payroll, and communication files.
- Test full employee, scheduling, timekeeping, payroll, portal, and permissions workflows.
- Run backend tests, frontend tests, and the frontend build.
- Update the gap and issue registers with evidence.
- Perform a final Team & Productivity code review.
