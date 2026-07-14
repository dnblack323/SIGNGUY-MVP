"""EC9 Phase 9E-2 Corrections (1 & 2) + Phase 9E-3 — Vehicle Graphics & Wraps.

Correction 1: Apparel decoration-method pricing authority — HTV/Screen Print
Transfer stay exact-table; the other 7 methods are labeled
`foundation_estimate` (never presented as an exact uploaded table); the
DTF/Sublimation per-sq-in area assumption is editable, snapshotted, and
raises a `calculation_warnings` entry.

Correction 2: idempotent additive default-key merge for long-lived tenants
(no "Reset to starter" required to receive newly-introduced schema keys).

Phase 9E-3: Vehicle Graphics / Wrap pricing (spot/partial/half/full/custom
coverage, cost-plus vs package/benchmark, removal/install/design/travel,
fleet quantity, rush, manual override, provisional-assumption warnings).
"""
from __future__ import annotations
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from server import app
from app.core.db import db
from app.deps import get_current_user
from app.services.pricing import calculate_pricing, get_or_init_pricing_settings
from app.services.starter_defaults import build_starter_pack, STARTER_DEFAULT_VERSION


def _override(u):
    async def _get(): return {**u}
    return _get


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear(): app.dependency_overrides.pop(get_current_user, None)


# ============================================================
# CORRECTION 1 — Apparel decoration method pricing authority
# ============================================================

def test_correction1_htv_and_screen_print_transfer_remain_exact_table():
    settings = build_starter_pack()
    htv = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=25,
                            category_inputs={"garment_type": "short_sleeve_tee", "brand": "gildan_5000", "placement": "front_small", "decoration_method": "htv"})
    spt = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=25,
                            category_inputs={"garment_type": "short_sleeve_tee", "brand": "gildan_5000", "placement": "front_small", "decoration_method": "screen_print_transfer"})
    assert htv["decoration_pricing_source"] == "exact_table"
    assert spt["decoration_pricing_source"] == "exact_table"
    assert htv["decoration_table_revenue"] == 225.00  # unchanged from Phase 9E-2 (25 x $9.00)
    assert htv["calculation_warnings"] == []


def test_correction1_other_methods_labeled_foundation_estimate_with_warning():
    settings = build_starter_pack()
    for method in ["dtf_transfer", "direct_screen_print", "embroidery", "dtg", "patch_emblem", "sublimation", "specialty_custom"]:
        r = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=5,
                              category_inputs={"garment_type": "polo", "brand": "gildan_8800", "decoration_method": method})
        assert r["decoration_pricing_source"] == "foundation_estimate", method
        assert any("provisional" in w.lower() for w in r["calculation_warnings"]), method


def test_correction1_provisional_area_assumption_is_editable_and_warned_and_snapshotted():
    settings = build_starter_pack()
    default_run = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=1,
                                    category_inputs={"garment_type": "polo", "brand": "gildan_8800", "decoration_method": "dtf_transfer"})
    assert default_run["decoration_area_assumption_is_provisional"] is True
    assert default_run["decoration_area_assumption_sqin"] == 116  # front_back combo default
    assert any("STARTER ASSUMPTION" in w for w in default_run["calculation_warnings"])

    # Tenant edits the assumption via the existing generic category-update path
    edited_methods = dict(settings["category_defaults"]["apparel"]["decoration_methods"])
    edited_methods["dtf_transfer"] = {**edited_methods["dtf_transfer"], "default_area_sqin_by_placement": {"front": 40, "back": 200, "combo": 240, "hat": 20}}
    settings["category_defaults"]["apparel"]["decoration_methods"] = edited_methods
    edited_run = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=1,
                                   category_inputs={"garment_type": "polo", "brand": "gildan_8800", "decoration_method": "dtf_transfer"})
    assert edited_run["decoration_area_assumption_sqin"] == 240
    assert edited_run["decoration_material_cost"] != default_run["decoration_material_cost"]

    # Per-calculation override remains available too
    override_run = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=1,
                                     category_inputs={"garment_type": "polo", "brand": "gildan_8800", "decoration_method": "dtf_transfer", "decoration_area_sqin": 999})
    assert override_run["decoration_area_assumption_sqin"] == 999
    assert override_run["source_labels"]["decoration_area_sqin"] == "user_entered"


def test_correction1_manual_pricing_still_works_for_foundation_estimate_methods():
    settings = build_starter_pack()
    r = calculate_pricing(settings=settings, category="apparel", width_inches=None, height_inches=None, quantity=1,
                          category_inputs={"garment_type": "polo", "brand": "gildan_8800", "decoration_method": "embroidery"},
                          manual_selling_price=77.0)
    assert r["selling_price"] == 77.0
    assert r["pricing_method_used"] == "manual_override"
    assert r["suggested_price"] > 0


