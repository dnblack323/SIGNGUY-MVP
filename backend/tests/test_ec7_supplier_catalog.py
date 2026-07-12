"""EC7 phase 7b — Supplier catalog + test adapter tests.

Covers:
  - deterministic seeding (idempotent, ~80 SKUs, all categories)
  - catalog search + product retrieval + variants
  - account price w/ quantity breaks
  - inventory by warehouse
  - shipping quote
  - discontinued + out-of-stock representation
  - cross-tenant isolation
  - connector capability advertisement
"""
from __future__ import annotations
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from server import app
from app.core.db import db
from app.deps import get_current_user
from app.services.supplier_connectors import (
    TestSupplierAdapter, ConnectorCapability, get_connector, list_connectors,
)


def _override(u):
    async def _get(): return {**u}
    return _get


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear(): app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def ec7b_ctx():
    ta = f"t-ec7b-{uuid.uuid4().hex[:6]}"
    tb = f"t-ec7bB-{uuid.uuid4().hex[:6]}"
    ua = {"id": f"u-a-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
          "email": f"a-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    ub = {"id": f"u-b-{uuid.uuid4().hex[:6]}", "tenant_id": tb,
          "email": f"b-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([{"id": ta, "slug": ta, "name": "TA"},
                                   {"id": tb, "slug": tb, "name": "TB"}])
    await db.users.insert_many([{**ua}, {**ub}])
    yield {"ua": ua, "ub": ub, "ta": ta, "tb": tb}
    _clear()


@pytest.mark.asyncio
async def test_test_adapter_seed_is_idempotent_and_covers_catalog(ec7b_ctx):
    ua = ec7b_ctx["ua"]
    ta = ec7b_ctx["ta"]
    adapter = TestSupplierAdapter()
    s1 = await adapter.seed_tenant(tenant_id=ta)
    s2 = await adapter.seed_tenant(tenant_id=ta)
    # Idempotent: re-seed doesn't grow the collections
    v1 = await db.vendors.count_documents({"tenant_id": ta, "seed_source": "test_adapter"})
    p1 = await db.supplier_products.count_documents({"tenant_id": ta})
    w1 = await db.supplier_warehouses.count_documents({"tenant_id": ta})
    st1 = await db.supplier_product_stock.count_documents({"tenant_id": ta})
    assert v1 == 4                                 # 4 synthetic vendors
    assert 60 <= p1 <= 100                          # 60-100 SKU target
    assert w1 == 8                                  # 3 + 2 + 2 + 1 = 8 warehouses
    assert st1 >= 60                                # at least one stock row per SKU
    assert s1["vendors"] == 4 and s2["vendors"] == 4
    # Category coverage
    for cat in ("apparel", "vinyl", "laminate", "substrate", "hardware", "supplies"):
        c = await db.supplier_products.count_documents({"tenant_id": ta, "category": cat})
        assert c > 0, f"missing category {cat}"
    # Discontinued row exists
    disc = await db.supplier_products.count_documents({"tenant_id": ta, "discontinued": True})
    assert disc >= 1


@pytest.mark.asyncio
async def test_seed_endpoint_and_catalog_search(ec7b_ctx):
    ua = ec7b_ctx["ua"]
    async with await _client(ua) as c:
        r = await c.post("/api/vendors/seed/test-adapter")
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["seeded"] is True
        assert body["vendors"] == 4
        assert 60 <= body["products"] <= 100
        # Search for a vinyl SKU
        r2 = await c.get("/api/supply/catalog", params={"q": "PermaCast", "category": "vinyl"})
        assert r2.status_code == 200
        items = r2.json()["items"]
        assert any("PermaCast" in it["description"] for it in items)
        # Cross-category search still respects category
        assert all(it["category"] == "vinyl" for it in items)
    _clear()


