"""EC9 Phase 9E-2 — Promotional Items calculator.

Unlike the other calculators, this category is driven primarily by the
tenant's own reusable `PricingSavedItem` library (Phase 9D) — there is
deliberately NO large hardcoded product catalog here. The caller (router)
resolves an optional `saved_item` dict (a `PricingSavedItem`) and passes it
in; this module only uses it for (a) the exact-match quantity-tier price
lookup (`resolve_quantity_tier_price` — e.g. the preloaded Business Card /
Magnetic Business Card starter items) and (b) as the default `pricing_method`
when the caller didn't specify one. Loading a saved item's other stored
defaults into the editable form is a frontend concern (Phase 9D's existing
"load saved_config, stays editable" contract) — this module never invents
values a saved item didn't actually configure.

A FORMULA LIBRARY invoked from `services/pricing.calculate_pricing()`.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from .pricing_flat_sqft import _apply_components, _d, _r2, _resolve
from .pricing_saved_items import resolve_quantity_tier_price


def _r2_or_none(v: Optional[Decimal]) -> Optional[float]:
    return None if v is None else _r2(v)


def calculate_promotional_pricing(
    *, shop: dict[str, Any], cat: dict[str, Any], pricing_components: list[dict[str, Any]],
    quantity: int, manual_selling_price: Optional[float], category_inputs: dict[str, Any],
    saved_item: Optional[dict[str, Any]],
) -> dict[str, Any]:
    inputs = category_inputs or {}
    qty = max(1, int(quantity or 1))

    saved_default_method = (saved_item or {}).get("default_pricing_method")
    pricing_method, pm_src = _resolve(inputs, "pricing_method", saved_default_method or "manual")
    if pm_src == "shop_default" and saved_default_method:
        pm_src = "saved_item"

    promotional_item_type, pit_src = _resolve(inputs, "promotional_item_type", None)
    order_item_name, name_src = _resolve(inputs, "order_item_name", (saved_item or {}).get("name"))
    description, desc_src = _resolve(inputs, "description", None)
    vendor_supplier, vendor_src = _resolve(inputs, "vendor_supplier", None)

    known_supplier_cost, ksc_src = _resolve(inputs, "known_supplier_cost", cat.get("default_known_supplier_cost", True))
    unit_cost, uc_src = _resolve(inputs, "unit_cost", 0.0)
    item_cost = _d(unit_cost) * qty if known_supplier_cost else Decimal("0")

    flat_fee_price, ffp_src = _resolve(inputs, "flat_fee_price", None)

    setup_required, sr_src = _resolve(inputs, "setup_required", cat.get("default_setup_required", False))
    setup_fee, sf_src = _resolve(inputs, "setup_fee", 0.0)
    setup_cost = _d(setup_fee) if setup_required else Decimal("0")

    decoration_method, dm_src = _resolve(inputs, "decoration_method", None)
    decoration_location, dl_src = _resolve(inputs, "decoration_location", None)
    decoration_fee_required, dfr_src = _resolve(inputs, "decoration_fee_required", cat.get("default_decoration_fee_required", False))
    decoration_fee_type, dft_src = _resolve(inputs, "decoration_fee_type", "per_piece")
    decoration_fee_amount, dfa_src = _resolve(inputs, "decoration_fee_amount", 0.0)
    decoration_cost = Decimal("0")
    if decoration_fee_required:
        decoration_cost = (_d(decoration_fee_amount) * qty) if decoration_fee_type == "per_piece" else _d(decoration_fee_amount)

    personalization_required, pr_src = _resolve(inputs, "personalization_required", cat.get("default_personalization_required", False))
    personalization_count, pc_src = _resolve(inputs, "personalization_count", 0)
    personalization_fee, pf_src = _resolve(inputs, "personalization_fee", 0.0)
    personalization_cost = (_d(personalization_fee) * _d(personalization_count)) if personalization_required else Decimal("0")

    shipping_required, shr_src = _resolve(inputs, "shipping_required", cat.get("default_shipping_required", False))
    shipping_cost_in, shc_src = _resolve(inputs, "shipping_cost", 0.0)
    shipping_cost = _d(shipping_cost_in) if shipping_required else Decimal("0")

    rush, rush_src = _resolve(inputs, "rush", cat.get("default_rush", False))

    base_cost = item_cost + decoration_cost + setup_cost + personalization_cost
    components_cost, components_applied = _apply_components(pricing_components, base_cost)
    base_cost += components_cost

    overhead_pct = _d(shop.get("default_overhead_percent") or 0)
    overhead_cost = base_cost * (overhead_pct / Decimal("100"))
    true_cost = base_cost + overhead_cost + shipping_cost

    markup = _d(cat.get("default_markup_multiplier") or 1.50)
    target_margin = _d(cat.get("target_margin_percent") or 33)
    minimum_charge = _d(cat.get("minimum_charge") or 50.0)

    tier_match = False
    tier_price: Optional[Decimal] = None
    requires_manual_price = False
    if pricing_method == "tier_pricing":
        if saved_item:
            found = resolve_quantity_tier_price(saved_item, qty)
            if found is not None:
                tier_match = True
                tier_price = _d(found)
        if not tier_match:
            requires_manual_price = True

    by_markup = (base_cost + overhead_cost) * markup
    by_margin = (base_cost + overhead_cost) / (Decimal("1") - target_margin / Decimal("100")) if target_margin < 100 else (base_cost + overhead_cost)
    cost_plus_price = max(by_markup, by_margin, minimum_charge)

    if pricing_method == "tier_pricing" and tier_match:
        pre_addon_price: Optional[Decimal] = tier_price + decoration_cost + setup_cost + personalization_cost
    elif pricing_method == "flat_fee" and flat_fee_price is not None:
        pre_addon_price = _d(flat_fee_price) + decoration_cost + setup_cost + personalization_cost
    elif requires_manual_price:
        pre_addon_price = None
    else:  # per_piece or manual — cost-plus already includes decoration/setup/personalization in base_cost
        pre_addon_price = cost_plus_price

    if pre_addon_price is None:
        suggested_price = None
    else:
        price_with_shipping = pre_addon_price + shipping_cost
        rush_pct = _d(shop.get("rush_fee_percent") or 0)
        price_after_rush = price_with_shipping * (Decimal("1") + rush_pct / Decimal("100")) if rush else price_with_shipping
        global_min = _d(shop.get("minimum_order_amount") or 0)
        suggested_price = max(price_after_rush, global_min)

    if manual_selling_price is not None and manual_selling_price >= 0:
        selling_price: Optional[Decimal] = _d(manual_selling_price)
        method_used = "manual_override"
    elif suggested_price is not None:
        selling_price = suggested_price
        method_used = pricing_method
    else:
        selling_price = None
        method_used = "manual_required_no_tier_match"

    if selling_price is not None:
        profit_amount: Optional[Decimal] = selling_price - true_cost
        profit_margin_percent: Optional[Decimal] = (profit_amount / selling_price) * Decimal("100") if selling_price > 0 else Decimal("0")
    else:
        profit_amount = None
        profit_margin_percent = None

    breakdown: list[dict[str, Any]] = []
    if item_cost > 0: breakdown.append({"label": "Item cost", "amount": _r2(item_cost)})
    if decoration_cost > 0: breakdown.append({"label": "Decoration fee", "amount": _r2(decoration_cost)})
    if setup_cost > 0: breakdown.append({"label": "Setup fee", "amount": _r2(setup_cost)})
    if personalization_cost > 0: breakdown.append({"label": "Personalization", "amount": _r2(personalization_cost)})
    for comp in components_applied:
        breakdown.append({"label": comp["name"] or "Pricing component", "amount": comp["amount"]})
    breakdown.append({"label": "Overhead", "amount": _r2(overhead_cost)})
    if shipping_cost > 0: breakdown.append({"label": "Shipping / pass-through", "amount": _r2(shipping_cost)})
    breakdown.append({"label": "True cost", "amount": _r2(true_cost)})
    if tier_match:
        breakdown.append({"label": "Saved tier price", "amount": _r2(tier_price)})
    if requires_manual_price:
        breakdown.append({"label": "No configured tier for this quantity — manual price required", "amount": 0.0})
    elif suggested_price is not None:
        breakdown.append({"label": "Suggested price", "amount": _r2(suggested_price)})
    if selling_price is not None:
        breakdown.append({"label": "Selling price", "amount": _r2(selling_price)})
        breakdown.append({"label": "Profit", "amount": _r2(profit_amount)})

    category_inputs_used = {
        "order_item_name": order_item_name, "description": description, "promotional_item_type": promotional_item_type,
        "vendor_supplier": vendor_supplier, "known_supplier_cost": known_supplier_cost, "unit_cost": unit_cost,
        "pricing_method": pricing_method, "flat_fee_price": flat_fee_price, "decoration_method": decoration_method,
        "decoration_location": decoration_location, "setup_required": setup_required, "setup_fee": setup_fee,
        "decoration_fee_required": decoration_fee_required, "decoration_fee_type": decoration_fee_type,
        "decoration_fee_amount": decoration_fee_amount, "personalization_required": personalization_required,
        "personalization_count": personalization_count, "personalization_fee": personalization_fee,
        "shipping_required": shipping_required, "shipping_cost": shipping_cost_in, "rush": rush,
    }
    source_labels = {
        "pricing_method": pm_src, "order_item_name": name_src, "description": desc_src,
        "promotional_item_type": pit_src, "vendor_supplier": vendor_src, "known_supplier_cost": ksc_src,
        "unit_cost": uc_src, "flat_fee_price": ffp_src, "decoration_method": dm_src, "decoration_location": dl_src,
        "setup_required": sr_src, "setup_fee": sf_src, "decoration_fee_required": dfr_src,
        "decoration_fee_type": dft_src, "decoration_fee_amount": dfa_src, "personalization_required": pr_src,
        "personalization_count": pc_src, "personalization_fee": pf_src, "shipping_required": shr_src,
        "shipping_cost": shc_src, "rush": rush_src,
    }

    return {
        "category": "promotional",
        "width_inches": 0.0, "height_inches": 0.0,
        "quantity": qty,
        "area_sqft_each": 0.0, "area_sqft_total": 0.0,
        "material_key": (saved_item or {}).get("name") or promotional_item_type or "Custom promotional item",
        "material_sell_rate_per_sqft": None,
        "material_cost": _r2(item_cost),
        "labor_cost": 0.0,
        "design_cost": 0.0,
        "setup_cost": _r2(setup_cost),
        "finishing_cost": _r2(decoration_cost),
        "hardware_cost": 0.0,
        "install_cost": 0.0,
        "outsourcing_cost": 0.0,
        "file_cleanup_cost": 0.0,
        "overhead_cost": _r2(overhead_cost),
        "base_cost": _r2(base_cost),
        "true_cost": _r2(true_cost),
        "suggested_price": _r2_or_none(suggested_price),
        "selling_price": _r2_or_none(selling_price),
        "profit_amount": _r2_or_none(profit_amount),
        "profit_margin_percent": _r2_or_none(profit_margin_percent),
        "pricing_method_used": method_used,
        "quantity_discount_percent": 0,
        "rush_applied": bool(rush),
        "pricing_components_applied": components_applied,
        # Promotional-specific additive keys
        "saved_item_id": (saved_item or {}).get("id"),
        "saved_item_name": (saved_item or {}).get("name"),
        "tier_match": tier_match,
        "tier_price": _r2_or_none(tier_price),
        "requires_manual_price": requires_manual_price,
        "personalization_cost": _r2(personalization_cost),
        "shipping_cost": _r2(shipping_cost),
        "category_inputs_used": category_inputs_used,
        "source_labels": source_labels,
        "breakdown": breakdown,
        "shop_defaults_used": {
            "default_overhead_percent": shop.get("default_overhead_percent"),
            "target_profit_margin_percent": shop.get("target_profit_margin_percent"),
            "default_markup_multiplier": shop.get("default_markup_multiplier"),
            "minimum_order_amount": shop.get("minimum_order_amount"),
            "rush_fee_percent": shop.get("rush_fee_percent"),
        },
    }
