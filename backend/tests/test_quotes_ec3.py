"""EC3 — Quote line items, revisions, conversion, tenant isolation.

Uses direct FastAPI dependency overrides to exercise the router in-process
against the real MongoDB used by other tests, seeded via `seeded_users`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

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
        "id": cust_id,
        "tenant_id": tenant_id,
        "name": f"Test {cust_id}",
        "email": "c@example.com",
    })
    return cust_id


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override_as(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear_overrides():
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_quote_line_items_backend_derived_totals(seeded_users):
    user = seeded_users["user_a"]
    cust_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        r = await c.post("/api/quotes", json={
            "customer_id": cust_id,
            "job_name": "Sign package",
        })
        assert r.status_code == 201, r.text
        quote = r.json()
        qid = quote["id"]

        # Add two line items
        r = await c.post(f"/api/quotes/{qid}/line-items", json={
            "description": "Banner 3x6",
            "quantity": 2,
            "unit_price_cents": 5000,
            "category": "banners",
        })
        assert r.status_code == 201
        r = await c.post(f"/api/quotes/{qid}/line-items", json={
            "description": "Design fee",
            "quantity": 1,
            "unit_price_cents": 7500,
            "discount_cents": 500,
            "category": "services",
        })
        assert r.status_code == 201

        r = await c.get(f"/api/quotes/{qid}")
        assert r.status_code == 200
        body = r.json()
        assert body["totals"]["subtotal_cents"] == 2 * 5000 + 7500
        assert body["totals"]["discount_cents"] == 500
        assert body["totals"]["total_cents"] == 2 * 5000 + 7500 - 500
        assert body["quote"]["total_cents"] == body["totals"]["total_cents"]
    _clear_overrides()


@pytest.mark.asyncio
async def test_sent_quote_edit_creates_revision(seeded_users):
    user = seeded_users["user_a"]
    cust_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        r = await c.post("/api/quotes", json={"customer_id": cust_id, "job_name": "Wrap"})
        qid = r.json()["id"]
        r = await c.post(f"/api/quotes/{qid}/line-items", json={
            "description": "Banner", "quantity": 1, "unit_price_cents": 10000,
            "category": "banners",
        })
        # send it
        r = await c.post(f"/api/quotes/{qid}/status", json={"status": "sent"})
        assert r.status_code == 200
        assert r.json()["status"] == "sent"

        # Edit the price → should force a revision
        r = await c.post(f"/api/quotes/{qid}/line-items", json={
            "description": "Extra banner", "quantity": 1, "unit_price_cents": 12000,
            "category": "banners",
        })
        assert r.status_code == 201

        # New quote revision should be 2
        r = await c.get(f"/api/quotes/{qid}")
        assert r.json()["quote"]["revision_number"] == 2

        r = await c.get(f"/api/quotes/{qid}/revisions")
        assert r.status_code == 200
        revs = r.json()["items"]
        assert len(revs) == 1
        assert revs[0]["revision_number"] == 1
        assert revs[0]["job_name"] == "Wrap"
    _clear_overrides()


@pytest.mark.asyncio
async def test_expired_quote_conversion_blocked_and_overridable(seeded_users):
    user = seeded_users["user_a"]
    cust_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        r = await c.post("/api/quotes", json={
            "customer_id": cust_id,
            "job_name": "Wrap",
            "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        })
        qid = r.json()["id"]
        r = await c.post(f"/api/quotes/{qid}/status", json={"status": "sent"})
        assert r.status_code == 200

        # Without override → rejected
        r = await c.post(f"/api/quotes/{qid}/convert-to-order", json={})
        assert r.status_code == 400
        assert "expired" in r.json()["detail"].lower()

        # With override but no reason → 400
        r = await c.post(f"/api/quotes/{qid}/convert-to-order", json={"allow_expired": True})
        assert r.status_code == 400

        # With override + reason → success
        r = await c.post(f"/api/quotes/{qid}/convert-to-order", json={
            "allow_expired": True, "override_reason": "customer approved verbally",
        })
        assert r.status_code == 200
        assert r.json()["order"]["id"]
    _clear_overrides()


@pytest.mark.asyncio
async def test_convert_idempotent_and_copies_items(seeded_users):
    user = seeded_users["user_a"]
    cust_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        r = await c.post("/api/quotes", json={"customer_id": cust_id, "job_name": "Sign"})
        qid = r.json()["id"]
        for _ in range(2):
            await c.post(f"/api/quotes/{qid}/line-items", json={
                "description": "Item", "quantity": 1, "unit_price_cents": 2500, "category": "banners",
            })

        r1 = await c.post(f"/api/quotes/{qid}/convert-to-order", json={})
        assert r1.status_code == 200
        order_id = r1.json()["order"]["id"]
        assert r1.json()["already_converted"] is False

        r2 = await c.post(f"/api/quotes/{qid}/convert-to-order", json={})
        assert r2.status_code == 200
        assert r2.json()["already_converted"] is True
        assert r2.json()["order"]["id"] == order_id

        # Order items copied
        r = await c.get(f"/api/orders/{order_id}")
        body = r.json()
        assert len(body["items"]) == 2
        assert body["order"]["source_quote_id"] == qid
        assert body["order"]["source_quote_revision"] == 1
        assert body["totals"]["subtotal_cents"] == 5000
    _clear_overrides()


@pytest.mark.asyncio
async def test_declined_quote_cannot_convert(seeded_users):
    user = seeded_users["user_a"]
    cust_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        r = await c.post("/api/quotes", json={"customer_id": cust_id, "job_name": "X"})
        qid = r.json()["id"]
        await c.post(f"/api/quotes/{qid}/status", json={"status": "sent"})
        await c.post(f"/api/quotes/{qid}/status", json={"status": "declined", "reason": "no budget"})
        r = await c.post(f"/api/quotes/{qid}/convert-to-order", json={})
        assert r.status_code == 400
        assert "declined" in r.json()["detail"].lower()
    _clear_overrides()


@pytest.mark.asyncio
async def test_tenant_isolation_on_quotes(seeded_users):
    user_a = seeded_users["user_a"]
    user_b = seeded_users["user_b"]
    cust_id = await _seed_customer(user_a["tenant_id"])
    async with await _client_as(user_a) as ca:
        r = await ca.post("/api/quotes", json={"customer_id": cust_id, "job_name": "T"})
        qid = r.json()["id"]
    _clear_overrides()

    async with await _client_as(user_b) as cb:
        r = await cb.get(f"/api/quotes/{qid}")
        assert r.status_code == 404
        r = await cb.post(f"/api/quotes/{qid}/convert-to-order", json={})
        assert r.status_code == 404
    _clear_overrides()
