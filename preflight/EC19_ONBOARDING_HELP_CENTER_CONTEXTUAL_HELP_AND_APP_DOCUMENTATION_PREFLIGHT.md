# EC19 Onboarding, Help Center, Contextual Help, and App Documentation Preflight

**Status:** PREFLIGHT COMPLETE / IMPLEMENTATION AUTHORIZED  
**Branch:** `CODEX-ec19-branch`  
**Date:** 2026-07-20  
**Controlling specification:** `specs_pack/extracted/EC19_Onboarding_Help_and_App_Documentation.docx`  
**Owner authorization:** 2026-07-20 prompt authorizing planning, implementation, testing, documentation, commit, push, CI wait, and closure for EC19 only.

## Authority

The EC19 spec labels itself as planning-only, but the latest owner prompt explicitly authorizes EC19 planning and implementation. That prompt is authoritative for this branch.

H1 is closed for EC19 only. H7 remains active but does not block EC19 education, onboarding, contextual guidance, or safe explanation of EC16-EC18 boundaries. EC20, EC21, and EC22 are not authorized.

## Scope

EC19 implements app onboarding and help surfaces without duplicating existing systems:

- Versioned tenant onboarding program definitions.
- Tenant onboarding state, step responses, skip/defer behavior, progress, and dashboard.
- Owner/admin-only setup mutation through existing canonical services.
- Platform-admin bootstrap for onboarding definitions, help articles, contextual help entries, and starter documentation records.
- Pricing Setup Assistant over EC9 grouped pricing quiz and pricing settings contracts.
- Historical invoice import intake records only, routed through EC17/EC16 AI/provider boundaries with no live provider call.
- Placeholder registry and sample template exercise over EC10/EC12 template contracts.
- Setup package handoff/readiness over EC13 setup-package purchase records, with no checkout creation.
- Searchable Help Center, role/module guides, lifecycle-managed help articles, contextual help registry, feedback, support escalation, failed-subscription guidance, and release notes.
- Frontend onboarding dashboard, help center, contextual help component, and navigation enablement.

## Out of Scope

- No EC20 platform admin console, platform analytics, or platform dunning operations.
- No EC21 marketing website, public pricing, founder signup, or public commercial offer pages.
- No EC22 final release-hardening work.
- No Stripe API calls, checkout sessions, billing portal, subscriptions, or webhooks added by EC19.
- No real OpenAI, SMS, email, Meta, OCR, or external provider calls.
- No AI-credit pricing, provider-cost pricing, final model-cost decisions, BYOK, MCP, or live provider activation.
- No EC4 invoice/payment mutations.
- No Webstore payout changes.
- No duplicate Business Assistant.

## Existing Contracts Reused

- EC2 settings: `backend/app/services/settings.py` and `/api/settings`.
- EC9 pricing setup quiz: `backend/app/services/pricing_quiz.py` and `/api/pricing/quiz`.
- EC10/EC12 reusable templates: `backend/app/services/template_service.py` and `/api/templates`.
- EC12 support/community: existing support request records remain authoritative for support routing.
- EC13 setup-package and billing state: `backend/app/services/tenant_billing.py` and `/api/billing/state`.
- EC16/EC17 AI boundaries: historical import analysis remains intake/registry only unless EC16/EC17 later provides an authorized provider-backed execution path.
- EC18 Business Assistant: EC19 may link to and explain it, but must not create a duplicate assistant.

## Implementation Plan

### EC19A - Onboarding Engine and Core Setup

- Add canonical onboarding models/service/router.
- Add onboarding permissions.
- Add tenant-scoped onboarding program definitions, tenant instances, task states, step responses, import records, template exercises, contextual test records, and audit events.
- Add platform-admin bootstrap endpoint.
- Add owner/admin onboarding dashboard, progress, status, skip/defer/resume, dependencies, and setup readiness.
- Apply approved company-profile setup values only through EC2 settings.

### EC19B - Setup Assistants and Handoffs

- Add Pricing Setup Assistant endpoints that call EC9 quiz contracts and do not write pricing unless the owner/admin explicitly approves.
- Add historical invoice import intake metadata and analysis-request records with `pending_provider`/`unavailable` states and no external provider execution.
- Add placeholder registry, placeholder preview, missing-value warnings, and sample template exercise over EC10/EC12 validation/preview.
- Add setup-package handoff state over EC13 setup-package purchases without creating checkout sessions or changing prices.

### EC19C - Help Center, Contextual Help, and Documentation UX

- Add lifecycle-managed help articles and role/module guides.
- Add contextual help registry keyed by module/surface/field.
- Add search, article read, role guide, module guide, release note, privacy/data deletion, and failed-subscription guidance endpoints.
- Add feedback and support escalation records.
- Add frontend Help Center and reusable contextual help component.

