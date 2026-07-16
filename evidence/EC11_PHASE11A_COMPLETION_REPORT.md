# EC11 Phase 11A Completion Report

**Date:** 2026-07-16. **Scope:** Production Workflow Definitions and Canonical Stage Contracts only.

## Summary

Phase 11A adds the tenant-scoped production workflow foundation for later EC11 phases. It defines reusable workflow definitions, ordered stage-definition contracts, canonical future live-stage statuses, starter workflows, category/default resolution, staff configuration endpoints, and a compact internal configuration UI.

No live Work Order stages are generated in this phase.

## Existing systems reused

- Existing tenant, user, role, and permission architecture.
- Existing Work Order, Order, and Order Item records are referenced only by future contract; none are mutated.
- Existing audit service records workflow/stage configuration changes.
- Existing navigation, settings-style page, and API client conventions are reused.
- Existing Mongo index and UUID conventions are reused.

## Workflow model

New `ProductionWorkflowDefinition` records are stored in `production_workflows` and include tenant id, name, workflow key, scope type, category assignments, active/archive state, version, starter/source references, tenant-default flag, and ordered embedded stage definitions.

Starter workflows are tenant-scoped, idempotently seeded, marked with `scope_type = system_starter`, and protected from direct content edits. Users duplicate a starter before editing its contents.

## Stage-definition contract

Each reusable stage definition supports stable key, display name, sequence, active flag, required/optional, skip rules, default role, estimated duration and due-date-offset placeholders, customer/employee visibility, previous-stage requirement, proof/approval gate reference, equipment/certification references, future checklist references, and color/icon display metadata.

No detailed timer-session fields and no payroll fields were added.

## Canonical statuses

Phase 11A centralizes the future live-stage statuses:

- `not_started`
- `in_progress`
- `waiting`
- `blocked`
- `completed`
- `skipped`

Reusable workflow definitions do not carry live stage status.

## Resolution behavior

The resolver contract is deterministic:

1. explicit Order Item workflow instance reference, when provided later
2. tenant-custom category-assigned workflow
3. tenant-scoped starter category workflow
4. tenant default workflow
5. manual/no-workflow fallback

Tenant-custom category assignments supersede starter category templates during resolution. This preserves starter templates as fallbacks while allowing a duplicated tenant workflow to take over a category.

Phase 11A exposes this as preview/contract behavior only and does not modify Order Items.

## Backend CI follow-up

Initial GitHub Actions backend run `29527594762` failed one assertion in `tests/test_ec11_phase11a_production_workflows.py`: after assigning `banners` to a duplicated workflow, category resolution returned another active workflow instead of the tenant-assigned duplicate.

The fix keeps starter workflows available but changes category resolution to prefer non-starter tenant workflows before falling back to system starter workflows.

## Original resolver order

The original resolver intent remains:

1. explicit Order Item workflow instance reference, when provided later
2. category-assigned workflow
3. tenant default workflow
4. manual/no-workflow fallback

## Starter workflows

The small starter set includes General Sign Production, Banner Production, Rigid Sign / Panel Production, Cut Vinyl / Lettering, Digital Print and Lamination, Apparel Production, Vehicle Graphics / Basic Wrap Production, Installation-Only Work, and Custom / Manual Workflow.

## Endpoints and UI

Staff endpoints were added under `/api/production-workflows` for list/get/create/update/duplicate/archive/restore, set tenant default, assign categories, add/update/reorder/archive stages, status contract, and resolution preview.

Frontend route `/settings/production-workflows` was added with workflow list, starter/default/category labels, create/duplicate/archive/restore, focused editor, ordered stage editor, category assignment, and resolution preview.

## Permissions and isolation

New staff permissions:

- `production_workflow:read`
- `production_workflow:manage`

Staff receive read-only access. Owner/admin receive manage through the existing owner/admin all-permissions model. Employee Portal and Customer Portal tokens cannot access staff workflow configuration routes. All reads/writes are tenant-scoped.

## Audit events

Audit events are emitted for workflow created, updated, duplicated, archived, restored, tenant default changed, category assignment changed, stage added, stage updated, stage reordered, and stage archived.

## Validation

- Backend compile passed for `backend/app` and `backend/tests/test_ec11_phase11a_production_workflows.py`.
- Local EC11 test collection passed for `tests/test_ec11_phase11a_production_workflows.py`.
- Local targeted pytest execution could not run end-to-end because this Windows environment has no MongoDB service or Docker.
- GitHub Actions is the authoritative backend pytest environment for the targeted test file and full backend suite.
- Frontend production build passed: `CI=true GENERATE_SOURCEMAP=false REACT_APP_BACKEND_URL=https://placeholder.invalid yarn.cmd build`.

## Confirmed boundaries

- No live Work Order stages were generated.
- No Work Order stage-action endpoints were added.
- No Employee Portal production page was added.
- No kiosk was added.
- No detailed production timer sessions/events were added.
- No payroll time-clock integration was added.
- No bottleneck analytics, advanced reports, rework analytics, throughput analytics, or pricing-feedback code was added.
- Phase 11B and later phases were not started.
- Phases 11G and 11H remain not authorized.
- EC12 remains not started.
