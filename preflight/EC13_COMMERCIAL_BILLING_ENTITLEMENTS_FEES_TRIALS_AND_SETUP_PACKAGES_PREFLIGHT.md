# EC13 Commercial Billing, Entitlements, Fees, Trials, and Setup Packages - Preflight Audit

**Status:** PREFLIGHT COMPLETE. Implementation NOT started.
**Repository:** `dnblack323/SIGNGUY-MVP`
**Branch:** `CODEX-ec13-branch`
**Date:** 2026-07-18

## Post-Preflight Acceptance Addendum

The owner accepted this preflight as COMPLETE on 2026-07-18. The following preflight questions are resolved for implementation planning:

- Founder availability is first 25 signed shops; Founder status is tenant/shop-scoped, not user-scoped.
- Existing explicit EC12 Founder access is preserved until the EC13 Founder migration contract is implemented and verified.
- Smart Pricing is not included as a paid add-on in EC13.
- SMS/MMS final pricing is not defined or seeded in EC13; only future usage-billing hooks/categories may be modeled.
- Only owner-approved active prices may be published or sent to Stripe. Unapproved products/prices remain unavailable, never zero-priced or placeholder products.
- Platform-fee refunds use immutable original fee snapshots plus separate proportional reversal/adjustment records.

Detailed Phase 13A plan: `/app/preflight/EC13_PHASE13A_COMMERCIAL_BILLING_CATALOG_AND_CORE_CONTRACTS_PLAN.md`.

## 1. EC13 Purpose

EC13 owns SignGuy's commercial billing system: tenant billing accounts, subscription plans, prices, Founder commercial state, trials, paid extended trials, setup-package purchases, Stripe subscription/checkout/billing portal integration, SignGuy platform-fee policy, and plan/add-on-derived entitlements.

EC13 must not merge three separate money domains:

- Platform commercial billing: SignGuy charges a tenant for SignGuy AI.
- Customer commerce: a shop charges its customer through Quotes, Orders, Invoices, Payments, or EC4 Stripe Core.
- Webstore commerce: future Webstore buyers pay for products through EC14 Stripe Connect/payout flows.

AI usage/credits are commercially priced in EC13 but the live usage gateway, provider cost ledger, and credit ledger are EC16-owned.

## 2. Authoritative Specification Sources

Authority order used for this audit:

1. Current owner prompt authorizing EC13 preflight only.
2. `specs_pack/extracted/00_Master_Index_and_Owner_Decision_Register.docx`
3. `specs_pack/extracted/EC13_Commercial_Billing_Fees_Trials_Setup_and_Entitlements.docx`
4. `memory/documentation_authority_register.md`
5. `memory/owner_specification_hold_register.md`
6. `memory/checkpoint_reference_table.md`
7. `memory/progress_register.md`
8. `memory/MASTER_CHECKPOINT_CHECKLIST.md`
9. `memory/PRD.md`
10. Completed checkpoint evidence and current code
11. `docs/commercial/REVISED_COMMERCIAL_SOURCE_OF_TRUTH_2026-07.md` as historical/reference only where not superseded

Related implementation references reviewed:

- EC2: `preflight/EC2_SHARED_PLATFORM_SERVICES_PREFLIGHT.md`, `docs/architecture/EC2_SHARED_SERVICES.md`, `backend/app/models/feature_entitlement.py`, `backend/app/services/entitlements.py`, `backend/app/routers/entitlements.py`, `frontend/src/lib/entitlements.js`, `backend/tests/test_entitlements.py`
- EC4: `preflight/EC4_INVOICES_PAYMENTS_STRIPE_CORE_PREFLIGHT.md`, `docs/integrations/stripe_core.md`, `docs/integrations/stripe_webhooks.md`, `docs/modules/invoices.md`, `docs/modules/payments.md`, `docs/security/payment_security.md`, `backend/app/services/stripe_core.py`, `backend/app/services/payment_service.py`, `backend/app/routers/payments.py`, `backend/app/routers/webhooks_stripe.py`
- EC12: `evidence/EC12_PHASE12G_COMPLETION_REPORT.md`, `evidence/EC12_PHASE12I_CLOSURE_REPORT.md`, `backend/app/models/community.py`, `backend/app/services/community_service.py`, `backend/app/routers/community.py`, `backend/tests/test_ec12_phase12g_community_support.py`
- EC16/19/20/21 specs: `EC16_Shared_AI_Gateway_Cost_Credits_and_Governance.docx`, `EC19_Onboarding_Help_and_App_Documentation.docx`, `EC20_Platform_Admin_Analytics_Dunning_and_Support.docx`, `EC21_Marketing_Public_Pricing_Founder_and_Signup.docx`

