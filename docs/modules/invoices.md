# Invoices Module (EC4)

**Owner checkpoint:** EC4.

## Model

`backend/app/models/invoice.py::Invoice`. Two independent status fields:

- **document_status** — `draft, issued, void`
- **financial_status** — `unpaid, partial, paid, refunded, voided` (backend-derived by `services/invoice_reconciliation.reconcile`)

The legacy single `status` field is retained ONLY as a compatibility mirror for older code; router endpoints no longer accept it.

## Money (integer cents)

`subtotal_cents, discount_cents, tax_cents, fee_cents, total_cents, amount_paid_cents, amount_refunded_cents, balance_due_cents`.

Backend-derived; never trust client-supplied values.

## Endpoints

- `GET /api/invoices`
- `POST /api/invoices`
- `GET /api/invoices/{id}` → `{ invoice, payments }`
- `PATCH /api/invoices/{id}` (draft only)
- `POST /api/invoices/{id}/status` (accepts `{ document_status, reason? }`; direct `paid` mutation rejected)
- `GET /api/invoices/{id}/payment-history`

## Rules

- One invoice per order — enforced by unique compound `(tenant_id, order_id)` index.
- Direct financial-status mutation via API is rejected.
- Voiding an invoice with net confirmed payments is blocked.
- Voiding requires a reason.
