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
from app.core.permissions import Perm, permissions_for_role as real_permissions_for_role
from app.core.db import db as _db
from app.deps import get_current_user
import app.routers.orders as orders_router
import app.routers.quotes as quotes_router
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


PARITY_CATEGORY_PAYLOADS = [
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


DEFERRED_CONSUMER_COLLECTIONS = [
    "pricing_calculation_records",
    "pricing_saved_calculations",
    "webstores",
    "webstore_products",
    "wrap_lab_projects",
    "wrap_lab_jobs",
]


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
@pytest.mark.parametrize("case", PARITY_CATEGORY_PAYLOADS, ids=[case["category"] for case in PARITY_CATEGORY_PAYLOADS])
async def test_quote_and_order_items_support_same_nine_pricing_categories(case, seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    payload = {
        "description": f"{case['category']} parity item",
        "unit_price_cents": 1,
        "selected_price_source": "suggested",
        **case,
    }
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        oid = await _new_order(c, cust)
        quote_r = await c.post(f"/api/quotes/{qid}/line-items", json=payload)
        order_r = await c.post(f"/api/orders/{oid}/items", json=payload)

        assert quote_r.status_code == 201, quote_r.text
        assert order_r.status_code == 201, order_r.text
        quote_item = quote_r.json()
        order_item = order_r.json()
        assert quote_item["category"] == order_item["category"] == case["category"]
        assert quote_item["unit_price_cents"] == order_item["unit_price_cents"]
        assert quote_item["unit_price_cents"] == quote_item["suggested_price_cents"]
        assert order_item["unit_price_cents"] == order_item["suggested_price_cents"]
        assert quote_item["unit_price_cents"] > 0
        assert quote_item["pricing_snapshot"]["selected_selling_price_dollars"] == order_item["pricing_snapshot"]["selected_selling_price_dollars"]
        assert quote_item["pricing_snapshot"]["selected_pricing_method"] == order_item["pricing_snapshot"]["selected_pricing_method"]
        assert quote_item["pricing_snapshot"].get("pricing_method_results") == order_item["pricing_snapshot"].get("pricing_method_results")
        assert quote_item["pricing_snapshot"].get("detail_sections") == order_item["pricing_snapshot"].get("detail_sections")
    _clear()


@pytest.mark.asyncio
async def test_failed_calculated_result_cannot_be_transferred_to_quote_or_order_item(monkeypatch, seeded_users):
    async def failed_calculation(**kwargs):
        return {
            "category": kwargs["category"],
            "selling_price": None,
            "pricing_method_used": "manual_required_no_tier_match",
            "pricing_method_results": [
                {
                    "method_id": "tier_pricing",
                    "display_name": "Tier pricing",
                    "amount": None,
                    "available": False,
                    "selected": True,
                    "status": ["manual_price_required"],
                    "errors": ["no_exact_tier_match"],
                }
            ],
            "calculation_warnings": [],
            "errors": ["no_exact_tier_match"],
            "mutated": False,
            "persistent_entities_created": [],
        }

    monkeypatch.setattr(quotes_router, "calculate_for_references", failed_calculation)
    monkeypatch.setattr(orders_router, "calculate_for_references", failed_calculation)
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    payload = {
        "description": "Unavailable promotional tier",
        "quantity": 125,
        "unit_price_cents": 9999,
        "category": "promotional",
        "category_inputs": {"pricing_method": "tier_pricing"},
        "selected_price_source": "suggested",
    }
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        oid = await _new_order(c, cust)
        quote_r = await c.post(f"/api/quotes/{qid}/line-items", json=payload)
        order_r = await c.post(f"/api/orders/{oid}/items", json=payload)

        assert quote_r.status_code == 400
        assert order_r.status_code == 400
        assert quote_r.json()["detail"] == "Calculated pricing result is not transferable"
        assert order_r.json()["detail"] == "Calculated pricing result is not transferable"
        assert await _db.quote_line_items.count_documents({"tenant_id": user["tenant_id"], "quote_id": qid}) == 0
        assert await _db.order_items.count_documents({"tenant_id": user["tenant_id"], "order_id": oid}) == 0
    _clear()


@pytest.mark.asyncio
async def test_price_calculation_requires_pricing_permission_in_quote_and_order_flows(monkeypatch, seeded_users):
    def test_permissions_for_role(role: str) -> list[str]:
        if role == "quote-order-no-pricing":
            return [Perm.QUOTE_WRITE.value, Perm.ORDER_WRITE.value]
        return real_permissions_for_role(role)

    monkeypatch.setattr(deps_module, "permissions_for_role", test_permissions_for_role)
    monkeypatch.setattr(quotes_router, "permissions_for_role", test_permissions_for_role)
    monkeypatch.setattr(orders_router, "permissions_for_role", test_permissions_for_role)

    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        oid = await _new_order(c, cust)
    no_pricing_user = {**user, "role": "quote-order-no-pricing"}
    async with await _client_as(no_pricing_user) as c:
        quote_r = await c.post(f"/api/quotes/{qid}/line-items", json=CALC_PAYLOAD)
        order_r = await c.post(f"/api/orders/{oid}/items", json=CALC_PAYLOAD)
        manual_r = await c.post(f"/api/quotes/{qid}/line-items", json={
            "description": "Manual allowed", "quantity": 1, "unit_price_cents": 4200,
        })
        assert quote_r.status_code == 403
        assert order_r.status_code == 403
        assert quote_r.json()["detail"] == "Missing permission: pricing:calculate"
        assert order_r.json()["detail"] == "Missing permission: pricing:calculate"
        assert manual_r.status_code == 201, manual_r.text
    _clear()


@pytest.mark.asyncio
async def test_quote_order_calculated_items_do_not_create_saved_calculation_webstore_or_wrap_lab_records(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    before = {
        collection: await _db[collection].count_documents({"tenant_id": user["tenant_id"]})
        for collection in DEFERRED_CONSUMER_COLLECTIONS
    }
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        oid = await _new_order(c, cust)
        quote_r = await c.post(f"/api/quotes/{qid}/line-items", json=CALC_PAYLOAD)
        order_r = await c.post(f"/api/orders/{oid}/items", json=CALC_PAYLOAD)
        assert quote_r.status_code == 201, quote_r.text
        assert order_r.status_code == 201, order_r.text

    after = {
        collection: await _db[collection].count_documents({"tenant_id": user["tenant_id"]})
        for collection in DEFERRED_CONSUMER_COLLECTIONS
    }
    assert after == before
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
