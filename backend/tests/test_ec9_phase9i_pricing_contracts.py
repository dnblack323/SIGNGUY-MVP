"""EC9 Phase 9I-A shared pricing contract and method registry tests."""
from __future__ import annotations

import pytest

from app.services.pricing import calculate_pricing
from app.services.pricing_contracts import (
    PricingContractError,
    TenantCategoryMethodConfiguration,
    validate_tenant_method_configuration,
)
from app.services.pricing_method_registry import (
    available_method_ids_for_context,
    get_category_definition,
    list_category_definitions,
    list_method_definitions,
    list_preset_definitions,
    validate_registry,
)
from app.services.pricing_snapshot import build_calculated_snapshot
from app.services.pricing_saved_items import BUSINESS_CARD_STARTER_ITEMS
from app.services.starter_defaults import CATEGORY_IDS, build_starter_pack


def test_registry_contains_all_and_only_registered_category_ids():
    categories = list_category_definitions()
    assert [category.id for category in categories] == CATEGORY_IDS
    assert len({category.id for category in categories}) == 9
    validate_registry()


def test_method_ids_are_unique_and_all_references_exist():
    methods = list_method_definitions()
    method_ids = {method.id for method in methods}
    assert len(method_ids) == len(methods)
    for category in list_category_definitions():
        assert set(category.supported_method_ids) <= method_ids
        assert category.recommended_primary_method_id in category.supported_method_ids
        assert set(category.recommended_simple_setup_method_ids) <= set(category.supported_method_ids)
        assert len(category.recommended_simple_setup_method_ids) <= 3


def test_presets_are_not_accidentally_treated_as_categories():
    category_ids = {category.id for category in list_category_definitions()}
    presets = list_preset_definitions()
    assert {preset.display_name for preset in presets} == {starter["name"] for starter in BUSINESS_CARD_STARTER_ITEMS}
    assert all(preset.id not in category_ids for preset in presets)
    assert all(preset.category_id == "promotional" for preset in presets)
    assert all(preset.supported_method_ids == ("tier_pricing",) for preset in presets)
    assert all(not preset.supports_comparison for preset in presets)


def test_simple_setup_recommendations_match_owner_decisions():
    expected = {
        "banners": ("square_foot_plus_addons", "cost_plus"),
        "rigid_signs": ("per_sqft", "cost_plus"),
        "cut_vinyl": ("per_sqft", "cost_plus"),
        "digital_print": ("per_sqft", "cost_plus"),
        "vehicle_graphics": ("vehicle_benchmark", "vehicle_cost_plus"),
        "apparel": ("apparel_table", "apparel_cost_plus"),
        "services": ("service_rate", "cost_plus"),
        "promotional": ("tier_pricing", "flat_fee"),
        "custom": ("unit_price_x_quantity",),
    }
    for category_id, methods in expected.items():
        category = get_category_definition(category_id)
        assert category.recommended_simple_setup_method_ids == methods
        assert category.recommended_primary_method_id == methods[0]


def test_categories_with_one_method_remain_valid_without_fabricated_comparison():
    custom = get_category_definition("custom")
    assert custom.supported_method_ids == ("unit_price_x_quantity",)
    assert custom.supports_comparison is False
    assert custom.max_comparison_methods == 1
    cfg = validate_tenant_method_configuration(
        {
            "tenant_id": "tenant-a",
            "category_id": "custom",
            "enabled_method_ids": ["unit_price_x_quantity"],
            "primary_method_id": "unit_price_x_quantity",
        },
        custom,
    )
    assert cfg.comparison_order == ("unit_price_x_quantity",)


def test_valid_two_and_three_method_configurations_are_accepted():
    rigid = get_category_definition("rigid_signs")
    rigid_cfg = validate_tenant_method_configuration(
        {
            "tenant_id": "tenant-a",
            "category_id": "rigid_signs",
            "enabled_method_ids": ["per_sqft", "cost_plus"],
            "primary_method_id": "per_sqft",
            "comparison_order": ["cost_plus", "per_sqft"],
            "configuration_mode": "advanced",
        },
        rigid,
    )
    assert rigid_cfg.comparison_order == ("cost_plus", "per_sqft")

    banners = get_category_definition("banners")
    banner_cfg = validate_tenant_method_configuration(
        {
            "tenant_id": "tenant-a",
            "category_id": "banners",
            "enabled_method_ids": ["square_foot_plus_addons", "cost_plus", "target_margin"],
            "primary_method_id": "square_foot_plus_addons",
        },
        banners,
    )
    assert banner_cfg.comparison_order == ("square_foot_plus_addons", "cost_plus", "target_margin")


