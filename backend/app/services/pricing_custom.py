"""EC9 Phase 9E-4 — Custom / Miscellaneous calculator.

Per EC09 controlling document Section 4 "Custom / Miscellaneous Pricing":
Custom is the strict fallback category for items that don't fit any other
pricing structure. It has NO automated cost-estimation engine — the only
computation is `unit_price x quantity`, with the entered unit price always
authoritative. No width/height/area/material/labor/overhead concepts apply
here by design.

- `unit_cost_manual` (optional) feeds ONLY the profit/margin display — it
  never changes the selling price.
- `markup_percent_adjustment` (optional) is a purely informational reference
  figure showing what price a % markup would produce. It is NEVER applied
  automatically and never replaces the entered unit price — both the
  original unit price and the adjusted reference are returned separately and
  clearly labeled.
- The category's configured minimum charge is applied only when it exceeds
  the `unit_price x quantity` subtotal.
- `manual_selling_price` (the universal override) remains a fully separate,
  higher-priority path, exactly like every other category.

A FORMULA LIBRARY invoked from `services/pricing.calculate_pricing()`.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from .pricing_flat_sqft import _d, _r2


def calculate_custom_pricing(
    *, cat: dict[str, Any], quantity: int, manual_selling_price: Optional[float],
    category_inputs: dict[str, Any],
) -> dict[str, Any]:
    inputs = category_inputs or {}
    qty = max(1, int(quantity or 1))
    warnings: list[str] = []

    item_name = inputs.get("item_name") or None
    description = inputs.get("description") or None
    notes = inputs.get("notes") or None

    unit_price = _d(inputs.get("unit_price", 0))
    unit_cost_manual = _d(inputs.get("unit_cost_manual", 0))
    markup_percent_adjustment = _d(inputs.get("markup_percent_adjustment", 0))

    subtotal = unit_price * qty

    default_minimum = _d(cat.get("minimum_charge", 0))
    minimum_charge = _d(inputs.get("minimum_charge_override", default_minimum))
    minimum_applied = minimum_charge > subtotal
    pre_override_price = max(subtotal, minimum_charge)

    # Informational-only markup reference — never applied automatically, and
    # never replaces the entered unit price.
    markup_adjusted_unit_price: Optional[Decimal] = None
    markup_adjusted_subtotal: Optional[Decimal] = None
    if markup_percent_adjustment != 0:
        markup_adjusted_unit_price = unit_price * (Decimal("1") + markup_percent_adjustment / Decimal("100"))
        markup_adjusted_subtotal = markup_adjusted_unit_price * qty
        warnings.append(
            f"Markup adjustment ({float(markup_percent_adjustment):.1f}%) is informational only — it shows what "
            f"${_r2(markup_adjusted_subtotal)} would be. The entered unit price (${_r2(unit_price)}) remains the "
            "authoritative selling price unless you manually change it or use the manual override below."
        )

    if manual_selling_price is not None and manual_selling_price >= 0:
        selling_price = _d(manual_selling_price)
        method_used = "manual_override"
    else:
        selling_price = pre_override_price
        method_used = "unit_price_x_quantity"

    true_cost = unit_cost_manual * qty
    profit_amount = selling_price - true_cost
    profit_margin_percent = (profit_amount / selling_price) * Decimal("100") if selling_price > 0 else Decimal("0")

    breakdown = [{"label": f"Unit price (${_r2(unit_price)} x {qty})", "amount": _r2(subtotal)}]
    if minimum_applied:
        breakdown.append({"label": f"Minimum charge applied (${_r2(minimum_charge)})", "amount": _r2(minimum_charge - subtotal)})
    if markup_adjusted_subtotal is not None:
        breakdown.append({"label": f"Markup-adjusted reference only ({float(markup_percent_adjustment):.1f}%, not applied)", "amount": _r2(markup_adjusted_subtotal)})
    if true_cost > 0:
        breakdown.append({"label": "Unit cost (for profit/margin only)", "amount": _r2(true_cost)})
    breakdown.append({"label": "Selling price", "amount": _r2(selling_price)})
    breakdown.append({"label": "Profit", "amount": _r2(profit_amount)})

    return {
        "category": "custom",
        "width_inches": 0.0, "height_inches": 0.0,
        "quantity": qty,
        "area_sqft_each": 0.0, "area_sqft_total": 0.0,
        "material_key": item_name,
        "material_sell_rate_per_sqft": None,
        "material_cost": 0.0,
        "labor_cost": 0.0,
        "design_cost": 0.0,
        "setup_cost": 0.0,
        "finishing_cost": 0.0,
        "hardware_cost": 0.0,
        "install_cost": 0.0,
        "outsourcing_cost": 0.0,
        "overhead_cost": 0.0,
        "base_cost": _r2(true_cost),
        "true_cost": _r2(true_cost),
        "suggested_price": _r2(pre_override_price),
        "selling_price": _r2(selling_price),
        "profit_amount": _r2(profit_amount),
        "profit_margin_percent": _r2(profit_margin_percent),
        "pricing_method_used": method_used,
        "quantity_discount_percent": 0,
        "rush_applied": False,
        "pricing_components_applied": [],
        # Custom-specific additive keys
        "unit_price": _r2(unit_price),
        "unit_cost_manual": _r2(unit_cost_manual) if unit_cost_manual > 0 else None,
        "minimum_charge_applied": minimum_applied,
        "markup_percent_adjustment": float(markup_percent_adjustment) if markup_percent_adjustment else None,
        "markup_adjusted_unit_price_informational": _r2(markup_adjusted_unit_price) if markup_adjusted_unit_price is not None else None,
        "markup_adjusted_subtotal_informational": _r2(markup_adjusted_subtotal) if markup_adjusted_subtotal is not None else None,
        "item_name": item_name,
        "description": description,
        "notes": notes,
        "calculation_warnings": warnings,
        "category_inputs_used": {
            "item_name": item_name, "description": description, "unit_price": float(unit_price),
            "unit_cost_manual": float(unit_cost_manual), "markup_percent_adjustment": float(markup_percent_adjustment),
            "minimum_charge_override": float(minimum_charge), "notes": notes,
        },
        "source_labels": {
            "unit_price": "user_entered" if "unit_price" in inputs else "not_set",
            "unit_cost_manual": "user_entered" if "unit_cost_manual" in inputs else "not_set",
            "minimum_charge_override": "user_entered" if "minimum_charge_override" in inputs else "shop_default",
        },
        "breakdown": breakdown,
        "shop_defaults_used": {},
    }
