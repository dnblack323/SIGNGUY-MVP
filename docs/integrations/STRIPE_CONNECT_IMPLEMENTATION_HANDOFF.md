# Webstores Stripe Connect Implementation Handoff

## Scope

This document hands the Webstores Stripe-ready foundation to Emergent. The current MVP branch contains no live Stripe provider adapter and makes no Stripe API calls. The charge model is explicitly deferred.

## Provider boundary

Implement the adapter behind:

- `backend/app/services/webstore_payment_provider.py`
- `WebstorePaymentProvider`
- `ProviderResult`
- `get_webstore_payment_provider()`

Required operations are already named in the protocol:

- `create_connected_account_onboarding_link`
- `retrieve_connected_account_status`
- `synchronize_payment_readiness`
- `create_checkout_session`
- `retrieve_checkout_session`
- `verify_payment`
- `verify_webhook_signature_and_parse`
- `create_refund`
- `retrieve_refund`
- `retrieve_transfer_or_payout`
- `retrieve_dispute`
- `reconcile_provider_event`

The disabled implementation is `NotConfiguredWebstorePaymentProvider`. It must remain the safe default until the adapter is complete.

## Configuration

The accepted placeholders are in `.env.example`:

```text
STRIPE_ENABLED=false
STRIPE_MODE=test
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_CONNECT_CLIENT_ID=
STRIPE_CONNECT_RETURN_URL=
STRIPE_CONNECT_REFRESH_URL=
STRIPE_CHECKOUT_SUCCESS_URL=
STRIPE_CHECKOUT_CANCEL_URL=
STRIPE_CONNECT_CHARGE_MODEL=deferred
```

Application parsing is in `backend/app/core/config.py`. Validation is in `backend/app/core/security_guards.py` via `collect_webstore_stripe_violations`. Enabling the integration must fail closed when credentials, Connect client ID, webhook verification, callback URLs, mode, or an approved charge model are missing or inconsistent. The deferred charge model is never valid for provider authority.

No secret may be serialized to frontend data, API responses, logs, audit metadata, documents, screenshots, or error messages.

## Existing persistence

Additive model fields are in `backend/app/models/webstore.py`:

- `Webstore`: provider name/mode, connected-account reference, onboarding state, charges/payouts capability, requirements, restriction state, verification time, and readiness source.
- `WebstorePurchaseIntent`: checkout attempt identity/state, expected amount/currency, provider references, reconciliation, processing, and recovery state.
- `WebstorePaymentEvent`: provider mode/account reference, reconciliation state, quarantine reason, and processing state.
- `WebstorePurchaseIntent`: payout/dispute provider-event sequence markers for out-of-order protection.
- `WebstoreLedgerEntry`: allowlisted provider event type, mode, account, payment reference, and sequence fields; no raw provider payload.
- `WebstoreStripeConnectRecord`: provider mode/account/onboarding/capability state, expected amounts, provider references, reconciliation, recovery, and allocation snapshot.

These fields are preparation only. A stored value cannot establish provider readiness. No destructive migration or applied migration edit is required by this foundation.

## Checkout contract

The public routes remain:

- `POST /api/public/webstores/{slug}/cart-quote`
- `POST /api/public/webstores/{slug}/purchase-intents`
- Compatibility route: `POST /api/public/webstores/{slug}/buyer-orders`

`backend/app/services/webstores.py:create_purchase_intent` must revalidate the complete cart before calling `provider.create_checkout_session`. It must reject browser-supplied money fields, use integer cents, snapshot the resolved cart, and use an idempotency key. It must return only safe redirect information after the adapter exists.

In the current foundation, the provider boundary is unavailable and the endpoint returns HTTP 503 with `payment_provider_not_configured` before looking up or writing a purchase intent. It must not create a local checkout ID, Payment, Order, ledger entry, or Production record.

## Webhook contract

The existing development route is:

- `POST /api/webhooks/webstores/test-provider`

It remains a restricted development harness only and cannot be production authority. Emergent must add the real provider route with:

- raw request body preservation;
- provider signature verification before parsing;
- provider and event ID idempotency;
- mode/account/tenant/store/purchase-intent/amount/currency reconciliation;
- provider state retrieval;
- quarantine for mismatches;
- out-of-order and retry-safe processing;
- no raw provider payload exposure;
- no success-page or browser-redirect payment mutation.

`backend/app/services/webstore_payments.py:process_verified_payment_event` is the canonical conversion entrypoint. It accepts raw event dictionaries only at the future adapter boundary; internal conversion tests use `VerifiedProviderPayment` plus `ProviderAuthority`. The current foundation rejects unconfigured events before lookup or mutation. Do not remove canonical Customer, Order, Order Item, Payment, ledger, notification, email, or Production reuse. Raw event payloads are not persisted.

## Canonical conversion

The eventual verified event workflow must create or match one canonical Customer, one canonical Payment, one canonical Order, canonical Order Items with immutable pricing/allocation snapshots, one inventory mutation, eligible Production handoff, deduplicated notifications/email activity, and buyer confirmation. Use durable processing/recovery state and unique reconciliation keys. Mark the provider event processed only after conversion completes or is durably scheduled for retry.

