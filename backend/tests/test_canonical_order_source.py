from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.time_utils import utc_now
from app.deps import get_current_user
from app.services.webstores import bridge_buyer_order_to_order
from server import app


def _override_as(user: dict):
    async def _dep():
        return user

    return _dep


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override_as(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear_overrides() -> None:
    app.dependency_overrides.pop(get_current_user, None)


async def _seed_customer(tenant_id: str, suffix: str | None = None) -> str:
    suffix = suffix or uuid.uuid4().hex[:8]
    customer_id = f"cust-source-{suffix}"
    await db.customers.insert_one(
        {
            "id": customer_id,
            "tenant_id": tenant_id,
            "name": f"Source Customer {suffix}",
            "email": f"source-{suffix}@example.com",
        }
    )
    return customer_id


@pytest.mark.asyncio
async def test_direct_order_source_is_manual_and_cannot_be_spoofed(seeded_users):
    user = seeded_users["user_a"]
    customer_id = await _seed_customer(user["tenant_id"])

    async with await _client_as(user) as client:
        spoofed = await client.post(
            "/api/orders",
            json={"customer_id": customer_id, "job_name": "Spoof", "order_source": "webstore"},
        )
        assert spoofed.status_code == 422

        created = await client.post("/api/orders", json={"customer_id": customer_id, "job_name": "Manual Alpha"})
        assert created.status_code == 201, created.text
        order = created.json()
        assert order["order_source"] == "manual"
        assert order.get("order_source_record_id") is None

        patch_spoof = await client.patch(f"/api/orders/{order['id']}", json={"order_source": "quote"})
        assert patch_spoof.status_code == 422

        updated = await client.patch(f"/api/orders/{order['id']}", json={"job_name": "Manual Alpha Updated"})
        assert updated.status_code == 200, updated.text
        assert updated.json()["order_source"] == "manual"

    _clear_overrides()


@pytest.mark.asyncio
async def test_quote_conversion_source_is_quote(seeded_users):
    user = seeded_users["user_a"]
    customer_id = await _seed_customer(user["tenant_id"])

    async with await _client_as(user) as client:
        quote_resp = await client.post("/api/quotes", json={"customer_id": customer_id, "job_name": "Quote Alpha"})
        assert quote_resp.status_code == 201, quote_resp.text
        quote_id = quote_resp.json()["id"]

        conversion = await client.post(f"/api/quotes/{quote_id}/convert-to-order", json={})
        assert conversion.status_code == 200, conversion.text
        order = conversion.json()["order"]
        assert order["order_source"] == "quote"
        assert order["order_source_record_type"] == "quote"
        assert order["order_source_record_id"] == quote_id
        assert order["source_quote_id"] == quote_id

    _clear_overrides()


@pytest.mark.asyncio
async def test_webstore_bridge_source_is_webstore(seeded_users):
    user = seeded_users["user_a"]
    suffix = uuid.uuid4().hex[:8]
    buyer_order_id = f"buyer-source-{suffix}"
    await db.webstore_buyer_orders.insert_one(
        {
            "id": buyer_order_id,
            "tenant_id": user["tenant_id"],
            "webstore_id": f"store-source-{suffix}",
            "buyer_name": "Webstore Buyer",
            "buyer_email": f"webstore-buyer-{suffix}@example.com",
            "buyer_phone": "555-0100",
            "product_subtotal_cents": 2500,
            "tax_cents": 200,
            "total_cents": 2700,
            "line_items": [
                {
                    "product_id": f"prod-source-{suffix}",
                    "name": "Store Tee",
                    "quantity": 1,
                    "unit_price_cents": 2500,
                    "line_total_cents": 2500,
                }
            ],
            "status": "paid",
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }
    )

    bridge = await bridge_buyer_order_to_order(user, buyer_order_id)
    order = bridge["order"]
    assert order["order_source"] == "webstore"
    assert order["order_source_record_type"] == "webstore_buyer_order"
    assert order["order_source_record_id"] == buyer_order_id

    repeat = await bridge_buyer_order_to_order(user, buyer_order_id)
    assert repeat["order"]["id"] == order["id"]
    assert repeat["order"]["order_source"] == "webstore"


@pytest.mark.asyncio
async def test_wrap_lab_and_unknown_legacy_source_inference_is_tenant_scoped(seeded_users):
    user_a = seeded_users["user_a"]
    user_b = seeded_users["user_b"]
    customer_id = await _seed_customer(user_a["tenant_id"])
    order_id = f"legacy-order-{uuid.uuid4().hex[:8]}"
    await db.orders.insert_one(
        {
            "id": order_id,
            "tenant_id": user_a["tenant_id"],
            "number": 880001,
            "customer_id": customer_id,
            "job_name": "Legacy Wrap",
            "status": "draft",
            "created_by": user_a["id"],
        }
    )
    await db.wrap_projects.insert_one(
        {
            "id": f"wrap-other-{uuid.uuid4().hex[:8]}",
            "tenant_id": user_b["tenant_id"],
            "customer_id": f"customer-other-{uuid.uuid4().hex[:8]}",
            "order_id": order_id,
            "project_name": "Wrong Tenant Wrap",
            "status": "lead_intake",
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }
    )

    async with await _client_as(user_a) as client:
        wrong_tenant = await client.get(f"/api/orders/{order_id}")
        assert wrong_tenant.status_code == 200, wrong_tenant.text
        assert wrong_tenant.json()["order"]["order_source"] == "legacy_unknown"

    await db.wrap_projects.insert_one(
        {
            "id": f"wrap-source-{uuid.uuid4().hex[:8]}",
            "tenant_id": user_a["tenant_id"],
            "customer_id": customer_id,
            "order_id": order_id,
            "project_name": "Correct Tenant Wrap",
            "status": "lead_intake",
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }
    )

    async with await _client_as(user_a) as client:
        correct_tenant = await client.get(f"/api/orders/{order_id}")
        assert correct_tenant.status_code == 200, correct_tenant.text
        order = correct_tenant.json()["order"]
        assert order["order_source"] == "wrap_lab"
        assert order["order_source_record_type"] == "wrap_project"

    _clear_overrides()


@pytest.mark.asyncio
async def test_order_source_filtering_combines_status_search_and_pagination(seeded_users):
    user = seeded_users["user_a"]
    customer_id = await _seed_customer(user["tenant_id"])

    async with await _client_as(user) as client:
        for name in ["Alpha Vehicle", "Alpha Banner", "Beta Sign"]:
            response = await client.post("/api/orders", json={"customer_id": customer_id, "job_name": name})
            assert response.status_code == 201, response.text

        filtered = await client.get("/api/orders?order_source=manual&status=draft&search=Alpha&limit=1&skip=0")
        assert filtered.status_code == 200, filtered.text
        body = filtered.json()
        assert body["total"] == 2
        assert body["limit"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["order_source"] == "manual"
        assert "Alpha" in body["items"][0]["job_name"]

        second_page = await client.get("/api/orders?order_source=manual&status=draft&search=Alpha&limit=1&skip=1")
        assert second_page.status_code == 200, second_page.text
        assert len(second_page.json()["items"]) == 1
        assert second_page.json()["items"][0]["id"] != body["items"][0]["id"]

        unsupported = await client.get("/api/orders?order_source=made_up")
        assert unsupported.status_code == 400

        config = await client.get("/api/orders/source-filters")
        assert config.status_code == 200, config.text
        visible_sources = config.json()["visible_sources"]
        values = {item["value"] for item in visible_sources}
        assert {"manual", "quote", "webstore", "wrap_lab", "legacy_unknown"} <= values
        assert next(item for item in visible_sources if item["value"] == "legacy_unknown")["label"] == "Legacy / Unknown"
        reserved = {item["value"] for item in config.json()["reserved_hidden_sources"]}
        assert reserved == {"email", "facebook"}

    _clear_overrides()
