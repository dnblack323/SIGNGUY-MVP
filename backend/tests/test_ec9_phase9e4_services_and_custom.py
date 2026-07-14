"""EC9 Phase 9E-4 — Services (existing `pricing_services.py` engine, now wired
into the dispatcher) + Custom / Miscellaneous (new strict manual fallback).

Services: reuses the pre-existing, unmodified formula set (labor/travel/
trip/equipment/subcontract/permit/rush/minimum-charge). This file tests the
NEW dispatcher wiring, the NEW optional Labor Role override, and exercises
every pricing_method + add-on already implemented in `pricing_services.py`.

Custom / Miscellaneous: strict EC09 fallback — `unit_price x quantity`, no
automated cost-estimation engine, optional `unit_cost_manual` for
profit/margin display only (never changes price), optional markup shown as
an informational reference only (never auto-applied), configured minimum
applied only when it exceeds the subtotal, manual override stays separate.

Credit-Conservation Rule in effect: targeted pytest only. No `testing_agent`,
no full regression suite, no browser automation.
"""
from __future__ import annotations
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from server import app
from app.core.db import db
from app.deps import get_current_user
from app.services.pricing import calculate_pricing
from app.services.starter_defaults import build_starter_pack


def _override(u):
    async def _get(): return {**u}
    return _get


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear(): app.dependency_overrides.pop(get_current_user, None)


def _calc_services(settings, quantity=1, category_inputs=None, manual_selling_price=None, **kw):
    return calculate_pricing(settings=settings, category="services", width_inches=None, height_inches=None,
                              quantity=quantity, category_inputs=category_inputs or {},
                              manual_selling_price=manual_selling_price, **kw)


def _calc_custom(settings, quantity=1, category_inputs=None, manual_selling_price=None, **kw):
    return calculate_pricing(settings=settings, category="custom", width_inches=None, height_inches=None,
                              quantity=quantity, category_inputs=category_inputs or {},
                              manual_selling_price=manual_selling_price, **kw)


# ============================================================
# Dispatcher wiring
# ============================================================

def test_services_dispatcher_wiring_reaches_real_engine():
    settings = build_starter_pack()
    r = _calc_services(settings, category_inputs={"service_type": "general_labor"})
    assert r["category"] == "services"
    assert "service_rate_is_provisional" in r  # unique to pricing_services.py output


def test_custom_dispatcher_wiring_reaches_new_engine():
    settings = build_starter_pack()
    r = _calc_custom(settings, category_inputs={"unit_price": 10, "quantity": 1})
    assert r["category"] == "custom"
    assert "minimum_charge_applied" in r  # unique to pricing_custom.py output


# ============================================================
# Services — pricing methods
# ============================================================

def test_hourly_pricing():
    settings = build_starter_pack()
    r = _calc_services(settings, category_inputs={"service_type": "general_labor", "estimated_hours": 2, "crew_size": 1, "complexity": "easy"})
    assert r["labor_cost"] == 56.0  # 2h x 1 x 1.0 x $28/hr
    assert r["pricing_method_used"] == "hourly"
    assert r["selling_price"] == 115.92  # (56 * 1.15) * 1.80


def test_per_crew_hour_pricing():
    settings = build_starter_pack()
    r = _calc_services(settings, category_inputs={"service_type": "general_labor", "pricing_method": "per_crew_hour",
                                                    "estimated_hours": 2, "crew_size": 3, "complexity": "easy"})
    assert r["labor_cost"] == 168.0  # 2h x 3 crew x $28/hr
    assert r["pricing_method_used"] == "per_crew_hour"
    assert r["selling_price"] == 347.76  # (168 * 1.15) * 1.80


def test_per_unit_pricing():
    settings = build_starter_pack()
    r = _calc_services(settings, category_inputs={"service_type": "general_labor", "pricing_method": "per_unit", "unit_rate": 15.0, "units": 10})
    assert r["labor_cost"] == 150.0
    assert r["pricing_method_used"] == "per_unit"
    assert r["selling_price"] == 310.5  # (150 * 1.15) * 1.80


def test_flat_fee_pricing_bypasses_markup():
    settings = build_starter_pack()
    r = _calc_services(settings, category_inputs={"service_type": "artwork_setup"})  # default_pricing_method=flat_fee, flat_fee_default=25
    assert r["pricing_method_used"] == "flat_fee"
    assert r["labor_cost"] == 0.0
    assert r["selling_price"] == 25.0  # all-in flat fee, never run through markup


def test_pass_through_pricing_uses_marked_up_vendor_cost_as_primary():
    settings = build_starter_pack()
    r = _calc_services(settings, category_inputs={
        "service_type": "general_labor", "pricing_method": "pass_through",
        "outsourced_required": True, "vendor_cost": 200.0, "markup_applies": True, "subcontract_markup_percent_override": 20,
    })
    assert r["pricing_method_used"] == "pass_through"
    assert r["selling_price"] == 240.0  # 200 * 1.20