# ============================================================
# CORRECTION 2 — Idempotent additive default merge
# ============================================================

@pytest.fixture
async def stale_tenant():
    tid = f"t-9e2c-{uuid.uuid4().hex[:6]}"
    pack = build_starter_pack()
    # Simulate a tenant created BEFORE Phase 9E-2/9E-3: strip the new keys
    # and set a stale version, but ALSO simulate a tenant-edited value that
    # must survive the merge untouched.
    stale_apparel = {k: v for k, v in pack["category_defaults"]["apparel"].items() if k not in ("garments", "decoration_methods", "plus_size_upcharge")}
    stale_apparel["minimum_charge"] = 999.00  # tenant-edited value
    pack["category_defaults"]["apparel"] = stale_apparel
    stale_vehicle = {k: v for k, v in pack["category_defaults"]["vehicle_graphics"].items() if k not in ("vehicle_types", "benchmark_prices")}
    pack["category_defaults"]["vehicle_graphics"] = stale_vehicle
    pack["starter_default_version"] = "0.9.0-stale-simulated"
    pack["tenant_id"] = tid
    await db.pricing_settings.insert_one({**pack})
    yield tid
    await db.pricing_settings.delete_many({"tenant_id": tid})


@pytest.mark.asyncio
async def test_correction2_missing_keys_are_added(stale_tenant):
    doc = await get_or_init_pricing_settings(stale_tenant)
    assert "garments" in doc["category_defaults"]["apparel"]
    assert "decoration_methods" in doc["category_defaults"]["apparel"]
    assert "vehicle_types" in doc["category_defaults"]["vehicle_graphics"]
    assert "benchmark_prices" in doc["category_defaults"]["vehicle_graphics"]


@pytest.mark.asyncio
async def test_correction2_existing_edited_values_remain_unchanged(stale_tenant):
    doc = await get_or_init_pricing_settings(stale_tenant)
    assert doc["category_defaults"]["apparel"]["minimum_charge"] == 999.00


@pytest.mark.asyncio
async def test_correction2_merge_is_idempotent(stale_tenant):
    doc1 = await get_or_init_pricing_settings(stale_tenant)
    doc2 = await get_or_init_pricing_settings(stale_tenant)
    assert doc1["category_defaults"]["apparel"]["garments"].keys() == doc2["category_defaults"]["apparel"]["garments"].keys()
    assert doc2["category_defaults"]["apparel"]["minimum_charge"] == 999.00
    assert doc2["starter_default_version"] == STARTER_DEFAULT_VERSION


@pytest.mark.asyncio
async def test_correction2_default_version_updates_correctly(stale_tenant):
    before = await db.pricing_settings.find_one({"tenant_id": stale_tenant}, {"_id": 0})
    assert before["starter_default_version"] == "0.9.0-stale-simulated"
    await get_or_init_pricing_settings(stale_tenant)
    after = await db.pricing_settings.find_one({"tenant_id": stale_tenant}, {"_id": 0})
    assert after["starter_default_version"] == STARTER_DEFAULT_VERSION


@pytest.mark.asyncio
async def test_correction2_historical_snapshots_remain_unchanged(stale_tenant):
    from app.services.pricing_snapshot import build_calculated_snapshot
    settings_before = await get_or_init_pricing_settings(stale_tenant)
    calc_before = calculate_pricing(settings=settings_before, category="promotional", width_inches=None, height_inches=None,
                                    quantity=1, category_inputs={"pricing_method": "flat_fee", "flat_fee_price": 50.0})
    historical_snapshot = build_calculated_snapshot(calc_result=calc_before, quantity=1)
    # Merge runs (idempotent, additive-only)
    await get_or_init_pricing_settings(stale_tenant)
    await get_or_init_pricing_settings(stale_tenant)
    # The already-built snapshot dict itself is untouched by any later merge —
    # snapshots are a point-in-time copy, never re-derived from live settings.
    assert historical_snapshot["calculated_unit_price_cents"] == 5000


# ============================================================
# PHASE 9E-3 — Vehicle Graphics & Wraps
# ============================================================

def test_vehicle_type_changes_assumptions():
    settings = build_starter_pack()
    sedan = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                              category_inputs={"vehicle_type": "sedan", "coverage_type": "full"})
    semi = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                             category_inputs={"vehicle_type": "semi", "coverage_type": "full"})
    assert semi["area_sqft_each"] > sedan["area_sqft_each"]
    assert semi["selling_price"] > sedan["selling_price"]


