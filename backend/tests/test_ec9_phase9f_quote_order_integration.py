"""EC9 Phase 9F — Quote, Order, and Order Item Pricing Integration.

Covers: calculator-created / manual / saved-item / canonical-material /
Pricing-Component-based items on Quotes and Orders; suggested-vs-manual price
selection + persistence; Order/Quote-level pricing summaries; Quote-to-Order
conversion (no recalculation); draft recalculation preview + accept/reject;
locked-document recalculation guard; tenant isolation; permissions;
integer-cent boundaries.

Credit-Conservation Rule: targeted pytest only. No `testing_agent`, no full
regression suite, no browser automation. Reuses the `seeded_users` fixture
already used by `test_quotes_ec3.py` / `test_orders_ec3.py`.
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
    r = await c.post("/api/quotes", json={"customer_id": cust_id, "job_name": "Phase 9F quote"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _new_order(c: AsyncClient, cust_id: str) -> str:
    r = await c.post("/api/orders", json={"customer_id": cust_id, "job_name": "Phase 9F order"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


CALC_PAYLOAD = {
    "description": "Consult", "quantity": 1, "unit_price_cents": 0, "category": "services",
    "category_inputs": {"service_type": "general_labor", "estimated_hours": 2, "crew_size": 1, "complexity": "easy"},
    "selected_price_source": "suggested",
}


# ============================================================
# Add calculated / manual items to Quote and Order
# ============================================================

@pytest.mark.asyncio
async def test_add_calculated_item_to_quote(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json=CALC_PAYLOAD)
        assert r.status_code == 201, r.text
        item = r.json()
        assert item["pricing_status"] == "calculated"
        assert item["selected_price_source"] == "suggested"
        assert item["unit_price_cents"] == item["suggested_price_cents"]
        assert item["unit_price_cents"] > 0
        assert item["pricing_snapshot"]["source"] == "calculator"
        assert item["estimated_cost_cents"] is not None
    _clear()


@pytest.mark.asyncio
async def test_add_calculated_item_to_order_as_order_item(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        oid = await _new_order(c, cust)
        r = await c.post(f"/api/orders/{oid}/items", json=CALC_PAYLOAD)
        assert r.status_code == 201, r.text
        item = r.json()
        assert item["pricing_status"] == "calculated"
        assert item["unit_price_cents"] == item["suggested_price_cents"]
        assert item["pricing_snapshot"]["source"] == "calculator"
    _clear()


@pytest.mark.asyncio
async def test_manual_only_item_no_calculator_used(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json={
            "description": "Hand-typed price, no category", "quantity": 1, "unit_price_cents": 4200,
        })
        assert r.status_code == 201, r.text
        item = r.json()
        assert item["pricing_status"] == "manual"
        assert item["selected_price_source"] == "manual"
        assert item["suggested_price_cents"] is None
        assert item["unit_price_cents"] == 4200
        assert item["pricing_snapshot"]["source"] == "user_entered"
    _clear()


@pytest.mark.asyncio
async def test_manual_price_available_even_with_category_selected(seeded_users):
    """Manual pricing must remain available for every category — even one
    that also has a calculator engine."""
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json={
            "description": "Banner, manually priced", "quantity": 1, "unit_price_cents": 9999, "category": "banners",
        })
        assert r.status_code == 201, r.text
        item = r.json()
        # category given but no calculator signal -> stays a pure manual item (backward compatible).
        assert item["pricing_status"] == "manual"
        assert item["unit_price_cents"] == 9999
    _clear()


# ============================================================
# Saved-item / canonical-material / Pricing-Component references
# ============================================================

@pytest.mark.asyncio
async def test_canonical_material_reference_item(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        mat_id = f"mat-{uuid.uuid4().hex[:8]}"
        await _db.materials.insert_one({"id": mat_id, "tenant_id": user["tenant_id"], "name": "White Vinyl"})
        r = await c.post(f"/api/pricing/material-profiles/materials/{mat_id}", json={
            "pricing_unit": "per_sqft", "normalized_cost_basis": 1.5, "suggested_sell_rate": 4.0,
            "category_applicability": ["banners"],
        })
        assert r.status_code == 201, r.text
        profile_id = r.json()["id"]

        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json={
            "description": "Banner w/ canonical material", "quantity": 1, "unit_price_cents": 0,
            "category": "banners", "width_inches": 24, "height_inches": 36,
            "category_inputs": {}, "material_profile_id": profile_id, "selected_price_source": "suggested",
        })
        assert r.status_code == 201, r.text
        item = r.json()
        assert item["material_profile_id"] == profile_id
        assert item["pricing_snapshot"]["material_profile_id"] == profile_id
        assert item["unit_price_cents"] > 0
    _clear()


@pytest.mark.asyncio
async def test_pricing_component_reference_item(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        r = await c.post("/api/pricing/components", json={
            "key": "rush-fee-9f", "name": "Rush Fee", "charge_type": "rush_charge", "percent": 20,
            "category_applicability": ["services"],
        })
        assert r.status_code == 201, r.text
        comp_id = r.json()["id"]

        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json={
            "description": "Rushed service", "quantity": 1, "unit_price_cents": 0, "category": "services",
            "category_inputs": {"service_type": "general_labor", "estimated_hours": 1},
            "pricing_component_ids": [comp_id], "selected_price_source": "suggested",
        })
        assert r.status_code == 201, r.text
        item = r.json()
        assert item["pricing_component_ids"] == [comp_id]
        assert item["pricing_snapshot"]["pricing_component_ids"] == [comp_id]
    _clear()


@pytest.mark.asyncio
async def test_saved_item_reference_item(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        r = await c.post("/api/pricing/saved-items", json={"name": "Standard Banner 2x4", "category": "banners"})
        assert r.status_code == 201, r.text
        saved_id = r.json()["id"]

        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json={
            "description": "Standard Banner 2x4", "quantity": 2, "unit_price_cents": 0, "category": "banners",
            "width_inches": 24, "height_inches": 48, "category_inputs": {}, "saved_item_id": saved_id,
            "selected_price_source": "suggested",
        })
        assert r.status_code == 201, r.text
        item = r.json()
        assert item["saved_item_id"] == saved_id
        assert item["pricing_snapshot"]["saved_item_id"] == saved_id
    _clear()


# ============================================================
# Manual vs suggested selection + persistence
# ============================================================

@pytest.mark.asyncio
async def test_selected_price_source_manual_wins_over_suggested(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        payload = {**CALC_PAYLOAD, "selected_price_source": "manual", "manual_price_cents": 5000,
                   "manual_override_reason": "shop rate"}
        r = await c.post(f"/api/quotes/{qid}/line-items", json=payload)
        assert r.status_code == 201, r.text
        item = r.json()
        assert item["selected_price_source"] == "manual"
        assert item["unit_price_cents"] == 5000          # manual wins
        assert item["suggested_price_cents"] > 0          # but suggested still recorded, visible separately
        assert item["suggested_price_cents"] != 5000
        assert item["manual_price_cents"] == 5000
    _clear()


@pytest.mark.asyncio
async def test_client_cannot_spoof_suggested_price(seeded_users):
    """Backend-authoritative: even if the client sends a fabricated
    unit_price_cents, selecting 'suggested' forces the server-computed
    value."""
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        payload = {**CALC_PAYLOAD, "unit_price_cents": 1}  # client tries to fake a $0.01 price
        r = await c.post(f"/api/quotes/{qid}/line-items", json=payload)
        assert r.status_code == 201, r.text
        item = r.json()
        assert item["unit_price_cents"] != 1
        assert item["unit_price_cents"] == item["suggested_price_cents"]
    _clear()


# ============================================================
# Order-level pricing summary
# ============================================================

@pytest.mark.asyncio
async def test_order_level_pricing_summary(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        oid = await _new_order(c, cust)
        await c.post(f"/api/orders/{oid}/items", json=CALC_PAYLOAD)
        await c.post(f"/api/orders/{oid}/items", json={"description": "manual add-on", "quantity": 1, "unit_price_cents": 1000})
        r = await c.get(f"/api/orders/{oid}")
        assert r.status_code == 200
        summary = r.json()["pricing_summary"]
        assert summary["item_count"] == 2
        assert summary["total_manual_price_amount_cents"] == 1000
        assert summary["total_suggested_price_amount_cents"] > 0
        assert summary["selected_final_total_cents"] == r.json()["totals"]["total_cents"]
        assert summary["estimated_total_profit_cents"] >= 0
    _clear()


@pytest.mark.asyncio
async def test_quote_level_pricing_summary(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        await c.post(f"/api/quotes/{qid}/line-items", json=CALC_PAYLOAD)
        r = await c.get(f"/api/quotes/{qid}")
        assert r.status_code == 200
        summary = r.json()["pricing_summary"]
        assert summary["item_count"] == 1
        assert summary["total_estimated_cost_cents"] > 0
    _clear()


# ============================================================
# Order Item / Quote Line Item detail (full document already returned)
# ============================================================

@pytest.mark.asyncio
async def test_order_item_detail_contains_full_pricing_context(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        oid = await _new_order(c, cust)
        r = await c.post(f"/api/orders/{oid}/items", json=CALC_PAYLOAD)
        r = await c.get(f"/api/orders/{oid}")
        assert r.status_code == 200
        detail = r.json()["items"][0]
        for key in ("category_inputs", "source_labels", "calculation_warnings", "pricing_snapshot",
                    "suggested_price_cents", "estimated_cost_cents", "estimated_profit_cents",
                    "estimated_margin_percent", "price_selected_by_user_id"):
            assert key in detail
        assert detail["pricing_snapshot"]["breakdown"]
        assert detail["pricing_snapshot"]["formula_version"]
    _clear()


# ============================================================
# Quote-to-Order conversion — no recalculation
# ============================================================

@pytest.mark.asyncio
async def test_quote_to_order_conversion_preserves_calculated_item_exactly(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json=CALC_PAYLOAD)
        q_item = r.json()
        r = await c.post(f"/api/quotes/{qid}/convert-to-order", json={})
        assert r.status_code == 200, r.text
        order = r.json()["order"]
        r = await c.get(f"/api/orders/{order['id']}")
        o_items = r.json()["items"]
        assert len(o_items) == 1
        o_item = o_items[0]
        assert o_item["unit_price_cents"] == q_item["unit_price_cents"]
        assert o_item["suggested_price_cents"] == q_item["suggested_price_cents"]
        assert o_item["selected_price_source"] == q_item["selected_price_source"]
        assert o_item["category_inputs"] == q_item["category_inputs"]
        assert o_item["pricing_snapshot"]["snapshot_id"] == q_item["pricing_snapshot"]["snapshot_id"]  # cloned as-is
        assert o_item["calculation_warnings"] == q_item["calculation_warnings"]
    _clear()


@pytest.mark.asyncio
async def test_quote_to_order_conversion_preserves_manual_item(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json={"description": "manual", "quantity": 1, "unit_price_cents": 12345})
        q_item = r.json()
        r = await c.post(f"/api/quotes/{qid}/convert-to-order", json={})
        order = r.json()["order"]
        r = await c.get(f"/api/orders/{order['id']}")
        o_item = r.json()["items"][0]
        assert o_item["unit_price_cents"] == 12345 == q_item["unit_price_cents"]
        assert o_item["pricing_status"] == "manual"
    _clear()


@pytest.mark.asyncio
async def test_conversion_is_idempotent_and_does_not_duplicate_pricing_fields(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        await c.post(f"/api/quotes/{qid}/line-items", json=CALC_PAYLOAD)
        r1 = await c.post(f"/api/quotes/{qid}/convert-to-order", json={})
        r2 = await c.post(f"/api/quotes/{qid}/convert-to-order", json={})
        assert r1.json()["order"]["id"] == r2.json()["order"]["id"]
        assert r2.json()["already_converted"] is True
    _clear()


# ============================================================
# Recalculation workflow (draft only): preview -> accept / reject
# ============================================================

@pytest.mark.asyncio
async def test_recalculate_preview_does_not_mutate_draft_quote_item(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json=CALC_PAYLOAD)
        item_id = r.json()["id"]
        old_price = r.json()["unit_price_cents"]

        r = await c.post(f"/api/quotes/{qid}/line-items/{item_id}/recalculate-preview", json={
            "category_inputs": {"service_type": "general_labor", "estimated_hours": 10, "crew_size": 1, "complexity": "easy"},
        })
        assert r.status_code == 200, r.text
        preview = r.json()
        assert preview["old"]["unit_price_cents"] == old_price
        assert preview["new"]["unit_price_cents"] != old_price  # candidate differs

        # rejection = do nothing further; confirm old item is untouched
        r = await c.get(f"/api/quotes/{qid}/line-items")
        assert r.json()["items"][0]["unit_price_cents"] == old_price
    _clear()


@pytest.mark.asyncio
async def test_accepting_recalculation_updates_item_and_preserves_previous_snapshot(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json=CALC_PAYLOAD)
        item_id = r.json()["id"]
        old_snapshot_id = r.json()["pricing_snapshot"]["snapshot_id"]
        old_price = r.json()["unit_price_cents"]

        new_inputs = {"service_type": "general_labor", "estimated_hours": 10, "crew_size": 1, "complexity": "easy"}
        r = await c.patch(f"/api/quotes/{qid}/line-items/{item_id}", json={"category_inputs": new_inputs, "recalculate": True})
        assert r.status_code == 200, r.text
        updated = r.json()
        assert updated["unit_price_cents"] != old_price
        assert updated["last_recalculated_at"] is not None
        assert updated["previous_pricing_snapshot"]["snapshot_id"] == old_snapshot_id  # historical snapshot preserved
        assert updated["pricing_snapshot"]["snapshot_id"] != old_snapshot_id
    _clear()


@pytest.mark.asyncio
async def test_rejecting_recalculation_leaves_item_unchanged(seeded_users):
    """Rejection = the client simply never PATCHes. Old item stays byte-identical."""
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json=CALC_PAYLOAD)
        item_id, before = r.json()["id"], r.json()
        await c.post(f"/api/quotes/{qid}/line-items/{item_id}/recalculate-preview", json={
            "category_inputs": {"service_type": "general_labor", "estimated_hours": 99},
        })
        r = await c.get(f"/api/quotes/{qid}/line-items")
        after = r.json()["items"][0]
        assert after["unit_price_cents"] == before["unit_price_cents"]
        assert after["pricing_snapshot"]["snapshot_id"] == before["pricing_snapshot"]["snapshot_id"]
    _clear()


@pytest.mark.asyncio
async def test_recalculate_preview_blocked_for_non_draft_quote(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json=CALC_PAYLOAD)
        item_id = r.json()["id"]
        r = await c.post(f"/api/quotes/{qid}/status", json={"status": "sent"})
        assert r.status_code == 200, r.text
        r = await c.post(f"/api/quotes/{qid}/line-items/{item_id}/recalculate-preview", json={})
        assert r.status_code == 400
    _clear()


@pytest.mark.asyncio
async def test_recalculate_preview_blocked_for_non_draft_order(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        oid = await _new_order(c, cust)
        r = await c.post(f"/api/orders/{oid}/items", json=CALC_PAYLOAD)
        item_id = r.json()["id"]
        r = await c.post(f"/api/orders/{oid}/status", json={"status": "confirmed"})
        assert r.status_code == 200, r.text
        r = await c.post(f"/api/orders/{oid}/items/{item_id}/recalculate-preview", json={})
        assert r.status_code == 400
    _clear()


# ============================================================
# Tenant isolation + permissions + integer-cent boundaries
# ============================================================

@pytest.mark.asyncio
async def test_tenant_isolation_on_quote_line_items(seeded_users):
    user_a, user_b = seeded_users["user_a"], seeded_users["user_b"]
    cust_a = await _seed_customer(user_a["tenant_id"])
    async with await _client_as(user_a) as c:
        qid = await _new_quote(c, cust_a)
        await c.post(f"/api/quotes/{qid}/line-items", json=CALC_PAYLOAD)
    async with await _client_as(user_b) as c:
        r = await c.get(f"/api/quotes/{qid}")
        assert r.status_code == 404  # tenant B cannot see tenant A's quote
    _clear()


@pytest.mark.asyncio
async def test_permission_denied_for_role_without_quote_write(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
    no_perms_user = {**user, "role": "no-perms-role-9f"}
    async with await _client_as(no_perms_user) as c:
        r = await c.post(f"/api/quotes/{qid}/line-items", json=CALC_PAYLOAD)
        assert r.status_code == 403
    _clear()


@pytest.mark.asyncio
async def test_integer_cent_boundaries_on_calculated_and_manual_items(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json=CALC_PAYLOAD)
        item = r.json()
        assert isinstance(item["unit_price_cents"], int)
        assert isinstance(item["suggested_price_cents"], int)
        assert isinstance(item["estimated_cost_cents"], int)
        r = await c.post(f"/api/quotes/{qid}/line-items", json={"description": "penny item", "quantity": 3, "unit_price_cents": 1})
        item2 = r.json()
        assert item2["line_subtotal_cents"] == 3
    _clear()
