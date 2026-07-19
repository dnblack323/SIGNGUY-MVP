# EC16 Shared AI Gateway, Usage, Cost, Credits, and Governance Preflight and Implementation Plan

**Status:** PREFLIGHT COMPLETE - READY TO BUILD
**Date:** 2026-07-19
**Branch:** `CODEX-ec16-branch`
**Starting HEAD:** `6b19fc0d07931cfffaf67daa65d7f35d8de6fa42`
**Upstream:** `origin/CODEX-ec16-branch`
**Remote parity:** `origin/main` and `origin/CODEX-ec16-branch` both at `6b19fc0d07931cfffaf67daa65d7f35d8de6fa42`
**EC15 final closure ancestor:** `e623fd48922f9021792d9f98845be0a4478493d0` present in history
**Working tree at preflight start:** clean

## 1. Authority and Starting Point

- Current owner prompt authorizes the entire next incomplete checkpoint after EC15 and explicitly directs continuing through all planned subphases until the checkpoint is complete.
- The next authoritative incomplete checkpoint is **EC16 - Shared AI Gateway, Usage, Cost, Credits, and Governance**.
- Controlling specification: `specs_pack/extracted/EC16_Shared_AI_Gateway_Cost_Credits_and_Governance.docx`.
- Authority order: `memory/documentation_authority_register.md`.
- Checkpoint tracking: `memory/MASTER_CHECKPOINT_CHECKLIST.md`, `memory/checkpoint_reference_table.md`, `memory/progress_register.md`, and `memory/owner_specification_hold_register.md`.
- Existing code is implementation evidence only and must not override the EC16 specification or owner decisions.

H4 is treated as lifted for **EC16 only** by the current owner prompt. H4 remains active for EC17 and EC18. H7 remains active and limits live commercial/provider activation until the measured provider-cost audit is complete.

## 2. Business Purpose

EC16 creates the one shared, metered, tenant-safe AI infrastructure layer that every later AI feature must use. It prevents EC17 Studio AI Tools, EC18 Assistant/Voice, pricing advisory, Webstores, Wrap Lab, and future modules from calling providers directly or spending credits without centralized telemetry, governance, cost tracking, and audit.

## 3. Exact Included Scope

- Canonical AI gateway contracts and local execution boundary.
- Provider-agnostic model routing records.
- Capability registry and versioned prompt registry.
- Context packet contracts and action execution contracts.
- AI usage ledger.
- Provider cost ledger.
- Customer-facing AI credit accounts and append-only credit ledger.
- Idempotent credit reservation, commit, refund, release, and adjustment contracts.
- Governance policies for rate limits, spend limits, credit limits, low-credit warnings, zero-credit blocking, and budget alerts.
- Tenant-facing credit balance/history endpoints.
- Platform-admin cost and usage visibility endpoints.
- Backend permission, platform-admin, portal-token, and tenant-isolation enforcement.
- Audit/activity events for mutable governance, credit, and ledger state.
- Required indexes and uniqueness constraints.
- Targeted backend tests.
- Minimal frontend surfaces for tenant credits/usage and platform governance/cost dashboards if practical in the checkpoint.
- Documentation and completion evidence.

## 4. Explicit Exclusions and Non-Goals

- No EC17 Studio AI tool catalog, generated-asset workflows, final per-tool credit costs, prompt-library user experience, or AI activity workspace.
- No EC18 paid Business Assistant, actions, intelligence, realtime voice, call handling, or assistant UI.
- No EC19 onboarding/help/documentation work.
- No direct provider calls unless a local fake/no-op adapter is used only for tests and gateway contract verification.
- No external credentials, no provider API keys in frontend, logs, or test fixtures.
- No silent provider fallback.
- No live commercial activation of AI top-up pricing, included credit amounts, model assignments, or per-tool prices while H7 remains active.
- No Stripe API calls, Checkout Sessions, Billing Portal Sessions, subscriptions, setup purchases, or Stripe webhooks.
- No EC4 customer invoice/payment mutations.
- No EC13 catalog price changes or entitlement projection changes.
- No EC14 Webstore payout, buyer order, or storefront commerce changes.
- No EC15 Wrap Lab workflow mutation.
- No AI-generated image/design/business-output implementation beyond gateway contract test fixtures.
- No floating-point money fields. Monetary values use integer cents; provider sub-cent estimates use integer micros with clear field names.

## 5. Dependencies and Reuse

