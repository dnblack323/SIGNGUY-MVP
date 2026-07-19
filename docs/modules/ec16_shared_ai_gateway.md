# EC16 Shared AI Gateway Runtime Contracts

**Status:** IMPLEMENTED - LOCAL VALIDATION PASSED - GITHUB CI PENDING
**Checkpoint:** EC16 Shared AI Gateway, Usage, Cost, Credits, and Governance
**Primary route:** `/api/ai`

## Boundaries

EC16 implements the shared AI infrastructure layer only. It does not implement EC17 Studio AI Tools, EC18 Business Assistant/Voice, EC19 onboarding/help, live provider execution, live provider credential use, Stripe checkout, subscription changes, EC4 payment mutation, EC13 catalog/subscription mutation, EC14 Webstore payout mutation, or EC15 Wrap Lab workflow mutation.

Every gateway request in EC16 is deterministic local contract execution. The platform dashboard reports `external_provider_calls: 0`.

## Canonical Backend Collections

- `ai_provider_configs`
- `ai_model_profiles`
- `ai_capabilities`
- `ai_prompt_versions`
- `ai_context_packets`
- `ai_action_requests`
- `ai_usage_ledger_entries`
- `ai_provider_cost_ledger_entries`
- `ai_credit_accounts`
- `ai_credit_ledger_entries`
- `ai_governance_policies`
- `ai_budget_alerts`
- `ai_provider_health_events`

Tenant collections filter by `tenant_id`. Platform collections are available only to platform AI admins.

## Gateway Flow

1. Resolve active capability.
2. Check EC2 entitlement if the capability has `entitlement_feature_key`.
3. Resolve an active allowed model profile and active provider config.
4. Enforce governance policies.
5. Reserve credits.
6. Record action request.
7. Record usage telemetry.
8. Record provider cost telemetry.
9. Commit credits on success or release credits on provider failure.
10. Record audit/activity.

Provider cost rows and customer credit ledger rows are separate records.

## Credit Rules

- One `ai_credit_accounts` row exists per tenant.
- Included and purchased balances are stored as integer credits.
- Reservations increment `reserved_credits`.
- Commits consume included credits before purchased credits.
- Provider failure releases reserved credits.
- Manual grants and adjustments require platform AI admin access, a reason, an audit event, and append-only ledger rows.
- Credit ledger rows are append-only; historical rows are not rewritten.

## Cost Rules

Provider estimated and actual costs are stored in integer micros, with optional integer cents for rounded display/reconciliation. No floating-point money fields are introduced.

## Prompt and Capability Rules

- Published prompt versions are immutable for prompt content, schemas, checksum, prompt key, capability key, and version.
- Capabilities are registry contracts only. EC16 does not create Studio tool workflows.
- Disabled or non-active capabilities cannot execute through the gateway.

## Governance Rules

Governance policies can apply globally, by tenant, by capability, or by model profile.

Supported EC16 controls:

- Zero-credit blocking.
- Disabled capability lists.
- Daily request limits.
- Daily credit limits.
- Daily provider-cost limits.
- Low-credit threshold alerts.
- Budget alert acknowledgement/resolution.

Budget alerts are tenant-scoped but platform AI admins can see all alerts.

## Permissions

- Tenant credit reads require `ai_credit:read`.
- Tenant alert acknowledgement requires `ai_credit:admin` or platform AI admin.
- Tenant history reads require `ai_history:read`.
- Gateway request creation requires `ai_tool:use` or `ai_assistant:use`.
- Provider/model/capability/prompt/governance/credit grant/adjustment/dashboard/provider-health routes require platform AI admin access.
- Portal tokens are rejected by the shared staff-route auth dependency.

## Frontend Surfaces

- `/settings/ai-credits`: tenant AI balance, ledger, open alerts, and gateway history.
- `/settings/ai-governance`: platform-only dashboard for AI provider boundary, policy, usage, and cost visibility.

Creative Studio entries remain disabled/deferred for EC17.

## Indexes

EC16 adds indexes for provider/model uniqueness, capability keys, prompt version identity, tenant context/action/history lookups, idempotent gateway requests, usage/cost ledger lookups, tenant credit account uniqueness, idempotent credit ledger rows, governance policy lookup, budget alert queues, and provider health history.

## Tests

Targeted tests cover platform-only mutation, portal rejection, tenant isolation, prompt immutability, credit grants, reservation/commit/release, idempotency, provider-cost separation, zero-credit blocking, governance rate limits, budget alerts, platform dashboard counts, and no EC4/EC13/EC14/EC15 side effects.
