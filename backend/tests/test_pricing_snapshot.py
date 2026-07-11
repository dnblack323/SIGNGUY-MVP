"""EC3 — Pricing snapshot unit tests."""
from app.services.pricing_snapshot import apply_override, build_calculated_snapshot, build_manual_snapshot


def test_manual_snapshot_captures_price_and_actor():
    snap = build_manual_snapshot(
        unit_price_cents=1250,
        quantity=2,
        reason="rush job discount",
        actor_user_id="u-1",
        actor_email="op@example.com",
    )
    assert snap["source"] == "manual"
    assert snap["pricing_method"] == "manual"
    assert snap["unit_price_cents"] == 1250
    assert snap["override_reason"] == "rush job discount"
    assert snap["override_actor_user_id"] == "u-1"
    assert "captured_at" in snap


def test_calculated_snapshot_captures_calculator_result():
    calc = {
        "selling_price": 45.00,
        "pricing_method_used": "per_sqft",
        "category": "banners",
        "material_key": "banner_13oz",
        "material_cost": 5.00,
        "labor_cost": 3.00,
        "overhead_cost": 1.50,
        "true_cost": 9.50,
        "area_sqft_total": 8.0,
        "width_inches": 24,
        "height_inches": 48,
    }
    snap = build_calculated_snapshot(calc_result=calc, quantity=3)
    assert snap["source"] == "calculator"
    assert snap["pricing_method"] == "per_sqft"
    assert snap["calculator_version"] is not None
    assert snap["calculated_unit_price_cents"] == 4500
    assert snap["quantity"] == 3


def test_apply_override_preserves_calculated_value():
    calc = {"selling_price": 30.00, "pricing_method_used": "per_sqft"}
    snap = build_calculated_snapshot(calc_result=calc, quantity=1)
    updated = apply_override(
        snap,
        override_unit_price_cents=2500,
        reason="customer negotiation",
        actor_user_id="u-1",
        actor_email="op@example.com",
    )
    assert updated["calculated_unit_price_cents"] == 3000
    assert updated["override_unit_price_cents"] == 2500
    assert updated["override_reason"] == "customer negotiation"