- EC1 permission model and portal-token separation through `backend/app/core/permissions.py` and `backend/app/deps.py`.
- EC2 audit, activity, feature entitlement, settings, notifications, integration-status, and tenant isolation patterns.
- EC9 pricing advisory remains provider-neutral scaffolding; EC16 may add gateway linkage contracts but must not make advisory auto-apply pricing or mutate Quote/Order records.
- EC13 commercial billing remains the owner of plans, included-credit commercial promises, credit-pack prices, subscription status, and EC2 entitlement projection.
- EC14 Webstores local AI usage contract records remain separate until a future integration bridges them through EC16.
- EC15 Wrap Lab AI references remain local warnings/contracts only until a future AI phase uses EC16.

## 6. Current Implementation Audit

- No canonical EC16 model, repository, service, router, frontend page, or test file exists.
- `backend/app/core/permissions.py` already declares staff permissions for `ai_tool:use`, `ai_assistant:use`, `ai_prompt:read`, `ai_prompt:write`, `ai_history:read`, `ai_credit:read`, and `ai_credit:admin`, plus platform permission `platform:ai_credit_admin`.
- Existing platform-admin checks are service-local in EC12/EC13; EC16 should introduce or reuse a clear platform-admin helper without weakening staff/portal scope separation.
- `backend/app/models/pricing_advisory.py`, `backend/app/services/pricing_advisory.py`, and `backend/app/routers/pricing_advisory.py` are EC9 provider-neutral advisory contracts that always return unavailable placeholders.
- `backend/app/models/webstore.py` and `backend/app/services/webstores.py` include `webstore_ai_usage_events` as EC14 local contract records with no provider calls.
- `backend/app/services/wrap_lab.py` contains AI-related warning text only and no provider execution.
- `backend/app/core/db.py` has no EC16 indexes yet.
- `backend/server.py` has no EC16 router registration yet.
- `frontend/src/lib/navigation.js` already has a Creative Studio area, but EC17 tools remain disabled/deferred.

## 7. Canonical Entities and Relationships

- `AIProviderConfig`: platform-scoped provider adapter configuration. Stores provider key, display name, status, credential mode, BYOK readiness metadata, supported modalities, and no plaintext secrets.
- `AIModelProfile`: platform-scoped model profile linked to `AIProviderConfig`; stores task category, intensity, model alias, unit labels, default token/unit estimates, and status.
- `AICapability`: platform-scoped capability registry entry; maps feature/action keys to entitlement feature keys, credit requirement behavior, permitted providers/models, context requirements, and lifecycle status.
- `AIPromptVersion`: immutable prompt contract linked to an AI capability; stores prompt key, version, template body, schema metadata, status, checksum, and publication metadata.
- `AIContextPacket`: tenant-scoped request context snapshot with source record links, consent flags, redaction metadata, and status.
- `AIActionRequest`: tenant-scoped gateway request envelope linked to capability/model/prompt/context/session; tracks idempotency key, background flag, lifecycle, duration, result summary, and ledger references.
- `AIUsageLedgerEntry`: append-only tenant usage record tied to an action request; records tenant, user, feature, action, provider, model, input/output units, duration, result, source links, background flag, and idempotency key.
- `AIProviderCostLedgerEntry`: append-only provider cost record tied to an action request and usage row; records estimated and actual cost in integer micros/cents, currency, provider invoice references, and reconciliation status.
- `AICreditAccount`: one tenant credit account storing current included and purchased balances, billing-cycle window, low-credit threshold, and status.
- `AICreditLedgerEntry`: append-only customer-facing credit ledger; grant/reserve/commit/release/refund/adjustment/expiration entries with idempotency keys and links to action requests.
- `AIGovernancePolicy`: tenant or platform policy for rate limits, spend caps, credit caps, zero-credit behavior, disabled capabilities, budget-alert thresholds, and effective dates.
- `AIBudgetAlert`: tenant-scoped alert state for low credits, spend caps, rate limits, and provider cost anomalies.
- `AIProviderHealthEvent`: platform-scoped provider/model health and fallback telemetry without enabling silent fallback.

Relationships:

- One provider has many model profiles.
- One capability references allowed model profiles and may have many prompt versions.
- One action request selects one capability, one model profile, one prompt version, and optionally one context packet.
- One action request may create one or more usage, provider-cost, and credit ledger entries.
- One tenant has one active credit account and many credit ledger entries.
- Governance policies may apply globally, per tenant, per capability, or per model profile.

## 8. Lifecycle and Status Contracts

