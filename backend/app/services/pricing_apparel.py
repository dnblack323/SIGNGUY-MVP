"""EC9 Phase 9E-2 — Apparel calculator.

Implements the EC09-controlling-document Apparel formulas: garment/blank
cost, size breakdown (with auto-counted plus-size upcharge), decoration
method (9 methods — HTV & Screen Print Transfer are fully priced off the
garment quantity/placement tier tables; the other 7 have full foundation
support and are cost-plus priced from their own setup/material constants),
decoration location/placement, number of print colors, embroidery stitch
count, setup/design charges, personalization (custom name/number), specialty
finishes, rush, and manual price override.

A FORMULA LIBRARY invoked from `services/pricing.calculate_pricing()` — not a
second pricing engine, never called directly by routers. Reuses the same
`_d`/`_r2`/`_resolve`/`_apply_components` helpers as
`services/pricing_flat_sqft.py` to avoid duplicating cost-assembly logic.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from .pricing_flat_sqft import _apply_components, _d, _r2, _resolve

APPAREL_PLACEMENT_MAP_GARMENT = {"front_small": "front", "back_large": "back", "front_back": "combo"}
APPAREL_PLACEMENT_MAP_HAT = {"front_only": "front", "side_back": "back", "front_side_back": "combo"}
PLUS_SIZES = {"2XL", "3XL", "4XL", "5XL"}


def _find_tier(tiers: list[dict[str, Any]], qty: int) -> Optional[dict[str, Any]]:
    for t in tiers or []:
        lo = t.get("min_qty", 0)
        hi = t.get("max_qty")
        if qty >= lo and (hi is None or qty <= hi):
            return t
    return tiers[-1] if tiers else None


def calculate_apparel_pricing(
    *, shop: dict[str, Any], cat: dict[str, Any], pricing_components: list[dict[str, Any]],
    quantity: int, manual_selling_price: Optional[float], category_inputs: dict[str, Any],
) -> dict[str, Any]:
    inputs = category_inputs or {}
    garments: dict[str, Any] = cat.get("garments") or {}
    decoration_methods: dict[str, Any] = cat.get("decoration_methods") or {}

    garment_type, gt_src = _resolve(inputs, "garment_type", "short_sleeve_tee")
    garment_cfg = garments.get(garment_type) or next(iter(garments.values()), {})
    is_hat = bool(garment_cfg.get("is_hat"))

    sizes, sizes_src = _resolve(inputs, "sizes", None)
    if isinstance(sizes, dict) and sizes:
        qty = max(1, sum(int(v or 0) for v in sizes.values()))
        plus_size_count = sum(int(v or 0) for k, v in sizes.items() if k in PLUS_SIZES)
    else:
        qty = max(1, int(quantity or 1))
        plus_size_count = 0

    if is_hat:
        brand_key, brand_src = None, "shop_default"
        blank_cost_each = _d(garment_cfg.get("blank_cost", 0))
        tiers = garment_cfg.get("tiers") or []
    else:
        brands = garment_cfg.get("brands") or {}
        default_brand = next(iter(brands.keys()), None)
        brand_key, brand_src = _resolve(inputs, "brand", default_brand)
        brand_cfg = brands.get(brand_key) or next(iter(brands.values()), {})
        blank_cost_each = _d(brand_cfg.get("blank_cost", 0))
        tiers = brand_cfg.get("tiers") or []

    customer_supplied, cs_src = _resolve(inputs, "customer_supplied", False)
    blank_cost = Decimal("0") if customer_supplied else blank_cost_each * qty

    default_placement = "front_side_back" if is_hat else "front_back"
    placement, placement_src = _resolve(inputs, "placement", default_placement)
    placement_map = APPAREL_PLACEMENT_MAP_HAT if is_hat else APPAREL_PLACEMENT_MAP_GARMENT
    col = placement_map.get(placement, "combo")

    tier_row = _find_tier(tiers, qty)
    table_unit_price = _d(tier_row.get(col)) if tier_row else Decimal("0")
    table_revenue = table_unit_price * qty

    decoration_method, dm_src = _resolve(inputs, "decoration_method", cat.get("default_decoration_method", "htv"))
    dm_cfg = decoration_methods.get(decoration_method) or decoration_methods.get("htv") or {}
    table_based = bool(dm_cfg.get("table_based"))
    pricing_authority = dm_cfg.get("pricing_authority", "exact_table" if table_based else "foundation_estimate")

    calculation_warnings: list[str] = []
    if pricing_authority == "foundation_estimate":
        calculation_warnings.append(
            f"'{dm_cfg.get('label', decoration_method)}' uses a provisional Pricing Foundation cost-plus "
            "estimate — it is not an exact production-tested price table like HTV / Screen Print Transfer."
        )

    num_colors, nc_src = _resolve(inputs, "num_colors", 1)
    num_colors = max(1, int(num_colors or 1))
    stitch_count, stitch_src = _resolve(inputs, "stitch_count", 0)

    cost_type = dm_cfg.get("material_cost_type")
    rate = _d(dm_cfg.get("material_cost_rate", 0))
    is_provisional_area_assumption = bool(dm_cfg.get("is_provisional_area_assumption")) and cost_type == "per_sqin"
    decoration_area_assumption_sqin: Optional[Decimal] = None
    area_src = "not_applicable"
    if cost_type == "per_color_per_piece":
        decoration_material_cost = rate * _d(num_colors) * qty
    elif cost_type == "per_1000_stitches":
        decoration_material_cost = rate * (_d(stitch_count) / Decimal("1000")) * qty
    elif cost_type == "per_piece":
        decoration_material_cost = rate * qty
    elif cost_type == "per_sqin":
        method_area_defaults = dm_cfg.get("default_area_sqin_by_placement") or {}
        decoration_area_sqin, area_src = _resolve(
            inputs, "decoration_area_sqin", method_area_defaults.get("hat" if is_hat else col, 16),
        )
        decoration_area_assumption_sqin = _d(decoration_area_sqin)
        decoration_material_cost = rate * decoration_area_assumption_sqin * qty
        if is_provisional_area_assumption:
            calculation_warnings.append(
                f"Decoration area for '{dm_cfg.get('label', decoration_method)}' is a provisional STARTER "
                f"ASSUMPTION ({decoration_area_assumption_sqin} sq in) — not an owner-approved EC09 pricing "
                "fact. Edit it in Pricing Foundation \u2192 Apparel \u2192 Decoration Methods, or override "
                "`decoration_area_sqin` per-calculation."
            )
    else:
        decoration_material_cost = Decimal("0")

    setup_cost = _d(dm_cfg.get("setup_fee", 0))
    if dm_cfg.get("setup_fee_per_color"):
        setup_cost *= _d(num_colors)

    artwork_needed, artwork_src = _resolve(inputs, "artwork_needed", False)
    design_complexity, dc_src = _resolve(inputs, "design_complexity", "simple")
    design_cost = Decimal("0")
    if artwork_needed:
        design_fees = cat.get("design_setup_fee_by_complexity") or {}
        design_cost = _d(design_fees.get(design_complexity, 10.00))

    custom_name_number, cnn_src = _resolve(inputs, "custom_name_number", False)
    custom_name_number_count, cnnc_src = _resolve(inputs, "custom_name_number_count", 0)
    personalization_cost = Decimal("0")
    if custom_name_number:
        rate_key = "custom_name_number_charge_hat" if is_hat else "custom_name_number_charge_garment"
        personalization_cost = _d(cat.get(rate_key, 0)) * _d(custom_name_number_count)

    specialty_finish, sf_src = _resolve(inputs, "specialty_finish", False)
    two_tone_hat_finish, tt_src = _resolve(inputs, "two_tone_hat_finish", False)
    leather_patch, lp_src = _resolve(inputs, "leather_patch", False)
    bag_and_fold, bf_src = _resolve(inputs, "bag_and_fold", False)

    specialty_cost = Decimal("0")
    if specialty_finish:
        key = "specialty_finish_charge_hat" if is_hat else "specialty_finish_charge_garment"
        specialty_cost += _d(cat.get(key, 0)) * qty
    if is_hat and two_tone_hat_finish:
        specialty_cost += _d(cat.get("two_tone_hat_finish_charge", 0)) * qty
    if is_hat and leather_patch:
        specialty_cost += _d(cat.get("leather_patch_charge", 0)) * qty
    if bag_and_fold:
        specialty_cost += _d(cat.get("bag_and_fold_charge", 0)) * qty

    plus_size_upcharge = _d(cat.get("plus_size_upcharge", 0)) * _d(plus_size_count)
    finishing_cost = specialty_cost + plus_size_upcharge

    rush, rush_src = _resolve(inputs, "rush", False)
    rush_percent, rush_pct_src = _resolve(inputs, "rush_percent", cat.get("rush_default_percent", 17.5))

    base_cost = blank_cost + decoration_material_cost + setup_cost + design_cost + personalization_cost + finishing_cost
    components_cost, components_applied = _apply_components(pricing_components, base_cost)
    base_cost += components_cost

    overhead_pct = _d(shop.get("default_overhead_percent") or 0)
    overhead_cost = base_cost * (overhead_pct / Decimal("100"))
    true_cost = base_cost + overhead_cost

    markup = _d(cat.get("default_markup_multiplier") or 2.15)
    minimum_charge = _d(cat.get("minimum_charge") or 60.0)
    min_sell_per_piece = dm_cfg.get("min_sell_per_piece")

    by_markup = true_cost * markup
    candidates = [by_markup, minimum_charge]
    if min_sell_per_piece is not None:
        candidates.append(_d(min_sell_per_piece) * qty)
    if table_based and tier_row:
        candidates.append(table_revenue)
    pre_rush_price = max(candidates)

    rush_premium = pre_rush_price * (_d(rush_percent) / Decimal("100")) if rush else Decimal("0")
    suggested_price = pre_rush_price + rush_premium

    global_min = _d(shop.get("minimum_order_amount") or 0)
    suggested_price = max(suggested_price, global_min)

    if manual_selling_price is not None and manual_selling_price >= 0:
        selling_price = _d(manual_selling_price)
        method_used = "manual_override"
    else:
        selling_price = suggested_price
        method_used = "apparel_table" if (table_based and tier_row) else "apparel_cost_plus"

    profit_amount = selling_price - true_cost
    profit_margin_percent = (profit_amount / selling_price) * Decimal("100") if selling_price > 0 else Decimal("0")

    breakdown = [{"label": f"Blank ({garment_cfg.get('label', garment_type)})", "amount": _r2(blank_cost)}]
    if decoration_material_cost > 0: breakdown.append({"label": "Decoration material", "amount": _r2(decoration_material_cost)})
    if setup_cost > 0: breakdown.append({"label": "Decoration setup", "amount": _r2(setup_cost)})
    if design_cost > 0: breakdown.append({"label": "Artwork / design", "amount": _r2(design_cost)})
    if personalization_cost > 0: breakdown.append({"label": "Custom name / number", "amount": _r2(personalization_cost)})
    if finishing_cost > 0: breakdown.append({"label": "Specialty finishes", "amount": _r2(finishing_cost)})
    for comp in components_applied:
        breakdown.append({"label": comp["name"] or "Pricing component", "amount": comp["amount"]})
    breakdown.append({"label": "Overhead", "amount": _r2(overhead_cost)})
    breakdown.append({"label": "True cost", "amount": _r2(true_cost)})
    if rush_applied := bool(rush):
        breakdown.append({"label": f"Rush ({float(rush_percent):.1f}%)", "amount": _r2(rush_premium)})
    breakdown.append({"label": "Suggested price", "amount": _r2(suggested_price)})
    breakdown.append({"label": "Selling price", "amount": _r2(selling_price)})
    breakdown.append({"label": "Profit", "amount": _r2(profit_amount)})

    brand_label = None if is_hat else (garment_cfg.get("brands") or {}).get(brand_key, {}).get("label")
    material_key = f"{garment_cfg.get('label', garment_type)}" + (f" — {brand_label}" if brand_label else "")

    category_inputs_used = {
        "garment_type": garment_type, "brand": brand_key, "sizes": sizes, "customer_supplied": customer_supplied,
        "placement": placement, "decoration_method": decoration_method, "num_colors": num_colors,
        "stitch_count": stitch_count, "artwork_needed": artwork_needed, "design_complexity": design_complexity,
        "custom_name_number": custom_name_number, "custom_name_number_count": custom_name_number_count,
        "specialty_finish": specialty_finish, "two_tone_hat_finish": two_tone_hat_finish,
        "leather_patch": leather_patch, "bag_and_fold": bag_and_fold, "rush": rush, "rush_percent": rush_percent,
    }
    source_labels = {
        "garment_type": gt_src, "brand": brand_src, "sizes": sizes_src, "customer_supplied": cs_src,
        "placement": placement_src, "decoration_method": dm_src, "num_colors": nc_src, "stitch_count": stitch_src,
        "artwork_needed": artwork_src, "design_complexity": dc_src, "custom_name_number": cnn_src,
        "custom_name_number_count": cnnc_src, "specialty_finish": sf_src, "two_tone_hat_finish": tt_src,
        "leather_patch": lp_src, "bag_and_fold": bf_src, "rush": rush_src, "rush_percent": rush_pct_src,
        "decoration_area_sqin": area_src,
    }

    return {
        "category": "apparel",
        "width_inches": 0.0, "height_inches": 0.0,
        "quantity": qty,
        "area_sqft_each": 0.0, "area_sqft_total": 0.0,
        "material_key": material_key,
        "material_sell_rate_per_sqft": None,
        "material_cost": _r2(blank_cost),
        "labor_cost": 0.0,
        "design_cost": _r2(design_cost),
        "setup_cost": _r2(setup_cost),
        "finishing_cost": _r2(finishing_cost + decoration_material_cost + personalization_cost),
        "hardware_cost": 0.0,
        "install_cost": 0.0,
        "outsourcing_cost": 0.0,
        "file_cleanup_cost": 0.0,
        "overhead_cost": _r2(overhead_cost),
        "base_cost": _r2(base_cost),
        "true_cost": _r2(true_cost),
        "suggested_price": _r2(suggested_price),
        "selling_price": _r2(selling_price),
        "profit_amount": _r2(profit_amount),
        "profit_margin_percent": _r2(profit_margin_percent),
        "pricing_method_used": method_used,
        "quantity_discount_percent": 0,
        "rush_applied": rush_applied,
        "pricing_components_applied": components_applied,
        # Apparel-specific additive keys
        "garment_type": garment_type,
        "brand": brand_key,
        "is_hat": is_hat,
        "plus_size_count": plus_size_count,
        "decoration_method": decoration_method,
        "decoration_table_based": table_based,
        "decoration_pricing_source": pricing_authority,
        "decoration_table_revenue": _r2(table_revenue) if table_based else None,
        "decoration_material_cost": _r2(decoration_material_cost),
        "decoration_area_assumption_sqin": float(decoration_area_assumption_sqin) if decoration_area_assumption_sqin is not None else None,
        "decoration_area_assumption_is_provisional": is_provisional_area_assumption,
        "calculation_warnings": calculation_warnings,
        "personalization_cost": _r2(personalization_cost),
        "category_inputs_used": category_inputs_used,
        "source_labels": source_labels,
        "breakdown": breakdown,
        "shop_defaults_used": {
            "production_hourly_rate": shop.get("production_hourly_rate"),
            "design_hourly_rate": shop.get("design_hourly_rate"),
            "install_hourly_rate": shop.get("install_hourly_rate"),
            "default_overhead_percent": shop.get("default_overhead_percent"),
            "labor_burden_percent": shop.get("labor_burden_percent"),
            "target_profit_margin_percent": shop.get("target_profit_margin_percent"),
            "default_markup_multiplier": shop.get("default_markup_multiplier"),
            "minimum_order_amount": shop.get("minimum_order_amount"),
            "rush_fee_percent": shop.get("rush_fee_percent"),
        },
    }
