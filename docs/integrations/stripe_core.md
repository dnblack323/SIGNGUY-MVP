# Stripe Core (EC4)

## Configuration

- `STRIPE_API_KEY` (env). Test mode defaults to `sk_test_emergent`.
- `STRIPE_PUBLISHABLE_KEY` (env, optional) — surfaced to the frontend when initiating a PaymentIntent.
- `STRIPE_WRITES_ENABLED` — must be `true` to allow server-side PaymentIntent + Refund creation.
- `STRIPE_WEBHOOK_ENABLED` + `STRIPE_WEBHOOK_SECRET` — required to enable the webhook route.

## Flow (server-initiated PaymentIntent)

1. Frontend POSTs `/api/invoices/{id}/stripe-intents` with `{amount_cents}` and (optionally) `Idempotency-Key`.
2. Backend re-derives `balance_due_cents` and rejects overpayment.
3. A pending internal `Payment` row is inserted (`source=stripe, status=pending`).
4. `stripe.PaymentIntent.create` is called with:
   - `amount` = the same server-derived cents,
   - `currency` = "usd",
   - `metadata` = `{tenant_id, invoice_id, internal_payment_id, app}`,
   - `idempotency_key` = the internal key,
   - `automatic_payment_methods` = enabled.
5. Backend returns `{payment_id, client_secret, status: pending, publishable_key}`.
6. Frontend confirms with Stripe Elements. **Redirect success is NOT authoritative** — the internal Payment stays `pending` until…
7. Stripe fires `payment_intent.succeeded` → webhook confirms internally and reconciles the Invoice.

## Refunds

`POST /api/payments/{id}/refund` → `stripe.Refund.create(payment_intent=…, amount=…, idempotency_key=…)`. A pending refund `Payment` row is inserted with `refund_of_payment_id` = the source. `charge.refunded` webhook finalizes.
