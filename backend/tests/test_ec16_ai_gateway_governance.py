"""EC16 - AI gateway governance, limits, and alert tests."""
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
    tenant_id = f"t-ec16-gov-{suffix}"
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
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "EC16 Gov Tenant"})
    await db.users.insert_many([owner, platform_admin])
    yield {"suffix": suffix, "tenant_id": tenant_id, "owner": owner, "platform_admin": platform_admin}
    app.dependency_overrides.pop(get_current_user, None)


async def _setup_capability(ctx: dict) -> str:
    async with await _client_as(ctx["platform_admin"]) as platform:
        provider = await platform.post("/api/ai/platform/providers", json={"provider_key": f"govprovider{ctx['suffix']}", "display_name": "Gov Provider", "status": "active"})
        model = await platform.post(
            "/api/ai/platform/models",
            json={"provider_config_id": provider.json()["id"], "model_key": f"govmodel{ctx['suffix']}", "display_name": "Gov Model", "task_category": "pricing", "status": "active"},
        )
        capability = await platform.post(
            "/api/ai/platform/capabilities",
            json={
                "capability_key": f"gov.capability.{ctx['suffix']}",
                "display_name": "Gov Capability",
                "feature_key": "pricing",
                "action_key": "analysis",
                "entitlement_feature_key": f"ai.gov.{ctx['suffix']}",
                "status": "active",
                "default_credit_charge": 1,
                "allowed_model_profile_ids": [model.json()["id"]],
            },
        )
        assert capability.status_code == 201, capability.text
    await db.feature_entitlements.insert_one({"id": f"ent-{ctx['suffix']}", "tenant_id": ctx["tenant_id"], "feature_key": f"ai.gov.{ctx['suffix']}", "enabled": True, "granted_by": "test"})
    return capability.json()["capability_key"]


@pytest.mark.asyncio
async def test_zero_credit_blocks_billable_request_and_creates_alert(ctx):
    capability_key = await _setup_capability(ctx)
    async with await _client_as(ctx["owner"]) as owner:
        blocked = await owner.post("/api/ai/gateway/requests", json={"capability_key": capability_key, "idempotency_key": f"zero-{ctx['suffix']}"})
        assert blocked.status_code == 402
        alerts = await owner.get("/api/ai/alerts", params={"status": "open"})
        assert alerts.status_code == 200
        assert any(a["alert_type"] == "zero_credit" for a in alerts.json()["items"])


@pytest.mark.asyncio
async def test_rate_limit_blocks_second_request_and_platform_dashboard_counts(ctx):
    capability_key = await _setup_capability(ctx)
    async with await _client_as(ctx["platform_admin"]) as platform:
        grant = await platform.post(f"/api/ai/platform/credit-accounts/{ctx['tenant_id']}/grants", json={"included_credits": 5, "reason": "governance test"})
        assert grant.status_code == 201, grant.text
        policy = await platform.post(
            "/api/ai/platform/governance-policies",
            json={"scope_type": "capability", "capability_key": capability_key, "status": "active", "max_requests_per_day": 1},
        )
        assert policy.status_code == 201, policy.text

    async with await _client_as(ctx["owner"]) as owner:
        first = await owner.post("/api/ai/gateway/requests", json={"capability_key": capability_key, "idempotency_key": f"first-{ctx['suffix']}"})
        assert first.status_code == 201, first.text
        second = await owner.post("/api/ai/gateway/requests", json={"capability_key": capability_key, "idempotency_key": f"second-{ctx['suffix']}"})
        assert second.status_code == 429

    async with await _client_as(ctx["platform_admin"]) as platform:
        dashboard = await platform.get("/api/ai/platform/dashboard")
        assert dashboard.status_code == 200
        assert dashboard.json()["external_provider_calls"] == 0
        assert dashboard.json()["open_alerts"] >= 1
