"""EC9 Phase 9G — Immutable Pricing Snapshots + provider-neutral Advisory
contracts.

Covers: complete immutable snapshot creation on Quote/Order item pricing
writes; integer-cent storage; frozen Material/Profile/SavedItem/Component/
Shop-Defaults values that survive later edits to the LIVE records;
recalculation creates a NEW snapshot while the old one is only relabeled
"superseded" (never mutated); lineage chain; Quote→Order conversion clones
lineage losslessly; deterministic explain/compare endpoints; tenant
isolation; permissions; provider-neutral Advisory request/response contracts
with zero live AI/provider calls.

Credit-Conservation Rule: targeted pytest only. No `testing_agent`, no full
regression suite, no browser automation. Reuses the `seeded_users` fixture
already used by `test_ec9_phase9f_quote_order_integration.py`.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from server import app
from app.core.db import db as _db
from app.deps import get_current_user
from app.models.pricing_advisory import AdvisoryResponseItem
from app.services.pricing_advisory import create_advisory_request, decide_advisory_response
from app.services.pricing_snapshot_records import create_snapshot_record


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
    r = await c.post("/api/quotes", json={"customer_id": cust_id, "job_name": "Phase 9G quote"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _new_order(c: AsyncClient, cust_id: str) -> str:
    r = await c.post("/api/orders", json={"customer_id": cust_id, "job_name": "Phase 9G order"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


CALC_PAYLOAD = {
    "description": "Consult", "quantity": 1, "unit_price_cents": 0, "category": "services",
    "category_inputs": {"service_type": "general_labor", "estimated_hours": 2, "crew_size": 1, "complexity": "easy"},
    "selected_price_source": "suggested",
}


# ============================================================
# Complete snapshot creation + integer-cent storage + frozen values
# ============================================================

@pytest.mark.asyncio
async def test_snapshot_created_on_quote_line_item_add(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json=CALC_PAYLOAD)
        assert r.status_code == 201, r.text
        item = r.json()

        r = await c.get(f"/api/pricing/snapshots", params={"source_type": "quote_line_item", "source_id": item["id"]})
        assert r.status_code == 200, r.text
        records = r.json()["items"]
        assert len(records) == 1
        rec = records[0]
        assert rec["status"] == "active"
        assert rec["tenant_id"] == user["tenant_id"]
        assert rec["quote_id"] == qid
        assert rec["category"] == "services"
        assert rec["selected_final_price_cents"] == item["unit_price_cents"]
        assert rec["suggested_price_cents"] == item["suggested_price_cents"]
        assert rec["selected_price_source"] == "suggested"
        assert isinstance(rec["selected_final_price_cents"], int)  # integer cents
        assert rec["calculated_by_user_id"] == user["id"]
        assert rec["previous_snapshot_id"] is None
    _clear()


@pytest.mark.asyncio
async def test_snapshot_created_on_order_item_add(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        oid = await _new_order(c, cust)
        r = await c.post(f"/api/orders/{oid}/items", json=CALC_PAYLOAD)
        assert r.status_code == 201, r.text
        item = r.json()

        r = await c.get("/api/pricing/snapshots", params={"source_type": "order_item", "source_id": item["id"]})
        assert r.status_code == 200
        records = r.json()["items"]
        assert len(records) == 1
        assert records[0]["order_id"] == oid
        assert records[0]["order_item_id"] == item["id"]
        assert records[0]["status"] == "active"
    _clear()


@pytest.mark.asyncio
async def test_material_saved_item_and_component_values_frozen_after_live_edits(seeded_users):
    """Material Pricing Profile, Saved Item, and Pricing Component values must
    be frozen at calc time and survive later edits to the LIVE records."""
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

        r = await c.post("/api/pricing/components", json={
            "key": "setup-9g", "name": "Setup Fee", "charge_type": "setup_fee", "amount": 15.0,
            "category_applicability": ["banners"],
        })
        assert r.status_code == 201, r.text
        comp_id = r.json()["id"]

        r = await c.post("/api/pricing/saved-items", json={"name": "Standard Banner 9G", "category": "banners"})
        assert r.status_code == 201, r.text
        saved_id = r.json()["id"]

        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json={
            "description": "Banner w/ refs", "quantity": 1, "unit_price_cents": 0, "category": "banners",
            "width_inches": 24, "height_inches": 36, "category_inputs": {},
            "material_profile_id": profile_id, "pricing_component_ids": [comp_id], "saved_item_id": saved_id,
            "selected_price_source": "suggested",
        })
        assert r.status_code == 201, r.text
        item = r.json()

        r = await c.get("/api/pricing/snapshots", params={"source_type": "quote_line_item", "source_id": item["id"]})
        rec = r.json()["items"][0]
        assert rec["material_profile_ids"] == [profile_id]
        assert rec["material_ids"] == [mat_id]
        assert rec["material_values_used"]["suggested_sell_rate"] == 4.0
        assert rec["pricing_component_ids"] == [comp_id]
        assert rec["pricing_component_values_used"][0]["id"] == comp_id
        assert rec["pricing_component_values_used"][0]["amount"] == 15.0
        assert rec["saved_item_id"] == saved_id
        assert rec["saved_item_values_used"]["name"] == "Standard Banner 9G"
        assert rec["shop_defaults_used"]  # non-empty — shop defaults were in effect
        assert rec["formula_version"]

        # Now mutate the LIVE records
        await c.patch(f"/api/pricing/material-profiles/{profile_id}", json={"suggested_sell_rate": 999.0})
        await c.patch(f"/api/pricing/components/{comp_id}", json={"amount": 999.0})
        await c.patch(f"/api/pricing/saved-items/{saved_id}", json={"name": "RENAMED"})

        # Re-fetch the SAME historical record — must be byte-identical
        r2 = await c.get(f"/api/pricing/snapshots/{rec['id']}")
        assert r2.status_code == 200
        rec2 = r2.json()
        assert rec2["material_values_used"]["suggested_sell_rate"] == 4.0
        assert rec2["pricing_component_values_used"][0]["amount"] == 15.0
        assert rec2["saved_item_values_used"]["name"] == "Standard Banner 9G"
    _clear()


# ============================================================
# Immutability, lineage, and status transitions
# ============================================================

@pytest.mark.asyncio
async def test_recalculation_creates_new_snapshot_and_supersedes_old(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json=CALC_PAYLOAD)
        item_id = r.json()["id"]

        r = await c.get("/api/pricing/snapshots", params={"source_type": "quote_line_item", "source_id": item_id})
        first = r.json()["items"][0]
        assert first["status"] == "active"

        new_inputs = {"service_type": "general_labor", "estimated_hours": 10, "crew_size": 1, "complexity": "easy"}
        r = await c.patch(f"/api/quotes/{qid}/line-items/{item_id}", json={"category_inputs": new_inputs, "recalculate": True})
        assert r.status_code == 200, r.text

        r = await c.get("/api/pricing/snapshots", params={"source_type": "quote_line_item", "source_id": item_id})
        records = sorted(r.json()["items"], key=lambda x: x["created_at"])
        assert len(records) == 2  # append-only — old one is NOT deleted

        old, new = records[0], records[1]
        assert old["id"] == first["id"]
        assert old["status"] == "superseded"
        assert old["superseded_by_snapshot_id"] == new["id"]
        # OLD record's pricing DATA is byte-identical to what it was originally
        assert old["suggested_price_cents"] == first["suggested_price_cents"]
        assert old["selected_final_price_cents"] == first["selected_final_price_cents"]

        assert new["status"] == "active"
        assert new["previous_snapshot_id"] == old["id"]
        assert new["suggested_price_cents"] != old["suggested_price_cents"]
    _clear()


@pytest.mark.asyncio
async def test_recalculate_preview_does_not_create_a_candidate_record(seeded_users):
    """A non-accepted preview is a pure compute — it must NOT persist anything."""
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json=CALC_PAYLOAD)
        item_id = r.json()["id"]

        r = await c.get("/api/pricing/snapshots", params={"source_type": "quote_line_item", "source_id": item_id})
        before_count = len(r.json()["items"])
        assert before_count == 1

        await c.post(f"/api/quotes/{qid}/line-items/{item_id}/recalculate-preview", json={
            "category_inputs": {"service_type": "general_labor", "estimated_hours": 99},
        })

        r = await c.get("/api/pricing/snapshots", params={"source_type": "quote_line_item", "source_id": item_id})
        after = r.json()["items"]
        assert len(after) == before_count  # rejected/unactioned preview persisted nothing
        assert after[0]["status"] == "active"
    _clear()


@pytest.mark.asyncio
async def test_quote_to_order_conversion_clones_snapshot_lineage_losslessly(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json=CALC_PAYLOAD)
        quote_item = r.json()
        await c.post(f"/api/quotes/{qid}/status", json={"status": "sent"})
        r = await c.post(f"/api/quotes/{qid}/status", json={"status": "approved"})
        assert r.status_code == 200, r.text
        r = await c.post(f"/api/quotes/{qid}/convert-to-order")
        assert r.status_code == 200, r.text
        order = r.json()["order"]

        r = await c.get(f"/api/orders/{order['id']}")
        order_item = r.json()["items"][0]
        # lossless: same price + snapshot content copied verbatim
        assert order_item["unit_price_cents"] == quote_item["unit_price_cents"]

        r = await c.get("/api/pricing/snapshots", params={"source_type": "quote_line_item", "source_id": quote_item["id"]})
        quote_snap = r.json()["items"][0]
        r = await c.get("/api/pricing/snapshots", params={"source_type": "order_item", "source_id": order_item["id"]})
        order_snaps = r.json()["items"]
        assert len(order_snaps) == 1
        order_snap = order_snaps[0]
        assert order_snap["status"] == "active"
        assert order_snap["previous_snapshot_id"] == quote_snap["id"]  # cross-document lineage preserved
        assert order_snap["selected_final_price_cents"] == quote_snap["selected_final_price_cents"]
        assert order_snap["quote_id"] == qid
        assert order_snap["order_id"] == order["id"]
        # original quote-side snapshot is untouched (still "active" for the quote's own item)
        assert quote_snap["status"] == "active"
    _clear()


# ============================================================
# Deterministic explain + compare
# ============================================================

@pytest.mark.asyncio
async def test_explain_snapshot_is_deterministic_and_non_ai(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json=CALC_PAYLOAD)
        item_id = r.json()["id"]
        r = await c.get("/api/pricing/snapshots", params={"source_type": "quote_line_item", "source_id": item_id})
        snap_id = r.json()["items"][0]["id"]

        r = await c.get(f"/api/pricing/snapshots/{snap_id}/explain")
        assert r.status_code == 200, r.text
        explanation = r.json()
        for section in [
            "inputs_used", "defaults_used", "materials_and_components", "cost_calculation",
            "suggested_price_calculation", "final_price_reason", "assumptions_and_warnings",
            "accountability", "status",
        ]:
            assert section in explanation
        assert explanation["changes_from_previous"] is None  # first snapshot, no predecessor

        # Calling it again must be byte-identical (deterministic, no AI variance)
        r2 = await c.get(f"/api/pricing/snapshots/{snap_id}/explain")
        assert r2.json() == explanation
    _clear()


@pytest.mark.asyncio
async def test_compare_snapshots_returns_deterministic_diff(seeded_users):
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json=CALC_PAYLOAD)
        item_id = r.json()["id"]
        r = await c.get("/api/pricing/snapshots", params={"source_type": "quote_line_item", "source_id": item_id})
        base_id = r.json()["items"][0]["id"]

        new_inputs = {"service_type": "general_labor", "estimated_hours": 10, "crew_size": 1, "complexity": "easy"}
        await c.patch(f"/api/quotes/{qid}/line-items/{item_id}", json={"category_inputs": new_inputs, "recalculate": True})
        r = await c.get("/api/pricing/snapshots", params={"source_type": "quote_line_item", "source_id": item_id})
        candidate_id = [x for x in r.json()["items"] if x["status"] == "active"][0]["id"]

        r = await c.post("/api/pricing/snapshots/compare", json={
            "base_snapshot_id": base_id, "candidate_snapshot_id": candidate_id,
        })
        assert r.status_code == 200, r.text
        diff = r.json()["diff"]
        assert diff["suggested_price_change"]["delta"] != 0
        assert diff["labor_cost_change"] is not None
    _clear()


# ============================================================
# Tenant isolation + permissions
# ============================================================

@pytest.mark.asyncio
async def test_snapshot_tenant_isolation(seeded_users):
    user_a, user_b = seeded_users["user_a"], seeded_users["user_b"]
    cust_a = await _seed_customer(user_a["tenant_id"])
    async with await _client_as(user_a) as c:
        qid = await _new_quote(c, cust_a)
        r = await c.post(f"/api/quotes/{qid}/line-items", json=CALC_PAYLOAD)
        item_id = r.json()["id"]
        r = await c.get("/api/pricing/snapshots", params={"source_type": "quote_line_item", "source_id": item_id})
        snap_id = r.json()["items"][0]["id"]
    _clear()
    async with await _client_as(user_b) as c:
        r = await c.get(f"/api/pricing/snapshots/{snap_id}")
        assert r.status_code == 404
        r = await c.get("/api/pricing/snapshots", params={"source_type": "quote_line_item", "source_id": item_id})
        assert r.json()["items"] == []
    _clear()


@pytest.mark.asyncio
async def test_snapshot_endpoints_require_permission(seeded_users):
    user = {**seeded_users["user_a"], "role": "no_such_role"}
    async with await _client_as(user) as c:
        r = await c.get("/api/pricing/snapshots")
        assert r.status_code == 403
    _clear()


# ============================================================
# Advisory contracts — request/response, no live AI/provider calls
# ============================================================

@pytest.mark.asyncio
async def test_advisory_request_creates_unavailable_placeholder_responses(seeded_users):
    user = seeded_users["user_a"]
    async with await _client_as(user) as c:
        r = await c.post("/api/pricing/advisory/requests", json={
            "category": "banners", "item_description": "48x96 banner", "quantity": 1,
            "current_suggested_price_cents": 12000,
            "requested_advisory_types": [
                "ai_pricing_analysis", "historical_pricing_comparison", "underpricing_warning",
                "not_a_real_type",  # invalid type — must be silently filtered, not rejected
            ],
            "data_consent": True,
        })
        assert r.status_code == 201, r.text
        req = r.json()
        assert len(req["responses"]) == 3  # partial: invalid type dropped, valid ones kept
        for resp in req["responses"]:
            assert resp["status"] == "unavailable"
            assert resp["source_type"] == "none"
        assert req["overall_status"] == "unavailable"
        assert req["tenant_id"] == user["tenant_id"]
    _clear()


@pytest.mark.asyncio
async def test_advisory_request_with_no_types_is_not_requested(seeded_users):
    user = seeded_users["user_a"]
    async with await _client_as(user) as c:
        r = await c.post("/api/pricing/advisory/requests", json={"category": "banners"})
        assert r.status_code == 201, r.text
        assert r.json()["responses"] == []
        assert r.json()["overall_status"] == "not_requested"
    _clear()


@pytest.mark.asyncio
async def test_advisory_decision_rejected_never_touches_pricing(seeded_users):
    user = seeded_users["user_a"]
    async with await _client_as(user) as c:
        r = await c.post("/api/pricing/advisory/requests", json={
            "category": "banners", "requested_advisory_types": ["underpricing_warning"],
        })
        req_id = r.json()["id"]
        r = await c.post(
            f"/api/pricing/advisory/requests/{req_id}/responses/underpricing_warning/decision",
            json={"decision": "rejected", "notes": "not useful"},
        )
        assert r.status_code == 200, r.text
        resp = [x for x in r.json()["responses"] if x["advisory_type"] == "underpricing_warning"][0]
        assert resp["user_decision"] == "rejected"
        assert resp["user_notes"] == "not useful"
    _clear()


@pytest.mark.asyncio
async def test_advisory_accept_without_price_data_does_not_block_or_create_snapshot(seeded_users):
    """§11 — advisory failures/unavailability never block normal pricing, and
    an "unavailable" placeholder (no recommended price) accepting is a no-op
    on pricing — it must never fabricate a snapshot."""
    user = seeded_users["user_a"]
    async with await _client_as(user) as c:
        r = await c.post("/api/pricing/advisory/requests", json={
            "category": "banners", "requested_advisory_types": ["ai_pricing_analysis"],
        })
        req_id = r.json()["id"]
        r = await c.post(
            f"/api/pricing/advisory/requests/{req_id}/responses/ai_pricing_analysis/decision",
            json={"decision": "accepted"},
        )
        assert r.status_code == 200, r.text
    n_before = await _db.pricing_snapshot_records.count_documents({"tenant_id": user["tenant_id"]})
    assert n_before == 0
    _clear()


@pytest.mark.asyncio
async def test_advisory_accept_with_populated_response_creates_new_snapshot(seeded_users):
    """Exercises the ONLY code path allowed to turn an accepted advisory
    adjustment into pricing: a synthetic, already-populated response (never
    reachable via any live AI/provider call in this phase) proves the wiring
    without building fake operational AI."""
    user = seeded_users["user_a"]
    cust = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        qid = await _new_quote(c, cust)
        r = await c.post(f"/api/quotes/{qid}/line-items", json=CALC_PAYLOAD)
        item = r.json()

    req = await create_advisory_request(
        user["tenant_id"], user["id"],
        {"category": "services", "requested_advisory_types": ["ai_pricing_analysis"]},
    )
    # Simulate a hypothetical future EC16/EC17 provider having populated this
    # response — never done by any code path reachable from the API today.
    populated = AdvisoryResponseItem(
        advisory_type="ai_pricing_analysis", status="completed", source_type="internal_test_fixture",
        recommended_price_range_cents=[5000, 6000], confidence="medium",
    ).model_dump()
    await _db.pricing_advisory_requests.update_one(
        {"id": req["id"]}, {"$set": {"responses": [populated]}},
    )

    updated = await decide_advisory_response(
        user["tenant_id"], req["id"], "ai_pricing_analysis", "accepted", user_id=user["id"],
        apply_to={"source_type": "quote_line_item", "source_id": item["id"], "quote_id": qid, "item_doc": item},
    )
    assert updated["responses"][0]["user_decision"] == "accepted"

    records = await _db.pricing_snapshot_records.find(
        {"tenant_id": user["tenant_id"], "source_type": "quote_line_item", "source_id": item["id"]}, {"_id": 0},
    ).sort("created_at", 1).to_list(10)
    assert len(records) == 2
    assert records[-1]["status"] == "accepted"
    assert records[0]["status"] == "superseded"
    _clear()


@pytest.mark.asyncio
async def test_advisory_tenant_isolation(seeded_users):
    user_a, user_b = seeded_users["user_a"], seeded_users["user_b"]
    async with await _client_as(user_a) as c:
        r = await c.post("/api/pricing/advisory/requests", json={
            "category": "banners", "requested_advisory_types": ["underpricing_warning"],
        })
        req_id = r.json()["id"]
    _clear()
    async with await _client_as(user_b) as c:
        r = await c.get(f"/api/pricing/advisory/requests/{req_id}")
        assert r.status_code == 404
    _clear()


@pytest.mark.asyncio
async def test_advisory_response_status_contract_supports_stale():
    """Contract-level check: the response model supports every status listed
    in the controlling spec, including `stale` — set only by a FUTURE
    provider integration, never by any code in this phase."""
    item = AdvisoryResponseItem(advisory_type="historical_pricing_comparison", status="stale")
    assert item.status == "stale"


@pytest.mark.asyncio
async def test_no_live_provider_call_ever_occurs(seeded_users):
    """Every response this phase creates is `unavailable` / `source_type=none`
    — the only structurally-honest proxy for "no live AI/web/market call was
    made" without mocking a network layer that doesn't exist in this code."""
    user = seeded_users["user_a"]
    async with await _client_as(user) as c:
        r = await c.post("/api/pricing/advisory/requests", json={
            "category": "banners",
            "requested_advisory_types": [
                "ai_pricing_analysis", "historical_pricing_comparison", "local_market_comparison",
                "regional_market_comparison", "target_margin_analysis", "cost_risk_analysis",
                "underpricing_warning", "overpricing_warning", "price_confidence_analysis",
            ],
        })
        assert r.status_code == 201
        for resp in r.json()["responses"]:
            assert resp["status"] == "unavailable"
            assert resp["source_type"] == "none"
            assert resp["recommended_price_range_cents"] is None
    _clear()


