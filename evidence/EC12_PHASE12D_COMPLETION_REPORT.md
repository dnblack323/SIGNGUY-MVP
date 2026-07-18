# EC12 Phase 12D Completion Report

**Date:** 2026-07-17  
**Scope:** EC12 Phase 12D - Shared Calendar, Appointments, and Shop Schedule  
**Branch:** `CODEX-ec12-branch`

## Existing Systems Reused

- Existing EC8 Schedule/Shift system for shift projections.
- Existing Phase 12A/12B Task records for due-date projections.
- Existing Phase 12C approved absence records for absence overlays.
- Existing EC11 production stage instances for production milestone projections.
- Existing Employees, Customers, Orders, Work Orders, notifications, audit/activity, permissions, and tenant isolation.

## Implementation Summary

- Added canonical stored `CalendarEvent` appointment model and `calendar_events` indexes.
- Added staff `/api/calendar` routes for feed, conflict check, create, get, update, reschedule, cancel, archive, and restore.
- Added one normalized calendar feed combining stored appointments, shifts, approved absences, task due dates, and production stage due dates.
- Activated `/shop-schedule` with day, week, month, and agenda/list views, employee/event-type filters, search, appointment creation, conflict warning/override, and safe display metadata.
- Added Employee Portal self-scoped calendar overlays on My Schedule.

## Conflict Behavior

- Conflict checks cover assigned employee appointment overlap, shift overlap, approved absence overlap, same-location overlap, and same-customer overlap where linked.
- Manager override requires a reason and is audited.
- Conflict handling does not mutate unrelated records.

## Safety Boundaries

- Stored appointments validate same-tenant linked Customer, Order, Work Order, Production Stage, Employee, and User records.
- Calendar feed items use safe allow-list projections and do not expose payroll, pay rates, private absence reasons, pricing, profit, internal notes, or raw file paths.
- Shift, absence, task, and production milestone projections are not copied into duplicate permanent calendar event rows.
- No Google/Outlook sync, SMS sending, messages, daily digest, community, templates, EC13, or EC19 work was added.

## Validation

- Local compile passed.
- Local frontend tests passed: `yarn.cmd test --watchAll=false` -> 7 suites, 29 tests.
- Local frontend production build passed: `yarn.cmd build`.
- GitHub Actions run `29566855738` passed:
  - `backend-tests`
  - `frontend-tests`
  - `frontend-build`

## Not Started

- Phase 12E and later EC12 phases remain not started.
- No payroll mutation occurred.
- No SMS sending was added.

