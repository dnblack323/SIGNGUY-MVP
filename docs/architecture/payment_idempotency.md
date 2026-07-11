# Payment Idempotency (EC4)

## Manual payments

- Optional client `Idempotency-Key` header. When supplied, a repeat request with the same key returns the previously created row (`already_exists: true`).
- Unique partial index: `(tenant_id, invoice_id, idempotency_key)` with `idempotency_key` a string.
- DuplicateKeyError on race is caught and re-fetched.

## Stripe payment initiation

- Server generates an idempotency key `pi:{invoice_id}:{amount_cents}:{uuid}` unless the client supplies `Idempotency-Key`.
- Key is passed to Stripe's `PaymentIntent.create(idempotency_key=…)`.
- Also stored on our internal Payment row (unique index).

## Webhooks

- Every event lands in the EC2 `webhook_events` collection with unique `(provider, provider_event_id)`.
- Duplicates are marked `duplicate` and become no-ops.
- Handler functions (`confirm_stripe_from_webhook` etc.) also check target row state before mutating — so out-of-order or replayed events won't downgrade a `confirmed` payment.
