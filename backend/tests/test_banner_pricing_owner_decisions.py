from app.services.pricing import calculate_pricing
from app.services.pricing_snapshot import build_calculated_snapshot
from app.services.starter_defaults import build_starter_pack


def _settings():
    settings = build_starter_pack()
    settings["tenant_id"] = "tenant-pricing-test"
    return settings


def _banner(width, height, inputs=None, quantity=1, manual=None):
    return calculate_pricing(
        settings=_settings(),
        category="banners",
        width_inches=width,
        height_inches=height,
        quantity=quantity,
        material_key=None,
        design_needed=False,
        install_needed=False,
        manual_selling_price=manual,
        category_inputs=inputs or {},
    )


def _method_amount(result, method):
    for row in result["pricing_method_results"]:
        if row["method"] == method:
            return row["amount"]
    raise AssertionError(f"method missing: {method}")


def test_banner_default_uses_square_foot_plus_addons_not_highest_method():
    result = _banner(8, 3, {"dimension_unit": "ft"})

    assert result["width_inches"] == 96.0
    assert result["height_inches"] == 36.0
    assert result["area_sqft_total"] == 24.0
    assert result["pricing_method_used"] == "square_foot_plus_addons"
    assert result["selling_price"] == 192.0
    assert _method_amount(result, "cost_plus") > result["selling_price"]
    assert result["calculation_warnings"] == []


def test_banner_feet_and_inches_inputs_calculate_identically():
    feet = _banner(8, 3, {"dimension_unit": "ft"})
    inches = _banner(96, 36, {"dimension_unit": "in"})

    assert feet["selling_price"] == inches["selling_price"]
    assert feet["true_cost"] == inches["true_cost"]
    assert feet["pricing_method_results"] == inches["pricing_method_results"]
    assert feet["measurement"]["input_unit"] == "ft"
    assert inches["measurement"]["input_unit"] == "in"


def test_banner_hem_sell_rate_is_75_cents_per_linear_foot():
    result = _banner(96, 36, {"dimension_unit": "in", "hems": True})

    assert result["pricing_method_used"] == "square_foot_plus_addons"
    assert result["selling_price"] == 208.5
    assert result["finishing_sell_price"] == 16.5
    assert result["finishing_cost"] == 7.7


def test_banner_legacy_input_names_map_to_canonical_short_names():
    result = _banner(96, 36, {
        "dimension_unit": "in",
        "banner_hems": True,
        "banner_use_type": "outdoor",
        "banner_hardware_keys": ["rope"],
    })

    assert result["category_inputs_used"]["hems"] is True
    assert result["category_inputs_used"]["use_type"] == "outdoor"
    assert result["category_inputs_used"]["hardware_keys"] == ["rope"]
    assert result["source_labels"]["hems"] == "banner_hems"
    assert result["source_labels"]["use_type"] == "banner_use_type"
    assert result["source_labels"]["hardware_keys"] == "banner_hardware_keys"
    assert result["selling_price"] == 208.5


def test_banner_can_select_comparison_method_without_highest_default():
    default_result = _banner(96, 36, {"dimension_unit": "in"})
    selected = _banner(96, 36, {"dimension_unit": "in", "selected_pricing_method": "cost_plus"})

    assert default_result["pricing_method_used"] == "square_foot_plus_addons"
    assert selected["pricing_method_used"] == "cost_plus"
    assert selected["selling_price"] == _method_amount(selected, "cost_plus")
    assert selected["selling_price"] > default_result["selling_price"]


def test_banner_manual_override_does_not_replace_selected_price():
    result = _banner(96, 36, {"dimension_unit": "in"}, manual=50)

    assert result["pricing_method_used"] == "manual_override"
    assert result["selling_price"] == 50.0
    assert "selected_price_below_true_cost" in result["calculation_warnings"]
    assert "manual_override_reason_recommended" in result["calculation_warnings"]


def test_banner_snapshot_preserves_method_results_and_normalized_dimensions():
    result = _banner(
        96,
        36,
        {"dimension_unit": "ft", "entered_width": 8, "entered_height": 3, "selected_pricing_method": "target_margin"},
    )
    snapshot = build_calculated_snapshot(calc_result=result, quantity=1)

    assert snapshot["width_inches"] == 96.0
    assert snapshot["height_inches"] == 36.0
    assert snapshot["measurement"]["input_unit"] == "ft"
    assert snapshot["selected_pricing_method"] == "target_margin"
    assert snapshot["pricing_method_results"]
    assert snapshot["detail_sections"]
