# EC13 Commercial Billing Runtime Contracts

**Status:** Implemented pending GitHub CI.
**Scope:** EC13 commercial billing runtime after Phase 13A.
**Date:** 2026-07-19

## Boundary

EC13 owns tenant commercial billing records, trial records, setup-package billing records, checkout-session records, billing portal session records, subscription lifecycle records, dunning state, EC13-derived entitlement projection, Stripe Billing boundaries, and platform-fee assessment contracts.

EC13 remains separate from:

- EC4 customer invoices, customer payments, PaymentIntent handling, and refunds.
- EC14 Webstore commerce, Stripe Connect, buyer orders, and payouts.
- EC16 AI provider usage/cost/credit ledgers.
- EC19 guided onboarding implementation.
- EC20 broad platform-admin cockpit and analytics.
- EC21 marketing website, public pricing, signup UI, and Founder offer pages.

## Runtime Entities

- `TenantBillingAccount`: one tenant billing account per tenant, with billing owner, billing email, account status, Stripe customer reference, current subscription pointer, and trial pointer.
- `TenantSubscription`: current plan/product/price contract, billing interval, Stripe subscription/customer references, period dates, dunning state, scheduled cancellation, scheduled downgrade, and manual grace fields.
- `TrialRecord`: free and paid extended trial state with starts/ends timestamps, credit allotment placeholder, conversion credit cents, and one-trial-per-kind tenant guard.
- `CheckoutSessionRecord`: internal checkout idempotency record for subscription, setup-package, extended-trial, and future credit-pack sessions.
- `BillingPortalSessionRecord`: audit record for tenant-owner Billing Portal session creation.
- `SetupPackagePurchase`: EC13 paid setup purchase/waiver record with an explicit `ec19_handoff_status` field that stays `not_started` until EC19 is authorized.
- `CommercialEntitlementRule`: Phase 13A catalog rule consumed by the runtime entitlement projector.
- `PlatformFeeTransactionContract`: immutable platform-fee snapshot record created from EC4 payment facts without mutating EC4 records.

## Lifecycle Contracts

- Billing accounts: `pending`, `trialing`, `active`, `past_due`, `restricted`, `suspended`, `canceled`, `closed`.
- Subscriptions: `pending_checkout`, `trialing`, `active`, `past_due`, `cancellation_scheduled`, `canceled`, `incomplete`, `unpaid`.
- Trials: `free_active`, `free_expired`, `extended_pending_payment`, `extended_active`, `extended_expired`, `converted`, `forfeited`.
- Checkout sessions: `created`, `completed`, `expired`, `canceled`, `superseded`.
- Setup purchases: `pending_payment`, `paid`, `waived`, `refunded`, `partially_refunded`, `fulfilled`, `canceled`.
- Dunning: `current`, `day_1_7_warning`, `day_8_14_soft_restriction`, `eligible_for_suspension`, `suspended`, `manually_extended`, `resolved`.

Subscription checkout completion is idempotent by Stripe checkout session ID. Duplicate checkout creation is prevented per tenant and idempotency key, and pending checkout records block duplicate pending sessions of the same purchase type.

## Money Rules

All EC13 money is stored as integer cents:

- `amount_cents`
- `conversion_credit_cents`
- `basis_amount_cents`
- `platform_fee_cents`

EC13 platform-fee assessment reads EC4 payment facts, snapshots the fee basis and rate, and writes a separate platform-fee transaction. It does not update, delete, or rewrite the original EC4 `payments` or `invoices` documents.

## Permissions

- Tenant owners/admins may manage only their own tenant billing account, checkout sessions, free/extended trials, setup-package checkout, Billing Portal session, cancellation, and downgrade.
- Staff users without owner/admin role cannot mutate tenant billing.
- Platform admins or `platform:subscription_admin` users may perform platform-only actions such as setup waivers, manual grace, suspension, trial expiration, and platform-fee assessment.
- Portal tokens are denied by the staff-route dependency before reaching EC13 routes.
- Cross-tenant tenant-owner reads are denied.

## Stripe Boundaries

EC13 Stripe Billing uses a new boundary module, `app/services/stripe_billing.py`, separate from EC4 `stripe_core.py`.

Implemented EC13 Stripe Billing responsibilities:

- Create Checkout Sessions for subscription, setup-package, and extended-trial records.
- Create Billing Portal Sessions for tenant billing owners/admins.
- Verify Stripe Billing webhooks at `/api/webhooks/stripe-billing`.
- Process subscription checkout completion and invoice payment success/failure events.

Non-goals retained outside this implementation:

- No mutation of EC4 payment webhooks or EC4 PaymentIntent flows.
- No Webstore Stripe Connect/payout behavior.
- No frontend checkout or public pricing page.
- No Stripe product/price publisher beyond the Phase 13A catalog fields.

In local dev/test with placeholder Stripe keys and `AUTH_DEV_BYPASS=true`, the boundary returns deterministic fake Stripe session records without external network calls.

## Entitlement Boundaries

EC13 writes only EC13-derived rows in EC2 `feature_entitlements` where `granted_by` is `commercial_billing`.

The entitlement projector:

- Grants enabled commercial rules for active subscriptions, past-due subscriptions not suspended, cancellation-scheduled subscriptions, and active trials.
- Preserves manually reviewed or test-seeded entitlement rows whose `granted_by` source is not `commercial_billing` or `None`.
- Disables stale EC13-derived entitlement rows when commercial state no longer grants them.
- Audits projection changes.

EC13 does not implement the EC16 AI credit ledger or provider usage metering.

## Founder And Setup Boundaries

Founder commercial contracts remain tenant/shop-scoped through the Phase 13A `FounderTenantContract`. Existing EC12 explicit Founder community access is not mutated by EC13 billing runtime code.

Setup package purchases are billing records only. They do not create onboarding checklists, guided setup flows, help-center work, or EC19 implementation artifacts.

## Dunning And Grace

Dunning is day based:

- Days 1-7 after first failed payment: `day_1_7_warning`.
- Days 8-14: `day_8_14_soft_restriction`.
- Day 15 and later: `eligible_for_suspension`.

Platform manual grace requires platform-admin authority and a reason. Suspension requires platform-admin authority and a reason, updates tenant billing account state, and reprojects EC13-derived entitlements.

## Indexes

EC13 runtime adds indexes for:

- Unique tenant billing account per tenant and sparse Stripe customer ID.
- Unique tenant subscription ID, active-style subscription per tenant, sparse Stripe subscription ID, dunning lookups, and current-period lookup.
- Unique free and extended trial per tenant.
- Unique checkout idempotency key per tenant and sparse Stripe checkout session ID.
- Billing Portal session lookup by tenant and sparse Stripe portal session ID.
- Setup package purchase ID, tenant/status lookup, tenant/package/status lookup, and sparse checkout session ID.
- Unique original platform-fee transaction per EC4 payment source.

## Tests

Targeted tests cover:

- Tenant billing account creation, staff denial, cross-tenant denial, and portal token denial.
- Free trial lifecycle and duplicate prevention.
- Subscription checkout creation, idempotency, completion, active subscription state, and entitlement projection.
- Billing Portal session route.
- Setup package purchase records, paid completion, waiver permission, waiver reason, and EC19 handoff non-start.
- Extended trial checkout, conversion credit cents, and paid activation.
- Dunning transitions, cancellation, downgrade scheduling, manual grace, suspension, and entitlement disablement.
- Platform-fee assessment from EC4 payment facts without EC4 payment mutation or Webstore payout mutation.
- Stripe Billing event idempotency and separation from EC4 invoices/payments.

