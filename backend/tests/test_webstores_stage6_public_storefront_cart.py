"""Focused Stage 6 public storefront and server-priced cart coverage."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db, ensure_indexes
from app.core.time_utils import prepare_for_mongo
from server import app


async def _public_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed_store(*, store_type: str = "general", settings: dict | None = None, setup: dict | None = None) -> tuple[dict, dict]:
    suffix = uuid.uuid4().hex[:10]
    tenant_id = f"t-stage6-{suffix}"
    store_id = f"ws-stage6-{suffix}"
    product_id = f"prod-stage6-{suffix}"
    store = {
        "id": store_id,
        "tenant_id": tenant_id,
        "name": f"Stage 6 {store_type.title()} Store",
        "slug": f"stage6-{suffix}",
        "public_slug": f"stage6-public-{suffix}",
        "public_url": f"/p/webstores/stage6-public-{suffix}",
        "store_type": store_type,
        "status": "live",
        "store_settings": settings or {},
        "setup_profile": setup or {},
    }
    product = {
        "id": product_id,
        "tenant_id": tenant_id,
        "webstore_id": store_id,
        "name": "Stage 6 Shirt",
        "description": "Approved public shirt",
        "product_type": "shirt",
        "sku": "STAGE6-SHIRT",
        "selling_price_cents": 2500,
        "production_cost_cents": 700,
        "store_owner_share_cents": 300,
        "status": "active",
        "public": True,
        "approval_status": "approved",
        "approval_revision": 2,
        "approval_invalidated_at": None,
        "revision": 2,
        "variants": [],
        "fulfillment_methods": ["pickup"],
        "default_fulfillment_method": "pickup",
        "personalization_enabled": False,
        "customer_images": {},
    }
    await db.webstores.insert_one(prepare_for_mongo(store))
    await db.webstore_products.insert_one(prepare_for_mongo(product))
    return store, product


@pytest.mark.asyncio
async def test_public_storefront_filters_approval_and_redacts_internal_product_data():
    await ensure_indexes()
    store, product = await _seed_store()
    await db.webstore_products.insert_one(prepare_for_mongo({
        **product,
        "id": f"draft-{product['id']}",
        "name": "Private Draft",
        "public": False,
        "approval_status": "pending_owner_approval",
    }))

    async with await _public_client() as client:
        response = await client.get(f"/api/public/webstores/{store['public_slug']}")
        detail = await client.get(f"/api/public/webstores/{store['public_slug']}/products/{product['id']}")

    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()["products"]] == [product["id"]]
    public_product = response.json()["products"][0]
    assert "production_cost_cents" not in public_product
    assert "store_owner_share_cents" not in public_product
    assert detail.status_code == 200
    assert detail.json()["product"]["id"] == product["id"]


@pytest.mark.asyncio
async def test_cart_quote_reprices_variants_and_has_no_order_side_effect():
    await ensure_indexes()
    store, product = await _seed_store()
    await db.webstore_products.update_one(
        {"tenant_id": store["tenant_id"], "id": product["id"]},
        {"$set": {
            "fulfillment_methods": ["pickup", "shipping"],
            "default_fulfillment_method": "pickup",
            "shipping_cost_cents": 500,
            "variants": [{"id": "large", "name": "Large", "selling_price_cents": 2900, "status": "active"}],
            "personalization_enabled": True,
            "personalization_fields": [{"key": "name", "label": "Name", "required": True, "type": "text"}],
        }},
    )
    before_orders = await db.orders.count_documents({"tenant_id": store["tenant_id"]})
    before_intents = await db.webstore_purchase_intents.count_documents({"tenant_id": store["tenant_id"]})

    async with await _public_client() as client:
        missing = await client.post(f"/api/public/webstores/{store['public_slug']}/cart-quote", json={
            "line_items": [{"product_id": product["id"], "quantity": 1, "variant": {"id": "large"}, "fulfillment_method": "shipping"}],
        })
        quote = await client.post(f"/api/public/webstores/{store['public_slug']}/cart-quote", json={
            "line_items": [{
                "product_id": product["id"],
                "quantity": 2,
                "variant": {"id": "large"},
                "personalization": {"name": "Casey"},
                "fulfillment_method": "shipping",
                "unit_price_cents": 1,
            }],
        })

    assert missing.status_code == 400
    assert missing.json()["detail"] == "Required personalization fields are missing"
    assert quote.status_code == 200, quote.text
    assert quote.json()["subtotal_cents"] == 5800
    assert quote.json()["shipping_cents"] == 1000
    assert quote.json()["total_cents"] == 6800
    assert quote.json()["quote_version"] == "webstore_cart_quote_v1"
    assert quote.json()["expires_at"]
    assert await db.orders.count_documents({"tenant_id": store["tenant_id"]}) == before_orders
    assert await db.webstore_purchase_intents.count_documents({"tenant_id": store["tenant_id"]}) == before_intents


@pytest.mark.asyncio
async def test_fundraiser_progress_is_paid_only_and_donation_promo_are_previewed():
    await ensure_indexes()
    store, product = await _seed_store(
        store_type="fundraiser",
        setup={"fundraiser_goal_amount": 10000},
        settings={
            "donation": {"enabled": True, "minimum_cents": 100, "maximum_cents": 2000},
            "promo_codes": [{"code": "TEAM10", "discount_type": "percentage", "discount_basis_points": 1000}],
        },
    )
    await db.webstore_purchase_intents.insert_one(prepare_for_mongo({
        "id": f"unpaid-{product['id']}", "tenant_id": store["tenant_id"], "webstore_id": store["id"],
        "status": "pending_payment", "total_cents": 9999,
    }))

    async with await _public_client() as client:
        before_payment = await client.get(f"/api/public/webstores/{store['public_slug']}")
        await db.webstore_purchase_intents.insert_one(prepare_for_mongo({
            "id": f"paid-{product['id']}", "tenant_id": store["tenant_id"], "webstore_id": store["id"],
            "status": "paid_order_created", "canonical_payment_id": "pay-stage6", "total_cents": 2500,
        }))
        after_payment = await client.get(f"/api/public/webstores/{store['public_slug']}")
        quote = await client.post(f"/api/public/webstores/{store['public_slug']}/cart-quote", json={
            "line_items": [{"product_id": product["id"], "quantity": 1}],
            "donation_cents": 500,
            "promo_code": " team10 ",
        })

    assert before_payment.json()["webstore"]["fundraiser_progress"]["completed_sales_cents"] == 0
    assert after_payment.json()["webstore"]["fundraiser_progress"]["completed_sales_cents"] == 2500
    assert quote.status_code == 200, quote.text
    assert quote.json()["discount_cents"] == 250
    assert quote.json()["donation_cents"] == 500
    assert quote.json()["total_cents"] == 2750
    assert quote.json()["unpaid_progress_excluded"] is True