## Refunds and lifecycle events

The canonical refund entrypoint is:

- `backend/app/services/webstores.py:refund_webstore_payment`
- `backend/app/services/webstore_payments.py:initiate_webstore_refund`

Refund orchestration calls `WebstorePaymentProvider.create_refund`, reconciles the typed allowlisted `ProviderRefund`, then calls EC4 `payment_service.record_provider_refund` to create the canonical refund Payment exactly once. The unconfigured provider returns `PAYMENT_PROVIDER_NOT_CONFIGURED` before mutation. Payout/transfer/dispute states enter through `reconcile_webstore_financial_event` after adapter reconciliation; the former staff-supplied `/payout-events` and `/dispute-events` routes are absent so raw status, amount, and provider IDs cannot establish truth. Duplicate event IDs replay idempotently, conflicting duplicates reject, and out-of-order events reject without overwriting newer state.

## Readiness and launch gates

Readiness is exposed through:

- `GET /api/webstores/{webstore_id}/payment-provider`
- `GET /api/webstores/{webstore_id}/launch-readiness`

The status labels are `Not configured`, `Test configuration incomplete`, `Connected — verification required`, `Restricted`, `Ready for test checkout`, and `Live ready`. Backend state mapping lives in `provider_configuration_status`; only typed provider-authoritative status can reach the connected/restricted/ready mappings. The current disabled foundation reaches only `Not configured` by default. Deferred charge model, incomplete configuration, missing verification, and stored flags cannot reach either ready state. `launch_readiness` ignores stored readiness flags and blocks `launch_ready`, `scheduled`, and `live` while provider authority is absent.

Public serialization in `backend/app/services/webstores.py` also forces `checkout_enabled=false` unless provider authority is available.

## Frontend integration points

- API helpers: `frontend/src/lib/webstores.js`.
- Staff status and prepared controls: `frontend/src/pages/WebstoreDetailPage.jsx`.
- Public checkout continues to fail closed through the backend; frontend must never calculate authoritative totals or call privileged provider APIs.

Controls for Connect, resume onboarding, refresh, requirements, and disconnect are status/action placeholders. They must show the safe provider error while disabled and never claim onboarding completion. Frontend code displays the backend status and does not calculate readiness.

## Money and charge-model boundary

Keep all amounts as integer cents and preserve immutable snapshots for buyer total, subtotal, discount, donation, tax, fulfillment, production allocation, owner/fundraiser share, SignGuy platform fee, processor fee evidence, refund allocation, and transfer/payout allocation. Do not encode which Stripe account receives any allocation until the charge model is approved. The version-one SignGuy transaction-fee default is 0%; shop-created management fees remain separate.

## Expected provider event categories

The adapter must cover connected-account updates, Checkout Session/payment success and failure, refund updates, transfer/payout updates, dispute lifecycle updates, and reconciliation/missed-event recovery. Map only safe fields into the existing models; do not persist unrestricted provider payloads.

## Test fixtures and commands

Provider tests use typed `ProviderAuthority`, `VerifiedProviderPayment`, `ProviderRefund`, and `ProviderFinancialEvent` fixtures or a mocked provider client behind this boundary. They must not add production-route bypasses or fake paid state. Required checks include configuration fail-closed behavior, stored-flag rejection, idempotency, tenant/store/account/mode/amount/currency mismatch, signature failures, conflict rejection, out-of-order rejection, canonical conversion recovery, refund lifecycle, privacy, permissions, and existing non-Webstore regressions.

Focused backend command:

```text
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_webstores_stripe_ready_foundation.py backend\tests\test_webstores_stage1_foundation.py backend\tests\test_webstores_stage2_setup.py backend\tests\test_webstores_stage3_branding.py backend\tests\test_webstores_stage4a_product_foundation.py backend\tests\test_webstores_stage4b_owner_approval.py backend\tests\test_ec14_webstores.py -q
```

Frontend Webstores command:

```text
cd frontend
C:\Users\thesi\AppData\Roaming\npm\yarn.cmd test --watchAll=false WebstoresStage1.test.jsx WebstoresStage3Branding.test.jsx WebstoresStage4AProductFoundation.test.jsx
```

Before live credentials are permitted, complete the full backend suite, frontend suite/build, migration/index checks, provider test-mode acceptance, and the separate 80-check connected browser acceptance. This foundation is not a production-commerce acceptance.

## Exact remaining TODO markers

1. Implement the approved Stripe adapter in `backend/app/services/webstore_payment_provider.py`.
2. Record the owner-approved charge model and liability decisions.
3. Add production signed webhook route and event mapping.
4. Add provider-authoritative account onboarding/status synchronization.
5. Complete checkout session creation/retrieval and redirect handling.
6. Complete durable payment-to-canonical-commerce recovery.
7. Complete provider refunds, transfers/payouts, disputes, and allocation reversals.
8. Run Stripe test mode and all provider-dependent browser checks.
9. Permit live credentials only after separate acceptance.