- Provider config: `draft`, `active`, `disabled`, `retired`.
- Model profile: `draft`, `active`, `disabled`, `retired`.
- Capability: `draft`, `active`, `disabled`, `retired`.
- Prompt version: `draft`, `published`, `retired`; published prompt content is immutable.
- Context packet: `created`, `redacted`, `used`, `expired`, `discarded`.
- Action request: `received`, `blocked`, `reserved`, `executing`, `succeeded`, `failed`, `refunded`, `canceled`.
- Usage ledger: `estimated`, `final`, `reversed`.
- Provider cost ledger: `estimated`, `actual`, `adjusted`, `reconciled`.
- Credit account: `active`, `restricted`, `suspended`, `closed`.
- Credit ledger: `grant`, `reserve`, `commit`, `release`, `refund`, `adjustment`, `expiration`; entries are append-only and never delete or rewrite prior credit history.
- Governance policy: `draft`, `active`, `inactive`, `retired`.
- Budget alert: `open`, `acknowledged`, `resolved`.

Rules:

- Every billable AI action must reserve credits before execution and either commit, release, or refund.
- Provider costs and customer credits remain separate records.
- Failed provider execution releases/refunds reserved credits according to the recorded failure policy.
- Zero-credit behavior blocks billable actions unless a governance policy explicitly allows a non-billable capability.
- Idempotency keys prevent duplicate reservations, commits, refunds, and provider-boundary events.
- Published prompt versions, final usage ledger rows, provider-cost ledger rows, and credit ledger rows are immutable except for append-only reversal/adjustment records.

## 9. Permission Model

- Tenant users:
  - `ai_credit:read`: read own tenant credit account and ledger summary.
  - `ai_credit:admin`: tenant owner/admin credit administration actions allowed by EC16, such as acknowledging tenant budget alerts.
  - `ai_history:read`: read own tenant AI usage/action history.
  - `ai_prompt:read`: read published prompt/capability metadata where exposed.
  - `ai_prompt:write`: not broadly used for tenant users in EC16 unless the route is explicitly tenant-scoped and non-provider-executing.
  - `ai_tool:use` and `ai_assistant:use`: reserved for later EC17/EC18 execution paths; EC16 gateway checks can recognize them but must not implement EC17/EC18 features.
- Platform users:
  - `platform:admin` or `platform:ai_credit_admin`: mutate provider configs, model profiles, capabilities, prompt versions, global governance policies, credit grants/adjustments, and platform cost dashboards.
- Portal/public tokens:
  - No EC16 staff/platform route accepts portal or public tokens.
  - Future portal AI use must be explicitly authorized by a later checkpoint and still route through EC16.

Backend checks are authoritative. Frontend visibility is advisory only.

## 10. Stripe, Commercial, and Entitlement Boundaries

- EC16 does not call Stripe and does not create checkout, subscription, billing portal, or webhook records.
- EC13 remains the source of plan/product/price, included-credit commercial promises, and credit-pack commercial price authority.
- EC16 may store credit-account balances and ledger entries derived from EC13 subscription/trial state but must not mutate EC13 catalog prices, subscriptions, setup-package records, dunning records, or EC2 entitlements in this checkpoint.
- EC16 does not publish products or activate provisional AI credit pack pricing while H7 remains active.
- EC2 `feature_entitlements` remains the feature entitlement gate. EC16 can read entitlements before permitting a capability but must not bypass or replace EC2.

## 11. Provider Boundary

- All AI execution must pass through the EC16 gateway service.
- Direct provider calls from EC17/EC18/Webstores/Wrap Lab/pricing advisory are prohibited.
- Phase implementation may include a deterministic local/no-op adapter for tests and contract validation only.
- Platform-managed credentials are the first supported credential mode.
- BYOK fields and adapter boundaries may be reserved, but no BYOK workflow or credential storage is activated in EC16 unless the spec explicitly supports it.
- Silent provider fallback is prohibited. Any future fallback must be policy-selected, audited, and visible.

## 12. Implementation Subphases

### Phase 16A - Backend Contracts, Repositories, Indexes, and Router Skeleton

Scope:

- Add EC16 models for provider config, model profile, capability, prompt version, context packet, action request, usage ledger, provider cost ledger, credit account, credit ledger, governance policy, budget alert, and provider health event.
- Add tenant-scoped repositories and platform-scoped repository helpers.
- Register EC16 indexes.
- Add router registration under `/api/ai`.
- Add platform-admin helper for platform AI routes without mixing staff/platform scopes.

Files:

- `backend/app/models/ai_gateway.py`
- `backend/app/repositories/ai_gateway.py`
- `backend/app/services/ai_gateway.py`
- `backend/app/routers/ai_gateway.py`
- `backend/app/core/db.py`
- `backend/app/core/permissions.py`
- `backend/app/deps.py`
- `backend/server.py`
- `backend/tests/test_ec16_ai_gateway_contracts.py`

