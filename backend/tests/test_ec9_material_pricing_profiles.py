"""EC9 phase 9A — Material Pricing Profile tests.

Confirms: EC7 `Material` remains canonical (profile links by material_id,
never duplicates Material fields); one profile per (tenant, material); tenant
isolation; Material.pricing_material_id gets wired to the new profile.
"""
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
async def ec9_ctx():
    ta = f"t-ec9-{uuid.uuid4().hex[:6]}"
    tb = f"t-ec9b-{uuid.uuid4().hex[:6]}"
    ua = {"id": f"u-a-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
          "email": f"a-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    ub = {"id": f"u-b-{uuid.uuid4().hex[:6]}", "tenant_id": tb,
          "email": f"b-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([{"id": ta, "slug": ta, "name": "TA"}, {"id": tb, "slug": tb, "name": "TB"}])
    await db.users.insert_many([{**ua}, {**ub}])
    yield {"ua": ua, "ub": ub, "ta": ta, "tb": tb}
    _clear()


@pytest.mark.asyncio
async def test_create_profile_links_canonical_material(ec9_ctx):
    ua = ec9_ctx["ua"]
    async with await _client(ua) as c:
        m = await c.post("/api/materials", json={"name": "Oracal 651 Test", "category": "vinyl", "current_cost_cents": 12500})
        mid = m.json()["id"]
        r = await c.post(f"/api/pricing/material-profiles/materials/{mid}", json={
            "pricing_unit": "per_sqft", "normalized_cost_basis": 1.25, "waste_percent": 10.0,
            "suggested_sell_rate": 12.0, "category_applicability": ["cut_vinyl"],
        })
        assert r.status_code == 201
        profile = r.json()
        assert profile["material_id"] == mid
        # No Material fields (name/sku/supplier/unit_of_measure/etc.) duplicated onto the profile
        assert "name" not in profile and "sku" not in profile and "current_cost_cents" not in profile
        # Material now points back at the profile via the pre-existing reserved field
        mat = await c.get(f"/api/materials/{mid}")
        assert mat.json()["material"]["pricing_material_id"] == profile["id"]
    _clear()


@pytest.mark.asyncio
async def test_one_profile_per_material(ec9_ctx):
    ua = ec9_ctx["ua"]
    async with await _client(ua) as c:
        m = await c.post("/api/materials", json={"name": "Coroplast Test", "category": "substrate", "current_cost_cents": 9000})
        mid = m.json()["id"]
        r1 = await c.post(f"/api/pricing/material-profiles/materials/{mid}", json={"category_applicability": ["rigid_signs"]})
        assert r1.status_code == 201
        r2 = await c.post(f"/api/pricing/material-profiles/materials/{mid}", json={"category_applicability": ["rigid_signs"]})
        assert r2.status_code == 400
    _clear()


@pytest.mark.asyncio
async def test_tenant_isolation_on_material_profile(ec9_ctx):
    ua, ub = ec9_ctx["ua"], ec9_ctx["ub"]
    async with await _client(ua) as c:
        m = await c.post("/api/materials", json={"name": "Banner Vinyl Test", "category": "banner", "current_cost_cents": 8500})
        mid = m.json()["id"]
    _clear()
    async with await _client(ub) as c:
        r = await c.post(f"/api/pricing/material-profiles/materials/{mid}", json={"category_applicability": ["banners"]})
        assert r.status_code == 400  # material not found for tenant B
    _clear()


@pytest.mark.asyncio
async def test_unknown_category_rejected(ec9_ctx):
    ua = ec9_ctx["ua"]
    async with await _client(ua) as c:
        m = await c.post("/api/materials", json={"name": "Test Vinyl", "category": "vinyl", "current_cost_cents": 100})
        mid = m.json()["id"]
        r = await c.post(f"/api/pricing/material-profiles/materials/{mid}", json={"category_applicability": ["not_a_real_category"]})
        assert r.status_code == 400
    _clear()