## Permission Model

- `onboarding:read`: owner/admin/staff can view onboarding progress and guides.
- `onboarding:write`: owner/admin can change onboarding setup state and apply approved setup values.
- `help:read`: owner/admin/staff can read help and contextual guidance.
- `help:manage`: owner/admin for tenant help feedback management; platform admin required for platform master help-article mutations.
- Portal identities are not authorized for EC19 internal onboarding/help routes.
- Cross-tenant reads/writes are forbidden unless the actor is platform admin and the endpoint explicitly supports platform scope.

## Lifecycle Contracts

- Program definitions are versioned and platform-managed.
- Tenant onboarding instances are tenant-scoped and never shared across tenants.
- Step status values: `not_started`, `in_progress`, `completed`, `skipped`, `deferred`, `blocked`.
- Required/recommended/optional levels determine progress messaging; skipped required steps remain visible.
- Owner/admin approval is required before onboarding writes canonical settings or pricing setup changes.
- Help article status values: `draft`, `published`, `archived`.
- Published help records are readable; archived records are platform/admin-visible only.
- Historical import records are intake/evidence records only in EC19.

## Required Indexes

- `onboarding_program_definitions`: `id`, `program_key/version`, `status/effective_at`.
- `tenant_onboarding_instances`: `id`, unique active `tenant_id/program_key`, `tenant_id/status/updated_at`.
- `onboarding_task_states`: `id`, unique `tenant_id/program_key/task_key`, `tenant_id/status/updated_at`.
- `onboarding_step_responses`: `id`, `tenant_id/task_key/created_at`, idempotency key.
- `onboarding_import_records`: `id`, `tenant_id/import_type/status/created_at`.
- `onboarding_template_exercises`: `id`, `tenant_id/template_id/status/updated_at`.
- `contextual_help_definitions`: `id`, unique `surface_key/help_key`, `module/status`.
- `help_articles`: `id`, unique `slug`, `status/category/updated_at`, text search over title/body/search keywords.
- `help_feedback`: `id`, `tenant_id/article_id/created_at`, idempotency key.
- `support_escalations`: `id`, `tenant_id/status/created_at`, idempotency key.

## Acceptance Tests

- Platform bootstrap is idempotent and platform-admin-only.
- Owner/admin can view dashboard and mutate onboarding; staff can read but cannot write setup state.
- Portal/customer identities cannot access EC19 internal routes.
- Cross-tenant onboarding and help feedback are isolated.
- Company profile setup writes only through EC2 settings and records audit.
- Pricing Setup Assistant uses EC9 quiz contracts and does not apply changes without explicit approval.
- Historical invoice import records do not call a real provider and do not mutate invoices/payments.
- Placeholder registry rejects unknown placeholders and reports missing values.
- Template exercise reuses template validation/preview and does not consume AI credits.
- Setup package handoff reads EC13 setup purchases and does not create checkout sessions.
- Help article publish/archive lifecycle gates visibility.
- Contextual help returns module-specific entries.
- Failed-subscription guidance reads EC13 billing state and produces guidance only.

## Expected Files

Backend:

- `backend/app/models/onboarding.py`
- `backend/app/services/onboarding.py`
- `backend/app/routers/onboarding.py`
- `backend/app/services/help_center.py`
- `backend/app/routers/help_center.py`
- `backend/app/core/permissions.py`
- `backend/app/core/db.py`
- `backend/server.py`
- `backend/tests/test_ec19_onboarding_help.py`

Frontend:

- `frontend/src/lib/onboarding.js`
- `frontend/src/pages/OnboardingPage.jsx`
- `frontend/src/pages/HelpCenterPage.jsx`
- `frontend/src/components/help/ContextualHelp.jsx`
- `frontend/src/App.js`
- `frontend/src/lib/navigation.js`
- `frontend/src/__tests__/ec19.onboarding-help.test.js`

Documentation/tracking:

- `docs/modules/ec19_onboarding_help_center.md`
- `docs/modules/ec19_placeholder_registry.md`
- `docs/modules/ec19_setup_package_handoff.md`
- `evidence/EC19_IMPLEMENTATION_COMPLETION_REPORT.md`
- `memory/MASTER_CHECKPOINT_CHECKLIST.md`
- `memory/checkpoint_reference_table.md`
- `memory/progress_register.md`
- `memory/SIGNGUY_FOLLOW_UP_REQUIREMENTS_REGISTER.md`

## Preflight Result

Preflight is complete and EC19 implementation may begin after this documentation/tracking commit is pushed. No implementation occurred in this preflight commit.
