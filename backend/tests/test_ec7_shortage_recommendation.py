"""EC7 phase 7b — Shortage calculation + purchasing recommendation tests.

Covers:
  - shortage aggregates duplicate materials across Order Items
  - recommendation compares supplier delivered cost (not just unit price)
  - recommendation NEVER crosses `compatible_group` (cast vs calendared)
  - lowest_delivered_cost picks the cheaper delivered option
  - fastest_arrival picks the shortest lead time
  - preferred_supplier boosts preferred-flagged vendors
"""
from __future__ import annotations
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from server import app
from app.core.db import db
from app.deps import get_current_user
from app.services import shortage_service, purchasing_recommendation
from app.services.supplier_connectors import TestSupplierAdapter


def _override(u):
    async def _get(): return {**u}
    return _get


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear(): app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def seeded_tenant():
    ta = f"t-rec-{uuid.uuid4().hex[:6]}"
    ua = {"id": f"u-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
          "email": f"u-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_one({"id": ta, "slug": ta, "name": "TA"})
    await db.users.insert_one({**ua})
    await TestSupplierAdapter().seed_tenant(tenant_id=ta)
    yield {"tenant_id": ta, "user": ua}
    _clear()


@pytest.mark.asyncio
async def test_shortage_aggregates_and_marks_shortage(seeded_tenant):
    ta = seeded_tenant["tenant_id"]
    ua = seeded_tenant["user"]
    # Create a Material with 4 in stock at a location.
    async with await _client(ua) as c:
        m = (await c.post("/api/materials", json={"name": "Cast Wrap Gloss White 60x25",
                                                    "sku": "MAT-CST-WHT",
                                                    "category": "vinyl"})).json()
        loc = (await c.post("/api/inventory/locations", json={"name": "Main"})).json()
        await c.post("/api/inventory/adjustments/increase",
                     json={"material_id": m["id"], "location_id": loc["id"], "quantity": 4})
        # Requirements: 10 needed; short by 6.
        rows = await shortage_service.compute_shortage(
            tenant_id=ta,
            requirements=[
                {"material_id": m["id"], "quantity": 6, "order_item_id": "oi1", "order_id": "o1"},
                {"material_id": m["id"], "quantity": 4, "order_item_id": "oi2", "order_id": "o1"},
            ],
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["required"] == 10
        assert row["available"] == 4
        assert row["shortage"] == 6
        assert row["has_shortage"] is True
        assert set(row["order_item_ids"]) == {"oi1", "oi2"}
        assert row["order_ids"] == ["o1"]


@pytest.mark.asyncio
async def test_recommendation_respects_compatible_group(seeded_tenant):
    ta = seeded_tenant["tenant_id"]
    ua = seeded_tenant["user"]
    # Create a Material that matches the CAST WRAP compatible_group SKU.
    async with await _client(ua) as c:
        m = (await c.post("/api/materials", json={"name": "Cast Wrap 60\" Gloss White",
                                                    "sku": "NW-CST-WHT",
                                                    "category": "vinyl"})).json()
    # Request 2 units with compatible_group cast_wrap. Recommender must ONLY
    # return cast_wrap products, never calendared_cut, even though they're
    # both category=vinyl.
    result = await purchasing_recommendation.recommend(
        tenant_id=ta,
        requirements=[{"material_id": m["id"], "quantity": 2,
                       "compatible_group": "cast_wrap"}],
        priority="lowest_delivered_cost",
    )
    assert result["items"], "expected at least one item option"
    item = result["items"][0]
    # Every alternative must be within the requested compatible_group
    all_opts = ([item["chosen"]] if item["chosen"] else []) + item["alternatives"]
    for opt in all_opts:
        assert opt["compatible_group"] == "cast_wrap"


@pytest.mark.asyncio
async def test_recommendation_lowest_delivered_cost_vs_fastest_arrival(seeded_tenant):
    ta = seeded_tenant["tenant_id"]
    ua = seeded_tenant["user"]
    async with await _client(ua) as c:
        m = (await c.post("/api/materials", json={"name": "PermaCast Wrap 60\" Gloss Black",
                                                    "sku": "NW-CST-BLK",
                                                    "category": "vinyl"})).json()
    cheap = await purchasing_recommendation.recommend(
        tenant_id=ta,
        requirements=[{"material_id": m["id"], "quantity": 2,
                       "compatible_group": "cast_wrap"}],
        priority="lowest_delivered_cost",
    )
    fast = await purchasing_recommendation.recommend(
        tenant_id=ta,
        requirements=[{"material_id": m["id"], "quantity": 2,
                       "compatible_group": "cast_wrap"}],
        priority="fastest_arrival",
    )
    chosen_cheap = cheap["items"][0]["chosen"]["chosen_warehouse"]
    chosen_fast = fast["items"][0]["chosen"]["chosen_warehouse"]
    # Cheapest must have lowest cost across returned options
    all_opts_cheap = cheap["items"][0]["alternatives"] + [cheap["items"][0]["chosen"]]
    min_cost = min(o["chosen_warehouse"]["delivered_cost_cents"] for o in all_opts_cheap)
    assert chosen_cheap["delivered_cost_cents"] == min_cost
    # Fastest must have shortest lead time across the same options
    all_opts_fast = fast["items"][0]["alternatives"] + [fast["items"][0]["chosen"]]
    min_lead = min(o["chosen_warehouse"]["lead_time_days"] for o in all_opts_fast)
    assert chosen_fast["lead_time_days"] == min_lead


@pytest.mark.asyncio
async def test_recommendation_prefers_preferred_supplier(seeded_tenant):
    ta = seeded_tenant["tenant_id"]
    ua = seeded_tenant["user"]
    async with await _client(ua) as c:
        m = (await c.post("/api/materials", json={"name": "PermaCast Wrap 60\" Gloss White",
                                                    "sku": "NW-CST-WHT",
                                                    "category": "vinyl"})).json()
    result = await purchasing_recommendation.recommend(
        tenant_id=ta,
        requirements=[{"material_id": m["id"], "quantity": 2,
                       "compatible_group": "cast_wrap"}],
        priority="preferred_supplier",
    )
    chosen = result["items"][0]["chosen"]
    assert chosen["vendor_preferred"] is True


@pytest.mark.asyncio
async def test_no_match_returns_empty_but_no_crash(seeded_tenant):
    ta = seeded_tenant["tenant_id"]
    ua = seeded_tenant["user"]
    async with await _client(ua) as c:
        m = (await c.post("/api/materials", json={"name": "Unicorn Glue",
                                                    "sku": "UNI-GLUE-1",
                                                    "category": "supplies"})).json()
    result = await purchasing_recommendation.recommend(
        tenant_id=ta,
        requirements=[{"material_id": m["id"], "quantity": 5,
                       "compatible_group": "no-such-group"}],
        priority="best_combined_score",
    )
    assert result["items"][0]["chosen"] is None
    assert result["warnings"]
