# EC12 Phase 12C Completion Report

**Date:** 2026-07-17  
**Scope:** EC12 Phase 12C - Employee Time-Off and Absence Workflow  
**Branch:** `CODEX-ec12-branch`

## Existing Systems Reused

- Existing EC8 Employee records, Employee Portal identity/token separation, Schedule/Shift system, notifications, activity/audit, permissions, and tenant isolation.
- Existing `/api/portal/employee` router for self-scoped Employee Portal access.
- Existing calendar projection boundary from Phase 12D for approved absence overlays.

## Implementation Summary

- Added canonical `TimeOffRequest` model and `time_off_requests` indexes.
- Added employee self-submit/list/detail/cancel/respond-to-clarification routes through Employee Portal.
- Added manager list/detail/approve/deny/request-clarification routes under `/api/time-off`.
- Preserved request history for create, clarification, clarification response, approval, denial, and cancellation.
- Approved absences project onto the shared calendar feed without creating shifts.
- Schedule conflicts are surfaced from existing shifts; managers resolve shift conflicts separately.
- Private reasons are excluded from broad calendar/feed responses.

## Security And Isolation

- Same-tenant Employee validation is enforced server-side.
- Employee Portal routes are self-scoped from the portal token and never accept a client employee id.
- Inactive employees are denied by the existing Employee Portal guard before request creation.
- Staff review routes require schedule permissions; portal tokens are rejected from staff routes.
- No payroll entries, time entries, shifts, messages, SMS, templates, EC13, or EC19 records are created.

## Validation

- Local compile passed: `python -m compileall backend/app backend/tests/test_ec12_phase12c_time_off.py backend/tests/test_ec12_phase12d_calendar_appointments.py`.
- Local targeted pytest collection passed for EC12 Phase 12A-12D files after installing the local test runner dependencies; full DB-backed local execution remains unavailable because no local MongoDB service exists.
- GitHub Actions run `29566855738` passed:
  - `backend-tests`
  - `frontend-tests`
  - `frontend-build`

## CI Fix

- Initial run `29566320649` failed in `backend-tests` because the Phase 12C test expected inactive Employee Portal time-off submission to reach the service-level inactive-employee check (`400`), but the existing Employee Portal guard correctly blocks inactive employees earlier with `403`.
- Fixed the targeted test expectation in commit `641c2c2413edebddc433f2bd5fc740f811db27d0`.

## Not Started

- Phase 12E and later EC12 phases remain not started.
- Messages, notes workspace, daily digest, community, support, templates, EC13, and EC19 remain not started.
- No SMS sending was added.

