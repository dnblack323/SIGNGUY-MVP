# EC12 Phase 12E Completion Report

**Date:** 2026-07-17  
**Scope:** EC12 Phase 12E - Messages, Notes, Announcements, and Daily Digest  
**Branch:** `CODEX-ec12-branch`

## Existing Systems Reused

- Existing tenants, staff users, Employee records, Employee Portal identities, permissions, audit/activity, and notifications.
- Existing Phase 12A/12B Tasks, Phase 12D Calendar Events, EC8 Announcements, and EC11 production-stage records as linked-record sources.
- Existing Employee Portal authentication/token separation; customer portal tokens remain rejected from employee/staff communication routes.

## Implementation Summary

- Added canonical shared `MessageThread`, `ThreadMessage`, `MessageReadState`, `InternalNote`, `CommunicationPreference`, and `DailyDigest` contracts.
- Added one shared `communication_service.py` with thread-type constants, same-tenant active participant checks, linked-record validation, participant access enforcement, per-identity read state, note visibility filtering, preferences, quiet hours, and derived digest generation.
- Added staff `/api/communications` endpoints for threads, messages, participants, read state, notes, preferences, badge count, and digest preview/generation/delivery marking.
- Enabled compact staff `/team/messages` workspace with Inbox, Notes, Announcements integration note, Daily Digest, and Preferences tabs.
- Reused the existing Announcements model/router and updated permission names to `announcement:*`.

## Safety Boundaries

- No customer participation in threads was added.
- Employee-visible threads require explicit `employee_visible` visibility and participant membership.
- Linked-record discussions validate linked record ownership but do not mutate Customers, Orders, Order Items, Work Orders, production stages, tasks, or calendar events.
- Notes are stored in one shared collection; no module-local note tables were added.
- Daily digest is derived from source systems and does not copy source records into a parallel operational store.
- Digest excludes payroll, pricing, profit, margin, and private notes.
- No SMS sending, marketing automation, community, Founders area, support routing, Template Vault, EC13, EC19, or Phase 12G work was added.

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

- `backend/tests/test_ec12_phase12e_communications.py`

## Known Gaps

- No email delivery worker was added; digest in-app preview/generation works and email delivery remains bounded to existing authorized email architecture.
- No advanced AI-generated digest content was added.
- No community/support/founders/template commercial scope was started.

## Status

- Phase 12E COMPLETE.
- Phase 12F completed in the paired report.
- Phase 12G and later NOT STARTED.
- EC12 remains IN PROGRESS.
