# EC13 Phase 13A - Commercial Billing Catalog and Core Contracts Plan

**Status:** PLAN COMPLETE. Implementation NOT started.
**Repository:** `dnblack323/SIGNGUY-MVP`
**Branch:** `CODEX-ec13-branch`
**Date:** 2026-07-18

## 1. Updated Owner Decisions

The EC13 preflight is accepted as COMPLETE. These post-preflight owner decisions are binding before implementation:

- Founder availability is first 25 signed shops, not 50 users.
- Founder status is assigned per tenant/shop, not per individual user.
- Existing explicit EC12 Founder access stays authoritative until the EC13 migration contract is implemented, verified, and explicitly connected.
- Smart Pricing is not an EC13 paid add-on. EC13 must only leave the commercial architecture capable of future add-ons.
- SMS/MMS final pricing is not defined or seeded in EC13. EC13 may add future usage-billing categories/hooks only as inactive/unpriced contracts.
- External SMS sending, provider integration, final SMS/MMS usage pricing, and SMS/MMS credit rules are deferred.
- EC13 must not invent or seed unapproved standalone monthly or annual prices.
- EC13 must support monthly, annual, add-on, and standalone price models.
- Only owner-approved active prices may be published or sent to Stripe.
- Unapproved products/prices must remain unavailable, not zero-priced or placeholder Stripe products.
- Platform-fee refunds use reversal records: full refunds create full proportional platform-fee reversals; partial refunds create proportional partial reversals.
- Stripe/provider fees are recorded separately and are not silently rewritten.
- Manual platform-fee exceptions require platform-admin permission, reason, audit event, and separate adjustment record.
- Original platform-fee transactions are immutable and are never modified or deleted.

## 2. Phase 13A Scope

Phase 13A is a contracts/catalog foundation only. It should create the canonical commercial billing catalog and core contract types without enabling checkout, subscription webhooks, billing portal, entitlement mutation, trial activation, setup-package purchase, platform-fee charging, or frontend billing screens.

In scope:

- Canonical commercial billing entity models.
- Versioned plan/product/price catalog contracts.
- Monthly and annual billing interval contracts.
- Product and price active/inactive/unavailable rules.
- Integer-cent money storage for commercial prices and fee schedules.
- Immutable published-price rules.
- Separation from EC4 customer invoices/payments.
- Separation from future EC14 Webstore commerce.
- Entitlement derivation contracts with EC2, but no entitlement writes yet.
- Founder tenant migration contract, but no migration execution yet.
- Stripe product/price synchronization boundary contracts, but no outbound Stripe sync yet.
- Permission and tenant-isolation contracts.
- Audit event requirements.
- Required MongoDB indexes.
- Acceptance tests for model invariants and contract boundaries.
- Documentation for catalog/versioning rules.

Out of scope:

- Stripe Checkout Sessions.
- Stripe Billing Portal.
- Stripe webhook processing for subscriptions.
- Trial start/extend/expire behavior.
- Setup-package purchase behavior.
- Commercial billing frontend.
- EC19 onboarding/help work.
- EC14 Webstores implementation.
- EC16 AI gateway/credit ledger/provider cost ledger.
- EC20 platform admin cockpit.
- EC21 public pricing/signup.

## 3. Canonical Entities And Relationships

### CommercialCatalogVersion

Purpose: immutable catalog release marker for commercial products, prices, entitlement mappings, fee schedules, trial rules, and setup packages.

Fields:

- `id`
- `version`
- `status`: `draft`, `published`, `retired`
- `effective_at`
- `retired_at`
- `notes`
- `created_by_user_id`
- `published_by_user_id`
- `published_at`
- `created_at`
- `updated_at`

Relationships:

- One catalog version has many `CommercialProduct`, `CommercialPrice`, `CommercialEntitlementRule`, and `PlatformFeeSchedule` records.
- Published versions are immutable.

### CommercialProduct

Purpose: canonical sellable or future-sellable commercial product contract.

Fields:

- `id`
- `catalog_version_id`
- `product_key`
- `name`
- `description`
- `product_type`: `core`, `bundle`, `addon`, `standalone`, `setup_package`, `credit_pack`, `trial_extension`, `usage_category`
- `status`: `draft`, `active`, `inactive`, `unavailable`, `retired`
- `owner_checkpoint`
- `requires_owner_activation`
- `publishable`
- `stripe_sync_enabled`
- `metadata`
- `created_at`
- `updated_at`