## 3. Owner Decisions Already Locked

- Founder availability is **first 25 signed shops**, not first 50 users. The current prompt's "first 50 users" item is superseded by EC13 and the hold register.
- Founder receives one complete included package: Core + Webstores + Wrap Lab + 1,000 monthly AI credits.
- Founder monthly price is `$119` for the first 3 paid months, then `$189` while continuously active.
- Founder annual price is `$1,890` upfront and replaces the introductory monthly discount.
- Founder setup is `$299` Kickstart unless an explicitly approved waiver exists.
- GA Core is `$149/month` or `$1,490/year`, with 300 monthly credits.
- Webstores add-on is `$89/month` or `$890/year`, with 300 monthly credits.
- Wrap Lab add-on is `$119/month` or `$1,190/year`, with 500 monthly credits.
- Complete Bundle is `$279/month` or `$2,790/year`, with 1,100 monthly credits.
- Webstores standalone is `$109/month` provisional; annual standalone is not approved.
- Wrap Lab standalone is `$139/month` provisional after readiness verification; annual standalone is not approved.
- Free trial is 48 hours from verified activation/explicit start, with 25 credits.
- Extended trial is `$20` for 7 days, with 75 total credits and a `$20` credit if subscribing within 14 days after trial end.
- Credit packs are 100/$19, 300/$45, and 800/$99, subject to EC16/H7 provider-cost audit.
- Platform fees are Founder months 1-3: 0% standard and 0% Webstores; Founder month 4+: 0.5% standard and 1.5% Webstores; GA: 1% standard and 2% Webstores.
- Setup package prices are DIY $0, Founder Kickstart $299, Standard $499, Full $999, White Glove $1,999+.
- Setup is billed separately from software access, AI packs, Stripe processing, and platform fees.
- Products, prices, coupons, entitlements, and fee bases are backend-controlled.
- No duplicated frontend price constants.
- Transaction fee snapshots must be immutable.
- Included credits reset; purchased credits remain while the subscription stays paid/active.
- Dunning authority is day-based: Days 1-7 normal access with warnings, Days 8-14 soft restriction, Day 15+ eligible for suspension. It is not Stripe retry-count based.
- EC16 requires provider cost and credit ledgers to remain separate.
- EC21 public pricing must render from commercial configuration or a shared versioned manifest, never duplicate constants.
- Founder/community access currently uses explicit platform-managed Founder access and must not be silently replaced without migration.

## 4. Open Contradictions Or Decisions Requiring Owner Confirmation

- The prompt repeats "first 50 users"; controlling EC13 authority says first 25 signed shops. Treat 25 as locked unless the owner issues a newer written correction.
- "Avoid feature-gating ordinary core business records" is consistent with EC13/EC20 access-preservation language, but EC13 should still encode an explicit rule that customers, quotes, orders, invoices, payments, billing/export/support/privacy/account-recovery remain accessible in delinquency flows.
- Smart Pricing as a paid add-on is not an EC13-locked commercial product in the reviewed authority. EC9 pricing is core; EC16/17 AI/advisory work remains held. Owner confirmation is needed before inventing a Smart Pricing SKU.
- External SMS/MMS commercial usage pricing is not locked in EC13. SMS sending remains not started; any separate usage billing needs owner confirmation and a later owner checkpoint.
- Refund/partial-refund proportional platform-fee policy is required but the exact arithmetic and accounting treatment are not specified.
- Standalone annual prices for Webstores and Wrap Lab remain not approved.
- Founder waiver rules are mentioned but not enumerated; EC13 needs a waiver reason/audit contract without inventing broad automatic waivers.
- Tax handling for SignGuy's own subscriptions/setup packages is not specified beyond EC7 customer invoice tax snapshots. EC13 should support Stripe Tax/manual tax fields only after owner/accounting direction.

## 5. Existing Source Map

### Backend

- `backend/app/models/feature_entitlement.py` - tenant-scoped entitlement rows with `feature_key`, `enabled`, optional quota, used quota, expiry, `granted_by`, and notes.
- `backend/app/services/entitlements.py` - tenant read/check service, including expiry and quota denial. Write path exists only as `_upsert_entitlement_for_tests`.
- `backend/app/routers/entitlements.py` - tenant-readable `/api/entitlements` endpoints guarded by `settings:read`.
- `backend/app/deps.py` - `require_entitlement(feature_key)` dependency returns HTTP 402 when a tenant lacks access.
- `backend/app/core/permissions.py` - reserves staff `subscription:read`, `subscription:manage`, `ai_credit:*`, add-on permissions, and platform `platform:subscription_admin`, `platform:ai_credit_admin`.
- `backend/app/services/stripe_core.py` - EC4 PaymentIntent/refund wrapper for customer invoices.
- `backend/app/services/payment_service.py` - manual/Stripe customer payments and refunds, not platform subscriptions.
- `backend/app/routers/payments.py` - invoice-scoped customer-payment endpoints.
- `backend/app/routers/webhooks_stripe.py` - EC4 Stripe webhook handler for PaymentIntent/refund events.
- `backend/app/services/webhooks.py` and `backend/app/models/webhook_event.py` - provider-agnostic webhook dedupe/status framework reusable by EC13.
- `backend/app/models/community.py`, `backend/app/services/community_service.py`, `backend/app/routers/community.py` - Founder area and explicit `FounderAccess` grants.

