# Payments Module (EC4)

**Owner checkpoint:** EC4.

## Model

`backend/app/models/payment.py::Payment`. One collection for **all** customer payments — manual + Stripe.

- `source`: `manual | stripe`
- `status`: `pending | confirmed | failed | voided | refunded | partially_refunded`
- Stripe fields: `stripe_payment_intent_id`, `stripe_charge_id`, `stripe_refund_id`, `provider_event_id`
- Void: `voided_at, voided_by, void_reason`
- Refund linkage: `refund_of_payment_id, refund_reason, refunded_at`
- Idempotency: `idempotency_key` unique per `(tenant_id, invoice_id, idempotency_key)`

## Endpoints

- `POST /api/invoices/{id}/manual-payments` — record manual payment (Idempotency-Key supported).
- `POST /api/payments/{id}/void` — void a manual, confirmed payment (reason required).
- `POST /api/invoices/{id}/stripe-intents` — server-initiated PaymentIntent (test-mode).
- `POST /api/payments/{id}/refund` — server-initiated Stripe refund (reason required).
- `GET /api/invoices/{id}/payment-history` — full history + reconciled totals.

## Rules

- Amount must be positive.
- Overpayment rejected server-side (re-checked race-safely inside the write).
- Stripe payments cannot be manually voided (issue a refund instead).
- Refunds only for Stripe payments in `confirmed` state.
- Reconciliation runs on every write / webhook event.
