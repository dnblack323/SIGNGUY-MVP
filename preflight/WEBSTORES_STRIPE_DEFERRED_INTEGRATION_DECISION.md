# Webstores Stripe Deferred Integration Decision

Status: Owner-authorized foundation decision, 2026-08-01.

## Why live Stripe is deferred

The owner decided that real Stripe integration will be completed later by Emergent after the application is otherwise complete. This correction therefore prepares the application for Stripe without requiring credentials, making provider calls, moving money, or pretending that test checkout is operational.

## Established decisions

- Webstore Owners or clients will eventually receive their appropriate share through Stripe Connect.
- The sign shop must not become an informal payment middleman.
- SignGuy AI must not invent or maintain a private stored-money balance.
- Buyer totals, discounts, donations, taxes, fulfillment, production allocation, owner/fundraiser share, SignGuy fee, processor fee evidence, refunds, and payout/transfer allocations remain explicit immutable integer-cent snapshots.
- The version-one SignGuy transaction-fee default is 0%.
- Optional shop-created Webstore management fees remain separate from SignGuy platform fees.
- Provider-specific readiness must be authoritative; stored database flags cannot make a Webstore payment-ready.

## Decisions intentionally deferred

The following remain owner/architecture decisions for the later Stripe integration:

- Direct charges versus destination charges versus separate charges and transfers.
- Merchant of record.
- Connected account receiving the buyer payment.
- Sign-shop production allocation route.
- Owner/fundraiser share route.
- Platform fee collection route.
- Responsibility for refunds, disputes, chargebacks, taxes, negative balances, and reversals.
- Whether payouts are solely Stripe-controlled or whether any platform-initiated transfer is authorized.

No code in this foundation selects or implies one of those routes.

## Authorized implementation

This correction may implement:

- One typed payment-provider boundary.
- A disabled provider implementation returning `PAYMENT_PROVIDER_NOT_CONFIGURED`.
- Configuration placeholders and validation.
- Provider/readiness/checkout-attempt/reconciliation fields on existing Webstore records.
- Safe launch and checkout gates.
- Staff-visible provider status and prepared controls that fail safely.
- Integer-cent allocation snapshot contracts without account routing.
- Regression tests and an exact Emergent handoff.

## Never report real readiness

`stripe_payment_ready`, `payment_readiness_status`, connected-account references, or any other stored field cannot independently make a Webstore ready. With `STRIPE_ENABLED=false`, an incomplete configuration, a deferred charge model, or no provider adapter, readiness is false, public checkout is unavailable, and live/launch-ready transitions are blocked.

The foundation must never report production payments operational, create a fake successful payment, create a canonical paid Order from a browser redirect, or accept the development harness as production authority.

## Emergent responsibility

Emergent must implement the approved Stripe adapter behind the existing provider interface, add raw-body signed webhook verification, retrieve provider state, reconcile tenant/store/account/mode/amount/currency/metadata, implement idempotent Checkout Sessions and refunds, reconcile payout/transfer/dispute events, complete durable canonical conversion and recovery, and run the separate connected acceptance process in Stripe test mode before any live credentials are permitted.

## Acceptance boundary

Batch 3 cannot be called production-commerce complete until the later Stripe integration passes separate acceptance. The valid foundation completion statement is:

`WEBSTORES STRIPE-READY FOUNDATION COMPLETE - LIVE STRIPE INTEGRATION DEFERRED`