No `billing`, `subscription`, `plan`, `trial`, `checkout`, `billing portal`, `setup_package`, `platform_fee`, `ai_credit ledger`, or `usage ledger` implementation files were found in `backend/app`.

### Frontend

- `frontend/src/pages/FeatureAccessPage.jsx` - existing feature-access read surface.
- `frontend/src/lib/entitlements.js` - client wrapper for read-only entitlement status.
- `frontend/src/components/invoices/PaymentDialogs.jsx`, `frontend/src/pages/InvoiceDetailPage.jsx`, `frontend/src/portal/PortalInvoicePayPage.jsx` - customer invoice payment UI.
- `frontend/src/pages/CommunityPage.jsx` - Founders tab and support/feedback surface.
- `frontend/src/lib/navigation.js` - disabled placeholders for Webstores, Wrap Lab, Studio/AI, `/settings/subscriptions`, portals, and platform governance.

No active billing settings, subscription management, checkout, trial banner, billing portal, setup-package purchase, AI credit purchase, or platform-admin billing page exists.

### Database

Existing collections/indexes relevant to EC13:

- `feature_entitlements`: unique `(tenant_id, feature_key)`.
- `webhook_events`: unique `(provider, provider_event_id)`.
- `payments`: customer invoice payments with Stripe IDs and idempotency indexes.
- `invoices`: customer invoices with document/financial status indexes.
- `founder_access`: `id` unique and `(user_id, tenant_id, revoked_at)`.
- `settings`: namespaced tenant settings; secrets are prohibited.

No commercial billing account, subscription, plan, price, trial, setup-package purchase, platform-fee ledger, checkout-session, billing-portal-session, dunning-state, or AI-credit ledger collection exists.

### Stripe

Current Stripe integration is EC4 Payment Intents/refunds for a shop's customer invoices. It does not use Stripe Products, Prices, Subscriptions, Checkout Sessions, Billing Portal, Coupons/Promotions for SignGuy plans, Stripe Tax, or Connect.

### Webhooks

`/api/webhooks/stripe` verifies signatures, records into `webhook_events`, dedupes by `(provider, provider_event_id)`, and handles customer-payment events:

- `payment_intent.succeeded`
- `payment_intent.payment_failed`
- `payment_intent.canceled`
- `charge.refunded`
- `refund.updated`

Subscription events such as `checkout.session.completed`, `customer.subscription.*`, `invoice.payment_failed`, and `invoice.payment_succeeded` are not handled.

### Settings

`settings` can hold non-secret typed JSON by namespace/key. It should not hold Stripe secrets or unversioned pricing constants. EC13 may use settings for display preferences, but commercial truth should be versioned backend config/manifest plus commercial models.

### Platform Admin

Only platform/admin permission primitives and EC12 platform-style checks exist. No active Platform Admin cockpit, tenant billing card, suspend/reactivate UI, dunning UI, impersonation UI, broadcast email UI, or platform analytics implementation was found. EC20 owns most platform-admin operations; EC13 should provide the billing state and minimal admin APIs needed for commercial correctness.

### Public Pricing

No public pricing/marketing implementation exists. EC21 owns the public pricing/signup surfaces and must consume EC13's versioned manifest/configuration.

### Tests

Existing relevant tests:

- `backend/tests/test_entitlements.py`
- `backend/tests/test_payments_ec4.py`
- `backend/tests/test_invoice_reconciliation.py`
- `backend/tests/test_ec6_portal_payment.py`
- `backend/tests/test_ec12_phase12g_community_support.py`
- `backend/tests/test_ec12_phase12h_productivity_templates.py`
- `backend/tests/test_permissions_scope.py`
- `backend/tests/test_money_policy.py`

No EC13-specific tests exist yet.

### Legacy/Duplicate Code

- `docs/commercial/REVISED_COMMERCIAL_SOURCE_OF_TRUTH_2026-07.md` is historical/reference under the current authority rules where EC13 and the hold register supersede it.
- The old master plan's commercial sections are historical for EC13.
- EC4 payment code must not be duplicated or repurposed as platform subscription billing.
- EC12 `FounderAccess` must not be silently collapsed into commercial subscription state.

