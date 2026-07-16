"""EC10 Phase 10E-4 - internal Decision Room review queue.

Covers the thin review-queue router over the existing Phase 10E-4 service
groundwork: normalized multi-source queue reads, reviewer assignment,
supported acknowledge/review actions, internal notes, tenant isolation, and
the no-commercial-mutation boundary.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.portal_security import create_portal_token
from app.deps import get_current_user
from server import app


def _override(u):
    async def _get():
        return {**u}
    return _get


async def _staff_client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _anon_client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    ta = f"t-ec10e4-a-{suffix}"
    tb = f"t-ec10e4-b-{suffix}"
    owner_a = {"id": f"u-a-{suffix}", "tenant_id": ta, "email": f"a-{suffix}@example.com", "role": "owner", "is_active": True}
    staff_a = {"id": f"staff-a-{suffix}", "tenant_id": ta, "email": f"staff-a-{suffix}@example.com", "role": "staff", "is_active": True}
    owner_b = {"id": f"u-b-{suffix}", "tenant_id": tb, "email": f"b-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([{"id": ta, "slug": ta, "name": "TA"}, {"id": tb, "slug": tb, "name": "TB"}])
    await db.users.insert_many([owner_a, staff_a, owner_b])

    customer_a = {"id": f"cust-a-{suffix}", "tenant_id": ta, "name": "Jane Customer", "archived": False}
    order_a = {"id": f"o-{suffix}", "tenant_id": ta, "number": 1, "customer_id": customer_a["id"], "job_name": "Test Order", "status": "draft"}
    await db.customers.insert_one(customer_a)
    await db.orders.insert_one(order_a)

    portal_identity_a = {
        "id": f"pi-a-{suffix}", "tenant_id": ta, "portal_type": "customer", "customer_id": customer_a["id"],
        "email": f"jane-{suffix}@example.com", "status": "active",
        "permissions": ["portal:view_decision_rooms", "portal:respond_decision_rooms"], "permissions_preset": "custom",
    }
    await db.portal_identities.insert_one(portal_identity_a)
    token_a = create_portal_token(portal_identity_id=portal_identity_a["id"], tenant_id=ta, customer_id=customer_a["id"], portal_type="customer")

    source_file = {
        "id": f"file-{suffix}", "tenant_id": ta, "filename": "art.png", "content_type": "image/png",
        "mime_type": "image/png", "visibility": "customer_visible", "storage_key": f"k-{suffix}",
    }
    proof_a = {
        "id": f"proof-{suffix}", "tenant_id": ta, "number": 1, "parent_type": "order",
        "parent_id": order_a["id"], "title": "Layout proof", "status": "draft",
    }
    await db.files.insert_one(source_file)
    await db.proofs.insert_one(proof_a)

    yield {
        "owner_a": owner_a, "staff_a": staff_a, "owner_b": owner_b, "ta": ta, "tb": tb,
        "customer_a": customer_a, "order_a": order_a, "portal_token_a": token_a,
        "source_file": source_file, "proof_a": proof_a,
    }
    _clear()


async def _create_published_room_with_activity(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        room_resp = await c.post("/api/decision-rooms", json={
            "title": "Review queue room", "customer_safe_intro": "Pick one.",
            "customer_id": ctx["customer_a"]["id"], "order_id": ctx["order_a"]["id"],
            "allow_customer_questions": True, "allow_customer_comments": True,
            "allow_save_for_later": True, "allow_change_requests": True,
        })
        assert room_resp.status_code == 201, room_resp.text
        rid = room_resp.json()["id"]
        opt_resp = await c.post(f"/api/decision-rooms/{rid}/options", json={
            "customer_label": "Standard", "manual_price_cents": 25000,
            "file_ids": [ctx["source_file"]["id"]], "proof_id": ctx["proof_a"]["id"],
        })
        assert opt_resp.status_code == 201, opt_resp.text
        opt_id = opt_resp.json()["options"][0]["id"]
        assert (await c.post(f"/api/decision-rooms/{rid}/transition", json={"target": "ready"})).status_code == 200
        assert (await c.post(f"/api/decision-rooms/{rid}/publish")).status_code == 200

    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        decision = await c2.post(f"/api/portal/decision-rooms/{rid}/decisions", json={
            "action_type": "option_selected", "option_id": opt_id, "idempotency_key": f"d-{uuid.uuid4().hex}",
        })
        assert decision.status_code == 201, decision.text
        question = await c2.post(f"/api/portal/decision-rooms/{rid}/questions", json={
            "customer_message": "Can this be ready Friday?", "idempotency_key": f"q-{uuid.uuid4().hex}",
        })
        assert question.status_code == 201, question.text
        overlay = await c2.post(f"/api/portal/decision-rooms/{rid}/overlays", json={
            "overlay_type": "pin", "customer_message": "Use this logo position.",
            "normalized_x": 0.25, "normalized_y": 0.5, "source_file_id": ctx["source_file"]["id"],
            "idempotency_key": f"o-{uuid.uuid4().hex}",
        })
        assert overlay.status_code == 201, overlay.text
        saved = await c2.post(f"/api/portal/decision-rooms/{rid}/save-for-later", json={
            "note": "I need to ask my manager.", "idempotency_key": f"s-{uuid.uuid4().hex}",
        })
        assert saved.status_code == 201, saved.text

    return {
        "room_id": rid, "option_id": opt_id,
        "decision": decision.json(), "question": question.json(), "overlay": overlay.json(), "saved": saved.json(),
    }


@pytest.mark.asyncio
async def test_review_queue_lists_all_customer_activity_with_filters_and_proof_reference(ctx):
    created = await _create_published_room_with_activity(ctx)
    async with await _staff_client(ctx["owner_a"]) as c:
        queue = await c.get("/api/decision-room-review-queue", params={"unresolved_only": False})
        assert queue.status_code == 200, queue.text
        items = queue.json()["items"]
        by_type = {(it["record_type"], it["record_id"]): it for it in items}
        assert ("customer_decision", created["decision"]["id"]) in by_type
        assert ("question", created["question"]["id"]) in by_type
        assert ("overlay", created["overlay"]["id"]) in by_type
        assert ("saved_for_later", created["saved"]["id"]) in by_type

        decision_item = by_type[("customer_decision", created["decision"]["id"])]
        assert decision_item["decision_room_title"] == "Review queue room"
        assert decision_item["customer_name"] == "Jane Customer"
        assert decision_item["option_label"] == "Standard"
        assert decision_item["proof_id"] == ctx["proof_a"]["id"]

        unresolved = await c.get("/api/decision-room-review-queue", params={"unresolved_only": True})
        unresolved_types = {it["record_type"] for it in unresolved.json()["items"]}
        assert "saved_for_later" not in unresolved_types
        assert {"customer_decision", "question", "overlay"}.issubset(unresolved_types)

        pin_only = await c.get("/api/decision-room-review-queue", params={"activity_type": "pin", "unresolved_only": False})
        assert [it["record_id"] for it in pin_only.json()["items"]] == [created["overlay"]["id"]]


@pytest.mark.asyncio
async def test_review_queue_assign_notes_and_supported_acknowledge_actions(ctx):
    created = await _create_published_room_with_activity(ctx)
    async with await _staff_client(ctx["owner_a"]) as c:
        assign = await c.post(
            f"/api/decision-room-review-queue/customer_decision/{created['decision']['id']}/assign",
            json={"assigned_user_id": ctx["staff_a"]["id"]},
        )
        assert assign.status_code == 200, assign.text
        assert assign.json()["assigned_user_id"] == ctx["staff_a"]["id"]

        note = await c.post(
            f"/api/decision-room-review-queue/customer_decision/{created['decision']['id']}/notes",
            json={"note": "<b>Call customer before applying anything.</b>"},
        )
        assert note.status_code == 201, note.text
        assert "<b>" not in note.json()["note"]
        notes = await c.get(f"/api/decision-room-review-queue/customer_decision/{created['decision']['id']}/notes")
        assert len(notes.json()["items"]) == 1

        ack_decision = await c.post(f"/api/decision-room-review-queue/customer_decision/{created['decision']['id']}/acknowledge")
        assert ack_decision.status_code == 200, ack_decision.text
        assert ack_decision.json()["internal_review_status"] == "acknowledged"

        ack_overlay = await c.post(f"/api/decision-room-review-queue/overlay/{created['overlay']['id']}/acknowledge")
        assert ack_overlay.status_code == 200, ack_overlay.text
        assert ack_overlay.json()["status"] == "reviewed"

        unsupported = await c.post(f"/api/decision-room-review-queue/question/{created['question']['id']}/acknowledge")
        assert unsupported.status_code == 400


@pytest.mark.asyncio
async def test_review_queue_is_tenant_scoped_and_does_not_mutate_commercial_records(ctx):
    created = await _create_published_room_with_activity(ctx)
    order_before = await db.orders.find_one({"id": ctx["order_a"]["id"]}, {"_id": 0})
    proof_before = await db.proofs.find_one({"id": ctx["proof_a"]["id"]}, {"_id": 0})

    async with await _staff_client(ctx["owner_b"]) as c_other:
        other_queue = await c_other.get("/api/decision-room-review-queue", params={"unresolved_only": False})
        assert other_queue.status_code == 200
        assert other_queue.json()["items"] == []
        other_note = await c_other.post(
            f"/api/decision-room-review-queue/customer_decision/{created['decision']['id']}/notes",
            json={"note": "should not attach"},
        )
        assert other_note.status_code == 404

    async with await _staff_client(ctx["owner_a"]) as c:
        assert (await c.post(f"/api/decision-room-review-queue/customer_decision/{created['decision']['id']}/acknowledge")).status_code == 200
        assert (await c.post(f"/api/decision-room-review-queue/overlay/{created['overlay']['id']}/acknowledge")).status_code == 200
        assert (await c.post(
            f"/api/decision-room-review-queue/customer_decision/{created['decision']['id']}/assign",
            json={"assigned_user_id": ctx["staff_a"]["id"]},
        )).status_code == 200

    order_after = await db.orders.find_one({"id": ctx["order_a"]["id"]}, {"_id": 0})
    proof_after = await db.proofs.find_one({"id": ctx["proof_a"]["id"]}, {"_id": 0})
    assert order_after == order_before
    assert proof_after == proof_before
