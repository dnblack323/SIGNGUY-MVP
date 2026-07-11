# Invoice Dual Status (EC4)

Invoice state is split into two independent fields:

- **document_status** — controls the invoice document lifecycle.
  - `draft` — the invoice can be edited.
  - `issued` — customer-visible commercial terms are frozen; the row is read-only except via a controlled correction path.
  - `void` — the invoice is voided (never deleted).
- **financial_status** — describes the money reality. Derived by `services/invoice_reconciliation.reconcile` from the `payments` collection.
  - `unpaid` — no confirmed payments.
  - `partial` — some confirmed net payment but less than total.
  - `paid` — net confirmed payment ≥ total.
  - `refunded` — refunds reduce net paid to zero.
  - `voided` — document is void.

## Rules

- Financial status can NEVER be mutated directly. The `/status` endpoint accepts only `document_status`.
- Direct `paid` requests are rejected with `422`.
- Issuing an invoice never marks it paid.
- Recording a payment never automatically issues a draft invoice.
- Voiding an invoice is blocked while net confirmed payments remain — refund or void manual payments first.
- Reconciliation is idempotent: safe to run repeatedly.

## Legacy compat

Existing invoices without the new fields are read via helpers:
- `document_status` derived from `status`: `void → void`, `draft → draft`, everything else → `issued`.
- `financial_status` derived live by `reconcile()`.
- Legacy single `status` field remains as a mirror ONLY for backwards-compatible reads.