## 6. Current Data Model

The current app has no commercial subscription data model.

Existing money/customer commerce data model:

- `Invoice`: tenant-scoped customer invoice, with `document_status`, backend-derived `financial_status`, and integer-cent totals.
- `Payment`: tenant-scoped customer payment/refund record linked to an invoice/customer/order.
- `WebhookEvent`: provider event log for replay safety.
- `FeatureEntitlement`: tenant feature access read/check row.
- `FounderAccess`: explicit platform-managed access for Founder community surfaces.

EC13 must add a commercial model without changing customer invoice/payment semantics.

## 7. Existing Entitlement Model

The EC2 entitlement model is reusable but incomplete for commercial billing:

- Good reuse: tenant scope, feature key, enabled flag, expiry, quota, quota used, `require_entitlement`, unique `(tenant_id, feature_key)`.
- Missing: platform write API, source-of-truth derivation from subscription/trial/add-on/setup purchase, historical entitlement snapshots, reason/source, plan/version, lifecycle audit, and idempotent recomputation from commercial state.
- Required EC13 direction: keep `FeatureEntitlement` as the runtime access projection, but derive it from canonical commercial subscription/trial/add-on/setup records. Do not let staff/frontend set entitlements directly.

## 8. Existing Stripe Architecture

Current Stripe is EC4 customer-payment Stripe Core:

- PaymentIntent creation for an existing invoice balance.
- Refund creation against an invoice payment.
- Stripe webhook signature verification.
- Internal Payment row is authoritative for customer invoice reconciliation.
- Replay protection through `webhook_events`.
- Publishable key/client secret are not rendered as visible text or persisted.

Missing EC13 Stripe architecture:

- Stripe Customer mapping for tenants.
- Stripe Products/Prices mapping for SignGuy plans/add-ons/setup/credit packs.
- Checkout Sessions for subscriptions, setup packages, extended trials, and credit packs.
- Billing Portal sessions for tenant owners.
- Subscription lifecycle webhooks.
- Stripe invoice payment success/failure dunning linkage.
- Coupons/promotions for Founder intro price and conversion credit.
- Idempotent checkout creation and duplicate pending checkout prevention.

## 9. Existing Trial Behavior

No production trial model, free-trial lifecycle, extended-trial purchase, conversion credit, trial countdown, trial expiration, one-trial-per-business guard, or trial entitlement projection exists.

EC13 must build trial state before checkout/subscription activation can be production-ready.

## 10. Existing Founder Access Behavior

Founder access currently exists only as explicit platform-managed community access:

- `FounderAccess` row in `founder_access`.
- `users.founder_access` flag set on grant/revoke.
- Founders community scope gates on explicit user Founder access or platform admin status.
- Tests confirm Founder access does not mutate `feature_entitlements`, `subscriptions`, `template_definitions`, or onboarding records.

This is not a commercial Founder subscription engine. EC13 must preserve existing Founder community access and add a migration/relationship contract to commercial Founder state.

## 11. Existing Setup/Onboarding Fee Behavior

Paid setup/onboarding packages do not exist in code.

Related existing systems:

- EC9 Pricing Foundation setup quiz/configuration.
- EC12 templates and communications.
- EC19 specification for onboarding/help/checklist behavior, not implemented.
- Historical commercial doc and EC13 spec define setup package prices and included services.

EC13 should build setup-package purchase/billing records only. EC19 owns the guided onboarding product experience; paid setup purchases must not create a parallel onboarding system.

## 12. Existing Platform-Fee Behavior

No SignGuy platform-fee calculation, snapshot, ledger, display, refund policy, or Webstore fee basis exists.

EC4 `Invoice.fee_cents` is customer-invoice money, not SignGuy platform-fee billing. EC13 must not overload it.

## 13. Existing AI-Credit Or Usage Behavior

No AI gateway, usage ledger, provider cost ledger, credit ledger, credit reservation/commit/refund, top-up credit purchase, low-credit warning, or zero-credit block exists.

Existing pricing/advisory code is deterministic/scaffolded. EC16 owns live AI metering and ledger implementation. EC13 may define commercial products/prices and provision initial credit entitlement contracts, but it must not implement live AI calls or a duplicate EC16 ledger.

## 14. Dependencies On EC2, EC4, EC12, EC16, EC20, And EC21