Rules:

- `active` plus at least one active approved price is required before publication or Stripe sync.
- `unavailable` products cannot be published, purchased, or sent to Stripe.
- Smart Pricing may appear only as a future architecture placeholder if needed, with `status=unavailable`, no price, no entitlement rule, and owning checkpoint noted. Prefer omitting it in 13A unless a test requires future-addon support.
- SMS/MMS usage categories may be contract placeholders only, with no price and `status=unavailable`.

### CommercialPrice

Purpose: immutable owner-approved price contract.

Fields:

- `id`
- `catalog_version_id`
- `product_id`
- `price_key`
- `billing_interval`: `none`, `monthly`, `annual`, `one_time`, `usage`
- `currency`
- `amount_cents`
- `is_active`
- `is_public`
- `is_stripe_syncable`
- `stripe_product_id`
- `stripe_price_id`
- `approved_by_owner`
- `approved_at`
- `effective_at`
- `retired_at`
- `created_at`
- `updated_at`

Rules:

- `amount_cents` is integer cents only.
- Published prices are immutable. Revisions create a new price record and retire the old one.
- Unapproved prices cannot be active, public, or Stripe-syncable.
- Standalone monthly/annual prices require explicit owner-approved active prices. No zero-dollar or placeholder price may stand in for unapproved standalone pricing.

### CommercialEntitlementRule

Purpose: contract that maps a product/price/subscription item to EC2 feature entitlements.

Fields:

- `id`
- `catalog_version_id`
- `product_id`
- `feature_key`
- `entitlement_scope`: `plan`, `addon`, `standalone`, `trial`, `setup`, `usage`
- `enabled`
- `quota`
- `quota_interval`: `none`, `monthly`, `annual`, `lifetime`
- `expires_with_subscription`
- `source_priority`
- `created_at`
- `updated_at`

Rules:

- Phase 13A defines rules only. It does not write `feature_entitlements`.
- Ordinary core business records must not be gated by commercial entitlements: customers, quotes, orders, order items, invoices, customer payments, exports, billing, support, privacy, and account recovery remain accessible according to later dunning rules.

### FounderTenantContract

Purpose: per-tenant Founder commercial contract and migration bridge to existing EC12 explicit Founder access.

Fields:

- `id`
- `tenant_id`
- `founder_slot_number`
- `founder_status`: `not_founder`, `pending`, `active`, `grace`, `lost`, `revoked`
- `source`: `manual_owner_decision`, `migration_review`, `subscription_activation`
- `ec12_founder_access_preserved`
- `migration_verified_at`
- `migration_notes`
- `created_by_user_id`
- `created_at`
- `updated_at`

Rules:

- One active Founder contract per tenant.
- Founder is tenant/shop-scoped, never user-scoped.
- Existing EC12 `founder_access` and `users.founder_access` are preserved until migration is implemented and verified.
- Phase 13A defines the contract only. It does not backfill tenants or mutate Founder access.

### PlatformFeeSchedule

Purpose: versioned platform-fee rate contract.

Fields:

- `id`
- `catalog_version_id`
- `fee_key`
- `account_status`: `founder_intro`, `founder_active`, `ga`, `custom`
- `transaction_type`: `standard_customer_payment`, `webstore_sale`
- `rate_basis_points`
- `is_active`
- `effective_at`
- `retired_at`
- `created_at`
- `updated_at`

Rules:

- Fee rates are backend-controlled.
- Fee snapshots/reversals are later-phase transactional records, not Phase 13A active charges.

### PlatformFeeTransactionContract

Purpose: contract for later platform-fee snapshots and reversal records.

Fields:

- `id`
- `tenant_id`
- `source_transaction_type`
- `source_transaction_id`
- `fee_schedule_id`
- `basis_amount_cents`
- `platform_fee_cents`
- `currency`
- `snapshot_rate_basis_points`
- `status`: `assessed`, `reversed`, `partially_reversed`, `adjusted`
- `reversal_of_fee_transaction_id`
- `adjustment_reason`
- `created_by_user_id`
- `created_at`

Rules:

- Original fee transaction is immutable.
- Reversals and manual exceptions are separate records.
- Stripe/provider fees are separate records or fields and are not silently rewritten.

## 4. Lifecycle/Status Contracts

Catalog version:

- `draft`: editable by platform subscription admins.
- `published`: immutable and available for runtime reads.
- `retired`: preserved for historical subscriptions and transactions.

