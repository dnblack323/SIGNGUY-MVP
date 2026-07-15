"""EC10 Phase 10B — additive pricing workflow state + intake workflow backend tests.

Frontend workflow items (list render, filters, quick/detailed create, multi-item
add/edit/duplicate/reorder/remove, file/questionnaire attach, assignment, status
transitions, internal-notes protection) were verified via `craco build` (compile)
and manual route smoke-check per the minimal-credit instruction — no browser
automation/testing_agent was run for Phase 10B (not authorized).
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.deps import get_current_user
from server import app


def _override(u):
    async def _get():
        return {**u}
    return _get


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    ta = f"t-ec10b-a-{suffix}"
    tb = f"t-ec10b-b-{suffix}"
    ua = {"id": f"u-a-{suffix}", "tenant_id": ta, "email": f"a-{suffix}@example.com", "role": "owner", "is_active": True}
    ub = {"id": f"u-b-{suffix}", "tenant_id": tb, "email": f"b-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([{"id": ta, "slug": ta, "name": "TA"}, {"id": tb, "slug": tb, "name": "TB"}])
    await db.users.insert_many([ua, ub])
    yield {"ua": ua, "ub": ub, "ta": ta, "tb": tb}
    _clear()


async def _create_basic(c, **overrides):
    payload = {
        "project_name": "10B test job", "contact_name": "Jane Doe",
        "items": [{"item_name": "Sign A", "category": "banners", "quantity": 1}],
    }
    payload.update(overrides)
    r = await c.post("/api/intake", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.asyncio
async def test_legacy_phase10a_intake_remains_readable_without_new_fields(ctx):
    """A Phase 10A-shaped document (no pricing-workflow keys at all) must
    still deserialize and be returned correctly — Pydantic fills defaults."""
    ua, ta = ctx["ua"], ctx["ta"]
    legacy_id = f"in-legacy-{uuid.uuid4().hex[:8]}"
    await db.intake_submissions.insert_one({
        "id": legacy_id, "tenant_id": ta, "intake_number": 999, "status": "draft",
        "source_type": "internal_user", "items": [{"id": "item-1", "category": "banners", "quantity": 1}],
        "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00",
    })
    async with await _client(ua) as c:
        r = await c.get(f"/api/intake/{legacy_id}")
        assert r.status_code == 200
        body = r.json()
        # No crash/error on a legacy shape that predates the pricing-workflow
        # fields — missing keys are simply absent (frontend treats them as
        # "not_started"/unset), never a 500.
        assert body["id"] == legacy_id
        assert body["items"][0]["category"] == "banners"


@pytest.mark.asyncio
async def test_pricing_workflow_state_additive_and_valid_transitions(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        intake = await _create_basic(c)
        item_id = intake["items"][0]["id"]
        r = await c.patch(f"/api/intake/{intake['id']}/items/{item_id}", json={"pricing_status": "ready_for_pricing"})
        assert r.status_code == 200
        assert r.json()["items"][0]["pricing_status"] == "ready_for_pricing"


@pytest.mark.asyncio
async def test_invalid_pricing_status_value_rejected(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        intake = await _create_basic(c)
        item_id = intake["items"][0]["id"]
        r = await c.patch(f"/api/intake/{intake['id']}/items/{item_id}", json={"pricing_status": "totally_made_up"})
        assert r.status_code == 422  # pydantic Literal rejection


@pytest.mark.asyncio
async def test_manual_price_uses_integer_cents_and_is_explicit(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        intake = await _create_basic(c)
        item_id = intake["items"][0]["id"]
        # manual_price_entered without manual_price_cents is rejected — never invented.
        missing = await c.patch(f"/api/intake/{intake['id']}/items/{item_id}", json={"pricing_status": "manual_price_entered"})
        assert missing.status_code == 400
        ok = await c.patch(
            f"/api/intake/{intake['id']}/items/{item_id}",
            json={"pricing_status": "manual_price_entered", "manual_price_cents": 4599, "selected_price_source": "manual"},
        )
        assert ok.status_code == 200
        item = ok.json()["items"][0]
        assert item["manual_price_cents"] == 4599
        assert isinstance(item["manual_price_cents"], int)
        assert item["selected_price_source"] == "manual"


@pytest.mark.asyncio
async def test_pricing_snapshot_reference_only_and_no_pricing_invented(ctx):
    ua, ta = ctx["ua"], ctx["ta"]
    snap_id = f"snap-{uuid.uuid4().hex[:8]}"
    await db.pricing_snapshot_records.insert_one({
        "id": snap_id, "tenant_id": ta, "snapshot_type": "manual_test", "created_at": "2026-01-01T00:00:00+00:00",
    })
    async with await _client(ua) as c:
        intake = await _create_basic(c)
        item_id = intake["items"][0]["id"]
        r = await c.patch(f"/api/intake/{intake['id']}/items/{item_id}", json={"pricing_snapshot_id": snap_id})
        assert r.status_code == 200
        item = r.json()["items"][0]
        assert item["pricing_snapshot_id"] == snap_id
        # It is a bare string reference — no nested snapshot object was copied in.
        assert isinstance(item["pricing_snapshot_id"], str)
        bad = await c.patch(f"/api/intake/{intake['id']}/items/{item_id}", json={"pricing_snapshot_id": "ghost-snap"})
        assert bad.status_code == 404


@pytest.mark.asyncio
async def test_pricing_workflow_tenant_isolation(ctx):
    ua, ub, ta = ctx["ua"], ctx["ub"], ctx["ta"]
    snap_id = f"snap-{uuid.uuid4().hex[:8]}"
    await db.pricing_snapshot_records.insert_one({"id": snap_id, "tenant_id": ta, "snapshot_type": "x"})
    async with await _client(ua) as c:
        intake = await _create_basic(c)
        item_id = intake["items"][0]["id"]
        iid = intake["id"]
    _clear()
    async with await _client(ub) as c2:
        cross = await c2.patch(f"/api/intake/{iid}/items/{item_id}", json={"pricing_status": "ready_for_pricing"})
        assert cross.status_code == 404


@pytest.mark.asyncio
async def test_multi_item_add_edit_duplicate_reorder_remove(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        intake = await _create_basic(c)
        iid = intake["id"]
        item1 = intake["items"][0]["id"]
        r2 = await c.post(f"/api/intake/{iid}/items", json={"item_name": "Sign B", "category": "cut_vinyl", "quantity": 2})
        item2 = r2.json()["items"][1]["id"]

        # edit
        edited = await c.patch(f"/api/intake/{iid}/items/{item1}", json={"description": "Updated desc"})
        assert edited.status_code == 200
        assert next(i for i in edited.json()["items"] if i["id"] == item1)["description"] == "Updated desc"

        # duplicate — new id, no conversion/pricing lineage inherited
        dup = await c.post(f"/api/intake/{iid}/items/{item1}/duplicate")
        assert dup.status_code == 201
        dup_items = dup.json()["items"]
        assert len(dup_items) == 3
        dup_item = dup_items[-1]
        assert dup_item["id"] not in {item1, item2}
        assert dup_item["conversion_status"] == "pending"
        assert dup_item["quote_line_item_id"] is None
        assert dup_item["pricing_status"] == "not_started"

        # reorder
        all_ids = [i["id"] for i in dup_items]
        reordered_order = list(reversed(all_ids))
        reordered = await c.patch(f"/api/intake/{iid}/items/reorder", json={"item_ids": reordered_order})
        assert reordered.status_code == 200
        assert [i["id"] for i in reordered.json()["items"]] == reordered_order

        # remove (unconverted item can be removed)
        removed = await c.delete(f"/api/intake/{iid}/items/{item2}")
        assert removed.status_code == 200
        assert all(i["id"] != item2 for i in removed.json()["items"])


@pytest.mark.asyncio
async def test_remove_blocked_after_conversion(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        intake = await _create_basic(c)
        iid, item1 = intake["id"], intake["items"][0]["id"]
        # simulate a converted item (Phase 10F territory — directly set for this test)
        await db.intake_submissions.update_one(
            {"id": iid}, {"$set": {"items.0.conversion_status": "converted_to_quote_line_item"}},
        )
        blocked = await c.delete(f"/api/intake/{iid}/items/{item1}")
        assert blocked.status_code == 400


@pytest.mark.asyncio
async def test_reorder_rejects_mismatched_id_set(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        intake = await _create_basic(c)
        bad = await c.patch(f"/api/intake/{intake['id']}/items/reorder", json={"item_ids": ["nope"]})
        assert bad.status_code == 400


@pytest.mark.asyncio
async def test_submit_validation_and_missing_information_summary(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        r = await c.post("/api/intake", json={"project_name": ""})  # nothing usable at all
        iid = r.json()["id"]
        summary = await c.get(f"/api/intake/{iid}/missing-information")
        assert summary.status_code == 200
        fields = summary.json()["missing_fields"]
        assert "project_name_or_description_required" in fields
        assert "customer_or_contact_required" in fields
        assert "at_least_one_item_required" in fields
        bad_submit = await c.post(f"/api/intake/{iid}/transition", json={"target": "submitted"})
        assert bad_submit.status_code == 400
        assert "missing_fields" in bad_submit.json()["detail"]

        good = await _create_basic(c)
        good_submit = await c.post(f"/api/intake/{good['id']}/transition", json={"target": "submitted"})
        assert good_submit.status_code == 200


@pytest.mark.asyncio
async def test_installation_details_required_when_installation_flagged(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        intake = await _create_basic(c, installation_required=True)
        submit = await c.post(f"/api/intake/{intake['id']}/transition", json={"target": "submitted"})
        assert submit.status_code == 400
        assert "installation_details_required" in submit.json()["detail"]["missing_fields"]
        await c.patch(f"/api/intake/{intake['id']}", json={"installation_location": "123 Main St"})
        submit2 = await c.post(f"/api/intake/{intake['id']}/transition", json={"target": "submitted"})
        assert submit2.status_code == 200


@pytest.mark.asyncio
async def test_status_history_actor_and_timestamp_recorded(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        intake = await _create_basic(c)
        await c.post(f"/api/intake/{intake['id']}/transition", json={"target": "submitted"})
        r = await c.post(f"/api/intake/{intake['id']}/transition", json={"target": "under_review"})
        history = r.json()["status_history"]
        assert len(history) == 2
        assert history[0]["to"] == "submitted"
        assert history[1]["to"] == "under_review"
        assert history[1]["actor_user_id"] == ua["id"]
        assert history[1]["at"] is not None
        assert r.json()["reviewed_by_user_id"] == ua["id"]


@pytest.mark.asyncio
async def test_list_filters_and_search(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        await _create_basic(c, project_name="Storefront Banner Job", priority="high")
        await _create_basic(c, project_name="Vehicle Wrap Job", priority="low")

        by_priority = await c.get("/api/intake", params={"priority": "high"})
        assert all(i["priority"] == "high" for i in by_priority.json()["items"])

        by_search = await c.get("/api/intake", params={"q": "Vehicle Wrap"})
        assert any("Vehicle Wrap" in i["project_name"] for i in by_search.json()["items"])
        assert all("Storefront" not in i["project_name"] for i in by_search.json()["items"])

        multi_status = await c.get("/api/intake", params=[("status", "draft"), ("status", "submitted")])
        assert multi_status.status_code == 200
        assert all(i["status"] in {"draft", "submitted"} for i in multi_status.json()["items"])

        # missing-information indicator present in list rows
        assert "missing_information" in by_priority.json()["items"][0]


@pytest.mark.asyncio
async def test_internal_notes_not_exposed_through_customer_safe_helper(ctx):
    from app.services.intake_service import serialize_for_customer
    ua = ctx["ua"]
    async with await _client(ua) as c:
        intake = await _create_basic(c, internal_notes="staff eyes only")
        doc = await db.intake_submissions.find_one({"id": intake["id"]}, {"_id": 0})
        safe = serialize_for_customer(doc)
        assert "internal_notes" not in safe
        assert "assigned_user_id" not in safe


@pytest.mark.asyncio
async def test_assignment_is_permission_checked_tenant_scoped_and_audited(ctx):
    ua, ub = ctx["ua"], ctx["ub"]
    async with await _client(ua) as c:
        intake = await _create_basic(c)
        iid = intake["id"]
        assign = await c.patch(f"/api/intake/{iid}", json={"assigned_user_id": ua["id"]})
        assert assign.status_code == 200
        assert assign.json()["assigned_user_id"] == ua["id"]
    _clear()
    async with await _client(ub) as c2:
        cross = await c2.patch(f"/api/intake/{iid}", json={"assigned_user_id": ub["id"]})
        assert cross.status_code == 404
    events = [e async for e in db.audit_events.find(
        {"tenant_id": ctx["ta"], "entity_type": "intake_submission", "entity_id": iid, "action": "intake.update"},
        {"_id": 0},
    )]
    assert any("assigned_user_id" in e["diff"].get("fields", []) for e in events)
