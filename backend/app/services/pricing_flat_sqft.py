"""EC9 Phase 9E-1 — Core Flat & Square-Foot Product calculators.

Implements the EC09-controlling-document formulas for the first 4 category
calculators: Banners, Rigid Signs / Panels, Digital Print, Cut Vinyl.

This module is a FORMULA LIBRARY invoked from inside
`services/pricing.calculate_pricing()` — it is not a second pricing engine
and is never called directly by routers. It reuses:
  - canonical EC7 `Material` + Phase 9A `MaterialPricingProfile` (via the
    already-resolved `material_profile` dict passed in by the caller), or
    falls back to the legacy `starter_defaults.MATERIALS` static catalog
    (`material_key`) for backward compatibility with existing calculator use.
  - Phase 9A `PricingComponent`s (already-resolved list passed in) as
    additive extra charges (setup/rush/permit/etc. on top of the formula).
  - Shop-level Pricing Foundation defaults (`shop_defaults`) for labor rates,
    overhead%, rush%, file cleanup fee, install minimum, etc.
  - Category-level Pricing Foundation defaults (`category_defaults.<cat>`)
    for the category-specific seeded constants below.

Every returned dict keeps the EXACT top-level keys the pre-existing generic
`calculate_pricing()` output already had (`material_cost`, `labor_cost`,
`design_cost`, `install_cost`, `overhead_cost`, `true_cost`, `selling_price`,
`profit_amount`, `profit_margin_percent`, `pricing_method_used`, `breakdown`,
`shop_defaults_used`, ...) so `services/pricing_snapshot.build_calculated_snapshot`
(Phase 9F, not yet wired) keeps working unmodified — only NEW additive keys
are introduced (`suggested_price`, `category_inputs_used`, `source_labels`,
`quantity_discount_percent`, `rush_applied`, `pricing_components_applied`).
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from .starter_defaults import DESIGN_COMPLEXITY_MULTIPLIERS, FLAT_SQFT_QUANTITY_TIERS, INSTALL_COMPLEXITY_MULTIPLIERS

FLAT_SQFT_CATEGORIES = {"banners", "rigid_signs", "digital_print", "cut_vinyl"}


def _d(v: Any) -> Decimal:
    if v is None:
        return Decimal("0")
    return Decimal(str(v))


def _r2(v: Decimal) -> float:
    return float(v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _resolve(inputs: dict[str, Any], key: str, default: Any) -> tuple[Any, str]:
    """Return (value, source_label). `user_entered` if the caller explicitly
    supplied a non-None value in `category_inputs`, else `shop_default`."""
    if key in inputs and inputs[key] is not None:
        return inputs[key], "user_entered"
    return default, "shop_default"


def _quantity_discount_percent(category: str, qty: int) -> float:
    for lo, hi, pct in FLAT_SQFT_QUANTITY_TIERS.get(category, []):
        if qty >= lo and (hi is None or qty <= hi):
            return pct
    return 0.0


def _design_mult(level: Optional[str]) -> Decimal:
    return _d(DESIGN_COMPLEXITY_MULTIPLIERS.get(level or "simple", 1.0))


def _install_mult(level: Optional[str]) -> Decimal:
    return _d(INSTALL_COMPLEXITY_MULTIPLIERS.get(level or "easy", 1.0))


def _resolve_material(material_key: Optional[str], materials_legacy: dict[str, Any],
                      material_profile: Optional[dict[str, Any]]) -> tuple[Decimal, Optional[Decimal], Optional[str]]:
    """Returns (cost_per_sqft, sell_rate_per_sqft_or_None, resolved_label)."""
    if material_profile:
        cost = _d(material_profile.get("normalized_cost_basis"))
        sell = material_profile.get("suggested_sell_rate")
        label = material_profile.get("material_name") or material_profile.get("material_id")
        return cost, (_d(sell) if sell is not None else None), label
    if material_key and material_key in materials_legacy:
        m = materials_legacy[material_key]
        return _d(m.get("cost_per_sqft")), _d(m.get("sell_per_sqft")) if m.get("sell_per_sqft") is not None else None, material_key
    return Decimal("0"), None, material_key


def _apply_components(pricing_components: list[dict[str, Any]], subtotal: Decimal) -> tuple[Decimal, list[dict[str, Any]]]:
    """Sum active Pricing Components (Phase 9A) as additive extra charges on
    top of the formula-computed cost. Flat `amount` adds directly; `percent`
    is a percentage of `subtotal` (pre-overhead base cost)."""
    total = Decimal("0")
    applied = []
    for c in pricing_components or []:
        amt = Decimal("0")
        if c.get("amount") is not None:
            amt += _d(c["amount"])
        if c.get("percent") is not None:
            amt += subtotal * (_d(c["percent"]) / Decimal("100"))
        if amt != 0:
            total += amt
            applied.append({"id": c.get("id"), "name": c.get("name"), "amount": _r2(amt)})
    return total, applied


def _finalize(
    *, category: str, shop: dict[str, Any], cat: dict[str, Any], qty: int,
    material_cost: Decimal, labor_cost: Decimal, design_cost: Decimal, install_cost: Decimal,
    finishing_cost: Decimal, hardware_cost: Decimal, file_cleanup_cost: Decimal,
    premium_multiplier: Decimal, pricing_components: list[dict[str, Any]],
    width_inches, height_inches, area_sqft_each: Decimal, total_area: Decimal,
    material_key: Optional[str], material_sell_rate: Optional[Decimal], manual_selling_price: Optional[float],
    category_inputs_used: dict[str, Any], source_labels: dict[str, str], rush_applied: bool,
) -> dict[str, Any]:
    base_cost = material_cost + labor_cost + design_cost + install_cost + finishing_cost + hardware_cost + file_cleanup_cost
    components_cost, components_applied = _apply_components(pricing_components, base_cost)
    base_cost += components_cost

    overhead_pct = _d(shop.get("default_overhead_percent") or 0)
    overhead_cost = base_cost * (overhead_pct / Decimal("100"))
    true_cost = base_cost + overhead_cost

    markup = _d(cat.get("default_markup_multiplier") or shop.get("default_markup_multiplier") or 2.5)
    target_margin = _d(cat.get("target_margin_percent") or shop.get("target_profit_margin_percent") or 40)
    base_rate = _d(cat.get("base_sell_rate_per_sqft") or 0)
    minimum_charge = _d(cat.get("minimum_charge") or 0)

    by_markup = true_cost * markup
    by_margin = true_cost / (Decimal("1") - target_margin / Decimal("100")) if target_margin < 100 else true_cost
    by_rate = base_rate * total_area if base_rate > 0 else Decimal("0")
    pre_premium_price = max(by_markup, by_margin, by_rate, minimum_charge)
    pre_premium_price *= premium_multiplier

    qty_discount_pct = _quantity_discount_percent(category, qty)
    price_after_qty = pre_premium_price * (Decimal("1") - _d(qty_discount_pct) / Decimal("100"))
    price_after_qty = max(price_after_qty, minimum_charge)

    rush_pct = _d(shop.get("rush_fee_percent") or 0)
    price_after_rush = price_after_qty * (Decimal("1") + rush_pct / Decimal("100")) if rush_applied else price_after_qty

    global_min = _d(shop.get("minimum_order_amount") or 0)
    suggested_price = max(price_after_rush, global_min)

    if manual_selling_price is not None and manual_selling_price >= 0:
        selling_price = _d(manual_selling_price)
        method_used = "manual_override"
    else:
        selling_price = suggested_price
        method_used = "cost_plus_labor" if not base_rate else "per_sqft"

    profit_amount = selling_price - true_cost
    profit_margin_percent = (profit_amount / selling_price) * Decimal("100") if selling_price > 0 else Decimal("0")

    breakdown = [{"label": "Material", "amount": _r2(material_cost)}, {"label": "Production labor", "amount": _r2(labor_cost)}]
    if design_cost > 0: breakdown.append({"label": "Design", "amount": _r2(design_cost)})
    if finishing_cost > 0: breakdown.append({"label": "Finishing", "amount": _r2(finishing_cost)})
    if hardware_cost > 0: breakdown.append({"label": "Hardware", "amount": _r2(hardware_cost)})
    if file_cleanup_cost > 0: breakdown.append({"label": "File cleanup", "amount": _r2(file_cleanup_cost)})
    if install_cost > 0: breakdown.append({"label": "Install", "amount": _r2(install_cost)})
    for comp in components_applied:
        breakdown.append({"label": comp["name"] or "Pricing component", "amount": comp["amount"]})
    breakdown.append({"label": "Overhead", "amount": _r2(overhead_cost)})
    breakdown.append({"label": "True cost", "amount": _r2(true_cost)})
    if qty_discount_pct: breakdown.append({"label": f"Quantity discount ({qty_discount_pct:.0f}%)", "amount": _r2(price_after_qty - pre_premium_price)})
    if rush_applied: breakdown.append({"label": "Rush", "amount": _r2(price_after_rush - price_after_qty)})
    breakdown.append({"label": "Suggested price", "amount": _r2(suggested_price)})
    breakdown.append({"label": "Selling price", "amount": _r2(selling_price)})
    breakdown.append({"label": "Profit", "amount": _r2(profit_amount)})

    return {
        "category": category,
        "width_inches": float(width_inches or 0),
        "height_inches": float(height_inches or 0),
        "quantity": qty,
        "area_sqft_each": _r2(area_sqft_each),
        "area_sqft_total": _r2(total_area),
        "material_key": material_key,
        "material_sell_rate_per_sqft": float(material_sell_rate) if material_sell_rate is not None else None,
        "material_cost": _r2(material_cost),
        "labor_cost": _r2(labor_cost),
        "design_cost": _r2(design_cost),
        "setup_cost": 0.0,
        "finishing_cost": _r2(finishing_cost),
        "hardware_cost": _r2(hardware_cost),
        "install_cost": _r2(install_cost),
        "outsourcing_cost": 0.0,
        "file_cleanup_cost": _r2(file_cleanup_cost),
        "overhead_cost": _r2(overhead_cost),
        "base_cost": _r2(base_cost),
        "true_cost": _r2(true_cost),
        "suggested_price": _r2(suggested_price),
        "selling_price": _r2(selling_price),
        "profit_amount": _r2(profit_amount),
        "profit_margin_percent": _r2(profit_margin_percent),
        "pricing_method_used": method_used,
        "quantity_discount_percent": qty_discount_pct,
        "rush_applied": rush_applied,
        "pricing_components_applied": components_applied,
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
            "install_minimum_charge": shop.get("install_minimum_charge"),
            "setup_fee_default": shop.get("setup_fee_default"),
            "rush_fee_percent": shop.get("rush_fee_percent"),
            "file_cleanup_fee_default": shop.get("file_cleanup_fee_default"),
        },
    }


def _install_cost(cat: dict[str, Any], shop: dict[str, Any], total_area: Decimal, install_complexity: Optional[str],
                  extra_mult: Decimal = Decimal("1")) -> Decimal:
    install_hr = _d(cat.get("install_base_hr_per_sqft") or 0.08) * total_area * _install_mult(install_complexity) * extra_mult
    install_cost = install_hr * _d(shop.get("install_hourly_rate") or 0)
    install_min = _d(shop.get("install_minimum_charge") or 0)
    return max(install_cost, install_min) if install_min > 0 else install_cost


def calc_banners(*, shop, cat, materials_legacy, material_profile, pricing_components, width_inches, height_inches,
                 quantity, material_key, design_needed, install_needed, manual_selling_price, inputs: dict[str, Any]) -> dict[str, Any]:
    qty = max(1, int(quantity or 1))
    width_ft = _d(width_inches) / Decimal("12")
    height_ft = _d(height_inches) / Decimal("12")
    raw_area = width_ft * height_ft
    min_area, min_area_src = _resolve(inputs, "min_billable_area_sqft", cat.get("min_billable_area_sqft", 4.0))
    area_each = max(raw_area, _d(min_area))
    total_area = area_each * qty
    waste_pct = _d(cat.get("waste_percent") or 0)
    waste_area = total_area * (Decimal("1") + waste_pct / Decimal("100"))

    coating_type, coating_src = _resolve(inputs, "coating_type", "none")
    coating_rates = cat.get("coating_rate_per_sqft") or {}
    coating_rate = _d(coating_rates.get(coating_type, 0))

    double_sided, ds_src = _resolve(inputs, "double_sided", "single")
    ds_mult = Decimal("1")
    if double_sided == "same_side":
        ds_mult = _d(cat.get("double_sided_same_side_multiplier", 1.75))
    elif double_sided == "different_side":
        ds_mult = _d(cat.get("double_sided_different_side_multiplier", 2.00))

    mat_cost_per_sqft, mat_sell_rate, mat_label = _resolve_material(material_key, materials_legacy, material_profile)
    print_consumable, pc_src = _resolve(inputs, "print_consumable_rate_per_sqft", cat.get("print_consumable_rate_per_sqft", 0.75))
    material_cost = waste_area * ((mat_cost_per_sqft + coating_rate) * ds_mult + _d(print_consumable))

    labor_cost = total_area * _d(cat.get("production_labor_hr_per_sqft", 0.10)) * _d(shop.get("production_hourly_rate") or 0)

    design_cost = Decimal("0")
    design_complexity, dc_src = _resolve(inputs, "design_complexity", "simple")
    if design_needed:
        design_hours = _d(cat.get("design_default_hours", 0.5)) * _design_mult(design_complexity)
        design_cost = design_hours * _d(shop.get("design_hourly_rate") or 0)

    install_complexity, ic_src = _resolve(inputs, "install_complexity", "easy")
    install_cost = _install_cost(cat, shop, total_area, install_complexity) if install_needed else Decimal("0")

    perimeter_ft = 2 * (width_ft + height_ft)
    finishing_cost = Decimal("0")
    hems, hems_src = _resolve(inputs, "hems", False)
    if hems:
        finishing_cost += perimeter_ft * _d(cat.get("hem_charge_per_linear_ft", 0.35)) * qty
    grommets, grom_src = _resolve(inputs, "grommets", "none")
    grommet_count, gc_src = _resolve(inputs, "grommet_count", None)
    if grommets and grommets != "none":
        count = int(grommet_count) if grommet_count else max(4, round(float(perimeter_ft) / 2))
        grommet_cost_each = _d(cat.get("grommet_sell_price_each", 0.75))
        grommet_min = _d(cat.get("grommet_minimum_charge", 4.00))
        finishing_cost += max(_d(count) * grommet_cost_each, grommet_min) * qty
    pole_pockets, pp_src = _resolve(inputs, "pole_pockets", False)
    pole_pocket_sides, pps_src = _resolve(inputs, "pole_pocket_sides", "top")
    if pole_pockets:
        side_mult = 2 if pole_pocket_sides == "top_bottom" else 1
        finishing_cost += width_ft * _d(cat.get("pole_pocket_charge_per_ft", 3.50)) * side_mult * qty
    reinforced_corners, rc_src = _resolve(inputs, "reinforced_corners", False)
    if reinforced_corners:
        finishing_cost += _d(cat.get("reinforced_corners_charge", 6.00)) * qty
    wind_slits, ws_src = _resolve(inputs, "wind_slits", False)
    if wind_slits:
        finishing_cost += _d(cat.get("wind_slit_charge", 2.00)) * qty
    specialty_sewing, ss_src = _resolve(inputs, "specialty_sewing", False)
    if specialty_sewing:
        finishing_cost += _d(cat.get("specialty_sewing_charge", 15.00)) * qty

    file_cleanup, fc_src = _resolve(inputs, "file_cleanup_needed", False)
    file_cleanup_cost = _d(shop.get("file_cleanup_fee_default", 20.00)) if file_cleanup else Decimal("0")

    hardware_charge, hw_src = _resolve(inputs, "hardware_charge", 0.0)
    hardware_cost = _d(hardware_charge)

    event_premium, ep_src = _resolve(inputs, "event_premium", False)
    step_and_repeat, sr_src = _resolve(inputs, "step_and_repeat", False)
    premium_mult = Decimal("1")
    if event_premium:
        premium_mult *= _d(cat.get("event_premium_multiplier", 1.20))
    if step_and_repeat:
        premium_mult *= _d(cat.get("step_and_repeat_multiplier", 1.30))

    rush, rush_src = _resolve(inputs, "rush", False)

    category_inputs_used = {
        "coating_type": coating_type, "double_sided": double_sided, "design_complexity": design_complexity,
        "install_complexity": install_complexity, "hems": hems, "grommets": grommets, "grommet_count": grommet_count,
        "pole_pockets": pole_pockets, "pole_pocket_sides": pole_pocket_sides, "reinforced_corners": reinforced_corners,
        "wind_slits": wind_slits, "specialty_sewing": specialty_sewing, "file_cleanup_needed": file_cleanup,
        "hardware_charge": hardware_charge, "event_premium": event_premium, "step_and_repeat": step_and_repeat, "rush": rush,
    }
    source_labels = {
        "min_billable_area_sqft": min_area_src, "coating_type": coating_src, "double_sided": ds_src,
        "print_consumable_rate_per_sqft": pc_src, "design_complexity": dc_src, "install_complexity": ic_src,
        "hems": hems_src, "grommets": grom_src, "grommet_count": gc_src, "pole_pockets": pp_src, "pole_pocket_sides": pps_src,
        "reinforced_corners": rc_src, "wind_slits": ws_src, "specialty_sewing": ss_src, "file_cleanup_needed": fc_src,
        "hardware_charge": hw_src, "event_premium": ep_src, "step_and_repeat": sr_src, "rush": rush_src,
    }

    return _finalize(
        category="banners", shop=shop, cat=cat, qty=qty, material_cost=material_cost, labor_cost=labor_cost,
        design_cost=design_cost, install_cost=install_cost, finishing_cost=finishing_cost, hardware_cost=hardware_cost,
        file_cleanup_cost=file_cleanup_cost, premium_multiplier=premium_mult, pricing_components=pricing_components,
        width_inches=width_inches, height_inches=height_inches, area_sqft_each=area_each, total_area=total_area,
        material_key=mat_label, material_sell_rate=mat_sell_rate, manual_selling_price=manual_selling_price,
        category_inputs_used=category_inputs_used, source_labels=source_labels, rush_applied=bool(rush),
    )


def calc_rigid_signs(*, shop, cat, materials_legacy, material_profile, pricing_components, width_inches, height_inches,
                     quantity, material_key, design_needed, install_needed, manual_selling_price, inputs: dict[str, Any]) -> dict[str, Any]:
    qty = max(1, int(quantity or 1))
    width_ft = _d(width_inches) / Decimal("12")
    height_ft = _d(height_inches) / Decimal("12")
    raw_area = width_ft * height_ft
    min_area, min_area_src = _resolve(inputs, "min_billable_area_sqft", cat.get("min_billable_area_sqft", 1.0))
    area_each = max(raw_area, _d(min_area))
    total_area = area_each * qty
    waste_pct = _d(cat.get("waste_percent") or 0)
    waste_area = total_area * (Decimal("1") + waste_pct / Decimal("100"))

    mat_cost_per_sqft, mat_sell_rate, mat_label = _resolve_material(material_key, materials_legacy, material_profile)
    graphic_method, gm_src = _resolve(inputs, "graphic_method", "direct_print")
    graphic_rate = _d((cat.get("graphic_method_cost_per_sqft") or {}).get(graphic_method, 1.25))

    shape_type, shape_src = _resolve(inputs, "shape_type", "standard")
    shape_mult = _d((cat.get("shape_multipliers") or {}).get(shape_type, 1.0))
    finish_quality, fq_src = _resolve(inputs, "finish_quality", "standard")
    finish_mult = _d((cat.get("finish_quality_multipliers") or {}).get(finish_quality, 1.0))
    thickness, th_src = _resolve(inputs, "thickness", "standard")
    thickness_mult = _d((cat.get("thickness_multipliers") or {}).get(thickness, 1.0))
    sidedness, side_src = _resolve(inputs, "sidedness", "single")
    ds_mult = _d(cat.get("double_sided_multiplier", 1.75)) if sidedness == "double" else Decimal("1")

    material_cost = (waste_area * mat_cost_per_sqft + waste_area * graphic_rate) * shape_mult * finish_mult * thickness_mult * ds_mult

    labor_cost = total_area * _d(cat.get("production_labor_hr_per_sqft", 0.15)) * _d(shop.get("production_hourly_rate") or 0)

    design_cost = Decimal("0")
    design_complexity, dc_src = _resolve(inputs, "design_complexity", "simple")
    if design_needed:
        design_hours = _d(cat.get("design_default_hours", 0.5)) * _design_mult(design_complexity)
        design_cost = design_hours * _d(shop.get("design_hourly_rate") or 0)

    install_complexity, ic_src = _resolve(inputs, "install_complexity", "easy")
    install_cost = _install_cost(cat, shop, total_area, install_complexity) if install_needed else Decimal("0")

    hardware_option, hw_src = _resolve(inputs, "hardware_option", "none")
    hw_opts = cat.get("hardware_options") or {}
    hardware_cost = Decimal("0")
    if hardware_option and hardware_option != "none" and hardware_option in hw_opts:
        hardware_cost = _d(hw_opts[hardware_option]["sell_price"]) * qty + _d(cat.get("hardware_handling_labor_default", 5.00))

    drill_prep, dp_src = _resolve(inputs, "drill_prep_required", False)
    finishing_cost = _d(cat.get("drill_prep_charge", 3.00)) * qty if drill_prep else Decimal("0")

    rush, rush_src = _resolve(inputs, "rush", False)

    category_inputs_used = {
        "graphic_method": graphic_method, "shape_type": shape_type, "finish_quality": finish_quality,
        "thickness": thickness, "sidedness": sidedness, "design_complexity": design_complexity,
        "install_complexity": install_complexity, "hardware_option": hardware_option,
        "drill_prep_required": drill_prep, "rush": rush,
    }
    source_labels = {
        "min_billable_area_sqft": min_area_src, "graphic_method": gm_src, "shape_type": shape_src,
        "finish_quality": fq_src, "thickness": th_src, "sidedness": side_src, "design_complexity": dc_src,
        "install_complexity": ic_src, "hardware_option": hw_src, "drill_prep_required": dp_src, "rush": rush_src,
    }

    return _finalize(
        category="rigid_signs", shop=shop, cat=cat, qty=qty, material_cost=material_cost, labor_cost=labor_cost,
        design_cost=design_cost, install_cost=install_cost, finishing_cost=finishing_cost, hardware_cost=hardware_cost,
        file_cleanup_cost=Decimal("0"), premium_multiplier=Decimal("1"), pricing_components=pricing_components,
        width_inches=width_inches, height_inches=height_inches, area_sqft_each=area_each, total_area=total_area,
        material_key=mat_label, material_sell_rate=mat_sell_rate, manual_selling_price=manual_selling_price,
        category_inputs_used=category_inputs_used, source_labels=source_labels, rush_applied=bool(rush),
    )


def calc_digital_print(*, shop, cat, materials_legacy, material_profile, pricing_components, width_inches, height_inches,
                       quantity, material_key, design_needed, install_needed, manual_selling_price, inputs: dict[str, Any]) -> dict[str, Any]:
    qty = max(1, int(quantity or 1))
    width_ft = _d(width_inches) / Decimal("12")
    height_ft = _d(height_inches) / Decimal("12")
    raw_area = width_ft * height_ft
    min_area, min_area_src = _resolve(inputs, "min_billable_area_sqft", cat.get("min_billable_area_sqft", 1.0))
    area_each = max(raw_area, _d(min_area))
    total_area = area_each * qty
    waste_pct = _d(cat.get("waste_percent") or 0)
    waste_area = total_area * (Decimal("1") + waste_pct / Decimal("100"))

    mat_cost_per_sqft, mat_sell_rate, mat_label = _resolve_material(material_key, materials_legacy, material_profile)
    quality_mode, qm_src = _resolve(inputs, "quality_mode", "standard")
    quality_mult = _d((cat.get("quality_multipliers") or {}).get(quality_mode, 1.0))
    material_cost = waste_area * mat_cost_per_sqft * quality_mult

    ink_coverage, ink_src = _resolve(inputs, "ink_coverage_percent", cat.get("base_ink_coverage_percent", 75.0))
    ink_cost = waste_area * _d(cat.get("ink_consumable_rate_per_sqft", 0.75)) * (_d(ink_coverage) / Decimal("100"))
    material_cost += ink_cost

    laminate, lam_src = _resolve(inputs, "laminate", False)
    if laminate:
        material_cost += waste_area * _d(cat.get("laminate_rate_per_sqft", 1.00))

    production_hours = max(total_area * _d(cat.get("production_labor_hr_per_sqft", 0.08)), _d(cat.get("production_labor_min_hours", 0.2)))
    labor_cost = production_hours * _d(shop.get("production_hourly_rate") or 0)

    mounted, mnt_src = _resolve(inputs, "mounted_to_substrate", False)
    if mounted:
        labor_cost += total_area * _d(cat.get("mounting_labor_hr_per_sqft", 0.08)) * _d(shop.get("production_hourly_rate") or 0)

    contour_cut, cc_src = _resolve(inputs, "contour_cut", False)
    piece_separation, ps_src = _resolve(inputs, "piece_separation", False)
    finishing_cost = Decimal("0")
    if contour_cut and piece_separation:
        finishing_cost += _d(qty) * _d(cat.get("piece_separation_labor_hr_each", 0.02)) * _d(shop.get("production_hourly_rate") or 0)

    design_cost = Decimal("0")
    design_complexity, dc_src = _resolve(inputs, "design_complexity", "simple")
    if design_needed:
        design_hours = _d(cat.get("design_default_hours", 0.5)) * _design_mult(design_complexity)
        design_cost = design_hours * _d(shop.get("design_hourly_rate") or 0)

    install_complexity, ic_src = _resolve(inputs, "install_complexity", "easy")
    install_cost = _install_cost(cat, shop, total_area, install_complexity) if install_needed else Decimal("0")

    file_cleanup, fc_src = _resolve(inputs, "file_cleanup_needed", False)
    file_cleanup_cost = _d(shop.get("file_cleanup_fee_default", 20.00)) if file_cleanup else Decimal("0")

    rush, rush_src = _resolve(inputs, "rush", False)

    category_inputs_used = {
        "quality_mode": quality_mode, "ink_coverage_percent": ink_coverage, "laminate": laminate,
        "mounted_to_substrate": mounted, "contour_cut": contour_cut, "piece_separation": piece_separation,
        "design_complexity": design_complexity, "install_complexity": install_complexity,
        "file_cleanup_needed": file_cleanup, "rush": rush,
    }
    source_labels = {
        "min_billable_area_sqft": min_area_src, "quality_mode": qm_src, "ink_coverage_percent": ink_src,
        "laminate": lam_src, "mounted_to_substrate": mnt_src, "contour_cut": cc_src, "piece_separation": ps_src,
        "design_complexity": dc_src, "install_complexity": ic_src, "file_cleanup_needed": fc_src, "rush": rush_src,
    }

    return _finalize(
        category="digital_print", shop=shop, cat=cat, qty=qty, material_cost=material_cost, labor_cost=labor_cost,
        design_cost=design_cost, install_cost=install_cost, finishing_cost=finishing_cost, hardware_cost=Decimal("0"),
        file_cleanup_cost=file_cleanup_cost, premium_multiplier=Decimal("1"), pricing_components=pricing_components,
        width_inches=width_inches, height_inches=height_inches, area_sqft_each=area_each, total_area=total_area,
        material_key=mat_label, material_sell_rate=mat_sell_rate, manual_selling_price=manual_selling_price,
        category_inputs_used=category_inputs_used, source_labels=source_labels, rush_applied=bool(rush),
    )


def calc_cut_vinyl(*, shop, cat, materials_legacy, material_profile, pricing_components, width_inches, height_inches,
                   quantity, material_key, design_needed, install_needed, manual_selling_price, inputs: dict[str, Any]) -> dict[str, Any]:
    qty = max(1, int(quantity or 1))
    width_ft = _d(width_inches) / Decimal("12")
    height_ft = _d(height_inches) / Decimal("12")
    raw_area = width_ft * height_ft
    min_area, min_area_src = _resolve(inputs, "min_billable_area_sqft", cat.get("min_billable_area_sqft", 0.5))
    area_each = max(raw_area, _d(min_area))
    total_area = area_each * qty
    waste_pct = _d(cat.get("waste_percent") or 0)
    waste_area = total_area * (Decimal("1") + waste_pct / Decimal("100"))

    mat_cost_per_sqft, mat_sell_rate, mat_label = _resolve_material(material_key, materials_legacy, material_profile)
    material_cost = waste_area * mat_cost_per_sqft

    num_colors, nc_src = _resolve(inputs, "number_of_colors", "1")
    color_mult = _d((cat.get("color_count_multipliers") or {}).get(str(num_colors), 1.0))
    weeding_complexity, wc_src = _resolve(inputs, "weeding_complexity", "simple")
    weeding_mult = _d((cat.get("weeding_complexity_multipliers") or {}).get(weeding_complexity, 1.0))
    labor_cost = total_area * _d(cat.get("production_labor_hr_per_sqft", 0.20)) * _d(shop.get("production_hourly_rate") or 0) * color_mult * weeding_mult

    masking, mask_src = _resolve(inputs, "masking", False)
    finishing_cost = waste_area * _d(cat.get("masking_tape_cost_per_sqft", 0.15)) if masking else Decimal("0")

    design_cost = Decimal("0")
    design_complexity, dc_src = _resolve(inputs, "design_complexity", "simple")
    if design_needed:
        design_hours = _d(cat.get("design_default_hours", 0.5)) * _design_mult(design_complexity)
        design_cost = design_hours * _d(shop.get("design_hourly_rate") or 0)

    install_complexity, ic_src = _resolve(inputs, "install_complexity", "easy")
    surface_type, st_src = _resolve(inputs, "surface_type", "flat")
    surface_mult = _d((cat.get("surface_type_multipliers") or {}).get(surface_type, 1.0))
    install_cost = _install_cost(cat, shop, total_area, install_complexity, extra_mult=surface_mult) if install_needed else Decimal("0")

    file_cleanup, fc_src = _resolve(inputs, "file_cleanup_needed", False)
    file_cleanup_cost = _d(shop.get("file_cleanup_fee_default", 20.00)) if file_cleanup else Decimal("0")

    rush, rush_src = _resolve(inputs, "rush", False)

    category_inputs_used = {
        "number_of_colors": num_colors, "weeding_complexity": weeding_complexity, "masking": masking,
        "design_complexity": design_complexity, "install_complexity": install_complexity, "surface_type": surface_type,
        "file_cleanup_needed": file_cleanup, "rush": rush,
    }
    source_labels = {
        "min_billable_area_sqft": min_area_src, "number_of_colors": nc_src, "weeding_complexity": wc_src,
        "masking": mask_src, "design_complexity": dc_src, "install_complexity": ic_src, "surface_type": st_src,
        "file_cleanup_needed": fc_src, "rush": rush_src,
    }

    return _finalize(
        category="cut_vinyl", shop=shop, cat=cat, qty=qty, material_cost=material_cost, labor_cost=labor_cost,
        design_cost=design_cost, install_cost=install_cost, finishing_cost=finishing_cost, hardware_cost=Decimal("0"),
        file_cleanup_cost=file_cleanup_cost, premium_multiplier=Decimal("1"), pricing_components=pricing_components,
        width_inches=width_inches, height_inches=height_inches, area_sqft_each=area_each, total_area=total_area,
        material_key=mat_label, material_sell_rate=mat_sell_rate, manual_selling_price=manual_selling_price,
        category_inputs_used=category_inputs_used, source_labels=source_labels, rush_applied=bool(rush),
    )


_DISPATCH = {
    "banners": calc_banners,
    "rigid_signs": calc_rigid_signs,
    "digital_print": calc_digital_print,
    "cut_vinyl": calc_cut_vinyl,
}


def calculate_flat_sqft_pricing(
    *, category: str, shop: dict[str, Any], cat: dict[str, Any], materials_legacy: dict[str, Any],
    material_profile: Optional[dict[str, Any]], pricing_components: list[dict[str, Any]],
    width_inches, height_inches, quantity, material_key, design_needed: bool, install_needed: bool,
    manual_selling_price, category_inputs: dict[str, Any],
) -> dict[str, Any]:
    fn = _DISPATCH[category]
    return fn(
        shop=shop, cat=cat, materials_legacy=materials_legacy, material_profile=material_profile,
        pricing_components=pricing_components, width_inches=width_inches, height_inches=height_inches,
        quantity=quantity, material_key=material_key, design_needed=design_needed, install_needed=install_needed,
        manual_selling_price=manual_selling_price, inputs=category_inputs or {},
    )
