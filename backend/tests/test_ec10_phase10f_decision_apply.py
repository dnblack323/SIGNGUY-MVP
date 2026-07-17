"""EC10 Phase 10F - staff-controlled Decision Room apply path."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.portal_security import create_portal_token
from app.deps import get_current_user
from server import app


def _override(u):
    async def _get():
        return {**u}
    return _get


async def _staff_client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _anon_client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-ec10f-{suffix}"
    owner = {"id": f"u-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    customer = {"id": f"cust-{suffix}", "tenant_id": tenant_id, "name": "Decision Customer", "archived": False}
    order = {"id": f"order-{suffix}", "tenant_id": tenant_id, "number": 1, "customer_id": customer["id"], "job_name": "Decision job", "status": "draft"}
    order_item = {
        "id": f"oi-{suffix}", "tenant_id": tenant_id, "order_id": order["id"], "position": 0,
        "description": "Original option", "quantity": 1, "unit_price_cents": 10000,
        "discount_cents": 0, "tax_cents": 0, "line_subtotal_cents": 10000, "line_total_cents": 10000,
    }
    portal_identity = {
        "id": f"pi-{suffix}", "tenant_id": tenant_id, "portal_type": "customer", "customer_id": customer["id"],
        "email": f"customer-{suffix}@example.com", "status": "active",
        "permissions": ["portal:view_decision_rooms", "portal:respond_decision_rooms"], "permissions_preset": "custom",
    }
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "Tenant"})
    await db.users.insert_one(owner)
    await db.customers.insert_one(customer)
    await db.orders.insert_one(order)
    await db.order_items.insert_one(order_item)
    await db.portal_identities.insert_one(portal_identity)
    token = create_portal_token(portal_identity_id=portal_identity["id"], tenant_id=tenant_id, customer_id=customer["id"], portal_type="customer")
    yield {"tenant_id": tenant_id, "owner": owner, "customer": customer, "order": order, "order_item": order_item, "portal_token": token}
    _clear()


async def _published_room(ctx):
    async with await _staff_client(ctx["owner"]) as c:
        room = (await c.post("/api/decision-rooms", json={
            "title": "Decision apply room", "customer_id": ctx["customer"]["id"],
            "order_id": ctx["order"]["id"], "order_item_id": ctx["order_item"]["id"],
        })).json()
        rid = room["id"]
        opt_a = (await c.post(f"/api/decision-rooms/{rid}/options", json={
            "customer_label": "Standard", "manual_price_cents": 25000,
            "order_item_id": ctx["order_item"]["id"],
        })).json()["options"][0]["id"]
        opt_b = next(o["id"] for o in (await c.post(f"/api/decision-rooms/{rid}/options", json={
            "customer_label": "Premium", "manual_price_cents": 45000,
            "order_item_id": ctx["order_item"]["id"],
        })).json()["options"] if o["customer_label"] == "Premium")
        assert (await c.post(f"/api/decision-rooms/{rid}/transition", json={"target": "ready"})).status_code == 200
        assert (await c.post(f"/api/decision-rooms/{rid}/publish")).status_code == 200
    return rid, opt_a, opt_b


async def _select(ctx, room_id, option_id, key):
    _clear()
    async with await _anon_client() as c:
        c.headers["Authorization"] = f"Bearer {ctx['portal_token']}"
        resp = await c.post(f"/api/portal/decision-rooms/{room_id}/decisions", json={
            "action_type": "option_selected", "option_id": option_id, "idempotency_key": key,
        })
        assert resp.status_code == 201, resp.text
        return resp.json()


@pytest.mark.asyncio
async def test_staff_apply_is_only_path_that_mutates_order_item(ctx):
    rid, opt_a, _opt_b = await _published_room(ctx)
    before = await db.order_items.find_one({"id": ctx["order_item"]["id"]}, {"_id": 0})
    decision = await _select(ctx, rid, opt_a, "apply-one")
    after_customer = await db.order_items.find_one({"id": ctx["order_item"]["id"]}, {"_id": 0})
    assert after_customer == before

    async with await _staff_client(ctx["owner"]) as c:
        applied = await c.post(f"/api/decision-rooms/{rid}/decisions/{decision['id']}/apply", json={"note": "Staff accepted"})
        assert applied.status_code == 200, applied.text
        body = applied.json()
        assert body["internal_review_status"] == "applied"
        assert body["applied_target_type"] == "order_item"
        assert body["applied_target_id"] == ctx["order_item"]["id"]

        second = await c.post(f"/api/decision-rooms/{rid}/decisions/{decision['id']}/apply", json={"note": "retry"})
        assert second.status_code == 200
        assert second.json()["applied_pricing_snapshot_record_id"] == body["applied_pricing_snapshot_record_id"]

    item = await db.order_items.find_one({"id": ctx["order_item"]["id"]}, {"_id": 0})
    assert item["unit_price_cents"] == 25000
    assert item["line_total_cents"] == 25000
    snapshots = [s async for s in db.pricing_snapshot_records.find({"tenant_id": ctx["tenant_id"], "source_id": ctx["order_item"]["id"]}, {"_id": 0})]
    assert len(snapshots) == 1


@pytest.mark.asyncio
async def test_superseded_selection_cannot_be_applied(ctx):
    rid, opt_a, opt_b = await _published_room(ctx)
    first = await _select(ctx, rid, opt_a, "sel-a")
    second = await _select(ctx, rid, opt_b, "sel-b")
    assert second["supersedes_decision_id"] == first["id"]

    async with await _staff_client(ctx["owner"]) as c:
        old = await c.post(f"/api/decision-rooms/{rid}/decisions/{first['id']}/apply", json={"note": "too late"})
        assert old.status_code == 409
        ok = await c.post(f"/api/decision-rooms/{rid}/decisions/{second['id']}/apply", json={"note": "latest"})
        assert ok.status_code == 200

    item = await db.order_items.find_one({"id": ctx["order_item"]["id"]}, {"_id": 0})
    assert item["unit_price_cents"] == 45000