Product:

- `draft`: not runtime visible.
- `active`: eligible for runtime use if prices allow it.
- `inactive`: existing references may remain; new checkout/public use blocked.
- `unavailable`: known future product/category; not sellable, not public, not Stripe-syncable.
- `retired`: historical only.

Price:

- Draft/unpublished prices may be edited.
- Active published prices are immutable.
- Retired prices remain readable for historical records.
- `is_public` and `is_stripe_syncable` require `approved_by_owner=true`.

Founder contract:

- `not_founder`: default/no Founder commercial contract.
- `pending`: tenant is being reviewed/allocated.
- `active`: tenant has active Founder commercial status.
- `grace`: temporary owner-approved exception.
- `lost`: tenant lost Founder commercial status.
- `revoked`: platform-admin revocation with reason.

Platform fee transaction:

- `assessed`: original immutable fee snapshot.
- `reversed`: full proportional reversal exists.
- `partially_reversed`: partial proportional reversal exists.
- `adjusted`: manual exception exists as a separate adjustment.

## 5. Permission Model

Phase 13A should use existing permission names where possible:

- `subscription:read`: tenant owner/admin reads published catalog summaries and own-tenant commercial contract previews when later available.
- `subscription:manage`: not used for mutation in 13A unless a read-only admin preview endpoint needs a future guard. No tenant self-service writes in 13A.
- `platform:subscription_admin`: create/edit draft catalog records, publish catalog version, retire products/prices, define Founder migration contract records if Phase 13A includes admin-only contract seed data.
- `platform:tenant_read`: future read-only platform tenant billing inspection, not required for 13A unless exposing admin reads.

Hard rules:

- Platform permissions never satisfy staff `Perm` checks.
- Staff permissions never satisfy platform-admin catalog mutation checks.
- Customer Portal, Employee Portal, and future Webstore portal tokens must not access EC13 catalog/admin endpoints.
- Frontend role visibility is not authoritative.

## 6. Stripe Boundaries

Phase 13A must not call Stripe.

Allowed:

- Store optional empty `stripe_product_id` and `stripe_price_id` fields for future sync.
- Define `is_stripe_syncable` as false unless owner-approved and active.
- Define sync eligibility rules.
- Document mapping between `CommercialProduct`/`CommercialPrice` and future Stripe Product/Price records.

Forbidden in 13A:

- Creating Stripe Products.
- Creating Stripe Prices.
- Creating Checkout Sessions.
- Creating Billing Portal Sessions.
- Handling subscription webhooks.
- Sending unavailable/unapproved products or prices to Stripe.
- Reusing EC4 customer PaymentIntent code for platform subscriptions.

## 7. Entitlement Boundaries

Phase 13A defines entitlement mapping contracts only.

Allowed:

- Define `CommercialEntitlementRule`.
- Validate feature-key format and rule shape.
- Read current EC2 entitlement keys for consistency if useful.
- Test that no entitlement projection writes occur.

Forbidden:

- Mutating `feature_entitlements`.
- Enabling Webstores, Wrap Lab, AI tools, Smart Pricing, Template Vault, or any add-on through EC13 Phase 13A.
- Gating ordinary core records.
- Implementing EC16 AI credit ledgers or usage enforcement.

## 8. Migration Considerations

- Existing tenants have no billing account or Founder commercial contract.
- Existing EC12 Founder access is user/community scoped; EC13 Founder status is tenant/shop scoped.
- 13A should only define a `FounderTenantContract` shape and migration invariants.
- No backfill should run in 13A.
- A later phase must reconcile tenant Founder contracts against existing `founder_access` rows and user flags, with reports and tests before any access change.
- Existing EC4 customer invoices/payments must remain untouched.
- Existing disabled frontend billing navigation remains disabled until later phases add backend truth and screens.

## 9. Required Indexes

Suggested indexes for Phase 13A:

- `commercial_catalog_versions`: unique `version`; `(status, effective_at)`.
- `commercial_products`: unique `(catalog_version_id, product_key)`; `(status, product_type)`; `(owner_checkpoint, status)`.
- `commercial_prices`: unique `(catalog_version_id, price_key)`; `(product_id, billing_interval, is_active)`; `(stripe_price_id)` sparse unique; `(is_public, is_active)`.
- `commercial_entitlement_rules`: `(catalog_version_id, product_id)`; `(feature_key, enabled)`; unique `(catalog_version_id, product_id, feature_key, entitlement_scope)`.
- `founder_tenant_contracts`: unique `(tenant_id, founder_status)` partial for active/pending/grace statuses; unique `founder_slot_number` sparse; `(tenant_id, created_at)`.
- `platform_fee_schedules`: unique `(catalog_version_id, fee_key)`; `(account_status, transaction_type, is_active)`.
- Future `platform_fee_transactions`: `(tenant_id, source_transaction_type, source_transaction_id)`; `(reversal_of_fee_transaction_id)`; not necessarily created in 13A unless contract model lands.

