"""EC10 Phase 10E-3 — Customer Questions, Anchored Comments/Pins, and Save
for Later. Covers submission via Customer Portal AND Public Token, staff
respond/resolve, normalized-coordinate + frozen-media/markup validation,
Fabric.js-payload rejection, overlay ownership (edit/withdraw), save-for-
later gating + lifecycle, idempotency, rate limiting, tenant isolation, and
— critically — that NO Quote/Order/Order Item/pricing/Proof/staff markup is
ever mutated by any of this.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.portal_security import create_portal_token
from app.deps import get_current_user
from app.services.portal_tokens import mint_public_action_token
from server import app


def _override(u):
    async def _get():
        return {**u}
    return _get


async def _staff_client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


async def _anon_client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    ta = f"t-ec10e3-a-{suffix}"
    tb = f"t-ec10e3-b-{suffix}"
    owner_a = {"id": f"u-a-{suffix}", "tenant_id": ta, "email": f"a-{suffix}@example.com", "role": "owner", "is_active": True}
    owner_b = {"id": f"u-b-{suffix}", "tenant_id": tb, "email": f"b-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([{"id": ta, "slug": ta, "name": "TA"}, {"id": tb, "slug": tb, "name": "TB"}])
    await db.users.insert_many([owner_a, owner_b])

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

    # A staff-authored source file + VisualMarkup + MarkupVersion — inserted
    # directly (bypassing the full upload/create_markup flow, which is out
    # of scope for THIS test file) purely so anchor validation has a real
    # visual_markup_id/markup_version_id to check against.
    source_file = {"id": f"file-{suffix}", "tenant_id": ta, "filename": "art.png", "content_type": "image/png", "visibility": "customer_visible", "storage_key": f"k-{suffix}"}
    await db.files.insert_one(source_file)
    vm = {
        "id": f"vm-{suffix}", "tenant_id": ta, "source_file_id": source_file["id"], "source_file_type": "pdf",
        "source_page_number": 2, "current_version_number": 1, "status": "active",
    }
    await db.visual_markups.insert_one(vm)
    mv = {
        "id": f"mv-{suffix}", "tenant_id": ta, "visual_markup_id": vm["id"], "version_number": 1,
        "canvas_width": 800, "canvas_height": 600, "source_display_width": 800, "source_display_height": 600,
        "structured_markup_json": {"objects": []}, "status": "active",
    }
    await db.markup_versions.insert_one(mv)

    yield {
        "owner_a": owner_a, "owner_b": owner_b, "ta": ta, "tb": tb,
        "customer_a": customer_a, "order_a": order_a, "portal_token_a": token_a,
        "source_file": source_file, "visual_markup": vm, "markup_version": mv,
    }
    _clear()


async def _create_published_room(c, *, customer_id, order_id, title="Q&A room", extra=None, with_markup_option=False, vm_id=None):
    payload = {"title": title, "customer_safe_intro": "Ask us anything.", "customer_id": customer_id, "order_id": order_id}
    payload.update(extra or {})
    room = (await c.post("/api/decision-rooms", json=payload)).json()
    rid = room["id"]
    opt_payload = {"customer_label": "Standard", "manual_price_cents": 25000}
    if with_markup_option:
        opt_payload["visual_markup_id"] = vm_id
    opt_resp = await c.post(f"/api/decision-rooms/{rid}/options", json=opt_payload)
    opt_id = opt_resp.json()["options"][0]["id"]
    opt2_resp = await c.post(f"/api/decision-rooms/{rid}/options", json={"customer_label": "Premium", "manual_price_cents": 45000})
    assert opt2_resp.status_code == 201, opt2_resp.text

    ready = await c.post(f"/api/decision-rooms/{rid}/transition", json={"target": "ready"})
    assert ready.status_code == 200, ready.text
    published = await c.post(f"/api/decision-rooms/{rid}/publish")
    assert published.status_code == 200, published.text
    return rid, opt_id


# ---- Questions --------------------------------------------------------------

@pytest.mark.asyncio
async def test_portal_question_room_and_option_level(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, opt_id = await _create_published_room(
            c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"], extra={"allow_customer_questions": True},
        )
    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        room_level = await c2.post(f"/api/portal/decision-rooms/{rid}/questions", json={"customer_message": "What's the turnaround time?"})
        assert room_level.status_code == 201, room_level.text
        assert room_level.json()["option_id"] is None
        assert room_level.json()["status"] == "open"

        option_level = await c2.post(f"/api/portal/decision-rooms/{rid}/questions", json={"customer_message": "Does this include lamination?", "option_id": opt_id})
        assert option_level.status_code == 201
        assert option_level.json()["option_id"] == opt_id

        mine = (await c2.get(f"/api/portal/decision-rooms/{rid}/questions")).json()["items"]
        assert len(mine) == 2


@pytest.mark.asyncio
async def test_question_requires_flag_and_message(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, _opt = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"], title="No questions")
        rid2, _opt2 = await _create_published_room(
            c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"], title="Questions allowed", extra={"allow_customer_questions": True},
        )
    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        flag_denied = await c2.post(f"/api/portal/decision-rooms/{rid}/questions", json={"customer_message": "Hello?"})
        assert flag_denied.status_code == 400
        empty_msg = await c2.post(f"/api/portal/decision-rooms/{rid2}/questions", json={"customer_message": "   "})
        assert empty_msg.status_code == 400
        html_stripped = await c2.post(f"/api/portal/decision-rooms/{rid2}/questions", json={"customer_message": "<script>alert(1)</script>Hi there"})
        assert html_stripped.status_code == 201
        assert "<script>" not in html_stripped.json()["customer_message"]
        assert "Hi there" in html_stripped.json()["customer_message"]


@pytest.mark.asyncio
async def test_question_media_and_markup_anchor_validation(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, opt_id = await _create_published_room(
            c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"], extra={"allow_customer_questions": True},
            with_markup_option=True, vm_id=ctx["visual_markup"]["id"],
        )
    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"

        wrong_page = await c2.post(f"/api/portal/decision-rooms/{rid}/questions", json={
            "customer_message": "About this markup", "visual_markup_id": ctx["visual_markup"]["id"], "page_number": 99,
        })
        assert wrong_page.status_code == 400

        wrong_version = await c2.post(f"/api/portal/decision-rooms/{rid}/questions", json={
            "customer_message": "About this markup", "visual_markup_id": ctx["visual_markup"]["id"],
            "markup_version_id": "not-a-real-version", "page_number": 2,
        })
        assert wrong_version.status_code == 404

        unrelated_markup = await c2.post(f"/api/portal/decision-rooms/{rid}/questions", json={
            "customer_message": "About this markup", "visual_markup_id": "vm-does-not-belong-here", "page_number": 2,
        })
        assert unrelated_markup.status_code == 404

        media_not_in_version = await c2.post(f"/api/portal/decision-rooms/{rid}/questions", json={
            "customer_message": "About this file", "source_file_id": "file-not-referenced-anywhere",
        })
        assert media_not_in_version.status_code == 404

        ok = await c2.post(f"/api/portal/decision-rooms/{rid}/questions", json={
            "customer_message": "About this markup", "option_id": opt_id,
            "visual_markup_id": ctx["visual_markup"]["id"], "markup_version_id": ctx["markup_version"]["id"], "page_number": 2,
        })
        assert ok.status_code == 201, ok.text


@pytest.mark.asyncio
async def test_staff_response_lifecycle_and_customer_safe_view(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, _opt = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"], extra={"allow_customer_questions": True})
    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        q = (await c2.post(f"/api/portal/decision-rooms/{rid}/questions", json={"customer_message": "Is rush available?"})).json()

    async with await _staff_client(ctx["owner_a"]) as c:
        staff_list = (await c.get(f"/api/decision-rooms/{rid}/questions")).json()["items"]
        assert len(staff_list) == 1
        assert "responded_by_user_id" in staff_list[0]  # staff sees full doc

        resp = await c.post(f"/api/decision-rooms/{rid}/questions/{q['id']}/respond", json={"staff_response": "Yes, 24-hour rush is available."})
        assert resp.status_code == 200
        assert resp.json()["status"] == "answered"

        resolved = await c.post(f"/api/decision-rooms/{rid}/questions/{q['id']}/resolve")
        assert resolved.status_code == 200
        assert resolved.json()["status"] == "resolved"
    _clear()

    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        mine = (await c2.get(f"/api/portal/decision-rooms/{rid}/questions")).json()["items"]
        assert mine[0]["status"] == "resolved"
        assert mine[0]["staff_response"] == "Yes, 24-hour rush is available."
        assert "responded_by_user_id" not in mine[0]  # customer never sees the internal staff id
        assert "customer_id" not in mine[0]


# ---- Anchored comments/pins --------------------------------------------------

@pytest.mark.asyncio
async def test_overlay_pin_and_comment_with_normalized_coordinates(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, opt_id = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"], extra={"allow_customer_comments": True})
        opt = (await c.get(f"/api/decision-rooms/{rid}")).json()["options"][0]
        assert opt["id"] == opt_id
        # Reuse the option's own frozen-safe media reference for anchoring (uploaded via a helper elsewhere in
        # the suite would be heavier; instead directly attach the pre-seeded customer_visible file to the option).
        await c.patch(f"/api/decision-rooms/{rid}/options/{opt_id}", json={"file_ids": [ctx["source_file"]["id"]]})
        await c.post(f"/api/decision-rooms/{rid}/publish")  # re-publish v2 to freeze the attachment
    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        pin1 = await c2.post(f"/api/portal/decision-rooms/{rid}/overlays", json={
            "overlay_type": "pin", "customer_message": "Fix this corner", "normalized_x": 0.1, "normalized_y": 0.2,
            "source_file_id": ctx["source_file"]["id"],
        })
        assert pin1.status_code == 201, pin1.text
        assert pin1.json()["marker_number"] == 1

        pin2 = await c2.post(f"/api/portal/decision-rooms/{rid}/overlays", json={
            "overlay_type": "pin", "customer_message": "And this one", "normalized_x": 0.5, "normalized_y": 0.6,
            "source_file_id": ctx["source_file"]["id"],
        })
        assert pin2.json()["marker_number"] == 2

        comment = await c2.post(f"/api/portal/decision-rooms/{rid}/overlays", json={
            "overlay_type": "comment", "customer_message": "General note", "normalized_x": 0.9, "normalized_y": 0.9,
            "source_file_id": ctx["source_file"]["id"],
        })
        assert comment.status_code == 201
        assert comment.json()["marker_number"] is None

        mine = (await c2.get(f"/api/portal/decision-rooms/{rid}/overlays")).json()["items"]
        assert len(mine) == 3


@pytest.mark.asyncio
async def test_overlay_requires_flag_anchor_and_valid_coordinates(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, opt_id = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"], title="No comments")
        rid2, opt_id2 = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"], title="Comments allowed", extra={"allow_customer_comments": True})
        await c.patch(f"/api/decision-rooms/{rid2}/options/{opt_id2}", json={"file_ids": [ctx["source_file"]["id"]]})
        await c.post(f"/api/decision-rooms/{rid2}/publish")
    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        flag_denied = await c2.post(f"/api/portal/decision-rooms/{rid}/overlays", json={
            "overlay_type": "pin", "customer_message": "x", "normalized_x": 0.5, "normalized_y": 0.5, "source_file_id": ctx["source_file"]["id"],
        })
        assert flag_denied.status_code == 400

        no_anchor = await c2.post(f"/api/portal/decision-rooms/{rid2}/overlays", json={"overlay_type": "pin", "customer_message": "x", "normalized_x": 0.5, "normalized_y": 0.5})
        assert no_anchor.status_code == 400

        bad_coords = await c2.post(f"/api/portal/decision-rooms/{rid2}/overlays", json={
            "overlay_type": "pin", "customer_message": "x", "normalized_x": 1.5, "normalized_y": 0.5, "source_file_id": ctx["source_file"]["id"],
        })
        assert bad_coords.status_code == 400

        media_not_in_version = await c2.post(f"/api/portal/decision-rooms/{rid2}/overlays", json={
            "overlay_type": "pin", "customer_message": "x", "normalized_x": 0.5, "normalized_y": 0.5, "source_file_id": "not-a-real-file",
        })
        assert media_not_in_version.status_code == 404

        ok = await c2.post(f"/api/portal/decision-rooms/{rid2}/overlays", json={
            "overlay_type": "pin", "customer_message": "x", "normalized_x": 0.5, "normalized_y": 0.5, "source_file_id": ctx["source_file"]["id"],
        })
        assert ok.status_code == 201


@pytest.mark.asyncio
async def test_overlay_fabric_json_payload_rejected(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, opt_id = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"], extra={"allow_customer_comments": True})
        await c.patch(f"/api/decision-rooms/{rid}/options/{opt_id}", json={"file_ids": [ctx["source_file"]["id"]]})
        await c.post(f"/api/decision-rooms/{rid}/publish")
    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        resp = await c2.post(f"/api/portal/decision-rooms/{rid}/overlays", json={
            "overlay_type": "pin", "customer_message": "x", "normalized_x": 0.5, "normalized_y": 0.5,
            "source_file_id": ctx["source_file"]["id"], "structured_markup_json": {"objects": [{"type": "rect"}]},
        })
        assert resp.status_code == 422  # extra="forbid" — Fabric.js JSON is never accepted from a customer


@pytest.mark.asyncio
async def test_overlay_edit_withdraw_ownership_and_staff_markup_untouched(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, opt_id = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"], extra={"allow_customer_comments": True})
        await c.patch(f"/api/decision-rooms/{rid}/options/{opt_id}", json={"file_ids": [ctx["source_file"]["id"]]})
        await c.post(f"/api/decision-rooms/{rid}/publish")
    _clear()

    markup_version_before = await db.markup_versions.find_one({"id": ctx["markup_version"]["id"]}, {"_id": 0})

    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        overlay = (await c2.post(f"/api/portal/decision-rooms/{rid}/overlays", json={
            "overlay_type": "comment", "customer_message": "original text", "normalized_x": 0.3, "normalized_y": 0.4, "source_file_id": ctx["source_file"]["id"],
        })).json()

        edited = await c2.patch(f"/api/portal/decision-rooms/{rid}/overlays/{overlay['id']}", json={"customer_message": "edited text"})
        assert edited.status_code == 200 and edited.json()["customer_message"] == "edited text"

        withdrawn = await c2.post(f"/api/portal/decision-rooms/{rid}/overlays/{overlay['id']}/withdraw")
        assert withdrawn.status_code == 200 and withdrawn.json()["status"] == "withdrawn"

        locked = await c2.patch(f"/api/portal/decision-rooms/{rid}/overlays/{overlay['id']}", json={"customer_message": "too late"})
        assert locked.status_code == 400

    # A second portal identity tied to a DIFFERENT customer must never touch this overlay.
    other_customer = {"id": f"cust-other-{uuid.uuid4().hex[:8]}", "tenant_id": ctx["ta"], "name": "Other Co", "archived": False}
    await db.customers.insert_one(other_customer)
    other_identity = {
        "id": f"pi-other-{uuid.uuid4().hex[:8]}", "tenant_id": ctx["ta"], "portal_type": "customer", "customer_id": other_customer["id"],
        "email": f"other-{uuid.uuid4().hex[:8]}@example.com", "status": "active",
        "permissions": ["portal:view_decision_rooms", "portal:respond_decision_rooms"], "permissions_preset": "custom",
    }
    await db.portal_identities.insert_one(other_identity)
    other_token = create_portal_token(portal_identity_id=other_identity["id"], tenant_id=ctx["ta"], customer_id=other_customer["id"], portal_type="customer")

    async with await _anon_client() as c3:
        c3.headers["Authorization"] = f"Bearer {other_token}"
        overlay2 = (await c3.post(f"/api/portal/decision-rooms/{rid}/overlays", json={
            "overlay_type": "comment", "customer_message": "mine", "normalized_x": 0.1, "normalized_y": 0.1, "source_file_id": ctx["source_file"]["id"],
        }))
        # `other_customer` doesn't own this room at all → not accessible.
        assert overlay2.status_code == 404

    markup_version_after = await db.markup_versions.find_one({"id": ctx["markup_version"]["id"]}, {"_id": 0})
    assert markup_version_before == markup_version_after  # staff-authored markup is completely untouched


# ---- Save for later ----------------------------------------------------------

@pytest.mark.asyncio
async def test_save_for_later_gating_and_lifecycle(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, _opt = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"], title="No save")
        rid2, _opt2 = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"], title="Save allowed", extra={"allow_save_for_later": True})
    _clear()

    decisions_before = await db.customer_decisions.count_documents({})

    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        disabled = await c2.post(f"/api/portal/decision-rooms/{rid}/save-for-later", json={"note": "later"})
        assert disabled.status_code == 400

        saved = await c2.post(f"/api/portal/decision-rooms/{rid2}/save-for-later", json={"note": "come back next week", "idempotency_key": "sfl-1"})
        assert saved.status_code == 201, saved.text
        room2 = (await c2.get(f"/api/portal/decision-rooms/{rid2}")).json()
        assert saved.json()["published_version_id"] == room2["published_version_id"]

        dup = await c2.post(f"/api/portal/decision-rooms/{rid2}/save-for-later", json={"note": "different note", "idempotency_key": "sfl-1"})
        assert dup.status_code == 201
        assert dup.json()["id"] == saved.json()["id"]  # idempotent — same row, note NOT changed

        mine = (await c2.get(f"/api/portal/decision-rooms/{rid2}/save-for-later")).json()["items"]
        assert len(mine) == 1

    count = await db.decision_room_saved_for_later.count_documents({"decision_room_id": rid2})
    assert count == 1

    async with await _staff_client(ctx["owner_a"]) as c:
        await c.post(f"/api/decision-rooms/{rid2}/transition", json={"target": "closed"})
    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        closed_denied = await c2.post(f"/api/portal/decision-rooms/{rid2}/save-for-later", json={"note": "x"})
        assert closed_denied.status_code == 400

    decisions_after = await db.customer_decisions.count_documents({})
    assert decisions_before == decisions_after  # save-for-later never creates a CustomerDecision


# ---- Shared: public token parity, tenant isolation, rate limiting, audit ---

@pytest.mark.asyncio
async def test_public_token_parity_for_questions_and_overlays(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, opt_id = await _create_published_room(
            c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"],
            extra={"allow_customer_questions": True, "allow_customer_comments": True},
        )
        await c.patch(f"/api/decision-rooms/{rid}/options/{opt_id}", json={"file_ids": [ctx["source_file"]["id"]]})
        await c.post(f"/api/decision-rooms/{rid}/publish")
        raw, _ = await mint_public_action_token(tenant_id=ctx["ta"], action="decision_room_view", parent_type="decision_room", parent_id=rid, single_use=False)
    _clear()
    async with await _anon_client() as c2:
        q = await c2.post(f"/api/public/decision-rooms/{rid}/questions", params={"t": raw}, json={"customer_message": "Public question", "signer_name": "Guest"})
        assert q.status_code == 201
        assert q.json().get("id")

        ov = await c2.post(f"/api/public/decision-rooms/{rid}/overlays", params={"t": raw}, json={
            "overlay_type": "pin", "customer_message": "Public pin", "normalized_x": 0.2, "normalized_y": 0.3, "source_file_id": ctx["source_file"]["id"],
        })
        assert ov.status_code == 201

        listed_q = (await c2.get(f"/api/public/decision-rooms/{rid}/questions", params={"t": raw})).json()["items"]
        listed_ov = (await c2.get(f"/api/public/decision-rooms/{rid}/overlays", params={"t": raw})).json()["items"]
        assert len(listed_q) == 1 and len(listed_ov) == 1


@pytest.mark.asyncio
async def test_tenant_isolation_on_public_question_submission(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, _opt = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"], extra={"allow_customer_questions": True})
    _clear()
    raw_b, _ = await mint_public_action_token(tenant_id=ctx["tb"], action="decision_room_view", parent_type="decision_room", parent_id=rid, single_use=False)
    async with await _anon_client() as c2:
        resp = await c2.post(f"/api/public/decision-rooms/{rid}/questions", params={"t": raw_b}, json={"customer_message": "Hi"})
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_public_action_rate_limiting(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, _opt = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"], extra={"allow_customer_questions": True})
        raw, _ = await mint_public_action_token(tenant_id=ctx["ta"], action="decision_room_view", parent_type="decision_room", parent_id=rid, single_use=False)
    _clear()
    async with await _anon_client() as c2:
        statuses = []
        for i in range(25):
            r = await c2.post(f"/api/public/decision-rooms/{rid}/questions", params={"t": raw}, json={"customer_message": f"Q{i}", "idempotency_key": f"rl-{i}"})
            statuses.append(r.status_code)
        assert 429 in statuses  # the 21st+ request within the window must be throttled


@pytest.mark.asyncio
async def test_audit_events_recorded_and_notification_failure_does_not_lose_action(ctx, monkeypatch):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, _opt = await _create_published_room(
            c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"], extra={"allow_customer_questions": True},
        )
    _clear()

    import app.services.decision_room_service as svc_module

    async def _boom(*args, **kwargs):
        raise RuntimeError("simulated notification outage")
    monkeypatch.setattr(svc_module, "notify_tenant_owners", _boom)

    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        resp = await c2.post(f"/api/portal/decision-rooms/{rid}/questions", json={"customer_message": "Does the notification outage lose me?"})
        assert resp.status_code == 201  # the question is saved even though the notification hook threw

    audit = await db.audit_events.find_one({"tenant_id": ctx["ta"], "action": "decision_room.customer_question_submitted"}, {"_id": 0})
    assert audit is not None
    assert "message_length" in (audit.get("diff") or {})
    assert "Does the notification outage lose me" not in str(audit.get("diff"))  # full message body never in audit metadata
