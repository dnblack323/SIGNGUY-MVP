"""EC17 - AI Studio catalog, permissions, and inactive capability contracts."""
from __future__ import annotations

import json
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
    tenant_id = f"t-ec17-{suffix}"
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
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "EC17 Tenant"})
    await db.users.insert_many([owner, staff, platform_admin])
    yield {"tenant_id": tenant_id, "owner": owner, "staff": staff, "platform_admin": platform_admin}
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_catalog_uses_approved_identifiers_and_keeps_removed_ec18_meta_inactive(ctx):
    async with await _client_as(ctx["owner"]) as client:
        response = await client.get("/api/ai-studio/catalog")
        assert response.status_code == 200, response.text
    catalog = response.json()
    active_keys = {mode["capability_key"] for tool in catalog["tools"] for mode in tool["modes"]}
    assert {
        "studio.image.sign_mockup",
        "studio.image.banner_concept",
        "studio.image.logo_concepts",
        "studio.image.logo_refresh",
        "studio.image.mockup",
        "studio.image.wrap_mockup",
        "studio.image.custom_concept",
        "studio.image.edit_fill",
        "studio.image.motorsports_graphics",
        "studio.image.photo_cleanup",
        "studio.artwork.vector_guidance",
        "studio.artwork.font_finder",
        "studio.text.marketing_content",
        "studio.text.completed_job_post",
        "studio.text.social_pack",
        "studio.text.content_calendar",
        "studio.text.campaign_plan",
        "studio.text.copy_writer",
        "studio.text.brand_kit",
        "studio.text.idea_brainstorm",
        "studio.text.review_reply",
        "studio.text.email_draft",
        "studio.text.document_draft",
        "studio.text.proposal_draft",
        "studio.research.permit_guidance",
        "pricing.advisory",
        "pricing.insights",
        "pricing.historical_invoice_analysis",
        "wrap_lab.cost_guidance",
        "pricing.setup_suggestions",
        "webstore.product_description",
    }.issubset(active_keys)

    inactive = catalog["inactive_capability_identifiers"]
    for key in inactive["removed"] + inactive["ec18_only"] + inactive["meta_only"]:
        assert key not in active_keys
    assert "assistant.chat" in inactive["ec18_only"]
    assert "integration.facebook.message_classify" in inactive["meta_only"]
    assert "order.service_prefill" in inactive["removed"]

    assert catalog["credit_display"] == "AI credits apply"
    assert set(catalog["usage_bands"]) == {"light", "standard", "heavy", "premium"}
    rendered = json.dumps(catalog)
    assert "default_credit_charge" not in rendered
    assert "credit_charge_credits" not in rendered


@pytest.mark.asyncio
async def test_platform_bootstrap_only_and_portal_rejection(ctx):
    async with await _client_as(ctx["staff"]) as staff:
        denied = await staff.post("/api/ai-studio/platform/bootstrap")
        assert denied.status_code == 403
        catalog_denied = await staff.get("/api/ai-studio/catalog")
        assert catalog_denied.status_code == 403

    async with await _client_as(ctx["platform_admin"]) as platform:
        boot = await platform.post("/api/ai-studio/platform/bootstrap")
        assert boot.status_code == 201, boot.text
        assert "studio.image.custom_concept" in boot.json()["capability_keys"]
        assert "assistant.chat" not in boot.json()["capability_keys"]
        assert boot.json()["external_provider_calls"] == 0

    token = create_portal_token(portal_identity_id="portal-ec17", tenant_id=ctx["tenant_id"], portal_type="customer")
    async with await _token_client(token) as portal:
        response = await portal.get("/api/ai-studio/catalog")
        assert response.status_code == 401
