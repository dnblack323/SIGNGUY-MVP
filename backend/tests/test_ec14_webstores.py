"""EC14 - Webstores contracts."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.portal_security import create_portal_token
from app.deps import get_current_user
from app.models.webstore import WebstoreBrandingPublishedVersion
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
    tenant_id = f"t-ec14-{suffix}"
    other_tenant_id = f"t-ec14-other-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    staff = {"id": f"staff-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "role": "staff", "is_active": True}
    other_owner = {"id": f"other-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "EC14 Tenant"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Other EC14 Tenant"},
    ])
    await db.users.insert_many([owner, staff, other_owner])
    yield {"tenant_id": tenant_id, "other_tenant_id": other_tenant_id, "owner": owner, "staff": staff, "other_owner": other_owner}
    app.dependency_overrides.pop(get_current_user, None)


async def _build_launchable_store(client: AsyncClient, suffix: str) -> dict:
    owner_resp = await client.post(
        "/api/webstores/owners",
        json={"name": "Fundraiser Chair", "email": f"chair-{suffix}@example.com", "organization": "Boosters"},
    )
    assert owner_resp.status_code == 201, owner_resp.text
    webstore_owner = owner_resp.json()

    store_resp = await client.post(
        "/api/webstores",
        json={
            "owner_id": webstore_owner["id"],
            "name": f"Boosters Store {suffix}",
            "slug": f"boosters-{suffix}",
            "store_type": "fundraiser",
        },
    )
    assert store_resp.status_code == 201, store_resp.text
    store = store_resp.json()
    await db.webstores.update_one(
        {"tenant_id": store["tenant_id"], "id": store["id"]},
        {"$set": {
            "setup_profile.fundraiser_goal_amount": 10000,
            "setup_profile.profit_allocation_type": "fundraiser",
            "store_settings.deadlines.order_deadline_at": "2099-12-31T23:59:59+00:00",
        }},
    )
    await db.webstore_questionnaire_submissions.insert_one({
        "id": f"questionnaire-{suffix}",
        "tenant_id": store["tenant_id"],
        "webstore_id": store["id"],
        "owner_id": store["owner_id"],
        "status": "submitted",
        "answers": {"fundraiser_goal_amount": 10000},
        "submitted_snapshot": {"answers": {"fundraiser_goal_amount": 10000}},
    })

    template_resp = await client.post(
        "/api/webstores/product-templates",
        json={
            "template_name": f"Cotton Tee {suffix}",
            "product_category": "apparel",
            "product_type": "t_shirt",
            "default_description": "Soft cotton shirt",
            "suggested_production_cost_cents": 700,
            "suggested_selling_price_cents": 2500,
            "suggested_store_owner_share_cents": 300,
            "platform_fee_basis_points": 200,
            "default_variants": [{"size": "L", "color": "Black"}],
        },
    )
    assert template_resp.status_code == 201, template_resp.text
    template = template_resp.json()

    product_resp = await client.post(
        f"/api/webstores/{store['id']}/products",
        json={"source_template_id": template["id"]},
    )
    assert product_resp.status_code == 201, product_resp.text
    product = product_resp.json()
    await db.webstore_products.update_one(
        {"tenant_id": product["tenant_id"], "webstore_id": store["id"], "id": product["id"]},
        {
            "$set": {
                "status": "active",
                "public": True,
                "featured": True,
                "sku": f"TEE-{suffix}",
                "launch_packet_eligible": True,
                "launch_packet_include": True,
                "approval_status": "approved",
                "approval_revision": product["revision"],
                "mockup_associations": [{"mockup_id": f"mockup-{suffix}"}],
                "selling_price_cents": template["suggested_selling_price_cents"],
                "production_cost_cents": template["suggested_production_cost_cents"],
                "store_owner_share_cents": template["suggested_store_owner_share_cents"],
                "platform_fee_basis_points": template["platform_fee_basis_points"],
                "variants": template["default_variants"],
            }
        },
    )
    product.update(
        {
            "status": "active",
            "public": True,
            "featured": True,
            "sku": f"TEE-{suffix}",
            "launch_packet_eligible": True,
            "launch_packet_include": True,
            "approval_status": "approved",
            "approval_revision": product["revision"],
            "mockup_associations": [{"mockup_id": f"mockup-{suffix}"}],
            "selling_price_cents": template["suggested_selling_price_cents"],
            "production_cost_cents": template["suggested_production_cost_cents"],
            "store_owner_share_cents": template["suggested_store_owner_share_cents"],
            "platform_fee_basis_points": template["platform_fee_basis_points"],
            "variants": template["default_variants"],
        }
    )
    await db.webstore_mockups.insert_one(
        {
            "id": f"mockup-{suffix}",
            "tenant_id": product["tenant_id"],
            "webstore_id": store["id"],
            "product_id": product["id"],
            "generation_source": "manual",
            "purpose": "customer_preview",
            "alt_text": "Cotton tee mockup",
            "status": "owner_approved",
            "shop_approved": True,
            "owner_visible": True,
            "owner_approved": True,
        }
    )
    await db.webstore_branding_versions.insert_one(
        WebstoreBrandingPublishedVersion(
            tenant_id=store["tenant_id"],
            webstore_id=store["id"],
            version=1,
            branding={
                "brand_basics": {"display_name": store["name"]},
                "colors_fonts": {"primary_color": "#0f172a", "accent_color": "#2563eb"},
                "store_type_content": {"fundraiser_name": "Boosters", "campaign_message": "Support the team."},
            },
            content_hash=f"stage6-ec14-{suffix}",
            published_by_user_id="stage6-test",
            published_by_email="stage6@example.com",
        ).model_dump()
    )

    packet_resp = await client.post(f"/api/webstores/{store['id']}/launch-packets", json={"promotion_copy": "Order by Friday"})
    assert packet_resp.status_code == 201, packet_resp.text
    packet = packet_resp.json()
    send_resp = await client.post(f"/api/webstores/{store['id']}/launch-packets/{packet['id']}/send")
    assert send_resp.status_code == 200, send_resp.text

    return {"webstore_owner": webstore_owner, "store": store, "template": template, "product": product, "packet": packet}


@pytest.mark.asyncio
async def test_webstore_permission_tenant_and_owner_portal_scope(ctx):
    async with await _client_as(ctx["staff"]) as staff_client:
        denied = await staff_client.post("/api/webstores/owners", json={"name": "Nope", "email": "nope@example.com"})
        assert denied.status_code == 403

    async with await _client_as(ctx["owner"]) as owner_client:
        built = await _build_launchable_store(owner_client, uuid.uuid4().hex[:6])
        other_owner_resp = await owner_client.post(
            "/api/webstores/owners",
            json={"name": "Other Chair", "email": f"other-chair-{uuid.uuid4().hex[:6]}@example.com"},
        )
        assert other_owner_resp.status_code == 201
        other_store_resp = await owner_client.post(
            "/api/webstores",
            json={"owner_id": other_owner_resp.json()["id"], "name": "Other Store", "slug": f"other-{uuid.uuid4().hex[:6]}"},
        )
        assert other_store_resp.status_code == 201

    identity = await db.portal_identities.find_one({"id": built["webstore_owner"]["portal_identity_id"]}, {"_id": 0})
    token = create_portal_token(
        portal_identity_id=identity["id"],
        tenant_id=ctx["tenant_id"],
        portal_type="webstore_owner",
    )
    async with await _token_client(token) as portal:
        mine = await portal.get("/api/portal/webstores")
        assert mine.status_code == 200, mine.text
        assert [item["id"] for item in mine.json()["items"]] == [built["store"]["id"]]
        forbidden = await portal.get(f"/api/portal/webstores/{other_store_resp.json()['id']}")
        assert forbidden.status_code == 403

    async with await _client_as(ctx["other_owner"]) as other_client:
        isolated = await other_client.get(f"/api/webstores/{built['store']['id']}")
        assert isolated.status_code == 404


@pytest.mark.asyncio
async def test_public_storefront_can_launch_before_provider_checkout_authority(ctx, monkeypatch):
    monkeypatch.setenv("AUTH_DEV_BYPASS", "true")
    suffix = uuid.uuid4().hex[:6]

    async with await _client_as(ctx["owner"]) as owner_client:
        built = await _build_launchable_store(owner_client, suffix)
        store = built["store"]
        product = built["product"]

        blocked = await owner_client.post(f"/api/webstores/{store['id']}/status", json={"status": "live"})
        assert blocked.status_code == 409
        readiness = await owner_client.get(f"/api/webstores/{store['id']}/launch-readiness")
        checks = readiness.json()["checks"]
        assert checks["active_public_products_with_prices"] is True
        assert checks["entitlement"] is False

        identity = await db.portal_identities.find_one({"id": built["webstore_owner"]["portal_identity_id"]}, {"_id": 0})
        token = create_portal_token(portal_identity_id=identity["id"], tenant_id=ctx["tenant_id"], portal_type="webstore_owner")
        async with await _token_client(token) as portal:
            approval = await portal.post(f"/api/portal/webstores/{store['id']}/launch-packets/{built['packet']['id']}/approve")
            assert approval.status_code == 200, approval.text

        async with await _client_as(ctx["owner"]) as owner_client_again:
            await _upsert_entitlement_for_tests(tenant_id=ctx["tenant_id"], feature_key="webstores", enabled=True)
            patched = await owner_client_again.patch(f"/api/webstores/{store['id']}", json={"terms_fee_acknowledged": True, "payment_readiness_status": "ready"})
            assert patched.status_code == 200, patched.text
            async with await _token_client(token) as portal:
                terms = await portal.post(f"/api/portal/webstores/{store['id']}/terms/accept", json={"terms_version": store["required_terms_version"]})
                assert terms.status_code == 200, terms.text
            app.dependency_overrides[get_current_user] = _override(ctx["owner"])
            ready = await owner_client_again.get(f"/api/webstores/{store['id']}/launch-readiness")
            assert ready.status_code == 200
            assert ready.json()["ready"] is True, ready.text
            assert ready.json()["checks"]["payment_ready"] is False
            assert ready.json()["public_launch_blocked_until_batch_3"] is True
            assert ready.json()["payment_readiness_source"] == "provider_boundary"
            launched = await owner_client_again.post(f"/api/webstores/{store['id']}/status", json={"status": "live"})
            assert launched.status_code == 200, launched.text
            launched_store = await db.webstores.find_one({"tenant_id": ctx["tenant_id"], "id": store["id"]}, {"_id": 0})
            assert launched_store["status"] == "live"
            assert launched_store["checkout_enabled"] is False
            public = await owner_client_again.get(f"/api/public/webstores/{store['public_slug']}")
            assert public.status_code == 200, public.text
            assert public.json()["webstore"]["checkout_enabled"] is False
            return
