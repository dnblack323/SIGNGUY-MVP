"""Pure document-level pricing totals for Quote and Order documents.

This module accepts already-priced line-item dictionaries and frozen snapshot
evidence. It does not price individual lines, resolve settings, query storage,
or know about tenants, users, permissions, routers, or audits.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable

from .money import ROUNDING_MODE
from .validation import ContractValidationError


DIGITAL_PRINT_DOCUMENT_MINIMUM_POLICY = "digital_print_document_order_minimum"


def _int(value: Any, *, field_name: str = "value") -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        raise ContractValidationError(f"{field_name} must not be a boolean")
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _nonnegative_int(value: Any, *, field_name: str) -> int:
    return max(0, _int(value, field_name=field_name))


def _snapshot_dollars_to_cents(snapshot: dict[str, Any], key: str) -> int | None:
    value = snapshot.get(key)
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except Exception:
        return None
    if not amount.is_finite() or amount < 0:
        return None
    return int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUNDING_MODE))


def compute_line_totals(
    *,
    quantity: int,
    unit_price_cents: int,
    discount_cents: int = 0,
    tax_cents: int = 0,
) -> dict[str, int]:
    """Return backend-authoritative line totals in integer cents."""

    q = _nonnegative_int(quantity, field_name="quantity")
    unit = _nonnegative_int(unit_price_cents, field_name="unit_price_cents")
    disc = _nonnegative_int(discount_cents, field_name="discount_cents")
    tax = _nonnegative_int(tax_cents, field_name="tax_cents")
    subtotal = q * unit
    line_total = max(0, subtotal - disc + tax)
    return {
        "line_subtotal_cents": subtotal,
        "discount_cents": disc,
        "tax_cents": tax,
        "line_total_cents": line_total,
    }


def compute_document_totals(items: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Sum already-derived line-item totals into document totals."""

    subtotal = 0
    discount = 0
    tax = 0
    total = 0
    count = 0
    for item in items or []:
        subtotal += _nonnegative_int(item.get("line_subtotal_cents"), field_name="line_subtotal_cents")
        discount += _nonnegative_int(item.get("discount_cents"), field_name="discount_cents")
        tax += _nonnegative_int(item.get("tax_cents"), field_name="tax_cents")
        total += _nonnegative_int(item.get("line_total_cents"), field_name="line_total_cents")
        count += 1
    return {
        "subtotal_cents": subtotal,
        "discount_cents": discount,
        "tax_cents": tax,
        "total_cents": total,
        "item_count": count,
    }