- EC2: reuse settings, webhook framework, audit/activity, notifications, integration status, feature entitlements, permission model.
- EC4: reuse Stripe SDK wrapper patterns and security rules, but keep platform subscriptions separate from customer invoice PaymentIntent flows.
- EC12: preserve explicit Founder access and support/community boundaries; no subscription inference from community access.
- EC16: consumes EC13 plan/price/credit-pack commercial config but owns AI gateway, usage ledger, provider cost ledger, credit ledger, and cost dashboards.
- EC20: consumes EC13 billing/dunning state for platform admin, support, suspension/reactivation, analytics, and dunning operations.
- EC21: consumes EC13 versioned commercial manifest/config for public pricing, Founder slot count, signup, checkout, and trial presentation.

## 15. Systems Depending On EC13

- `require_entitlement` guards for Webstores, Wrap Lab, advanced production, Studio AI, AI Assistant, Template Vault, and future paid features.
- Tenant owner subscription/settings UI.
- EC20 platform admin dunning/support/analytics.
- EC21 public pricing/signup.
- EC16 credit entitlements and AI usage blocks.
- EC14 Webstores add-on/standalone entitlement.
- EC15 Wrap Lab add-on/standalone entitlement.
- EC22 final commercial hardening.

## 16. Problems And Risks Found

- No canonical commercial models exist.
- No Stripe subscription/customer/price mapping exists.
- EC4 Stripe webhook handler currently ignores subscription invoice events.
- Existing entitlement writes are test-only.
- Founder commercial state is absent, while Founder community access exists separately.
- Commercial constants exist in historical docs/specs but no versioned runtime manifest exists.
- No platform admin billing surface exists.
- No dunning state exists.
- No trial state exists.
- No setup-package purchase records exist.
- Existing navigation exposes disabled placeholders; implementation must not just enable them without backend truth.
- The prompt's "first 50 users" conflicts with controlling "first 25 shops".

## 17. Keep / Rebuild / Remove Decisions

Keep:

- EC2 `FeatureEntitlement` as the runtime access projection.
- EC2 `webhook_events` and `services/webhooks.py` for Stripe webhook replay safety.
- EC4 Stripe security patterns and signature verification.
- EC4 customer invoice/payment model untouched.
- EC12 explicit `FounderAccess` for community/founder surfaces.
- Locked money policy: transactional commerce values use integer cents.
- Existing disabled frontend placeholders until backend contracts exist.

Rebuild/add:

- Commercial products/prices/version manifest.
- Tenant billing account.
- Tenant subscription lifecycle.
- Trial lifecycle.
- Setup package purchase lifecycle.
- Checkout session orchestration.
- Billing portal session endpoint.
- Subscription/dunning webhook processing.
- Entitlement derivation service.
- Founder commercial migration contract.
- Platform-fee calculation/snapshot contract.

Remove/reject:

- Any frontend-defined price constants.
- Any attempt to reuse EC4 customer invoice `Payment` rows as SignGuy subscription payments.
- Any implicit Founder status inferred from email, role, or existing community membership.
- Any retry-count-based dunning logic as the suspension authority.
- Any EC16 live AI ledger/provider implementation inside EC13.
- Any EC19 onboarding implementation inside EC13.

## 18. Security And Tenant-Isolation Risks

- Platform billing data is cross-tenant sensitive; platform permissions must remain disjoint from staff and portal permissions.
- Tenant owners/admins may manage their own subscription only, never another tenant's billing account.
- Customer portal and employee portal tokens must be denied from platform billing endpoints.
- Stripe webhook tenant resolution must use internal Stripe IDs mapped to tenant billing accounts, not untrusted payload metadata.
- Checkout and billing portal URLs must be short-lived and never persisted as secrets.
- Logs must not include Stripe secrets, client secrets, raw webhook payloads, payment methods, or full customer billing data.
- Suspension must preserve export, support, billing, account recovery, privacy, and data deletion access.

## 19. Money And Accounting Risks

- All EC13 transactional amounts must be integer cents: plan prices, setup fees, credits, platform fees, discounts, refunds, tax, and Stripe amounts.
- Plan/price records must be immutable once used. Changes create a new version.
- Platform fees must be separate from Stripe processing, taxes, shipping, supplier charges, and customer-facing line items.
- Refund and partial-refund behavior needs an explicit proportional-fee policy before implementation.
- Annual plans must reset included AI credits monthly, not issue a full year of credits upfront.
- Founder intro price should use promotion/coupon logic, not a permanent Founder intro SKU.
- Extended-trial `$20` conversion credit must be auditable and applied only within the approved window.

## 20. Webhook/Idempotency Risks

