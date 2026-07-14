"""EC9 Phase 9E-4 — Services calculator (General Labor, Graphic Design,
Artwork Setup, File Cleanup, Consultation, Site Survey, Measurement,
Delivery, Installation, Removal, Maintenance/Repair, Vehicle Graphics
Install, Wrap Install, Service Call Labor, Project Management, Permit
Handling, Custom Flat-Fee Service).

Pricing only — no scheduling/production-stage tracking here. `service_type`
is a preset selector (pre-fills pricing_method/rate/minimum); `pricing_method`
(hourly / per_crew_hour / per_unit / flat_fee / cost_plus / pass_through /
hybrid / manual) is what actually controls which fields matter and which
formula path runs — never square-foot logic forced onto an hourly/flat-fee
service.

Reuses: EC7 canonical Materials (via the already-resolved `material_profile`
dict — same mechanism `pricing_flat_sqft.py` uses), Pricing Components,
Global Pricing Foundation shop rates, and the same `_d`/`_r2`/`_resolve`/
`_apply_components`/`_install_mult`/`_design_mult` helpers as every other
Phase 9E formula module.

A FORMULA LIBRARY invoked from `services/pricing.calculate_pricing()`.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from .pricing_flat_sqft import _apply_components, _d, _design_mult, _install_mult, _r2, _resolve

_HOURLY_METHODS = {"hourly", "per_crew_hour", "cost_plus"}

# EC9 Phase 9E-4 — optional Labor Role override. Maps a role selection to the
# matching global Pricing Foundation shop rate — never a second rate table.
# `helper` and `specialty_technician` have no EC09-given rate (seeded at
# $0.00 in `starter_defaults.SHOP_DEFAULTS`, never invented); selecting one
# while it is still unconfigured surfaces a warning rather than silently
# substituting a different rate.
LABOR_ROLES: dict[str, str] = {
    "design": "design_hourly_rate",
    "production": "production_hourly_rate",
    "installer": "install_hourly_rate",
    "helper": "helper_hourly_rate",
    "project_manager": "admin_hourly_rate",
    "admin": "admin_hourly_rate",
    "specialty_technician": "specialty_technician_hourly_rate",
}


def calculate_services_pricing(
    *, shop: dict[str, Any], cat: dict[str, Any], pricing_components: list[dict[str, Any]],
    quantity: int, manual_selling_price: Optional[float], category_inputs: dict[str, Any],
    material_profile: Optional[dict[str, Any]],
) -> dict[str, Any]:
    inputs = category_inputs or {}
    qty = max(1, int(quantity or 1))
    warnings: list[str] = []

    service_types: dict[str, Any] = cat.get("service_types") or {}
    equipment_types: dict[str, Any] = cat.get("equipment_types") or {}

    service_type, stype_src = _resolve(inputs, "service_type", "general_labor")
    st_cfg = service_types.get(service_type) or service_types.get("general_labor") or {}
    if st_cfg.get("is_rate_provisional"):
        warnings.append(f"'{st_cfg.get('label', service_type)}' has no distinct EC09 rate — borrowing the nearest documented Pricing Foundation rate as a provisional, editable starter assumption.")

    pricing_method, pm_src = _resolve(inputs, "pricing_method", st_cfg.get("default_pricing_method", "hourly"))

    # ---- Labor / revenue-candidate side ----
    estimated_hours, hrs_src = _resolve(inputs, "estimated_hours", st_cfg.get("default_hours", 1.0))
    crew_size, crew_src = _resolve(inputs, "crew_size", 1)
    crew_size = max(1, int(crew_size or 1))
    complexity, cx_src = _resolve(inputs, "complexity", "easy")

    if "hourly_rate_default" in st_cfg:
        default_rate = st_cfg["hourly_rate_default"]
    else:
        default_rate = shop.get(st_cfg.get("rate_shop_key", "production_hourly_rate"), 0)

    # EC9 Phase 9E-4 — optional Labor Role override. If selected, it replaces
    # the service_type preset rate with the matching configured shop rate
    # (still overridable below by an explicit hourly_rate_override). Never
    # silently substitutes another rate when the role's own rate is
    # unconfigured ($0.00) — warns instead, and pricing for this portion
    # stays at $0 until the shop configures that rate or enters a manual
    # override, preserving existing service_type preset behavior otherwise.
    labor_role, role_src = _resolve(inputs, "labor_role", None)
    if labor_role and labor_role in LABOR_ROLES:
        role_rate_key = LABOR_ROLES[labor_role]
        role_rate = shop.get(role_rate_key, 0)
        default_rate = role_rate
        if _d(role_rate) <= 0:
            warnings.append(
                f"Labor role '{labor_role.replace('_', ' ')}' has no configured rate ('{role_rate_key}' is $0.00 in "
                "Pricing Foundation) — this portion will price at $0 until you configure that rate or enter a "
                "manual hourly rate override / manual selling price."
            )
    hourly_rate, rate_src = _resolve(inputs, "hourly_rate_override", default_rate)

    unit_rate, ur_src = _resolve(inputs, "unit_rate", 0.0)
    units, units_src = _resolve(inputs, "units", qty)
    flat_fee_amount, ffa_src = _resolve(inputs, "flat_fee_amount", st_cfg.get("flat_fee_default", 0.0))

    labor_cost = Decimal("0")
    revenue_candidate: Optional[Decimal] = None
    if pricing_method in _HOURLY_METHODS:
        hours_effective = _d(estimated_hours) * crew_size * _install_mult(complexity)
        labor_cost = hours_effective * _d(hourly_rate)
    elif pricing_method == "per_unit":
        labor_cost = _d(units) * _d(unit_rate)
    elif pricing_method in ("flat_fee", "custom_flat_fee"):
        revenue_candidate = _d(flat_fee_amount)  # already an all-in sell price, not run through markup again
    elif pricing_method == "hybrid":
        hours_effective = _d(estimated_hours) * crew_size * _install_mult(complexity)
        labor_cost = hours_effective * _d(hourly_rate)
        revenue_candidate = max(labor_cost, _d(flat_fee_amount))  # cost_plus floor still applied below too
    elif pricing_method == "pass_through":
        pass  # handled entirely via outsourced_price_addon below
    elif pricing_method == "manual":
        pass  # relies purely on the universal manual_selling_price override

    # ---- Materials (canonical EC7 Material via already-resolved profile) ----
    materials_required, matreq_src = _resolve(inputs, "materials_required", False)
    material_quantity, matqty_src = _resolve(inputs, "material_quantity", 1.0)
    material_cost_manual, matcost_src = _resolve(inputs, "material_cost_manual", 0.0)
    material_cost = Decimal("0")
    material_label = None
    if materials_required:
        if material_profile:
            material_cost = _d(material_profile.get("normalized_cost_basis", 0)) * _d(material_quantity)
            material_label = material_profile.get("material_name") or material_profile.get("material_id")
        else:
            material_cost = _d(material_cost_manual) * _d(material_quantity)

    # ---- Equipment ----
    equipment_required, eqreq_src = _resolve(inputs, "equipment_required", False)
    equipment_type, eqtype_src = _resolve(inputs, "equipment_type", "ladder")
    eq_cfg = equipment_types.get(equipment_type) or {}
    equipment_rate, eqrate_src = _resolve(inputs, "equipment_rate", eq_cfg.get("rate_per_day", 0.0))
    equipment_quantity, eqqty_src = _resolve(inputs, "equipment_quantity", 1.0)
    equipment_cost = _d(equipment_rate) * _d(equipment_quantity) if equipment_required else Decimal("0")

    # ---- Design add-on (independent of `service_type == graphic_design`) ----
    design_required, dn_src = _resolve(inputs, "design_needed", False)
    design_complexity, dc_src = _resolve(inputs, "design_complexity", "simple")
    design_cost = Decimal("0")
    if design_required:
        design_cost = _d(cat.get("design_default_hours", 0.5)) * _design_mult(design_complexity) * _d(shop.get("design_hourly_rate", 0))

    # ---- Setup add-on ----
    setup_required, sr_src = _resolve(inputs, "setup_required", False)
    setup_fee, sf_src = _resolve(inputs, "setup_fee", shop.get("setup_fee_default", 0.0))
    setup_cost = _d(setup_fee) if setup_required else Decimal("0")

    # ---- Travel ----
    travel_required, tr_src = _resolve(inputs, "travel_required", False)
    travel_miles, tm_src = _resolve(inputs, "travel_miles", 0.0)
    travel_time_hours, tth_src = _resolve(inputs, "travel_time_hours", 0.0)
    travel_cost_per_mile, tcpm_src = _resolve(inputs, "travel_cost_per_mile_override", cat.get("travel_cost_per_mile", 0.0))
    travel_sell_rate_per_mile, tspm_src = _resolve(inputs, "travel_sell_rate_per_mile_override", cat.get("travel_sell_rate_per_mile", 0.0))
    travel_cost = Decimal("0")
    travel_price_addon = Decimal("0")
    if travel_required:
        travel_cost = _d(travel_miles) * _d(travel_cost_per_mile) + _d(travel_time_hours) * _d(shop.get("travel_hourly_rate", 0))
        sell_rate = _d(travel_sell_rate_per_mile) if _d(travel_sell_rate_per_mile) > 0 else _d(travel_cost_per_mile)
        travel_price_addon = _d(travel_miles) * sell_rate + _d(travel_time_hours) * _d(shop.get("travel_hourly_rate", 0))
        if _d(travel_cost_per_mile) == 0 and _d(travel_sell_rate_per_mile) == 0 and _d(travel_miles) > 0:
            warnings.append("Travel mileage rate is not yet configured (EC09 leaves this tenant-configurable with no default $) — travel mileage is charging $0 until set in Pricing Foundation \u2192 Services.")

    # ---- Trip charge ----
    trip_charge_applies, tca_src = _resolve(inputs, "trip_charge_applies", False)
    trip_count, tc_src = _resolve(inputs, "trip_count", 1)
    trip_charge_amount, tcam_src = _resolve(inputs, "trip_charge_amount", cat.get("trip_charge_default", 0.0))
    trip_charge_total = _d(trip_count) * _d(trip_charge_amount) if trip_charge_applies else Decimal("0")
    if trip_charge_applies and _d(trip_charge_amount) == 0:
        warnings.append("Trip charge is not yet configured (EC09 leaves this tenant-configurable with no default $) — charging $0 until set in Pricing Foundation \u2192 Services.")

    # ---- Outsourced / vendor pass-through ----
    outsourced_required, outreq_src = _resolve(inputs, "outsourced_required", False)
    vendor_name, vendor_src = _resolve(inputs, "vendor_name", None)
    vendor_cost, vc_src = _resolve(inputs, "vendor_cost", 0.0)
    markup_applies, ma_src = _resolve(inputs, "markup_applies", True)
    subcontract_markup_percent, smp_src = _resolve(inputs, "subcontract_markup_percent_override", cat.get("subcontract_markup_percent", 0.0))
    outsourced_price_addon = Decimal("0")
    if outsourced_required:
        outsourced_price_addon = _d(vendor_cost) * (Decimal("1") + _d(subcontract_markup_percent) / Decimal("100")) if markup_applies else _d(vendor_cost)
        if markup_applies and _d(subcontract_markup_percent) == 0:
            warnings.append("Subcontract markup % is not yet configured (EC09 leaves this tenant-configurable with no default %) — vendor cost is being passed through at $0 markup until set.")

    # ---- Permit / access pass-through (zero-margin, added equally to cost and price) ----
    permit_required, pr_src = _resolve(inputs, "permit_required", False)
    permit_fee, pf_src = _resolve(inputs, "permit_fee", 0.0)
    permit_cost = _d(permit_fee) if permit_required else Decimal("0")

    rush, rush_src = _resolve(inputs, "rush", False)
    rush_percent, rp_src = _resolve(inputs, "rush_percent", cat.get("rush_default_percent", 25.0))

    apply_minimum_charge, amc_src = _resolve(inputs, "apply_minimum_charge", True)
    if st_cfg.get("minimum_charge") is not None:
        default_minimum = st_cfg["minimum_charge"]
    elif service_type == "installation":
        default_minimum = shop.get("install_minimum_charge", 0.0)
    else:
        default_minimum = cat.get("default_minimum_charge", 25.0)
    minimum_charge, min_src = _resolve(inputs, "minimum_charge_override", default_minimum)

    base_cost = material_cost + labor_cost + equipment_cost + design_cost + setup_cost + permit_cost
    if outsourced_required and pricing_method != "pass_through":
        base_cost += _d(vendor_cost)  # tracked as true cost even when the addon above already covers the sell side
    components_cost, components_applied = _apply_components(pricing_components, base_cost)
    base_cost += components_cost

    overhead_pct = _d(shop.get("default_overhead_percent") or 0)
    overhead_cost = base_cost * (overhead_pct / Decimal("100"))
    true_cost = base_cost + overhead_cost + travel_cost

    markup = _d(cat.get("default_markup_multiplier") or 1.80)
    cost_plus_price = true_cost * markup

    if pricing_method == "pass_through":
        primary_candidate = outsourced_price_addon
        outsourced_price_addon = Decimal("0")  # already the primary candidate — avoid double-adding below
    elif pricing_method in ("flat_fee", "custom_flat_fee", "hybrid"):
        primary_candidate = revenue_candidate if revenue_candidate is not None else cost_plus_price
    elif pricing_method == "manual":
        primary_candidate = cost_plus_price
    else:  # hourly / per_crew_hour / per_unit / cost_plus
        primary_candidate = cost_plus_price

    pre_addon_price = primary_candidate
    if apply_minimum_charge:
        pre_addon_price = max(pre_addon_price, _d(minimum_charge))

    price_with_addons = pre_addon_price + travel_price_addon + trip_charge_total + outsourced_price_addon

    rush_premium = price_with_addons * (_d(rush_percent) / Decimal("100")) if rush else Decimal("0")
    suggested_price = price_with_addons + rush_premium

    global_min = _d(shop.get("minimum_order_amount") or 0)
    suggested_price = max(suggested_price, global_min)

    if manual_selling_price is not None and manual_selling_price >= 0:
        selling_price = _d(manual_selling_price)
        method_used = "manual_override"
    else:
        selling_price = suggested_price
        method_used = pricing_method

    profit_amount = selling_price - true_cost
    profit_margin_percent = (profit_amount / selling_price) * Decimal("100") if selling_price > 0 else Decimal("0")

    breakdown = [{"label": f"{st_cfg.get('label', service_type)} labor", "amount": _r2(labor_cost)}]
    if material_cost > 0: breakdown.append({"label": f"Materials{f' ({material_label})' if material_label else ''}", "amount": _r2(material_cost)})
    if equipment_cost > 0: breakdown.append({"label": f"Equipment ({eq_cfg.get('label', equipment_type)})", "amount": _r2(equipment_cost)})
    if design_cost > 0: breakdown.append({"label": "Design add-on", "amount": _r2(design_cost)})
    if setup_cost > 0: breakdown.append({"label": "Setup fee", "amount": _r2(setup_cost)})
    if permit_cost > 0: breakdown.append({"label": "Permit / access fee", "amount": _r2(permit_cost)})
    for comp in components_applied:
        breakdown.append({"label": comp["name"] or "Pricing component", "amount": comp["amount"]})
    breakdown.append({"label": "Overhead", "amount": _r2(overhead_cost)})
    breakdown.append({"label": "True cost", "amount": _r2(true_cost)})
    breakdown.append({"label": "Cost-plus candidate", "amount": _r2(cost_plus_price)})
    if apply_minimum_charge and _d(minimum_charge) > primary_candidate:
        breakdown.append({"label": f"Minimum charge applied (${_r2(_d(minimum_charge))})", "amount": _r2(_d(minimum_charge) - primary_candidate)})
    if travel_price_addon > 0: breakdown.append({"label": "Travel", "amount": _r2(travel_price_addon)})
    if trip_charge_total > 0: breakdown.append({"label": "Trip charge", "amount": _r2(trip_charge_total)})
    if outsourced_price_addon > 0: breakdown.append({"label": f"Outsourced{f' ({vendor_name})' if vendor_name else ''}", "amount": _r2(outsourced_price_addon)})
    rush_applied = bool(rush)
    if rush_applied:
        breakdown.append({"label": f"Rush ({float(rush_percent):.1f}%)", "amount": _r2(rush_premium)})
    breakdown.append({"label": "Suggested price", "amount": _r2(suggested_price)})
    breakdown.append({"label": "Selling price", "amount": _r2(selling_price)})
    breakdown.append({"label": "Profit", "amount": _r2(profit_amount)})

    category_inputs_used = {
        "service_type": service_type, "pricing_method": pricing_method, "estimated_hours": estimated_hours,
        "crew_size": crew_size, "complexity": complexity, "labor_role": labor_role,
        "hourly_rate_override": hourly_rate, "unit_rate": unit_rate,
        "units": units, "flat_fee_amount": flat_fee_amount, "materials_required": materials_required,
        "material_quantity": material_quantity, "material_cost_manual": material_cost_manual,
        "equipment_required": equipment_required, "equipment_type": equipment_type, "equipment_rate": equipment_rate,
        "equipment_quantity": equipment_quantity, "design_needed": design_required, "design_complexity": design_complexity,
        "setup_required": setup_required, "setup_fee": setup_fee, "travel_required": travel_required,
        "travel_miles": travel_miles, "travel_time_hours": travel_time_hours, "trip_charge_applies": trip_charge_applies,
        "trip_count": trip_count, "trip_charge_amount": trip_charge_amount, "outsourced_required": outsourced_required,
        "vendor_name": vendor_name, "vendor_cost": vendor_cost, "markup_applies": markup_applies,
        "subcontract_markup_percent_override": subcontract_markup_percent, "permit_required": permit_required,
        "permit_fee": permit_fee, "rush": rush, "rush_percent": rush_percent, "apply_minimum_charge": apply_minimum_charge,
        "minimum_charge_override": minimum_charge,
    }
    source_labels = {
        "service_type": stype_src, "pricing_method": pm_src, "estimated_hours": hrs_src, "crew_size": crew_src,
        "complexity": cx_src, "labor_role": role_src, "hourly_rate_override": rate_src, "unit_rate": ur_src, "units": units_src,
        "flat_fee_amount": ffa_src, "materials_required": matreq_src, "material_quantity": matqty_src,
        "material_cost_manual": matcost_src, "equipment_required": eqreq_src, "equipment_type": eqtype_src,
        "equipment_rate": eqrate_src, "equipment_quantity": eqqty_src, "design_needed": dn_src,
        "design_complexity": dc_src, "setup_required": sr_src, "setup_fee": sf_src, "travel_required": tr_src,
        "travel_miles": tm_src, "travel_time_hours": tth_src, "trip_charge_applies": tca_src, "trip_count": tc_src,
        "trip_charge_amount": tcam_src, "outsourced_required": outreq_src, "vendor_name": vendor_src,
        "vendor_cost": vc_src, "markup_applies": ma_src, "subcontract_markup_percent_override": smp_src,
        "permit_required": pr_src, "permit_fee": pf_src, "rush": rush_src, "rush_percent": rp_src,
        "apply_minimum_charge": amc_src, "minimum_charge_override": min_src,
    }

    return {
        "category": "services",
        "width_inches": 0.0, "height_inches": 0.0,
        "quantity": qty,
        "area_sqft_each": 0.0, "area_sqft_total": 0.0,
        "material_key": material_label or st_cfg.get("label", service_type),
        "material_sell_rate_per_sqft": None,
        "material_cost": _r2(material_cost),
        "labor_cost": _r2(labor_cost),
        "design_cost": _r2(design_cost),
        "setup_cost": _r2(setup_cost),
        "finishing_cost": 0.0,
        "hardware_cost": _r2(equipment_cost),
        "install_cost": 0.0,
        "outsourcing_cost": _r2(outsourced_price_addon + (_d(vendor_cost) if (outsourced_required and pricing_method != "pass_through") else Decimal("0"))),
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
        # Services-specific additive keys
        "cost_plus_price": _r2(cost_plus_price),
        "minimum_charge_applied": bool(apply_minimum_charge and _d(minimum_charge) > primary_candidate),
        "travel_cost": _r2(travel_cost),
        "travel_price_addon": _r2(travel_price_addon),
        "trip_charge_total": _r2(trip_charge_total),
        "vendor_cost": _r2(_d(vendor_cost)) if outsourced_required else None,
        "outsourced_price_addon": _r2(outsourced_price_addon),
        "permit_cost": _r2(permit_cost),
        "service_rate_is_provisional": bool(st_cfg.get("is_rate_provisional")),
        "labor_role_used": labor_role,
        "calculation_warnings": warnings,
        "category_inputs_used": category_inputs_used,
        "source_labels": source_labels,
        "breakdown": breakdown,
        "shop_defaults_used": {
            "production_hourly_rate": shop.get("production_hourly_rate"),
            "design_hourly_rate": shop.get("design_hourly_rate"),
            "install_hourly_rate": shop.get("install_hourly_rate"),
            "removal_hourly_rate": shop.get("removal_hourly_rate"),
            "consultation_hourly_rate": shop.get("consultation_hourly_rate"),
            "site_survey_hourly_rate": shop.get("site_survey_hourly_rate"),
            "admin_hourly_rate": shop.get("admin_hourly_rate"),
            "travel_hourly_rate": shop.get("travel_hourly_rate"),
            "default_overhead_percent": shop.get("default_overhead_percent"),
            "target_profit_margin_percent": shop.get("target_profit_margin_percent"),
            "default_markup_multiplier": cat.get("default_markup_multiplier"),
            "minimum_order_amount": shop.get("minimum_order_amount"),
            "rush_fee_percent": cat.get("rush_default_percent"),
        },
    }
