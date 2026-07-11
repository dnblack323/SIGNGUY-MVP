# Quote-to-Order Conversion (EC3)

## Contract

Endpoint: `POST /api/quotes/{id}/convert-to-order`

Body:
```json
{ "allow_expired": false, "override_reason": null }
```

## Rules

- Only quotes not already `converted / declined / void` may convert.
- Expired quotes (`expires_at` in the past) require `allow_expired=true` **and** `override_reason` (audit event captures both).
- Conversion uses the latest committed revision (`quotes.revision_number`).
- Creates one Order + copies Quote Line Items into `order_items`.
- Preserves per-line `pricing_snapshot`, dimensions, category, discount/tax cents, manual override metadata, and defaults `production_required` via `services/order_item_rules.default_production_required(category)`.
- Order records `source_quote_id + source_quote_revision`. Legacy `quote_id` field retained for backward compat.
- Quote records `converted_order_id + converted_revision + converted_at`.

## Idempotency + race safety

- Guarded by `find_one_and_update` on `converted_order_id == None`.
- Repeated calls return the winning order with `already_converted: true`.
- Concurrent racing writers cannot create duplicate orders.

## Error codes

| Code | Detail |
|---|---|
| 404 | Quote not found |
| 400 | Cannot convert a declined quote |
| 400 | Cannot convert a voided quote |
| 400 | Quote has expired |
| 400 | Override reason required for expired conversion |
| 409 | Conversion race lost (retryable) |
