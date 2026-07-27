"""EC9 Phase 9I-C Banner shared comparison contract tests."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.services import pricing_method_comparisons
from server import app
from app.core.db import db
from app.core.permissions import ROLE_PERMISSIONS, Perm
from app.deps import get_current_user
from app.services.pricing import calculate_pricing, get_or_init_pricing_settings


def _override_as(user: dict):
    async def _dep():
        return dict(user)

    return _dep


def _clear_override() -> None:
    app.dependency_overrides.pop(get_current_user, None)


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override_as(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _banner_payload(**overrides):
    payload = {
        "category": "banners",
        "width_inches": 96,
        "height_inches": 36,
        "quantity": 1,
        "category_inputs": {"dimension_unit": "in"},
    }
    payload.update(overrides)
    return payload


def _amount_by_method(body: dict, method_id: str) -> float:
    for row in body["comparison_results"]:
        if row["method_id"] == method_id:
            return row["amount"]
    raise AssertionError(f"method missing: {method_id}")


def _direct_ordinary_banner(settings: dict) -> dict:
    return calculate_pricing(
        settings=settings,
        category="banners",
        width_inches=96,
        height_inches=36,
        quantity=1,
        category_inputs={"dimension_unit": "in"},
    )


async def _tenant_counts(tenant_id: str) -> dict[str, int]:
    collections = [
        "pricing_settings",
        "audit_events",
        "pricing_snapshot_records",
        "pricing_calculation_records",
        "quotes",
        "orders",
        "order_items",
        "work_orders",
    ]
    return {
        collection: await db[collection].count_documents({"tenant_id": tenant_id})
        for collection in collections
    }


@pytest.mark.asyncio
async def test_banner_comparison_contract_wraps_existing_results_without_mutating_pricing(seeded_users):
    user = seeded_users["user_a"]
    settings = await get_or_init_pricing_settings(user["tenant_id"])
    before = _direct_ordinary_banner(settings)
    audit_before = await db.audit_events.count_documents({"tenant_id": user["tenant_id"]})

    async with await _client_as(user) as c:
        res = await c.post("/api/pricing/method-comparison", json=_banner_payload())
        assert res.status_code == 200, res.text
        body = res.json()

    settings_after = await get_or_init_pricing_settings(user["tenant_id"])
    after = _direct_ordinary_banner(settings_after)
    audit_after = await db.audit_events.count_documents({"tenant_id": user["tenant_id"]})

    assert body["category_id"] == "banners"
    assert body["configuration_source"] == "existing_calculator_defaults"
    assert body["settings_source"] == "persisted_settings"
    assert body["mutated"] is False
    assert body["persistent_entities_created"] == []
    assert body["selected_method_id"] == "square_foot_plus_addons"
    assert body["primary_method_id"] == "square_foot_plus_addons"
    assert body["canonical_method_id"] == "square_foot_plus_addons"
    assert body["pricing_result"]["selling_price"] == before["selling_price"] == after["selling_price"]
    assert body["pricing_result"]["pricing_method_used"] == before["pricing_method_used"] == after["pricing_method_used"]
    assert body["pricing_result"]["pricing_method_results"] == before["pricing_method_results"] == after["pricing_method_results"]
    assert body["comparison_results"][0]["method_id"] == "square_foot_plus_addons"
    assert _amount_by_method(body, "cost_plus") > body["pricing_result"]["selling_price"]
    assert audit_after == audit_before
    stored = await db.pricing_settings.find_one({"tenant_id": user["tenant_id"]}, {"_id": 0})
    assert "banners" not in (stored.get("category_method_configurations") or {})
    _clear_override()


@pytest.mark.asyncio
async def test_saved_banner_configuration_controls_order_and_selected_method_without_highest_default(seeded_users):
    user = seeded_users["user_a"]
    async with await _client_as(user) as c:
        saved = await c.put("/api/pricing/settings/categories/banners/advanced-setup", json={
            "enabled_method_ids": ["cost_plus", "square_foot_plus_addons"],
            "primary_method_id": "cost_plus",
            "comparison_order": ["cost_plus", "square_foot_plus_addons"],
            "compare_automatically": False,
        })
        assert saved.status_code == 200, saved.text
        res = await c.post("/api/pricing/method-comparison", json=_banner_payload(
            expected_configuration_version=saved.json()["configuration_version"],
        ))
        assert res.status_code == 200, res.text
        body = res.json()

    settings = await get_or_init_pricing_settings(user["tenant_id"])
    ordinary = _direct_ordinary_banner(settings)
    reread = await db.pricing_settings.find_one({"tenant_id": user["tenant_id"]}, {"_id": 0})
    saved_config = (reread.get("category_method_configurations") or {}).get("banners")

    assert body["configuration_source"] == "saved_tenant_configuration"
    assert body["configuration_version"] == saved.json()["configuration_version"]
    assert body["comparison_order"] == ["cost_plus", "square_foot_plus_addons"]
    assert [row["method_id"] for row in body["comparison_results"]] == ["cost_plus", "square_foot_plus_addons"]
    assert body["selected_method_id"] == "cost_plus"
    assert body["primary_method_id"] == "cost_plus"
    assert body["canonical_method_id"] == "square_foot_plus_addons"
    assert [row["method_id"] for row in body["comparison_results"] if row["selected"]] == ["cost_plus"]
    assert body["pricing_result"]["pricing_method_used"] == "square_foot_plus_addons"
    assert body["pricing_result"]["selling_price"] == ordinary["selling_price"] == _amount_by_method(body, "square_foot_plus_addons")
    assert body["pricing_result"]["selling_price"] != _amount_by_method(body, "cost_plus")
    assert _amount_by_method(body, "square_foot_plus_addons") < _amount_by_method(body, "cost_plus")
    assert saved_config["configuration_version"] == saved.json()["configuration_version"]
    _clear_override()


@pytest.mark.asyncio
async def test_explicit_banner_comparison_methods_are_non_persistent_and_limited(seeded_users):
    user = seeded_users["user_a"]
    async with await _client_as(user) as c:
        res = await c.post("/api/pricing/method-comparison", json=_banner_payload(
            method_ids=["target_margin", "square_foot_plus_addons"],
            primary_method_id="target_margin",
        ))
        assert res.status_code == 200, res.text
        duplicate = await c.post("/api/pricing/method-comparison", json=_banner_payload(
            method_ids=["cost_plus", "cost_plus"],
            primary_method_id="cost_plus",
        ))
        too_many = await c.post("/api/pricing/method-comparison", json=_banner_payload(
            method_ids=["square_foot_plus_addons", "cost_plus", "target_margin", "minimum_charge"],
            primary_method_id="square_foot_plus_addons",
        ))
        unsupported = await c.post("/api/pricing/method-comparison", json=_banner_payload(
            method_ids=["per_sqft"],
            primary_method_id="per_sqft",
        ))

    body = res.json()
    assert body["configuration_source"] == "explicit_request"
    assert body["comparison_order"] == ["target_margin", "square_foot_plus_addons"]
    assert body["selected_method_id"] == "target_margin"
    assert body["primary_method_id"] == "target_margin"
    assert body["canonical_method_id"] == "square_foot_plus_addons"
    assert body["pricing_result"]["pricing_method_used"] == "square_foot_plus_addons"
    assert body["pricing_result"]["selling_price"] == _amount_by_method(body, "square_foot_plus_addons")
    assert body["pricing_result"]["selling_price"] != _amount_by_method(body, "target_margin")
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"]["code"] == "duplicate_method"
    assert too_many.status_code in {400, 422}
    assert unsupported.status_code == 400
    assert unsupported.json()["detail"]["code"] == "unsupported_method"
    assert await db.audit_events.count_documents({"tenant_id": user["tenant_id"], "entity_type": "pricing_method_configuration"}) == 0
    _clear_override()


@pytest.mark.asyncio
async def test_first_run_tenant_comparison_uses_read_only_starter_fallback_without_persistence(seeded_users):
    user = seeded_users["user_a"]
    before = await _tenant_counts(user["tenant_id"])
    assert before["pricing_settings"] == 0

    async with await _client_as(user) as c:
        res = await c.post("/api/pricing/method-comparison", json=_banner_payload())
    assert res.status_code == 200, res.text
    body = res.json()
    after = await _tenant_counts(user["tenant_id"])

    assert after == before
    assert body["mutated"] is False
    assert body["persistent_entities_created"] == []
    assert body["settings_source"] == "starter_defaults_fallback"
    assert body["configuration_source"] == "starter_defaults_fallback"
    assert body["configuration_version"] is None
    assert body["pricing_result"]["selling_price"] == 192.0
    assert body["pricing_result"]["pricing_method_used"] == "square_foot_plus_addons"
    assert await db.pricing_settings.find_one({"tenant_id": user["tenant_id"]}) is None
    _clear_override()


@pytest.mark.asyncio
async def test_unsupported_category_returns_structured_404_without_dispatch_or_persistence(seeded_users, monkeypatch):
    user = seeded_users["user_a"]
    before = await _tenant_counts(user["tenant_id"])

    def _fail_if_called(**_kwargs):
        raise AssertionError("calculate_pricing should not run for unsupported comparison categories")

    monkeypatch.setattr(pricing_method_comparisons, "calculate_pricing", _fail_if_called)
    async with await _client_as(user) as c:
        res = await c.post("/api/pricing/method-comparison", json={
            **_banner_payload(),
            "category": "rigid_signs",
        })
    after = await _tenant_counts(user["tenant_id"])

    assert res.status_code == 404
    assert res.json()["detail"] == {
        "field": "category_id",
        "code": "comparison_not_available",
        "message": "Shared comparison is currently available only for Banners in Phase 9I-C.",
    }
    assert after == before
    _clear_override()


@pytest.mark.asyncio
async def test_failed_or_missing_existing_method_results_are_not_fabricated_or_selected_by_price(seeded_users, monkeypatch):
    user = seeded_users["user_a"]
    before = await _tenant_counts(user["tenant_id"])

    def _fake_existing_calculation(**_kwargs):
        return {
            "category": "banners",
            "selling_price": 192.0,
            "true_cost": 99.64,
            "pricing_method_used": "square_foot_plus_addons",
            "selected_pricing_method": "square_foot_plus_addons",
            "pricing_method_results": [
                {
                    "method": "square_foot_plus_addons",
                    "label": "Square-foot base + add-ons",
                    "amount": 192.0,
                    "pre_adjustment_amount": 192.0,
                    "status": ["selected"],
                    "enabled": True,
                },
                {
                    "method": "cost_plus",
                    "label": "Cost + markup",
                    "amount": None,
                    "pre_adjustment_amount": None,
                    "status": ["failed", "missing_cost_basis"],
                    "enabled": True,
                },
            ],
        }

    monkeypatch.setattr(pricing_method_comparisons, "calculate_pricing", _fake_existing_calculation)
    response = await pricing_method_comparisons.compare_pricing_methods(
        tenant_id=user["tenant_id"],
        category_id="banners",
        width_inches=96,
        height_inches=36,
        quantity=1,
        method_ids=["cost_plus", "square_foot_plus_addons", "target_margin"],
        primary_method_id="cost_plus",
    )
    after = await _tenant_counts(user["tenant_id"])

    assert response["primary_method_id"] == "cost_plus"
    assert response["selected_method_id"] == "cost_plus"
    assert response["canonical_method_id"] == "square_foot_plus_addons"
    assert response["pricing_result"]["selling_price"] == 192.0
    assert [row["method_id"] for row in response["comparison_results"]] == ["cost_plus", "square_foot_plus_addons"]
    cost_plus = response["comparison_results"][0]
    assert cost_plus["amount"] is None
    assert cost_plus["pre_adjustment_amount"] is None
    assert cost_plus["available"] is False
    assert cost_plus["selected"] is True
    assert "failed" in cost_plus["status"]
    assert "target_margin" not in {row["method_id"] for row in response["comparison_results"]}
    assert response["mutated"] is False
    assert response["persistent_entities_created"] == []
    assert after == before


@pytest.mark.asyncio
async def test_banner_comparison_is_tenant_isolated(seeded_users):
    user_a = seeded_users["user_a"]
    user_b = seeded_users["user_b"]
    async with await _client_as(user_a) as c:
        a_saved = await c.put("/api/pricing/settings/categories/banners/advanced-setup", json={
            "enabled_method_ids": ["cost_plus"],
            "primary_method_id": "cost_plus",
            "comparison_order": ["cost_plus"],
        })
        assert a_saved.status_code == 200
    _clear_override()

    async with await _client_as(user_b) as c:
        b_saved = await c.put("/api/pricing/settings/categories/banners/advanced-setup", json={
            "enabled_method_ids": ["square_foot_plus_addons"],
            "primary_method_id": "square_foot_plus_addons",
            "comparison_order": ["square_foot_plus_addons"],
        })
        assert b_saved.status_code == 200
        b_res = await c.post("/api/pricing/method-comparison", json=_banner_payload())
        assert b_res.status_code == 200
    _clear_override()

    async with await _client_as(user_a) as c:
        a_res = await c.post("/api/pricing/method-comparison", json=_banner_payload())
        assert a_res.status_code == 200
        not_my_version = await c.post("/api/pricing/method-comparison", json=_banner_payload(
            expected_configuration_version=999,
        ))
        assert not_my_version.status_code == 409

    assert [row["method_id"] for row in a_res.json()["comparison_results"]] == ["cost_plus"]
    assert [row["method_id"] for row in b_res.json()["comparison_results"]] == ["square_foot_plus_addons"]
    _clear_override()


@pytest.mark.asyncio
async def test_method_comparison_requires_pricing_calculate_and_rejects_portal_token(seeded_users):
    user = {**seeded_users["user_a"], "role": "no_pricing"}
    async with await _client_as(user) as c:
        denied = await c.post("/api/pricing/method-comparison", json=_banner_payload())
    assert denied.status_code == 403
    _clear_override()

    token = "portal-" + uuid.uuid4().hex
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"}) as c:
        rejected = await c.post("/api/pricing/method-comparison", json=_banner_payload())
    assert rejected.status_code in {401, 403}


@pytest.mark.asyncio
async def test_audit_history_requires_audit_permission_not_only_pricing_read(seeded_users, monkeypatch):
    role = f"pricing-reader-{uuid.uuid4().hex[:8]}"
    monkeypatch.setitem(ROLE_PERMISSIONS, role, [Perm.PRICING_READ.value])
    user = {**seeded_users["user_a"], "role": role}
    async with await _client_as(user) as c:
        denied = await c.get("/api/pricing/settings/categories/banners/method-configuration/audit")
    assert denied.status_code == 403
    assert "audit:read" in denied.json()["detail"]
    _clear_override()


@pytest.mark.asyncio
async def test_method_availability_saved_item_reference_is_tenant_scoped(seeded_users):
    user_a = seeded_users["user_a"]
    user_b = seeded_users["user_b"]
    other_item_id = f"promo-{uuid.uuid4().hex[:8]}"
    await db.pricing_saved_items.insert_one({
        "id": other_item_id,
        "tenant_id": user_b["tenant_id"],
        "name": "Other Tenant Business Cards",
        "category": "promotional",
        "default_pricing_method": "tier_pricing",
        "quantity_tiers": [{"quantity": 100, "price": 25.0}],
        "active": True,
    })
    async with await _client_as(user_a) as c:
        denied = await c.post("/api/pricing/settings/categories/promotional/method-availability", json={
            "saved_item_id": other_item_id,
        })
    assert denied.status_code == 404
    assert denied.json()["detail"] == "Saved item not found"
    _clear_override()


@pytest.mark.asyncio
async def test_platform_role_does_not_grant_tenant_pricing_write(seeded_users):
    user = {
        **seeded_users["user_a"],
        "role": "staff",
        "platform_role": "PLATFORM_CREATOR",
        "platform_admin": True,
        "permissions": ["platform:creator", "platform:admin"],
    }
    async with await _client_as(user) as c:
        read_ok = await c.post("/api/pricing/settings/categories/banners/simple-setup/preview")
        denied_write = await c.put("/api/pricing/settings/categories/banners/advanced-setup", json={
            "enabled_method_ids": ["square_foot_plus_addons"],
            "primary_method_id": "square_foot_plus_addons",
            "comparison_order": ["square_foot_plus_addons"],
        })
    assert read_ok.status_code == 200
    assert denied_write.status_code == 403
    _clear_override()
