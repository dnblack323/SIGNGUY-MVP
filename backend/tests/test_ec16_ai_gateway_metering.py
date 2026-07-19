"""EC16 - AI gateway metering, cost, credit, and idempotency tests."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.deps import get_current_user
from server import app


def _override(user: dict):
    async def _get():
        return {**user}

    return _get


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest_asyncio.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-ec16-meter-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    platform_admin = {
        "id": f"platform-{suffix}",
        "tenant_id": tenant_id,
        "email": f"platform-{suffix}@example.com",
        "role": "owner",
        "is_active": True,
        "platform_admin": True,
        "platform_role": "admin",
    }
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "EC16 Meter Tenant"})
    await db.users.insert_many([owner, platform_admin])
    yield {"suffix": suffix, "tenant_id": tenant_id, "owner": owner, "platform_admin": platform_admin}
    app.dependency_overrides.pop(get_current_user, None)


async def _setup_gateway(ctx: dict) -> str:
    async with await _client_as(ctx["platform_admin"]) as platform:
        provider = await platform.post("/api/ai/platform/providers", json={"provider_key": f"meterprovider{ctx['suffix']}", "display_name": "Meter Provider", "status": "active"})
        assert provider.status_code == 201, provider.text
        model = await platform.post(
            "/api/ai/platform/models",
            json={
                "provider_config_id": provider.json()["id"],
                "model_key": f"metermodel{ctx['suffix']}",
                "display_name": "Meter Model",
                "task_category": "pricing",
                "status": "active",
                "estimated_input_cost_micros_per_unit": 2,
                "estimated_output_cost_micros_per_unit": 3,
            },
        )
        assert model.status_code == 201, model.text
        capability = await platform.post(
            "/api/ai/platform/capabilities",
            json={
                "capability_key": f"meter.capability.{ctx['suffix']}",
                "display_name": "Meter Capability",
                "feature_key": "pricing",
                "action_key": "analysis",
                "entitlement_feature_key": f"ai.meter.{ctx['suffix']}",
                "status": "active",
                "default_credit_charge": 3,
                "allowed_model_profile_ids": [model.json()["id"]],
            },
        )
        assert capability.status_code == 201, capability.text
        grant = await platform.post(
            f"/api/ai/platform/credit-accounts/{ctx['tenant_id']}/grants",
            json={"included_credits": 10, "purchased_credits": 5, "reason": "EC16 test grant", "idempotency_key": f"grant-{ctx['suffix']}"},
        )
        assert grant.status_code == 201, grant.text
    await db.feature_entitlements.insert_one({"id": f"ent-{ctx['suffix']}", "tenant_id": ctx["tenant_id"], "feature_key": f"ai.meter.{ctx['suffix']}", "enabled": True, "granted_by": "test"})
    return capability.json()["capability_key"]


@pytest.mark.asyncio
async def test_gateway_success_is_metered_idempotent_and_separate_from_commerce(ctx):
    capability_key = await _setup_gateway(ctx)
    before_payments = await db.payments.count_documents({"tenant_id": ctx["tenant_id"]})
    before_invoices = await db.invoices.count_documents({"tenant_id": ctx["tenant_id"]})
    before_catalog = await db.commercial_products.count_documents({})
    before_webstore = await db.webstore_buyer_orders.count_documents({"tenant_id": ctx["tenant_id"]})
    before_wrap = await db.wrap_projects.count_documents({"tenant_id": ctx["tenant_id"]})

    async with await _client_as(ctx["owner"]) as owner:
        request = await owner.post(
            "/api/ai/gateway/requests",
            json={
                "capability_key": capability_key,
                "idempotency_key": f"gw-{ctx['suffix']}",
                "input_units": 100,
                "output_units": 50,
                "duration_ms": 42,
                "source_links": [{"entity_type": "pricing_snapshot", "entity_id": "snap-1"}],
            },
        )
        assert request.status_code == 201, request.text
        first = request.json()
        assert first["status"] == "succeeded"
        assert first["credit_charge_credits"] == 3
        repeat = await owner.post(
            "/api/ai/gateway/requests",
            json={"capability_key": capability_key, "idempotency_key": f"gw-{ctx['suffix']}", "input_units": 100, "output_units": 50},
        )
        assert repeat.status_code == 201
        assert repeat.json()["id"] == first["id"]

        account = await owner.get("/api/ai/credits/account")
        assert account.status_code == 200
        assert account.json()["included_balance_credits"] == 7
        assert account.json()["purchased_balance_credits"] == 5
        assert account.json()["reserved_credits"] == 0

    assert await db.ai_usage_ledger_entries.count_documents({"tenant_id": ctx["tenant_id"], "action_request_id": first["id"]}) == 1
    assert await db.ai_provider_cost_ledger_entries.count_documents({"tenant_id": ctx["tenant_id"], "action_request_id": first["id"]}) == 1
    assert await db.ai_credit_ledger_entries.count_documents({"tenant_id": ctx["tenant_id"], "action_request_id": first["id"], "entry_type": "reserve"}) == 1
    assert await db.ai_credit_ledger_entries.count_documents({"tenant_id": ctx["tenant_id"], "action_request_id": first["id"], "entry_type": "commit"}) == 1
    assert await db.ai_credit_ledger_entries.count_documents({"tenant_id": ctx["tenant_id"], "entry_type": "commit"}) == 1
    assert await db.payments.count_documents({"tenant_id": ctx["tenant_id"]}) == before_payments
    assert await db.invoices.count_documents({"tenant_id": ctx["tenant_id"]}) == before_invoices
    assert await db.commercial_products.count_documents({}) == before_catalog
    assert await db.webstore_buyer_orders.count_documents({"tenant_id": ctx["tenant_id"]}) == before_webstore
    assert await db.wrap_projects.count_documents({"tenant_id": ctx["tenant_id"]}) == before_wrap


@pytest.mark.asyncio
async def test_provider_failure_releases_reserved_credits_without_provider_call(ctx):
    capability_key = await _setup_gateway(ctx)
    async with await _client_as(ctx["owner"]) as owner:
        failed = await owner.post(
            "/api/ai/gateway/requests",
            json={"capability_key": capability_key, "idempotency_key": f"fail-{ctx['suffix']}", "simulate_result": "provider_failure", "input_units": 20},
        )
        assert failed.status_code == 201, failed.text
        assert failed.json()["status"] == "failed"
        account = await owner.get("/api/ai/credits/account")
        assert account.json()["included_balance_credits"] == 10
        assert account.json()["purchased_balance_credits"] == 5
        assert account.json()["reserved_credits"] == 0
    assert await db.ai_credit_ledger_entries.count_documents({"tenant_id": ctx["tenant_id"], "action_request_id": failed.json()["id"], "entry_type": "release"}) == 1
    cost = await db.ai_provider_cost_ledger_entries.find_one({"tenant_id": ctx["tenant_id"], "action_request_id": failed.json()["id"]}, {"_id": 0})
    assert cost["actual_cost_micros"] == 0
