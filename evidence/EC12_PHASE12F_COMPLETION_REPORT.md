# EC12 Phase 12F Completion Report

**Date:** 2026-07-17  
**Scope:** EC12 Phase 12F - Employee Account Experience Completion  
**Branch:** `CODEX-ec12-branch`

## Existing Systems Reused

- Existing Employee Portal shell, authentication, magic-link/password handoff, token separation, and self-scoped route pattern.
- Existing Employee records, profile fields, availability blocks, files collection, schedule, time-off, tasks, announcements, training, certifications, payroll self-view, Time Clock, and authorized production work.
- Existing Phase 12E communication service for employee-visible messages, preferences, quiet hours, and digest.

## Implementation Summary

- Added Employee Portal self-scoped messages routes for thread list, thread detail, replies, and read state.
- Added Employee Portal self-scoped communication preferences and quiet-hours routes.
- Added Employee Portal digest preview/generation routes.
- Extended Employee Portal profile update to support preferred name, contact email, phone, profile image file reference, availability notes, structured availability blocks, timezone, and emergency contact fields.
- Updated Employee Portal UI with Messages navigation/page and Profile & Preferences controls.
- Preserved existing Employee Portal areas: Home, Time Clock, My Schedule, My Time Off, My Tasks, Messages, Announcements, Production, Training, Certifications, My Pay, and Profile.

## Safety Boundaries

- Employee Portal routes resolve the acting employee from the portal token; no client-supplied employee id is trusted.
- Protected employment fields, pay rate, status, role/permissions, linked staff user, and activation state cannot be changed from the Employee Portal.
- Profile images must reference an existing tenant file; inline base64 image data is rejected.
- Availability updates do not create shifts, time-off requests, payroll entries, or schedule mutations.
- Password/account security remains delegated to existing Employee Portal authentication; no second login or password store was added.
- Employee messages show only employee-visible threads where the employee is a participant.
- Customer portal tokens are denied from Employee Portal routes; portal tokens are denied from staff communication routes.
- No SMS sending, payroll mutation, community, Founders area, support routing, Template Vault, EC13, EC19, or Phase 12G work was added.

## Validation

- Local compile passed: `python -m compileall backend/app backend/tests/test_ec12_phase12e_communications.py backend/tests/test_ec12_phase12f_employee_account_experience.py`.
- Targeted pytest collection passed for the new Phase 12E/12F tests: 2 tests collected.
- Local DB-backed targeted pytest passed after starting a throwaway local MongoDB instance:
  `python -m pytest backend/tests/test_ec12_phase12e_communications.py backend/tests/test_ec12_phase12f_employee_account_experience.py -q` -> 2 passed.
- Local directly affected EC12 stack pytest passed:
  `python -m pytest backend/tests/test_ec12_phase12a_tasks.py backend/tests/test_ec12_phase12b_tasks_experience.py backend/tests/test_ec12_phase12c_time_off.py backend/tests/test_ec12_phase12d_calendar_appointments.py backend/tests/test_ec12_phase12e_communications.py backend/tests/test_ec12_phase12f_employee_account_experience.py -q` -> 10 passed.
- Frontend tests passed: `yarn.cmd test --watchAll=false` -> 7 suites, 29 tests.
- Frontend production build passed: `yarn.cmd build`.
- GitHub Actions run `29573599455` passed: `backend-tests`, `frontend-tests`, and `frontend-build`.
- CI failure on run `29572535798` was caused by Mongo rejecting `communication_preferences` upserts where `$setOnInsert` default fields overlapped with `$set` update fields. Fixed by removing all update keys from the insert-default document before upsert.

## Targeted Test File

- `backend/tests/test_ec12_phase12f_employee_account_experience.py`

## Known Gaps

- No new password recovery UI was added; existing Employee Portal account-security handoffs remain authoritative.
- No shift-approval workflow for availability was added; manager schedule remains authoritative.
- No community/support/founders/template commercial scope was started.

## Status

- Phase 12F COMPLETE.
- Phase 12G and later NOT STARTED.
- EC12 remains IN PROGRESS.
