"""EC9 Phase 9I-B tenant pricing-method configuration tests."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from server import app
from app.core.db import db
from app.core.security import create_access_token
from app.deps import get_current_user
from app.services.pricing import calculate_pricing, get_or_init_pricing_settings
from app.services.pricing_method_registry import get_category_definition
from app.services.starter_defaults import build_starter_pack


def _override_as(user: dict):
    async def _dep():
        return dict(user)

    return _dep


def _clear_override() -> None:
    app.dependency_overrides.pop(get_current_user, None)


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override_as(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _anon_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _insert_promotional_tier_item(tenant_id: str, *, name: str = "Configured Promo") -> str:
    item_id = f"promo-{uuid.uuid4().hex[:8]}"
    await db.pricing_saved_items.insert_one({
        "id": item_id,
        "tenant_id": tenant_id,
        "name": name,
        "category": "promotional",
        "default_pricing_method": "tier_pricing",
        "quantity_tiers": [{"quantity": 100, "price": 25.0}],
        "active": True,
        "quick_select": True,
    })
    return item_id


@pytest.mark.asyncio
async def test_create_read_update_and_reread_tenant_category_configuration(seeded_users):
    user = seeded_users["user_a"]
    async with await _client_as(user) as c:
        create = await c.put("/api/pricing/settings/categories/rigid_signs/advanced-setup", json={
            "enabled_method_ids": ["per_sqft", "cost_plus"],
            "primary_method_id": "per_sqft",
            "comparison_order": ["cost_plus", "per_sqft"],
            "compare_automatically": True,
            "method_configuration_refs": {"per_sqft": "category_defaults.rigid_signs"},
        })
        assert create.status_code == 200, create.text
        body = create.json()
        assert body["configuration_version"] == 1
        assert body["tenant_id"] == user["tenant_id"]
        assert body["category_id"] == "rigid_signs"
        assert body["comparison_order"] == ["cost_plus", "per_sqft"]

        reread = await c.get("/api/pricing/settings/categories/rigid_signs/method-configuration")
        assert reread.status_code == 200
        assert reread.json()["method_configuration_refs"] == {"per_sqft": "category_defaults.rigid_signs"}

        update = await c.put("/api/pricing/settings/categories/rigid_signs/advanced-setup", json={
            "enabled_method_ids": ["per_sqft"],
            "primary_method_id": "per_sqft",
            "comparison_order": ["per_sqft"],
            "compare_automatically": False,
            "expected_configuration_version": 1,
        })
        assert update.status_code == 200, update.text
        assert update.json()["configuration_version"] == 2
        assert update.json()["enabled_method_ids"] == ["per_sqft"]
    _clear_override()


@pytest.mark.asyncio
async def test_one_configuration_per_tenant_category_and_tenants_are_isolated(seeded_users):
    user_a = seeded_users["user_a"]
    user_b = seeded_users["user_b"]
    async with await _client_as(user_a) as c:
        first = await c.post("/api/pricing/settings/categories/custom/simple-setup/apply", json={})
        assert first.status_code == 200, first.text
        second = await c.post("/api/pricing/settings/categories/custom/simple-setup/apply", json={})
        assert second.status_code == 200
        assert second.json()["configuration_version"] == first.json()["configuration_version"]
        audits = await db.audit_events.count_documents({
            "tenant_id": user_a["tenant_id"],
            "entity_type": "pricing_method_configuration",
            "entity_id": "custom",
        })
        assert audits == 1
    _clear_override()

    async with await _client_as(user_b) as c:
        mine = await c.get("/api/pricing/settings/category-method-configurations")
        assert mine.status_code == 200
        assert mine.json()["items"] == []
        created = await c.put("/api/pricing/settings/categories/custom/advanced-setup", json={
            "enabled_method_ids": ["unit_price_x_quantity"],
            "primary_method_id": "unit_price_x_quantity",
            "comparison_order": ["unit_price_x_quantity"],
        })
        assert created.status_code == 200
        assert created.json()["tenant_id"] == user_b["tenant_id"]
    _clear_override()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload,field",
    [
        ({"enabled_method_ids": ["not_a_method"], "primary_method_id": "not_a_method"}, "enabled_method_ids"),
        ({"enabled_method_ids": ["per_sqft", "per_sqft"], "primary_method_id": "per_sqft"}, "enabled_method_ids"),
        ({"enabled_method_ids": ["per_sqft", "cost_plus", "target_margin", "minimum_charge"], "primary_method_id": "per_sqft"}, "enabled_method_ids"),
        ({"enabled_method_ids": ["per_sqft"], "primary_method_id": ""}, "primary_method_id"),
        ({"enabled_method_ids": ["per_sqft"], "primary_method_id": "cost_plus"}, "primary_method_id"),
        ({"enabled_method_ids": ["per_sqft", "cost_plus"], "primary_method_id": "per_sqft", "comparison_order": ["per_sqft"]}, "comparison_order"),
    ],
)
async def test_advanced_validation_returns_structured_errors(seeded_users, payload, field):
    user = seeded_users["user_a"]
    base = {"comparison_order": payload.get("enabled_method_ids", []), "compare_automatically": False}
    async with await _client_as(user) as c:
        res = await c.put("/api/pricing/settings/categories/rigid_signs/advanced-setup", json={**base, **payload})
        assert res.status_code in {400, 422}, res.text
        if res.status_code == 400:
            assert res.json()["detail"]["field"] == field
    _clear_override()


@pytest.mark.asyncio
async def test_unknown_category_and_unavailable_contextual_method_are_rejected(seeded_users):
    user = seeded_users["user_a"]
    await get_or_init_pricing_settings(user["tenant_id"])
    await db.pricing_settings.update_one(
        {"tenant_id": user["tenant_id"]},
        {"$set": {"category_defaults.vehicle_graphics.benchmark_prices": {}}},
    )
    async with await _client_as(user) as c:
        unknown = await c.put("/api/pricing/settings/categories/nope/advanced-setup", json={
            "enabled_method_ids": ["per_sqft"],
            "primary_method_id": "per_sqft",
            "comparison_order": ["per_sqft"],
        })
        assert unknown.status_code == 404

        unavailable = await c.put("/api/pricing/settings/categories/vehicle_graphics/advanced-setup", json={
            "enabled_method_ids": ["vehicle_benchmark", "vehicle_cost_plus"],
            "primary_method_id": "vehicle_benchmark",
            "comparison_order": ["vehicle_benchmark", "vehicle_cost_plus"],
        })
        assert unavailable.status_code == 400
        assert unavailable.json()["detail"]["code"] == "missing_vehicle_benchmark"
    _clear_override()


@pytest.mark.asyncio
async def test_simple_preview_is_non_mutating_and_deterministic(seeded_users):
    user = seeded_users["user_a"]
    async with await _client_as(user) as c:
        before = await db.audit_events.count_documents({"tenant_id": user["tenant_id"]})
        p1 = await c.post("/api/pricing/settings/categories/rigid_signs/simple-setup/preview")
        p2 = await c.post("/api/pricing/settings/categories/rigid_signs/simple-setup/preview")
        assert p1.status_code == p2.status_code == 200
        assert p1.json() == p2.json()
        assert p1.json()["recommended_method_ids"] == ["per_sqft", "cost_plus"]
        assert p1.json()["mutated"] is False
        stored = await c.get("/api/pricing/settings/categories/rigid_signs/method-configuration")
        assert stored.status_code == 404
        after = await db.audit_events.count_documents({"tenant_id": user["tenant_id"]})
        assert after == before
    _clear_override()


@pytest.mark.asyncio
async def test_simple_setup_one_method_custom_and_vehicle_omits_unavailable_benchmark(seeded_users):
    user = seeded_users["user_a"]
    await get_or_init_pricing_settings(user["tenant_id"])
    await db.pricing_settings.update_one(
        {"tenant_id": user["tenant_id"]},
        {"$set": {"category_defaults.vehicle_graphics.benchmark_prices": {}}},
    )
    async with await _client_as(user) as c:
        custom = await c.post("/api/pricing/settings/categories/custom/simple-setup/preview")
        assert custom.status_code == 200
        assert custom.json()["recommended_method_ids"] == ["unit_price_x_quantity"]
        assert custom.json()["warnings"][0]["code"] == "single_method_available"

        vehicle = await c.post("/api/pricing/settings/categories/vehicle_graphics/simple-setup/preview")
        assert vehicle.status_code == 200
        assert vehicle.json()["recommended_method_ids"] == ["vehicle_cost_plus"]
        reasons = {m["method_id"]: m["reason"] for m in vehicle.json()["availability"]["methods"]}
        assert reasons["vehicle_benchmark"] == "missing_vehicle_benchmark"
    _clear_override()


@pytest.mark.asyncio
async def test_promotional_methods_respect_tenant_configuration(seeded_users):
    user = seeded_users["user_a"]
    async with await _client_as(user) as c:
        empty = await c.post("/api/pricing/settings/categories/promotional/simple-setup/preview")
        assert empty.status_code == 200
        assert empty.json()["recommended_method_ids"] == []

        item_id = await _insert_promotional_tier_item(user["tenant_id"])
        tier_only = await c.post("/api/pricing/settings/categories/promotional/simple-setup/preview")
        assert tier_only.status_code == 200
        assert tier_only.json()["recommended_method_ids"] == ["tier_pricing"]

        availability = await c.post("/api/pricing/settings/categories/promotional/method-availability", json={
            "saved_item_id": item_id,
            "category_inputs": {"flat_fee_price": 50.0, "unit_cost": 2.5},
        })
        assert availability.status_code == 200
        assert availability.json()["available_method_ids"] == ["tier_pricing", "per_piece", "flat_fee"]
    _clear_override()


@pytest.mark.asyncio
async def test_simple_apply_conflict_and_confirmed_replacement_are_audited(seeded_users):
    user = seeded_users["user_a"]
    async with await _client_as(user) as c:
        adv = await c.put("/api/pricing/settings/categories/rigid_signs/advanced-setup", json={
            "enabled_method_ids": ["per_sqft"],
            "primary_method_id": "per_sqft",
            "comparison_order": ["per_sqft"],
        })
        assert adv.status_code == 200
        conflict = await c.post("/api/pricing/settings/categories/rigid_signs/simple-setup/apply", json={
            "expected_configuration_version": adv.json()["configuration_version"],
        })
        assert conflict.status_code == 409
        replace = await c.post("/api/pricing/settings/categories/rigid_signs/simple-setup/apply", json={
            "expected_configuration_version": adv.json()["configuration_version"],
            "replace_advanced": True,
        })
        assert replace.status_code == 200
        assert replace.json()["configuration_mode"] == "simple"
        audit = await db.audit_events.find_one({
            "tenant_id": user["tenant_id"],
            "action": "pricing.method_config.simple.replace_advanced",
            "entity_id": "rigid_signs",
        }, {"_id": 0})
        assert audit
        assert "enabled_method_ids" in audit["diff"]["changed_fields"]
    _clear_override()


@pytest.mark.asyncio
async def test_advanced_setup_requires_permission_and_portal_tokens_are_rejected(seeded_users):
    user = seeded_users["user_a"]
    staff = {**user, "id": f"staff-{uuid.uuid4().hex[:8]}", "role": "staff", "email": f"staff-{uuid.uuid4().hex[:6]}@example.com"}
    async with await _client_as(staff) as c:
        readable = await c.post("/api/pricing/settings/categories/custom/simple-setup/preview")
        assert readable.status_code == 200
        denied = await c.put("/api/pricing/settings/categories/custom/advanced-setup", json={
            "enabled_method_ids": ["unit_price_x_quantity"],
            "primary_method_id": "unit_price_x_quantity",
            "comparison_order": ["unit_price_x_quantity"],
        })
        assert denied.status_code == 403
    _clear_override()

    portal_token = create_access_token(
        subject="portal-user",
        tenant_id=user["tenant_id"],
        extra={"sub_scope": "portal", "typ": "portal_access"},
    )
    async with await _anon_client() as c:
        denied = await c.put(
            "/api/pricing/settings/categories/custom/advanced-setup",
            headers={"Authorization": f"Bearer {portal_token}"},
            json={
                "enabled_method_ids": ["unit_price_x_quantity"],
                "primary_method_id": "unit_price_x_quantity",
                "comparison_order": ["unit_price_x_quantity"],
            },
        )
        assert denied.status_code == 401


@pytest.mark.asyncio
async def test_stale_version_fails_and_restore_preserves_unrelated_defaults(seeded_users):
    user = seeded_users["user_a"]
    async with await _client_as(user) as c:
        created = await c.put("/api/pricing/settings/categories/rigid_signs/advanced-setup", json={
            "enabled_method_ids": ["per_sqft"],
            "primary_method_id": "per_sqft",
            "comparison_order": ["per_sqft"],
        })
        assert created.status_code == 200
        stale = await c.put("/api/pricing/settings/categories/rigid_signs/advanced-setup", json={
            "enabled_method_ids": ["per_sqft", "cost_plus"],
            "primary_method_id": "per_sqft",
            "comparison_order": ["per_sqft", "cost_plus"],
            "expected_configuration_version": 99,
        })
        assert stale.status_code == 409

        await db.pricing_settings.update_one(
            {"tenant_id": user["tenant_id"]},
            {"$set": {"category_defaults.rigid_signs.minimum_charge": 123.45}},
        )
        conflict = await c.post("/api/pricing/settings/categories/rigid_signs/restore-recommendations", json={
            "expected_configuration_version": created.json()["configuration_version"],
        })
        assert conflict.status_code == 409
        restored = await c.post("/api/pricing/settings/categories/rigid_signs/restore-recommendations", json={
            "expected_configuration_version": created.json()["configuration_version"],
            "replace_advanced": True,
        })
        assert restored.status_code == 200
        settings = await get_or_init_pricing_settings(user["tenant_id"])
        assert settings["category_defaults"]["rigid_signs"]["minimum_charge"] == 123.45
    _clear_override()


@pytest.mark.asyncio
async def test_legacy_aliases_are_narrow_and_registry_is_not_mutated(seeded_users):
    user = seeded_users["user_a"]
    before = get_category_definition("services").to_dict()
    async with await _client_as(user) as c:
        mapped = await c.put("/api/pricing/settings/categories/services/advanced-setup", json={
            "enabled_method_ids": ["cost_plus_labor"],
            "primary_method_id": "cost_plus_labor",
            "comparison_order": ["cost_plus_labor"],
        })
        assert mapped.status_code == 200, mapped.text
        assert mapped.json()["enabled_method_ids"] == ["cost_plus"]

        ambiguous = await c.put("/api/pricing/settings/categories/services/advanced-setup", json={
            "enabled_method_ids": ["common_job_prices"],
            "primary_method_id": "common_job_prices",
            "comparison_order": ["common_job_prices"],
        })
        assert ambiguous.status_code == 400
        assert ambiguous.json()["detail"]["code"] == "ambiguous_legacy_method"

        bad_ref = await c.put("/api/pricing/settings/categories/services/advanced-setup", json={
            "enabled_method_ids": ["service_rate"],
            "primary_method_id": "service_rate",
            "comparison_order": ["service_rate"],
            "method_configuration_refs": {"cost_plus": "not-enabled"},
        })
        assert bad_ref.status_code == 400
        assert bad_ref.json()["detail"]["code"] == "reference_method_not_enabled"
    _clear_override()
    assert get_category_definition("services").to_dict() == before


@pytest.mark.asyncio
async def test_existing_pricing_results_and_snapshots_are_unchanged(seeded_users):
    user = seeded_users["user_a"]
    settings_before = build_starter_pack()
    result_before = calculate_pricing(
        settings=settings_before,
        category="banners",
        width_inches=8,
        height_inches=3,
        quantity=1,
        category_inputs={"dimension_unit": "ft"},
    )
    async with await _client_as(user) as c:
        saved = await c.put("/api/pricing/settings/categories/banners/advanced-setup", json={
            "enabled_method_ids": ["square_foot_plus_addons", "cost_plus", "target_margin"],
            "primary_method_id": "square_foot_plus_addons",
            "comparison_order": ["square_foot_plus_addons", "cost_plus", "target_margin"],
        })
        assert saved.status_code == 200, saved.text
    _clear_override()

    settings_after = build_starter_pack()
    result_after = calculate_pricing(
        settings=settings_after,
        category="banners",
        width_inches=8,
        height_inches=3,
        quantity=1,
        category_inputs={"dimension_unit": "ft"},
    )
    assert result_after["selling_price"] == result_before["selling_price"] == 192.00
    assert result_after["pricing_method_results"] == result_before["pricing_method_results"]
    assert await db.quotes.count_documents({"tenant_id": user["tenant_id"]}) == 0
    assert await db.orders.count_documents({"tenant_id": user["tenant_id"]}) == 0


@pytest.mark.asyncio
async def test_audit_history_endpoint_returns_method_configuration_events(seeded_users):
    user = seeded_users["user_a"]
    async with await _client_as(user) as c:
        created = await c.post("/api/pricing/settings/categories/custom/simple-setup/apply", json={})
        assert created.status_code == 200
        history = await c.get("/api/pricing/settings/categories/custom/method-configuration/audit")
        assert history.status_code == 200
        assert history.json()["total"] == 1
        assert history.json()["items"][0]["action"] == "pricing.method_config.simple.apply"
    _clear_override()
