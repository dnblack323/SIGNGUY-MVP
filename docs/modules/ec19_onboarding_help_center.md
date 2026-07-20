# EC19 Onboarding and Help Center

EC19 adds the canonical onboarding and help/documentation layer for internal SignGuy AI users.

## Delivered Runtime Surface

- Tenant onboarding dashboard at `/onboarding` and `/help/onboarding`.
- Help Center at `/help`, `/help/docs`, and `/help/whats-new`.
- Reusable contextual help component for module surfaces.
- Backend APIs under `/api/onboarding` and `/api/help`.

## Canonical Data Contracts

- `onboarding_program_definitions`: platform-managed, versioned onboarding definitions.
- `tenant_onboarding_instances`: one tenant-scoped onboarding instance per program.
- `onboarding_task_states`: per-tenant task status, skip, defer, block, and completion state.
- `onboarding_step_responses`: immutable-ish response records for setup actions and exercises.
- `onboarding_import_records`: historical invoice import intake metadata only.
- `onboarding_template_exercises`: placeholder/template exercises over the canonical template engine.
- `help_articles`: lifecycle-managed Help Center content.
- `contextual_help_definitions`: module/surface-specific guidance.
- `help_feedback`: tenant-scoped article usefulness feedback.
- `support_escalations`: tenant-scoped help escalation records.

## Boundaries

- EC2 settings remain authoritative for company profile and branding values.
- EC9 remains authoritative for pricing setup and pricing defaults.
- EC10/EC12 templates remain authoritative for reusable templates and placeholder validation.
- EC13 remains authoritative for setup-package purchase and failed-subscription state.
- EC16/EC17/EC18 remain authoritative for AI gateway, Studio AI, and Business Assistant behavior.
- EC19 does not add live providers, Stripe checkout, EC4 finance mutations, Webstore payout changes, or a duplicate assistant.

## Permissions

- `onboarding:read`: owner/admin/staff read access.
- `onboarding:write`: owner/admin setup mutation.
- `help:read`: owner/admin/staff Help Center access.
- `help:manage`: owner/admin permission catalog entry; platform help master mutation still requires explicit platform-admin status.
- `support:write`: support escalation creation.

Portal identities cannot access EC19 internal routes.

## Lifecycle Rules

- Onboarding task statuses: `not_started`, `in_progress`, `completed`, `skipped`, `deferred`, `blocked`.
- Required steps remain visible if skipped or deferred.
- Canonical writes happen only through approved owner/admin actions.
- Help article statuses: `draft`, `published`, `archived`.
- Draft/archived help articles are hidden from normal Help Center reads.
- Historical import analysis is provider-deferred and records `analysis_status="unavailable"` when analysis is requested.

## Acceptance Coverage

Targeted backend coverage is in `backend/tests/test_ec19_onboarding_help.py`.

Targeted frontend coverage is in `frontend/src/__tests__/ec19.onboarding-help.test.jsx`.
