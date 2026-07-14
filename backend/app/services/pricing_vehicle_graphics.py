"""EC9 Phase 9E-3 — Vehicle Graphics & Wrap Pricing calculator.

Pricing only (no Wrap Lab workflows/inspections/diagrams — that's EC15,
out of scope). Implements the EC09-controlling-document formula: estimated
coverage area -> waste-adjusted material area -> material/laminate/window-
perf costs -> production/design/prep/removal/install/helper labor ->
overhead -> "use higher of coverage benchmark or cost-plus result" (never
inventing a benchmark $ for `mini_van`/`other`, which have none) -> rush ->
fleet quantity -> manual override (always available, never silently
replaced by a benchmark).

Any EC09-unspecified operational assumption (mini_van/other/box_truck_24/
semi install hours; mini_van base sqft) is drawn from
`starter_defaults.VEHICLE_TYPES`/`VEHICLE_INSTALL_HOURS`, each entry already
carrying its own `is_provisional` flag — this module turns that flag into a
`calculation_warnings` entry and a `pricing_authority` source label rather
than presenting it as an exact EC09 benchmark.

A FORMULA LIBRARY invoked from `services/pricing.calculate_pricing()`.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from .pricing_flat_sqft import _apply_components, _d, _design_mult, _install_mult, _r2, _resolve

_COVERAGE_TIER_ORDER = ["spot", "partial", "half", "full"]


def _operational_tier_for_custom_pct(pct: Decimal) -> str:
    """Custom (user-typed) coverage % borrows the nearest standard tier's
    design-hours/waste%/install-hours operational defaults — labeled via
    `operational_tier_used` in the result, never silent."""
    if pct <= Decimal("20"):
        return "spot"
    if pct <= Decimal("45"):
        return "partial"
    if pct <= Decimal("65"):
        return "half"
    return "full"


def calculate_vehicle_graphics_pricing(
    *, shop: dict[str, Any], cat: dict[str, Any], pricing_components: list[dict[str, Any]],
    quantity: int, manual_selling_price: Optional[float], category_inputs: dict[str, Any],
) -> dict[str, Any]:
    inputs = category_inputs or {}
    qty = max(1, int(quantity or 1))
    warnings: list[str] = []

    vehicle_types: dict[str, Any] = cat.get("vehicle_types") or {}
    coverage_types: dict[str, Any] = cat.get("coverage_types") or {}
    install_hours_table: dict[str, Any] = cat.get("install_hours") or {}
    benchmark_prices: dict[str, Any] = cat.get("benchmark_prices") or {}
    wrap_materials: dict[str, Any] = cat.get("wrap_materials") or {}
    laminate_types: dict[str, Any] = cat.get("laminate_types") or {}
    window_perf_rates: dict[str, Any] = cat.get("window_perf_sell_per_sqft") or {}
    seam_mults: dict[str, Any] = cat.get("seam_complexity_multipliers") or {}
    prep_hours_table: dict[str, Any] = cat.get("surface_prep_hours") or {}
    removal_hours_table: dict[str, Any] = cat.get("removal_hours") or {}

    vehicle_type, vt_src = _resolve(inputs, "vehicle_type", "sedan")
    vt_cfg = vehicle_types.get(vehicle_type) or next(iter(vehicle_types.values()), {})
    if vt_cfg.get("is_provisional"):
        warnings.append(f"'{vt_cfg.get('label', vehicle_type)}' has no exact EC09 base-sqft row — using a provisional foundation estimate ({vt_cfg.get('base_sqft')} sq ft), editable in Pricing Foundation.")

    coverage_type, ct_src = _resolve(inputs, "coverage_type", "partial")
    ct_cfg = coverage_types.get(coverage_type) or coverage_types.get("partial") or {}

    if coverage_type == "custom":
        coverage_pct, cp_src = _resolve(inputs, "coverage_percent", 40.0)
    else:
        coverage_pct, cp_src = _d(ct_cfg.get("coverage_percent", 0)), "shop_default"
    coverage_pct = _d(coverage_pct)

    operational_tier = coverage_type if coverage_type in _COVERAGE_TIER_ORDER else _operational_tier_for_custom_pct(coverage_pct)
    if coverage_type == "custom":
        warnings.append(f"Custom coverage % ({coverage_pct}%) borrows the '{operational_tier}' tier's design-hours/waste%% operational defaults.")
    op_cfg = coverage_types.get(operational_tier) or {}

    base_sqft = _d(vt_cfg.get("base_sqft", 0))
    estimated_sqft = base_sqft * (coverage_pct / Decimal("100"))
    override_sqft, sqft_src = _resolve(inputs, "estimated_sqft_override", None)
    wrap_sqft = _d(override_sqft) if override_sqft is not None else estimated_sqft
    if override_sqft is None:
        warnings.append(f"Wrap area is an ESTIMATE ({_r2(wrap_sqft)} sq ft = {vt_cfg.get('label', vehicle_type)} base {base_sqft} sq ft x {coverage_pct}% coverage) — override `estimated_sqft_override` with a measured value if known.")

    waste_pct = _d(op_cfg.get("waste_percent", 12))
    waste_sqft = wrap_sqft * (Decimal("1") + waste_pct / Decimal("100"))

    material_key, mat_src = _resolve(inputs, "wrap_material", "standard_calendared_vinyl")
    mat_cfg = wrap_materials.get(material_key) or next(iter(wrap_materials.values()), {})
    material_cost = waste_sqft * _d(mat_cfg.get("shop_cost_per_sqft", 0))

    laminate_required, lam_src = _resolve(inputs, "laminate_required", False)
    laminate_type, lamt_src = _resolve(inputs, "laminate_type", "gloss")
    laminate_cost = Decimal("0")
    if laminate_required:
        lam_cfg = laminate_types.get(laminate_type) or {}
        laminate_cost = waste_sqft * _d(lam_cfg.get("cost_per_sqft", 0))

    window_perf_type, wp_src = _resolve(inputs, "window_perf_type", "none")
    window_perf_sqft, wps_src = _resolve(inputs, "window_perf_sqft", 0.0)
    window_perf_cost = Decimal("0")
    if window_perf_type != "none" and _d(window_perf_sqft) > 0:
        window_perf_cost = _d(window_perf_sqft) * _d(window_perf_rates.get(window_perf_type, 0))

    production_rate = _d(cat.get("production_hourly_rate_override") or shop.get("production_hourly_rate") or 0)
    production_hours = max(wrap_sqft * _d(cat.get("production_hr_per_sqft", 0.12)), _d(cat.get("production_min_hours", 1.0)))
    production_cost = production_hours * production_rate

    design_needed, dn_src = _resolve(inputs, "design_needed", False)
    design_complexity, dc_src = _resolve(inputs, "design_complexity", "simple")
    design_cost = Decimal("0")
    if design_needed:
        design_hours = _d(op_cfg.get("design_base_hours", 1.5)) * _design_mult(design_complexity)
        design_cost = design_hours * _d(cat.get("design_hourly_rate_override") or shop.get("design_hourly_rate") or 0)

    file_cleanup_needed, fc_src = _resolve(inputs, "file_cleanup_needed", False)
    file_cleanup_cost = _d(shop.get("file_cleanup_fee_default", 20.00)) if file_cleanup_needed else Decimal("0")

    surface_prep, sp_src = _resolve(inputs, "surface_prep", "none")
    prep_hours = _d(prep_hours_table.get(surface_prep, 0))

    removal_required, rr_src = _resolve(inputs, "removal_required", "none")
    removal_hours = _d(removal_hours_table.get(removal_required, 0))
    install_rate = _d(cat.get("install_hourly_rate_override") or shop.get("install_hourly_rate") or 0)
    removal_cost = Decimal("0")
    if removal_required != "none":
        removal_cost = removal_hours * install_rate + _d(cat.get("removal_consumables_allowance", 8.00))

    install_needed, in_src = _resolve(inputs, "install_needed", True)
    install_difficulty, id_src = _resolve(inputs, "install_difficulty", "easy")
    seam_complexity, sc_src = _resolve(inputs, "seam_complexity", "basic")
    helper_required, hr_src = _resolve(inputs, "helper_required", False)
    install_cost = Decimal("0")
    helper_cost = Decimal("0")
    install_hours_is_provisional = False
    if install_needed:
        vehicle_install_row = install_hours_table.get(vehicle_type) or {}
        base_install_hours = _d((vehicle_install_row.get("hours") or {}).get(operational_tier, 0))
        install_hours_is_provisional = bool(vehicle_install_row.get("is_provisional"))
        if install_hours_is_provisional:
            warnings.append(f"'{vt_cfg.get('label', vehicle_type)}' has no exact EC09 install-hours row for '{operational_tier}' — using a provisional foundation estimate ({base_install_hours} hr), editable in Pricing Foundation.")
        install_hours = base_install_hours * _install_mult(install_difficulty) * _d(seam_mults.get(seam_complexity, 1.0))
        install_hours += prep_hours
        install_cost = max(install_hours * install_rate, _d(cat.get("install_min_charge", 125.00)))
        if helper_required:
            helper_cost = install_hours * _d(cat.get("helper_hourly_rate", 35.00))

    travel_required, tr_src = _resolve(inputs, "travel_required", False)
    travel_miles, tm_src = _resolve(inputs, "travel_miles", 0.0)
    travel_cost = _d(travel_miles) * _d(cat.get("travel_cost_per_mile", 1.00)) if travel_required else Decimal("0")

    rush, rush_src = _resolve(inputs, "rush", False)
    rush_percent, rp_src = _resolve(inputs, "rush_percent", cat.get("rush_default_percent", 30.0))

    labor_cost = production_cost + removal_cost + install_cost + helper_cost
    finishing_cost = laminate_cost + window_perf_cost

    base_cost = material_cost + labor_cost + design_cost + file_cleanup_cost + finishing_cost
    components_cost, components_applied = _apply_components(pricing_components, base_cost)
    base_cost += components_cost

    overhead_pct_override = cat.get("overhead_percent_override")
    overhead_pct = _d(overhead_pct_override if overhead_pct_override is not None else (shop.get("default_overhead_percent") or 0))
    overhead_cost = base_cost * (overhead_pct / Decimal("100"))
    true_cost = base_cost + overhead_cost + travel_cost

    markup = _d(cat.get("default_markup_multiplier") or 2.40)
    minimum_charge = _d(cat.get("minimum_charge") or 150.00)
    cost_plus_price = true_cost * markup

    benchmark_price: Optional[Decimal] = None
    benchmark_row = benchmark_prices.get(vehicle_type)
    if coverage_type in _COVERAGE_TIER_ORDER and benchmark_row and coverage_type in benchmark_row:
        benchmark_price = _d(benchmark_row[coverage_type])

    candidates = [cost_plus_price, minimum_charge]
    if benchmark_price is not None:
        candidates.append(benchmark_price)
    pre_rush_price = max(candidates)

    rush_premium = pre_rush_price * (_d(rush_percent) / Decimal("100")) if rush else Decimal("0")
    price_per_vehicle = pre_rush_price + rush_premium
    suggested_price = price_per_vehicle * qty  # fleet/multi-vehicle quantity multiplies the total, per EC09

    global_min = _d(shop.get("minimum_order_amount") or 0)
    suggested_price = max(suggested_price, global_min)

    if manual_selling_price is not None and manual_selling_price >= 0:
        selling_price = _d(manual_selling_price)
        method_used = "manual_override"
    else:
        selling_price = suggested_price
        method_used = "vehicle_benchmark" if (benchmark_price is not None and benchmark_price >= cost_plus_price) else "vehicle_cost_plus"

    profit_amount = selling_price - (true_cost * qty)
    profit_margin_percent = (profit_amount / selling_price) * Decimal("100") if selling_price > 0 else Decimal("0")

    breakdown = [{"label": f"Material ({mat_cfg.get('label', material_key)})", "amount": _r2(material_cost)}]
    if laminate_cost > 0: breakdown.append({"label": "Laminate", "amount": _r2(laminate_cost)})
    if window_perf_cost > 0: breakdown.append({"label": "Window perf", "amount": _r2(window_perf_cost)})
    breakdown.append({"label": "Production labor", "amount": _r2(production_cost)})
    if design_cost > 0: breakdown.append({"label": "Design", "amount": _r2(design_cost)})
    if file_cleanup_cost > 0: breakdown.append({"label": "File cleanup", "amount": _r2(file_cleanup_cost)})
    if removal_cost > 0: breakdown.append({"label": "Removal", "amount": _r2(removal_cost)})
    if install_cost > 0: breakdown.append({"label": "Install", "amount": _r2(install_cost)})
    if helper_cost > 0: breakdown.append({"label": "Second installer / helper", "amount": _r2(helper_cost)})
    for comp in components_applied:
        breakdown.append({"label": comp["name"] or "Pricing component", "amount": comp["amount"]})
    breakdown.append({"label": "Overhead", "amount": _r2(overhead_cost)})
    if travel_cost > 0: breakdown.append({"label": "Travel", "amount": _r2(travel_cost)})
    breakdown.append({"label": "True cost (per vehicle)", "amount": _r2(true_cost)})
    if benchmark_price is not None: breakdown.append({"label": "Package/benchmark candidate", "amount": _r2(benchmark_price)})
    breakdown.append({"label": "Cost-plus candidate", "amount": _r2(cost_plus_price)})
    rush_applied = bool(rush)
    if rush_applied:
        breakdown.append({"label": f"Rush ({float(rush_percent):.0f}%)", "amount": _r2(rush_premium)})
    if qty > 1: breakdown.append({"label": f"Fleet quantity ({qty} vehicles)", "amount": _r2(price_per_vehicle * (qty - 1))})
    breakdown.append({"label": "Suggested price", "amount": _r2(suggested_price)})
    breakdown.append({"label": "Selling price", "amount": _r2(selling_price)})
    breakdown.append({"label": "Profit", "amount": _r2(profit_amount)})

    category_inputs_used = {
        "vehicle_type": vehicle_type, "coverage_type": coverage_type, "coverage_percent": float(coverage_pct),
        "estimated_sqft_override": override_sqft, "wrap_material": material_key, "laminate_required": laminate_required,
        "laminate_type": laminate_type, "window_perf_type": window_perf_type, "window_perf_sqft": window_perf_sqft,
        "design_needed": design_needed, "design_complexity": design_complexity, "file_cleanup_needed": file_cleanup_needed,
        "surface_prep": surface_prep, "removal_required": removal_required, "install_needed": install_needed,
        "install_difficulty": install_difficulty, "seam_complexity": seam_complexity, "helper_required": helper_required,
        "travel_required": travel_required, "travel_miles": travel_miles, "rush": rush, "rush_percent": rush_percent,
        "operational_tier_used": operational_tier,
    }
    source_labels = {
        "vehicle_type": vt_src, "coverage_type": ct_src, "coverage_percent": cp_src, "estimated_sqft_override": sqft_src,
        "wrap_material": mat_src, "laminate_required": lam_src, "laminate_type": lamt_src, "window_perf_type": wp_src,
        "window_perf_sqft": wps_src, "design_needed": dn_src, "design_complexity": dc_src, "file_cleanup_needed": fc_src,
        "surface_prep": sp_src, "removal_required": rr_src, "install_needed": in_src, "install_difficulty": id_src,
        "seam_complexity": sc_src, "helper_required": hr_src, "travel_required": tr_src, "travel_miles": tm_src,
        "rush": rush_src, "rush_percent": rp_src,
    }

    return {
        "category": "vehicle_graphics",
        "width_inches": 0.0, "height_inches": 0.0,
        "quantity": qty,
        "area_sqft_each": _r2(wrap_sqft), "area_sqft_total": _r2(wrap_sqft * qty),
        "material_key": mat_cfg.get("label", material_key),
        "material_sell_rate_per_sqft": mat_cfg.get("sell_rate_per_sqft"),
        "material_cost": _r2(material_cost),
        "labor_cost": _r2(labor_cost),
        "design_cost": _r2(design_cost),
        "setup_cost": 0.0,
        "finishing_cost": _r2(finishing_cost),
        "hardware_cost": 0.0,
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
        "quantity_discount_percent": 0,
        "rush_applied": rush_applied,
        "pricing_components_applied": components_applied,
        # Vehicle-specific additive keys
        "benchmark_price_used": _r2(benchmark_price) if benchmark_price is not None else None,
        "cost_plus_price": _r2(cost_plus_price),
        "vehicle_type_is_provisional": bool(vt_cfg.get("is_provisional")),
        "install_hours_is_provisional": install_hours_is_provisional,
        "estimated_sqft_was_overridden": override_sqft is not None,
        "removal_cost": _r2(removal_cost),
        "helper_cost": _r2(helper_cost),
        "travel_cost": _r2(travel_cost),
        "calculation_warnings": warnings,
        "category_inputs_used": category_inputs_used,
        "source_labels": source_labels,
        "breakdown": breakdown,
        "shop_defaults_used": {
            "production_hourly_rate": cat.get("production_hourly_rate_override"),
            "design_hourly_rate": cat.get("design_hourly_rate_override"),
            "install_hourly_rate": cat.get("install_hourly_rate_override"),
            "default_overhead_percent": overhead_pct_override if overhead_pct_override is not None else shop.get("default_overhead_percent"),
            "target_profit_margin_percent": shop.get("target_profit_margin_percent"),
            "default_markup_multiplier": cat.get("default_markup_multiplier"),
            "minimum_order_amount": shop.get("minimum_order_amount"),
            "rush_fee_percent": cat.get("rush_default_percent"),
        },
    }
