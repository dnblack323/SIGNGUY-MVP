"""Focused Stage 8A verified-payment to canonical Order bridge tests."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db, ensure_indexes
from app.deps import get_current_user
from app.services import webstore_payments
from app.services.webstore_payments import complete_verified_payment_handoff
from app.services.webstores import WebstoreError
from server import app


async def _seed_handoff(suffix: str) -> dict[str, str]:
    tenant_id = f"tenant-stage8a-{suffix}"
    webstore_id = f"webstore-stage8a-{suffix}"
    intent_id = f"intent-stage8a-{suffix}"
    event_id = f"event-stage8a-{suffix}"
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "Stage 8A Shop"})
    await db.webstores.insert_one(
        {
            "id": webstore_id,
            "tenant_id": tenant_id,
            "name": "Stage 8A Webstore",
            "public_slug": webstore_id,
            "status": "live",
        }
    )
    await db.webstore_purchase_intents.insert_one(
        {
            "id": intent_id,
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "public_slug": webstore_id,
            "buyer_name": "Stage 8A Buyer",
            "buyer_email": f"buyer-{suffix}@example.com",
            "line_items": [
                {
                    "product_id": "product-shirt",
                    "variant_id": "variant-large",
                    "name": "Team Shirt",
                    "quantity": 2,
                    "unit_price_cents": 1500,
                    "line_total_cents": 3000,
                    "selected_options": {"size": "Large"},
                    "production_mapping": {"method": "screen_print"},
                }
            ],
            "product_subtotal_cents": 3000,
            "total_cents": 3000,
            "currency": "usd",
            "status": "payment_verified",
            "provider": "test-fixture",
            "provider_mode": "test",
            "provider_payment_id": f"pi-stage8a-{suffix}",
            "provider_account_reference": "acct-stage8a",
            "verified_payment_event_id": event_id,
            "reconciliation_state": "verified_pending_stage8",
            "processing_state": "verified",
            "production_bridge_status": "not_started",
            "immutable_snapshot": {"financial_lines": []},
        }
    )
    await db.webstore_payment_events.insert_one(
        {
            "id": event_id,
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "purchase_intent_id": intent_id,
            "provider": "test-fixture",
            "provider_event_id": f"evt-stage8a-{suffix}",
            "provider_payment_id": f"pi-stage8a-{suffix}",
            "provider_mode": "test",
            "provider_account_reference": "acct-stage8a",
            "amount_cents": 3000,
            "currency": "usd",
            "status": "processed",
            "reconciliation_state": "verified_pending_stage8",
            "processing_state": "verified",
        }
    )
    return {"tenant_id": tenant_id, "webstore_id": webstore_id, "intent_id": intent_id, "event_id": event_id}


@pytest.mark.asyncio
async def test_verified_handoff_is_idempotent_and_preserves_checkout_snapshot():
    await ensure_indexes()
    ctx = await _seed_handoff(uuid.uuid4().hex[:8])

    first = await complete_verified_payment_handoff(
        tenant_id=ctx["tenant_id"],
        webstore_id=ctx["webstore_id"],
        purchase_intent_id=ctx["intent_id"],
        actor_user_id="staff-stage8a",
        actor_email="staff-stage8a@example.com",
    )
    replay = await complete_verified_payment_handoff(
        tenant_id=ctx["tenant_id"],
        webstore_id=ctx["webstore_id"],
        purchase_intent_id=ctx["intent_id"],
        actor_user_id="staff-stage8a",
        actor_email="staff-stage8a@example.com",
    )

    assert first["handoff_status"] == "completed"
    assert first["order"]["source_type"] == "webstore_purchase_intent"
    assert first["items"][0]["description"] == "Team Shirt"
    assert first["items"][0]["pricing_snapshot"]["line_item"]["selected_options"] == {"size": "Large"}
    assert replay["already_processed"] is True
    assert replay["order"]["id"] == first["order"]["id"]
    assert await db.orders.count_documents({"tenant_id": ctx["tenant_id"]}) == 1
    assert await db.order_items.count_documents({"tenant_id": ctx["tenant_id"]}) == 1
    assert await db.payments.count_documents({"tenant_id": ctx["tenant_id"]}) == 1
    assert await db.work_orders.count_documents({"tenant_id": ctx["tenant_id"]}) == 0

    intent = await db.webstore_purchase_intents.find_one({"id": ctx["intent_id"]}, {"_id": 0})
    event = await db.webstore_payment_events.find_one({"id": ctx["event_id"]}, {"_id": 0})
    assert intent["status"] == "paid_order_created"
    assert intent["canonical_order_id"] == first["order"]["id"]
    assert intent["canonical_payment_id"] == first["payment"]["id"]
    assert intent["fulfillment_status"] == "awaiting_production_handoff"
    assert event["reconciliation_state"] == "canonical_records_created"
    assert event["processing_state"] == "completed"


@pytest.mark.asyncio
async def test_verified_handoff_recovers_after_order_created_before_payment(monkeypatch: pytest.MonkeyPatch):
    await ensure_indexes()
    ctx = await _seed_handoff(uuid.uuid4().hex[:8])
    original_create_payment = webstore_payments._create_payment
    failed = {"value": False}

    async def fail_once(*args, **kwargs):
        if not failed["value"]:
            failed["value"] = True
            raise RuntimeError("simulated payment write failure")
        return await original_create_payment(*args, **kwargs)

    monkeypatch.setattr(webstore_payments, "_create_payment", fail_once)
    with pytest.raises(RuntimeError):
        await complete_verified_payment_handoff(
            tenant_id=ctx["tenant_id"],
            webstore_id=ctx["webstore_id"],
            purchase_intent_id=ctx["intent_id"],
            actor_user_id="staff-stage8a",
            actor_email="staff-stage8a@example.com",
        )

    interrupted_intent = await db.webstore_purchase_intents.find_one({"id": ctx["intent_id"]}, {"_id": 0})
    assert interrupted_intent["status"] == "handoff_processing"
    assert interrupted_intent["recovery_state"] == "handoff_retry_required"
    assert await db.orders.count_documents({"tenant_id": ctx["tenant_id"]}) == 1
    assert await db.payments.count_documents({"tenant_id": ctx["tenant_id"]}) == 0

    monkeypatch.setattr(webstore_payments, "_create_payment", original_create_payment)
    recovered = await complete_verified_payment_handoff(
        tenant_id=ctx["tenant_id"],
        webstore_id=ctx["webstore_id"],
        purchase_intent_id=ctx["intent_id"],
        actor_user_id="staff-stage8a",
        actor_email="staff-stage8a@example.com",
    )
    assert recovered["handoff_status"] == "completed"
    assert await db.orders.count_documents({"tenant_id": ctx["tenant_id"]}) == 1
    assert await db.payments.count_documents({"tenant_id": ctx["tenant_id"]}) == 1


@pytest.mark.asyncio
async def test_handoff_route_enforces_staff_permission_and_store_scope():
    await ensure_indexes()
    ctx = await _seed_handoff(uuid.uuid4().hex[:8])
    staff = {
        "id": "staff-stage8a-route",
        "tenant_id": ctx["tenant_id"],
        "email": "route-staff-stage8a@example.com",
        "role": "owner",
        "is_active": True,
    }

    async def current_user():
        return staff

    app.dependency_overrides[get_current_user] = current_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/webstores/{ctx['webstore_id']}/orders/handoff",
                json={"purchase_intent_id": ctx["intent_id"]},
            )
            assert response.status_code == 200, response.text

            forbidden_staff = {**staff, "role": "employee"}

            async def forbidden_user():
                return forbidden_staff

            app.dependency_overrides[get_current_user] = forbidden_user
            forbidden = await client.post(
                f"/api/webstores/{ctx['webstore_id']}/orders/handoff",
                json={"purchase_intent_id": ctx["intent_id"]},
            )
            assert forbidden.status_code == 403

            app.dependency_overrides[get_current_user] = current_user
            wrong_store = await client.post(
                f"/api/webstores/{ctx['webstore_id']}-other/orders/handoff",
                json={"purchase_intent_id": ctx["intent_id"]},
            )
            assert wrong_store.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)
