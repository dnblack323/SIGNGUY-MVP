# Payment Security (EC4)

## Server is authoritative for every commerce amount

- `amount_cents` for PaymentIntent creation is derived on the server from `Invoice.balance_due_cents`. The client cannot send `total`, `paid_cents`, `tenant_id`, or `invoice_total`.
- Backend re-runs `reconcile()` inside the write path before recording a payment.

## Never trust the redirect

- The frontend never marks a Stripe payment successful. Only the Stripe-signed webhook may flip an internal Payment from `pending` → `confirmed`.

## Signature verification

- Every Stripe webhook must be verified via `stripe.Webhook.construct_event(payload, signature, STRIPE_WEBHOOK_SECRET)`. Invalid signature → 401. Missing secret → route returns 404 (fail-closed).

## Replay + race safety

- `webhook_events` collection enforces unique `(provider, provider_event_id)`.
- Manual-payment idempotency uses `(tenant_id, invoice_id, idempotency_key)` unique partial index.
- Overpayment race: after insert we re-derive balance and roll back if net went negative.

## Tenant + permission isolation

- Every endpoint requires the corresponding EC1 `Perm` (`payment:read/write/void/refund`, `invoice:read/write/send/void`).
- All queries scoped by `tenant_id`.
- Refund + payment-void are NOT included in the default `STAFF_PERMS` role — they must be granted explicitly.

## Never expose secrets

- Publishable key is optional (`STRIPE_PUBLISHABLE_KEY`). Secret key is never returned to the client.
- `client_secret` is returned only to authenticated internal callers for the internal test PaymentIntent flow. EC6 will introduce the scoped portal-token path for customer-facing links.
