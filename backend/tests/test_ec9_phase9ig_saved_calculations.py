"""EC9 Phase 9I-G - Saved Calculation Library."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from server import app
from app.core.db import db as _db
from app.core.permissions import Perm, permissions_for_role as real_permissions_for_role
from app.deps import get_current_user
import app.deps as deps_module


def _override_as(user: dict):
    async def _dep():
        return user
    return _dep


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override_as(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


PAYLOADS = [
    {"category": "banners", "width_inches": 96, "height_inches": 36, "quantity": 1, "category_inputs": {"selected_pricing_method": "square_foot_plus_addons"}},
    {"category": "rigid_signs", "width_inches": 24, "height_inches": 24, "quantity": 1, "category_inputs": {"hardware_option": "h_stake", "drill_prep_required": True}},
    {"category": "cut_vinyl", "width_inches": 12, "height_inches": 12, "quantity": 1, "category_inputs": {"number_of_colors": "3", "weeding_complexity": "extreme", "masking": True}},
    {"category": "digital_print", "width_inches": 24, "height_inches": 36, "quantity": 1, "category_inputs": {"laminate": True, "quality_mode": "photo", "contour_cut": True}},
    {"category": "vehicle_graphics", "width_inches": None, "height_inches": None, "quantity": 1, "category_inputs": {"vehicle_type": "pickup", "coverage_type": "partial"}},
    {"category": "apparel", "width_inches": None, "height_inches": None, "quantity": 25, "category_inputs": {"garment_type": "short_sleeve_tee", "brand": "gildan_5000", "placement": "front_small"}},
    {"category": "promotional", "width_inches": None, "height_inches": None, "quantity": 100, "category_inputs": {"pricing_method": "per_piece", "unit_price": 2.5, "unit_cost": 1.0}},
    {"category": "services", "width_inches": None, "height_inches": None, "quantity": 1, "category_inputs": {"service_type": "general_labor", "estimated_hours": 2}},
    {"category": "custom", "width_inches": None, "height_inches": None, "quantity": 2, "category_inputs": {"item_name": "Custom", "unit_price": 25.0, "unit_cost_manual": 10.0}},
]


DEFERRED_COLLECTIONS = [
    "pricing_calculation_records",
    "webstores",
    "webstore_products",
    "wrap_lab_projects",
    "wrap_lab_jobs",
    "quotes",
    "orders",
    "quote_line_items",
    "order_items",
    "work_orders",
    "pricing_snapshot_records",
]


async def _save(c: AsyncClient, name: str, calculation_inputs: dict, source_context: str = "pricing_calculator") -> dict:
    r = await c.post("/api/pricing/saved-calculations", json={
        "name": name,
        "notes": "kept for reuse",
        "calculation_inputs": calculation_inputs,
        "source_context": source_context,
    })
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", PAYLOADS, ids=[p["category"] for p in PAYLOADS])
async def test_all_nine_categories_can_be_saved_and_reopened(payload, seeded_users):
    user = seeded_users["user_a"]
    async with await _client_as(user) as c:
        calc_r = await c.post("/api/pricing/calculate", json=payload)
        assert calc_r.status_code == 200, calc_r.text
        authoritative = calc_r.json()

        saved = await _save(c, f"{payload['category']} saved {uuid.uuid4().hex[:6]}", payload)
        assert saved["category"] == payload["category"]
        assert saved["selling_price"] == authoritative["selling_price"]
        assert saved["selling_price_cents"] == round(authoritative["selling_price"] * 100)
        assert saved["calculation_inputs"] == {
            "category": payload["category"],
            "width_inches": payload.get("width_inches"),
            "height_inches": payload.get("height_inches"),
            "quantity": payload.get("quantity") or 1,
            "material_key": None,
            "design_needed": False,
            "install_needed": False,
            "manual_selling_price": None,
            "category_inputs": payload.get("category_inputs") or {},
            "material_profile_id": None,
            "pricing_component_ids": [],
            "saved_item_id": None,
        }
        assert saved["calculation_result"]["selling_price"] == authoritative["selling_price"]
        assert saved["pricing_method_results"]
        assert saved["pricing_reproducibility_ref"]["starter_default_version"]

        reopened = await c.get(f"/api/pricing/saved-calculations/{saved['id']}")
        assert reopened.status_code == 200, reopened.text
        assert reopened.json()["calculation_result"] == saved["calculation_result"]
    _clear()


@pytest.mark.asyncio
async def test_ordinary_calculation_does_not_auto_save_or_create_unrelated_records(seeded_users):
    user = seeded_users["user_a"]
    before = {name: await _db[name].count_documents({"tenant_id": user["tenant_id"]}) for name in DEFERRED_COLLECTIONS}
    before_saved = await _db.pricing_saved_calculations.count_documents({"tenant_id": user["tenant_id"]})
    async with await _client_as(user) as c:
        r = await c.post("/api/pricing/calculate", json=PAYLOADS[0])
        assert r.status_code == 200, r.text
    after = {name: await _db[name].count_documents({"tenant_id": user["tenant_id"]}) for name in DEFERRED_COLLECTIONS}
    assert after == before
    assert await _db.pricing_saved_calculations.count_documents({"tenant_id": user["tenant_id"]}) == before_saved
    _clear()


@pytest.mark.asyncio
async def test_failed_or_missing_price_calculation_cannot_be_saved(seeded_users):
    user = seeded_users["user_a"]
    async with await _client_as(user) as c:
        r = await c.post("/api/pricing/saved-calculations", json={
            "name": "No tier",
            "calculation_inputs": {
                "category": "promotional",
                "quantity": 125,
                "category_inputs": {"pricing_method": "tier_pricing"},
            },
        })
        assert r.status_code == 400
        assert "selling price" in r.json()["detail"]
    assert await _db.pricing_saved_calculations.count_documents({"tenant_id": user["tenant_id"], "name": "No tier"}) == 0
    _clear()


@pytest.mark.asyncio
async def test_search_filter_rename_notes_do_not_rewrite_payload_duplicate_preserves_original(seeded_users):
    user = seeded_users["user_a"]
    async with await _client_as(user) as c:
        saved = await _save(c, "Lobby Banner", PAYLOADS[0])
        original_inputs = saved["calculation_inputs"]
        original_result = saved["calculation_result"]

        filtered = await c.get("/api/pricing/saved-calculations", params={"search": "Lobby", "category": "banners", "archived": False})
        assert filtered.status_code == 200, filtered.text
        assert [item["id"] for item in filtered.json()["items"]] == [saved["id"]]

        patch = await c.patch(f"/api/pricing/saved-calculations/{saved['id']}", json={"name": "Lobby Banner v2", "notes": "renamed only"})
        assert patch.status_code == 200, patch.text
        patched = patch.json()
        assert patched["name"] == "Lobby Banner v2"
        assert patched["notes"] == "renamed only"
        assert patched["calculation_inputs"] == original_inputs
        assert patched["calculation_result"] == original_result

        dup = await c.post(f"/api/pricing/saved-calculations/{saved['id']}/duplicate", json={"name": "Lobby Banner Copy"})
        assert dup.status_code == 201, dup.text
        duplicated = dup.json()
        assert duplicated["id"] != saved["id"]
        assert duplicated["duplicated_from_id"] == saved["id"]
        assert duplicated["created_by_user_id"] == user["id"]
        assert duplicated["calculation_inputs"] == original_inputs
        assert duplicated["calculation_result"] == original_result

        original = await c.get(f"/api/pricing/saved-calculations/{saved['id']}")
        assert original.json()["name"] == "Lobby Banner v2"
    _clear()


@pytest.mark.asyncio
async def test_archive_restore_and_use_calculation_recalculates_fresh_without_mutating_original(seeded_users):
    user = seeded_users["user_a"]
    async with await _client_as(user) as c:
        saved = await _save(c, "Reusable service", PAYLOADS[7])
        archive = await c.post(f"/api/pricing/saved-calculations/{saved['id']}/archive")
        assert archive.status_code == 200, archive.text
        assert archive.json()["archived"] is True

        blocked = await c.post(f"/api/pricing/saved-calculations/{saved['id']}/recalculate")
        assert blocked.status_code == 400

        restored = await c.post(f"/api/pricing/saved-calculations/{saved['id']}/restore")
        assert restored.status_code == 200, restored.text
        assert restored.json()["archived"] is False

        use = await c.post(f"/api/pricing/saved-calculations/{saved['id']}/recalculate")
        assert use.status_code == 200, use.text
        data = use.json()
        assert data["saved_price"] == saved["selling_price"]
        assert data["current_price"] == saved["selling_price"]
        assert data["current_result"]["selling_price"] == saved["selling_price"]
        assert data["transferable"] is True

        after = await c.get(f"/api/pricing/saved-calculations/{saved['id']}")
        assert after.json()["calculation_inputs"] == saved["calculation_inputs"]
        assert after.json()["calculation_result"] == saved["calculation_result"]
    _clear()


@pytest.mark.asyncio
async def test_tenant_isolation_and_pricing_permission_enforcement(monkeypatch, seeded_users):
    user_a, user_b = seeded_users["user_a"], seeded_users["user_b"]
    async with await _client_as(user_a) as c:
        saved = await _save(c, "Tenant A calc", PAYLOADS[0])
    async with await _client_as(user_b) as c:
        assert (await c.get(f"/api/pricing/saved-calculations/{saved['id']}")).status_code == 404
        assert (await c.patch(f"/api/pricing/saved-calculations/{saved['id']}", json={"name": "wrong"})).status_code == 404
        assert (await c.post(f"/api/pricing/saved-calculations/{saved['id']}/recalculate")).status_code == 404

    def test_permissions_for_role(role: str) -> list[str]:
        if role == "pricing-read-only":
            return [Perm.PRICING_READ.value]
        return real_permissions_for_role(role)

    monkeypatch.setattr(deps_module, "permissions_for_role", test_permissions_for_role)
    read_only = {**user_a, "role": "pricing-read-only"}
    async with await _client_as(read_only) as c:
        assert (await c.get("/api/pricing/saved-calculations")).status_code == 200
        create = await c.post("/api/pricing/saved-calculations", json={"name": "Denied", "calculation_inputs": PAYLOADS[0]})
        use = await c.post(f"/api/pricing/saved-calculations/{saved['id']}/recalculate")
        assert create.status_code == 403
        assert use.status_code == 403
    _clear()


@pytest.mark.asyncio
async def test_saved_calculation_indexes_are_defined(clean_db):
    indexes = await clean_db.pricing_saved_calculations.index_information()
    keys = [tuple(spec["key"]) for spec in indexes.values()]
    assert (("id", 1),) in keys
    assert (("tenant_id", 1), ("archived", 1), ("updated_at", -1)) in keys
    assert (("tenant_id", 1), ("category", 1), ("archived", 1), ("updated_at", -1)) in keys
