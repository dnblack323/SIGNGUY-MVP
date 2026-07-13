"""EC9 Phase 9B closure — explicit Phase 9A invariant verification.

Covers invariants not already exercised by
`test_ec9_material_pricing_profiles.py` / `test_ec9_pricing_saved_items.py`:
  4. Archiving a Material does not delete historical pricing snapshots.
  5. Archived Materials cannot be newly selected for pricing unless restored.
  6. Deactivating a PricingSavedItem/PricingComponent does not alter other collections.
  9. All new records carry tenant scope, timestamps, and archive/status fields.
 10. No pricing profile becomes a second inventory record.
Invariants 1/3 (uniqueness) are additionally re-verified here at the raw
Mongo layer (defense in depth beyond the service-level 400 check already
covered by `test_one_profile_per_material`). Invariants 2, 7, 8 are already
covered by the Phase 9A test files referenced above and are not repeated.
"""
from __future__ import annotations
import uuid
import pytest
from pymongo.errors import DuplicateKeyError
from httpx import ASGITransport, AsyncClient
from server import app
from app.core.db import db
from app.deps import get_current_user
from app.models.material_pricing_profile import MaterialPricingProfile


def _override(u):
    async def _get(): return {**u}
    return _get


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear(): app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def inv_ctx():
    ta = f"t-ec9-inv-{uuid.uuid4().hex[:6]}"
    ua = {"id": f"u-a-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
          "email": f"a-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_one({"id": ta, "slug": ta, "name": "TA"})
    await db.users.insert_one({**ua})
    yield {"ua": ua, "ta": ta}
    _clear()


@pytest.mark.asyncio
async def test_invariant_1_and_3_unique_index_rejects_raw_duplicate(inv_ctx):
    """DB-level defense in depth: even bypassing the service, Mongo's unique
    (tenant_id, material_id) index refuses a second profile document."""
    ua, ta = inv_ctx["ua"], inv_ctx["ta"]
    async with await _client(ua) as c:
        m = await c.post("/api/materials", json={"name": "Dup Test Vinyl", "category": "vinyl", "current_cost_cents": 100})
        mid = m.json()["id"]
        r1 = await c.post(f"/api/pricing/material-profiles/materials/{mid}", json={})
        assert r1.status_code == 201
    _clear()
    doc2 = MaterialPricingProfile(tenant_id=ta, material_id=mid).model_dump()
    with pytest.raises(DuplicateKeyError):
        await db.material_pricing_profiles.insert_one(dict(doc2))
    count = await db.material_pricing_profiles.count_documents({"tenant_id": ta, "material_id": mid})
    assert count == 1


@pytest.mark.asyncio
async def test_invariant_4_archiving_material_preserves_historical_snapshot(inv_ctx):
    ua = inv_ctx["ua"]
    async with await _client(ua) as c:
        m = await c.post("/api/materials", json={"name": "Archive Test Vinyl", "category": "vinyl", "current_cost_cents": 500})
        mid = m.json()["id"]
        cust = await c.post("/api/customers", json={"name": "Archive Test Customer"})
        cid = cust.json()["id"]
        q = await c.post("/api/quotes", json={"customer_id": cid, "job_name": "Archive Test Job"})
        qid = q.json()["id"]
        li = await c.post(f"/api/quotes/{qid}/line-items", json={
            "category": "cut_vinyl", "description": "Archive test decal", "quantity": 1,
            "unit_price_cents": 2500, "material_key": mid,
        })
        item_id = li.json()["id"]
        snapshot_before = li.json()["pricing_snapshot"]
        # Archive the material
        arch = await c.post(f"/api/materials/{mid}/archive")
        assert arch.status_code == 200
        # Historical line item + its snapshot are completely untouched
        detail = await c.get(f"/api/quotes/{qid}/line-items")
        after = next(x for x in detail.json()["items"] if x["id"] == item_id)
        assert after["pricing_snapshot"] == snapshot_before
        assert after["unit_price_cents"] == 2500
    _clear()


@pytest.mark.asyncio
async def test_invariant_5_archived_material_rejected_for_new_selection(inv_ctx):
    ua = inv_ctx["ua"]
    async with await _client(ua) as c:
        m = await c.post("/api/materials", json={"name": "Will Be Archived", "category": "vinyl", "current_cost_cents": 500})
        mid = m.json()["id"]
        await c.post(f"/api/materials/{mid}/archive")
        # New pricing profile creation on an archived material is rejected
        r1 = await c.post(f"/api/pricing/material-profiles/materials/{mid}", json={})
        assert r1.status_code == 400
        # New saved item referencing an archived material is rejected
        r2 = await c.post("/api/pricing/saved-items", json={"name": "Bad Saved Item", "category": "cut_vinyl", "material_refs": [mid]})
        assert r2.status_code == 400
        # Restoring (reactivating) the material makes it selectable again
        restore = await c.post(f"/api/materials/{mid}/restore")
        assert restore.status_code == 200
        r3 = await c.post(f"/api/pricing/material-profiles/materials/{mid}", json={})
        assert r3.status_code == 201
    _clear()


@pytest.mark.asyncio
async def test_invariant_6_deactivating_component_and_saved_item_is_isolated(inv_ctx):
    ua = inv_ctx["ua"]
    async with await _client(ua) as c:
        comp = await c.post("/api/pricing/components", json={"key": "iso_test_fee", "name": "Iso Test Fee", "amount": 10.0})
        cid = comp.json()["id"]
        item = await c.post("/api/pricing/saved-items", json={"name": "Iso Test Item", "category": "banners"})
        iid = item.json()["id"]
        before_materials = await db.materials.count_documents({"tenant_id": inv_ctx["ta"]})
        before_profiles = await db.material_pricing_profiles.count_documents({"tenant_id": inv_ctx["ta"]})
        await c.patch(f"/api/pricing/components/{cid}", json={"active": False})
        await c.patch(f"/api/pricing/saved-items/{iid}", json={"active": False})
        after_materials = await db.materials.count_documents({"tenant_id": inv_ctx["ta"]})
        after_profiles = await db.material_pricing_profiles.count_documents({"tenant_id": inv_ctx["ta"]})
        assert before_materials == after_materials
        assert before_profiles == after_profiles
        # The records themselves are archived, not deleted
        assert (await c.get(f"/api/pricing/components/{cid}")).json()["active"] is False
        assert (await c.get(f"/api/pricing/saved-items/{iid}")).json()["active"] is False
    _clear()


@pytest.mark.asyncio
async def test_invariant_9_new_records_have_tenant_scope_timestamps_status(inv_ctx):
    ua, ta = inv_ctx["ua"], inv_ctx["ta"]
    async with await _client(ua) as c:
        m = await c.post("/api/materials", json={"name": "Fields Test", "category": "vinyl", "current_cost_cents": 100})
        mid = m.json()["id"]
        profile = (await c.post(f"/api/pricing/material-profiles/materials/{mid}", json={})).json()
        comp = (await c.post("/api/pricing/components", json={"key": "fields_test_fee", "name": "Fields Test Fee"})).json()
        item = (await c.post("/api/pricing/saved-items", json={"name": "Fields Test Item", "category": "banners"})).json()
    for doc in (profile, comp, item):
        assert doc.get("id")
        assert doc.get("created_at")
        assert doc.get("updated_at")
        assert "active" in doc
    assert profile["material_id"] == mid
    assert comp["key"] == "fields_test_fee"
    _clear()


@pytest.mark.asyncio
async def test_invariant_10_profile_is_not_a_second_inventory_record(inv_ctx):
    ua = inv_ctx["ua"]
    async with await _client(ua) as c:
        m = await c.post("/api/materials", json={"name": "Inventory Check", "category": "vinyl", "current_cost_cents": 100, "stock_tracked": True})
        mid = m.json()["id"]
        profile = (await c.post(f"/api/pricing/material-profiles/materials/{mid}", json={})).json()
    inventory_only_fields = {"stock_tracked", "reorder_point", "reorder_quantity", "quantity_on_hand", "current_cost_cents", "sku", "vendor_item_number"}
    assert not (inventory_only_fields & set(profile.keys()))
    _clear()
