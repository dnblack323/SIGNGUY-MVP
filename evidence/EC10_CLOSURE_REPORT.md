# EC10 Closure Report

**Date:** 2026-07-16. **Scope:** EC10 final validation and closure after Phases 10A through 10H.

## Closed Scope

EC10 - Order Intake, Visual Markup, Customer Decision Room, and Templates is now **COMPLETE / CLOSED**.

Completed phases:

- Phase 10A - Intake architecture and canonical data contracts.
- Phase 10B - Quick and Detailed Internal Intake.
- Phase 10C - Asset Upload and Visual Markup.
- Phase 10D - Customer Decision Room internal authoring.
- Phase 10E - Customer-safe Decision Room experience, closed through 10E-5.
- Phase 10F - Staff-controlled decision-to-Quote/Order application.
- Phase 10G - EC10-scoped reusable templates.
- Phase 10H - Final EC10 validation and closure.

## Validation

- Backend compile passed for `backend\app` and the new targeted EC10F/EC10G test files.
- Existing frontend tests passed: 7 suites / 29 tests.
- Frontend production build passed.
- GitHub Actions is the authoritative backend pytest environment for this repo because local Python runtimes lack `pytest` and local MongoDB-backed backend tests are not available.

## Security and Scope Confirmations

- Customer Decision Room access remains tenant-safe.
- Customer/public views remain frozen published-version views.
- Customer-safe filtering remains in place for internal notes, raw storage paths, costs, profit, margins, staff ids, pricing internals, and audit internals.
- Customer media access remains limited to media frozen into published versions.
- Customer actions remain append-only and idempotent.
- Staff apply is the only Decision Room path that mutates Quote Line Items or Order Items.
- Applied decisions cannot be superseded historical selections.
- Staff apply creates immutable pricing snapshot records and does not silently recalculate frozen Decision Room pricing from live defaults.
- Templates copy values at apply time and do not create live mutable references.

## Known Gaps Carried Forward

- EC11 Production Timeline, Workflow Configuration, Stage Tracking, and Kiosk is not started.
- EC12 and later checkpoints are not started.
- PDF-page-anchored customer overlays remain backend-valid but do not yet have a dedicated click-to-place PDF UI.
- No customer-facing push notification channel for staff Decision Room responses was added.
- Quote/Order/Order Item templates, Proof templates, production workflow templates, appointment templates, and email/SMS templates are deferred to their owning future scopes.

## Final Status

- EC10: **COMPLETE / CLOSED**
- EC11: **NOT STARTED**
- EC12-EC22: **NOT STARTED** except EC9 already closed before EC10.
