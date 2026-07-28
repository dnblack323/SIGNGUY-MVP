"""EC9 Phase 9I-D shared category method-output normalization tests."""
from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.core.db import db
from app.services.pricing import calculate_pricing
from app.services.pricing_apparel import calculate_apparel_pricing
from app.services.pricing_custom import calculate_custom_pricing
from app.services.pricing_flat_sqft import calculate_flat_sqft_pricing
from app.services.pricing_method_registry import get_category_definition
from app.services.pricing_promotional import calculate_promotional_pricing
from app.services.pricing_services import calculate_services_pricing
from app.services.pricing_vehicle_graphics import calculate_vehicle_graphics_pricing
from app.services.starter_defaults import build_starter_pack


COUNTED_COLLECTIONS = [
    "pricing_settings",
    "audit_events",
    "pricing_snapshot_records",
    "pricing_calculation_records",
    "quotes",
    "orders",
    "order_items",
    "work_orders",
]


CASES: list[dict[str, Any]] = [
    {
        "category": "rigid_signs",
        "width_inches": 24,
        "height_inches": 24,
        "quantity": 1,
        "category_inputs": {"hardware_option": "h_stake", "drill_prep_required": True},
        "detail_key": "hardware_cost",
    },
    {
        "category": "cut_vinyl",
        "width_inches": 12,
        "height_inches": 12,
        "quantity": 1,
        "category_inputs": {"number_of_colors": "3", "weeding_complexity": "extreme", "masking": True},
        "detail_key": "finishing_cost",
    },
    {
        "category": "digital_print",
        "width_inches": 24,
        "height_inches": 36,
        "quantity": 1,
        "category_inputs": {"laminate": True, "quality_mode": "photo", "contour_cut": True},
        "detail_key": "area_sqft_total",
    },
    {
        "category": "vehicle_graphics",
        "width_inches": None,
        "height_inches": None,
        "quantity": 1,
        "category_inputs": {"vehicle_type": "pickup", "coverage_type": "partial"},
        "detail_key": "cost_plus_price",
    },
    {
        "category": "apparel",
        "width_inches": None,
        "height_inches": None,
        "quantity": 25,
        "category_inputs": {"garment_type": "short_sleeve_tee", "brand": "gildan_5000", "placement": "front_small"},
        "detail_key": "decoration_table_revenue",
    },
    {
        "category": "promotional",
        "width_inches": None,
        "height_inches": None,
        "quantity": 100,
        "category_inputs": {"pricing_method": "per_piece", "unit_price": 2.5, "unit_cost": 1.0},
        "detail_key": "shipping_cost",
    },
    {
        "category": "services",
        "width_inches": None,
        "height_inches": None,
        "quantity": 1,
        "category_inputs": {"service_type": "general_labor", "estimated_hours": 2},
        "detail_key": "cost_plus_price",
    },
    {
        "category": "custom",
        "width_inches": None,
        "height_inches": None,
        "quantity": 2,
        "category_inputs": {"item_name": "Custom", "unit_price": 25.0, "unit_cost_manual": 10.0},
        "detail_key": "unit_price",
    },
]


MANUAL_OVERRIDE_CASES: list[dict[str, Any]] = [
    {
        "category": "rigid_signs",
        "width_inches": 24,
        "height_inches": 24,
        "quantity": 1,
        "category_inputs": {"hardware_option": "h_stake"},
    },
    {
        "category": "cut_vinyl",
        "width_inches": 12,
        "height_inches": 12,
        "quantity": 1,
        "category_inputs": {"number_of_colors": "2", "weeding_complexity": "standard"},
    },
    {
        "category": "digital_print",
        "width_inches": 24,
        "height_inches": 36,
        "quantity": 1,
        "category_inputs": {"laminate": True, "quality_mode": "standard"},
    },
    {
        "category": "vehicle_graphics",
        "width_inches": None,
        "height_inches": None,
        "quantity": 1,
        "category_inputs": {"vehicle_type": "pickup", "coverage_type": "partial"},
    },
    {
        "category": "apparel",
        "width_inches": None,
        "height_inches": None,
        "quantity": 25,
        "category_inputs": {"garment_type": "short_sleeve_tee", "brand": "gildan_5000", "placement": "front_small"},
    },
]


