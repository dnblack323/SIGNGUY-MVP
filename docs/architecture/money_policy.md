# Money Policy (LOCKED — EC1)

## Permanent engineering contract

1. **Commerce values are stored as integer cents.** Fields: `Quote.total_cents`, `QuoteLineItem.line_total_cents`, `Order.total_cents`, `OrderItem.unit_price_cents`, `OrderItem.line_total_cents`, `WorkOrderItemSnapshot.unit_price_cents`, `Invoice.total_cents`, `InvoiceLineItem.unit_price_cents`, `Payment.amount_cents`, and future `tax_cents`, `discount_cents`, `fee_cents`, `amount_paid_cents`, `balance_due_cents`.
2. **Transactional commerce fields carry the `_cents` suffix.** No unsuffixed money field on any commerce model.
3. **Pricing configuration remains dollar-based.** `SHOP_DEFAULTS`, `MATERIALS`, `CATEGORY_DEFAULTS` in `services/starter_defaults.py`; pricing calculations use `Decimal` internally.
4. **Single pricing→commerce conversion boundary** in `backend/app/core/money.py::dollars_to_cents`.
5. **Stripe amounts remain integer cents** on wire and in the Payment row.
6. **APIs return numeric cents.** Display formatting happens on the frontend via `centsToDollarsString` / `MoneyInput`.
7. **Reports SUM integer cents.** Renderer formats.

## Helpers

- `backend/app/core/money.py::dollars_to_cents(amount) -> int` — half-up rounding.
- `backend/app/core/money.py::cents_to_dollars(cents) -> Decimal` — 2 dp.
- `backend/app/core/money.py::sum_cents(iterable) -> int` — refuses non-int inputs.
- Frontend: `centsToDollarsString`, `parseDollarsToCents`, `MoneyInput` in `frontend/src/components/forms/`.

## Enforcement

- `backend/tests/test_money_policy.py` verifies:
  - No ambiguous money fields on Quote/Order/Invoice/WorkOrder Pydantic models.
  - `dollars_to_cents` / `cents_to_dollars` round-trip correctly.
  - Pricing configuration remains dollar-based.

## Do not

- Do not migrate existing commerce data. The current MVP already uses integer cents.
- Do not convert pricing configuration into cents.
- Do not float-multiply money on the wire or in reports.
- Do not add unsuffixed money fields on commerce models.
