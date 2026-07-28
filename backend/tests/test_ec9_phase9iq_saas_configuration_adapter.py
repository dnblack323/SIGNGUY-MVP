"""EC9 Phase 9I-Q SaaS configuration adapter tests."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from server import app
from app.core.db import db
from app.deps import get_current_user
import app.services.pricing as pricing_service
from app.services.order_pricing import resolve_references
from app.services.pricing import get_or_init_pricing_settings
from app.services.pricing_engine_adapter import PRICING_ENGINE_RESULT_FIELD, calculate_pricing_with_cents_first_envelope
from app.services.pricing_engine_config_adapter import (
    ENGINE_CONFIGURATION_CONTRACT_VERSION,
    SAAS_CONFIGURATION_ADAPTER_ID,
    build_line_engine_configuration,
)
from app.services.pricing_saved_calculations import calculate_saved_calculation_result
from pricing_engine.adapters import build_legacy_line_result
from pricing_engine.config import CATEGORY_IDS, build_starter_pack
from pricing_engine.line_engine import calculate_line

sys.path.insert(0, str(Path(__file__).parent))

from pricing_engine_fixture_runner import (
    _cents_to_legacy_dollars,
    _dimension_to_legacy_inches,
    _project_cents_first_result_for_fixture,
    _quantity_to_legacy_int,
    compare_fixture_result,
    load_fixture_pack,
)


FORBIDDEN_CONFIG_KEYS = {
    "_id",
    "tenant_id",
    "user_id",
    "actor_user_id",
    "actor_email",
    "permissions",
    "db",
    "database",
    "request",
    "router",
    "audit",
    "entitlements",
    "license",
    "licensing",
}


def _override_as(user: dict):
    async def _dep():
        return user
    return _dep


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override_as(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


def _legacy_args_from_fixture(fixture) -> dict:
    request = fixture.document["normalized_inputs"]["calculator_request"]
    return {
        "settings": build_starter_pack(),
        "category": fixture.category,
        "width_inches": _dimension_to_legacy_inches(request.get("width")),
        "height_inches": _dimension_to_legacy_inches(request.get("height")),
        "quantity": _quantity_to_legacy_int(request["quantity"]),
        "material_key": request.get("material_key"),
        "design_needed": bool(request.get("design_needed", False)),
        "install_needed": bool(request.get("install_needed", False)),
        "manual_selling_price": _cents_to_legacy_dollars(request.get("manual_selling_price_cents")),
        "category_inputs": deepcopy(request.get("category_inputs") or {}),
        "material_profile": None,
        "pricing_components": [],
        "saved_item": None,
    }


def _walk_dict(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key, item
            yield from _walk_dict(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dict(item)


async def _seed_customer(tenant_id: str) -> str:
    customer_id = f"cust-9iq-{uuid.uuid4().hex[:8]}"
    await db.customers.insert_one({"id": customer_id, "tenant_id": tenant_id, "name": "9IQ Customer"})
    return customer_id


async def _new_quote(client: AsyncClient, customer_id: str) -> str:
    response = await client.post("/api/quotes", json={"customer_id": customer_id, "job_name": "9IQ quote"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _new_order(client: AsyncClient, customer_id: str) -> str:
    response = await client.post("/api/orders", json={"customer_id": customer_id, "job_name": "9IQ order"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_current_and_legacy_settings_map_to_sanitized_engine_configuration_without_mutation():
    settings = build_starter_pack()
    settings.update({
        "_id": "mongo-id",
        "tenant_id": "tenant-a",
        "actor_email": "owner@example.com",
        "category_method_configurations": {"banners": {"configuration_version": 7}},
        "field_sources": {
            "shop_defaults.production_hourly_rate": "shop_default",
            "category_defaults.banners.minimum_charge": "user_entered",
            "category_defaults.apparel.garments": "unrelated",
        },
    })
    original = deepcopy(settings)

    config = build_line_engine_configuration(settings=settings, category="banners")

    assert settings == original
    assert config["contract_version"] == ENGINE_CONFIGURATION_CONTRACT_VERSION
    assert config["adapter_id"] == SAAS_CONFIGURATION_ADAPTER_ID
    assert set(config["engine_settings"]["category_defaults"]) == {"banners"}
    assert config["lineage"]["category_method_configuration_version"] == 7
    assert "category_defaults.apparel.garments" not in config["lineage"]["field_sources"]
    for key, _ in _walk_dict(config["engine_settings"]):
        assert key not in FORBIDDEN_CONFIG_KEYS

    legacy = {"tenant_id": "tenant-b", "category_defaults": {"custom": {"pricing_method": "manual"}}}
    legacy_original = deepcopy(legacy)
    legacy_config = build_line_engine_configuration(settings=legacy, category="custom")
    assert legacy == legacy_original
    assert legacy_config["engine_settings"]["shop_defaults"]["production_hourly_rate"] == 28.0
    assert legacy_config["engine_settings"]["category_defaults"]["custom"]["pricing_method"] == "manual"


def test_all_nine_fixture_results_match_through_saas_configuration_adapter():
    categories = set()
    for fixture in load_fixture_pack():
        args = _legacy_args_from_fixture(fixture)
        raw = pricing_service.calculate_pricing(**args)
        line_result = build_legacy_line_result(
            category_id=fixture.category,
            legacy_result=raw,
            normalized_input=fixture.document["normalized_inputs"]["calculator_request"],
        )
        compare_fixture_result(
            fixture,
            type("Execution", (), {
                "adapter_id": SAAS_CONFIGURATION_ADAPTER_ID,
                "normalized_result": _project_cents_first_result_for_fixture(line_result),
            })(),
        )
        assert raw["pricing_engine_configuration_used"]["adapter_id"] == SAAS_CONFIGURATION_ADAPTER_ID
        assert raw["pricing_engine_configuration_used"]["category_id"] == fixture.category
        categories.add(fixture.category)
    assert categories == set(CATEGORY_IDS)


def test_direct_pure_engine_and_saas_adapter_outputs_match_without_raw_settings_reaching_formula(monkeypatch):
    fixture = next(item for item in load_fixture_pack() if item.category == "banners")
    args = _legacy_args_from_fixture(fixture)
    seen_settings = []
    real_calculate_line = pricing_service.calculate_line

    def spy_calculate_line(**kwargs):
        seen_settings.append(deepcopy(kwargs["settings"]))
        return real_calculate_line(**kwargs)

    monkeypatch.setattr(pricing_service, "calculate_line", spy_calculate_line)

    saas = pricing_service.calculate_pricing(**args)
    normalized_config = build_line_engine_configuration(
        settings=args["settings"],
        category=args["category"],
        material_key=args["material_key"],
    )
    pure = calculate_line(
        settings=normalized_config["engine_settings"],
        category=args["category"],
        width_inches=args["width_inches"],
        height_inches=args["height_inches"],
        quantity=args["quantity"],
        material_key=args["material_key"],
        design_needed=args["design_needed"],
        install_needed=args["install_needed"],
        manual_selling_price=args["manual_selling_price"],
        category_inputs=args["category_inputs"],
        material_profile=args["material_profile"],
        pricing_components=args["pricing_components"],
        saved_item=args["saved_item"],
    )

    assert saas["selling_price"] == pure["selling_price"]
    assert seen_settings
    for key, _ in _walk_dict(seen_settings[0]):
        assert key not in FORBIDDEN_CONFIG_KEYS


@pytest.mark.asyncio
async def test_pricing_calculate_quote_order_saved_calculation_and_snapshots_use_adapter(monkeypatch, seeded_users):
    user = seeded_users["user_a"]
    customer_id = await _seed_customer(user["tenant_id"])
    categories: list[str] = []
    real_calculate_line = pricing_service.calculate_line

    def spy_calculate_line(**kwargs):
        settings = kwargs["settings"]
        assert "tenant_id" not in settings
        assert "_id" not in settings
        assert set(settings["category_defaults"]) == {kwargs["category"]}
        categories.append(kwargs["category"])
        return real_calculate_line(**kwargs)

    monkeypatch.setattr(pricing_service, "calculate_line", spy_calculate_line)

    payload = {
        "category": "banners",
        "width_inches": 96,
        "height_inches": 36,
        "quantity": 1,
        "category_inputs": {"selected_pricing_method": "square_foot_plus_addons"},
    }
    async with await _client_as(user) as client:
        calc = await client.post("/api/pricing/calculate", json=payload)
        assert calc.status_code == 200, calc.text
        body = calc.json()
        assert body[PRICING_ENGINE_RESULT_FIELD]["normalized_input"]["pricing_engine_configuration"]["adapter_id"] == SAAS_CONFIGURATION_ADAPTER_ID

        quote_id = await _new_quote(client, customer_id)
        quote_item = await client.post(
            f"/api/quotes/{quote_id}/line-items",
            json={
                "description": "9IQ quote banner",
                "quantity": 1,
                "unit_price_cents": 0,
                "selected_price_source": "suggested",
                **payload,
            },
        )
        assert quote_item.status_code == 201, quote_item.text
        quote_snapshot = quote_item.json()["pricing_snapshot"]
        assert quote_snapshot["pricing_engine_configuration_used"]["adapter_id"] == SAAS_CONFIGURATION_ADAPTER_ID

        order_id = await _new_order(client, customer_id)
        order_item = await client.post(
            f"/api/orders/{order_id}/items",
            json={
                "description": "9IQ order banner",
                "quantity": 1,
                "unit_price_cents": 0,
                "selected_price_source": "suggested",
                **payload,
            },
        )
        assert order_item.status_code == 201, order_item.text
        assert order_item.json()["pricing_snapshot"]["pricing_engine_configuration_used"]["adapter_id"] == SAAS_CONFIGURATION_ADAPTER_ID

        saved = await client.post(
            "/api/pricing/saved-calculations",
            json={"name": "9IQ saved banner", "calculation_inputs": payload},
        )
        assert saved.status_code == 201, saved.text
        assert saved.json()["pricing_reproducibility_ref"]["pricing_engine_adapter_source"]

    assert categories.count("banners") >= 4
    _clear()


@pytest.mark.asyncio
async def test_cross_tenant_and_inactive_references_are_rejected_without_leaking_foreign_data(seeded_users):
    user_a = seeded_users["user_a"]
    user_b = seeded_users["user_b"]
    material_id = f"mat-9iq-{uuid.uuid4().hex[:8]}"
    profile_id = f"profile-9iq-{uuid.uuid4().hex[:8]}"
    component_id = f"component-9iq-{uuid.uuid4().hex[:8]}"
    saved_item_id = f"saved-9iq-{uuid.uuid4().hex[:8]}"
    await db.materials.insert_one({"id": material_id, "tenant_id": user_b["tenant_id"], "name": "Foreign Vinyl", "active": True})
    await db.material_pricing_profiles.insert_one({
        "id": profile_id,
        "tenant_id": user_a["tenant_id"],
        "material_id": material_id,
        "active": True,
        "normalized_cost_basis": 1.0,
    })
    await db.pricing_components.insert_one({
        "id": component_id,
        "tenant_id": user_b["tenant_id"],
        "key": "foreign-component",
        "name": "Foreign Component",
        "charge_type": "setup_fee",
        "amount": 99.0,
        "active": True,
    })
    await db.pricing_saved_items.insert_one({
        "id": saved_item_id,
        "tenant_id": user_b["tenant_id"],
        "name": "Foreign Saved Item",
        "category": "promotional",
        "active": True,
    })

    with pytest.raises(ValueError, match="material_profile_not_found"):
        await resolve_references(tenant_id=user_a["tenant_id"], material_profile_id=profile_id)
    with pytest.raises(ValueError, match="pricing_component_not_found"):
        await resolve_references(tenant_id=user_a["tenant_id"], pricing_component_ids=[component_id])
    with pytest.raises(ValueError, match="saved_item_not_found"):
        await resolve_references(tenant_id=user_a["tenant_id"], saved_item_id=saved_item_id)

    async with await _client_as(user_a) as client:
        response = await client.post(
            "/api/pricing/calculate",
            json={
                "category": "services",
                "quantity": 1,
                "category_inputs": {"service_type": "general_labor", "estimated_hours": 1},
                "pricing_component_ids": [component_id],
            },
        )
    assert response.status_code == 404
    assert response.json()["detail"] == "Pricing component not found"
    assert "Foreign Component" not in response.text
    _clear()


@pytest.mark.asyncio
async def test_tenant_settings_remain_tenant_specific_and_mapping_is_non_mutating(seeded_users):
    user_a = seeded_users["user_a"]
    user_b = seeded_users["user_b"]
    settings_a = await get_or_init_pricing_settings(user_a["tenant_id"])
    settings_b = await get_or_init_pricing_settings(user_b["tenant_id"])
    await db.pricing_settings.update_one(
        {"tenant_id": user_b["tenant_id"]},
        {"$set": {"shop_defaults.production_hourly_rate": 80.0}},
    )
    settings_b = await get_or_init_pricing_settings(user_b["tenant_id"])

    inputs = {
        "category": "services",
        "width_inches": None,
        "height_inches": None,
        "quantity": 1,
        "category_inputs": {"service_type": "general_labor", "estimated_hours": 2},
    }
    before_a = deepcopy(settings_a)
    before_b = deepcopy(settings_b)
    result_a = calculate_pricing_with_cents_first_envelope(settings=settings_a, **inputs)
    result_b = calculate_pricing_with_cents_first_envelope(settings=settings_b, **inputs)

    assert settings_a == before_a
    assert settings_b == before_b
    assert result_a[PRICING_ENGINE_RESULT_FIELD]["selling_price_cents"] != result_b[PRICING_ENGINE_RESULT_FIELD]["selling_price_cents"]
    assert result_a[PRICING_ENGINE_RESULT_FIELD]["normalized_input"]["pricing_engine_configuration"]["adapter_id"] == SAAS_CONFIGURATION_ADAPTER_ID
    assert result_b[PRICING_ENGINE_RESULT_FIELD]["normalized_input"]["pricing_engine_configuration"]["adapter_id"] == SAAS_CONFIGURATION_ADAPTER_ID


@pytest.mark.asyncio
async def test_saved_calculation_reuse_and_quote_to_order_do_not_recalculate_historical_pricing(monkeypatch, seeded_users):
    user = seeded_users["user_a"]
    customer_id = await _seed_customer(user["tenant_id"])
    payload = {
        "category": "digital_print",
        "width_inches": 24,
        "height_inches": 36,
        "quantity": 1,
        "category_inputs": {"laminate": True},
    }

    saved = await calculate_saved_calculation_result(user["tenant_id"], payload)
    assert saved["pricing_engine_result"]["normalized_input"]["pricing_engine_configuration"]["adapter_id"] == SAAS_CONFIGURATION_ADAPTER_ID

    async with await _client_as(user) as client:
        quote_id = await _new_quote(client, customer_id)
        item = await client.post(
            f"/api/quotes/{quote_id}/line-items",
            json={
                "description": "9IQ digital print",
                "quantity": 1,
                "unit_price_cents": 0,
                "selected_price_source": "suggested",
                **payload,
            },
        )
        assert item.status_code == 201, item.text
        quote_item = item.json()
        quoted_cents = quote_item["suggested_price_cents"]

        def fail_if_called(*args, **kwargs):
            raise AssertionError("quote-to-order conversion must not map current pricing configuration")

        monkeypatch.setattr(pricing_service, "build_line_engine_configuration", fail_if_called)
        converted = await client.post(f"/api/quotes/{quote_id}/convert-to-order", json={})
        assert converted.status_code == 200, converted.text
        order_id = converted.json()["order"]["id"]
        order_detail = await client.get(f"/api/orders/{order_id}")
        assert order_detail.status_code == 200, order_detail.text
        order_item = order_detail.json()["items"][0]
        assert order_item["suggested_price_cents"] == quoted_cents
        assert order_item["pricing_snapshot"]["snapshot_id"] == quote_item["pricing_snapshot"]["snapshot_id"]
    _clear()
