"""EC10 Phase 10E-1 (completion gap fix) — customer-safe DERIVATIVE media
access for a published Decision Room (images, proof previews, rendered
markup previews). No selection/rejection/comment actions exist yet — this
file only tests customer-safe MEDIA retrieval and its access boundaries.
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
    ta = f"t-ec10e1m-a-{suffix}"
    tb = f"t-ec10e1m-b-{suffix}"
    owner_a = {"id": f"u-a-{suffix}", "tenant_id": ta, "email": f"a-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([{"id": ta, "slug": ta, "name": "TA"}, {"id": tb, "slug": tb, "name": "TB"}])
    await db.users.insert_one(owner_a)

    customer_a = {"id": f"cust-a-{suffix}", "tenant_id": ta, "name": "Jane Customer", "archived": False}
    order_a = {"id": f"o-{suffix}", "tenant_id": ta, "number": 1, "customer_id": customer_a["id"], "job_name": "Test Order", "status": "draft"}
    await db.customers.insert_one(customer_a)
    await db.orders.insert_one(order_a)

    portal_identity_a = {
        "id": f"pi-a-{suffix}", "tenant_id": ta, "portal_type": "customer", "customer_id": customer_a["id"],
        "email": f"jane-{suffix}@example.com", "status": "active",
        "permissions": ["portal:view_decision_rooms"], "permissions_preset": "custom",
    }
    await db.portal_identities.insert_one(portal_identity_a)
    portal_token_a = create_portal_token(portal_identity_id=portal_identity_a["id"], tenant_id=ta, customer_id=customer_a["id"], portal_type="customer")

    yield {"owner_a": owner_a, "ta": ta, "tb": tb, "customer_a": customer_a, "order_a": order_a, "portal_token_a": portal_token_a, "suffix": suffix}
    _clear()


async def _upload_file(c, *, visibility="internal", filename="photo.png", content=b"\x89PNG\r\n\x1a\n" + b"0" * 40, mime="image/png"):
    up = await c.post("/api/files/upload", files={"file": (filename, content, mime)}, data={"visibility": visibility})
    assert up.status_code == 201, up.text
    return up.json()["file"]["id"]


@pytest.mark.asyncio
async def test_portal_and_public_can_retrieve_referenced_customer_safe_media(ctx):
    owner_a, ta, customer_a, order_a = ctx["owner_a"], ctx["ta"], ctx["customer_a"], ctx["order_a"]
    async with await _staff_client(owner_a) as c:
        customer_visible_file = await _upload_file(c, visibility="customer_visible", content=b"\x89PNG\r\n\x1a\n" + b"1" * 40)
        preview_file = await _upload_file(c, visibility="internal", filename="preview.png", content=b"\x89PNG\r\n\x1a\n" + b"2" * 40)  # structurally-safe role, no flag needed
        proof_file = await _upload_file(c, visibility="internal", filename="proof.png", content=b"\x89PNG\r\n\x1a\n" + b"3" * 40)
        proof_doc = {"id": f"proof-{ctx['suffix']}", "tenant_id": ta, "number": 1, "parent_type": "order", "parent_id": order_a["id"], "title": "Proof", "status": "draft", "current_file_id": proof_file}
        await db.proofs.insert_one(proof_doc)

        room = (await c.post("/api/decision-rooms", json={"title": "Wrap options", "customer_id": customer_a["id"], "order_id": order_a["id"]})).json()
        rid = room["id"]
        opt = (await c.post(f"/api/decision-rooms/{rid}/options", json={
            "customer_label": "Standard", "manual_price_cents": 1000,
            "file_ids": [customer_visible_file], "rendered_preview_file_id": preview_file, "proof_id": proof_doc["id"],
        })).json()["options"][0]
        await c.post(f"/api/decision-rooms/{rid}/options", json={"customer_label": "Premium", "manual_price_cents": 2000})
        await c.post(f"/api/decision-rooms/{rid}/transition", json={"target": "ready"})
        await c.post(f"/api/decision-rooms/{rid}/publish")
        raw, _ = await mint_public_action_token(tenant_id=ta, action="decision_room_view", parent_type="decision_room", parent_id=rid, single_use=False)

    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        r1 = await c2.get(f"/api/portal/decision-rooms/{rid}/media/{customer_visible_file}")
        assert r1.status_code == 200 and r1.headers["content-type"].startswith("image/")
        r2 = await c2.get(f"/api/portal/decision-rooms/{rid}/media/{preview_file}")
        assert r2.status_code == 200  # structurally-safe role (rendered preview) — no visibility flag required
        r3 = await c2.get(f"/api/portal/decision-rooms/{rid}/media/{proof_file}")
        assert r3.status_code == 200  # resolved via frozen `_frozen_proof_preview_file_id`

    async with await _anon_client() as c3:
        pub1 = await c3.get(f"/api/public/decision-rooms/{rid}/media/{customer_visible_file}", params={"t": raw})
        assert pub1.status_code == 200
        pub2 = await c3.get(f"/api/public/decision-rooms/{rid}/media/{proof_file}", params={"t": raw})
        assert pub2.status_code == 200

    # Confirm the customer-safe room payload actually surfaces the resolvable proof preview id.
    _clear()
    async with await _anon_client() as c4:
        c4.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        body = (await c4.get(f"/api/portal/decision-rooms/{rid}")).json()
        std = next(o for o in body["options"] if o["customer_label"] == "Standard")
        assert std["proof_preview_file_id"] == proof_file
        assert "proof_id" not in std  # internal linkage id itself never leaks


@pytest.mark.asyncio
async def test_unrelated_and_internal_only_file_rejected(ctx):
    owner_a, ta, customer_a, order_a = ctx["owner_a"], ctx["ta"], ctx["customer_a"], ctx["order_a"]
    async with await _staff_client(owner_a) as c:
        internal_flagged_file = await _upload_file(c, visibility="internal")  # in file_ids, but never flipped customer_visible
        unrelated_file = await _upload_file(c, visibility="customer_visible")  # valid file, never referenced by this room at all

        room = (await c.post("/api/decision-rooms", json={"title": "Wrap options", "customer_id": customer_a["id"], "order_id": order_a["id"]})).json()
        rid = room["id"]
        await c.post(f"/api/decision-rooms/{rid}/options", json={"customer_label": "A", "manual_price_cents": 1000, "file_ids": [internal_flagged_file]})
        await c.post(f"/api/decision-rooms/{rid}/options", json={"customer_label": "B", "manual_price_cents": 2000})
        await c.post(f"/api/decision-rooms/{rid}/transition", json={"target": "ready"})
        await c.post(f"/api/decision-rooms/{rid}/publish")

    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        internal_denied = await c2.get(f"/api/portal/decision-rooms/{rid}/media/{internal_flagged_file}")
        assert internal_denied.status_code == 404
        unrelated_denied = await c2.get(f"/api/portal/decision-rooms/{rid}/media/{unrelated_file}")
        assert unrelated_denied.status_code == 404
        guessed_denied = await c2.get(f"/api/portal/decision-rooms/{rid}/media/does-not-exist")
        assert guessed_denied.status_code == 404


@pytest.mark.asyncio
async def test_draft_only_and_post_publish_media_rejected(ctx):
    """Media attached AFTER a room's already-published version was frozen
    must NOT become retrievable — the frozen-version rule, not the live
    option list, controls access."""
    owner_a, ta, customer_a, order_a = ctx["owner_a"], ctx["ta"], ctx["customer_a"], ctx["order_a"]
    async with await _staff_client(owner_a) as c:
        room = (await c.post("/api/decision-rooms", json={"title": "Wrap options", "customer_id": customer_a["id"], "order_id": order_a["id"]})).json()
        rid = room["id"]
        opt = (await c.post(f"/api/decision-rooms/{rid}/options", json={"customer_label": "A", "manual_price_cents": 1000})).json()["options"][0]
        await c.post(f"/api/decision-rooms/{rid}/options", json={"customer_label": "B", "manual_price_cents": 2000})
        await c.post(f"/api/decision-rooms/{rid}/transition", json={"target": "ready"})
        await c.post(f"/api/decision-rooms/{rid}/publish")

        # A brand-new customer-visible file attached to a live option AFTER publish.
        late_file = await _upload_file(c, visibility="customer_visible", content=b"\x89PNG\r\n\x1a\n" + b"9" * 40)
        await c.patch(f"/api/decision-rooms/{rid}/options/{opt['id']}", json={"file_ids": [late_file]})

    _clear()
    async with await _anon_client() as c2:
        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        denied = await c2.get(f"/api/portal/decision-rooms/{rid}/media/{late_file}")
        assert denied.status_code == 404  # not in the frozen v1 snapshot yet

        # room content itself still reflects only the frozen v1 state too
        body = (await c2.get(f"/api/portal/decision-rooms/{rid}")).json()
        std = next(o for o in body["options"] if o["customer_label"] == "A")
        assert late_file not in (std.get("file_ids") or [])


@pytest.mark.asyncio
async def test_public_token_state_boundaries_for_media(ctx):
    owner_a, ta, customer_a, order_a = ctx["owner_a"], ctx["ta"], ctx["customer_a"], ctx["order_a"]
    async with await _staff_client(owner_a) as c:
        safe_file = await _upload_file(c, visibility="customer_visible")
        room = (await c.post("/api/decision-rooms", json={"title": "Wrap options", "customer_id": customer_a["id"], "order_id": order_a["id"]})).json()
        rid = room["id"]
        await c.post(f"/api/decision-rooms/{rid}/options", json={"customer_label": "A", "manual_price_cents": 1000, "file_ids": [safe_file]})
        await c.post(f"/api/decision-rooms/{rid}/options", json={"customer_label": "B", "manual_price_cents": 2000})
        await c.post(f"/api/decision-rooms/{rid}/transition", json={"target": "ready"})
        await c.post(f"/api/decision-rooms/{rid}/publish")

        raw_expired, doc_expired = await mint_public_action_token(tenant_id=ta, action="decision_room_view", parent_type="decision_room", parent_id=rid, single_use=False)
        raw_revoked, doc_revoked = await mint_public_action_token(tenant_id=ta, action="decision_room_view", parent_type="decision_room", parent_id=rid, single_use=False)
        raw_wrong, _ = await mint_public_action_token(tenant_id=ta, action="quote_view", parent_type="quote", parent_id="some-quote", single_use=False)

    await db.public_action_tokens.update_one({"id": doc_expired["id"]}, {"$set": {"expires_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()}})
    await db.public_action_tokens.update_one({"id": doc_revoked["id"]}, {"$set": {"revoked": True}})
    _clear()
    async with await _anon_client() as c2:
        expired = await c2.get(f"/api/public/decision-rooms/{rid}/media/{safe_file}", params={"t": raw_expired})
        assert expired.status_code == 410
        revoked = await c2.get(f"/api/public/decision-rooms/{rid}/media/{safe_file}", params={"t": raw_revoked})
        assert revoked.status_code == 410
        wrong_purpose = await c2.get(f"/api/public/decision-rooms/{rid}/media/{safe_file}", params={"t": raw_wrong})
        assert wrong_purpose.status_code == 403


@pytest.mark.asyncio
async def test_cross_tenant_media_and_unavailable_object_and_no_storage_path_leak(ctx):
    owner_a, ta, tb, customer_a, order_a = ctx["owner_a"], ctx["ta"], ctx["tb"], ctx["customer_a"], ctx["order_a"]
    async with await _staff_client(owner_a) as c:
        safe_file = await _upload_file(c, visibility="customer_visible")
        room = (await c.post("/api/decision-rooms", json={"title": "Wrap options", "customer_id": customer_a["id"], "order_id": order_a["id"]})).json()
        rid = room["id"]
        opt = (await c.post(f"/api/decision-rooms/{rid}/options", json={"customer_label": "A", "manual_price_cents": 1000, "file_ids": [safe_file]})).json()["options"][0]
        await c.post(f"/api/decision-rooms/{rid}/options", json={"customer_label": "B", "manual_price_cents": 2000})
        await c.post(f"/api/decision-rooms/{rid}/transition", json={"target": "ready"})
        await c.post(f"/api/decision-rooms/{rid}/publish")

        # a File record whose bytes never actually made it to object storage (bogus key)
        unavailable_file_id = f"file-missing-{ctx['suffix']}"
        await db.files.insert_one({
            "id": unavailable_file_id, "tenant_id": ta, "storage_key": "does/not/exist/in/storage.png",
            "original_filename": "gone.png", "mime_type": "image/png", "size_bytes": 0,
            "uploaded_by": owner_a["id"], "visibility": "customer_visible", "archived": False,
        })
        await c.patch(f"/api/decision-rooms/{rid}/options/{opt['id']}", json={"file_ids": [safe_file, unavailable_file_id]})
        await c.post(f"/api/decision-rooms/{rid}/publish")  # re-publish so the bogus file is in the frozen v2 snapshot too

    raw_b, _ = await mint_public_action_token(tenant_id=tb, action="decision_room_view", parent_type="decision_room", parent_id=rid, single_use=False)
    _clear()
    async with await _anon_client() as c2:
        cross_tenant = await c2.get(f"/api/public/decision-rooms/{rid}/media/{safe_file}", params={"t": raw_b})
        assert cross_tenant.status_code == 404  # tenant B's token cannot see tenant A's room at all

        unavailable = await c2.get(f"/api/public/decision-rooms/{rid}/media/{unavailable_file_id}", params={"t": raw_b})
        assert unavailable.status_code == 404  # (still cross-tenant-blocked; asserts no crash/leak either way)

        c2.headers["Authorization"] = f"Bearer {ctx['portal_token_a']}"
        unavailable_same_tenant = await c2.get(f"/api/portal/decision-rooms/{rid}/media/{unavailable_file_id}")
        assert unavailable_same_tenant.status_code == 404
        assert "does/not/exist/in/storage.png" not in unavailable_same_tenant.text  # raw storage_key never exposed

        room_body = await c2.get(f"/api/portal/decision-rooms/{rid}")
        assert "does/not/exist/in/storage.png" not in room_body.text
        assert "storage_key" not in room_body.text
