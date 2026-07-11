# Quotes Module (EC3)

**Owner checkpoint:** EC3. **Do not** modify without a new preflight.

## Model

`backend/app/models/quote.py::Quote` + `backend/app/models/quote_line_item.py::QuoteLineItem` + `backend/app/models/quote_revision.py::QuoteRevision`.

Statuses: `draft, sent, viewed, approved, declined, expired (derived), converted, void`.

## Rules

- All money stored as integer cents (`subtotal_cents, discount_cents, tax_cents, total_cents`).
- Totals are ALWAYS backend-derived from the current revision's line items. Client-supplied totals are ignored.
- Editing customer-visible commercial fields on a `sent` (or later) quote snapshots the current state into `quote_revisions` and bumps `revision_number`.
- `expires_at` is derived at read time. Expired quotes cannot convert without an authorized `allow_expired + override_reason` payload (audited).
- `converted` quotes are read-only. `void` quotes cannot be edited or converted.

## Endpoints

- `GET  /api/quotes` (filter: status, customer_id, limit, skip)
- `POST /api/quotes`
- `GET  /api/quotes/{id}` → `{ quote, line_items, totals }`
- `PATCH /api/quotes/{id}`
- `POST /api/quotes/{id}/status`
- `POST /api/quotes/{id}/archive`
- `GET  /api/quotes/{id}/line-items`
- `POST /api/quotes/{id}/line-items`
- `PATCH /api/quotes/{id}/line-items/{line_id}`
- `DELETE /api/quotes/{id}/line-items/{line_id}`
- `GET  /api/quotes/{id}/revisions`
- `GET  /api/quotes/{id}/revisions/{n}`
- `POST /api/quotes/{id}/convert-to-order`

## Permissions

`quote:read, quote:write, quote:convert` (EC1 catalog).
