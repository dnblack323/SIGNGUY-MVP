"""CIR-020 - Webstore product AI actions use EC16/EC17 authority safely."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db, ensure_indexes
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
async def cir020_ctx():
    await ensure_indexes()
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-cir020-{suffix}"
    webstore_id = f"ws-cir020-{suffix}"
    product_id = f"prod-cir020-{suffix}"
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
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "CIR020 Tenant"})
    await db.users.insert_many([owner, platform_admin])
    await db.webstores.insert_one(
        {
            "id": webstore_id,
            "tenant_id": tenant_id,
            "slug": webstore_id,
            "name": "CIR020 Store",
            "status": "draft",
            "store_type": "general",
            "entitlement_feature_key": "webstores",
        }
    )
    await db.webstore_products.insert_one(
        {
            "id": product_id,
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "name": "Fundraiser Shirt",
            "product_type": "shirt",
            "category_name": "Apparel",
            "short_description": "A staff-written shirt description.",
            "full_description": "Original staff product copy must stay untouched.",
            "revision": 3,
            "status": "draft",
        }
    )
    await _upsert_entitlement_for_tests(tenant_id=tenant_id, feature_key="webstores", enabled=True)
    await _upsert_entitlement_for_tests(tenant_id=tenant_id, feature_key="ai_studio", enabled=True)
    async with await _client_as(platform_admin) as platform:
        boot = await platform.post("/api/ai-studio/platform/bootstrap")
        assert boot.status_code == 201, boot.text
        grant = await platform.post(
            f"/api/ai/platform/credit-accounts/{tenant_id}/grants",
            json={"included_credits": 8, "reason": "CIR-020 test", "idempotency_key": f"cir020-grant-{suffix}"},
        )
        assert grant.status_code == 201, grant.text
    yield {"tenant_id": tenant_id, "webstore_id": webstore_id, "product_id": product_id, "owner": owner}
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_webstore_product_description_ai_requires_preview_confirmation_and_saves_review_draft(cir020_ctx):
    async with await _client_as(cir020_ctx["owner"]) as client:
        preview = await client.post(
            f"/api/webstores/{cir020_ctx['webstore_id']}/products/{cir020_ctx['product_id']}/ai-actions/preview",
            json={"action": "product_description"},
        )
        assert preview.status_code == 200, preview.text
        preview_body = preview.json()
        assert preview_body["credit_charge_credits"] == 1
        assert preview_body["confirmation_required"] is True
        assert preview_body["auto_apply"] is False
        assert preview_body["manual_setup_available"] is True

        missing_confirmation = await client.post(
            f"/api/webstores/{cir020_ctx['webstore_id']}/products/{cir020_ctx['product_id']}/ai-actions",
            json={"action": "product_description", "prompt": "Make this ready for a booster club."},
        )
        assert missing_confirmation.status_code == 422

        stale_confirmation = await client.post(
            f"/api/webstores/{cir020_ctx['webstore_id']}/products/{cir020_ctx['product_id']}/ai-actions",
            json={"action": "product_description", "confirmed_credit_charge_credits": 0},
        )
        assert stale_confirmation.status_code == 409

        run = await client.post(
            f"/api/webstores/{cir020_ctx['webstore_id']}/products/{cir020_ctx['product_id']}/ai-actions",
            json={
                "action": "product_description",
                "confirmed_credit_charge_credits": preview_body["credit_charge_credits"],
                "prompt": "Make this ready for a booster club.",
                "idempotency_key": f"cir020-desc-{uuid.uuid4()}",
            },
        )
        assert run.status_code == 201, run.text
        body = run.json()
        assert body["auto_apply"] is False
        assert body["review_required"] is True
        assert body["ai_result"]["record_type"] == "editable_draft"
        assert body["ai_result"]["draft_type"] == "product_content_draft"
        assert body["webstore_ai_event"]["output_snapshot"]["record_id"] == body["ai_result"]["id"]

    product = await db.webstore_products.find_one({"tenant_id": cir020_ctx["tenant_id"], "id": cir020_ctx["product_id"]}, {"_id": 0})
    assert product["short_description"] == "A staff-written shirt description."
    assert product["full_description"] == "Original staff product copy must stay untouched."
    assert product["revision"] == 3
    assert await db.webstore_mockups.count_documents({"tenant_id": cir020_ctx["tenant_id"], "webstore_id": cir020_ctx["webstore_id"]}) == 0
    assert await db.ai_action_requests.count_documents({"tenant_id": cir020_ctx["tenant_id"], "capability_key": "webstore.product_description"}) == 1
    assert await db.ai_credit_ledger_entries.count_documents({"tenant_id": cir020_ctx["tenant_id"], "entry_type": "commit"}) == 1
    assert await db.webstore_ai_usage_events.count_documents({"tenant_id": cir020_ctx["tenant_id"], "webstore_id": cir020_ctx["webstore_id"], "action": "product_description"}) == 1


@pytest.mark.asyncio
async def test_webstore_product_mockup_ai_saves_asset_without_creating_mockup(cir020_ctx):
    async with await _client_as(cir020_ctx["owner"]) as client:
        preview = await client.post(
            f"/api/webstores/{cir020_ctx['webstore_id']}/products/{cir020_ctx['product_id']}/ai-actions/preview",
            json={"action": "product_mockup"},
        )
        assert preview.status_code == 200, preview.text
        run = await client.post(
            f"/api/webstores/{cir020_ctx['webstore_id']}/products/{cir020_ctx['product_id']}/ai-actions",
            json={
                "action": "product_mockup",
                "confirmed_credit_charge_credits": preview.json()["credit_charge_credits"],
                "prompt": "Concept only for a navy shirt.",
                "idempotency_key": f"cir020-mockup-{uuid.uuid4()}",
            },
        )
        assert run.status_code == 201, run.text
        body = run.json()
        assert body["ai_result"]["record_type"] == "generated_asset"
        assert body["ai_result"]["asset_type"] == "image_concept"
        assert body["ai_result"]["content_json"]["production_ready"] is False
        assert body["webstore_ai_event"]["output_snapshot"]["auto_apply"] is False

    assert await db.webstore_mockups.count_documents({"tenant_id": cir020_ctx["tenant_id"], "webstore_id": cir020_ctx["webstore_id"]}) == 0
    assert await db.ai_generated_assets.count_documents({"tenant_id": cir020_ctx["tenant_id"], "parent_record_type": "webstore", "parent_record_id": cir020_ctx["webstore_id"]}) == 1