def test_hybrid_pricing_uses_higher_of_labor_or_flat_floor():
    settings = build_starter_pack()
    r = _calc_services(settings, category_inputs={
        "service_type": "general_labor", "pricing_method": "hybrid",
        "estimated_hours": 5, "crew_size": 1, "complexity": "easy", "flat_fee_amount": 50.0,
    })
    assert r["labor_cost"] == 140.0  # 5h x $28/hr > $50 flat floor
    assert r["selling_price"] == 140.0


# ============================================================
# Services — minimum charge, add-ons, rush
# ============================================================

def test_minimum_charge_applied_when_cost_plus_result_is_below_it():
    settings = build_starter_pack()
    r = _calc_services(settings, category_inputs={"service_type": "consultation", "estimated_hours": 0.1})
    assert r["minimum_charge_applied"] is True
    assert r["selling_price"] == 50.0  # consultation's $50 minimum > tiny cost-plus result


def test_travel_and_trip_charges_add_to_final_price():
    settings = build_starter_pack()
    baseline = _calc_services(settings, category_inputs={"service_type": "site_survey", "estimated_hours": 1})
    with_addons = _calc_services(settings, category_inputs={
        "service_type": "site_survey", "estimated_hours": 1,
        "travel_required": True, "travel_miles": 20, "travel_time_hours": 0,
        "travel_cost_per_mile_override": 1.0, "travel_sell_rate_per_mile_override": 1.5,
        "trip_charge_applies": True, "trip_count": 2, "trip_charge_amount": 15.0,
    })
    assert with_addons["travel_price_addon"] == 30.0  # 20mi x $1.50
    assert with_addons["trip_charge_total"] == 30.0   # 2 x $15
    assert with_addons["selling_price"] > baseline["selling_price"]
    assert with_addons["selling_price"] == 292.65


def test_equipment_addon_increases_price():
    settings = build_starter_pack()
    r = _calc_services(settings, category_inputs={"service_type": "general_labor", "estimated_hours": 0,
                                                    "equipment_required": True, "equipment_type": "scissor_lift",
                                                    "equipment_rate": 50.0, "equipment_quantity": 2})
    assert r["hardware_cost"] == 100.0  # 2 days x $50/day
    assert r["selling_price"] == 207.0  # (100 * 1.15) * 1.80


def test_materials_addon_increases_price():
    settings = build_starter_pack()
    r = _calc_services(settings, category_inputs={"service_type": "general_labor", "estimated_hours": 0,
                                                    "materials_required": True, "material_quantity": 3, "material_cost_manual": 10.0})
    assert r["material_cost"] == 30.0
    assert r["selling_price"] == 62.1  # (30 * 1.15) * 1.80


def test_design_and_setup_addons_increase_price():
    settings = build_starter_pack()
    baseline = _calc_services(settings, category_inputs={"service_type": "general_labor", "estimated_hours": 0})
    r = _calc_services(settings, category_inputs={"service_type": "general_labor", "estimated_hours": 0,
                                                    "design_needed": True, "design_complexity": "complex",
                                                    "setup_required": True, "setup_fee": 40.0})
    assert r["design_cost"] == 63.75  # 0.5hr x 1.5 (complex) x $85/hr
    assert r["setup_cost"] == 40.0
    assert r["selling_price"] > baseline["selling_price"]


def test_outsourced_vendor_costs_addon_on_non_pass_through_method():
    settings = build_starter_pack()
    baseline = _calc_services(settings, category_inputs={"service_type": "general_labor", "estimated_hours": 0})
    r = _calc_services(settings, category_inputs={"service_type": "general_labor", "estimated_hours": 0,
                                                    "outsourced_required": True, "vendor_cost": 100.0,
                                                    "markup_applies": True, "subcontract_markup_percent_override": 10})
    assert r["outsourced_price_addon"] == 110.0  # 100 * 1.10
    assert r["selling_price"] > baseline["selling_price"]


def test_permit_addon_increases_price():
    settings = build_starter_pack()
    baseline = _calc_services(settings, category_inputs={"service_type": "general_labor", "estimated_hours": 0})
    r = _calc_services(settings, category_inputs={"service_type": "general_labor", "estimated_hours": 0,
                                                    "permit_required": True, "permit_fee": 30.0})
    assert r["permit_cost"] == 30.0
    assert r["selling_price"] > baseline["selling_price"]


def test_rush_increases_final_price():
    settings = build_starter_pack()
    normal = _calc_services(settings, category_inputs={"service_type": "general_labor", "estimated_hours": 2})
    rushed = _calc_services(settings, category_inputs={"service_type": "general_labor", "estimated_hours": 2, "rush": True})
    assert rushed["rush_applied"] is True
    assert rushed["selling_price"] > normal["selling_price"]