- Stripe subscription events must use `webhook_events` dedupe and handler-level idempotency.
- Duplicate checkout sessions must be prevented per tenant/product/period while a pending checkout exists.
- Subscription activation must be idempotent on `checkout.session.completed` and `customer.subscription.updated`.
- `invoice.payment_failed` and `invoice.payment_succeeded` must update dunning state idempotently.
- Webhook processing must tolerate out-of-order events by fetching/reconciling internal state.
- Customer invoice PaymentIntent events and platform subscription invoice events must route to separate handlers.

## 21. Cancellation, Downgrade, Grace-Period, And Dunning Risks

- The authoritative dunning model is day-based, not retry-count based.
- Downgrades and cancellations must define effective timing: immediate vs period end.
- Core records must remain readable during delinquency/suspension.
- Add-on and AI usage restrictions should be derivable from billing state.
- Founder continuous-active loss must be explicit, audited, and not triggered by a transient webhook race.
- Reactivation must restore entitlements idempotently.

## 22. Migration Risks

- Existing `FounderAccess` should be linked to commercial Founder state without silently revoking or granting access.
- Existing tenants/users lack billing account IDs; backfill must be additive and audit-friendly.
- Existing entitlements may be test-seeded/dev-only; EC13 should mark derived entitlements by source without clobbering manually reviewed records until migration is defined.
- Current Stripe EC4 env vars may not be sufficient for platform subscription webhooks if customer-commerce and platform-billing use different Stripe accounts or webhook secrets.
- Historical docs use old names (`Wrap Command Center`) and obsolete standalone pricing; implementation must use current names/prices.

## 23. Recommended EC13 Architecture

Build EC13 as a separate `commercial_billing` domain that projects access into EC2 entitlements and consumes EC4-style Stripe helpers only through shared low-level utilities.

Recommended layers:

- Versioned commercial catalog: backend-owned products, plans, prices, billing intervals, setup packages, credit packs, fee schedules, trial rules, and entitlement mappings.
- Tenant billing account: one account per tenant, with Stripe customer ID, billing owner, status, terms version, and safe contact fields.
- Subscription lifecycle: current plan, add-ons, billing interval, period dates, Stripe subscription ID, founder state, cancellation/downgrade state, and dunning state.
- Trial lifecycle: free and extended trial records with activation source, credit allotment, expiration, conversion window, and one-trial guard.
- Setup package purchases: independent purchase records linked to commercial checkout/payment status and later EC19 onboarding service fulfillment.
- Checkout orchestration: server-created Stripe Checkout Sessions with idempotency and internal pending checkout records.
- Billing portal orchestration: tenant-owner-only billing portal session endpoint.
- Webhook processor: platform-billing handler for subscription/checkout/invoice events, separate from EC4 customer payment handler.
- Entitlement projector: deterministic service that derives `feature_entitlements` from plan/add-on/trial/setup state.
- Platform-fee policy service: computes/snapshots fee rates and basis for standard customer payments and future Webstore sales without mutating EC4 payments or EC14 payouts.

## 24. Recommended Canonical Entities And Ownership

- `CommercialCatalogVersion` or manifest file: EC13 owns.
- `CommercialProduct`: EC13 owns product identity and type (`core`, `bundle`, `addon`, `standalone`, `setup_package`, `credit_pack`, `trial_extension`).
- `CommercialPrice`: EC13 owns immutable price records, interval, currency, cents, Stripe price ID, active/version fields.
- `TenantBillingAccount`: EC13 owns tenant-to-Stripe-customer mapping and billing owner.
- `TenantSubscription`: EC13 owns plan/add-on/current-period/dunning/founder status.
- `SubscriptionItem` or embedded add-ons: EC13 owns subscription components and entitlement sources.
- `TrialRecord`: EC13 owns trial lifecycle.
- `SetupPackagePurchase`: EC13 owns paid setup purchase and billing status; EC19 owns onboarding checklist execution.
- `CheckoutSessionRecord`: EC13 owns checkout idempotency and pending/completed/expired state.
- `BillingPortalSessionRecord` optional audit-only record: EC13 owns portal session audit metadata, not long-lived URLs.
- `PlatformFeeSchedule` and `PlatformFeeSnapshot`: EC13 owns fee calculation contracts; EC4/EC14 may call projection helpers later.
- `FeatureEntitlement`: EC2 owns shape and guard; EC13 owns commercial derivation writes.
- `FounderAccess`: EC12 owns community access; EC13 references/migrates, never replaces silently.

## 25. Recommended Status/Lifecycle Contracts

Suggested status contracts:

