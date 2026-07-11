# Manual Payment Voids (EC4)

## Endpoint

`POST /api/payments/{id}/void` — requires `payment:void` staff permission and JSON body `{ "reason": "..." }`.

## Rules

- Only `source == "manual"` AND `status == "confirmed"` may be voided.
- Stripe payments are rejected with `stripe_payments_cannot_be_manually_voided` — the operator must issue a refund instead.
- Void reason is required (empty string → 400).
- Original payment record is preserved; only `status`, `voided_at`, `voided_by`, `void_reason` are updated.
- Reconciliation runs immediately.
- Double-void is rejected.
- Audit event `payment_voided_manual` is written.
