"""EC3 — Orders / Order Items / production_required / financial-status rejection."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from server import app
from app.core.db import db as _db
from app.deps import get_current_user


def _override_as(user: dict):
    async def _dep():
        return user
    return _dep


async def _seed_customer(tenant_id: str) -> str:
    cust_id = f"cust-{uuid.uuid4().hex[:8]}"
    await _db.customers.insert_one({
        "id": cust_id, "tenant_id": tenant_id, "name": "T", "email": "t@example.com",
    })
    return cust_id


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override_as(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_order_item_totals_backend_derived(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        r = await c.post("/api/orders", json={"customer_id": cust, "job_name": "O"})
        oid = r.json()["id"]
        r = await c.post(f"/api/orders/{oid}/items", json={
            "description": "Banner", "quantity": 3, "unit_price_cents": 1500,
            "category": "banners",
        })
        assert r.status_code == 201
        r = await c.get(f"/api/orders/{oid}")
        body = r.json()
        assert body["items"][0]["line_total_cents"] == 4500
        assert body["items"][0]["production_required"] is True
        assert body["order"]["total_cents"] == 4500
        assert body["totals"]["item_count"] == 1
    _clear()


@pytest.mark.asyncio
async def test_order_item_production_required_defaults_by_category(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        r = await c.post("/api/orders", json={"customer_id": cust, "job_name": "Mixed"})
        oid = r.json()["id"]
        r = await c.post(f"/api/orders/{oid}/items", json={
            "description": "Design consulting", "quantity": 1, "unit_price_cents": 5000,
            "category": "services",
        })
        assert r.json()["production_required"] is False

        r = await c.post(f"/api/orders/{oid}/items", json={
            "description": "Rigid Sign", "quantity": 1, "unit_price_cents": 5000,
            "category": "rigid_signs",
        })
        assert r.json()["production_required"] is True
    _clear()


@pytest.mark.asyncio
async def test_manual_price_override_requires_reason(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        r = await c.post("/api/orders", json={"customer_id": cust, "job_name": "X"})
        oid = r.json()["id"]
        r = await c.post(f"/api/orders/{oid}/items", json={
            "description": "Banner", "quantity": 1, "unit_price_cents": 1000, "category": "banners",
        })
        item_id = r.json()["id"]
        # Attempt price change without reason
        r = await c.patch(f"/api/orders/{oid}/items/{item_id}", json={"unit_price_cents": 2000})
        assert r.status_code == 400
        assert "override" in r.json()["detail"].lower()
        # With reason
        r = await c.patch(f"/api/orders/{oid}/items/{item_id}", json={
            "unit_price_cents": 2000, "manual_override_reason": "customer discount",
        })
        assert r.status_code == 200
        assert r.json()["unit_price_cents"] == 2000
        assert r.json()["manual_override_reason"] == "customer discount"
    _clear()


@pytest.mark.asyncio
async def test_financial_status_rejected_on_order(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        r = await c.post("/api/orders", json={"customer_id": cust, "job_name": "Y"})
        oid = r.json()["id"]
        r = await c.post(f"/api/orders/{oid}/status", json={"status": "paid"})
        assert r.status_code == 422 or r.status_code == 400  # pydantic literal enforces
    _clear()


@pytest.mark.asyncio
async def test_invalid_status_transition_rejected(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        r = await c.post("/api/orders", json={"customer_id": cust, "job_name": "Z"})
        oid = r.json()["id"]
        r = await c.post(f"/api/orders/{oid}/status", json={"status": "completed"})
        assert r.status_code == 400
        assert "invalid transition" in r.json()["detail"].lower()
    _clear()


@pytest.mark.asyncio
async def test_production_required_override_requires_reason(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        r = await c.post("/api/orders", json={"customer_id": cust, "job_name": "R"})
        oid = r.json()["id"]
        r = await c.post(f"/api/orders/{oid}/items", json={
            "description": "Rigid", "quantity": 1, "unit_price_cents": 1000,
            "category": "rigid_signs",
        })
        item_id = r.json()["id"]
        r = await c.patch(f"/api/orders/{oid}/items/{item_id}", json={"production_required": False})
        assert r.status_code == 400
        r = await c.patch(f"/api/orders/{oid}/items/{item_id}", json={
            "production_required": False,
            "production_required_override_reason": "outsourced",
        })
        assert r.status_code == 200
        assert r.json()["production_required"] is False
    _clear()


@pytest.mark.asyncio
async def test_work_order_only_snaps_production_items(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        r = await c.post("/api/orders", json={"customer_id": cust, "job_name": "W"})
        oid = r.json()["id"]
        await c.post(f"/api/orders/{oid}/items", json={
            "description": "Banner", "quantity": 1, "unit_price_cents": 1000, "category": "banners",
        })
        await c.post(f"/api/orders/{oid}/items", json={
            "description": "Design consult", "quantity": 1, "unit_price_cents": 5000, "category": "services",
        })
        r = await c.post("/api/work-orders", json={"order_id": oid})
        assert r.status_code == 201
        snap = r.json()["items_snapshot"]
        assert len(snap) == 1
        assert snap[0]["description"] == "Banner"
        assert snap[0]["production_required"] is True
    _clear()
