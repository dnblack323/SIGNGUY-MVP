"""EC9 phase 9A — Pricing Component tests (non-inventory charges/fees)."""
from __future__ import annotations
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from server import app
from app.core.db import db
from app.deps import get_current_user


def _override(u):
    async def _get(): return {**u}
    return _get


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear(): app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def ec9c_ctx():
    ta = f"t-ec9c-{uuid.uuid4().hex[:6]}"
    ua = {"id": f"u-a-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
          "email": f"a-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_one({"id": ta, "slug": ta, "name": "TA"})
    await db.users.insert_one({**ua})
    yield {"ua": ua, "ta": ta}
    _clear()


@pytest.mark.asyncio
async def test_create_and_list_pricing_component(ec9c_ctx):
    ua = ec9c_ctx["ua"]
    async with await _client(ua) as c:
        r = await c.post("/api/pricing/components", json={
            "key": "standard_setup_fee", "name": "Standard Setup Fee",
            "charge_type": "setup_fee", "amount": 25.0, "category_applicability": ["promotional"],
        })
        assert r.status_code == 201
        cid = r.json()["id"]
        lst = await c.get("/api/pricing/components")
        assert any(i["id"] == cid for i in lst.json()["items"])
    _clear()


@pytest.mark.asyncio
async def test_duplicate_key_rejected(ec9c_ctx):
    ua = ec9c_ctx["ua"]
    async with await _client(ua) as c:
        payload = {"key": "rush_charge", "name": "Rush Charge", "charge_type": "rush_charge", "percent": 25.0}
        r1 = await c.post("/api/pricing/components", json=payload)
        assert r1.status_code == 201
        r2 = await c.post("/api/pricing/components", json=payload)
        assert r2.status_code == 400
    _clear()


@pytest.mark.asyncio
async def test_update_component(ec9c_ctx):
    ua = ec9c_ctx["ua"]
    async with await _client(ua) as c:
        r = await c.post("/api/pricing/components", json={"key": "design_fee", "name": "Design Fee", "charge_type": "design_fee", "amount": 75.0})
        cid = r.json()["id"]
        upd = await c.patch(f"/api/pricing/components/{cid}", json={"amount": 90.0, "active": False})
        assert upd.status_code == 200
        assert upd.json()["amount"] == 90.0
        assert upd.json()["active"] is False
    _clear()
