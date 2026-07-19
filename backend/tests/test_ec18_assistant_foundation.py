"""EC18A - Business Assistant foundation, entitlement, and action safety."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.portal_security import create_portal_token
from app.deps import get_current_user
from app.services import ai_gateway
from app.services.entitlements import _upsert_entitlement_for_tests
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
    tenant_id = f"t-ec18-{suffix}"
    other_tenant_id = f"t-ec18-other-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    staff = {"id": f"staff-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "role": "staff", "is_active": True}
    other_owner = {"id": f"owner-other-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True}
    platform_admin = {
        "id": f"platform-{suffix}",
        "tenant_id": tenant_id,
        "email": f"platform-{suffix}@example.com",
        "role": "owner",
        "is_active": True,
        "platform_admin": True,
        "platform_role": "admin",
    }
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "EC18 Tenant"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Other EC18 Tenant"},
    ])
    await db.users.insert_many([owner, staff, other_owner, platform_admin])
    await _upsert_entitlement_for_tests(tenant_id=tenant_id, feature_key="business_assistant", enabled=True)
    await _upsert_entitlement_for_tests(tenant_id=other_tenant_id, feature_key="business_assistant", enabled=True)
    await db.customers.insert_one({"id": f"cust-{suffix}", "tenant_id": tenant_id, "name": "Acme Signs", "updated_at": "2026-07-19T10:00:00+00:00"})
    await db.customers.insert_one({"id": f"cust-other-{suffix}", "tenant_id": other_tenant_id, "name": "Other Customer", "updated_at": "2026-07-19T10:00:00+00:00"})
    await db.invoices.insert_one({
        "id": f"inv-{suffix}", "tenant_id": tenant_id, "number": 1201, "document_status": "issued",
        "financial_status": "unpaid", "total_cents": 42500, "balance_due_cents": 42500,
        "created_at": "2026-07-19T12:00:00+00:00", "updated_at": "2026-07-19T12:00:00+00:00",
    })
    async with await _client_as(platform_admin) as platform:
        boot = await platform.post("/api/assistant/platform/bootstrap")
        assert boot.status_code == 201, boot.text
    await ai_gateway.grant_credits(platform_admin, tenant_id, {"included_credits": 50, "reason": "EC18 test"})
    await ai_gateway.grant_credits(platform_admin, other_tenant_id, {"included_credits": 50, "reason": "EC18 test"})
    yield {
        "suffix": suffix,
        "tenant_id": tenant_id,
        "other_tenant_id": other_tenant_id,
        "owner": owner,
        "staff": staff,
        "other_owner": other_owner,
        "platform_admin": platform_admin,
        "customer_id": f"cust-{suffix}",
        "other_customer_id": f"cust-other-{suffix}",
    }
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_catalog_bootstrap_uses_assistant_capabilities_and_keeps_deferred_inactive(ctx):
    async with await _client_as(ctx["owner"]) as client:
        catalog = await client.get("/api/assistant/catalog")
        assert catalog.status_code == 200, catalog.text
    body = catalog.json()
    assert body["entitlement_feature_key"] == "business_assistant"
    assert "assistant.chat" in body["capability_keys"]
    assert "assistant.voice_reply" in body["capability_keys"]
    assert "integration.facebook.message_classify" in body["deferred_capability_keys"]

    async with await _client_as(ctx["platform_admin"]) as platform:
        boot = await platform.post("/api/assistant/platform/bootstrap")
        assert boot.status_code == 201
    boot_body = boot.json()
    assert set(body["capability_keys"]).issubset(set(boot_body["capability_keys"]))
    assert "order.service_prefill" not in boot_body["capability_keys"]
    assert boot_body["external_provider_calls"] == 0


@pytest.mark.asyncio
async def test_entitlement_permission_portal_and_tenant_isolation(ctx):
    no_ent_tenant = f"no-ent-{ctx['suffix']}"
    no_ent_user = {"id": f"no-ent-user-{ctx['suffix']}", "tenant_id": no_ent_tenant, "email": "no-ent@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_one({"id": no_ent_tenant, "slug": no_ent_tenant, "name": "No Entitlement"})
    await db.users.insert_one(no_ent_user)

    async with await _client_as(no_ent_user) as client:
        denied = await client.get("/api/assistant/catalog")
        assert denied.status_code == 402

    async with await _client_as(ctx["staff"]) as staff:
        perm_denied = await staff.get("/api/assistant/catalog")
        assert perm_denied.status_code == 403

    token = create_portal_token(portal_identity_id="portal-ec18", tenant_id=ctx["tenant_id"], portal_type="customer")
    async with await _token_client(token) as portal:
        portal_denied = await portal.get("/api/assistant/catalog")
        assert portal_denied.status_code == 401

    async with await _client_as(ctx["owner"]) as owner:
        cross = await owner.post(
            "/api/assistant/messages",
            json={"message": "summarize this customer", "context": {"source_entity_type": "customer", "source_entity_id": ctx["other_customer_id"]}},
        )
        assert cross.status_code == 404


@pytest.mark.asyncio
async def test_source_linked_bi_answer_and_no_invoice_payment_mutation(ctx):
    before = {
        "invoices": await db.invoices.count_documents({"tenant_id": ctx["tenant_id"]}),
        "payments": await db.payments.count_documents({"tenant_id": ctx["tenant_id"]}),
    }
    async with await _client_as(ctx["owner"]) as client:
        response = await client.post("/api/assistant/messages", json={"message": "What is the latest invoice?", "mode": "finance", "idempotency_key": f"ask-{ctx['suffix']}"})
        assert response.status_code == 201, response.text
    body = response.json()
    assert "Latest invoice" in body["answer"]
    assert body["sources"][0]["source_type"] == "invoice"
    assert body["sources"][0]["route"].startswith("/invoices/")
    assert body["credit_display"] == "AI credits apply"
    assert await db.invoices.count_documents({"tenant_id": ctx["tenant_id"]}) == before["invoices"]
    assert await db.payments.count_documents({"tenant_id": ctx["tenant_id"]}) == before["payments"]
    action = await db.ai_action_requests.find_one({"tenant_id": ctx["tenant_id"], "id": body["action_request"]["id"]}, {"_id": 0})
    assert action["capability_key"] == "assistant.chat"


@pytest.mark.asyncio
async def test_action_proposal_requires_confirm_and_creates_draft_only(ctx):
    async with await _client_as(ctx["owner"]) as client:
        proposed = await client.post(
            "/api/assistant/actions/proposals",
            json={
                "action_type": "email_draft",
                "title": "Follow up",
                "subject": "Checking in",
                "body": "Thanks for considering this quote.",
                "target_refs": [{"type": "customer", "id": ctx["customer_id"], "source_updated_at": "2026-07-19T10:00:00+00:00"}],
                "idempotency_key": f"proposal-{ctx['suffix']}",
                "metering_idempotency_key": f"proposal-meter-{ctx['suffix']}",
            },
        )
        assert proposed.status_code == 201, proposed.text
        proposal_id = proposed.json()["id"]

        blocked = await client.post(f"/api/assistant/actions/proposals/{proposal_id}/execute", headers={"Idempotency-Key": f"exec-{ctx['suffix']}"})
        assert blocked.status_code == 409

        confirmed = await client.post(f"/api/assistant/actions/proposals/{proposal_id}/confirm")
        assert confirmed.status_code == 200, confirmed.text
        executed = await client.post(f"/api/assistant/actions/proposals/{proposal_id}/execute", headers={"Idempotency-Key": f"exec-{ctx['suffix']}"})
        assert executed.status_code == 200, executed.text

    result = executed.json()["canonical_result"]
    assert result["sent"] is False
    assert result["canonical_service"] == "ai_studio_editable_drafts"
    assert await db.email_logs.count_documents({"tenant_id": ctx["tenant_id"]}) == 0
    assert await db.ai_studio_editable_drafts.count_documents({"tenant_id": ctx["tenant_id"], "capability_key": "assistant.email_draft"}) == 1


@pytest.mark.asyncio
async def test_voice_unconfigured_returns_safe_unavailable_without_fake_session(ctx):
    async with await _client_as(ctx["owner"]) as client:
        config = await client.get("/api/assistant/voice/config")
        assert config.status_code == 200
        response = await client.post("/api/assistant/voice/sessions", json={})
        assert response.status_code == 201, response.text
    body = response.json()
    assert body["configured"] is False
    assert body["status"] == "unavailable"
    assert "OpenAI Voice is not configured" in body["message"]
    assert "api_key" not in str(body).lower()
