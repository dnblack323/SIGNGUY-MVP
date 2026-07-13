"""EC9 phase 9A — Pricing Saved Item tests.

Confirms saved items reference canonical EC7 Materials by id (never copy
material data), reject foreign/nonexistent material refs, and support
save-as-variation without mutating the source.
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
async def ec9s_ctx():
    ta = f"t-ec9s-{uuid.uuid4().hex[:6]}"
    ua = {"id": f"u-a-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
          "email": f"a-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_one({"id": ta, "slug": ta, "name": "TA"})
    await db.users.insert_one({**ua})
    yield {"ua": ua, "ta": ta}
    _clear()


@pytest.mark.asyncio
async def test_saved_item_references_canonical_material(ec9s_ctx):
    ua = ec9s_ctx["ua"]
    async with await _client(ua) as c:
        m = await c.post("/api/materials", json={"name": "Coroplast 4mm Test", "category": "substrate", "current_cost_cents": 9000})
        mid = m.json()["id"]
        r = await c.post("/api/pricing/saved-items", json={
            "name": "4x8 Yard Sign", "category": "rigid_signs", "material_refs": [mid],
            "saved_config": {"width_inches": 48, "height_inches": 96, "quantity": 1},
        })
        assert r.status_code == 201
        item = r.json()
        assert item["material_refs"] == [mid]
        assert "current_cost_cents" not in item  # no material data copied
    _clear()


@pytest.mark.asyncio
async def test_foreign_material_ref_rejected(ec9s_ctx):
    ua = ec9s_ctx["ua"]
    async with await _client(ua) as c:
        r = await c.post("/api/pricing/saved-items", json={
            "name": "Bad Item", "category": "banners", "material_refs": ["nonexistent-material-id"],
        })
        assert r.status_code == 400
    _clear()


@pytest.mark.asyncio
async def test_save_as_variation_does_not_mutate_source(ec9s_ctx):
    ua = ec9s_ctx["ua"]
    async with await _client(ua) as c:
        r = await c.post("/api/pricing/saved-items", json={"name": "Standard Banner", "category": "banners"})
        source_id = r.json()["id"]
        var = await c.post(f"/api/pricing/saved-items/{source_id}/save-as-variation", json={"name": "Event Banner Variation"})
        assert var.status_code == 201
        assert var.json()["variation_of_id"] == source_id
        assert var.json()["created_from"] == "variation"
        source_after = await c.get(f"/api/pricing/saved-items/{source_id}")
        assert source_after.json()["name"] == "Standard Banner"  # untouched
    _clear()