def compute_pricing_summary(items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Roll up stored item pricing evidence without recalculating prices."""

    item_list = list(items or [])
    total_estimated_cost_cents = 0
    total_suggested_price_cents = 0
    total_manual_price_amount_cents = 0
    total_estimated_profit_cents = 0
    warnings_count = 0
    for item in item_list:
        qty = max(1, _int(item.get("quantity"), field_name="quantity") or 1)
        if item.get("estimated_cost_cents") is not None:
            total_estimated_cost_cents += _int(item.get("estimated_cost_cents"), field_name="estimated_cost_cents")
        if item.get("suggested_price_cents") is not None:
            total_suggested_price_cents += _int(item.get("suggested_price_cents"), field_name="suggested_price_cents") * qty
        if item.get("selected_price_source") == "manual":
            total_manual_price_amount_cents += _int(item.get("line_subtotal_cents"), field_name="line_subtotal_cents")
        if item.get("estimated_profit_cents") is not None:
            total_estimated_profit_cents += _int(item.get("estimated_profit_cents"), field_name="estimated_profit_cents")
        if item.get("calculation_warnings"):
            warnings_count += 1

    selected_final_total_cents = sum(_int(i.get("line_total_cents"), field_name="line_total_cents") for i in item_list)
    estimated_margin_percent = (
        round((total_estimated_profit_cents / selected_final_total_cents) * 100, 2)
        if selected_final_total_cents > 0 else 0.0
    )
    return {
        "total_estimated_cost_cents": total_estimated_cost_cents,
        "total_manual_price_amount_cents": total_manual_price_amount_cents,
        "total_suggested_price_amount_cents": total_suggested_price_cents,
        "selected_final_total_cents": selected_final_total_cents,
        "estimated_total_profit_cents": total_estimated_profit_cents,
        "estimated_margin_percent": estimated_margin_percent,
        "item_count": len(item_list),
        "items_with_warnings_count": warnings_count,
    }


def build_digital_print_document_minimum(items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Build one document-level Digital Print minimum adjustment."""

    eligible: list[dict[str, Any]] = []
    order_minimum_candidates: list[int] = []
    eligible_subtotal_cents = 0

    for item in items or []:
        if item.get("category") != "digital_print":
            continue
        line_subtotal_cents = _nonnegative_int(item.get("line_subtotal_cents"), field_name="line_subtotal_cents")
        snapshot = dict(item.get("pricing_snapshot") or {})
        order_minimum_cents = _snapshot_dollars_to_cents(snapshot, "order_minimum")
        item_minimum_total_cents = _snapshot_dollars_to_cents(snapshot, "item_minimum_total")

        eligible_subtotal_cents += line_subtotal_cents
        if order_minimum_cents is not None:
            order_minimum_candidates.append(order_minimum_cents)

        eligible.append({
            "line_item_id": item.get("id"),
            "category": item.get("category"),
            "quantity": _nonnegative_int(item.get("quantity"), field_name="quantity") or 1,
            "unit_price_cents": _nonnegative_int(item.get("unit_price_cents"), field_name="unit_price_cents"),
            "line_subtotal_cents": line_subtotal_cents,
            "selected_price_source": item.get("selected_price_source") or "manual",
            "pricing_status": item.get("pricing_status") or "manual",
            "item_minimum_total_cents": item_minimum_total_cents,
            "order_minimum_cents": order_minimum_cents,
            "minimum_policy": snapshot.get("minimum_policy"),
            "minimum_scope": snapshot.get("minimum_scope"),
        })

    order_minimum_cents = max(order_minimum_candidates) if order_minimum_candidates else 0
    adjustment_cents = max(0, order_minimum_cents - eligible_subtotal_cents) if order_minimum_cents else 0
    return {
        "policy": DIGITAL_PRINT_DOCUMENT_MINIMUM_POLICY,
        "scope": "quote_or_order_document",
        "category": "digital_print",
        "eligible_line_items": eligible,
        "eligible_line_item_ids": [row["line_item_id"] for row in eligible if row.get("line_item_id")],
        "eligible_subtotal_cents": eligible_subtotal_cents,
        "order_minimum_cents": order_minimum_cents,
        "order_minimum_adjustment_cents": adjustment_cents,
        "adjustment_applied": adjustment_cents > 0,
        "adjustment_count": 1 if adjustment_cents > 0 else 0,
    }


def calculate_document(items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Return document totals plus immutable document-pricing evidence."""

    item_list = list(items or [])
    line_totals = compute_document_totals(item_list)
    digital_print_minimum = build_digital_print_document_minimum(item_list)
    adjustment_cents = _nonnegative_int(
        digital_print_minimum.get("order_minimum_adjustment_cents"),
        field_name="order_minimum_adjustment_cents",
    )
    adjusted_subtotal = int(line_totals["subtotal_cents"]) + adjustment_cents
    adjusted_total = int(line_totals["total_cents"]) + adjustment_cents
    digital_print_minimum["document_subtotal_before_adjustment_cents"] = int(line_totals["subtotal_cents"])
    digital_print_minimum["document_subtotal_after_adjustment_cents"] = adjusted_subtotal
    digital_print_minimum["document_total_after_adjustment_cents"] = adjusted_total
    return {
        "subtotal_cents": adjusted_subtotal,
        "discount_cents": int(line_totals["discount_cents"]),
        "tax_cents": int(line_totals["tax_cents"]),
        "total_cents": adjusted_total,
        "item_count": int(line_totals["item_count"]),
        "line_subtotal_cents": int(line_totals["subtotal_cents"]),
        "line_total_cents": int(line_totals["total_cents"]),
        "document_pricing_adjustment_cents": adjustment_cents,
        "digital_print_order_minimum_adjustment_cents": adjustment_cents,
        "digital_print_minimum": digital_print_minimum,
    }
