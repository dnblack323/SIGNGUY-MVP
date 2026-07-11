"""Canonical money conversion helpers (EC1 — Money Policy contract).

Permanent engineering contract:
- Transactional commerce money is stored as integer cents on Quote, Order Item,
  Work Order snapshot, Invoice, Invoice Line Item, and Payment.
- Transactional commerce fields carry the `_cents` suffix.
- Pricing configuration (SHOP_DEFAULTS, MATERIALS, CATEGORY_DEFAULTS) remains
  dollar-based; pricing calculations use `Decimal` internally.
- One explicit pricing-to-commerce conversion boundary lives in this module.
- Stripe amounts remain integer cents on the wire and in our Payment row.
- APIs return numeric cents. Display formatting happens on the frontend via
  `centsToDollarsString` / `MoneyInput`.
- Reports SUM integer cents. Display formatting happens in the renderer.

Do not introduce ambiguous unsuffixed money fields on any commerce model.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def dollars_to_cents(amount) -> int:
    """Convert a dollar amount (int / float / str / Decimal) to integer cents.

    Rounds half-up at the second decimal.
    Raises TypeError on unsupported input.
    Raises ValueError on non-numeric strings.
    """
    if amount is None:
        raise TypeError("dollars_to_cents: amount is required")
    if isinstance(amount, bool):
        raise TypeError("dollars_to_cents: bool is not a valid money amount")
    if isinstance(amount, Decimal):
        d = amount
    elif isinstance(amount, (int, float)):
        d = Decimal(str(amount))
    elif isinstance(amount, str):
        d = Decimal(amount.strip())
    else:
        raise TypeError(f"dollars_to_cents: unsupported type {type(amount).__name__}")
    cents = (d * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def cents_to_dollars(cents: int) -> Decimal:
    """Convert integer cents to a Decimal dollar amount (2 dp)."""
    if not isinstance(cents, int) or isinstance(cents, bool):
        raise TypeError("cents_to_dollars: integer cents required")
    return (Decimal(cents) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def sum_cents(values) -> int:
    """Safe integer sum for reports; refuses non-integer inputs."""
    total = 0
    for v in values:
        if not isinstance(v, int) or isinstance(v, bool):
            raise TypeError("sum_cents: only integer cents allowed")
        total += v
    return total
