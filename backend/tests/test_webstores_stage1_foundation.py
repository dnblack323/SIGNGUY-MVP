"""Webstores Stage 1 foundation and safety contracts."""
from __future__ import annotations

import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from pymongo.errors import DuplicateKeyError

from app.core.db import db, ensure_indexes
from app.core.portal_security import create_portal_token
from app.deps import get_current_user
from app.models.webstore import WEBSTORE_TYPES
from app.services.entitlements import _upsert_entitlement_for_tests
from app.services.portal_identity import create_portal_identity
from app.services.webstore_payments import process_verified_payment_event
from app.services.webstores import WebstoreError, create_buyer_order, create_purchase_intent
from server import app


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


@pytest.fixture
async def stage1_ctx():
    await ensure_indexes()
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-webstore-stage1-{suffix}"
    other_tenant_id = f"t-webstore-stage1-other-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    other_owner = {"id": f"other-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": f"shop-{suffix}", "name": f"Shop {suffix}"},
        {"id": other_tenant_id, "slug": f"other-shop-{suffix}", "name": f"Other Shop {suffix}"},
    ])
    await db.users.insert_many([owner, other_owner])
    yield {"suffix": suffix, "tenant_id": tenant_id, "other_tenant_id": other_tenant_id, "owner": owner, "other_owner": other_owner}
    app.dependency_overrides.pop(get_current_user, None)


async def _create_owner_and_store(client: AsyncClient, suffix: str, *, store_type: str = "general") -> dict:
    owner_resp = await client.post(
        "/api/webstores/owners",
        json={"name": f"Store Owner {suffix}", "email": f"webstore-owner-{suffix}@example.com"},
    )
    assert owner_resp.status_code == 201, owner_resp.text
    store_owner = owner_resp.json()
    store_resp = await client.post(
        "/api/webstores",
        json={
            "owner_id": store_owner["id"],
            "name": f"Stage Store {suffix}",
            "slug": f"stage-store-{suffix}",
            "store_type": store_type,
            "stripe_payment_ready": True,
        },
    )
    assert store_resp.status_code == 201, store_resp.text
    return {"webstore_owner": store_owner, "store": store_resp.json()}


async def _seed_live_public_store(ctx: dict, *, public_slug: str | None = None, internal_slug: str | None = None) -> dict:
    suffix = uuid.uuid4().hex[:8]
    webstore_id = f"ws-stage1-{suffix}"
    owner_id = f"wso-stage1-{suffix}"
    product_id = f"prod-stage1-{suffix}"
    public_slug = public_slug or f"public-stage1-{suffix}"
    internal_slug = internal_slug or f"internal-stage1-{suffix}"
    await db.webstore_owners.insert_one(
        {
            "id": owner_id,
            "tenant_id": ctx["tenant_id"],
            "name": "Stage Owner",
            "email": f"stage-owner-{suffix}@example.com",
            "status": "active",
        }
    )
    await db.webstores.insert_one(
        {
            "id": webstore_id,
            "tenant_id": ctx["tenant_id"],
            "owner_id": owner_id,
            "name": "Public Stage Store",
            "slug": internal_slug,
            "public_slug": public_slug,
            "store_type": "general",
            "status": "live",
            "checkout_enabled": True,
            "stripe_payment_ready": True,
            "production_cost_cents": 999999,
            "staff_notes": "internal",
            "public_url": f"/p/webstores/{public_slug}",
        }
    )
    await db.webstore_products.insert_one(
        {
            "id": product_id,
            "tenant_id": ctx["tenant_id"],
            "webstore_id": webstore_id,
            "name": "Stage Shirt",
            "description": "Cotton shirt",
            "category": "apparel",
            "product_type": "shirt",
            "sku": "STAGE-SHIRT",
            "production_cost_cents": 700,
            "selling_price_cents": 2500,
            "store_owner_share_cents": 300,
            "platform_fee_basis_points": 200,
            "supplier_notes": "internal supplier",
            "staff_notes": "internal staff",
            "status": "active",
            "public": True,
            "featured": True,
            "approval_status": "approved",
            "approval_revision": 1,
            "revision": 1,
            "variants": [],
        }
    )
    return {"webstore_id": webstore_id, "owner_id": owner_id, "product_id": product_id, "public_slug": public_slug}


