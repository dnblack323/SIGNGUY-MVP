"""Focused Stage 8C Webstore-to-Work-Order handoff tests."""
from __future__ import annotations

import asyncio
import uuid

import pytest

from app.core.db import db, ensure_indexes
from app.services.webstore_production import handoff_webstore_order_to_production
from app.services.webstores import WebstoreError
from backend.tests.test_webstores_stage8b_orders_projection import _seed_projection


@pytest.mark.asyncio
async def test_paid_webstore_order_handoff_is_idempotent_and_preserves_snapshot():
    await ensure_indexes()
    ctx = await _seed_projection(uuid.uuid4().hex[:8])
    user = {
        "id": "stage8c-staff",
        "tenant_id": ctx["tenant_id"],
        "role": "owner",
        "email": "stage8c@example.com",
    }

    first, second = await asyncio.gather(
        handoff_webstore_order_to_production(user, ctx["webstore_id"], ctx["order_id"]),
        handoff_webstore_order_to_production(user, ctx["webstore_id"], ctx["order_id"]),
    )

    assert first["work_order"]["order_id"] == ctx["order_id"]
    assert second["work_order"]["order_id"] == ctx["order_id"]
    assert await db.work_orders.count_documents({"tenant_id": ctx["tenant_id"], "order_id": ctx["order_id"], "current_version": True}) == 1
    work_order = await db.work_orders.find_one({"tenant_id": ctx["tenant_id"], "order_id": ctx["order_id"], "current_version": True}, {"_id": 0})
    assert work_order["items_snapshot"][0]["description"] == "Projection Shirt"

    await db.order_items.update_one(
        {"tenant_id": ctx["tenant_id"], "order_id": ctx["order_id"]},
        {"$set": {"description": "Edited after payment"}},
    )
    unchanged_work_order = await db.work_orders.find_one({"id": work_order["id"]}, {"_id": 0})
    assert unchanged_work_order["items_snapshot"][0]["description"] == "Projection Shirt"
    intent = await db.webstore_purchase_intents.find_one({"canonical_order_id": ctx["order_id"]}, {"_id": 0})
    assert intent["production_bridge_status"] == "bridged"
    assert intent["fulfillment_status"] == "in_production"
    assert intent["work_order_id"] == work_order["id"]


@pytest.mark.asyncio
async def test_production_handoff_requires_paid_order_and_store_scope():
    await ensure_indexes()
    ctx = await _seed_projection(uuid.uuid4().hex[:8])
    user = {"id": "stage8c-staff", "tenant_id": ctx["tenant_id"], "role": "owner"}

    with pytest.raises(WebstoreError) as wrong_store:
        await handoff_webstore_order_to_production(user, ctx["other_store_id"], ctx["order_id"])
    assert wrong_store.value.status_code == 404

    await db.webstore_purchase_intents.update_one(
        {"canonical_order_id": ctx["order_id"]},
        {"$set": {"status": "payment_processing"}},
    )
    with pytest.raises(WebstoreError) as unpaid:
        await handoff_webstore_order_to_production(user, ctx["webstore_id"], ctx["order_id"])
    assert unpaid.value.status_code == 409
