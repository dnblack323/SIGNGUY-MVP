"""EC17 - generated assets, editable drafts, and EC16 execution boundaries."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.deps import get_current_user
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
    tenant_id = f"t-ec17-assets-{suffix}"
    other_tenant_id = f"t-ec17-assets-other-{suffix}"
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
    other_owner = {"id": f"other-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "EC17 Asset Tenant"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Other Tenant"},
    ])
    await db.users.insert_many([owner, platform_admin, other_owner])
    await db.files.insert_one({"id": f"file-{suffix}", "tenant_id": tenant_id, "filename": "source.png"})
    yield {"tenant_id": tenant_id, "other_tenant_id": other_tenant_id, "owner": owner, "platform_admin": platform_admin, "other_owner": other_owner, "file_id": f"file-{suffix}"}
    app.dependency_overrides.pop(get_current_user, None)


async def _prepare(ctx):
    await _upsert_entitlement_for_tests(tenant_id=ctx["tenant_id"], feature_key="ai_studio", enabled=True)
    async with await _client_as(ctx["platform_admin"]) as platform:
        boot = await platform.post("/api/ai-studio/platform/bootstrap")
        assert boot.status_code == 201, boot.text
        grant = await platform.post(
            f"/api/ai/platform/credit-accounts/{ctx['tenant_id']}/grants",
            json={"included_credits": 10, "reason": "EC17 test grant", "idempotency_key": f"ec17-grant-{uuid.uuid4()}"},
        )
        assert grant.status_code == 201, grant.text


@pytest.mark.asyncio
async def test_image_edit_fill_preserves_original_and_links_ec16_records(ctx):
    await _prepare(ctx)
    async with await _client_as(ctx["owner"]) as client:
        response = await client.post(
            "/api/ai-studio/runs",
            json={
                "tool_key": "photo_editor",
                "mode_key": "edit_replace_area",
                "inputs": {
                    "prompt": "Replace the damaged panel background",
                    "source_image_id": ctx["file_id"],
                    "mask_description": "lower left panel",
                    "preserve_area_instructions": "preserve logo and text",
                    "reference_image_id": "ref-1",
                    "output_dimensions": "4:3",
                },
                "source_asset_ids": [ctx["file_id"]],
                "idempotency_key": f"ec17-image-{uuid.uuid4()}",
            },
        )
        assert response.status_code == 201, response.text
        asset = response.json()
        assert asset["record_type"] == "generated_asset"
        assert asset["asset_type"] == "image_concept"
        assert asset["content_json"]["source_image_preserved"] is True
        assert asset["content_json"]["selected_region_or_mask"] == "lower left panel"
        assert asset["content_json"]["external_provider_calls"] == 0
        assert "No claim that a real image edit occurred" in " ".join(asset["warnings"])

        action = await db.ai_action_requests.find_one({"tenant_id": ctx["tenant_id"], "id": asset["action_request_id"]}, {"_id": 0})
        assert action
        assert action["capability_key"] == "studio.image.edit_fill"
        assert action["status"] == "succeeded"
        usage = await db.ai_usage_ledger_entries.find_one({"tenant_id": ctx["tenant_id"], "action_request_id": action["id"]}, {"_id": 0})
        assert usage and usage["credits_charged"] == 1
        cost = await db.ai_provider_cost_ledger_entries.find_one({"tenant_id": ctx["tenant_id"], "action_request_id": action["id"]}, {"_id": 0})
        assert cost and cost["actual_cost_micros"] == 0

    async with await _client_as(ctx["other_owner"]) as other:
        isolated = await other.get(f"/api/ai-studio/generated-assets/{asset['id']}")
        assert isolated.status_code == 404


@pytest.mark.asyncio
async def test_social_output_is_editable_draft_with_publicity_warning_and_alt_text(ctx):
    await _prepare(ctx)
    order_id = f"order-{uuid.uuid4().hex[:8]}"
    await db.orders.insert_one({"id": order_id, "tenant_id": ctx["tenant_id"], "number": "1001", "job_name": "Lobby sign", "customer_id": "cust-1"})
    async with await _client_as(ctx["owner"]) as client:
        response = await client.post(
            "/api/ai-studio/runs",
            json={
                "tool_key": "social_post_builder",
                "mode_key": "completed_work_showcase",
                "inputs": {"prompt": "Lobby sign install", "publicity_permission_state": "unknown"},
                "context": {"context_type": "order", "context_id": order_id, "publicity_permission_state": "unknown"},
                "idempotency_key": f"ec17-social-{uuid.uuid4()}",
            },
        )
        assert response.status_code == 201, response.text
        draft = response.json()
        assert draft["record_type"] == "editable_draft"
        assert draft["draft_type"] == "content_draft"
        assert draft["content_json"]["image_alt_text"]
        assert draft["content_json"]["primary_caption"]
        assert draft["content_json"]["alternate_caption"]
        assert draft["content_json"]["platform_versions"]
        assert "unknown or missing" in " ".join(draft["warnings"])
        assets = await client.get("/api/ai-studio/generated-assets")
        assert assets.status_code == 200
        assert assets.json()["items"] == []