@pytest.mark.asyncio
async def test_public_purchase_creates_intent_not_unpaid_buyer_order_or_canonical_order(stage1_ctx):
    seeded = await _seed_live_public_store(stage1_ctx)
    before_buyer_orders = await db.webstore_buyer_orders.count_documents({"tenant_id": stage1_ctx["tenant_id"]})
    before_orders = await db.orders.count_documents({"tenant_id": stage1_ctx["tenant_id"]})

    public = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    async with public:
        tampered = await public.post(
            f"/api/public/webstores/{seeded['public_slug']}/purchase-intents",
            json={
                "buyer_name": "Casey Buyer",
                "buyer_email": "casey@example.com",
                "line_items": [{"product_id": seeded["product_id"], "quantity": 2}],
                "donation_cents": 5000,
                "shipping_cents": 800,
                "tax_cents": 400,
                "total_cents": 999999,
                "idempotency_key": f"intent-{uuid.uuid4().hex}",
            },
        )
        response = await public.post(
            f"/api/public/webstores/{seeded['public_slug']}/purchase-intents",
            json={
                "buyer_name": "Casey Buyer",
                "buyer_email": "casey@example.com",
                "line_items": [{"product_id": seeded["product_id"], "quantity": 2}],
                "idempotency_key": f"intent-{uuid.uuid4().hex}",
            },
        )

    assert tampered.status_code == 400
    assert response.status_code == 503, response.text
    assert response.json()["detail"] == "Online checkout is unavailable until the Webstore payment provider is configured and verified."
    assert await db.webstore_buyer_orders.count_documents({"tenant_id": stage1_ctx["tenant_id"]}) == before_buyer_orders
    assert await db.orders.count_documents({"tenant_id": stage1_ctx["tenant_id"]}) == before_orders
    assert await db.webstore_purchase_intents.count_documents({"tenant_id": stage1_ctx["tenant_id"]}) == 0


@pytest.mark.asyncio
async def test_purchase_intents_are_idempotent_and_service_rejects_public_money_authority(stage1_ctx):
    seeded = await _seed_live_public_store(stage1_ctx)
    key = f"intent-{uuid.uuid4().hex}"
    payload = {
        "buyer_name": "Ida Buyer",
        "buyer_email": "ida@example.com",
        "line_items": [{"product_id": seeded["product_id"], "quantity": 1}],
        "idempotency_key": key,
    }
    with pytest.raises(WebstoreError) as unavailable:
        await create_buyer_order(seeded["public_slug"], payload)
    assert unavailable.value.code == "payment_provider_not_configured"
    assert await db.webstore_purchase_intents.count_documents({"tenant_id": stage1_ctx["tenant_id"], "idempotency_key": key}) == 0

    with pytest.raises(WebstoreError) as money_error:
        await create_purchase_intent(seeded["public_slug"], {**payload, "idempotency_key": f"intent-{uuid.uuid4().hex}", "shipping_cents": 1})
    assert money_error.value.code == "public_money_fields_not_allowed"


@pytest.mark.asyncio
async def test_verified_payment_processing_is_idempotent_and_creates_canonical_graph_once(stage1_ctx):
    before_orders = await db.orders.count_documents({"tenant_id": stage1_ctx["tenant_id"]})
    with pytest.raises(WebstoreError) as unavailable:
        await process_verified_payment_event({
            "tenant_id": stage1_ctx["tenant_id"],
            "purchase_intent_id": f"intent-{uuid.uuid4().hex}",
            "provider": "stripe",
            "provider_event_id": f"evt_{uuid.uuid4().hex}",
            "provider_payment_id": f"pi_{uuid.uuid4().hex}",
            "amount_cents": 1000,
            "currency": "usd",
        })
    assert unavailable.value.code == "payment_provider_not_configured"
    assert await db.orders.count_documents({"tenant_id": stage1_ctx["tenant_id"]}) == before_orders
    assert await db.payments.count_documents({"tenant_id": stage1_ctx["tenant_id"]}) == 0


