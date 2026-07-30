# Webstores Stage 2 Setup and Owner Intake Evidence

Status: IMPLEMENTED FOR REVIEW

Branch: `feature/webstores-stage-2-setup`

## Scope Implemented

- Separate Webstore setup workflow state from Stage 1 lifecycle/status.
- Tenant-scoped Store Owner and Store Manager assignments.
- Primary Store Owner assignment with explicit confirmation and reason for primary-owner changes.
- Hashed 48-hour owner/manager invitations with one-time acceptance and replay prevention.
- Invitation resend supersedes pending tokens.
- Portal identity linking for accepted invitations without granting staff permissions.
- Tenant-scoped questionnaire templates, binding, draft save, submit, return-for-changes, immutable submitted snapshots, and staff review.
- Owner/staff setup-file upload, replacement versioning, removal, and private backend-proxied download.
- File validation for allowed extensions, maximum size, and basic content-type matching.
- Safe answer-application preview, deliberate apply, idempotent replay, and compensating reversal event.
- Computed setup progress for staff and owner portal views.
- Staff-safe and owner-safe response allowlists that hide storage keys, tenant internals, costs, margins, supplier data, staff-only notes, and platform-only data.

## Security Contracts

- Invitation raw tokens are never stored; only SHA-256 token hashes are persisted.
- Accepted, expired, revoked, and superseded invitations cannot be reused.
- Assignment-scoped portal identities can only list and open assigned Webstores.
- Store Manager assignments are scoped to one Webstore.
- Existing staff emails do not receive staff permissions through Webstore invitation acceptance.
- Setup files are stored through application-owned object storage and never exposed as direct public storage URLs.
- SVG inline preview is allowed only when basic sanitization marks it safe; AI/EPS/Office-style files remain download-only.
- Safe answer application rejects locked pricing, fee, payment, Stripe, and launch-readiness fields.
- Dry-run answer application does not persist changes.
- Routine setup progress reads do not create commerce records or alter checkout state.

## Deferred

- Real Stripe Checkout Sessions, webhooks, Connect, payouts, refunds, disputes, and donation transactions.
- Storefront branding editor and storefront redesign.
- Product catalog buildout.
- AI summaries, AI actions, and catalog AI.
- Launch Packet expansion.
- Stage 3 and later Webstore phases.
- EC4 invoice/payment changes and unrelated EC9 work.

## Verification

- Focused Stage 2 backend tests: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_webstores_stage2_setup.py -q` -> `5 passed, 6 warnings`.
- Existing Stage 1 backend regression: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_webstores_stage1_foundation.py -q` -> `9 passed, 6 warnings`.
- Combined Webstore backend regressions: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_webstores_stage2_setup.py backend/tests/test_webstores_stage1_foundation.py backend/tests/test_ec14_webstores.py -q` -> `16 passed, 6 warnings`.
- Portal/auth-adjacent backend regressions: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_ec6_portal_docs.py backend/tests/test_ec6_portal_payment.py backend/tests/test_ec8c_employee_portal.py -q` -> `29 passed, 6 warnings`.
- Focused Webstore frontend tests: `npm.cmd test -- --runTestsByPath src/__tests__/WebstoresStage1.test.jsx --watchAll=false` -> `1 suite passed, 4 tests passed`.
- Frontend production build: `npm.cmd run build` -> compiled successfully.
- Backend compile/import validation: `backend/.venv/Scripts/python.exe -m compileall -q backend/app backend/tests/test_webstores_stage2_setup.py` -> passed.
- `git diff --check` -> passed with CRLF conversion warnings only.
