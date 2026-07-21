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
        assert await db.onboarding_program_definitions.count_documents({"program_key": "shop_launch_v1", "version": 1}) == 1

    async with await _client_as(ctx["owner"]) as owner:
        dashboard = await owner.get("/api/onboarding/dashboard")
        assert dashboard.status_code == 200, dashboard.text
        assert dashboard.json()["progress"]["required_tasks"] >= 3
        company = await owner.post("/api/onboarding/company-profile/apply", json={"company_profile": {"shop_name": "EC19 Signs", "email": "shop@example.com"}})
        assert company.status_code == 200, company.text
        assert (await db.settings.find_one({"tenant_id": ctx["tenant_id"], "namespace": "company_profile", "key": "shop_name"}, {"_id": 0}))["value"] == "EC19 Signs"

    async with await _client_as(ctx["staff"]) as staff:
        read = await staff.get("/api/onboarding/dashboard")
        write = await staff.post("/api/onboarding/tasks/company_profile/status", json={"status": "completed"})
        assert read.status_code == 200
        assert write.status_code == 403

    async with await _portal_client(ctx["portal_token"]) as portal:
        denied = await portal.get("/api/onboarding/dashboard")
        assert denied.status_code in {401, 403}


@pytest.mark.asyncio
async def test_pricing_import_placeholders_template_and_setup_handoff_boundaries(ctx):
    async with await _client_as(ctx["owner"]) as owner:
        scenario = await owner.post("/api/onboarding/pricing/scenario", json={
            "category": "banners",
            "job_duration_hours": 2,
            "crew_size": 1,
            "material_cost_estimate": 50,
            "customer_charge": 250,
            "price_floor": 125,
            "includes_design": True,
        })
        assert scenario.status_code == 201, scenario.text
        suggestions = scenario.json()["derived_suggestions"]["suggested_shop_defaults_map"]
        applied = await owner.post(f"/api/onboarding/pricing/scenario/{scenario.json()['id']}/apply", json={"accepted_shop_defaults": suggestions})
        assert applied.status_code == 200, applied.text
        assert applied.json()["status"] == "applied"

        before_invoices = await db.invoices.count_documents({"tenant_id": ctx["tenant_id"]})
        before_payments = await db.payments.count_documents({"tenant_id": ctx["tenant_id"]})
        historical = await owner.post("/api/onboarding/historical-invoices", json={"file_name": "old-invoices.csv", "file_type": "csv", "file_size_bytes": 1200, "request_analysis": True})
        assert historical.status_code == 201, historical.text
        assert historical.json()["analysis_status"] == "unavailable"
        assert "provider" in historical.json()["analysis_boundary"]
        assert await db.invoices.count_documents({"tenant_id": ctx["tenant_id"]}) == before_invoices
        assert await db.payments.count_documents({"tenant_id": ctx["tenant_id"]}) == before_payments

        registry = await owner.get("/api/onboarding/placeholders")
        preview = await owner.post("/api/onboarding/placeholders/preview", json={"content": "Hi {{customer_name}} {{order_number}}", "context": {"customer_name": "Acme"}})
        unknown = await owner.post("/api/onboarding/placeholders/preview", json={"content": "Hi {{not_allowed}}", "context": {}})
        assert registry.status_code == 200
        assert any(p["key"] == "customer_name" for p in registry.json()["placeholders"])
        assert preview.status_code == 200
        assert preview.json()["missing_placeholders"] == ["order_number"]
        assert unknown.status_code == 400

        template = await owner.post("/api/onboarding/template-exercises", json={
            "name": "Install reminder",
            "template_type": "email",
            "body": {"channels": {"email_body": "Hi {{customer_name}}, install is on {{appointment_date}}."}},
            "context": {"customer_name": "Acme", "appointment_date": "2026-08-01"},
            "save_as_template": True,
        })
        assert template.status_code == 201, template.text
        assert template.json()["status"] == "saved"
        assert template.json()["template_id"]
        assert await db.ai_usage_events.count_documents({"tenant_id": ctx["tenant_id"]}) == 0

        setup_before = await db.checkout_session_records.count_documents({"tenant_id": ctx["tenant_id"]})
        account = {
            "id": f"acct-{ctx['suffix']}",
            "tenant_id": ctx["tenant_id"],
            "status": "pending",
            "created_at": _now(),
            "updated_at": _now(),
        }
        await db.tenant_billing_accounts.insert_one(account)
        purchase = {
            "id": f"setup-{ctx['suffix']}",
            "tenant_id": ctx["tenant_id"],
            "billing_account_id": account["id"],
            "package_key": "standard",
            "status": "paid",
            "amount_cents": 49900,
            "currency": "usd",
            "ec19_handoff_status": "not_started",
            "created_at": _now(),
            "updated_at": _now(),
        }
        await db.setup_package_purchases.insert_one(purchase)
        handoff = await owner.post("/api/onboarding/setup-package-handoff", json={"purchase_id": purchase["id"], "status": "ready_for_intake", "notes": "ready"})
        assert handoff.status_code == 200, handoff.text
        assert handoff.json()["handoff_status"] == "ready_for_intake"
        assert await db.checkout_session_records.count_documents({"tenant_id": ctx["tenant_id"]}) == setup_before

    async with await _client_as(ctx["other_owner"]) as other:
        other_dashboard = await other.get("/api/onboarding/dashboard")
        assert other_dashboard.status_code == 200
        assert other_dashboard.json()["instance"]["tenant_id"] == ctx["other_tenant_id"]
        assert not await db.onboarding_step_responses.count_documents({"tenant_id": ctx["other_tenant_id"], "payload.import_record_id": historical.json()["id"]})


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