# ============================================================
# Services — Labor Role override (EC9 Phase 9E-4 new capability)
# ============================================================

def test_labor_role_override_uses_matching_configured_shop_rate():
    settings = build_starter_pack()
    # general_labor presets to production_hourly_rate ($28/hr); overriding
    # the labor role to "design" must use design_hourly_rate ($85/hr) instead.
    r = _calc_services(settings, category_inputs={"service_type": "general_labor", "labor_role": "design",
                                                    "estimated_hours": 1, "crew_size": 1, "complexity": "easy"})
    assert r["labor_cost"] == 85.0
    assert r["labor_role_used"] == "design"
    assert r["calculation_warnings"] == []


def test_labor_role_not_selected_preserves_service_type_preset():
    settings = build_starter_pack()
    r = _calc_services(settings, category_inputs={"service_type": "general_labor", "estimated_hours": 1, "crew_size": 1, "complexity": "easy"})
    assert r["labor_cost"] == 28.0  # unchanged production_hourly_rate preset
    assert r["labor_role_used"] is None


def test_labor_role_helper_unconfigured_warns_and_preserves_manual_pricing():
    settings = build_starter_pack()
    r = _calc_services(settings, category_inputs={"service_type": "general_labor", "labor_role": "helper", "estimated_hours": 4})
    assert r["labor_cost"] == 0.0  # helper_hourly_rate defaults to $0.00 — never silently substituted
    assert any("helper" in w.lower() and "no configured rate" in w.lower() for w in r["calculation_warnings"])
    # Manual pricing still fully available despite the $0 labor role rate.
    manual = _calc_services(settings, category_inputs={"service_type": "general_labor", "labor_role": "helper", "estimated_hours": 4},
                             manual_selling_price=99.0)
    assert manual["selling_price"] == 99.0
    assert manual["pricing_method_used"] == "manual_override"


def test_labor_role_with_configured_rate_produces_no_warning():
    settings = build_starter_pack()
    settings["shop_defaults"]["helper_hourly_rate"] = 22.0  # tenant configures it
    r = _calc_services(settings, category_inputs={"service_type": "general_labor", "labor_role": "helper", "estimated_hours": 2})
    assert r["labor_cost"] == 44.0
    assert r["calculation_warnings"] == []


# ============================================================
# Services — manual override, hidden fields
# ============================================================

def test_services_manual_override_remains_separate():
    settings = build_starter_pack()
    r = _calc_services(settings, category_inputs={"service_type": "general_labor", "estimated_hours": 2}, manual_selling_price=500.0)
    assert r["selling_price"] == 500.0
    assert r["pricing_method_used"] == "manual_override"
    assert r["suggested_price"] != 500.0


def test_services_hidden_width_height_fields_do_not_affect_result():
    settings = build_starter_pack()
    without = _calc_services(settings, category_inputs={"service_type": "general_labor", "estimated_hours": 2})
    with_hidden = calculate_pricing(settings=settings, category="services", width_inches=999, height_inches=999,
                                     quantity=1, category_inputs={"service_type": "general_labor", "estimated_hours": 2})
    assert with_hidden["selling_price"] == without["selling_price"]
    assert with_hidden["area_sqft_total"] == 0.0


# ============================================================
# Custom / Miscellaneous — strict manual fallback
# ============================================================

def test_custom_unit_price_times_quantity():
    settings = build_starter_pack()
    r = _calc_custom(settings, quantity=4, category_inputs={"unit_price": 30.0})
    assert r["selling_price"] == 120.0
    assert r["pricing_method_used"] == "unit_price_x_quantity"
    assert r["minimum_charge_applied"] is False


def test_custom_unit_cost_affects_profit_margin_only_never_price():
    settings = build_starter_pack()
    r = _calc_custom(settings, quantity=1, category_inputs={"unit_price": 100.0, "unit_cost_manual": 40.0})
    assert r["selling_price"] == 100.0  # entered unit price stays authoritative
    assert r["true_cost"] == 40.0
    assert r["profit_amount"] == 60.0
    assert r["profit_margin_percent"] == 60.0


def test_custom_minimum_floor_applied_only_when_it_exceeds_subtotal():
    settings = build_starter_pack()
    below_min = _calc_custom(settings, quantity=2, category_inputs={"unit_price": 5.0})  # subtotal $10 < $50 category minimum
    assert below_min["minimum_charge_applied"] is True
    assert below_min["selling_price"] == 50.0

    above_min = _calc_custom(settings, quantity=10, category_inputs={"unit_price": 20.0})  # subtotal $200 > minimum
    assert above_min["minimum_charge_applied"] is False
    assert above_min["selling_price"] == 200.0

    custom_min_override = _calc_custom(settings, quantity=2, category_inputs={"unit_price": 5.0, "minimum_charge_override": 80.0})
    assert custom_min_override["selling_price"] == 80.0