## 10. Required Tests

Phase 13A backend tests:

- Catalog version can be drafted and published by platform subscription admin only.
- Published catalog version is immutable.
- Product key is unique within a catalog version.
- Product lifecycle prevents unavailable products from being public or Stripe-syncable.
- Commercial prices require integer `amount_cents`.
- Active/public/Stripe-syncable price requires owner approval.
- Published price cannot be edited; price revision creates a separate record.
- Monthly and annual billing intervals validate.
- Unapproved standalone prices cannot be created as active/public/Stripe-syncable.
- Unavailable products cannot have active Stripe-syncable prices.
- Smart Pricing is not seeded as a paid add-on.
- SMS/MMS has no final seeded price; any usage category is unavailable/unpriced.
- EC4 `invoices` and `payments` collections are not mutated.
- `feature_entitlements` collection is not mutated.
- Founder contract is tenant-scoped and rejects user-scoped Founder status.
- Founder contract does not mutate EC12 `founder_access` or `users.founder_access`.
- Platform-fee reversal contract preserves immutable original fee transaction semantics.
- Portal tokens are denied from any EC13 route introduced.
- Tenant isolation is enforced on every tenant-scoped commercial contract.
- Audit events are written for catalog publish/retire and platform-admin changes.

Documentation/test guard:

- Add a test or static assertion that `CommercialPrice` money fields use `_cents`.
- Add regression assertion that no new EC19 onboarding routes/models are introduced in 13A.

## 11. Exact Files Expected To Change

Likely create:

- `backend/app/models/commercial_catalog.py`
- `backend/app/services/commercial_catalog.py`
- `backend/app/routers/commercial_catalog.py` or `backend/app/routers/billing_catalog.py`
- `backend/tests/test_ec13_phase13a_commercial_catalog.py`
- `docs/commercial/ec13_commercial_catalog_contracts.md`
- `evidence/EC13_PHASE13A_COMPLETION_REPORT.md` only after implementation/validation, not during planning.

Likely modify:

- `backend/app/core/db.py` for indexes.
- `backend/server.py` to register the 13A router.
- `backend/app/core/permissions.py` only if the existing reserved permissions are insufficient.
- `memory/MASTER_CHECKPOINT_CHECKLIST.md` only at phase completion.
- `memory/progress_register.md` only at phase completion.
- `memory/checkpoint_reference_table.md` only at phase completion if status changes.

Do not modify in 13A:

- `backend/app/models/invoice.py`
- `backend/app/models/payment.py`
- `backend/app/services/payment_service.py`
- `backend/app/routers/payments.py`
- `backend/app/routers/webhooks_stripe.py` unless a no-op separation constant is strictly needed, which should be avoided in 13A.
- `frontend/src/portal/*`
- EC19 onboarding/help files.

## 12. Risks And Open Questions

Risks:

- Accidentally making unapproved standalone products look purchasable.
- Treating provisional prices as active publishable prices.
- Collapsing tenant-level Founder commercial status into user-level Founder access.
- Adding entitlement writes before catalog contracts are stable.
- Reusing EC4 customer payment semantics for platform subscriptions.
- Creating too much Stripe implementation in a contracts-only phase.
- Over-modeling future add-ons beyond what EC13 needs.

Open questions for later phases, not blockers for 13A:

- Which products/prices should be initially active in the first published catalog version.
- Whether Stripe product/price IDs are manually entered after dashboard setup or created by an automated sync in a later phase.
- Exact tax treatment for SignGuy subscription/setup charges.
- Exact proration policy for upgrades/downgrades.
- Exact catalog publication workflow UI, if any, for platform admins.

## 13. Confirmation No Implementation Occurred

Confirmed. This document is a Phase 13A implementation plan only. No backend models, services, routers, indexes, tests, frontend screens, Stripe synchronization, entitlement writes, Founder migration, platform-fee transactions, EC13 implementation phase, or EC19 work was performed.