@pytest.mark.asyncio
async def test_canonical_commerce_source_indexes_are_unique(stage1_ctx):
    order_indexes = await db.orders.index_information()
    item_indexes = await db.order_items.index_information()
    payment_indexes = await db.payments.index_information()

    assert any(
        spec.get("unique") is True
        and spec.get("key") == [("tenant_id", 1), ("source_type", 1), ("source_id", 1)]
        and spec.get("partialFilterExpression") == {"source_type": {"$type": "string"}, "source_id": {"$type": "string"}}
        for spec in order_indexes.values()
    )
    assert any(
        spec.get("unique") is True
        and spec.get("key") == [("tenant_id", 1), ("source_type", 1), ("source_id", 1), ("position", 1)]
        and spec.get("partialFilterExpression") == {"source_type": {"$type": "string"}, "source_id": {"$type": "string"}}
        for spec in item_indexes.values()
    )
    assert any(
        spec.get("unique") is True
        and spec.get("key") == [("tenant_id", 1), ("invoice_id", 1), ("idempotency_key", 1)]
        and spec.get("partialFilterExpression") == {"idempotency_key": {"$type": "string"}}
        for spec in payment_indexes.values()
    )


@pytest.mark.asyncio
async def test_verified_payment_rejects_amount_and_currency_mismatch_without_canonical_records(stage1_ctx):
    before_orders = await db.orders.count_documents({"tenant_id": stage1_ctx["tenant_id"]})
    with pytest.raises(WebstoreError) as mismatch_error:
        await process_verified_payment_event(
            {
                "tenant_id": stage1_ctx["tenant_id"],
                "purchase_intent_id": f"intent-{uuid.uuid4().hex}",
                "provider": "stripe",
                "provider_event_id": f"evt_{uuid.uuid4().hex}",
                "provider_payment_id": f"pi_{uuid.uuid4().hex}",
                "amount_cents": 1001,
                "currency": "usd",
            }
        )
    assert mismatch_error.value.code == "payment_provider_not_configured"
    assert await db.orders.count_documents({"tenant_id": stage1_ctx["tenant_id"]}) == before_orders
    assert await db.webstore_payment_events.count_documents({"tenant_id": stage1_ctx["tenant_id"]}) == 0


@pytest.mark.asyncio
async def test_public_slug_is_global_and_public_responses_are_redacted(stage1_ctx):
    seeded = await _seed_live_public_store(stage1_ctx, public_slug=f"shared-public-{stage1_ctx['suffix']}", internal_slug="same")
    await db.webstores.insert_one(
        {
            "id": f"other-ws-{stage1_ctx['suffix']}",
            "tenant_id": stage1_ctx["other_tenant_id"],
            "owner_id": f"other-owner-{stage1_ctx['suffix']}",
            "name": "Other Store",
            "slug": "same",
            "public_slug": f"other-public-{stage1_ctx['suffix']}",
            "store_type": "general",
            "status": "live",
            "checkout_enabled": True,
        }
    )
    public = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    async with public:
        by_internal_slug = await public.get("/api/public/webstores/same")
        by_public_slug = await public.get(f"/api/public/webstores/{seeded['public_slug']}")

    assert by_internal_slug.status_code == 404
    assert by_public_slug.status_code == 200
    body = by_public_slug.json()
    assert body["webstore"]["public_slug"] == seeded["public_slug"]
    assert "tenant_id" not in body["webstore"]
    assert "production_cost_cents" not in body["webstore"]
    assert "staff_notes" not in body["webstore"]
    product = body["products"][0]
    assert "production_cost_cents" not in product
    assert "store_owner_share_cents" not in product
    assert "supplier_notes" not in product
    assert body["webstore"]["checkout_enabled"] is False
    assert body["webstore"]["checkout_unavailable_reason"]


