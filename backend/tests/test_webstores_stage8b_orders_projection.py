"""Focused Stage 8B canonical Webstore Orders projection tests."""
from __future__ import annotations

import uuid

import pytest

from app.core.db import db, ensure_indexes
from app.services.webstore_orders import list_webstore_orders
from app.services.webstores import WebstoreError


async def _seed_projection(suffix: str) -> dict[str, str]:
    tenant_id = f"tenant-stage8b-{suffix}"
    webstore_id = f"webstore-stage8b-{suffix}"
    other_store_id = f"webstore-stage8b-other-{suffix}"
    customer_id = f"customer-stage8b-{suffix}"
    order_id = f"order-stage8b-{suffix}"
    intent_id = f"intent-stage8b-{suffix}"
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "Stage 8B Shop"})
    await db.webstores.insert_many(
        [
            {"id": webstore_id, "tenant_id": tenant_id, "slug": webstore_id, "name": "Stage 8B Webstore", "status": "live"},
            {"id": other_store_id, "tenant_id": tenant_id, "slug": other_store_id, "name": "Other Webstore", "status": "live"},
        ]
    )
    await db.customers.insert_one(
        {
            "id": customer_id,
            "tenant_id": tenant_id,
            "name": "Projection Buyer",
            "email": f"buyer-{suffix}@example.com",
            "phone": "555-0100",
        }
    )
    await db.orders.insert_one(
        {
            "id": order_id,
            "tenant_id": tenant_id,
            "number": 801,
            "customer_id": customer_id,
            "job_name": "Webstore order",
            "total_cents": 3200,
            "subtotal_cents": 3000,
            "tax_cents": 200,
            "amount_paid_cents": 3200,
            "balance_cents": 0,
            "status": "confirmed",
            "source_type": "webstore_purchase_intent",
            "source_id": intent_id,
            "created_by": "webstore-payment",
        }
    )
    await db.order_items.insert_one(
        {
            "id": f"item-stage8b-{suffix}",
            "tenant_id": tenant_id,
            "order_id": order_id,
            "position": 0,
            "description": "Projection Shirt",
            "sku": "SHIRT-001",
            "quantity": 2,
            "unit_price_cents": 1500,
            "line_subtotal_cents": 3000,
            "line_total_cents": 3000,
            "production_required": True,
            "estimated_cost_cents": 800,
            "pricing_snapshot": {
                "line_item": {
                    "product_id": "product-1",
                    "variant_id": "large",
                    "name": "Projection Shirt",
                    "selected_options": {"size": "Large"},
                    "production_mapping": {"method": "screen_print", "material": "cotton"},
                    "image_reference": {"file_id": "artwork-1"},
                    "fulfillment_method": "pickup",
                    "quantity": 2,
                    "unit_price_cents": 1500,
                    "line_total_cents": 3000,
                },
                "internal_cost_cents": 800,
            },
            "source_type": "webstore_purchase_intent",
            "source_id": intent_id,
        }
    )
    await db.payments.insert_one(
        {
            "id": f"payment-stage8b-{suffix}",
            "tenant_id": tenant_id,
            "invoice_id": f"webstore_purchase_intent:{intent_id}",
            "customer_id": customer_id,
            "order_id": order_id,
            "source": "stripe",
            "status": "confirmed",
            "amount_cents": 3200,
            "currency": "usd",
            "stripe_payment_intent_id": f"pi-internal-only-{suffix}",
            "confirmed_at": "2026-08-03T12:00:00+00:00",
        }
    )
    await db.webstore_purchase_intents.insert_one(
        {
            "id": intent_id,
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "buyer_name": "Projection Buyer",
            "buyer_email": f"buyer-{suffix}@example.com",
            "fulfillment_status": "awaiting_production_handoff",
            "production_bridge_status": "not_started",
            "status": "paid_order_created",
            "canonical_order_id": order_id,
            "line_items": [{"name": "Projection Shirt", "quantity": 2}],
        }
    )
    await db.webstore_buyer_orders.insert_one(
        {
            "id": f"legacy-stage8b-{suffix}",
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "buyer_name": "Legacy Order Must Not Appear",
            "total_cents": 9999,
        }
    )
    return {
        "tenant_id": tenant_id,
        "webstore_id": webstore_id,
        "other_store_id": other_store_id,
        "order_id": order_id,
        "customer_email": f"buyer-{suffix}@example.com",
    }


@pytest.mark.asyncio
async def test_projection_uses_canonical_records_and_hides_internal_fields():
    await ensure_indexes()
    ctx = await _seed_projection(uuid.uuid4().hex[:8])
    user = {
        "id": "staff-stage8b",
        "tenant_id": ctx["tenant_id"],
        "role": "owner",
        "email": "staff-stage8b@example.com",
    }

    result = await list_webstore_orders(user, ctx["webstore_id"])

    assert result["source_of_truth"] == "canonical_orders"
    assert result["total"] == 1
    order = result["items"][0]
    assert order["id"] == ctx["order_id"]
    assert order["customer"]["name"] == "Projection Buyer"
    assert order["customer"]["email"] == ctx["customer_email"]
    assert order["customer"]["phone"] == "555-0100"
    assert order["items"][0]["snapshot"]["selected_options"] == {"size": "Large"}
    assert "pricing_snapshot" not in order["items"][0]
    assert "estimated_cost_cents" not in order["items"][0]
    assert "stripe_payment_intent_id" not in order["payment"]
    assert "Legacy Order Must Not Appear" not in str(result)


@pytest.mark.asyncio
async def test_projection_enforces_tenant_and_assignment_scope():
    await ensure_indexes()
    ctx = await _seed_projection(uuid.uuid4().hex[:8])
    with pytest.raises(WebstoreError) as tenant_error:
        await list_webstore_orders(
            {"id": "other-tenant", "tenant_id": "tenant-other", "role": "owner"},
            ctx["webstore_id"],
        )
    assert tenant_error.value.status_code == 404

    with pytest.raises(WebstoreError) as assignment_error:
        await list_webstore_orders(
            {
                "id": "assigned-staff",
                "tenant_id": ctx["tenant_id"],
                "role": "staff",
                "webstore_id": ctx["other_store_id"],
            },
            ctx["webstore_id"],
        )
    assert assignment_error.value.status_code == 403

    with pytest.raises(WebstoreError) as permission_error:
        await list_webstore_orders(
            {"id": "unprivileged", "tenant_id": ctx["tenant_id"], "role": "unknown"},
            ctx["webstore_id"],
        )
    assert permission_error.value.status_code == 403

    assigned_user_id = f"assigned-db-{uuid.uuid4().hex[:8]}"
    await db.webstore_access_assignments.insert_one(
        {
            "id": f"assignment-{assigned_user_id}",
            "tenant_id": ctx["tenant_id"],
            "webstore_id": ctx["other_store_id"],
            "portal_identity_id": assigned_user_id,
            "email": f"assigned-{assigned_user_id}@example.com",
            "role": "manager",
            "status": "active",
        }
    )
    with pytest.raises(WebstoreError) as db_assignment_error:
        await list_webstore_orders(
            {
                "id": assigned_user_id,
                "tenant_id": ctx["tenant_id"],
                "role": "staff",
                "email": f"assigned-{assigned_user_id}@example.com",
            },
            ctx["webstore_id"],
        )
    assert db_assignment_error.value.status_code == 403
