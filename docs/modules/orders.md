# Orders Module (EC3)

**Owner checkpoint:** EC3. **Do not** modify without a new preflight.

## Model

`backend/app/models/order.py::Order` + `Order` embeds no items (items in `order_items` collection).

Statuses (operational only, NEVER financial): `draft, confirmed, in_production, ready, completed, cancelled, archived`.

Forbidden statuses (financial impersonation): `paid, partially_paid, invoiced, refunded, overpaid, unpaid`. Server rejects these values.

## Rules

- All money stored as integer cents (`subtotal_cents, discount_cents, tax_cents, total_cents, balance_cents`).
- Totals are ALWAYS backend-derived from `order_items` via `services/commerce_totals.compute_document_totals`. Client-supplied totals are ignored.
- Every item write recomputes totals.
- Source Quote linkage stored on `source_quote_id + source_quote_revision` (legacy `quote_id` retained for compat).
- Amounts in `amount_invoiced_cents / amount_paid_cents` remain zero until EC4 wires Invoice + Payment.

## Endpoints

- `GET  /api/orders`
- `POST /api/orders`
- `GET  /api/orders/{id}` → `{ order, items, totals }`
- `PATCH /api/orders/{id}`
- `POST /api/orders/{id}/status`
- `POST /api/orders/{id}/recalculate`
- `POST /api/orders/{id}/items`
- `PATCH /api/orders/{id}/items/{item_id}`
- `DELETE /api/orders/{id}/items/{item_id}`

## Permissions

`order:read, order:write` (EC1 catalog).
