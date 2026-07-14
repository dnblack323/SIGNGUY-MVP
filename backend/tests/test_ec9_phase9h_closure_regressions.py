"""EC9 Phase 9H — Closure regression tests.

Locks in the ONE critical defect found by `testing_agent_v4` during the
Phase 9H closure pass: Quote Line Item / Order Item pricing resolution never
forwarded `width_inches`/`height_inches` into the pricing engine for
flat/square-foot categories (banners, rigid_signs, cut_vinyl, digital_print),
silently falling back to the category's minimum billable area regardless of
what the user actually entered. Fixed in `routers/quotes.py` and
`routers/orders.py` (`_resolve_item_pricing` now accepts + forwards
`width_inches`/`height_inches` at add/update/recalculate-preview call sites;
`pricing_trigger_fields` now includes both so a dimensions-only edit also
triggers recalculation).

Credit-Conservation note: targeted pytest only, reusing the `seeded_users`
fixture pattern from `test_ec9_phase9f_quote_order_integration.py`.
"""
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


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override_as(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


async def _seed_customer(tenant_id: str) -> str:
    cust_id = f"cust-{uuid.uuid4().hex[:8]}"
    await _db.customers.insert_one({"id": cust_id, "tenant_id": tenant_id, "name": "Test Co", "email": "c@example.com"})
    return cust_id


async def _new_quote(c: AsyncClient, cust_id: str) -> str:
    r = await c.post("/api/quotes", json={"customer_id": cust_id, "job_name": "Phase 9H closure quote"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _new_order(c: AsyncClient, cust_id: str) -> str:
    r = await c.post("/api/orders", json={"customer_id": cust_id, "job_name": "Phase 9H closure order"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


LARGE_BANNER = {
    "description": "Big banner", "quantity": 1, "unit_price_cents": 0, "category": "banners",
    "width_inches": 96, "height_inches": 48, "category_inputs": {}, "selected_price_source": "suggested",
}
SMALL_BANNER = {
    "description": "Small banner", "quantity": 1, "unit_price_cents": 0, "category": "banners",
    "width_inches": 12, "height_inches": 12, "category_inputs": {}, "selected_price_source": "suggested",
}


@pytest.mark.asyncio
async def test_quote_line_item_dimensions_actually_reach_the_pricing_engine(seeded_users):
    """A 96x48in banner must price higher than a 12x12in banner — before the
    fix both silently used the category default/minimum area."""
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        r_large = await c.post(f"/api/quotes/{qid}/line-items", json=LARGE_BANNER)
        r_small = await c.post(f"/api/quotes/{qid}/line-items", json=SMALL_BANNER)
        assert r_large.status_code == 201 and r_small.status_code == 201
        large_item, small_item = r_large.json(), r_small.json()
        assert large_item["suggested_price_cents"] > small_item["suggested_price_cents"]
    _clear()


@pytest.mark.asyncio
async def test_order_item_dimensions_actually_reach_the_pricing_engine(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        oid = await _new_order(c, cust)
        r_large = await c.post(f"/api/orders/{oid}/items", json=LARGE_BANNER)
        r_small = await c.post(f"/api/orders/{oid}/items", json=SMALL_BANNER)
        assert r_large.status_code == 201 and r_small.status_code == 201
        assert r_large.json()["suggested_price_cents"] > r_small.json()["suggested_price_cents"]
    _clear()


@pytest.mark.asyncio
async def test_dimensions_only_update_triggers_recalculation(seeded_users):
    """Changing ONLY width/height (no category_inputs change) must trigger a
    fresh calculation — dimensions were previously missing entirely from
    `pricing_trigger_fields`."""
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json=SMALL_BANNER)
        item = r.json()
        old_price = item["suggested_price_cents"]

        r = await c.patch(f"/api/quotes/{qid}/line-items/{item['id']}", json={"width_inches": 96, "height_inches": 48})
        assert r.status_code == 200, r.text
        updated = r.json()
        assert updated["suggested_price_cents"] > old_price
    _clear()


@pytest.mark.asyncio
async def test_recalculate_preview_uses_stored_dimensions_when_not_overridden(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json=LARGE_BANNER)
        item = r.json()

        r = await c.post(f"/api/quotes/{qid}/line-items/{item['id']}/recalculate-preview", json={})
        assert r.status_code == 200, r.text
        preview = r.json()
        # Same stored dimensions + same defaults => same suggested price
        assert preview["new"]["suggested_price_cents"] == item["suggested_price_cents"]

        r2 = await c.post(
            f"/api/quotes/{qid}/line-items/{item['id']}/recalculate-preview",
            json={"width_inches": 12, "height_inches": 12},
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["new"]["suggested_price_cents"] < preview["new"]["suggested_price_cents"]
    _clear()


@pytest.mark.asyncio
async def test_order_recalculate_preview_dimension_override(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        oid = await _new_order(c, cust)
        r = await c.post(f"/api/orders/{oid}/items", json=SMALL_BANNER)
        item = r.json()

        r = await c.post(
            f"/api/orders/{oid}/items/{item['id']}/recalculate-preview",
            json={"width_inches": 96, "height_inches": 48},
        )
        assert r.status_code == 200, r.text
        assert r.json()["new"]["suggested_price_cents"] > item["suggested_price_cents"]
    _clear()
