"""EC19 onboarding, Help Center, contextual help, and documentation contracts."""
from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.portal_security import create_portal_token
from app.deps import get_current_user
from server import app


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _override(user: dict):
    async def _get():
        return {**user}

    return _get


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _portal_client(token: str) -> AsyncClient:
    app.dependency_overrides.pop(get_current_user, None)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"})


@pytest_asyncio.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-ec19-{suffix}"
    other_tenant_id = f"t-ec19-other-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    staff = {"id": f"staff-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "role": "staff", "is_active": True}
    other_owner = {"id": f"other-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True}
    platform_admin = {
        "id": f"platform-{suffix}",
        "tenant_id": tenant_id,
        "email": f"platform-{suffix}@example.com",
        "role": "staff",
        "is_active": True,
        "platform_admin": True,
        "platform_role": "admin",
    }
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "EC19 Tenant"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Other EC19 Tenant"},
    ])
    await db.users.insert_many([owner, staff, other_owner, platform_admin])
    portal_identity = {
        "id": f"portal-{suffix}",
        "tenant_id": tenant_id,
        "portal_type": "customer",
        "customer_id": f"customer-{suffix}",
        "email": f"portal-{suffix}@example.com",
        "status": "active",
    }
    await db.portal_identities.insert_one(portal_identity)
    token = create_portal_token(
        portal_identity_id=portal_identity["id"],
        tenant_id=tenant_id,
        portal_type="customer",
        customer_id=portal_identity["customer_id"],
    )
    yield {
        "suffix": suffix,
        "tenant_id": tenant_id,
        "other_tenant_id": other_tenant_id,
        "owner": owner,
        "staff": staff,
        "other_owner": other_owner,
        "platform_admin": platform_admin,
        "portal_token": token,
    }
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_platform_bootstrap_dashboard_permissions_and_portal_boundary(ctx):
    async with await _client_as(ctx["owner"]) as owner:
        denied = await owner.post("/api/onboarding/platform/bootstrap")
        assert denied.status_code == 403

    async with await _client_as(ctx["platform_admin"]) as platform:
        first = await platform.post("/api/onboarding/platform/bootstrap")
        second = await platform.post("/api/onboarding/platform/bootstrap")
        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        assert await db.onboarding_program_definitions.count_documents({"program_key": "shop_launch_v1", "version": 2}) == 1

    async with await _client_as(ctx["staff"]) as staff:
        read = await staff.get("/api/onboarding/dashboard")
        write = await staff.post("/api/onboarding/tasks/time_clock/status", json={"status": "completed"})
        position = await staff.post("/api/onboarding/position", json={"task_key": "company_profile"})
        assert read.status_code == 200
        assert write.status_code == 403
        assert position.status_code == 403

    async with await _portal_client(ctx["portal_token"]) as portal:
        denied = await portal.get("/api/onboarding/dashboard")
        assert denied.status_code in {401, 403}


@pytest.mark.asyncio
async def test_setup_package_handoff_boundary(ctx):
    async with await _client_as(ctx["owner"]) as owner:
        assert (await owner.get("/api/onboarding/setup-package-handoff")).json()["available"] is False
        setup_before = await db.checkout_session_records.count_documents({"tenant_id": ctx["tenant_id"]})
        account = {"id": f"acct-{ctx['suffix']}", "tenant_id": ctx["tenant_id"], "status": "pending", "created_at": _now(), "updated_at": _now()}
        await db.tenant_billing_accounts.insert_one(account)
        purchase = {
            "id": f"setup-{ctx['suffix']}", "tenant_id": ctx["tenant_id"], "billing_account_id": account["id"], "package_key": "standard",
            "status": "paid", "amount_cents": 49900, "currency": "usd", "ec19_handoff_status": "not_started", "created_at": _now(), "updated_at": _now(),
        }
        await db.setup_package_purchases.insert_one(purchase)
        handoff = await owner.post("/api/onboarding/setup-package-handoff", json={"purchase_id": purchase["id"], "status": "ready_for_intake", "notes": "ready"})
        assert handoff.status_code == 200, handoff.text
        assert handoff.json()["handoff_status"] == "ready_for_intake"
        assert await db.checkout_session_records.count_documents({"tenant_id": ctx["tenant_id"]}) == setup_before


