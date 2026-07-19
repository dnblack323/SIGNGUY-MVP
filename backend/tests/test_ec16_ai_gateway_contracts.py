"""EC16 - AI gateway contract and permission tests."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.portal_security import create_portal_token
from app.deps import get_current_user
from server import app


def _override(user: dict):
    async def _get():
        return {**user}

    return _get


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _token_client(token: str) -> AsyncClient:
    app.dependency_overrides.pop(get_current_user, None)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"})


@pytest_asyncio.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-ec16-{suffix}"
    other_tenant_id = f"t-ec16-other-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    staff = {"id": f"staff-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "role": "staff", "is_active": True}
    platform_admin = {
        "id": f"platform-{suffix}",
        "tenant_id": tenant_id,
        "email": f"platform-{suffix}@example.com",
        "role": "owner",
        "is_active": True,
        "platform_admin": True,
        "platform_role": "admin",
    }
    other_owner = {"id": f"other-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "EC16 Tenant"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Other EC16 Tenant"},
    ])
    await db.users.insert_many([owner, staff, platform_admin, other_owner])
    yield {"suffix": suffix, "tenant_id": tenant_id, "other_tenant_id": other_tenant_id, "owner": owner, "staff": staff, "platform_admin": platform_admin, "other_owner": other_owner}
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_platform_contracts_prompt_immutability_and_portal_rejection(ctx):
    async with await _client_as(ctx["staff"]) as staff:
        denied = await staff.post("/api/ai/platform/providers", json={"provider_key": f"ec16staff{ctx['suffix']}", "display_name": "Denied"})
        assert denied.status_code == 403

    async with await _client_as(ctx["platform_admin"]) as platform:
        provider = await platform.post(
            "/api/ai/platform/providers",
            json={"provider_key": f"ec16provider{ctx['suffix']}", "display_name": "EC16 Provider", "status": "active"},
        )
        assert provider.status_code == 201, provider.text
        model = await platform.post(
            "/api/ai/platform/models",
            json={
                "provider_config_id": provider.json()["id"],
                "model_key": f"ec16model{ctx['suffix']}",
                "display_name": "EC16 Model",
                "task_category": "pricing",
                "status": "active",
                "estimated_input_cost_micros_per_unit": 2,
                "estimated_output_cost_micros_per_unit": 4,
            },
        )
        assert model.status_code == 201, model.text
        capability = await platform.post(
            "/api/ai/platform/capabilities",
            json={
                "capability_key": f"ec16.capability.{ctx['suffix']}",
                "display_name": "EC16 Capability",
                "feature_key": "pricing",
                "action_key": "analysis",
                "entitlement_feature_key": f"ai.ec16.{ctx['suffix']}",
                "status": "active",
                "default_credit_charge": 2,
                "allowed_model_profile_ids": [model.json()["id"]],
            },
        )
        assert capability.status_code == 201, capability.text
        prompt = await platform.post(
            "/api/ai/platform/prompts",
            json={
                "capability_key": capability.json()["capability_key"],
                "prompt_key": f"ec16.prompt.{ctx['suffix']}",
                "version": "1",
                "template": "Summarize the request.",
            },
        )
        assert prompt.status_code == 201, prompt.text
        published = await platform.post(f"/api/ai/platform/prompts/{prompt.json()['id']}/publish")
        assert published.status_code == 200
        locked = await platform.patch(f"/api/ai/platform/prompts/{prompt.json()['id']}", json={"template": "mutate"})
        assert locked.status_code == 409
        assert "immutable" in locked.json()["detail"].lower()

    token = create_portal_token(portal_identity_id=f"portal-{ctx['suffix']}", tenant_id=ctx["tenant_id"], portal_type="customer")
    async with await _token_client(token) as portal:
        staff_route = await portal.get("/api/ai/credits/account")
        assert staff_route.status_code == 401

    async with await _client_as(ctx["other_owner"]) as other:
        isolated = await other.get("/api/ai/credits/ledger")
        assert isolated.status_code == 200
        assert isolated.json()["items"] == []
