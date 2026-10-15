"""EC17 - prompt library, document/email inventories, permit and import boundaries."""
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
    tenant_id = f"t-ec17-prompts-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "EC17 Prompt Tenant"})
    await db.users.insert_one(owner)
    yield {"tenant_id": tenant_id, "owner": owner}
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_prompt_publish_is_immutable_and_activity_hides_internal_fields(ctx):
    async with await _client_as(ctx["owner"]) as client:
        created = await client.post(
            "/api/ai-studio/prompts",
            json={"tool_key": "content_writer", "mode_key": "business_copy", "name": "Shop copy", "template": "Write {{topic}}."},
        )
        assert created.status_code == 201, created.text
        published = await client.post(f"/api/ai-studio/prompts/{created.json()['id']}/publish")
        assert published.status_code == 200
        locked = await client.patch(f"/api/ai-studio/prompts/{created.json()['id']}", json={"template": "Mutate {{topic}}."})
        assert locked.status_code == 409
        assert "immutable" in locked.json()["detail"].lower()

        activity = await client.get("/api/ai-studio/activity")
        assert activity.status_code == 200, activity.text
        assert "hidden_prompt" in activity.json()["hidden_internal_fields"]


@pytest.mark.asyncio
async def test_catalog_contains_complete_email_document_and_permit_boundaries(ctx):
    async with await _client_as(ctx["owner"]) as client:
        catalog = (await client.get("/api/ai-studio/catalog")).json()
    tools = {tool["tool_key"]: tool for tool in catalog["tools"]}
    email_modes = {mode["mode_key"] for mode in tools["email_draft_assistant"]["modes"]}
    assert {
        "quote_follow_up",
        "payment_reminder",
        "thank_you_email",
        "overdue_invoice_email",
        "job_update",
        "job_complete_email",
        "proof_approval_request",
        "custom_email",
    }.issubset(email_modes)
    document_modes = {mode["mode_key"] for mode in tools["document_writer"]["modes"]}
    assert {
        "general_business_document",
        "proposal",
        "scope_of_work",
        "standard_operating_procedure",
        "job_description",
        "policy_or_instructions",
        "customer_letter",
        "customer_order_document",
        "contract_draft",
    }.issubset(document_modes)
    contract_mode = next(mode for mode in tools["document_writer"]["modes"] if mode["mode_key"] == "contract_draft")
    assert "Legal review required" in " ".join(contract_mode["warnings"])
    permit_fields = {field["name"] for field in tools["permit_guidance"]["modes"][0]["fields"]}
    assert {"jurisdiction", "state", "city", "project_address", "sign_type", "sign_dimensions", "illumination", "mounting_method"}.issubset(permit_fields)
    assert "proper local authority" in " ".join(tools["permit_guidance"]["modes"][0]["warnings"])


@pytest.mark.asyncio
async def test_historical_import_analysis_preserves_safe_boundary(ctx):
    async with await _client_as(ctx["owner"]) as client:
        response = await client.post(
            "/api/ai-studio/pricing/historical-import-analyses",
            json={"source_file_name": "history.xlsx", "source_file_type": "xlsx", "source_file_size_bytes": 4096},
        )
        assert response.status_code == 201, response.text
        analysis = response.json()
        assert analysis["source_file_type"] == "xlsx"
        assert analysis["approval_boundary"] == "application_deferred_to_canonical_pricing_checkpoint"
        assert analysis["extracted_values"]
        assert "No OCR" in " ".join(analysis["warnings"])
        assert await db.pricing_advisory_requests.count_documents({"tenant_id": ctx["tenant_id"]}) == 0
