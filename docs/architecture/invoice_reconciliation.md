# Invoice Reconciliation Service (EC4)

`backend/app/services/invoice_reconciliation.py::reconcile(tenant_id, invoice_id)`.

## Contract

Recomputes and stores:
- `amount_paid_cents` — sum of `confirmed` payments where `refund_of_payment_id is null`.
- `amount_refunded_cents` — sum of `confirmed` payments where `refund_of_payment_id` is set.
- `balance_due_cents` — `max(0, total - (paid - refunded))`.
- `financial_status`.

## Rules

- Only `confirmed` payments count toward `paid`.
- Only `confirmed` refund rows contribute to `refunded`.
- `pending`, `failed`, `voided` payments are excluded.
- Reconciliation runs after every payment insert / confirmation / void / refund event (both manual + Stripe webhook).
- Repeated calls are safe: same input state → same output.

## Overpayment safety

`payment_service.record_manual` re-runs reconciliation after insert. If the newly-derived balance goes negative (a concurrent write pushed us over), the newly-inserted payment is rolled back with `overpayment_rejected`.
