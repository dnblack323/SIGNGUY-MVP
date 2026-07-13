"""EC9 Phase 9E-1 — Core Flat & Square-Foot Product calculators.

Covers the 4 category-specific formula engines (banners, rigid_signs,
digital_print, cut_vinyl): seeded defaults, conditional-field pricing
effects, minimum billable area, quantity tiers, rush, source labels, and
reuse of canonical EC7 Materials (via Material Pricing Profiles) + Pricing
Components through the real `/api/pricing/calculate` endpoint. Pure-formula
assertions use `calculate_pricing()` directly against a fresh starter pack
(no DB), matching the existing `test_ec9_phase9b_global_foundation.py`
convention; DB-backed reuse tests use the ASGI test client.
"""
from __future__ import annotations
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from server import app
from app.core.db import db
from app.deps import get_current_user
from app.services.pricing import calculate_pricing
from app.services.pricing_snapshot import build_calculated_snapshot
from app.services.starter_defaults import build_starter_pack


def _override(u):
    async def _get(): return {**u}
    return _get


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear(): app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def e1_ctx():
    ta = f"t-9e1-{uuid.uuid4().hex[:6]}"
    ua = {"id": f"u-a-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
          "email": f"a-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_one({"id": ta, "slug": ta, "name": "T9E1"})
    yield {"ua": ua, "ta": ta}
    _clear()


# ---------- Banners ----------

def test_banners_minimum_billable_area_enforced():
    settings = build_starter_pack()
    tiny = calculate_pricing(settings=settings, category="banners", width_inches=6, height_inches=6, quantity=1)
    assert tiny["area_sqft_each"] == 4.0  # 0.25 sqft raw -> clamped to the 4.0 sqft minimum


def test_banners_grommets_add_cost_and_are_source_labeled():
    settings = build_starter_pack()
    base = calculate_pricing(settings=settings, category="banners", width_inches=48, height_inches=96, quantity=1)
    with_grommets = calculate_pricing(settings=settings, category="banners", width_inches=48, height_inches=96, quantity=1,
                                      category_inputs={"grommets": "standard"})
    assert with_grommets["finishing_cost"] > base["finishing_cost"]
    assert with_grommets["source_labels"]["grommets"] == "user_entered"
    assert with_grommets["source_labels"]["hems"] == "shop_default"  # not supplied -> falls back


def test_banners_double_sided_different_side_increases_material_cost():
    settings = build_starter_pack()
    single = calculate_pricing(settings=settings, category="banners", width_inches=48, height_inches=96, quantity=1, material_key="banner_13oz")
    double = calculate_pricing(settings=settings, category="banners", width_inches=48, height_inches=96, quantity=1, material_key="banner_13oz",
                               category_inputs={"double_sided": "different_side"})
    assert double["material_cost"] > single["material_cost"]


def test_banners_rush_applies_shop_rush_percent():
    settings = build_starter_pack()
    normal = calculate_pricing(settings=settings, category="banners", width_inches=48, height_inches=96, quantity=1)
    rushed = calculate_pricing(settings=settings, category="banners", width_inches=48, height_inches=96, quantity=1,
                               category_inputs={"rush": True})
    assert rushed["rush_applied"] is True
    assert rushed["suggested_price"] > normal["suggested_price"]


def test_banners_quantity_tier_discount_applies_at_25():
    settings = build_starter_pack()
    qty1 = calculate_pricing(settings=settings, category="banners", width_inches=48, height_inches=96, quantity=1)
    qty25 = calculate_pricing(settings=settings, category="banners", width_inches=48, height_inches=96, quantity=25)
    assert qty1["quantity_discount_percent"] == 0
    assert qty25["quantity_discount_percent"] == 15
    # per-unit suggested price should be lower once the tier discount kicks in
    assert (qty25["suggested_price"] / 25) < (qty1["suggested_price"] / 1)


def test_banners_manual_price_keeps_suggested_price_and_cost_visible():
    settings = build_starter_pack()
    manual = calculate_pricing(settings=settings, category="banners", width_inches=48, height_inches=96, quantity=1,
                               manual_selling_price=999.0)
    assert manual["selling_price"] == 999.0
    assert manual["pricing_method_used"] == "manual_override"
    assert manual["suggested_price"] > 0  # suggested price still computed/visible, not erased
    assert manual["true_cost"] > 0
    assert manual["profit_amount"] == round(999.0 - manual["true_cost"], 2)


def test_banners_snapshot_compatibility_preserved():
    settings = build_starter_pack()
    calc = calculate_pricing(settings=settings, category="banners", width_inches=48, height_inches=96, quantity=2)
    snap = build_calculated_snapshot(calc_result=calc, quantity=2)
    assert snap["calculated_unit_price_cents"] == round(calc["selling_price"] * 100)
    assert snap["defaults_snapshot"]["design_hourly_rate"] == 85.00


# ---------- Rigid Signs ----------

def test_rigid_signs_hardware_option_adds_cost():
    settings = build_starter_pack()
    none_hw = calculate_pricing(settings=settings, category="rigid_signs", width_inches=24, height_inches=24, quantity=1)
    with_hw = calculate_pricing(settings=settings, category="rigid_signs", width_inches=24, height_inches=24, quantity=1,
                                category_inputs={"hardware_option": "h_stake"})
    assert with_hw["hardware_cost"] > none_hw["hardware_cost"] == 0


def test_rigid_signs_shape_finish_thickness_multipliers_increase_price():
    settings = build_starter_pack()
    standard = calculate_pricing(settings=settings, category="rigid_signs", width_inches=24, height_inches=24, quantity=1)
    premium = calculate_pricing(settings=settings, category="rigid_signs", width_inches=24, height_inches=24, quantity=1,
                                category_inputs={"shape_type": "complex_cut", "finish_quality": "show_quality", "thickness": "extra_heavy"})
    assert premium["material_cost"] > standard["material_cost"]


def test_rigid_signs_drill_prep_adds_finishing_cost():
    settings = build_starter_pack()
    base = calculate_pricing(settings=settings, category="rigid_signs", width_inches=24, height_inches=24, quantity=1)
    with_drill = calculate_pricing(settings=settings, category="rigid_signs", width_inches=24, height_inches=24, quantity=1,
                                   category_inputs={"drill_prep_required": True})
    assert with_drill["finishing_cost"] > base["finishing_cost"]


# ---------- Digital Print ----------

def test_digital_print_laminate_and_quality_mode_increase_material_cost():
    settings = build_starter_pack()
    base = calculate_pricing(settings=settings, category="digital_print", width_inches=24, height_inches=36, quantity=1)
    laminated = calculate_pricing(settings=settings, category="digital_print", width_inches=24, height_inches=36, quantity=1,
                                  category_inputs={"laminate": True, "quality_mode": "photo"})
    assert laminated["material_cost"] > base["material_cost"]


def test_digital_print_contour_cut_piece_separation_scales_with_quantity():
    settings = build_starter_pack()
    qty1 = calculate_pricing(settings=settings, category="digital_print", width_inches=24, height_inches=36, quantity=1,
                             category_inputs={"contour_cut": True, "piece_separation": True})
    qty10 = calculate_pricing(settings=settings, category="digital_print", width_inches=24, height_inches=36, quantity=10,
                              category_inputs={"contour_cut": True, "piece_separation": True})
    assert qty10["finishing_cost"] > qty1["finishing_cost"]


def test_digital_print_minimum_billable_area_enforced():
    settings = build_starter_pack()
    tiny = calculate_pricing(settings=settings, category="digital_print", width_inches=6, height_inches=6, quantity=1)
    assert tiny["area_sqft_each"] == 1.0


# ---------- Cut Vinyl ----------

def test_cut_vinyl_color_count_and_weeding_complexity_multiply_labor():
    settings = build_starter_pack()
    simple = calculate_pricing(settings=settings, category="cut_vinyl", width_inches=12, height_inches=12, quantity=1)
    complex_job = calculate_pricing(settings=settings, category="cut_vinyl", width_inches=12, height_inches=12, quantity=1,
                                    category_inputs={"number_of_colors": "3", "weeding_complexity": "extreme"})
    assert complex_job["labor_cost"] > simple["labor_cost"]


def test_cut_vinyl_masking_adds_finishing_cost():
    settings = build_starter_pack()
    no_mask = calculate_pricing(settings=settings, category="cut_vinyl", width_inches=12, height_inches=12, quantity=1)
    masked = calculate_pricing(settings=settings, category="cut_vinyl", width_inches=12, height_inches=12, quantity=1,
                               category_inputs={"masking": True})
    assert masked["finishing_cost"] > no_mask["finishing_cost"] == 0


def test_cut_vinyl_surface_type_multiplies_install_cost():
    settings = build_starter_pack()
    flat = calculate_pricing(settings=settings, category="cut_vinyl", width_inches=12, height_inches=12, quantity=1,
                             install_needed=True)
    awkward = calculate_pricing(settings=settings, category="cut_vinyl", width_inches=12, height_inches=12, quantity=1,
                                install_needed=True, category_inputs={"surface_type": "awkward"})
    assert awkward["install_cost"] > flat["install_cost"]


# ---------- Reuse: canonical Material + Material Pricing Profile + Pricing Components ----------

@pytest.mark.asyncio
async def test_calculate_reuses_material_pricing_profile_and_pricing_component(e1_ctx):
    ua = e1_ctx["ua"]
    async with await _client(ua) as c:
        mat = await c.post("/api/materials", json={"name": "Premium Banner Vinyl", "category": "banner", "current_cost_cents": 200})
        mid = mat.json()["id"]
        profile = await c.post(f"/api/pricing/material-profiles/materials/{mid}", json={
            "pricing_unit": "per_sqft", "normalized_cost_basis": 3.50, "suggested_sell_rate": 15.0,
            "category_applicability": ["banners"],
        })
        pid = profile.json()["id"]
        comp = await c.post("/api/pricing/components", json={
            "key": f"rush-fee-{uuid.uuid4().hex[:4]}", "name": "Weekend Rush Surcharge", "charge_type": "rush_charge", "amount": 25.0,
        })
        cid = comp.json()["id"]

        legacy = await c.post("/api/pricing/calculate", json={
            "category": "banners", "width_inches": 48, "height_inches": 96, "quantity": 1, "material_key": "banner_13oz",
        })
        with_profile_and_component = await c.post("/api/pricing/calculate", json={
            "category": "banners", "width_inches": 48, "height_inches": 96, "quantity": 1,
            "material_profile_id": pid, "pricing_component_ids": [cid],
        })
        assert legacy.status_code == 200 and with_profile_and_component.status_code == 200
        wpc = with_profile_and_component.json()
        assert wpc["material_key"] == "Premium Banner Vinyl"  # resolved from the canonical Material, not the legacy key
        assert any(a["id"] == cid for a in wpc["pricing_components_applied"])
        assert wpc["true_cost"] != legacy.json()["true_cost"]
    _clear()


@pytest.mark.asyncio
async def test_calculate_rejects_unknown_material_profile_id(e1_ctx):
    ua = e1_ctx["ua"]
    async with await _client(ua) as c:
        r = await c.post("/api/pricing/calculate", json={
            "category": "banners", "width_inches": 48, "height_inches": 96, "quantity": 1,
            "material_profile_id": "nonexistent-profile-id",
        })
        assert r.status_code == 404
    _clear()
