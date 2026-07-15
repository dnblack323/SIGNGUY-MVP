"""EC10 Phase 10A — Intake architecture and canonical data contracts.

Covers: create/submit draft intake, multi-item intake, source tracking,
customer/quote/order/file/questionnaire reference validation (incl. cross-
tenant rejection), status transitions (valid + invalid), audit events,
idempotency + duplicate-submission prevention, tenant isolation, permissions,
internal-note protection, no-inline-file-storage, conversion-contract preview
(no pricing invented, no live Quote/Order write).
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
    ta = f"t-ec10-a-{suffix}"
    tb = f"t-ec10-b-{suffix}"
    ua = {"id": f"u-a-{suffix}", "tenant_id": ta, "email": f"a-{suffix}@example.com", "role": "owner", "is_active": True}
    ub = {"id": f"u-b-{suffix}", "tenant_id": tb, "email": f"b-{suffix}@example.com", "role": "owner", "is_active": True}
    staff_a = {"id": f"staff-a-{suffix}", "tenant_id": ta, "email": f"staff-a-{suffix}@example.com", "role": "staff", "is_active": True}
    await db.tenants.insert_many([{"id": ta, "slug": ta, "name": "TA"}, {"id": tb, "slug": tb, "name": "TB"}])
    await db.users.insert_many([ua, ub, staff_a])
    yield {"ua": ua, "ub": ub, "staff_a": staff_a, "ta": ta, "tb": tb}
    _clear()


@pytest.mark.asyncio
async def test_create_draft_intake_minimal(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        r = await c.post("/api/intake", json={"project_name": "New sign job"})
        assert r.status_code == 201
        body = r.json()
        assert body["status"] == "draft"
        assert body["tenant_id"] == ctx["ta"]
        assert body["source_type"] == "internal_user"
        assert isinstance(body["intake_number"], int) and body["intake_number"] > 0
        assert body["items"] == []


@pytest.mark.asyncio
async def test_multi_item_intake_and_source_tracking(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        r = await c.post("/api/intake", json={
            "source_type": "customer_portal",
            "project_name": "Storefront package",
            "items": [
                {"category": "banners", "item_name": "Front banner", "quantity": 1,
                 "measurements": {"width_inches": 96, "height_inches": 36, "unit": "in", "source": "staff_measured"}},
                {"category": "cut_vinyl", "item_name": "Door decal", "quantity": 2},
            ],
        })
        assert r.status_code == 201
        body = r.json()
        assert body["source_type"] == "customer_portal"
        assert len(body["items"]) == 2
        assert body["items"][0]["category"] == "banners"
        assert body["items"][0]["measurements"]["width_inches"] == 96
        # each item has its own stable id
        assert body["items"][0]["id"] != body["items"][1]["id"]
        # no pricing invented anywhere in the item payload
        assert "unit_price_cents" not in body["items"][0]


@pytest.mark.asyncio
async def test_add_item_after_create(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        r = await c.post("/api/intake", json={"project_name": "Growing job"})
        iid = r.json()["id"]
        r2 = await c.post(f"/api/intake/{iid}/items", json={"category": "rigid_signs", "item_name": "Lobby sign"})
        assert r2.status_code == 201
        assert len(r2.json()["items"]) == 1


@pytest.mark.asyncio
async def test_customer_reference_validated_and_cross_tenant_rejected(ctx):
    ua, ub = ctx["ua"], ctx["ub"]
    async with await _client(ua) as c:
        cust = await c.post("/api/customers", json={"name": "Acme Co"})
        cid = cust.json()["id"]
        ok = await c.post("/api/intake", json={"project_name": "Acme job", "customer_id": cid})
        assert ok.status_code == 201
        bad = await c.post("/api/intake", json={"project_name": "Ghost job", "customer_id": "does-not-exist"})
        assert bad.status_code == 404
    _clear()
    async with await _client(ub) as c2:
        # Tenant B must never resolve Tenant A's customer id.
        cross = await c2.post("/api/intake", json={"project_name": "Cross tenant", "customer_id": cid})
        assert cross.status_code == 404


@pytest.mark.asyncio
async def test_quote_and_order_reference_validation(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        cust = await c.post("/api/customers", json={"name": "Ref Co"})
        cid = cust.json()["id"]
        q = await c.post("/api/quotes", json={"customer_id": cid, "job_name": "Ref Quote"})
        qid = q.json()["id"]
        ok = await c.post("/api/intake", json={"project_name": "Linked to quote", "quote_id": qid})
        assert ok.status_code == 201
        bad = await c.post("/api/intake", json={"project_name": "Bad quote ref", "quote_id": "nope"})
        assert bad.status_code == 404
        bad2 = await c.post("/api/intake", json={"project_name": "Bad order ref", "order_id": "nope"})
        assert bad2.status_code == 404


@pytest.mark.asyncio
async def test_file_reference_validation_and_cross_tenant_rejected(ctx):
    ua, ub = ctx["ua"], ctx["ub"]
    async with await _client(ua) as c:
        # No inline upload here — reuse the existing shared /files/upload endpoint.
        up = await c.post(
            "/api/files/upload",
            files={"file": ("photo.png", b"\x89PNG\r\n\x1a\n" + b"0" * 20, "image/png")},
        )
        assert up.status_code == 201
        fid = up.json()["file"]["id"]
        ok = await c.post("/api/intake", json={"project_name": "With photo", "file_ids": [fid]})
        assert ok.status_code == 201
        # no base64 anywhere in the stored/returned record — only a reference id
        assert ok.json()["file_ids"] == [fid]
        bad = await c.post("/api/intake", json={"project_name": "Missing file", "file_ids": ["ghost-file"]})
        assert bad.status_code == 404
    _clear()
    async with await _client(ub) as c2:
        cross = await c2.post("/api/intake", json={"project_name": "Cross tenant file", "file_ids": [fid]})
        assert cross.status_code == 404


@pytest.mark.asyncio
async def test_questionnaire_reference_validation(ctx):
    ua = ctx["ua"]
    ta = ctx["ta"]
    async with await _client(ua) as c:
        cust = await c.post("/api/customers", json={"name": "Quiz Co"})
        cid = cust.json()["id"]
        # CustomerIntake (EC6) is the existing questionnaire-submission store.
        qi = {"id": f"ci-{uuid.uuid4().hex[:8]}", "tenant_id": ta, "customer_id": cid, "number": 1, "status": "submitted"}
        await db.customer_intakes.insert_one(qi)
        ok = await c.post("/api/intake", json={"project_name": "Quiz linked", "questionnaire_submission_ids": [qi["id"]]})
        assert ok.status_code == 201
        bad = await c.post("/api/intake", json={"project_name": "Bad quiz ref", "questionnaire_submission_ids": ["ghost"]})
        assert bad.status_code == 404


@pytest.mark.asyncio
async def test_status_transitions_valid_and_invalid(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        r = await c.post("/api/intake", json={
            "project_name": "Lifecycle test", "contact_name": "Jane Doe",
            "items": [{"item_name": "Sign", "category": "banners", "quantity": 1}],
        })
        iid = r.json()["id"]
        submitted = await c.post(f"/api/intake/{iid}/transition", json={"target": "submitted"})
        assert submitted.status_code == 200
        assert submitted.json()["status"] == "submitted"
        assert submitted.json()["submitted_at"] is not None
        # Invalid: cannot jump straight to accepted from submitted.
        invalid = await c.post(f"/api/intake/{iid}/transition", json={"target": "accepted"})
        assert invalid.status_code == 400
        review = await c.post(f"/api/intake/{iid}/transition", json={"target": "under_review"})
        assert review.status_code == 200
        accepted = await c.post(f"/api/intake/{iid}/transition", json={"target": "accepted"})
        assert accepted.status_code == 200
        # Rejected/cancelled require a reason.
        r2 = await c.post("/api/intake", json={
            "project_name": "To be rejected", "contact_name": "Jane Doe",
            "items": [{"item_name": "Sign", "category": "banners", "quantity": 1}],
        })
        iid2 = r2.json()["id"]
        await c.post(f"/api/intake/{iid2}/transition", json={"target": "submitted"})
        await c.post(f"/api/intake/{iid2}/transition", json={"target": "under_review"})
        no_reason = await c.post(f"/api/intake/{iid2}/transition", json={"target": "rejected"})
        assert no_reason.status_code == 400
        with_reason = await c.post(f"/api/intake/{iid2}/transition", json={"target": "rejected", "reason": "Out of scope"})
        assert with_reason.status_code == 200
        assert with_reason.json()["status"] == "rejected"
        # Rejected records are never deleted — still fetchable.
        still_there = await c.get(f"/api/intake/{iid2}")
        assert still_there.status_code == 200
        assert still_there.json()["status"] == "rejected"
        # Terminal state: no further transitions.
        dead_end = await c.post(f"/api/intake/{iid2}/transition", json={"target": "submitted"})
        assert dead_end.status_code == 400


@pytest.mark.asyncio
async def test_conversion_requires_quote_or_order_id_and_preserves_reference(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        cust = await c.post("/api/customers", json={"name": "Convert Co"})
        cid = cust.json()["id"]
        q = await c.post("/api/quotes", json={"customer_id": cid, "job_name": "Convert Quote"})
        qid = q.json()["id"]
        r = await c.post("/api/intake", json={"project_name": "Convert me", "customer_id": cid,
                                               "items": [{"item_name": "Sign", "category": "banners", "quantity": 1}]})
        iid = r.json()["id"]
        await c.post(f"/api/intake/{iid}/transition", json={"target": "submitted"})
        await c.post(f"/api/intake/{iid}/transition", json={"target": "under_review"})
        await c.post(f"/api/intake/{iid}/transition", json={"target": "accepted"})
        # Missing quote_id -> rejected (no automatic pricing/quote invention).
        missing = await c.post(f"/api/intake/{iid}/transition", json={"target": "converted_to_quote"})
        assert missing.status_code == 400
        ok = await c.post(f"/api/intake/{iid}/transition", json={"target": "converted_to_quote", "quote_id": qid})
        assert ok.status_code == 200
        assert ok.json()["quote_id"] == qid
        assert ok.json()["converted_at"] is not None


@pytest.mark.asyncio
async def test_conversion_preview_contract_no_pricing_invented(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        r = await c.post("/api/intake", json={
            "project_name": "Preview test",
            "items": [{"category": "banners", "item_name": "Preview banner", "quantity": 3,
                       "category_inputs": {"width_inches": 48, "height_inches": 24}}],
        })
        iid = r.json()["id"]
        preview = await c.get(f"/api/intake/{iid}/conversion-preview")
        assert preview.status_code == 200
        body = preview.json()
        assert len(body["quote_line_item_previews"]) == 1
        assert len(body["order_item_previews"]) == 1
        qli = body["quote_line_item_previews"][0]
        assert qli["category"] == "banners"
        assert qli["quantity"] == 3
        assert "unit_price_cents" not in qli
        assert "price" not in qli


@pytest.mark.asyncio
async def test_idempotency_and_duplicate_submission_prevention(ctx):
    ua = ctx["ua"]
    key = f"idem-{uuid.uuid4().hex[:8]}"
    async with await _client(ua) as c:
        r1 = await c.post("/api/intake", json={"project_name": "Idempotent job", "idempotency_key": key})
        r2 = await c.post("/api/intake", json={"project_name": "Idempotent job (retry)", "idempotency_key": key})
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["id"] == r2.json()["id"]
        count = await db.intake_submissions.count_documents({"tenant_id": ctx["ta"], "idempotency_key": key})
        assert count == 1


@pytest.mark.asyncio
async def test_tenant_isolation_on_list_and_get(ctx):
    ua, ub = ctx["ua"], ctx["ub"]
    async with await _client(ua) as c:
        r = await c.post("/api/intake", json={"project_name": "Tenant A only"})
        iid = r.json()["id"]
    _clear()
    async with await _client(ub) as c2:
        cross_get = await c2.get(f"/api/intake/{iid}")
        assert cross_get.status_code == 404
        listing = await c2.get("/api/intake")
        assert all(item["id"] != iid for item in listing.json()["items"])


@pytest.mark.asyncio
async def test_permissions_enforced_for_staff_role(ctx):
    staff_a = ctx["staff_a"]
    async with await _client(staff_a) as c:
        # `staff` role has INTAKE_READ/WRITE via STAFF_PERMS.
        r = await c.post("/api/intake", json={"project_name": "Staff created"})
        assert r.status_code == 201
        listing = await c.get("/api/intake")
        assert listing.status_code == 200


@pytest.mark.asyncio
async def test_internal_note_protection_helper():
    from app.services.intake_service import serialize_for_customer
    doc = {
        "id": "x", "project_name": "Test", "internal_notes": "secret staff note",
        "assigned_user_id": "u1", "created_by_user_id": "u1", "customer_notes": "visible to customer",
    }
    safe = serialize_for_customer(doc)
    assert "internal_notes" not in safe
    assert "assigned_user_id" not in safe
    assert "created_by_user_id" not in safe
    assert safe["customer_notes"] == "visible to customer"


@pytest.mark.asyncio
async def test_audit_events_emitted_for_create_and_transition(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        r = await c.post("/api/intake", json={
            "project_name": "Audited job", "contact_name": "Jane Doe",
            "items": [{"item_name": "Sign", "category": "banners", "quantity": 1}],
        })
        iid = r.json()["id"]
        await c.post(f"/api/intake/{iid}/transition", json={"target": "submitted"})
    events = [
        e async for e in db.audit_events.find(
            {"tenant_id": ctx["ta"], "entity_type": "intake_submission", "entity_id": iid}, {"_id": 0}
        )
    ]
    actions = {e["action"] for e in events}
    assert "intake.create" in actions
    assert "intake.submitted" in actions
    for e in events:
        assert e["actor_user_id"] == ua["id"]
        assert e["actor_email"] == ua["email"]
