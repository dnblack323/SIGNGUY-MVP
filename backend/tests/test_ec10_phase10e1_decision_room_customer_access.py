"""EC10 Phase 10E-1 — Customer Portal + Public Token access to a published
Decision Room (read-only). No selection/rejection/comment/question actions
exist yet — this file only tests RETRIEVAL and its access-control/state
boundaries.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

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
    ta = f"t-ec10e1-a-{suffix}"
    tb = f"t-ec10e1-b-{suffix}"
    owner_a = {"id": f"u-a-{suffix}", "tenant_id": ta, "email": f"a-{suffix}@example.com", "role": "owner", "is_active": True}
    owner_b = {"id": f"u-b-{suffix}", "tenant_id": tb, "email": f"b-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([{"id": ta, "slug": ta, "name": "TA"}, {"id": tb, "slug": tb, "name": "TB"}])
    await db.users.insert_many([owner_a, owner_b])

    customer_a = {"id": f"cust-a-{suffix}", "tenant_id": ta, "name": "Jane Customer", "archived": False}
    customer_a2 = {"id": f"cust-a2-{suffix}", "tenant_id": ta, "name": "Other Customer Same Tenant", "archived": False}
    order_a = {"id": f"o-{suffix}", "tenant_id": ta, "number": 1, "customer_id": customer_a["id"], "job_name": "Test Order", "status": "draft"}
    await db.customers.insert_many([customer_a, customer_a2])
    await db.orders.insert_one(order_a)

    # Portal identity for customer_a, with the new Phase 10E-1 permission.
    portal_identity_a = {
        "id": f"pi-a-{suffix}", "tenant_id": ta, "portal_type": "customer", "customer_id": customer_a["id"],
        "email": f"jane-{suffix}@example.com", "status": "active",
        "permissions": ["portal:view_decision_rooms"], "permissions_preset": "custom",
    }
    portal_identity_a2 = {
        "id": f"pi-a2-{suffix}", "tenant_id": ta, "portal_type": "customer", "customer_id": customer_a2["id"],
        "email": f"other-{suffix}@example.com", "status": "active",
        "permissions": ["portal:view_decision_rooms"], "permissions_preset": "custom",
    }
    portal_identity_no_perm = {
        "id": f"pi-noperm-{suffix}", "tenant_id": ta, "portal_type": "customer", "customer_id": customer_a["id"],
        "email": f"noperm-{suffix}@example.com", "status": "active", "permissions": [], "permissions_preset": "custom",
    }
    await db.portal_identities.insert_many([portal_identity_a, portal_identity_a2, portal_identity_no_perm])

    token_a = create_portal_token(portal_identity_id=portal_identity_a["id"], tenant_id=ta, customer_id=customer_a["id"], portal_type="customer")
    token_a2 = create_portal_token(portal_identity_id=portal_identity_a2["id"], tenant_id=ta, customer_id=customer_a2["id"], portal_type="customer")
    token_noperm = create_portal_token(portal_identity_id=portal_identity_no_perm["id"], tenant_id=ta, customer_id=customer_a["id"], portal_type="customer")

    yield {
        "owner_a": owner_a, "owner_b": owner_b, "ta": ta, "tb": tb,
        "customer_a": customer_a, "customer_a2": customer_a2, "order_a": order_a,
        "portal_token_a": token_a, "portal_token_a2": token_a2, "portal_token_noperm": token_noperm,
    }
    _clear()


async def _create_published_room(c, *, customer_id, order_id, title="Wrap options"):
    """Creates a room with 2 active options + 1 archived option, publishes
    it, and returns the room id + the (frozen) published options snapshot."""
    room = (await c.post("/api/decision-rooms", json={
        "title": title, "internal_name": "internal codename", "customer_safe_intro": "Pick the option that fits.",
        "customer_id": customer_id, "order_id": order_id,
    })).json()
    rid = room["id"]
    opt_a = (await c.post(f"/api/decision-rooms/{rid}/options", json={
        "customer_label": "Standard", "customer_safe_description": "Good everyday option.",
        "manual_price_cents": 25000, "internal_notes": "Cost $80, margin 68%",
    })).json()["options"][0]
    await c.post(f"/api/decision-rooms/{rid}/options", json={"customer_label": "Premium", "manual_price_cents": 45000})
    archived = (await c.post(f"/api/decision-rooms/{rid}/options", json={"customer_label": "Discontinued", "manual_price_cents": 1000})).json()
    archived_id = next(o["id"] for o in archived["options"] if o["customer_label"] == "Discontinued")
    await c.post(f"/api/decision-rooms/{rid}/options/{archived_id}/archive")

    await c.post(f"/api/decision-rooms/{rid}/transition", json={"target": "ready"})
    published = (await c.post(f"/api/decision-rooms/{rid}/publish")).json()
    return rid, published


@pytest.mark.asyncio
async def test_portal_access_returns_published_room(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, _ = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"])
    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        list_resp = await c2.get("/api/portal/decision-rooms")
        assert list_resp.status_code == 200
        assert any(r["id"] == rid for r in list_resp.json()["items"])

        detail = await c2.get(f"/api/portal/decision-rooms/{rid}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["status"] == "published" and body["version_number"] == 1
        assert len(body["options"]) == 2  # archived "Discontinued" excluded


@pytest.mark.asyncio
async def test_portal_missing_permission_rejected(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, _ = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"])
    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_noperm']}"
        denied = await c2.get(f"/api/portal/decision-rooms/{rid}")
        assert denied.status_code == 403


@pytest.mark.asyncio
async def test_portal_customer_ownership_enforced(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, _ = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"])
    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a2']}"  # different customer, same tenant
        denied = await c2.get(f"/api/portal/decision-rooms/{rid}")
        assert denied.status_code == 404
        list_resp = await c2.get("/api/portal/decision-rooms")
        assert all(r["id"] != rid for r in list_resp.json()["items"])


@pytest.mark.asyncio
async def test_draft_room_inaccessible_to_portal_and_public(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        room = (await c.post("/api/decision-rooms", json={"title": "Still drafting", "customer_id": ctx["customer_a"]["id"]})).json()
        rid = room["id"]
        raw, _ = await mint_public_action_token(
            tenant_id=ctx["ta"], action="decision_room_view", parent_type="decision_room", parent_id=rid, single_use=False,
        )
    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        denied = await c2.get(f"/api/portal/decision-rooms/{rid}")
        assert denied.status_code == 404
    async with await _anon_client() as c3:
        denied_public = await c3.get(f"/api/public/decision-rooms/{rid}", params={"t": raw})
        assert denied_public.status_code == 404


@pytest.mark.asyncio
async def test_public_token_valid_access_and_published_version_only(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, published = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"], title="Original title")
        raw, _ = await mint_public_action_token(
            tenant_id=ctx["ta"], action="decision_room_view", parent_type="decision_room", parent_id=rid, single_use=False,
        )
        # Edit AFTER publish — current_version diverges; public view must still show the frozen v1 content.
        opt_id = published["options"][0]["id"]
        await c.patch(f"/api/decision-rooms/{rid}/options/{opt_id}", json={"customer_label": "Renamed after publish"})
    _clear()
    async with await _anon_client() as c2:
        resp = await c2.get(f"/api/public/decision-rooms/{rid}", params={"t": raw})
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Original title"
        assert body["version_number"] == 1
        labels = {o["customer_label"] for o in body["options"]}
        assert "Renamed after publish" not in labels
        assert "Standard" in labels  # unchanged, frozen at publish time


@pytest.mark.asyncio
async def test_public_token_invalid_expired_revoked_and_wrong_purpose(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, _ = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"])
        raw_expired, doc_expired = await mint_public_action_token(
            tenant_id=ctx["ta"], action="decision_room_view", parent_type="decision_room", parent_id=rid, single_use=False,
        )
        raw_revoked, doc_revoked = await mint_public_action_token(
            tenant_id=ctx["ta"], action="decision_room_view", parent_type="decision_room", parent_id=rid, single_use=False,
        )
        raw_wrong_purpose, _ = await mint_public_action_token(
            tenant_id=ctx["ta"], action="quote_view", parent_type="quote", parent_id="some-quote-id", single_use=False,
        )
    await db.public_action_tokens.update_one({"id": doc_expired["id"]}, {"$set": {"expires_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()}})
    await db.public_action_tokens.update_one({"id": doc_revoked["id"]}, {"$set": {"revoked": True}})
    _clear()
    async with await _anon_client() as c2:
        invalid = await c2.get(f"/api/public/decision-rooms/{rid}", params={"t": "not-a-real-token"})
        assert invalid.status_code == 401
        expired = await c2.get(f"/api/public/decision-rooms/{rid}", params={"t": raw_expired})
        assert expired.status_code == 410
        revoked = await c2.get(f"/api/public/decision-rooms/{rid}", params={"t": raw_revoked})
        assert revoked.status_code == 410
        wrong_purpose = await c2.get(f"/api/public/decision-rooms/{rid}", params={"t": raw_wrong_purpose})
        assert wrong_purpose.status_code == 403


@pytest.mark.asyncio
async def test_internal_and_cost_fields_excluded_and_inactive_options_excluded(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, _ = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"])
        raw, _ = await mint_public_action_token(
            tenant_id=ctx["ta"], action="decision_room_view", parent_type="decision_room", parent_id=rid, single_use=False,
        )
    _clear()
    async with await _anon_client() as c2:
        body = (await c2.get(f"/api/public/decision-rooms/{rid}", params={"t": raw})).json()
        assert "internal_name" not in body
        labels = {o["customer_label"] for o in body["options"]}
        assert "Discontinued" not in labels  # inactive option excluded
        for opt in body["options"]:
            for forbidden in ("internal_notes", "internal_name", "created_by_user_id", "updated_by_user_id",
                               "pricing_snapshot_id", "suggested_price_cents", "manual_price_cents",
                               "selected_price_source", "proof_id", "quote_line_item_id", "order_item_id"):
                assert forbidden not in opt
            assert "$80" not in str(opt)  # cost text from internal_notes never leaks
            assert "margin" not in str(opt).lower()


@pytest.mark.asyncio
async def test_expired_and_closed_room_states_remain_viewable(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, _ = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"])
        raw, _ = await mint_public_action_token(
            tenant_id=ctx["ta"], action="decision_room_view", parent_type="decision_room", parent_id=rid, single_use=False,
        )
        expired = await c.post(f"/api/decision-rooms/{rid}/transition", json={"target": "expired"})
        assert expired.status_code == 200
    _clear()
    async with await _anon_client() as c2:
        resp = await c2.get(f"/api/public/decision-rooms/{rid}", params={"t": raw})
        assert resp.status_code == 200 and resp.json()["status"] == "expired"

    async with await _staff_client(ctx["owner_a"]) as c:
        rid2, _ = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"], title="Second room")
        raw2, _ = await mint_public_action_token(
            tenant_id=ctx["ta"], action="decision_room_view", parent_type="decision_room", parent_id=rid2, single_use=False,
        )
        closed = await c.post(f"/api/decision-rooms/{rid2}/transition", json={"target": "closed"})
        assert closed.status_code == 200
    _clear()
    async with await _anon_client() as c3:
        resp2 = await c3.get(f"/api/public/decision-rooms/{rid2}", params={"t": raw2})
        assert resp2.status_code == 200 and resp2.json()["status"] == "closed"


@pytest.mark.asyncio
async def test_tenant_isolation_public_token_cannot_cross_tenant(ctx):
    async with await _staff_client(ctx["owner_a"]) as c:
        rid, _ = await _create_published_room(c, customer_id=ctx["customer_a"]["id"], order_id=ctx["order_a"]["id"])
    _clear()
    # A token minted for tenant B trying to view tenant A's room id: resolve_public_token
    # binds the token strictly to its own tenant, so the room lookup happens
    # under tenant B — the room (which only exists in tenant A) is invisible.
    raw_b, _ = await mint_public_action_token(
        tenant_id=ctx["tb"], action="decision_room_view", parent_type="decision_room", parent_id=rid, single_use=False,
    )
    async with await _anon_client() as c2:
        resp = await c2.get(f"/api/public/decision-rooms/{rid}", params={"t": raw_b})
        assert resp.status_code == 404