- Billing account: `pending`, `trialing`, `active`, `past_due`, `restricted`, `suspended`, `canceled`, `closed`.
- Subscription: `pending_checkout`, `trialing`, `active`, `past_due`, `cancellation_scheduled`, `canceled`, `incomplete`, `unpaid`.
- Trial: `not_started`, `free_active`, `free_expired`, `extended_pending_payment`, `extended_active`, `extended_expired`, `converted`, `forfeited`.
- Checkout: `created`, `completed`, `expired`, `canceled`, `superseded`.
- Setup purchase: `pending_payment`, `paid`, `waived`, `refunded`, `partially_refunded`, `fulfilled`, `canceled`.
- Dunning: `current`, `day_1_7_warning`, `day_8_14_soft_restriction`, `eligible_for_suspension`, `suspended`, `manually_extended`, `resolved`.
- Founder: `not_founder`, `pending_slot`, `active_founder`, `grace_exception`, `lost_founder`, `revoked`.

## 26. Recommended Permission Model

- Tenant owner/admin staff:
  - `subscription:read`: view own tenant billing/subscription state.
  - `subscription:manage`: start checkout, change plan/add-ons, open billing portal, cancel/reactivate own tenant where allowed.
  - `ai_credit:read`: view commercial credit balance/projection once EC16 exists.
- Platform operators:
  - `platform:subscription_admin`: catalog/admin overrides, Founder slot/waiver/dunning management.
  - `platform:tenant_read` and `platform:tenant_status`: support read/suspension operations in EC20.
  - `platform:ai_credit_admin`: EC16/EC20 credit adjustments after EC16 exists.
- Portal scopes:
  - Customer Portal and Employee Portal must not access EC13 tenant billing endpoints.
  - Future Webstore owner portal billing rules should be EC14/EC13 integrated only after EC14 authorization.

Backend enforcement is authoritative; frontend visibility is decoration only.

## 27. Recommended Phase Sequence

Recommended EC13 implementation phases:

1. **13A - Commercial contracts and catalog manifest:** versioned products/prices/fee/trial/setup contracts, no Stripe writes.
2. **13B - Tenant billing account and Founder migration contract:** tenant billing account model, Founder slot fields, explicit relationship to EC12 FounderAccess, no entitlement mutation yet.
3. **13C - Entitlement derivation service:** commercial-to-`feature_entitlements` projection, platform write path, audit, tenant isolation.
4. **13D - Trials:** free trial, extended trial purchase placeholder contract, expiration/conversion window, credit entitlement placeholders only.
5. **13E - Stripe products/prices and checkout orchestration:** server-created Checkout Sessions for subscription/setup/extended-trial/credit-pack purchase types with duplicate prevention.
6. **13F - Subscription webhook processing:** subscription activation, period dates, payment success/failure, dunning-state update, idempotency.
7. **13G - Billing portal and tenant owner billing UI:** own-tenant read/manage, portal session creation, disabled portal/customer/employee access.
8. **13H - Setup package billing records:** setup package purchase/waiver/refund lifecycle and EC19 handoff contract, no EC19 onboarding implementation.
9. **13I - Platform-fee policy and snapshots:** backend fee schedule and snapshot helpers, no mutation of customer invoices/payments or Webstore payouts.
10. **13J - Dunning, cancellation, downgrade, grace, Founder continuous-active rules:** day-based restrictions and reactivation contracts.
11. **13K - Platform-admin billing controls needed for EC13:** minimal admin APIs for Founder slots, waivers, manual grace/mark-paid, audit; defer analytics/support cockpit breadth to EC20.
12. **13L - Validation and closure:** full EC13 targeted suite, regression around EC2/EC4/EC12 boundaries, docs/evidence, no EC14/16/19/20/21 implementation.

## 28. Required Acceptance Tests

Backend tests should cover:

- Tenant isolation for every commercial collection.
- Platform-admin boundaries for catalog, overrides, Founder slots, grace, dunning.
- Tenant-owner billing permissions.
- Customer portal denial.
- Employee portal denial.
- Stripe webhook signature verification.
- Webhook idempotency and duplicate event no-op.
- Duplicate checkout prevention.
- Integer-cent money storage.
- Plan/price immutability.
- Entitlement derivation from subscription/trial/add-on state.
- Trial start/extend/expire.
- Extended-trial `$20` conversion credit.
- Founder access preservation and migration.
- Subscription activation from checkout/webhook.
- Payment failure and dunning transitions.
- Grace-period extension and reset on payment success/manual mark-paid.
- Cancellation.
- Downgrade.
- Upgrade.
- Proration rules.
- Refund/credit behavior.
- Billing portal access.
- Setup package purchase and waiver.
- No mutation of customer invoices/payments.
- No mutation of Webstore payouts.
- No unauthorized AI-credit ledger/provider implementation.
- No EC19 onboarding implementation.
- Audit history.
- Safe webhook logging and no raw secrets.
- No secret exposure in frontend/logs/storage.

Frontend tests should cover:

