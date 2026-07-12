"""EC7 phase 7a — Inventory foundation tests."""
from __future__ import annotations
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from server import app
from app.core.db import db
from app.deps import get_current_user
from app.services import inventory_service
from app.services.unit_conversion import convert_quantity


def _override(u):
    async def _get(): return {**u}
    return _get


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear(): app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def ec7_ctx():
    ta = f"t-ec7-{uuid.uuid4().hex[:6]}"
    tb = f"t-ec7b-{uuid.uuid4().hex[:6]}"
    ua = {"id": f"u-a-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
          "email": f"a-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    ub = {"id": f"u-b-{uuid.uuid4().hex[:6]}", "tenant_id": tb,
          "email": f"b-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([{"id": ta, "slug": ta, "name": "TA"}, {"id": tb, "slug": tb, "name": "TB"}])
    await db.users.insert_many([{**ua}, {**ub}])
    yield {"ua": ua, "ub": ub, "ta": ta, "tb": tb}
    _clear()


@pytest.mark.asyncio
async def test_material_crud_tenant_isolation(ec7_ctx):
    ua, ub = ec7_ctx["ua"], ec7_ctx["ub"]
    async with await _client(ua) as c:
        r = await c.post("/api/materials", json={"name": "3M IJ180", "category": "vinyl",
                                                  "current_cost_cents": 12500, "purchase_unit": "roll",
                                                  "unit_of_measure": "square_foot",
                                                  "roll_width_inches": 54, "roll_length_feet": 150})
        assert r.status_code == 201
        mid = r.json()["id"]
    _clear()
    # Tenant B cannot see A's material
    async with await _client(ub) as c:
        r2 = await c.get(f"/api/materials/{mid}")
        assert r2.status_code == 404
    _clear()


@pytest.mark.asyncio
async def test_receive_adjust_and_immutable_movements(ec7_ctx):
    ua = ec7_ctx["ua"]; ta = ec7_ctx["ta"]
    async with await _client(ua) as c:
        m = await c.post("/api/materials", json={"name": "Orafol 3164G", "category": "vinyl",
                                                  "current_cost_cents": 8900,
                                                  "purchase_unit": "roll", "unit_of_measure": "square_foot"})
        mid = m.json()["id"]
        loc = await c.post("/api/inventory/locations", json={"name": "Main Shop", "kind": "shop"})
        lid = loc.json()["id"]
        # Receive 5 units
        r = await c.post("/api/inventory/adjustments/increase",
                         json={"material_id": mid, "location_id": lid, "quantity": 5, "reason": "receive"})
        assert r.status_code == 201
        assert r.json()["after_quantity"] == 5.0
        # List items
        items = (await c.get(f"/api/inventory/items?material_id={mid}")).json()["items"]
        assert items[0]["quantity_on_hand"] == 5.0
        # Decrease 2
        d = await c.post("/api/inventory/adjustments/decrease",
                         json={"material_id": mid, "location_id": lid, "quantity": 2, "reason": "waste"})
        assert d.status_code == 201
        # Movements are immutable ledger
        mv = (await c.get(f"/api/inventory/movements?material_id={mid}")).json()["items"]
        assert len(mv) == 2
    _clear()


@pytest.mark.asyncio
async def test_negative_stock_rejected(ec7_ctx):
    ua = ec7_ctx["ua"]
    async with await _client(ua) as c:
        m = await c.post("/api/materials", json={"name": "M", "category": "other"})
        mid = m.json()["id"]
        loc = await c.post("/api/inventory/locations", json={"name": "Loc"})
        lid = loc.json()["id"]
        r = await c.post("/api/inventory/adjustments/decrease",
                         json={"material_id": mid, "location_id": lid, "quantity": 3})
        assert r.status_code == 400
        assert "negative_stock" in r.json()["detail"]
    _clear()


@pytest.mark.asyncio
async def test_idempotent_receive(ec7_ctx):
    ua = ec7_ctx["ua"]
    async with await _client(ua) as c:
        m = await c.post("/api/materials", json={"name": "M", "category": "other"})
        mid = m.json()["id"]
        loc = await c.post("/api/inventory/locations", json={"name": "L"})
        lid = loc.json()["id"]
        key = str(uuid.uuid4())
        r1 = await c.post("/api/inventory/adjustments/increase",
                          json={"material_id": mid, "location_id": lid, "quantity": 10},
                          headers={"Idempotency-Key": key})
        r2 = await c.post("/api/inventory/adjustments/increase",
                          json={"material_id": mid, "location_id": lid, "quantity": 10},
                          headers={"Idempotency-Key": key})
        assert r1.status_code == 201 and r2.status_code == 201
        # Same movement id returned; balance not doubled
        items = (await c.get(f"/api/inventory/items?material_id={mid}")).json()["items"]
        assert items[0]["quantity_on_hand"] == 10.0
    _clear()


@pytest.mark.asyncio
async def test_reservation_and_release(ec7_ctx):
    ua = ec7_ctx["ua"]; ta = ec7_ctx["ta"]
    async with await _client(ua) as c:
        m = await c.post("/api/materials", json={"name": "M", "category": "other"})
        mid = m.json()["id"]
        loc = await c.post("/api/inventory/locations", json={"name": "L"})
        lid = loc.json()["id"]
        await c.post("/api/inventory/adjustments/increase",
                     json={"material_id": mid, "location_id": lid, "quantity": 20})
        r = await c.post("/api/inventory/reservations",
                         json={"material_id": mid, "location_id": lid, "quantity": 5,
                               "source_entity_type": "order", "source_entity_id": "o1"})
        assert r.status_code == 201
        rid = r.json()["id"]
        items = (await c.get(f"/api/inventory/items?material_id={mid}")).json()["items"]
        assert items[0]["quantity_reserved"] == 5.0
        assert items[0]["quantity_available"] == 15.0
        # Over-reserve is rejected
        r2 = await c.post("/api/inventory/reservations",
                          json={"material_id": mid, "location_id": lid, "quantity": 100,
                                "source_entity_type": "order", "source_entity_id": "o2"})
        assert r2.status_code == 400
        # Release
        await c.delete(f"/api/inventory/reservations/{rid}")
        items = (await c.get(f"/api/inventory/items?material_id={mid}")).json()["items"]
        assert items[0]["quantity_reserved"] == 0.0
    _clear()


@pytest.mark.asyncio
async def test_physical_count_records_expected_and_observed(ec7_ctx):
    ua = ec7_ctx["ua"]
    async with await _client(ua) as c:
        m = await c.post("/api/materials", json={"name": "M", "category": "other"})
        mid = m.json()["id"]
        loc = await c.post("/api/inventory/locations", json={"name": "L"})
        lid = loc.json()["id"]
        await c.post("/api/inventory/adjustments/increase",
                     json={"material_id": mid, "location_id": lid, "quantity": 10})
        r = await c.post("/api/inventory/adjustments/count",
                         json={"material_id": mid, "location_id": lid, "observed_quantity": 7,
                               "reason": "quarterly count"})
        assert r.status_code == 201
        body = r.json()
        assert body["expected_quantity"] == 10.0
        assert body["observed_quantity"] == 7.0
        assert body["after_quantity"] == 7.0
        assert body["movement_type"] == "count_adjustment"
    _clear()


@pytest.mark.asyncio
async def test_transfer_between_locations(ec7_ctx):
    ua = ec7_ctx["ua"]
    async with await _client(ua) as c:
        m = await c.post("/api/materials", json={"name": "M", "category": "other"})
        mid = m.json()["id"]
        l1 = (await c.post("/api/inventory/locations", json={"name": "Shop"})).json()["id"]
        l2 = (await c.post("/api/inventory/locations", json={"name": "Vehicle", "kind": "vehicle"})).json()["id"]
        await c.post("/api/inventory/adjustments/increase",
                     json={"material_id": mid, "location_id": l1, "quantity": 10})
        r = await c.post("/api/inventory/transfers",
                         json={"material_id": mid, "from_location_id": l1, "to_location_id": l2, "quantity": 4})
        assert r.status_code == 201
        items = (await c.get(f"/api/inventory/items?material_id={mid}")).json()["items"]
        by_loc = {i["location_id"]: i["quantity_on_hand"] for i in items}
        assert by_loc[l1] == 6.0 and by_loc[l2] == 4.0
    _clear()


@pytest.mark.asyncio
async def test_low_stock_reporting(ec7_ctx):
    ua = ec7_ctx["ua"]
    async with await _client(ua) as c:
        m = await c.post("/api/materials", json={"name": "M", "category": "other", "reorder_point": 5})
        mid = m.json()["id"]
        loc = (await c.post("/api/inventory/locations", json={"name": "L"})).json()["id"]
        await c.post("/api/inventory/adjustments/increase",
                     json={"material_id": mid, "location_id": loc, "quantity": 4})
        r = await c.get("/api/inventory/items?low_stock=true")
        assert r.status_code == 200
        low = r.json()["items"]
        assert any(x["material_id"] == mid for x in low)
    _clear()


def test_unit_conversion_length():
    assert convert_quantity(quantity=1, from_unit="linear_foot", to_unit="linear_inch") == 12.0
    assert convert_quantity(quantity=144, from_unit="square_inch", to_unit="square_foot") == 1.0


def test_unit_conversion_roll_to_square_foot():
    r = convert_quantity(quantity=1, from_unit="roll", to_unit="square_foot",
                         material_meta={"roll_length_feet": 150, "roll_width_inches": 54})
    assert round(r, 2) == round(150 * 54 / 12.0, 2)


def test_unit_conversion_unsupported_rejects():
    with pytest.raises(ValueError):
        convert_quantity(quantity=1, from_unit="gallon", to_unit="each")
