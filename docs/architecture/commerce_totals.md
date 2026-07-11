# Commerce Totals Service (EC3)

`backend/app/services/commerce_totals.py` — canonical backend derivation of all commerce totals.

## Rules

- Integer cents only. No floating-point money math.
- Rounding at a single boundary: cents are already integers throughout commerce; conversion happens at `core/money.dollars_to_cents` when calculator output enters a commerce field.
- Never trust client-supplied totals. Routers call `compute_line_totals(...)` on every item write and `compute_document_totals(items)` on the parent document (Quote/Order).
- Negative results clamped to zero (defensive).
- Discounts and taxes accepted as line-item and document-level inputs; document totals sum item-level values.
- Sales-tax provider integration remains a future checkpoint boundary — EC3 accepts `tax_cents` as pass-through data.
