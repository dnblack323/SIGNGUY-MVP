"""EC10 Phase 10E-2 — Customer Option Selection, Rejection, and Change
Requests. Covers submission via Customer Portal AND Public Token, the
`option_selected`/`option_rejected`/`all_options_rejected`/`change_requested`
action types (per the owner's exact naming — no `select`/`reject`/
`request_change` abbreviations), idempotency, frozen-published-version
validation, `allow_reject_all`/`allow_change_requests` gating, selection
superseding, locked-room rejection, tenant isolation, and — critically —
that NO commercial record (Quote/Order/Order Item) is ever mutated by any
of this. `save_for_later` is explicitly OUT of scope (Phase 10E-3).
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
    ta = f"t-ec10e2-a-{suffix}"
    tb = f"t-ec10e2-b-{suffix}"
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
    portal_identity_viewonly = {
        "id": f"pi-view-{suffix}", "tenant_id": ta, "portal_type": "customer", "customer_id": customer_a["id"],
        "email": f"viewonly-{suffix}@example.com", "status": "active",
        "permissions": ["portal:view_decision_rooms"], "permissions_preset": "custom",
    }
    await db.portal_identities.insert_many([portal_identity_a, portal_identity_viewonly])
    token_a = create_portal_token(portal_identity_id=portal_identity_a["id"], tenant_id=ta, customer_id=customer_a["id"], portal_type="customer")
    token_viewonly = create_portal_token(portal_identity_id=portal_identity_viewonly["id"], tenant_id=ta, customer_id=customer_a["id"], portal_type="customer")

    yield {
        "owner_a": owner_a, "owner_b": owner_b, "ta": ta, "tb": tb,
        "customer_a": customer_a, "order_a": order_a,
        "portal_token_a": token_a, "portal_token_viewonly": token_viewonly,
    }
    _clear()


async def _create_published_room(c, *, customer_id, order_id, title="Wrap options", extra=None):
    payload = {
        "title": title, "customer_safe_intro": "Pick the option that fits.",
        "customer_id": customer_id, "order_id": order_id,
    }
    payload.update(extra or {})
    room = (await c.post("/api/decision-rooms", json=payload)).json()
    rid = room["id"]
    opt_a_resp = await c.post(f"/api/decision-rooms/{rid}/options", json={"customer_label": "Standard", "manual_price_cents": 25000})
    opt_a_id = opt_a_resp.json()["options"][0]["id"]
    opt_b_resp = await c.post(f"/api/decision-rooms/{rid}/options", json={"customer_label": "Premium", "manual_price_cents": 45000})
    opt_b_id = next(o["id"] for o in opt_b_resp.json()["options"] if o["customer_label"] == "Premium")

    await c.post(f"/api/decision-rooms/{rid}/transition", json={"target": "ready"})
    await c.post(f"/api/decision-rooms/{rid}/publish")
    return rid, opt_a_id, opt_b_id


@pytest.mark.asyncio
async def test_portal_select_creates_pending_review_decision(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, opt_a, _opt_b = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"])
    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        resp = await c2.post(f"/api/portal/decision-rooms/{rid}/decisions", json={
            "action_type": "option_selected", "option_id": opt_a, "idempotency_key": "k1",
        })
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["action_type"] == "option_selected"
        assert body["option_id"] == opt_a
        assert body["internal_review_status"] == "pending_review"
        assert body["source_access_mode"] == "portal"
        assert body["customer_id"] == ctx["customer_a"]["id"]
        assert body["published_version_id"]
        assert body["published_version_number"] == 1

        mine = (await c2.get(f"/api/portal/decision-rooms/{rid}/decisions")).json()["items"]
        assert len(mine) == 1 and mine[0]["id"] == body["id"]


@pytest.mark.asyncio
async def test_viewonly_identity_cannot_submit_decisions(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, opt_a, _opt_b = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"])
    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_viewonly']}"
        resp = await c2.post(f"/api/portal/decision-rooms/{rid}/decisions", json={"action_type": "option_selected", "option_id": opt_a})
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_idempotency_key_prevents_duplicate_rows(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, opt_a, _opt_b = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"])
    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        payload = {"action_type": "option_selected", "option_id": opt_a, "idempotency_key": "dup-key-1"}
        first = await c2.post(f"/api/portal/decision-rooms/{rid}/decisions", json=payload)
        second = await c2.post(f"/api/portal/decision-rooms/{rid}/decisions", json=payload)
        assert first.status_code == 201 and second.status_code == 201
        assert first.json()["id"] == second.json()["id"]

    count = await db.customer_decisions.count_documents({"decision_room_id": rid})
    assert count == 1


@pytest.mark.asyncio
async def test_selecting_different_option_supersedes_prior_selection(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, opt_a, opt_b = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"])
    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        first = (await c2.post(f"/api/portal/decision-rooms/{rid}/decisions", json={"action_type": "option_selected", "option_id": opt_a, "idempotency_key": "sel-1"})).json()
        second = (await c2.post(f"/api/portal/decision-rooms/{rid}/decisions", json={"action_type": "option_selected", "option_id": opt_b, "idempotency_key": "sel-2"})).json()
        assert second["supersedes_decision_id"] == first["id"]

        mine = (await c2.get(f"/api/portal/decision-rooms/{rid}/decisions")).json()["items"]
        assert len(mine) == 2  # prior history remains intact — never deleted/mutated
        old_row = next(d for d in mine if d["id"] == first["id"])
        assert old_row["option_id"] == opt_a  # never rewritten


@pytest.mark.asyncio
async def test_option_id_must_belong_to_frozen_published_version(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, opt_a, _opt_b = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"])
        # Add a brand-new option AFTER publish — it exists live but is NOT in the frozen v1 snapshot.
        new_opt = (await c.post(f"/api/decision-rooms/{rid}/options", json={"customer_label": "Added after publish", "manual_price_cents": 1000})).json()
        new_opt_id = next(o["id"] for o in new_opt["options"] if o["customer_label"] == "Added after publish")
    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        resp = await c2.post(f"/api/portal/decision-rooms/{rid}/decisions", json={"action_type": "option_selected", "option_id": new_opt_id})
        assert resp.status_code == 404
        resp2 = await c2.post(f"/api/portal/decision-rooms/{rid}/decisions", json={"action_type": "option_selected", "option_id": "not-a-real-id"})
        assert resp2.status_code == 404
        # unaffected: the real frozen option still works
        ok = await c2.post(f"/api/portal/decision-rooms/{rid}/decisions", json={"action_type": "option_selected", "option_id": opt_a})
        assert ok.status_code == 201


@pytest.mark.asyncio
async def test_all_options_rejected_requires_room_flag(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, _opt_a, _opt_b = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"], title="No reject-all")
        rid2, _o1, _o2 = await _create_published_room(
            c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"], title="Reject-all allowed", extra={"allow_reject_all": True},
        )
    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        denied = await c2.post(f"/api/portal/decision-rooms/{rid}/decisions", json={"action_type": "all_options_rejected"})
        assert denied.status_code == 400
        allowed = await c2.post(f"/api/portal/decision-rooms/{rid2}/decisions", json={"action_type": "all_options_rejected"})
        assert allowed.status_code == 201
        assert allowed.json()["option_id"] is None
        # option_id must never be set alongside all_options_rejected
        bad = await c2.post(f"/api/portal/decision-rooms/{rid2}/decisions", json={"action_type": "all_options_rejected", "option_id": "x"})
        assert bad.status_code == 400


@pytest.mark.asyncio
async def test_change_requested_requires_flag_and_comment(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, _opt_a, _opt_b = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"], title="No change requests")
        rid2, _o1, _o2 = await _create_published_room(
            c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"], title="Change requests allowed", extra={"allow_change_requests": True},
        )
    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        flag_denied = await c2.post(f"/api/portal/decision-rooms/{rid}/decisions", json={"action_type": "change_requested", "comment": "Please change the color"})
        assert flag_denied.status_code == 400
        no_comment = await c2.post(f"/api/portal/decision-rooms/{rid2}/decisions", json={"action_type": "change_requested"})
        assert no_comment.status_code == 400
        ok = await c2.post(f"/api/portal/decision-rooms/{rid2}/decisions", json={"action_type": "change_requested", "comment": "Please change the color"})
        assert ok.status_code == 201
        assert ok.json()["comment"] == "Please change the color"


@pytest.mark.asyncio
async def test_closed_and_draft_rooms_reject_new_decisions(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, opt_a, _opt_b = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"])
        await c.post(f"/api/decision-rooms/{rid}/transition", json={"target": "closed"})
    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        # Still readable (historical record)...
        read = await c2.get(f"/api/portal/decision-rooms/{rid}")
        assert read.status_code == 200 and read.json()["status"] == "closed"
        # ...but no new decision writes accepted.
        denied = await c2.post(f"/api/portal/decision-rooms/{rid}/decisions", json={"action_type": "option_selected", "option_id": opt_a})
        assert denied.status_code == 400

    async with await _staff_client(ctx["owner_a"]) as c:
        draft_room = (await c.post("/api/decision-rooms", json={"title": "Still drafting", "customer_id": ctx["customer_a"]["id"]})).json()
    _clear()
    async with await _anon_client() as c3:
        c3.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        denied_draft = await c3.post(f"/api/portal/decision-rooms/{draft_room['id']}/decisions", json={"action_type": "option_selected", "option_id": "x"})
        assert denied_draft.status_code == 404  # unpublished room existence never leaks


@pytest.mark.asyncio
async def test_public_token_submit_and_list_parity(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, opt_a, _opt_b = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"])
        raw, _ = await mint_public_action_token(
            tenant_id=ctx["ta"], action="decision_room_view", parent_type="decision_room", parent_id=rid, single_use=False,
        )
    _clear()
    async with await _anon_client() as c2:
        resp = await c2.post(f"/api/public/decision-rooms/{rid}/decisions", params={"t": raw}, json={
            "action_type": "option_rejected", "option_id": opt_a, "signer_name": "Public Jane",
        })
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["source_access_mode"] == "public_token"
        assert body["customer_id"] is None
        assert body["public_token_id"]
        assert body["actor_display"] == "Public Jane"

        listed = (await c2.get(f"/api/public/decision-rooms/{rid}/decisions", params={"t": raw})).json()["items"]
        assert len(listed) == 1 and listed[0]["id"] == body["id"]


@pytest.mark.asyncio
async def test_tenant_isolation_on_decision_submission(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, opt_a, _opt_b = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"])
    _clear()
    raw_b, _ = await mint_public_action_token(
        tenant_id=ctx["tb"], action="decision_room_view", parent_type="decision_room", parent_id=rid, single_use=False,
    )
    async with await _anon_client() as c2:
        resp = await c2.post(f"/api/public/decision-rooms/{rid}/decisions", params={"t": raw_b}, json={"action_type": "option_selected", "option_id": opt_a})
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_staff_can_list_and_acknowledge_but_never_mutates_commercial_records(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, opt_a, _opt_b = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"])
    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        submitted = (await c2.post(f"/api/portal/decision-rooms/{rid}/decisions", json={"action_type": "option_selected", "option_id": opt_a})).json()
    _clear()

    order_before = await db.orders.find_one({"id": ctx["order_a"]["id"]}, {"_id": 0})

    async with await _staff_client(ctx["owner_a"]) as c:
        staff_list = (await c.get(f"/api/decision-rooms/{rid}/decisions")).json()["items"]
        assert len(staff_list) == 1 and staff_list[0]["internal_review_status"] == "pending_review"

        ack = await c.post(f"/api/decision-rooms/{rid}/decisions/{submitted['id']}/acknowledge")
        assert ack.status_code == 200
        assert ack.json()["internal_review_status"] == "acknowledged"
        # action_type/option_id/pricing are never touched by acknowledge
        assert ack.json()["action_type"] == "option_selected"
        assert ack.json()["option_id"] == opt_a

    order_after = await db.orders.find_one({"id": ctx["order_a"]["id"]}, {"_id": 0})
    assert order_before == order_after  # zero commercial mutation from any of this


@pytest.mark.asyncio
async def test_customer_cannot_set_internal_review_fields(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, opt_a, _opt_b = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"])
    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        resp = await c2.post(f"/api/portal/decision-rooms/{rid}/decisions", json={
            "action_type": "option_selected", "option_id": opt_a,
            "internal_review_status": "acknowledged", "customer_id": "someone-else",
        })
        assert resp.status_code == 201
        body = resp.json()
        # Client-supplied identity/review fields are silently ignored — always server-derived.
        assert body["internal_review_status"] == "pending_review"
        assert body["customer_id"] == ctx["customer_a"]["id"]