@pytest.mark.asyncio
async def test_store_owner_and_manager_portal_scope_and_redaction(stage1_ctx):
    async with await _client_as(stage1_ctx["owner"]) as client:
        first = await _create_owner_and_store(client, f"{stage1_ctx['suffix']}-one")
        second_resp = await client.post(
            "/api/webstores",
            json={
                "owner_id": first["webstore_owner"]["id"],
                "name": f"Second Store {stage1_ctx['suffix']}",
                "slug": f"second-store-{stage1_ctx['suffix']}",
                "store_type": "event",
            },
        )
        assert second_resp.status_code == 201, second_resp.text
        second = second_resp.json()

    owner_identity = await db.portal_identities.find_one({"id": first["webstore_owner"]["portal_identity_id"]}, {"_id": 0})
    manager_identity = await create_portal_identity(
        tenant_id=stage1_ctx["tenant_id"],
        portal_type="webstore_manager",
        webstore_owner_id=first["webstore_owner"]["id"],
        webstore_id=first["store"]["id"],
        email=f"manager-{stage1_ctx['suffix']}@example.com",
        full_name="Store Manager",
    )

    async with await _portal_client(create_portal_token(portal_identity_id=owner_identity["id"], tenant_id=stage1_ctx["tenant_id"], portal_type="webstore_owner")) as owner_portal:
        owner_list = await owner_portal.get("/api/portal/webstores")
        assert owner_list.status_code == 200, owner_list.text
        assert {item["id"] for item in owner_list.json()["items"]} == {first["store"]["id"], second["id"]}

    async with await _portal_client(create_portal_token(portal_identity_id=manager_identity["id"], tenant_id=stage1_ctx["tenant_id"], portal_type="webstore_manager")) as manager_portal:
        manager_list = await manager_portal.get("/api/portal/webstores")
        assert manager_list.status_code == 200, manager_list.text
        assert [item["id"] for item in manager_list.json()["items"]] == [first["store"]["id"]]
        denied = await manager_portal.get(f"/api/portal/webstores/{second['id']}")
        assert denied.status_code == 403
        detail = await manager_portal.get(f"/api/portal/webstores/{first['store']['id']}")
        assert detail.status_code == 200, detail.text
        assert "tenant_id" not in detail.json()["webstore"]


@pytest.mark.asyncio
async def test_webstore_types_lifecycle_and_computed_readiness(stage1_ctx):
    async with await _client_as(stage1_ctx["owner"]) as client:
        created_types = []
        for store_type in ["b2b", "fundraiser", "event", "promotional", "general"]:
            built = await _create_owner_and_store(client, f"{stage1_ctx['suffix']}-{store_type}", store_type=store_type)
            created_types.append(built["store"]["store_type"])
            assert built["store"]["stripe_payment_ready"] is False
            assert built["store"]["public_slug"]
        assert created_types == ["b2b", "fundraiser", "event", "promotional", "general"]

        legacy = {
            **built["store"],
            "id": f"legacy-employee-{stage1_ctx['suffix']}",
            "name": "Legacy Employee Store",
            "slug": f"legacy-employee-{stage1_ctx['suffix']}",
            "public_slug": f"legacy-employee-public-{stage1_ctx['suffix']}",
            "public_url": f"/p/webstores/legacy-employee-public-{stage1_ctx['suffix']}",
            "store_type": "employee",
        }
        await db.webstores.insert_one(legacy)
        legacy_read = await client.get(f"/api/webstores/{legacy['id']}")
        assert legacy_read.status_code == 200, legacy_read.text
        assert legacy_read.json()["webstore"]["store_type"] == "employee"

        legacy_rename = await client.patch(
            f"/api/webstores/{legacy['id']}",
            json={"name": "Renamed Legacy Employee Store"},
        )
        assert legacy_rename.status_code == 200, legacy_rename.text
        assert legacy_rename.json()["store_type"] == "employee"

        non_employee_to_employee = await client.patch(
            f"/api/webstores/{built['store']['id']}",
            json={"store_type": "employee"},
        )
        assert non_employee_to_employee.status_code == 400

        other_legacy = {
            **{key: value for key, value in legacy.items() if key != "_id"},
            "id": f"legacy-employee-other-{stage1_ctx['suffix']}",
            "tenant_id": stage1_ctx["other_tenant_id"],
            "owner_id": f"other-legacy-owner-{stage1_ctx['suffix']}",
            "slug": f"other-legacy-employee-{stage1_ctx['suffix']}",
            "public_slug": f"other-legacy-employee-public-{stage1_ctx['suffix']}",
            "public_url": f"/p/webstores/other-legacy-employee-public-{stage1_ctx['suffix']}",
        }
        await db.webstores.insert_one(other_legacy)
        assert (await client.get(f"/api/webstores/{other_legacy['id']}")).status_code == 404

        templates = await client.get("/api/webstores/setup/questionnaire-templates", params={"active_only": True})
        assert templates.status_code == 200, templates.text
        seeded_types = {item["store_type"] for item in templates.json()["items"]}
        assert seeded_types == {"base", *WEBSTORE_TYPES, "employee"}

        rejected_employee = await client.post(
            "/api/webstores",
            json={"owner_id": built["webstore_owner"]["id"], "name": "New Employee Store", "store_type": "employee"},
        )
        assert rejected_employee.status_code == 400

        invalid_type = await client.post(
            "/api/webstores",
            json={"owner_id": built["webstore_owner"]["id"], "name": "Bad Type", "slug": f"bad-{stage1_ctx['suffix']}", "store_type": "employee-store"},
        )
        assert invalid_type.status_code == 400

        await _upsert_entitlement_for_tests(tenant_id=stage1_ctx["tenant_id"], feature_key="webstores", enabled=True)
        patched = await client.patch(f"/api/webstores/{built['store']['id']}", json={"terms_fee_acknowledged": True, "stripe_payment_ready": True})
        assert patched.status_code == 200
        assert patched.json()["stripe_payment_ready"] is False
        readiness = await client.get(f"/api/webstores/{built['store']['id']}/launch-readiness")
        assert readiness.status_code == 200
        assert readiness.json()["checks"]["payment_ready"] is False
        assert readiness.json()["payment_readiness_source"] == "provider_boundary"
        invalid_transition = await client.post(f"/api/webstores/{built['store']['id']}/status", json={"status": "live"})
        assert invalid_transition.status_code == 409
        valid_transition = await client.post(f"/api/webstores/{built['store']['id']}/status", json={"status": "questionnaire_sent"})
        assert valid_transition.status_code == 200, valid_transition.text