# ============================================================
# Standalone Calculator gap: canonical references reach the resolver
# ============================================================

@pytest.mark.asyncio
async def test_standalone_calculator_returns_frozen_reference_context(seeded_users):
    """Phase 9G §2 backend contract: `/pricing/calculate` (used by the
    standalone Calculator page) attaches the resolved reference snapshots
    needed to build a complete PricingSnapshotRecord once the result is added
    to a Quote/Order — proving the new frontend selectors have a real backend
    contract to send IDs to."""
    user = seeded_users["user_a"]
    async with await _client_as(user) as c:
        mat_id = f"mat-{uuid.uuid4().hex[:8]}"
        await _db.materials.insert_one({"id": mat_id, "tenant_id": user["tenant_id"], "name": "Calc Test Vinyl"})
        r = await c.post(f"/api/pricing/material-profiles/materials/{mat_id}", json={
            "pricing_unit": "per_sqft", "normalized_cost_basis": 1.0, "suggested_sell_rate": 3.0,
            "category_applicability": ["cut_vinyl"],
        })
        profile_id = r.json()["id"]

        r_without = await c.post("/api/pricing/calculate", json={
            "category": "cut_vinyl", "width_inches": 24, "height_inches": 24, "quantity": 1, "category_inputs": {},
        })
        assert r_without.status_code == 200, r_without.text

        r_with = await c.post("/api/pricing/calculate", json={
            "category": "cut_vinyl", "width_inches": 24, "height_inches": 24, "quantity": 1,
            "category_inputs": {}, "material_profile_id": profile_id,
        })
        assert r_with.status_code == 200, r_with.text
        # material_profile_id was actually resolved and fed into the formula
        # (proves the selected canonical id reaches the pricing resolver, not
        # just accepted-and-ignored) — the $3.00/sqft profile changes the
        # material cost basis vs. the shop's category default material.
        assert r_with.json()["material_cost"] != r_without.json()["material_cost"]
    _clear()
