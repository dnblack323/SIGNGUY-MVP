"""EC5 — Work Order generation, transitions, versioning, summary, tenant isolation."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from server import app
from app.core.db import db as _db
from app.deps import get_current_user


def _override(u):
    async def _dep(): return u
    return _dep


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


async def _seed_order(tenant_id: str, with_prod=True, with_non_prod=False) -> str:
    cust_id = f"cust-{uuid.uuid4().hex[:6]}"
    order_id = f"ord-{uuid.uuid4().hex[:6]}"
    await _db.customers.insert_one({"id": cust_id, "tenant_id": tenant_id, "name": "T", "email": "t@x.com"})
    await _db.orders.insert_one({"id": order_id, "tenant_id": tenant_id, "customer_id": cust_id,
                                 "number": 1, "job_name": "J", "status": "confirmed", "created_by": "u"})
    if with_prod:
        await _db.order_items.insert_one({
            "id": f"oi-{uuid.uuid4().hex[:6]}", "tenant_id": tenant_id, "order_id": order_id,
            "description": "Banner 3x6", "quantity": 2, "unit_price_cents": 5000,
            "category": "banners", "production_required": True, "position": 0,
        })
    if with_non_prod:
        await _db.order_items.insert_one({
            "id": f"oi-{uuid.uuid4().hex[:6]}", "tenant_id": tenant_id, "order_id": order_id,
            "description": "Design consulting", "quantity": 1, "unit_price_cents": 5000,
            "category": "services", "production_required": False, "position": 1,
        })
    return order_id


@pytest.mark.asyncio
async def test_generate_only_production_items(seeded_users):
    u = seeded_users["user_a"]
    oid = await _seed_order(u["tenant_id"], with_prod=True, with_non_prod=True)
    async with await _client(u) as c:
        r = await c.post("/api/work-orders", json={"order_id": oid, "priority": "high"})
        assert r.status_code == 201
        wo = r.json()
        assert len(wo["items_snapshot"]) == 1
        assert wo["items_snapshot"][0]["description"] == "Banner 3x6"
        assert wo["priority"] == "high"
        assert wo["current_version"] is True
    _clear()


@pytest.mark.asyncio
async def test_no_production_items_rejected(seeded_users):
    u = seeded_users["user_a"]
    oid = await _seed_order(u["tenant_id"], with_prod=False, with_non_prod=True)
    async with await _client(u) as c:
        r = await c.post("/api/work-orders", json={"order_id": oid})
        assert r.status_code == 400
        assert "production" in r.json()["detail"].lower()
    _clear()


@pytest.mark.asyncio
async def test_duplicate_generation_returns_existing(seeded_users):
    u = seeded_users["user_a"]
    oid = await _seed_order(u["tenant_id"])
    async with await _client(u) as c:
        r1 = await c.post("/api/work-orders", json={"order_id": oid})
        r2 = await c.post("/api/work-orders", json={"order_id": oid})
        assert r1.json()["id"] == r2.json()["id"]
        assert r2.json().get("already_exists") is True
    _clear()


@pytest.mark.asyncio
async def test_regenerate_supersedes_and_preserves_snapshot(seeded_users):
    u = seeded_users["user_a"]
    oid = await _seed_order(u["tenant_id"])
    async with await _client(u) as c:
        wo1_id = (await c.post("/api/work-orders", json={"order_id": oid})).json()["id"]
        snap1 = (await c.get(f"/api/work-orders/{wo1_id}")).json()["items_snapshot"]

        # Change source item
        await _db.order_items.update_many(
            {"tenant_id": u["tenant_id"], "order_id": oid},
            {"$set": {"description": "Banner 4x8", "quantity": 5}},
        )
        # Old snapshot unchanged
        cur = (await c.get(f"/api/work-orders/{wo1_id}")).json()["items_snapshot"]
        assert cur == snap1

        r = await c.post(f"/api/work-orders/{wo1_id}/regenerate", json={"reason": "customer changed size"})
        assert r.status_code == 201
        wo2 = r.json()
        assert wo2["version"] == 2
        assert wo2["superseded_from"] == wo1_id
        assert wo2["items_snapshot"][0]["description"] == "Banner 4x8"

        old = (await c.get(f"/api/work-orders/{wo1_id}")).json()
        assert old["production_status"] == "superseded"
        assert old["current_version"] is False
        assert old["superseded_by"] == wo2["id"]
    _clear()


@pytest.mark.asyncio
async def test_transitions_and_reasons(seeded_users):
    u = seeded_users["user_a"]
    oid = await _seed_order(u["tenant_id"])
    async with await _client(u) as c:
        wo_id = (await c.post("/api/work-orders", json={"order_id": oid})).json()["id"]

        r = await c.post(f"/api/work-orders/{wo_id}/transition", json={"target": "completed"})
        assert r.status_code == 400

        assert (await c.post(f"/api/work-orders/{wo_id}/transition", json={"target": "released"})).status_code == 200
        assert (await c.post(f"/api/work-orders/{wo_id}/transition", json={"target": "in_progress"})).status_code == 200

        r = await c.post(f"/api/work-orders/{wo_id}/transition", json={"target": "blocked"})
        assert r.status_code == 400

        r = await c.post(f"/api/work-orders/{wo_id}/transition", json={"target": "blocked", "reason": "artwork missing"})
        assert r.status_code == 200
        assert r.json()["block_reason"] == "artwork missing"

        assert (await c.post(f"/api/work-orders/{wo_id}/transition", json={"target": "released"})).status_code == 200
        assert (await c.post(f"/api/work-orders/{wo_id}/transition", json={"target": "in_progress"})).status_code == 200
        assert (await c.post(f"/api/work-orders/{wo_id}/transition", json={"target": "ready"})).status_code == 200

        r = await c.post(f"/api/work-orders/{wo_id}/transition", json={"target": "completed"})
        assert r.status_code == 200
        assert r.json()["completed_at"] is not None

        order = await _db.orders.find_one({"id": oid})
        assert order["status"] == "completed"
    _clear()


@pytest.mark.asyncio
async def test_assignment_and_cross_tenant(seeded_users):
    u_a = seeded_users["user_a"]
    u_b = seeded_users["user_b"]
    oid = await _seed_order(u_a["tenant_id"])
    async with await _client(u_a) as c:
        wo_id = (await c.post("/api/work-orders", json={"order_id": oid})).json()["id"]
        r = await c.post(f"/api/work-orders/{wo_id}/assign", json={"user_ids": [u_a["id"]]})
        assert r.status_code == 200
        assert u_a["id"] in r.json()["assigned_user_ids"]

        r = await c.post(f"/api/work-orders/{wo_id}/assign", json={"user_ids": [u_b["id"]]})
        assert r.status_code == 400
        assert "assignee" in r.json()["detail"].lower()
    _clear()


@pytest.mark.asyncio
async def test_summary_excludes_pricing_without_perm(seeded_users):
    u = seeded_users["user_a"]
    # Drop invoice:read to prove pricing is excluded when perm absent
    u_prod = {**u, "permissions": [p for p in (u.get("permissions") or []) if p != "invoice:read"]}
    oid = await _seed_order(u_prod["tenant_id"])
    async with await _client(u_prod) as c:
        wo_id = (await c.post("/api/work-orders", json={"order_id": oid})).json()["id"]
        r = await c.get(f"/api/work-orders/{wo_id}/summary")
        assert r.status_code == 200
        body = r.json()
        assert body["work_order_number"]
        for item in body["items"]:
            assert "unit_price_cents" not in item
    _clear()


@pytest.mark.asyncio
async def test_production_board(seeded_users):
    u = seeded_users["user_a"]
    oid = await _seed_order(u["tenant_id"])
    async with await _client(u) as c:
        wo_id = (await c.post("/api/work-orders", json={"order_id": oid})).json()["id"]
        await c.post(f"/api/work-orders/{wo_id}/transition", json={"target": "released"})
        r = await c.get("/api/production/board")
        assert r.status_code == 200
        body = r.json()
        assert wo_id in [w["id"] for w in body["columns"]["released"]]
        assert body["counts"]["released"] >= 1
    _clear()


@pytest.mark.asyncio
async def test_tenant_isolation_work_orders(seeded_users):
    u_a = seeded_users["user_a"]
    u_b = seeded_users["user_b"]
    oid = await _seed_order(u_a["tenant_id"])
    async with await _client(u_a) as c:
        wo_id = (await c.post("/api/work-orders", json={"order_id": oid})).json()["id"]
    _clear()
    async with await _client(u_b) as c:
        assert (await c.get(f"/api/work-orders/{wo_id}")).status_code == 404
        assert (await c.post(f"/api/work-orders/{wo_id}/transition", json={"target": "released"})).status_code == 404
        assert (await c.get(f"/api/work-orders/{wo_id}/summary")).status_code == 404
    _clear()
