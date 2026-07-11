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

## Security notes

- Stripe publishable key + PaymentIntent `client_secret` MUST NOT appear in the DOM, console, toasts, error messages, screenshots, or persistent storage. Held only in React state closures and passed internally to Stripe Elements (or a safe dev-mode simulate button gated by AUTH_DEV_BYPASS).
- Payment `stripe_payment_intent_id` is masked to `Stripe ····<last4>` in visible rows.
- All Stripe API errors (`stripe.error.StripeError` family) are caught in `payment_service.initiate_stripe` and `payment_service.initiate_refund`, re-raised as `ValueError("stripe_error:<user_message>")`, and translated by the router to HTTP 400 — never bubble as 500.
- Dev-simulated payments (via `/api/payments/{id}/dev-simulate-confirm`, gated by AUTH_DEV_BYPASS) carry `dev_simulated=true`. Refunds on dev-simulated payments short-circuit without touching Stripe.
- Server-side dedup on `POST /api/invoices/{id}/stripe-intents` reuses any existing pending Stripe payment for the same `(invoice_id, amount_cents)` tuple.
