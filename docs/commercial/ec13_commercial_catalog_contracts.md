# EC13 Phase 13A Commercial Billing Catalog Contracts

**Status:** Phase 13A complete; GitHub CI passed in run `29637493631`.
**Scope:** Phase 13A only.

## Boundary

Phase 13A defines the backend commercial billing catalog and core commercial contracts. It does not start Checkout Sessions, subscriptions, Billing Portal sessions, Stripe webhooks, trials, setup-package purchases, AI credits, EC4 customer invoice/payment changes, Webstore payout changes, entitlement mutations, or EC19 work.

## Entities

- `CommercialCatalogVersion`: versioned catalog release marker with `draft`, `published`, and `retired` status.
- `CommercialProduct`: commercial product contract for core plans, bundles, add-ons, standalone products, setup packages, credit packs, trial extensions, and usage categories.
- `CommercialPrice`: integer-cent price contract with monthly, annual, one-time, usage, and none intervals.
- `CommercialEntitlementRule`: mapping contract from commercial products to future EC2 entitlement derivation.
- `FounderTenantContract`: tenant/shop-scoped Founder contract for the first 25 signed shops.
- `PlatformFeeSchedule`: catalog-versioned platform-fee rate contract.
- `PlatformFeeTransactionContract`: append-only platform-fee assessment, reversal, and adjustment contract.

## Lifecycle Rules

- Only draft catalog versions may be changed.
- Publishing a catalog version locks the catalog and its existing prices.
- Active publishable products require at least one active owner-approved price before catalog publication.
- Inactive, unavailable, and retired products are not purchasable.
- Unavailable products cannot be public, purchasable, or Stripe-syncable.
- Active, public, or Stripe-syncable prices require `approved_by_owner=true`.
- Published prices cannot be edited; draft price revisions create a separate price record.
- Standalone monthly or annual prices must be non-zero owner-approved prices.

## Money Rules

All commercial money fields use integer cents:

- `amount_cents`
- `basis_amount_cents`
- `platform_fee_cents`
- `provider_fee_cents`

No floating-point commercial money fields are introduced in Phase 13A.

## Permission Rules

- Catalog, product, price, entitlement-rule, Founder-contract, and platform-fee mutations require platform-admin/platform-subscription-admin authority.
- Tenant owners/admins may read subscription catalog views through existing `subscription:read`.
- Portal tokens are rejected by the existing staff-route auth dependency.
- Founder commercial status is tenant/shop-scoped, not user-scoped.
- Non-platform users cannot query another tenant's Founder contracts.

## Stripe Boundary

Phase 13A stores future Stripe reference fields only:

- `stripe_product_id`
- `stripe_price_id`
- `is_stripe_syncable`

The implementation does not import Stripe, call Stripe APIs, publish Stripe products/prices, create Checkout Sessions, create Billing Portal Sessions, or process subscription webhooks.

## Entitlement Boundary

`CommercialEntitlementRule` defines future entitlement derivation contracts only. Phase 13A does not insert, update, or delete `feature_entitlements`.

## Founder Migration Boundary

`FounderTenantContract` records the future tenant-scoped commercial contract. It preserves existing EC12 explicit Founder access and does not mutate `founder_access` or `users.founder_access`.

## Platform-Fee Refund Boundary

Original platform-fee transaction contracts are immutable. Full refunds create full proportional reversal records, partial refunds create partial proportional reversal records, and manual exceptions create separate adjustment records with a required reason. Provider fees are stored separately and are not silently rewritten.

## Indexes

Phase 13A adds indexes for:

- Catalog version identity and status/effective lookup.
- Product uniqueness per catalog version and lifecycle lookup.
- Price uniqueness per catalog version, product/interval lookup, sparse Stripe price uniqueness, and public-active lookup.
- Entitlement-rule uniqueness per catalog/product/feature/scope.
- One active-style Founder contract per tenant and unique Founder slot numbers.
- Platform-fee schedule uniqueness per catalog version.
- Platform-fee transaction source and reversal lookup.