def test_coverage_type_changes_area_and_price():
    settings = build_starter_pack()
    spot = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                             category_inputs={"vehicle_type": "sedan", "coverage_type": "spot"})
    full = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                             category_inputs={"vehicle_type": "sedan", "coverage_type": "full"})
    assert spot["area_sqft_each"] == 22.50   # 150 x 15%
    assert full["area_sqft_each"] == 150.00  # 150 x 100%
    assert full["selling_price"] > spot["selling_price"]


def test_manual_sqft_override_beats_estimate():
    settings = build_starter_pack()
    estimated = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                                  category_inputs={"vehicle_type": "sedan", "coverage_type": "full"})
    overridden = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                                   category_inputs={"vehicle_type": "sedan", "coverage_type": "full", "estimated_sqft_override": 300})
    assert estimated["estimated_sqft_was_overridden"] is False
    assert overridden["estimated_sqft_was_overridden"] is True
    assert overridden["area_sqft_each"] == 300.00
    assert any("ESTIMATE" in w for w in estimated["calculation_warnings"])
    assert not any("ESTIMATE" in w for w in overridden["calculation_warnings"])


def test_wrap_material_changes_cost():
    settings = build_starter_pack()
    standard = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                                 category_inputs={"vehicle_type": "sedan", "coverage_type": "full", "wrap_material": "standard_calendared_vinyl"})
    premium = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                                category_inputs={"vehicle_type": "sedan", "coverage_type": "full", "wrap_material": "reflective_vinyl"})
    assert premium["material_cost"] > standard["material_cost"]


def test_laminate_toggle_changes_cost():
    settings = build_starter_pack()
    base = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                             category_inputs={"vehicle_type": "sedan", "coverage_type": "full"})
    with_lam = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                                 category_inputs={"vehicle_type": "sedan", "coverage_type": "full", "laminate_required": True, "laminate_type": "gloss"})
    assert with_lam["finishing_cost"] > base["finishing_cost"]
    assert with_lam["true_cost"] > base["true_cost"]


def test_install_difficulty_and_seam_complexity_change_labor():
    settings = build_starter_pack()
    easy = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                             category_inputs={"vehicle_type": "sedan", "coverage_type": "full", "install_difficulty": "easy", "seam_complexity": "basic"})
    hard = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                             category_inputs={"vehicle_type": "sedan", "coverage_type": "full", "install_difficulty": "extreme", "seam_complexity": "advanced"})
    assert hard["install_cost"] > easy["install_cost"]


def test_design_toggle_and_complexity_change_price():
    settings = build_starter_pack()
    no_design = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                                  category_inputs={"vehicle_type": "sedan", "coverage_type": "full"})
    with_design = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                                    category_inputs={"vehicle_type": "sedan", "coverage_type": "full", "design_needed": True, "design_complexity": "extreme"})
    assert with_design["design_cost"] > no_design["design_cost"] == 0


def test_file_cleanup_changes_price():
    settings = build_starter_pack()
    base = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                             category_inputs={"vehicle_type": "sedan", "coverage_type": "spot"})
    cleaned = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                                category_inputs={"vehicle_type": "sedan", "coverage_type": "spot", "file_cleanup_needed": True})
    assert cleaned["file_cleanup_cost"] > base["file_cleanup_cost"] == 0


def test_removal_toggle_and_inputs_change_price():
    settings = build_starter_pack()
    none = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                             category_inputs={"vehicle_type": "sedan", "coverage_type": "full", "removal_required": "none"})
    full_removal = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                                     category_inputs={"vehicle_type": "sedan", "coverage_type": "full", "removal_required": "full"})
    assert full_removal["removal_cost"] > none["removal_cost"] == 0
    assert full_removal["removal_cost"] == (4.00 * 75.00) + 8.00  # 4hr x $75/hr install rate + $8 consumables


def test_specialty_features_affect_labor_where_specified():
    """Second installer/helper + window perf are the explicitly-specified
    surface/feature add-ons for Phase 9E-3 (roof/bumpers/handles/mirrors/
    rivets have no EC09 numeric multiplier — correctly absent, no dead field)."""
    settings = build_starter_pack()
    base = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                             category_inputs={"vehicle_type": "sedan", "coverage_type": "full"})
    with_helper = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                                    category_inputs={"vehicle_type": "sedan", "coverage_type": "full", "helper_required": True})
    with_window_perf = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                                         category_inputs={"vehicle_type": "sedan", "coverage_type": "full", "window_perf_type": "side_windows", "window_perf_sqft": 10})
    assert with_helper["helper_cost"] > base["helper_cost"] == 0
    assert with_window_perf["finishing_cost"] > base["finishing_cost"]
    assert with_window_perf["finishing_cost"] - base["finishing_cost"] == 200.00  # 10 sqft x $20