def _raw_calculation(settings: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    shop = settings.get("shop_defaults") or {}
    cat_defaults = settings.get("category_defaults") or {}
    materials = settings.get("materials") or {}
    category = case["category"]
    category_inputs = case["category_inputs"]
    quantity = case["quantity"]
    manual_selling_price = case.get("manual_selling_price")

    if category in {"rigid_signs", "cut_vinyl", "digital_print"}:
        return calculate_flat_sqft_pricing(
            category=category,
            shop=shop,
            cat=cat_defaults[category],
            materials_legacy=materials,
            material_profile=None,
            pricing_components=[],
            width_inches=case["width_inches"],
            height_inches=case["height_inches"],
            quantity=quantity,
            material_key=None,
            design_needed=False,
            install_needed=False,
            manual_selling_price=manual_selling_price,
            category_inputs=category_inputs,
        )
    if category == "vehicle_graphics":
        return calculate_vehicle_graphics_pricing(
            shop=shop,
            cat=cat_defaults[category],
            pricing_components=[],
            quantity=quantity,
            manual_selling_price=manual_selling_price,
            category_inputs=category_inputs,
        )
    if category == "apparel":
        return calculate_apparel_pricing(
            shop=shop,
            cat=cat_defaults[category],
            pricing_components=[],
            quantity=quantity,
            manual_selling_price=manual_selling_price,
            category_inputs=category_inputs,
        )
    if category == "promotional":
        return calculate_promotional_pricing(
            shop=shop,
            cat=cat_defaults[category],
            pricing_components=[],
            quantity=quantity,
            manual_selling_price=manual_selling_price,
            category_inputs=category_inputs,
            saved_item=None,
        )
    if category == "services":
        return calculate_services_pricing(
            shop=shop,
            cat=cat_defaults[category],
            pricing_components=[],
            quantity=quantity,
            manual_selling_price=manual_selling_price,
            category_inputs=category_inputs,
            material_profile=None,
        )
    if category == "custom":
        return calculate_custom_pricing(
            cat=cat_defaults[category],
            quantity=quantity,
            manual_selling_price=manual_selling_price,
            category_inputs=category_inputs,
        )
    raise AssertionError(f"Unhandled test category: {category}")


def _normalized_calculation(settings: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    return calculate_pricing(
        settings=settings,
        category=case["category"],
        width_inches=case["width_inches"],
        height_inches=case["height_inches"],
        quantity=case["quantity"],
        manual_selling_price=case.get("manual_selling_price"),
        category_inputs=case["category_inputs"],
    )


def _selected_row(result: dict[str, Any]) -> dict[str, Any]:
    selected = [row for row in result["pricing_method_results"] if row["selected"]]
    assert len(selected) == 1
    return selected[0]


def _detail_keys(result: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for section in result["detail_sections"]:
        for line in section.get("lines") or []:
            if "key" in line:
                keys.add(line["key"])
    return keys


async def _tenant_counts(tenant_id: str) -> dict[str, int]:
    return {
        collection: await db[collection].count_documents({"tenant_id": tenant_id})
        for collection in COUNTED_COLLECTIONS
    }


@pytest.mark.parametrize("case", CASES, ids=[case["category"] for case in CASES])
def test_non_banner_category_outputs_preserve_authoritative_calculator_totals(case):
    settings = build_starter_pack()
    raw = _raw_calculation(settings, case)
    normalized = _normalized_calculation(settings, case)

    for field in (
        "selling_price",
        "suggested_price",
        "true_cost",
        "pricing_method_used",
        "profit_amount",
        "profit_margin_percent",
    ):
        assert normalized[field] == raw[field]
    assert normalized["breakdown"] == raw["breakdown"]
    assert normalized[case["detail_key"]] == raw[case["detail_key"]]


@pytest.mark.parametrize("case", CASES, ids=[case["category"] for case in CASES])
def test_normalized_method_rows_have_consistent_meanings_and_preserve_details(case):
    settings = build_starter_pack()
    result = _normalized_calculation(settings, case)
    category = get_category_definition(case["category"])
    rows = result["pricing_method_results"]
    selected = _selected_row(result)

    assert result["pricing_output_contract_version"]
    assert result["method_output_source"] == "existing_calculator_output"
    assert result["mutated"] is False
    assert result["persistent_entities_created"] == []
    assert [row["method_id"] for row in rows] == list(category.supported_method_ids)
    assert selected["amount"] == result["selling_price"]
    assert "selected" in selected["status"]
    assert "authoritative_total" in selected["status"]
    assert _detail_keys(result) >= {"pricing_method_used", "selling_price", "true_cost", case["detail_key"]}
    assert any(section["section"] == "existing_breakdown" for section in result["detail_sections"])


def test_unsupported_methods_are_reported_unavailable_without_rows():
    settings = build_starter_pack()
    result = calculate_pricing(
        settings=settings,
        category="services",
        width_inches=None,
        height_inches=None,
        quantity=1,
        category_inputs={"service_type": "general_labor", "estimated_hours": 1},
    )

    rows = {row["method_id"] for row in result["pricing_method_results"]}
    assert rows == {"service_rate", "cost_plus"}
    unsupported = next(item for item in result["method_availability"] if item["method_id"] == "square_foot_plus_addons")
    assert unsupported == {
        "method_id": "square_foot_plus_addons",
        "display_name": "Square-foot plus add-ons",
        "supported": False,
        "available": False,
        "reason": "unsupported_for_category",
    }


def test_failed_promotional_tier_result_does_not_fabricate_price():
    settings = build_starter_pack()
    result = calculate_pricing(
        settings=settings,
        category="promotional",
        width_inches=None,
        height_inches=None,
        quantity=125,
        category_inputs={"pricing_method": "tier_pricing"},
    )

    tier = next(row for row in result["pricing_method_results"] if row["method_id"] == "tier_pricing")
    assert result["selling_price"] is None
    assert result["pricing_method_used"] == "manual_required_no_tier_match"
    assert tier["amount"] is None
    assert tier["pre_adjustment_amount"] is None
    assert tier["available"] is False
    assert "manual_price_required" in tier["status"]
    assert "no_exact_tier_match" in tier["errors"]
    assert any(line["key"] == "requires_manual_price" and line["value"] is True for section in result["detail_sections"] for line in section.get("lines", []))


@pytest.mark.parametrize("case", MANUAL_OVERRIDE_CASES, ids=[case["category"] for case in MANUAL_OVERRIDE_CASES])
def test_manual_override_outputs_select_stable_manual_method_without_repricing(case):
    settings = build_starter_pack()
    manual_amount = 123.45
    manual_case = {**case, "manual_selling_price": manual_amount}

    raw = _raw_calculation(settings, manual_case)
    normalized = _normalized_calculation(settings, manual_case)
    selected = _selected_row(normalized)

    assert raw["pricing_method_used"] == "manual_override"
    assert normalized["pricing_method_used"] == "manual_override"
    assert raw["selling_price"] == manual_amount
    assert normalized["selling_price"] == manual_amount
    assert selected["method_id"] == "manual_override"
    assert selected["amount"] == normalized["selling_price"]
    assert selected["pre_adjustment_amount"] == normalized["selling_price"]
    assert selected["available"] is True
    assert selected["selected"] is True
    assert "selected" in selected["status"]
    assert "authoritative_total" in selected["status"]
    for row in normalized["pricing_method_results"]:
        if row["method_id"] == "manual_override":
            continue
        assert row["selected"] is False
        assert "authoritative_total" not in row["status"]
        if row["amount"] is not None:
            assert "candidate_from_existing_result" in row["status"]
    assert _detail_keys(normalized) >= {"pricing_method_used", "selling_price", "true_cost"}


def test_banner_pricing_output_remains_unchanged_by_category_normalizer():
    settings = build_starter_pack()
    shop = settings.get("shop_defaults") or {}
    cat_defaults = settings.get("category_defaults") or {}
    materials = settings.get("materials") or {}
    category_inputs = {"selected_pricing_method": "square_foot_plus_addons"}
    raw = calculate_flat_sqft_pricing(
        category="banners",
        shop=shop,
        cat=cat_defaults["banners"],
        materials_legacy=materials,
        material_profile=None,
        pricing_components=[],
        width_inches=96,
        height_inches=36,
        quantity=1,
        material_key=None,
        design_needed=False,
        install_needed=False,
        manual_selling_price=None,
        category_inputs=category_inputs,
    )
    normalized = calculate_pricing(
        settings=settings,
        category="banners",
        width_inches=96,
        height_inches=36,
        quantity=1,
        category_inputs=category_inputs,
    )

    configuration_evidence = normalized.pop("pricing_engine_configuration_used", None)
    assert configuration_evidence["adapter_id"] == "saas_configuration_adapter_9iq_v1"
    assert normalized == raw
    assert "pricing_output_contract_version" not in normalized


@pytest.mark.asyncio
async def test_normalized_category_output_is_pure_and_creates_no_persistent_records(clean_db):
    tenant_id = f"tenant-{uuid.uuid4().hex}"
    before = await _tenant_counts(tenant_id)
    settings = build_starter_pack()

    for case in CASES:
        result = _normalized_calculation(settings, case)
        assert result["mutated"] is False
        assert result["persistent_entities_created"] == []

    after = await _tenant_counts(tenant_id)
    assert after == before


@pytest.mark.asyncio
async def test_manual_override_normalization_is_pure_and_creates_no_persistent_records(clean_db):
    tenant_id = f"tenant-{uuid.uuid4().hex}"
    before = await _tenant_counts(tenant_id)
    settings = build_starter_pack()

    for case in MANUAL_OVERRIDE_CASES:
        result = _normalized_calculation(settings, {**case, "manual_selling_price": 123.45})
        assert result["mutated"] is False
        assert result["persistent_entities_created"] == []

    after = await _tenant_counts(tenant_id)
    assert after == before
