"""EC18C - Business Assistant intelligence, routines, memory, and delegation."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
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


@pytest_asyncio.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-ec18c-{suffix}"
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
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "EC18C Tenant"})
    await db.users.insert_many([owner, platform_admin])
    await _upsert_entitlement_for_tests(tenant_id=tenant_id, feature_key="business_assistant", enabled=True)
    await _upsert_entitlement_for_tests(tenant_id=tenant_id, feature_key="ai_studio", enabled=True)
    async with await _client_as(platform_admin) as platform:
        boot = await platform.post("/api/assistant/platform/bootstrap")
        assert boot.status_code == 201, boot.text
    await ai_gateway.grant_credits(platform_admin, tenant_id, {"included_credits": 100, "reason": "EC18C test"})
    await db.customers.insert_one({"id": f"cust-{suffix}", "tenant_id": tenant_id, "name": "Acme Signs", "updated_at": "2026-07-19T10:00:00+00:00"})
    await db.wrap_projects.insert_one({"id": f"wrap-{suffix}", "tenant_id": tenant_id, "customer_id": f"cust-{suffix}", "status": "completed", "updated_at": "2026-07-19T11:00:00+00:00"})
    await db.quotes.insert_one({"id": f"quote-{suffix}", "tenant_id": tenant_id, "number": 55, "status": "sent", "updated_at": "2026-07-19T10:00:00+00:00"})
    await db.invoices.insert_one({
        "id": f"inv-{suffix}", "tenant_id": tenant_id, "number": 2201, "document_status": "issued",
        "financial_status": "unpaid", "total_cents": 12500, "balance_due_cents": 12500,
        "created_at": "2026-07-19T12:00:00+00:00", "updated_at": "2026-07-19T12:00:00+00:00",
    })
    yield {"suffix": suffix, "tenant_id": tenant_id, "owner": owner, "customer_id": f"cust-{suffix}", "wrap_id": f"wrap-{suffix}"}
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_memory_controls_reject_secrets_and_allow_delete(ctx):
    async with await _client_as(ctx["owner"]) as client:
        secret = await client.post("/api/assistant/memory", json={"memory_key": "bad", "content_text": "api key is secret"})
        assert secret.status_code == 400
        saved = await client.post("/api/assistant/memory", json={"memory_key": "tone", "content_text": "Prefer concise customer updates."})
        assert saved.status_code == 201, saved.text
        listed = await client.get("/api/assistant/memory")
        assert listed.status_code == 200
        assert listed.json()["total"] == 1
        deleted = await client.delete(f"/api/assistant/memory/{saved.json()['id']}")
        assert deleted.status_code == 200
        listed_again = await client.get("/api/assistant/memory")
        assert listed_again.json()["total"] == 0


@pytest.mark.asyncio
async def test_routines_quick_actions_insights_and_studio_delegation_are_non_mutating(ctx):
    before_assets = await db.ai_generated_assets.count_documents({"tenant_id": ctx["tenant_id"]})
    async with await _client_as(ctx["owner"]) as client:
        routine = await client.post("/api/assistant/routines", json={"name": "Morning check", "prompt": "Show open invoices", "mode": "finance"})
        assert routine.status_code == 201, routine.text
        assert routine.json()["generated_proposal_only"] is True
        routines = await client.get("/api/assistant/routines")
        assert routines.json()["total"] == 1

        quick = await client.get("/api/assistant/quick-actions", params={"mode": "owner"})
        assert quick.status_code == 200
        assert any(item["label"] == "Latest invoice" for item in quick.json()["items"])

        insights = await client.get("/api/assistant/insights", params={"generate": "true"})
        assert insights.status_code == 200
        assert insights.json()["total"] >= 1
        assert insights.json()["items"][0]["source_citations"][0]["source_type"] == "invoice"

        delegation = await client.post(
            "/api/assistant/delegations/studio",
            json={"tool_key": "social_post_builder", "mode_key": "completed_work_showcase", "context": {"source_entity_type": "wrap_project", "source_entity_id": ctx["wrap_id"]}},
        )
        assert delegation.status_code == 201, delegation.text
        assert delegation.json()["route"].startswith("/studio?tool=social_post_builder")
        assert delegation.json()["created_record"] is False

    assert await db.ai_generated_assets.count_documents({"tenant_id": ctx["tenant_id"]}) == before_assets


@pytest.mark.asyncio
async def test_quote_followup_bi_and_bulk_email_draft_do_not_send(ctx):
    async with await _client_as(ctx["owner"]) as client:
        answer = await client.post("/api/assistant/messages", json={"message": "Which quotes need follow-up?", "idempotency_key": f"quote-follow-{ctx['suffix']}"})
        assert answer.status_code == 201, answer.text
        assert "open quote" in answer.json()["answer"]
        assert answer.json()["sources"][0]["source_type"] == "quote"

        proposed = await client.post(
            "/api/assistant/actions/proposals",
            json={
                "action_type": "bulk_email_draft",
                "title": "Follow up on quotes",
                "preview": {"summary": "Reviewable bulk quote follow-up drafts", "count": 1},
                "editable_payload": {"subject": "Following up", "body": "Checking in on your quote."},
                "target_refs": [{"type": "customer", "id": ctx["customer_id"], "source_updated_at": "2026-07-19T10:00:00+00:00"}],
                "idempotency_key": f"bulk-{ctx['suffix']}",
                "metering_idempotency_key": f"bulk-meter-{ctx['suffix']}",
            },
        )
        assert proposed.status_code == 201, proposed.text
        confirmed = await client.post(f"/api/assistant/actions/proposals/{proposed.json()['id']}/confirm")
        assert confirmed.status_code == 200, confirmed.text
        executed = await client.post(f"/api/assistant/actions/proposals/{proposed.json()['id']}/execute", headers={"Idempotency-Key": f"bulk-exec-{ctx['suffix']}"})
        assert executed.status_code == 200, executed.text

    assert executed.json()["canonical_result"]["sent"] is False
    assert executed.json()["canonical_result"]["results"][0]["status"] == "draft_created"
    assert await db.email_logs.count_documents({"tenant_id": ctx["tenant_id"]}) == 0