@pytest.mark.parametrize(
    "payload,error",
    [
        ({"enabled_method_ids": ["not_supported"], "primary_method_id": "not_supported"}, "Unsupported method"),
        ({"enabled_method_ids": ["per_sqft", "cost_plus", "target_margin", "minimum_charge"], "primary_method_id": "per_sqft"}, "No more than three"),
        ({"enabled_method_ids": ["per_sqft", "per_sqft"], "primary_method_id": "per_sqft"}, "duplicates"),
        ({"enabled_method_ids": ["per_sqft"], "primary_method_id": "cost_plus"}, "primary_method_id must be one"),
        ({"enabled_method_ids": ["per_sqft"], "primary_method_id": None}, "primary_method_id is required"),
        ({"enabled_method_ids": ["per_sqft", "cost_plus"], "primary_method_id": "per_sqft", "comparison_order": ["per_sqft"]}, "comparison_order"),
    ],
)
def test_invalid_tenant_method_configurations_are_rejected(payload, error):
    category = get_category_definition("rigid_signs")
    base = {"tenant_id": "tenant-a", "category_id": "rigid_signs"}
    with pytest.raises(PricingContractError, match=error):
        validate_tenant_method_configuration({**base, **payload}, category)


def test_tenant_specific_values_do_not_mutate_global_registry():
    category = get_category_definition("rigid_signs")
    before = category.to_dict()
    cfg = TenantCategoryMethodConfiguration(
        tenant_id="tenant-a",
        category_id="rigid_signs",
        enabled_method_ids=("per_sqft", "cost_plus"),
        primary_method_id="per_sqft",
        method_configuration_refs={"per_sqft": "tenant-specific-profile"},
        validation_warnings=("tenant warning",),
    )
    validate_tenant_method_configuration(cfg, category)
    assert get_category_definition("rigid_signs").to_dict() == before


def test_vehicle_benchmark_availability_requires_approved_configuration():
    settings = build_starter_pack()
    vehicle_defaults = settings["category_defaults"]["vehicle_graphics"]
    assert available_method_ids_for_context(
        "vehicle_graphics",
        category_defaults=vehicle_defaults,
        category_inputs={"vehicle_type": "sedan", "coverage_type": "full"},
    ) == ("vehicle_benchmark", "vehicle_cost_plus")
    assert available_method_ids_for_context(
        "vehicle_graphics",
        category_defaults=vehicle_defaults,
        category_inputs={"vehicle_type": "mini_van", "coverage_type": "full"},
    ) == ("vehicle_cost_plus",)
    assert available_method_ids_for_context("vehicle_graphics", category_defaults={}) == ("vehicle_cost_plus",)


def test_promotional_comparison_availability_respects_configured_methods():
    business_card = BUSINESS_CARD_STARTER_ITEMS[0]
    assert available_method_ids_for_context("promotional", saved_item=business_card) == ("tier_pricing",)
    assert available_method_ids_for_context(
        "promotional",
        category_inputs={"pricing_method": "per_piece", "unit_cost": 2.00, "flat_fee_price": 50.00},
    ) == ("per_piece", "flat_fee")
    assert available_method_ids_for_context("promotional") == ()


def test_cut_vinyl_and_digital_print_minimum_contracts_are_metadata_only():
    cut = get_category_definition("cut_vinyl")
    digital = get_category_definition("digital_print")
    settings = build_starter_pack()
    assert cut.recommended_starter_values["item_minimum"] == 25.00
    assert settings["category_defaults"]["cut_vinyl"]["minimum_charge"] == 25.00
    assert digital.recommended_starter_values["item_minimum"] == 20.00
    assert digital.recommended_starter_values["order_minimum"] == 40.00
    assert settings["category_defaults"]["digital_print"]["minimum_charge"] == 40.00


def test_apparel_registry_metadata_corrected_without_changing_price_outputs():
    current = build_starter_pack()
    old_metadata = build_starter_pack()
    old_metadata["category_defaults"]["apparel"]["pricing_method"] = "per_sqft"

    inputs = {"garment_type": "short_sleeve_tee", "brand": "gildan_5000", "placement": "front_small"}
    current_result = calculate_pricing(
        settings=current,
        category="apparel",
        width_inches=None,
        height_inches=None,
        quantity=25,
        category_inputs=inputs,
    )
    old_result = calculate_pricing(
        settings=old_metadata,
        category="apparel",
        width_inches=None,
        height_inches=None,
        quantity=25,
        category_inputs=inputs,
    )
    assert current["category_defaults"]["apparel"]["pricing_method"] == "per_sqft"
    assert get_category_definition("apparel").supported_method_ids == ("apparel_table", "apparel_cost_plus")
    for key in ("selling_price", "true_cost", "profit_amount", "profit_margin_percent", "pricing_method_used"):
        assert current_result[key] == old_result[key]


def test_banner_and_snapshot_outputs_remain_unchanged_by_registry_imports():
    settings = build_starter_pack()
    result = calculate_pricing(
        settings=settings,
        category="banners",
        width_inches=8,
        height_inches=3,
        quantity=1,
        category_inputs={"dimension_unit": "ft"},
    )
    assert result["pricing_method_used"] == "square_foot_plus_addons"
    assert result["selling_price"] == 192.00
    assert result["width_inches"] == 96.0
    assert result["height_inches"] == 36.0
    snapshot = build_calculated_snapshot(calc_result=result, quantity=1)
    assert snapshot["selected_pricing_method"] == "square_foot_plus_addons"
    assert snapshot["pricing_method_results"] == result["pricing_method_results"]