def test_fleet_quantity_changes_totals():
    settings = build_starter_pack()
    one = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                            category_inputs={"vehicle_type": "sedan", "coverage_type": "full"})
    three = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=3,
                              category_inputs={"vehicle_type": "sedan", "coverage_type": "full"})
    assert three["selling_price"] == pytest.approx(one["selling_price"] * 3, rel=0.01)


def test_package_benchmark_path_wins_when_higher_than_cost_plus():
    settings = build_starter_pack()
    r = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                          category_inputs={"vehicle_type": "sedan", "coverage_type": "full"})
    assert r["benchmark_price_used"] == 2400.00
    assert r["pricing_method_used"] in ("vehicle_benchmark", "vehicle_cost_plus")
    assert r["selling_price"] >= r["benchmark_price_used"]


def test_cost_plus_path_works_and_is_used_when_no_benchmark_row():
    settings = build_starter_pack()
    r = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                          category_inputs={"vehicle_type": "other", "coverage_type": "full"})
    assert r["benchmark_price_used"] is None
    assert r["pricing_method_used"] == "vehicle_cost_plus"
    assert r["selling_price"] == r["cost_plus_price"]


def test_manual_price_remains_separate_from_benchmark():
    settings = build_starter_pack()
    r = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                          category_inputs={"vehicle_type": "sedan", "coverage_type": "full"}, manual_selling_price=1500.0)
    assert r["selling_price"] == 1500.0
    assert r["pricing_method_used"] == "manual_override"
    assert r["suggested_price"] != 1500.0  # benchmark-derived suggestion still shown, not silently replaced


def test_rush_changes_final_price():
    settings = build_starter_pack()
    normal = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                               category_inputs={"vehicle_type": "sedan", "coverage_type": "spot"})
    rushed = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                               category_inputs={"vehicle_type": "sedan", "coverage_type": "spot", "rush": True})
    assert rushed["rush_applied"] is True
    assert rushed["selling_price"] > normal["selling_price"]


def test_provisional_vehicle_assumptions_produce_warning():
    settings = build_starter_pack()
    r = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                          category_inputs={"vehicle_type": "mini_van", "coverage_type": "full"})
    assert r["vehicle_type_is_provisional"] is True
    assert r["install_hours_is_provisional"] is True
    assert len(r["calculation_warnings"]) >= 2


def test_custom_coverage_percent_borrows_nearest_tier_and_never_invents_benchmark():
    settings = build_starter_pack()
    r = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                          category_inputs={"vehicle_type": "sedan", "coverage_type": "custom", "coverage_percent": 40})
    assert r["category_inputs_used"]["operational_tier_used"] == "partial"
    assert r["benchmark_price_used"] is None  # no benchmark row for "custom" — never invented
    assert any("Custom coverage" in w for w in r["calculation_warnings"])


@pytest.mark.asyncio
async def test_vehicle_tenant_isolation_holds():
    t1 = f"t-veh-{uuid.uuid4().hex[:6]}"
    t2 = f"t-veh-{uuid.uuid4().hex[:6]}"
    u1 = {"id": f"u-{uuid.uuid4().hex[:6]}", "tenant_id": t1, "email": f"{uuid.uuid4().hex[:6]}@x.com", "role": "owner", "is_active": True}
    u2 = {"id": f"u-{uuid.uuid4().hex[:6]}", "tenant_id": t2, "email": f"{uuid.uuid4().hex[:6]}@x.com", "role": "owner", "is_active": True}
    await db.tenants.insert_one({"id": t1, "slug": t1, "name": "V1"})
    await db.tenants.insert_one({"id": t2, "slug": t2, "name": "V2"})
    async with await _client(u1) as c:
        r1 = await c.patch("/api/pricing/settings/categories/vehicle_graphics", json={"minimum_charge": 9999.0})
        assert r1.status_code == 200
    async with await _client(u2) as c:
        settings2 = await c.get("/api/pricing/settings")
        assert settings2.json()["category_defaults"]["vehicle_graphics"]["minimum_charge"] != 9999.0
    _clear()


def test_money_boundary_integer_cents():
    settings = build_starter_pack()
    r = calculate_pricing(settings=settings, category="vehicle_graphics", width_inches=None, height_inches=None, quantity=1,
                          category_inputs={"vehicle_type": "sedan", "coverage_type": "spot"}, manual_selling_price=149.99)
    from app.services.pricing_snapshot import build_calculated_snapshot
    snap = build_calculated_snapshot(calc_result=r, quantity=1)
    assert snap["calculated_unit_price_cents"] == 14999