### Phase 16B - Credit Reservation, Usage, Cost, and Failure/Refund Flow

Scope:

- Implement credit account creation/read.
- Implement platform grants and manual adjustments with reason and audit.
- Implement reserve, commit, release, and refund ledger flows.
- Implement usage and provider-cost ledger writes through gateway request lifecycle.
- Enforce idempotency on reservations/commits/refunds.
- Ensure provider cost ledger is separate from customer credit ledger.

Files:

- `backend/app/services/ai_gateway.py`
- `backend/app/routers/ai_gateway.py`
- `backend/tests/test_ec16_ai_gateway_metering.py`

### Phase 16C - Governance, Rate Limits, Budget Alerts, and Provider Health

Scope:

- Implement global and tenant governance policy CRUD for platform admins.
- Enforce zero-credit blocking, per-capability enable/disable, rate windows, and spend caps at the gateway.
- Create/acknowledge/resolve budget alerts.
- Record provider/model health events without performing live fallback.

Files:

- `backend/app/services/ai_gateway.py`
- `backend/app/routers/ai_gateway.py`
- `backend/tests/test_ec16_ai_gateway_governance.py`

### Phase 16D - Frontend Tenant and Platform Surfaces

Scope:

- Add tenant credit/usage read surface under the existing subscription/control-center area or a small AI credits page.
- Add platform-only gateway governance/cost dashboard surface if the current frontend role/permission model can expose it safely.
- Keep Creative Studio tools disabled/deferred unless EC17 authorizes them.

Files:

- `frontend/src/lib/aiGateway.js`
- `frontend/src/pages/AICreditsPage.jsx`
- `frontend/src/pages/PlatformAIGovernancePage.jsx`
- `frontend/src/App.js`
- `frontend/src/lib/navigation.js`
- `frontend/src/__tests__/AICreditsPage.test.jsx`

### Phase 16E - Documentation, Evidence, and Closure Validation

Scope:

- Document EC16 runtime contracts.
- Update evidence and tracking docs.
- Run compile checks, targeted backend tests, frontend tests/build if frontend changed, `git diff --check`, push, inspect CI, and fix failures.
- Mark EC16 complete only after final branch-head GitHub CI passes.

Files:

- `docs/modules/ec16_shared_ai_gateway.md`
- `evidence/EC16_IMPLEMENTATION_COMPLETION_REPORT.md`
- `memory/MASTER_CHECKPOINT_CHECKLIST.md`
- `memory/checkpoint_reference_table.md`
- `memory/owner_specification_hold_register.md`
- `memory/progress_register.md`

## 13. Required Indexes

- `ai_provider_configs`: unique `id`; unique `provider_key`; `status/updated_at`.
- `ai_model_profiles`: unique `id`; unique `provider_config_id/model_key`; `task_category/intensity/status`; `status/updated_at`.
- `ai_capabilities`: unique `id`; unique `capability_key`; `status/updated_at`; `entitlement_feature_key/status`.
- `ai_prompt_versions`: unique `id`; unique `prompt_key/version`; `capability_key/status`; `status/published_at`.
- `ai_context_packets`: unique `id`; `tenant_id/user_id/created_at`; `tenant_id/source_entity_type/source_entity_id`; `tenant_id/status/created_at`.
- `ai_action_requests`: unique `id`; unique partial `tenant_id/idempotency_key`; `tenant_id/user_id/created_at`; `tenant_id/capability_key/status/created_at`; `tenant_id/session_id/created_at`; `provider_key/model_key/status`.
- `ai_usage_ledger_entries`: unique `id`; unique partial `tenant_id/idempotency_key`; `tenant_id/action_request_id`; `tenant_id/capability_key/created_at`; `tenant_id/user_id/created_at`; `provider_key/model_key/created_at`.
- `ai_provider_cost_ledger_entries`: unique `id`; unique partial `provider_key/provider_event_id`; `tenant_id/action_request_id`; `tenant_id/capability_key/created_at`; `provider_key/model_key/reconciliation_status`.
- `ai_credit_accounts`: unique `id`; unique `tenant_id`; `status/updated_at`; `billing_cycle_starts_at/billing_cycle_ends_at`.
- `ai_credit_ledger_entries`: unique `id`; unique partial `tenant_id/idempotency_key`; `tenant_id/credit_account_id/created_at`; `tenant_id/action_request_id`; `tenant_id/entry_type/created_at`.
- `ai_governance_policies`: unique `id`; unique partial active policy scope where applicable; `tenant_id/status/effective_at`; `scope_type/scope_key/status`.
- `ai_budget_alerts`: unique `id`; `tenant_id/status/created_at`; `tenant_id/alert_type/status`; `tenant_id/capability_key/status`.
- `ai_provider_health_events`: unique `id`; `provider_key/model_key/created_at`; `status/created_at`.

