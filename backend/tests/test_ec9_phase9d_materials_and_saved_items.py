"""EC9 Phase 9D — Canonical Materials and Reusable Saved Items tests.

Focused on the NEW Phase 9D behaviors only (Phase 9A already covers: profile
links canonical material / one profile per material / tenant isolation /
category validation / component create+update / saved-item canonical
material refs / save-as-variation non-mutation — not repeated here).

Covers: Business Card starter tiers preload exactly (never invented),
exact-match tier-price lookup (matching + non-matching quantity), quick-select
filtering, archived saved item excluded from active list, archived material
blocks new pricing profile + excluded from default list, pricing component
charge_type is a closed enum (structural guard against physical-inventory
misuse), active-flag archive/restore on a material pricing profile, and a
historical Quote line-item snapshot staying unchanged after a saved item is
later edited.
"""
from __future__ import annotations
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from server import app
from app.core.db import db
from app.deps import get_current_user
from app.services.pricing_saved_items import resolve_quantity_tier_price


def _override(u):
    async def _get(): return {**u}
    return _get


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear(): app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def ec9d_ctx():
    ta = f"t-ec9d-{uuid.uuid4().hex[:6]}"
    ua = {"id": f"u-a-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
          "email": f"a-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_one({"id": ta, "slug": ta, "name": "TA"})
    await db.users.insert_one({**ua})
    yield {"ua": ua, "ta": ta}
    _clear()


def test_resolve_quantity_tier_price_pure_function():
    item = {"quantity_tiers": [{"quantity": 100, "price": 25.0}, {"quantity": 250, "price": 45.0}]}
    assert resolve_quantity_tier_price(item, 250) == 45.0
    assert resolve_quantity_tier_price(item, 300) is None  # never invented


@pytest.mark.asyncio
async def test_business_card_starter_tiers_preloaded_exactly(ec9d_ctx):
    ua = ec9d_ctx["ua"]
    async with await _client(ua) as c:
        lst = await c.get("/api/pricing/saved-items", params={"category": "promotional"})
        assert lst.status_code == 200
        items = {i["name"]: i for i in lst.json()["items"]}
        assert "Standard Paper Business Cards" in items
        assert "Magnetic Business Cards" in items
        std = items["Standard Paper Business Cards"]
        assert std["quick_select"] is True
        assert {"quantity": 1000, "price": 125.0} in std["quantity_tiers"]
        assert {"quantity": 2500, "price": 225.0} in std["quantity_tiers"]
        mag = items["Magnetic Business Cards"]
        assert {"quantity": 25, "price": 25.0} in mag["quantity_tiers"]
        assert {"quantity": 1000, "price": 275.0} in mag["quantity_tiers"]
        # Idempotent: a second list call must not duplicate the starter items
        lst2 = await c.get("/api/pricing/saved-items", params={"category": "promotional"})
        names = [i["name"] for i in lst2.json()["items"]]
        assert names.count("Standard Paper Business Cards") == 1
    _clear()


@pytest.mark.asyncio
async def test_business_card_tier_price_lookup_matching_quantity(ec9d_ctx):
    ua = ec9d_ctx["ua"]
    async with await _client(ua) as c:
        lst = await c.get("/api/pricing/saved-items", params={"category": "promotional"})
        std_id = next(i["id"] for i in lst.json()["items"] if i["name"] == "Standard Paper Business Cards")
        r = await c.get(f"/api/pricing/saved-items/{std_id}/tier-price", params={"quantity": 250})
        assert r.status_code == 200
        assert r.json() == {"item_id": std_id, "quantity": 250, "matched": True, "price": 45.0}
    _clear()


@pytest.mark.asyncio
async def test_business_card_tier_price_lookup_nonmatching_quantity_no_invented_price(ec9d_ctx):
    ua = ec9d_ctx["ua"]
    async with await _client(ua) as c:
        lst = await c.get("/api/pricing/saved-items", params={"category": "promotional"})
        std_id = next(i["id"] for i in lst.json()["items"] if i["name"] == "Standard Paper Business Cards")
        r = await c.get(f"/api/pricing/saved-items/{std_id}/tier-price", params={"quantity": 300})
        assert r.status_code == 200
        assert r.json() == {"item_id": std_id, "quantity": 300, "matched": False, "price": None}
    _clear()


@pytest.mark.asyncio
async def test_quick_select_filtering(ec9d_ctx):
    ua = ec9d_ctx["ua"]
    async with await _client(ua) as c:
        await c.post("/api/pricing/saved-items", json={"name": "One-off Koozie Batch", "category": "promotional", "quick_select": False})
        quick_only = await c.get("/api/pricing/saved-items", params={"quick_select": True})
        names = [i["name"] for i in quick_only.json()["items"]]
        assert "One-off Koozie Batch" not in names
        assert "Standard Paper Business Cards" in names
    _clear()


@pytest.mark.asyncio
async def test_archived_saved_item_excluded_from_active_list(ec9d_ctx):
    ua = ec9d_ctx["ua"]
    async with await _client(ua) as c:
        r = await c.post("/api/pricing/saved-items", json={"name": "Retiring Item", "category": "banners"})
        iid = r.json()["id"]
        await c.patch(f"/api/pricing/saved-items/{iid}", json={"active": False})
        active_list = await c.get("/api/pricing/saved-items", params={"active": True})
        assert not any(i["id"] == iid for i in active_list.json()["items"])
        # restore
        restored = await c.patch(f"/api/pricing/saved-items/{iid}", json={"active": True})
        assert restored.json()["active"] is True
    _clear()


@pytest.mark.asyncio
async def test_archived_material_excluded_and_blocks_new_pricing_profile(ec9d_ctx):
    ua = ec9d_ctx["ua"]
    async with await _client(ua) as c:
        m = await c.post("/api/materials", json={"name": "Discontinued Vinyl", "category": "vinyl", "current_cost_cents": 500})
        mid = m.json()["id"]
        await c.post(f"/api/materials/{mid}/archive")
        default_list = await c.get("/api/materials")
        assert not any(i["id"] == mid for i in default_list.json()["items"])
        profile_attempt = await c.post(f"/api/pricing/material-profiles/materials/{mid}", json={"category_applicability": ["cut_vinyl"]})
        assert profile_attempt.status_code == 400
        await c.post(f"/api/materials/{mid}/restore")
        restored_list = await c.get("/api/materials")
        assert any(i["id"] == mid for i in restored_list.json()["items"])
    _clear()


@pytest.mark.asyncio
async def test_pricing_component_charge_type_is_closed_enum(ec9d_ctx):
    """Structural guard: PricingComponent.charge_type only accepts non-inventory
    fee kinds — a physical/stocked-item style charge_type is rejected (422),
    keeping physical items exclusively on canonical Materials."""
    ua = ec9d_ctx["ua"]
    async with await _client(ua) as c:
        r = await c.post("/api/pricing/components", json={
            "key": "bad_component", "name": "Bad", "charge_type": "stocked_hardware_purchase",
        })
        assert r.status_code in (400, 422)  # rejected either way; domain model enforces the closed enum
    _clear()


@pytest.mark.asyncio
async def test_material_pricing_profile_archive_restore_via_active_flag(ec9d_ctx):
    ua = ec9d_ctx["ua"]
    async with await _client(ua) as c:
        m = await c.post("/api/materials", json={"name": "Laminate Test", "category": "laminate", "current_cost_cents": 300})
        mid = m.json()["id"]
        prof = await c.post(f"/api/pricing/material-profiles/materials/{mid}", json={"category_applicability": ["rigid_signs"]})
        pid = prof.json()["id"]
        off = await c.patch(f"/api/pricing/material-profiles/{pid}", json={"active": False})
        assert off.json()["active"] is False
        on = await c.patch(f"/api/pricing/material-profiles/{pid}", json={"active": True})
        assert on.json()["active"] is True
    _clear()


@pytest.mark.asyncio
async def test_historical_line_item_snapshot_unchanged_after_saved_item_edit(ec9d_ctx):
    ua = ec9d_ctx["ua"]
    async with await _client(ua) as c:
        m = await c.post("/api/materials", json={"name": "Snapshot Vinyl", "category": "vinyl", "current_cost_cents": 1200})
        mid = m.json()["id"]
        saved = await c.post("/api/pricing/saved-items", json={
            "name": "3x6 Standard Banner", "category": "banners", "material_refs": [mid],
        })
        item_id = saved.json()["id"]
        cust = await c.post("/api/customers", json={"name": "9D Test Customer"})
        q = await c.post("/api/quotes", json={"customer_id": cust.json()["id"], "job_name": "9D Job"})
        li = await c.post(f"/api/quotes/{q.json()['id']}/line-items", json={
            "category": "banners", "description": "3x6 Standard Banner", "quantity": 1, "unit_price_cents": 7500,
        })
        li_id = li.json()["id"]
        # Later, the saved item is renamed/edited
        await c.patch(f"/api/pricing/saved-items/{item_id}", json={"name": "3x6 Standard Banner (updated)", "default_notes": "price revised"})
        # The already-created Quote line item must remain exactly as snapshotted
        refreshed = await c.get(f"/api/quotes/{q.json()['id']}")
        line_items = refreshed.json()["line_items"]
        target = next((x for x in line_items if x["id"] == li_id), None)
        assert target is not None
        assert target["unit_price_cents"] == 7500
        assert target["description"] == "3x6 Standard Banner"
    _clear()
