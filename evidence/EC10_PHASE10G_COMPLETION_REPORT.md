# EC10 Phase 10G Completion Report

**Date:** 2026-07-16. **Scope:** EC10-scoped reusable templates only.

## Delivered

- Added `TemplateDefinition` model and `template_definitions` indexes.
- Added staff permissions: `template:read`, `template:write`.
- Added `/api/templates` CRUD/list/get/archive/restore/apply router.
- Template types are intentionally limited to EC10 scope:
  - `intake`
  - `questionnaire`
  - `decision_options`
- Applying a template copies the template body at apply time:
  - `intake` templates create a new `IntakeSubmission` with `source_type = saved_template`.
  - `questionnaire` templates copy prompt config to an existing `CustomerIntake`.
  - `decision_options` templates copy option definitions into an existing Decision Room.
- Later edits to a template do not mutate already-created intake records or Decision Room options.
- Archived templates cannot be applied.

## Frontend

- Added compact internal `/templates` page.
- Added Shop Operations navigation entry.
- Page supports template type selection, JSON body editing, create, apply, archive, and restore.

## Tests and Validation

- Added targeted backend tests: `backend/tests/test_ec10_phase10g_templates.py`.
- Local Python compile: `python -m compileall backend\app backend\tests\test_ec10_phase10f_decision_apply.py backend\tests\test_ec10_phase10g_templates.py` passed.
- Local targeted pytest was not runnable because the available local Python runtimes do not have `pytest`; GitHub Actions backend CI is the authoritative backend execution environment with MongoDB.
- Frontend production build passed.
- Existing frontend tests passed: 7 suites / 29 tests.

## Explicit Deferrals

- Quote/Order/Order Item templates are not implemented in this phase.
- Proof/approval templates are not implemented in this phase.
- Production workflow templates remain EC11 scope.
- Appointment templates remain EC12 scope.
- Email/SMS templates remain deferred communications/settings scope.

## Boundaries

- No EC11, EC12, EC14, EC15, AI, commercial billing, Webstores, or Wrap Lab work was started.