def test_custom_manual_override_remains_separate_from_subtotal():
    settings = build_starter_pack()
    r = _calc_custom(settings, quantity=5, category_inputs={"unit_price": 10.0}, manual_selling_price=999.0)
    assert r["suggested_price"] == 50.0  # the unit_price x quantity subtotal, preserved separately
    assert r["selling_price"] == 999.0
    assert r["pricing_method_used"] == "manual_override"


def test_custom_markup_field_is_informational_only_never_auto_applied():
    settings = build_starter_pack()
    r = _calc_custom(settings, quantity=1, category_inputs={"unit_price": 100.0, "markup_percent_adjustment": 10})
    assert r["selling_price"] == 100.0  # entered unit price remains authoritative — never switched to cost-plus
    assert r["markup_adjusted_subtotal_informational"] == 110.0
    assert any("informational only" in w.lower() for w in r["calculation_warnings"])


def test_custom_does_not_use_generic_square_foot_logic():
    settings = build_starter_pack()
    r = calculate_pricing(settings=settings, category="custom", width_inches=100, height_inches=50, quantity=3,
                           category_inputs={"unit_price": 20.0})
    assert r["area_sqft_total"] == 0.0
    assert r["material_cost"] == 0.0
    assert r["labor_cost"] == 0.0
    assert r["selling_price"] == 60.0  # 20 x 3, width/height completely ignored


def test_custom_hidden_fields_do_not_affect_result():
    settings = build_starter_pack()
    without = _calc_custom(settings, quantity=2, category_inputs={"unit_price": 30.0})
    with_hidden = _calc_custom(settings, quantity=2, category_inputs={"unit_price": 30.0, "some_unused_field": "ignored"})
    assert with_hidden["selling_price"] == without["selling_price"]


def test_custom_never_invents_a_price_when_nothing_entered():
    settings = build_starter_pack()
    r = _calc_custom(settings, quantity=1, category_inputs={})
    assert r["selling_price"] == 50.0  # only the category's own configured minimum — never a guessed number
    assert r["unit_price"] == 0.0


# ============================================================
# Tenant isolation + integer-cent money boundaries
# ============================================================

@pytest.mark.asyncio
async def test_services_and_custom_tenant_isolation_holds():
    t1 = f"t-9e4-{uuid.uuid4().hex[:6]}"
    t2 = f"t-9e4-{uuid.uuid4().hex[:6]}"
    u1 = {"id": f"u-{uuid.uuid4().hex[:6]}", "tenant_id": t1, "email": f"{uuid.uuid4().hex[:6]}@x.com", "role": "owner", "is_active": True}
    u2 = {"id": f"u-{uuid.uuid4().hex[:6]}", "tenant_id": t2, "email": f"{uuid.uuid4().hex[:6]}@x.com", "role": "owner", "is_active": True}
    await db.tenants.insert_one({"id": t1, "slug": t1, "name": "N1"})
    await db.tenants.insert_one({"id": t2, "slug": t2, "name": "N2"})
    async with await _client(u1) as c:
        r1 = await c.patch("/api/pricing/settings/categories/services", json={"minimum_charge": 9999.0})
        assert r1.status_code == 200
        r2 = await c.patch("/api/pricing/settings/categories/custom", json={"minimum_charge": 8888.0})
        assert r2.status_code == 200
    async with await _client(u2) as c:
        settings2 = (await c.get("/api/pricing/settings")).json()
        assert settings2["category_defaults"]["services"]["minimum_charge"] != 9999.0
        assert settings2["category_defaults"]["custom"]["minimum_charge"] != 8888.0
    async with await _client(u1) as c:
        calc = await c.post("/api/pricing/calculate", json={"category": "custom", "quantity": 1,
                                                              "category_inputs": {"unit_price": 1.0}})
        assert calc.status_code == 200
        assert calc.json()["minimum_charge_applied"] is True
        assert calc.json()["selling_price"] == 8888.0
    _clear()


def test_money_boundary_integer_cents_services_and_custom():
    from app.services.pricing_snapshot import build_calculated_snapshot
    settings = build_starter_pack()
    svc = _calc_services(settings, category_inputs={"service_type": "general_labor", "estimated_hours": 2}, manual_selling_price=149.99)
    snap = build_calculated_snapshot(calc_result=svc, quantity=1)
    assert snap["calculated_unit_price_cents"] == 14999

    cust = _calc_custom(settings, quantity=1, category_inputs={"unit_price": 0.0}, manual_selling_price=0.01)
    snap2 = build_calculated_snapshot(calc_result=cust, quantity=1)
    assert snap2["calculated_unit_price_cents"] == 1
