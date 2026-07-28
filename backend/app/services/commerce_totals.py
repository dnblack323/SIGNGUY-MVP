"""Compatibility wrappers for backend-authoritative commerce totals."""
from __future__ import annotations

from typing import Any, Iterable

from pricing_engine.document_engine import (
    compute_document_totals as _compute_document_totals,
    compute_line_totals as _compute_line_totals,
    compute_pricing_summary as _compute_pricing_summary,
)


def compute_line_totals(
    *,
    quantity: int,
    unit_price_cents: int,
    discount_cents: int = 0,
    tax_cents: int = 0,
) -> dict[str, int]:
    """Return the derived line-item totals in integer cents."""

    return _compute_line_totals(
        quantity=quantity,
        unit_price_cents=unit_price_cents,
        discount_cents=discount_cents,
        tax_cents=tax_cents,
    )


def compute_document_totals(items: Iterable[dict]) -> dict[str, int]:
    """Sum a set of line items into a Quote/Order document total envelope."""

    return _compute_document_totals(items)


def compute_pricing_summary(items: Iterable[dict]) -> dict[str, Any]:
    """Roll up already-stored item pricing evidence."""

    return _compute_pricing_summary(items)
