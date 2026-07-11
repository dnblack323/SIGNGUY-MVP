"""EC3 — Commerce totals derivation (backend-authoritative).

Every commerce total (line, quote, order) is computed here. Routers MUST NOT
accept client-supplied totals; they call these helpers.

All values are integer cents. Rounding at a single boundary using
`round(value)` (Python 3 banker's rounding is acceptable at cent granularity
since the frontend already rounds with `Math.round`).
"""
from __future__ import annotations

from typing import Iterable


def _int(v) -> int:
    if v is None:
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def compute_line_totals(
    *,
    quantity: int,
    unit_price_cents: int,
    discount_cents: int = 0,
    tax_cents: int = 0,
) -> dict[str, int]:
    """Return the derived line-item totals in integer cents.

    line_subtotal_cents = quantity * unit_price_cents
    line_total_cents    = subtotal - discount + tax  (never negative)
    """
    q = max(0, _int(quantity))
    unit = max(0, _int(unit_price_cents))
    disc = max(0, _int(discount_cents))
    tax = max(0, _int(tax_cents))
    subtotal = q * unit
    line_total = subtotal - disc + tax
    if line_total < 0:
        line_total = 0
    return {
        "line_subtotal_cents": subtotal,
        "discount_cents": disc,
        "tax_cents": tax,
        "line_total_cents": line_total,
    }


def compute_document_totals(items: Iterable[dict]) -> dict[str, int]:
    """Sum a set of line items into a Quote/Order document total envelope."""
    subtotal = 0
    discount = 0
    tax = 0
    total = 0
    count = 0
    for item in items or []:
        subtotal += _int(item.get("line_subtotal_cents"))
        discount += _int(item.get("discount_cents"))
        tax += _int(item.get("tax_cents"))
        total += _int(item.get("line_total_cents"))
        count += 1
    return {
        "subtotal_cents": subtotal,
        "discount_cents": discount,
        "tax_cents": tax,
        "total_cents": total,
        "item_count": count,
    }