@pytest.mark.asyncio
async def test_help_center_lifecycle_contextual_feedback_support_and_billing_guidance(ctx):
    async with await _client_as(ctx["platform_admin"]) as platform:
        await platform.post("/api/onboarding/platform/bootstrap")
        draft = await platform.post("/api/help/platform/articles", json={
            "slug": f"ec19-draft-{ctx['suffix']}",
            "title": "Draft EC19",
            "category": "module_guides",
            "module": "onboarding",
            "body": "Draft body",
            "status": "draft",
        })
        assert draft.status_code == 201, draft.text

    async with await _client_as(ctx["owner"]) as owner:
        hidden = await owner.get(f"/api/help/articles/ec19-draft-{ctx['suffix']}")
        assert hidden.status_code == 404

    async with await _client_as(ctx["platform_admin"]) as platform:
        published = await platform.post(f"/api/help/platform/articles/ec19-draft-{ctx['suffix']}/status", json={"status": "published"})
        assert published.status_code == 200

    async with await _client_as(ctx["owner"]) as owner:
        search = await owner.get("/api/help/articles", params={"q": "pricing"})
        article = await owner.get(f"/api/help/articles/ec19-draft-{ctx['suffix']}")
        contextual = await owner.get("/api/help/contextual/pricing.quiz", params={"module": "pricing"})
        role = await owner.get("/api/help/role-guides/owner")
        feedback = await owner.post("/api/help/feedback", json={"article_slug": "pricing-setup-guide", "helpful": True, "idempotency_key": f"fb-{ctx['suffix']}"})
        feedback_dup = await owner.post("/api/help/feedback", json={"article_slug": "pricing-setup-guide", "helpful": True, "idempotency_key": f"fb-{ctx['suffix']}"})
        support = await owner.post("/api/help/support/escalations", json={"subject": "Need setup help", "message": "Please review setup", "idempotency_key": f"sup-{ctx['suffix']}"})
        assert search.status_code == 200
        assert any(item["slug"] == "pricing-setup-guide" for item in search.json()["items"])
        assert article.status_code == 200
        assert contextual.status_code == 200
        assert contextual.json()["items"][0]["article_slug"] == "pricing-setup-guide"
        assert role.status_code == 200
        assert feedback.status_code == 201
        assert feedback_dup.json()["id"] == feedback.json()["id"]
        assert support.status_code == 201
        assert support.json()["tenant_id"] == ctx["tenant_id"]

        account = {"id": f"bill-{ctx['suffix']}", "tenant_id": ctx["tenant_id"], "status": "past_due", "created_at": _now(), "updated_at": _now()}
        sub = {
            "id": f"sub-{ctx['suffix']}",
            "tenant_id": ctx["tenant_id"],
            "billing_account_id": account["id"],
            "catalog_version_id": "cat",
            "plan_product_id": "prod",
            "price_id": "price",
            "billing_interval": "monthly",
            "status": "past_due",
            "dunning_state": "day_8_14_soft_restriction",
            "created_at": _now(),
            "updated_at": _now(),
        }
        await db.tenant_billing_accounts.insert_one(account)
        await db.tenant_subscriptions.insert_one(sub)
        before = await db.tenant_subscriptions.find_one({"id": sub["id"]}, {"_id": 0})
        guidance = await owner.get("/api/help/billing/failed-subscription")
        after = await db.tenant_subscriptions.find_one({"id": sub["id"]}, {"_id": 0})
        assert guidance.status_code == 200
        assert guidance.json()["mutated_billing"] is False
        assert guidance.json()["dunning_state"] == "day_8_14_soft_restriction"
        assert before == after

    async with await _client_as(ctx["staff"]) as staff:
        denied = await staff.post("/api/help/platform/articles", json={"slug": f"nope-{ctx['suffix']}", "title": "No", "body": "No"})
        assert denied.status_code == 403