## 14. Required Tests

- Branch-safe import and router registration tests.
- Platform-only provider/model/capability/prompt mutation.
- Tenant staff denial for platform mutation.
- Portal-token rejection on EC16 routes.
- Tenant isolation for credit account, action, usage, and ledger reads.
- Prompt publication immutability.
- Capability disabled blocks gateway requests.
- Entitlement check boundary is consulted and cannot be bypassed.
- Zero-credit billable request blocks.
- Included and purchased balances consume in the documented order.
- Idempotent reserve, commit, refund, and release.
- Provider failure releases/refunds reserved credits.
- Provider cost ledger remains separate from credit ledger.
- Usage telemetry records tenant, user, feature, action, provider, model, units, duration, result, session, background flag, and source links.
- Rate-limit and spend-cap governance blocks.
- Budget alerts are created and require authorized acknowledgement/resolution.
- Manual credit adjustments require platform-admin permission, reason, audit, and append-only ledger rows.
- No Stripe, EC4 payment, EC13 catalog/subscription, EC14 payout, EC15 Wrap Lab, EC17 Studio, EC18 Assistant, or EC19 route side effects.
- Frontend tests for loading, empty, error, permission visibility, and populated states if frontend surfaces are added.

## 15. Exact Files Expected to Change

Planning:

- `preflight/EC16_SHARED_AI_GATEWAY_USAGE_COST_CREDITS_AND_GOVERNANCE_PREFLIGHT.md`
- `memory/MASTER_CHECKPOINT_CHECKLIST.md`
- `memory/checkpoint_reference_table.md`
- `memory/owner_specification_hold_register.md`
- `memory/progress_register.md`

Implementation:

- `backend/app/models/ai_gateway.py`
- `backend/app/repositories/ai_gateway.py`
- `backend/app/services/ai_gateway.py`
- `backend/app/routers/ai_gateway.py`
- `backend/app/core/db.py`
- `backend/app/core/permissions.py`
- `backend/app/deps.py`
- `backend/server.py`
- `backend/tests/test_ec16_ai_gateway_contracts.py`
- `backend/tests/test_ec16_ai_gateway_metering.py`
- `backend/tests/test_ec16_ai_gateway_governance.py`
- `frontend/src/lib/aiGateway.js`
- `frontend/src/pages/AICreditsPage.jsx`
- `frontend/src/pages/PlatformAIGovernancePage.jsx`
- `frontend/src/__tests__/AICreditsPage.test.jsx`
- `frontend/src/App.js`
- `frontend/src/lib/navigation.js`
- `docs/modules/ec16_shared_ai_gateway.md`
- `evidence/EC16_IMPLEMENTATION_COMPLETION_REPORT.md`
- `memory/MASTER_CHECKPOINT_CHECKLIST.md`
- `memory/checkpoint_reference_table.md`
- `memory/owner_specification_hold_register.md`
- `memory/progress_register.md`

## 16. Risks, Holds, and Open Questions

- H7 remains active. Control: build metering/governance/contracts, but do not live-activate provider-cost-dependent commercial numbers, final per-tool credit costs, or model assignments.
- EC16 spec is broad and references provider routing. Control: implement provider abstraction and deterministic local gateway behavior, not external provider calls.
- EC17 could be accidentally started through capability/prompt work. Control: EC16 implements capability contracts only; no Studio AI tool runtime or generated-asset workflow.
- EC18 could be accidentally started through assistant/action wording. Control: action service contracts are generic and no paid assistant, voice, or autonomous action workflow is built.
- Credit balances depend on EC13 subscription state. Control: EC16 stores accounts/ledgers and reads EC13 state where needed, but does not change EC13 subscriptions, catalog prices, Stripe sessions, or EC2 entitlement projection.
- Provider costs can be sub-cent. Control: store provider estimated/actual cost in integer micros and optional integer cents, with no floating-point money.

No unresolved owner decision blocks useful EC16 local implementation. The current owner prompt lifts H4 for EC16 only. H7 blocks live activation, not local foundation implementation.

## 17. Preflight Result

EC16 is identified, authorized for this branch, scoped, and ready to build. This preflight update performs documentation and tracking only; no EC16 implementation occurred in the preflight step.
