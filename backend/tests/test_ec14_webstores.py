"""EC14 - Webstores contracts."""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.portal_security import create_portal_token
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
async def test_launch_checkout_purchase_intent_ledger_reversal_and_legacy_bridge_safety(ctx, monkeypatch):
    monkeypatch.setenv("AUTH_DEV_BYPASS", "true")
    monkeypatch.setenv("WEBSTORE_TEST_WEBHOOK_SECRET", "webstore-test-secret")
    before_invoices = await db.invoices.count_documents({"tenant_id": ctx["tenant_id"]})
    before_payments = await db.payments.count_documents({"tenant_id": ctx["tenant_id"]})
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
            assert ready.json()["checks"]["payment_ready"] is True
            assert ready.json()["public_launch_blocked_until_batch_3"] is False
            assert ready.json()["payment_readiness_source"] == "computed"
            launched = await owner_client_again.post(f"/api/webstores/{store['id']}/status", json={"status": "live"})
            assert launched.status_code == 200, launched.text
            store = await db.webstores.find_one({"tenant_id": ctx["tenant_id"], "id": store["id"]}, {"_id": 0})

    public = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    async with public:
        storefront = await public.get(f"/api/public/webstores/{store['public_slug']}")
        assert storefront.status_code == 200, storefront.text
        public_product = storefront.json()["products"][0]
        assert public_product["id"] == product["id"]
        assert "production_cost_cents" not in public_product
        assert storefront.json()["webstore"]["checkout_enabled"] is True
        tampered = await public.post(
            f"/api/public/webstores/{store['public_slug']}/buyer-orders",
            json={
                "buyer_name": "Casey Buyer",
                "buyer_email": f"casey-{suffix}@example.com",
                "line_items": [{"product_id": product["id"], "quantity": 2}],
                "donation_cents": 500,
                "shipping_cents": 800,
                "tax_cents": 350,
                "idempotency_key": f"buyer-{suffix}",
            },
        )
        assert tampered.status_code == 400
        order_resp = await public.post(
            f"/api/public/webstores/{store['public_slug']}/buyer-orders",
            json={
                "buyer_name": "Casey Buyer",
                "buyer_email": f"casey-{suffix}@example.com",
                "line_items": [{"product_id": product["id"], "quantity": 2}],
                "idempotency_key": f"buyer-{suffix}",
            },
        )
        assert order_resp.status_code == 201, order_resp.text
        payload = order_resp.json()
        purchase_intent = payload["purchase_intent"]
        assert "immutable_snapshot" not in purchase_intent
        assert purchase_intent["product_subtotal_cents"] == 5000
        assert purchase_intent["donation_cents"] == 0
        assert purchase_intent["shipping_cents"] == 0
        assert purchase_intent["tax_cents"] == 0
        assert purchase_intent["total_cents"] == 5000
        assert payload["checkout_available"] is True
        assert payload["checkout"]["payment_authority"] == "verified_provider_event"
        assert await db.webstore_buyer_orders.count_documents({"tenant_id": ctx["tenant_id"]}) == 0
        assert await db.webstore_ledger_entries.count_documents({"tenant_id": ctx["tenant_id"], "buyer_order_id": purchase_intent["id"]}) == 0
        assert await db.orders.count_documents({"tenant_id": ctx["tenant_id"], "source_type": "webstore_purchase_intent", "source_id": purchase_intent["id"]}) == 0

        duplicate = await public.post(
            f"/api/public/webstores/{store['public_slug']}/buyer-orders",
            json={
                "buyer_name": "Casey Buyer",
                "buyer_email": f"casey-{suffix}@example.com",
                "line_items": [{"product_id": product["id"], "quantity": 2}],
                "idempotency_key": f"buyer-{suffix}",
            },
        )
        assert duplicate.status_code == 201
        assert duplicate.json()["purchase_intent"]["id"] == purchase_intent["id"]

    body = {
        "tenant_id": ctx["tenant_id"],
        "purchase_intent_id": purchase_intent["id"],
        "provider_event_id": f"evt-{suffix}",
        "provider_payment_id": f"pi-{suffix}",
        "amount_cents": 5000,
        "currency": "usd",
    }
    encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(b"webstore-test-secret", encoded, hashlib.sha256).hexdigest()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as webhook_client:
        processed = await webhook_client.post(
            "/api/webhooks/webstores/test-provider",
            content=encoded,
            headers={"Content-Type": "application/json", "X-Webstore-Test-Signature": f"sha256={signature}"},
        )
        assert processed.status_code == 200, processed.text
        replay = await webhook_client.post(
            "/api/webhooks/webstores/test-provider",
            content=encoded,
            headers={"Content-Type": "application/json", "X-Webstore-Test-Signature": f"sha256={signature}"},
        )
        assert replay.status_code == 200, replay.text

    payment_event = processed.json()["payment_event"]
    assert payment_event["status"] == "processed"
    assert await db.invoices.count_documents({"tenant_id": ctx["tenant_id"]}) == before_invoices
    assert await db.payments.count_documents({"tenant_id": ctx["tenant_id"]}) == before_payments + 1
    canonical = await db.webstore_purchase_intents.find_one({"tenant_id": ctx["tenant_id"], "id": purchase_intent["id"]}, {"_id": 0})
    assert canonical["canonical_order_id"]
    assert canonical["canonical_payment_id"]
    assert canonical["production_bridge_status"] == "bridged"
    assert canonical["work_order_id"]
    assert await db.orders.count_documents({"tenant_id": ctx["tenant_id"], "id": canonical["canonical_order_id"], "source_type": "webstore_purchase_intent"}) == 1
    assert await db.order_items.count_documents({"tenant_id": ctx["tenant_id"], "order_id": canonical["canonical_order_id"], "source_type": "webstore_purchase_intent"}) == 1
    assert await db.webstore_ledger_entries.count_documents({"tenant_id": ctx["tenant_id"], "buyer_order_id": purchase_intent["id"]}) >= 5

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as public_confirm:
        confirmation = await public_confirm.get(f"/api/public/webstores/{store['public_slug']}/confirmations/{canonical['confirmation_token']}")
        assert confirmation.status_code == 200, confirmation.text
        assert confirmation.json()["order"]["id"] == canonical["canonical_order_id"]

    async with await _client_as(ctx["owner"]) as owner_client:
        refund = await owner_client.post(
            f"/api/webstores/{store['id']}/payments/{canonical['canonical_payment_id']}/refund",
            json={"amount_cents": 1000, "reason": "Buyer requested quantity adjustment", "idempotency_key": f"refund-{suffix}"},
            headers={"Idempotency-Key": f"refund-{suffix}"},
        )
        assert refund.status_code == 201, refund.text
        assert refund.json()["refund_status"] == "partially_refunded"
        payout = await owner_client.post(
            f"/api/webstores/{store['id']}/payout-events",
            json={"purchase_intent_id": purchase_intent["id"], "amount_cents": 3200, "provider_event_id": f"payout-{suffix}", "status": "paid"},
        )
        assert payout.status_code == 201, payout.text
        dispute = await owner_client.post(
            f"/api/webstores/{store['id']}/dispute-events",
            json={"purchase_intent_id": purchase_intent["id"], "amount_cents": 500, "provider_event_id": f"dispute-{suffix}", "status": "opened"},
        )
        assert dispute.status_code == 201, dispute.text
        report = await owner_client.get(f"/api/webstores/{store['id']}/reports")
        assert report.status_code == 200
        assert report.json()["canonical_order_count"] == 1
        assert report.json()["refund_total_cents"] == 1000
        assert report.json()["payout_total_cents"] == 3200
        assert report.json()["dispute_hold_cents"] == 500

    ledger_id = f"legacy-ledger-{uuid.uuid4().hex[:8]}"
    await db.webstore_ledger_entries.insert_one(
        {
            "id": ledger_id,
            "tenant_id": ctx["tenant_id"],
            "webstore_id": store["id"],
            "buyer_order_id": "legacy-buyer-order",
            "entry_type": "platform_usage_fee",
            "amount_cents": 100,
            "currency": "usd",
            "basis_amount_cents": 5000,
            "source_type": "legacy_webstore_buyer_order",
            "source_id": "legacy-buyer-order",
            "status": "posted",
        }
    )
    async with await _client_as(ctx["owner"]) as owner_client:
        reversal = await owner_client.post(
            f"/api/webstores/ledger/{ledger_id}/platform-fee-reversals",
            json={"refund_basis_amount_cents": 2500},
        )
        assert reversal.status_code == 201, reversal.text
        assert reversal.json()["amount_cents"] == -50
        original = await db.webstore_ledger_entries.find_one({"id": ledger_id}, {"_id": 0})
        assert original["amount_cents"] == 100

        await db.webstore_buyer_orders.insert_one(
            {
                "id": f"legacy-buyer-{suffix}",
                "tenant_id": ctx["tenant_id"],
                "webstore_id": store["id"],
                "buyer_name": "Legacy Buyer",
                "buyer_email": f"legacy-{suffix}@example.com",
                "line_items": [],
                "product_subtotal_cents": 1000,
                "total_cents": 1000,
                "status": "new",
                "payment_status": "pending",
                "fulfillment_status": "not_started",
            }
        )
        bridge = await owner_client.post(f"/api/webstores/buyer-orders/legacy-buyer-{suffix}/bridge")
        assert bridge.status_code == 409
        assert bridge.json()["detail"] == "Legacy Webstore buyer orders cannot become canonical Orders without verified payment evidence."
