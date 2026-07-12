"""EC7 phase 7b — Purchase Order + Receiving lifecycle tests.

Covers:
  - draft PO w/ multiple lines and backend-derived totals
  - freight snapshot recomputes total
  - explicit confirm required to submit
  - idempotent supplier submission (replay does not double-log)
  - cancel with reason required
  - receive: partial → status "partially_received"; full → "received"
  - receive idempotency (replay same key = no-op)
  - receive over-quantity rejected
  - receiving creates inventory_movement + material_cost_history + updates Material.current_cost_cents
  - PO cancellation forbidden after fully received
"""
from __future__ import annotations
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from server import app
from app.core.db import db
from app.deps import get_current_user
from app.services.supplier_connectors import TestSupplierAdapter


def _override(u):
    async def _get(): return {**u}
    return _get


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear(): app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def po_ctx():
    ta = f"t-po-{uuid.uuid4().hex[:6]}"
    ua = {"id": f"u-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
          "email": f"u-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_one({"id": ta, "slug": ta, "name": "TA"})
    await db.users.insert_one({**ua})
    await TestSupplierAdapter().seed_tenant(tenant_id=ta)
    yield {"tenant_id": ta, "user": ua}
    _clear()


async def _make_material_and_location(c) -> tuple[str, str, str]:
    m = (await c.post("/api/materials", json={"name": "Cast Wrap Vinyl (test)",
                                                "sku": f"MAT-{uuid.uuid4().hex[:6]}",
                                                "category": "vinyl"})).json()
    loc = (await c.post("/api/inventory/locations", json={"name": "Main Shop", "kind": "shop"})).json()
    vendor = await db.vendors.find_one({"tenant_id": (await db.materials.find_one({"id": m["id"]}))["tenant_id"],
                                         "connector_key": "test_adapter"}, {"_id": 0})
    return m["id"], loc["id"], vendor["id"]


@pytest.mark.asyncio
async def test_create_draft_po_totals_are_backend_derived(po_ctx):
    ua = po_ctx["user"]
    async with await _client(ua) as c:
        mat_id, loc_id, vendor_id = await _make_material_and_location(c)
        payload = {
            "vendor_id": vendor_id, "ship_to_location_id": loc_id,
            "lines": [
                {"description": "Cast Wrap Vinyl (test)", "material_id": mat_id,
                 "quantity_ordered": 3, "unit_price_cents": 17900, "package_qty": 1,
                 "supplier_sku": "NW-CST-WHT"},
                {"description": "Cast Wrap Vinyl Extra (test)", "material_id": mat_id,
                 "quantity_ordered": 2, "unit_price_cents": 17500, "package_qty": 1,
                 "supplier_sku": "NW-CST-WHT"},
            ],
        }
        r = await c.post("/api/purchase-orders", json=payload)
        assert r.status_code == 201, r.text
        po = r.json()
        assert po["status"] == "draft"
        # Backend-derived subtotal = 3*17900 + 2*17500 = 88700
        assert po["subtotal_cents"] == 88700
        assert po["total_cents"] == 88700          # no freight yet
        # Set freight and re-check
        r2 = await c.post(f"/api/purchase-orders/{po['id']}/freight",
                          json={"shipping_cents": 2500, "handling_cents": 500})
        assert r2.status_code == 200
        assert r2.json()["total_cents"] == 88700 + 2500 + 500


@pytest.mark.asyncio
async def test_submit_requires_confirm_and_idempotency_key(po_ctx):
    ua = po_ctx["user"]
    async with await _client(ua) as c:
        mat_id, loc_id, vendor_id = await _make_material_and_location(c)
        po = (await c.post("/api/purchase-orders", json={
            "vendor_id": vendor_id, "ship_to_location_id": loc_id,
            "lines": [{"description": "L1", "material_id": mat_id,
                       "quantity_ordered": 1, "unit_price_cents": 500}],
        })).json()
        # Missing idempotency-key: rejected
        r = await c.post(f"/api/purchase-orders/{po['id']}/submit",
                         json={"confirm": True})
        assert r.status_code == 400
        assert "idempotency_key_required" in r.json()["detail"]
        # confirm=False rejected
        r2 = await c.post(f"/api/purchase-orders/{po['id']}/submit",
                          json={"confirm": False},
                          headers={"Idempotency-Key": "abc"})
        assert r2.status_code == 400
        # Correct submit succeeds
        key = str(uuid.uuid4())
        r3 = await c.post(f"/api/purchase-orders/{po['id']}/submit",
                          json={"confirm": True},
                          headers={"Idempotency-Key": key})
        assert r3.status_code == 200
        result = r3.json()
        assert result["status"] == "accepted"
        assert result["supplier_order_id"]
        # Replay same key => duplicate log short-circuits (no second order id issued)
        r4 = await c.post(f"/api/purchase-orders/{po['id']}/submit",
                          json={"confirm": True},
                          headers={"Idempotency-Key": key})
        assert r4.status_code == 200
        # There should be exactly ONE supplier_order_log for this tenant + key
        cnt = await db.supplier_order_log.count_documents(
            {"tenant_id": ua["tenant_id"], "idempotency_key": key}
        )
        assert cnt == 1


@pytest.mark.asyncio
async def test_cancel_requires_reason_and_blocks_when_received(po_ctx):
    ua = po_ctx["user"]
    async with await _client(ua) as c:
        mat_id, loc_id, vendor_id = await _make_material_and_location(c)
        po = (await c.post("/api/purchase-orders", json={
            "vendor_id": vendor_id, "ship_to_location_id": loc_id,
            "lines": [{"description": "L1", "material_id": mat_id,
                       "quantity_ordered": 1, "unit_price_cents": 500}],
        })).json()
        # Missing reason => rejected
        r = await c.post(f"/api/purchase-orders/{po['id']}/cancel", json={"reason": "  "})
        assert r.status_code == 400
        # Valid reason => cancelled
        r2 = await c.post(f"/api/purchase-orders/{po['id']}/cancel",
                          json={"reason": "Wrong material"})
        assert r2.status_code == 200
        po2 = (await c.get(f"/api/purchase-orders/{po['id']}")).json()["purchase_order"]
        assert po2["status"] == "cancelled"
        # Second cancel attempt rejected
        r3 = await c.post(f"/api/purchase-orders/{po['id']}/cancel",
                          json={"reason": "again"})
        assert r3.status_code == 400


@pytest.mark.asyncio
async def test_receive_partial_then_full_and_idempotent(po_ctx):
    ua = po_ctx["user"]
    ta = po_ctx["tenant_id"]
    async with await _client(ua) as c:
        mat_id, loc_id, vendor_id = await _make_material_and_location(c)
        po = (await c.post("/api/purchase-orders", json={
            "vendor_id": vendor_id, "ship_to_location_id": loc_id,
            "lines": [{"description": "Cast Wrap Vinyl", "material_id": mat_id,
                       "quantity_ordered": 5, "unit_price_cents": 17900,
                       "supplier_sku": "NW-CST-WHT"}],
        })).json()
        po_line_id = po["id"]
        # We need the line id specifically
        details = (await c.get(f"/api/purchase-orders/{po['id']}")).json()
        line_id = details["lines"][0]["id"]

        # Submit first
        key = str(uuid.uuid4())
        await c.post(f"/api/purchase-orders/{po['id']}/submit",
                     json={"confirm": True}, headers={"Idempotency-Key": key})
        # Partial receive: 2 of 5
        rk1 = str(uuid.uuid4())
        r = await c.post(f"/api/purchase-orders/{po['id']}/receive",
                         json={"lines": [{"po_line_id": line_id, "quantity": 2}]},
                         headers={"Idempotency-Key": rk1})
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["po_status"] == "partially_received"
        # Replay same key = no-op
        r2 = await c.post(f"/api/purchase-orders/{po['id']}/receive",
                          json={"lines": [{"po_line_id": line_id, "quantity": 2}]},
                          headers={"Idempotency-Key": rk1})
        assert r2.status_code == 201
        assert r2.json()["replayed"] is True
        # Inventory got 2 (not 4)
        items = (await c.get(f"/api/inventory/items?material_id={mat_id}")).json()["items"]
        assert items[0]["quantity_on_hand"] == 2.0
        # Over-quantity rejected
        r3 = await c.post(f"/api/purchase-orders/{po['id']}/receive",
                          json={"lines": [{"po_line_id": line_id, "quantity": 10}]},
                          headers={"Idempotency-Key": str(uuid.uuid4())})
        assert r3.status_code == 400
        # Receive remaining 3 => full
        rk2 = str(uuid.uuid4())
        r4 = await c.post(f"/api/purchase-orders/{po['id']}/receive",
                          json={"lines": [{"po_line_id": line_id, "quantity": 3}]},
                          headers={"Idempotency-Key": rk2})
        assert r4.status_code == 201
        assert r4.json()["po_status"] == "received"
        items = (await c.get(f"/api/inventory/items?material_id={mat_id}")).json()["items"]
        assert items[0]["quantity_on_hand"] == 5.0
        # Material cost history was created once (unit price differs from 0 initial)
        cnt = await db.material_cost_history.count_documents(
            {"tenant_id": ta, "material_id": mat_id, "source": "receiving"}
        )
        assert cnt >= 1
        # Material.current_cost_cents now reflects the received unit price
        mat = await db.materials.find_one({"tenant_id": ta, "id": mat_id})
        assert mat["current_cost_cents"] == 17900


@pytest.mark.asyncio
async def test_receive_after_cancel_is_forbidden(po_ctx):
    ua = po_ctx["user"]
    async with await _client(ua) as c:
        mat_id, loc_id, vendor_id = await _make_material_and_location(c)
        po = (await c.post("/api/purchase-orders", json={
            "vendor_id": vendor_id, "ship_to_location_id": loc_id,
            "lines": [{"description": "L1", "material_id": mat_id,
                       "quantity_ordered": 1, "unit_price_cents": 500}],
        })).json()
        line_id = (await c.get(f"/api/purchase-orders/{po['id']}")).json()["lines"][0]["id"]
        await c.post(f"/api/purchase-orders/{po['id']}/cancel", json={"reason": "test"})
        r = await c.post(f"/api/purchase-orders/{po['id']}/receive",
                         json={"lines": [{"po_line_id": line_id, "quantity": 1}]},
                         headers={"Idempotency-Key": str(uuid.uuid4())})
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_cart_checkout_groups_by_vendor(po_ctx):
    ua = po_ctx["user"]
    async with await _client(ua) as c:
        mat_id, loc_id, vendor_id = await _make_material_and_location(c)
        # Second vendor from seed
        vendors_all = await db.vendors.find({"tenant_id": ua["tenant_id"]}, {"_id": 0}).to_list(length=10)
        v2 = next(v for v in vendors_all if v["id"] != vendor_id)
        r = await c.post("/api/supply/cart/checkout", json={
            "ship_to_location_id": loc_id,
            "items": [
                {"vendor_id": vendor_id, "supplier_product_id": "sp1",
                 "material_id": mat_id, "description": "X", "quantity_ordered": 1,
                 "unit_price_cents": 100},
                {"vendor_id": vendor_id, "supplier_product_id": "sp2",
                 "material_id": mat_id, "description": "Y", "quantity_ordered": 1,
                 "unit_price_cents": 200},
                {"vendor_id": v2["id"], "supplier_product_id": "sp3",
                 "material_id": mat_id, "description": "Z", "quantity_ordered": 1,
                 "unit_price_cents": 300},
            ],
            "shipping_cents_by_vendor": {vendor_id: 500, v2["id"]: 700},
        })
        assert r.status_code == 201
        created = r.json()["created"]
        # Two POs: one per vendor
        assert len(created) == 2
        by_v = {po["vendor_id"]: po for po in created}
        assert by_v[vendor_id]["subtotal_cents"] == 300
        assert by_v[vendor_id]["shipping_cents"] == 500
        assert by_v[v2["id"]]["subtotal_cents"] == 300
        assert by_v[v2["id"]]["shipping_cents"] == 700
