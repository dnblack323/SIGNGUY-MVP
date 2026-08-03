# Webstores Stage 7: Stripe Connect and Verified Commerce

Status: Stage 7 implementation complete locally on `feature/webstores-stage-7-stripe-commerce`; commit/push pending separate instruction

Stage 6 is complete locally through the public Webstore storefront, server-priced cart quotes, and payment-gated checkout. Stage 7 enables verified provider commerce without starting the Stage 8 Orders, Production, reports, or relaunch work.

Implemented in this slice: the Stripe Connect adapter, tenant-scoped onboarding/status persistence, server-priced Checkout Session creation with idempotent replay, signed webhook normalization, unpaid Checkout Session protection, failure-safe signed pending/failed/canceled/expired payment-event recording, provider-authoritative payment verification held for the Stage 8 handoff, strict connected-account and Webstore-to-purchase matching, provider refund execution and authority-checked idempotent signed refund-event reconciliation with sanitized evidence retained in the existing activity/audit path, signed transfer/payout/dispute normalization with sanitized evidence retained in the existing activity/audit path, and the staff/public checkout UI boundaries. Events still require an existing canonical paid payment before ledger reconciliation; no Orders or Production creation is activated here.

## Reuse decisions

### Reuse from the current MVP

The current MVP is the implementation authority. Stage 7 will extend these existing contracts in place:

- `backend/app/services/webstore_payment_provider.py` for the single provider adapter boundary and typed provider authority.
- `backend/app/services/webstore_stripe_connect.py` for compatibility exports and the stable service seam.
- `backend/app/services/webstores.py` for immutable server-priced purchase intents and public cart validation.
- `backend/app/services/webstore_payments.py` for verified event idempotency, payment-event records, refund/reconciliation helpers, and the Webstore ledger.
- `backend/app/routers/webhooks_webstore.py` for the provider-event boundary.
- `backend/app/models/webstore.py`, `backend/app/models/payment.py`, and existing tenant-scoped indexes for canonical records.
- Existing Webstore owner portal assignments, notifications, permissions, and payment-readiness responses.

No second payment, checkout, order, ledger, or permission system will be introduced.

### Read-only donor references

- `C:\Users\thesi\Documents\GitHub\signguyai\backend\\routes\\stripe_connect.py`, `backend\\services\\stripe_service.py`, and `backend\\routes\\webstore_owners.py` are UX and provider-naming references only. They use retired `webstores_v2` records, legacy payout counters, and legacy order flows, so their code will not be copied.
- `C:\Users\thesi\Documents\GitHub\signguyai_rebuild_version` has generic order services but no authoritative Webstore Stripe Connect implementation. Its generic order code will not be imported into this Webstore stage.
- Donor questionnaire and owner-portal wording may inform copy only. The MVP shared Form Maker, Webstore adapter, tenant permissions, and portal records remain canonical.

## Stage 7 sequence

### 7A. Provider configuration and Connect readiness

- Add the real provider adapter behind the existing `WebstorePaymentProvider` protocol.
- Implement Connect onboarding-link creation and refresh behavior.
- Retrieve connected-account status from the provider and persist only the minimum tenant/Webstore-scoped provider references and verification state.
- Derive readiness from provider-authoritative charges, payouts, requirements, mode, account reference, and webhook verification.
- Keep secrets backend-only and fail closed when configuration, verification, or callback URLs are incomplete.

### 7B. Verified checkout session

- Keep server-priced cart quotes as the only source for totals.
- Create provider checkout sessions only from a fresh, validated purchase-intent snapshot.
- Require idempotency for checkout-session creation and replay the existing intent/session safely.
- Never accept client-supplied totals, fees, tax, shipping, donation, or payout values as authority.
- Do not create a canonical Payment, Order, or Work Order from a browser redirect.

### 7C. Webhook verification and payment reconciliation

- Verify the provider signature before parsing or mutating records.
- Require provider authority to match the Webstore, mode, connected account, currency, amount, and purchase intent.
- Reconcile duplicate, delayed, failed, canceled, and out-of-order provider events without double payment or double ledger rows.
- Preserve failed financial events and raw provider evidence for audit review.
- Record the verified payment and Webstore ledger effects through existing services.

### 7D. Refunds and provider financial events

- Add provider-authoritative refund execution and reconciliation through the existing typed refund contract.
- Record reversals as append-only ledger entries; never delete the original payment or ledger history.
- Reconcile transfers, payouts, and disputes as provider events with idempotency and account/mode checks.
- Keep reports read-only until Stage 8 explicitly connects them to the completed commerce records.

## Explicit Stage 8 boundary

Stage 7 will not build or activate:

- Webstore Orders UI or new order models.
- Quote-to-Order or purchase-to-Work-Order conversion changes.
- Production integration, inventory, fulfillment operations, or employee production screens.
- Post-launch reports, payout dashboards, or relaunch behavior.
- A second checkout route, local test-provider route outside development, or legacy `webstores_v2` migration.

## Required invariants

- Tenant isolation applies to Connect records, purchase intents, checkout sessions, provider events, payments, refunds, and ledger entries.
- Provider authority is backend-only and never trusted from browser payloads.
- A successful redirect is not payment evidence; only a verified provider event is authoritative.
- Every provider mutation has an idempotency key and a durable audit record.
- Amount and currency mismatches fail closed.
- Existing Stage 6 storefront/cart behavior remains available when provider authority is absent, but checkout remains visibly unavailable.

## Focused verification

Only focused tests will be run for Stage 7:

- Connect onboarding/status and readiness transitions.
- Provider configuration and secret/callback guards.
- Checkout-session idempotency and server-total authority.
- Webhook signature, tenant, account, mode, amount, and currency validation.
- Duplicate/out-of-order/failure-safe payment reconciliation.
- Refund and payout/dispute reconciliation with immutable ledger history.
- Stage 6 regression checks for the public storefront and payment-gated cart.

No full repository suite will be run unless separately requested.