@pytest.mark.asyncio
async def test_public_storefront_requires_current_product_owner_approval(stage1_ctx):
    seeded = await _seed_live_public_store(stage1_ctx)
    stale_id = f"stale-public-{uuid.uuid4().hex[:8]}"
    pending_id = f"pending-public-{uuid.uuid4().hex[:8]}"
    base_product = {
        "tenant_id": stage1_ctx["tenant_id"],
        "webstore_id": seeded["webstore_id"],
        "name": "Hidden Public Product",
        "description": "Should not be serialized",
        "selling_price_cents": 2500,
        "status": "active",
        "public": True,
        "revision": 1,
        "variants": [],
    }
    await db.webstore_products.insert_many([
        {**base_product, "id": pending_id, "approval_status": "pending_owner_approval", "approval_revision": 1},
        {**base_product, "id": stale_id, "approval_status": "approved", "approval_revision": 1, "revision": 2},
    ])

    public = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    async with public:
        response = await public.get(f"/api/public/webstores/{seeded['public_slug']}")
    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()["products"]] == [seeded["product_id"]]

    await db.webstores.update_one(
        {"id": seeded["webstore_id"], "tenant_id": stage1_ctx["tenant_id"]},
        {"$set": {"store_settings.access_policy.mode": "restricted"}},
    )
    public = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    async with public:
        restricted = await public.get(f"/api/public/webstores/{seeded['public_slug']}")
    assert restricted.status_code == 404


@pytest.mark.asyncio
async def test_legacy_buyer_order_requires_verified_payment_before_bridge(stage1_ctx):
    buyer_order_id = f"legacy-buyer-{uuid.uuid4().hex[:8]}"
    webstore_id = f"legacy-ws-{uuid.uuid4().hex[:8]}"
    await db.webstores.insert_one(
        {
            "id": webstore_id,
            "tenant_id": stage1_ctx["tenant_id"],
            "owner_id": f"legacy-owner-{uuid.uuid4().hex[:8]}",
            "name": "Legacy Store",
            "slug": f"legacy-{uuid.uuid4().hex[:8]}",
            "public_slug": f"legacy-public-{uuid.uuid4().hex[:8]}",
            "store_type": "general",
            "status": "live",
        }
    )
    await db.webstore_buyer_orders.insert_one(
        {
            "id": buyer_order_id,
            "tenant_id": stage1_ctx["tenant_id"],
            "webstore_id": webstore_id,
            "buyer_name": "Legacy Buyer",
            "buyer_email": "legacy@example.com",
            "line_items": [],
            "product_subtotal_cents": 1000,
            "total_cents": 1000,
            "status": "new",
            "payment_status": "pending",
            "fulfillment_status": "not_started",
        }
    )
    async with await _client_as(stage1_ctx["owner"]) as client:
        response = await client.post(f"/api/webstores/buyer-orders/{buyer_order_id}/bridge")
    assert response.status_code == 409
    assert response.json()["detail"] == "Legacy Webstore buyer orders cannot become canonical Orders without verified payment evidence."
    assert await db.orders.count_documents({"tenant_id": stage1_ctx["tenant_id"]}) == 0