@pytest.mark.asyncio
async def test_variants_and_apparel_expansion(ec7b_ctx):
    ua = ec7b_ctx["ua"]
    ta = ec7b_ctx["ta"]
    await TestSupplierAdapter().seed_tenant(tenant_id=ta)
    async with await _client(ua) as c:
        # Look up a Meridian Classic Crew Tee variant
        r = await c.get("/api/supply/catalog", params={"q": "Classic Crew Tee"})
        items = r.json()["items"]
        assert len(items) >= 9                     # 3 colors × 3 sizes = 9 SKUs
        # All belong to same family and each has color+size
        families = {it["family"] for it in items}
        assert families == {"MER-TEE-CLA"}
        sizes = {it["variant"]["size"] for it in items}
        colors = {it["variant"]["color"] for it in items}
        assert sizes == {"S", "M", "L"}
        assert colors == {"Black", "White", "Navy"}


@pytest.mark.asyncio
async def test_account_price_applies_quantity_breaks(ec7b_ctx):
    ua = ec7b_ctx["ua"]
    ta = ec7b_ctx["ta"]
    await TestSupplierAdapter().seed_tenant(tenant_id=ta)
    async with await _client(ua) as c:
        r = await c.get("/api/supply/catalog", params={"q": "PermaCast Wrap Vinyl 60"})
        items = [i for i in r.json()["items"] if "Gloss White" in i["description"]]
        sp = items[0]
        sp_id = sp["id"]
        # Below break -> base account price
        r1 = await c.post(f"/api/supply/catalog/{sp_id}/price", json={"quantity": 1})
        assert r1.status_code == 200
        assert r1.json()["unit_price_cents"] == 18900
        # At or above break -> lower unit price
        r2 = await c.post(f"/api/supply/catalog/{sp_id}/price", json={"quantity": 4})
        assert r2.json()["unit_price_cents"] == 17500


@pytest.mark.asyncio
async def test_inventory_and_shipping_and_discontinued(ec7b_ctx):
    ua = ec7b_ctx["ua"]
    ta = ec7b_ctx["ta"]
    await TestSupplierAdapter().seed_tenant(tenant_id=ta)
    async with await _client(ua) as c:
        # Discontinued reflective red vinyl has 0 stock everywhere
        r = await c.get("/api/supply/catalog", params={"q": "Engineer Grade Reflective"})
        sp = [x for x in r.json()["items"] if x.get("discontinued")][0]
        detail = (await c.get(f"/api/supply/catalog/{sp['id']}")).json()
        assert all(s["available_qty"] == 0 for s in detail["stock_by_warehouse"])
        # Shipping quote for another product (returns positive cost)
        good_items = (await c.get("/api/supply/catalog", params={"q": "PermaCast Wrap Vinyl"})).json()["items"]
        good = [g for g in good_items if "Gloss Black" in g["description"]][0]
        gdetail = (await c.get(f"/api/supply/catalog/{good['id']}")).json()
        # Pick any warehouse and confirm shipping quote is non-zero
        wh_id = gdetail["stock_by_warehouse"][0]["warehouse_id"]
        adapter = get_connector("test_adapter")
        quote = await adapter.get_shipping_quote(
            tenant_id=ta, vendor_id=good["vendor_id"],
            warehouse_id=wh_id, line_count=1
        )
        assert quote["cost_cents"] > 0
        assert quote["rate_type"] == "estimated"


@pytest.mark.asyncio
async def test_cross_tenant_isolation(ec7b_ctx):
    ta, tb = ec7b_ctx["ta"], ec7b_ctx["tb"]
    await TestSupplierAdapter().seed_tenant(tenant_id=ta)
    # Tenant B has nothing yet
    n_a = await db.supplier_products.count_documents({"tenant_id": ta})
    n_b = await db.supplier_products.count_documents({"tenant_id": tb})
    assert n_a > 0 and n_b == 0
    # Adapter search from tenant B returns empty
    adapter = TestSupplierAdapter()
    empty = await adapter.search_catalog(tenant_id=tb, vendor_id="", query="PermaCast")
    assert empty == []


def test_connector_registry_lists_all_three_tiers():
    lst = list_connectors()
    keys = {c["key"] for c in lst}
    assert {"test_adapter", "manual", "feed_csv"}.issubset(keys)
    ta = next(c for c in lst if c["key"] == "test_adapter")
    # Test adapter advertises ALL capabilities
    assert set(ta["capabilities"]) == {c.value for c in ConnectorCapability}
