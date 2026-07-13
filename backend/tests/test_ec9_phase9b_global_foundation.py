"""EC9 Phase 9B — Global Pricing Foundation tests.

Covers: EC09-exact seeded shop-level defaults, shop-defaults CRUD (tenant
isolated), `shop_defaults_used` propagation through `calculate_pricing()`,
and the `defaults_snapshot`/`foundation_effective_at` immutability guarantee
(changing shop defaults later must not alter an already-built snapshot).
"""
from __future__ import annotations
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from server import app
from app.core.db import db
from app.deps import get_current_user
from app.services.pricing import calculate_pricing
from app.services.pricing_snapshot import build_calculated_snapshot
from app.services.starter_defaults import SHOP_DEFAULTS, build_starter_pack


def _override(u):
    async def _get(): return {**u}
    return _get


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear(): app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def ec9b_ctx():
    ta = f"t-ec9-9b-{uuid.uuid4().hex[:6]}"
    tb = f"t-ec9-9bb-{uuid.uuid4().hex[:6]}"
    ua = {"id": f"u-a-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
          "email": f"a-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    ub = {"id": f"u-b-{uuid.uuid4().hex[:6]}", "tenant_id": tb,
          "email": f"b-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([{"id": ta, "slug": ta, "name": "TA"}, {"id": tb, "slug": tb, "name": "TB"}])
    await db.users.insert_many([{**ua}, {**ub}])
    yield {"ua": ua, "ub": ub, "ta": ta, "tb": tb}
    _clear()


def test_seeded_defaults_match_ec09_exactly():
    assert SHOP_DEFAULTS["production_hourly_rate"] == 28.00
    assert SHOP_DEFAULTS["design_hourly_rate"] == 85.00
    assert SHOP_DEFAULTS["install_hourly_rate"] == 95.00
    assert SHOP_DEFAULTS["removal_hourly_rate"] == 65.00
    assert SHOP_DEFAULTS["travel_hourly_rate"] == 45.00
    assert SHOP_DEFAULTS["admin_hourly_rate"] == 35.00
    assert SHOP_DEFAULTS["consultation_hourly_rate"] == 110.00
    assert SHOP_DEFAULTS["site_survey_hourly_rate"] == 95.00
    assert SHOP_DEFAULTS["finishing_hourly_rate"] == 28.00
    assert SHOP_DEFAULTS["default_overhead_percent"] == 15.00
    assert SHOP_DEFAULTS["target_profit_margin_percent"] == 40.00
    assert SHOP_DEFAULTS["default_markup_multiplier"] == 2.5


@pytest.mark.asyncio
async def test_shop_defaults_patch_persists_new_fields_tenant_isolated(ec9b_ctx):
    ua, ub = ec9b_ctx["ua"], ec9b_ctx["ub"]
    async with await _client(ua) as c:
        r = await c.patch("/api/pricing/settings/shop-defaults", json={
            "removal_hourly_rate": 70.0, "consultation_hourly_rate": 120.0,
            "install_minimum_charge": 50.0, "setup_fee_default": 15.0, "labor_burden_percent": 12.5,
        })
        assert r.status_code == 200
        sd = r.json()["shop_defaults"]
        assert sd["removal_hourly_rate"] == 70.0
        assert sd["consultation_hourly_rate"] == 120.0
        assert sd["install_minimum_charge"] == 50.0
        assert sd["setup_fee_default"] == 15.0
        assert sd["labor_burden_percent"] == 12.5
    _clear()
    async with await _client(ub) as c:
        settings_b = await c.get("/api/pricing/settings")
        # Tenant B's clone-once starter pack is unaffected by tenant A's edits
        assert settings_b.json()["shop_defaults"]["removal_hourly_rate"] == 65.00
    _clear()


def test_calculate_pricing_returns_shop_defaults_used():
    settings = build_starter_pack()
    result = calculate_pricing(settings=settings, category="banners", width_inches=48, height_inches=96, quantity=1)
    used = result["shop_defaults_used"]
    assert used["production_hourly_rate"] == 28.00
    assert used["design_hourly_rate"] == 85.00
    assert used["install_hourly_rate"] == 95.00
    assert used["default_overhead_percent"] == 15.00


def test_defaults_snapshot_immutable_after_shop_defaults_change():
    settings = build_starter_pack()
    calc = calculate_pricing(settings=settings, category="banners", width_inches=48, height_inches=96, quantity=1)
    snap = build_calculated_snapshot(calc_result=calc, quantity=1, foundation_effective_at="2026-02-01T00:00:00+00:00")
    assert snap["defaults_snapshot"]["design_hourly_rate"] == 85.00
    assert snap["foundation_effective_at"] == "2026-02-01T00:00:00+00:00"
    # Now simulate the shop editing its defaults AFTER the snapshot was captured
    settings["shop_defaults"]["design_hourly_rate"] = 200.00
    # The already-built snapshot dict must be completely unaffected
    assert snap["defaults_snapshot"]["design_hourly_rate"] == 85.00


@pytest.mark.asyncio
async def test_manual_entry_uses_user_entered_source_label(ec9b_ctx):
    ua = ec9b_ctx["ua"]
    async with await _client(ua) as c:
        cust = await c.post("/api/customers", json={"name": "9B Test Customer"})
        cid = cust.json()["id"]
        q = await c.post("/api/quotes", json={"customer_id": cid, "job_name": "9B Test Job"})
        qid = q.json()["id"]
        li = await c.post(f"/api/quotes/{qid}/line-items", json={
            "category": "banners", "product_type": "banner", "description": "Test banner",
            "quantity": 1, "unit_price_cents": 5000,
        })
        assert li.status_code == 201
        assert li.json()["pricing_snapshot"]["source"] == "user_entered"
    _clear()