- Billing page route hidden/disabled until backend permissions are present.
- Tenant owner sees only own subscription/trial/setup state.
- Staff without permissions cannot manage billing.
- Portal tokens cannot reach billing.
- Checkout/billing-portal actions call backend only.
- Pricing display comes from backend/shared manifest only.

## 29. Deferred Scope And Owning Checkpoint

- Webstore storefront, buyer orders, Stripe Connect, payouts, Webstore owner portal: EC14.
- Wrap Lab standalone readiness and Wrap workflows: EC15.
- AI gateway, usage ledger, provider cost ledger, credit ledger, generation history, cost dashboards: EC16.
- Studio AI tools/tool review: EC17.
- Paid Business Assistant/Realtime Voice: EC18.
- Guided onboarding checklist/help center/contextual docs: EC19.
- Full platform admin cockpit, analytics, broad dunning/support UX, impersonation, broadcast email, maintenance mode: EC20.
- Marketing website, public pricing, Founder offer page, signup flow: EC21.
- Final commercial release hardening: EC22.
- External SMS/MMS sending and billing: owner confirmation/later checkpoint.
- Smart Pricing paid add-on SKU: owner confirmation required.

## 30. Exact Files Likely To Be Created Or Modified

Likely backend additions:

- `backend/app/models/commercial_catalog.py`
- `backend/app/models/tenant_billing.py`
- `backend/app/models/tenant_subscription.py`
- `backend/app/models/trial.py`
- `backend/app/models/setup_package.py`
- `backend/app/models/checkout_session.py`
- `backend/app/models/platform_fee.py`
- `backend/app/services/commercial_catalog.py`
- `backend/app/services/tenant_billing.py`
- `backend/app/services/subscriptions.py`
- `backend/app/services/commercial_entitlements.py`
- `backend/app/services/trials.py`
- `backend/app/services/setup_packages.py`
- `backend/app/services/platform_fees.py`
- `backend/app/services/stripe_billing.py`
- `backend/app/routers/billing.py`
- `backend/app/routers/webhooks_stripe_billing.py` or a clearly separated extension to `webhooks_stripe.py`
- `backend/app/core/db.py`
- `backend/server.py`
- `backend/app/core/config.py`
- `backend/app/core/permissions.py` only if new perms beyond reserved names are needed

Likely frontend additions:

- `frontend/src/pages/BillingPage.jsx`
- `frontend/src/pages/BillingCheckoutReturnPage.jsx`
- `frontend/src/lib/billing.js`
- `frontend/src/components/billing/*`
- `frontend/src/lib/navigation.js`
- `frontend/src/App.js`

Likely docs/evidence/tests:

- `docs/commercial/commercial_catalog.md`
- `docs/commercial/billing_architecture.md`
- `docs/commercial/entitlement_derivation.md`
- `docs/commercial/dunning_and_grace.md`
- `docs/commercial/platform_fees.md`
- `docs/integrations/stripe_billing.md`
- `docs/security/billing_security.md`
- `backend/tests/test_ec13_*.py`
- `evidence/EC13_PHASE*_COMPLETION_REPORT.md`

Files that should not be modified for EC13 except for regression-safe integration points:

- `backend/app/models/invoice.py`
- `backend/app/models/payment.py`
- `backend/app/services/payment_service.py`
- `backend/app/routers/payments.py`
- `frontend/src/portal/PortalInvoicePayPage.jsx`
- EC14/EC15/EC16/EC19 implementation files not yet authorized.

## 31. Preflight Conclusion

EC13 is ready to be planned as a commercial billing implementation, but no implementation should start until the owner explicitly authorizes EC13 build phases.

The repo has strong reusable foundations: EC2 entitlements/webhooks/settings/audit, EC4 Stripe security patterns, EC12 explicit Founder access, and locked money/permission contracts. It does not yet have a production commercial billing engine. The correct architecture is to add a dedicated commercial billing domain that derives runtime entitlements and integrates with Stripe subscriptions while preserving existing customer invoice/payment flows.

Primary risks to control in implementation are: authority conflict around Founder count, plan/price immutability, dunning day-model enforcement, Founder migration, webhook idempotency, and strict separation from customer commerce, Webstore commerce, EC16 AI ledgers, and EC19 onboarding.

## 32. Confirmation No Implementation Was Performed

Confirmed. This preflight performed repository investigation and documentation updates only. No EC13 backend models, routers, services, frontend screens, database migrations, Stripe subscription logic, entitlement mutation logic, trial implementation, setup-package implementation, platform-fee implementation, AI-credit ledger, EC19 onboarding, EC14 Webstores, EC15 Wrap Lab, EC20 platform admin, or EC21 public pricing implementation was added.
