"""EC10 Phase 10D — Customer Decision Room backend tests (internal authoring
only). No customer/public access, no decision-to-order integration, and no
pricing recalculation exists anywhere in this phase — several tests below
explicitly assert that.
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
    ta = f"t-ec10d-a-{suffix}"
    tb = f"t-ec10d-b-{suffix}"
    ua = {"id": f"u-a-{suffix}", "tenant_id": ta, "email": f"a-{suffix}@example.com", "role": "owner", "is_active": True}
    staff_a = {"id": f"s-a-{suffix}", "tenant_id": ta, "email": f"staff-a-{suffix}@example.com", "role": "staff", "is_active": True}
    customer_role_a = {"id": f"c-a-{suffix}", "tenant_id": ta, "email": f"cust-a-{suffix}@example.com", "role": "customer", "is_active": True}
    ub = {"id": f"u-b-{suffix}", "tenant_id": tb, "email": f"b-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([{"id": ta, "slug": ta, "name": "TA"}, {"id": tb, "slug": tb, "name": "TB"}])
    await db.users.insert_many([ua, staff_a, customer_role_a, ub])

    customer_a = {"id": f"cust-{suffix}", "tenant_id": ta, "name": "Jane Customer", "archived": False}
    customer_b = {"id": f"custb-{suffix}", "tenant_id": tb, "name": "Other Tenant Customer", "archived": False}
    await db.customers.insert_many([customer_a, customer_b])

    quote_a = {"id": f"q-{suffix}", "tenant_id": ta, "number": 1, "customer_id": customer_a["id"],
               "job_name": "Test Quote", "status": "draft"}
    order_a = {"id": f"o-{suffix}", "tenant_id": ta, "number": 1, "customer_id": customer_a["id"],
               "job_name": "Test Order", "status": "draft"}
    order_item_a = {"id": f"oi-{suffix}", "tenant_id": ta, "order_id": order_a["id"], "description": "Banner", "quantity": 1}
    quote_line_item_a = {"id": f"qli-{suffix}", "tenant_id": ta, "quote_id": quote_a["id"], "description": "Banner"}
    await db.quotes.insert_one(quote_a)
    await db.orders.insert_one(order_a)
    await db.order_items.insert_one(order_item_a)
    await db.quote_line_items.insert_one(quote_line_item_a)

    snapshot_a = {"id": f"snap-{suffix}", "tenant_id": ta, "source_type": "order_item", "source_id": order_item_a["id"],
                  "selected_final_price_cents": 45000, "status": "active"}
    snapshot_b = {"id": f"snapb-{suffix}", "tenant_id": tb, "source_type": "order_item", "source_id": "x",
                  "selected_final_price_cents": 1000, "status": "active"}
    await db.pricing_snapshot_records.insert_many([snapshot_a, snapshot_b])

    proof_a = {"id": f"proof-{suffix}", "tenant_id": ta, "number": 1, "parent_type": "order",
               "parent_id": order_a["id"], "title": "Proof", "status": "draft"}
    await db.proofs.insert_one(proof_a)

    yield {
        "ua": ua, "staff_a": staff_a, "customer_role_a": customer_role_a, "ub": ub,
        "ta": ta, "tb": tb, "customer_a": customer_a, "customer_b": customer_b,
        "quote_a": quote_a, "order_a": order_a, "order_item_a": order_item_a,
        "quote_line_item_a": quote_line_item_a, "snapshot_a": snapshot_a, "snapshot_b": snapshot_b, "proof_a": proof_a,
    }
    _clear()


async def _upload_image(c, seed: bytes = b"0" * 40) -> str:
    up = await c.post("/api/files/upload", files={"file": ("photo.png", b"\x89PNG\r\n\x1a\n" + seed, "image/png")})
    assert up.status_code == 201, up.text
    return up.json()["file"]["id"]


async def _create_room(c, **overrides) -> dict:
    payload = {"title": "Wrap options for Jane"}
    payload.update(overrides)
    r = await c.post("/api/decision-rooms", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _option_payload(**overrides) -> dict:
    payload = {"customer_label": "Standard", "internal_name": "Std"}
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_create_draft_room_and_attach_context(ctx):
    ua, customer_a, quote_a, order_a, order_item_a = ctx["ua"], ctx["customer_a"], ctx["quote_a"], ctx["order_a"], ctx["order_item_a"]
    async with await _client(ua) as c:
        room = await _create_room(
            c, customer_id=customer_a["id"], quote_id=quote_a["id"], order_id=order_a["id"], order_item_id=order_item_a["id"],
        )
        assert room["status"] == "draft"
        assert room["current_version"] == 0 and room["published_version"] == 0
        assert room["customer_id"] == customer_a["id"]
        assert room["require_internal_acceptance"] is True  # default per owner decision #1


@pytest.mark.asyncio
async def test_cross_tenant_context_references_rejected(ctx):
    ua, customer_b, tb = ctx["ua"], ctx["customer_b"], ctx["tb"]
    async with await _client(ua) as c:
        r = await c.post("/api/decision-rooms", json={"title": "X", "customer_id": customer_b["id"]})
        assert r.status_code == 404
        r2 = await c.post("/api/decision-rooms", json={"title": "X", "order_id": "does-not-exist"})
        assert r2.status_code == 404


@pytest.mark.asyncio
async def test_add_multiple_options_badges_and_recommended_exclusivity(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        room = await _create_room(c)
        rid = room["id"]
        a = (await c.post(f"/api/decision-rooms/{rid}/options", json=_option_payload(customer_label="A", badge_type="recommended"))).json()
        opt_a = a["options"][0]
        assert opt_a["badge_type"] == "recommended"

        b = await c.post(
            f"/api/decision-rooms/{rid}/options",
            json=_option_payload(customer_label="B", badge_type="recommended", custom_badge_text="  Fancy\x00 Badge  "),
        )
        assert b.status_code == 201
        options = b.json()["options"]
        opt_a_after = next(o for o in options if o["customer_label"] == "A")
        opt_b_after = next(o for o in options if o["customer_label"] == "B")
        assert opt_a_after["badge_type"] == "none"   # exclusivity enforced — A demoted
        assert opt_b_after["badge_type"] == "recommended"
        assert opt_b_after["custom_badge_text"] == "Fancy Badge"  # sanitized (control char stripped, trimmed)

        c3 = await c.post(f"/api/decision-rooms/{rid}/options", json=_option_payload(customer_label="C", badge_type="custom", custom_badge_text="Best for Trucks"))
        assert c3.status_code == 201
        opt_c = next(o for o in c3.json()["options"] if o["customer_label"] == "C")
        assert opt_c["badge_type"] == "custom" and opt_c["custom_badge_text"] == "Best for Trucks"


@pytest.mark.asyncio
async def test_duplicate_option_new_id_and_does_not_inherit_recommended(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        room = await _create_room(c)
        rid = room["id"]
        created = await c.post(f"/api/decision-rooms/{rid}/options", json=_option_payload(customer_label="Premium", badge_type="recommended"))
        source_id = created.json()["options"][0]["id"]

        dup = await c.post(f"/api/decision-rooms/{rid}/options/{source_id}/duplicate")
        assert dup.status_code == 201
        options = dup.json()["options"]
        source_after = next(o for o in options if o["id"] == source_id)
        duplicate_opt = next(o for o in options if o["id"] != source_id)
        assert duplicate_opt["id"] != source_id
        assert duplicate_opt["badge_type"] == "none"          # does not inherit Recommended
        assert source_after["badge_type"] == "recommended"    # source untouched
        assert duplicate_opt["customer_label"] == "Premium"   # descriptions copied


@pytest.mark.asyncio
async def test_reorder_options(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        room = await _create_room(c)
        rid = room["id"]
        r1 = (await c.post(f"/api/decision-rooms/{rid}/options", json=_option_payload(customer_label="First"))).json()
        id1 = r1["options"][0]["id"]
        r2 = (await c.post(f"/api/decision-rooms/{rid}/options", json=_option_payload(customer_label="Second"))).json()
        id2 = next(o["id"] for o in r2["options"] if o["customer_label"] == "Second")

        reordered = await c.patch(f"/api/decision-rooms/{rid}/options/reorder", json={"option_ids": [id2, id1]})
        assert reordered.status_code == 200
        by_id = {o["id"]: o for o in reordered.json()["options"]}
        assert by_id[id2]["display_order"] == 0 and by_id[id1]["display_order"] == 1

        mismatch = await c.patch(f"/api/decision-rooms/{rid}/options/reorder", json={"option_ids": [id1]})
        assert mismatch.status_code == 400


@pytest.mark.asyncio
async def test_archive_and_restore_option(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        room = await _create_room(c)
        rid = room["id"]
        opt = (await c.post(f"/api/decision-rooms/{rid}/options", json=_option_payload())).json()["options"][0]

        archived = await c.post(f"/api/decision-rooms/{rid}/options/{opt['id']}/archive")
        assert archived.status_code == 200
        assert next(o for o in archived.json()["options"] if o["id"] == opt["id"])["active"] is False

        restored = await c.post(f"/api/decision-rooms/{rid}/options/{opt['id']}/restore")
        assert restored.status_code == 200
        assert next(o for o in restored.json()["options"] if o["id"] == opt["id"])["active"] is True


@pytest.mark.asyncio
async def test_attach_file_proof_markup_and_cross_tenant_rejection(ctx):
    ua, ub, proof_a = ctx["ua"], ctx["ub"], ctx["proof_a"]
    async with await _client(ua) as c:
        fid = await _upload_image(c)
        room = await _create_room(c)
        rid = room["id"]
        opt = (await c.post(f"/api/decision-rooms/{rid}/options", json=_option_payload())).json()["options"][0]

        markup = (await c.post("/api/markup", json={"source_file_id": fid})).json()

        attach = await c.post(
            f"/api/decision-rooms/{rid}/options/{opt['id']}/media/attach",
            json={"file_ids": [fid], "proof_id": proof_a["id"], "visual_markup_id": markup["id"], "thumbnail_file_id": fid},
        )
        assert attach.status_code == 200
        updated = next(o for o in attach.json()["options"] if o["id"] == opt["id"])
        assert updated["file_ids"] == [fid] and updated["proof_id"] == proof_a["id"] and updated["visual_markup_id"] == markup["id"]

        detach = await c.post(f"/api/decision-rooms/{rid}/options/{opt['id']}/media/detach", json={"field_names": ["proof_id", "file_ids"]})
        assert detach.status_code == 200
        after = next(o for o in detach.json()["options"] if o["id"] == opt["id"])
        assert after["proof_id"] is None and after["file_ids"] == []
    _clear()
    async with await _client(ub) as c2:
        room_b = await _create_room(c2)
        opt_b = (await c2.post(f"/api/decision-rooms/{room_b['id']}/options", json=_option_payload())).json()["options"][0]
        bad = await c2.post(
            f"/api/decision-rooms/{room_b['id']}/options/{opt_b['id']}/media/attach", json={"file_ids": [fid]},
        )
        assert bad.status_code == 404  # cross-tenant file reference rejected


@pytest.mark.asyncio
async def test_pricing_snapshot_attach_detach_and_display_price_computation(ctx):
    ua, ub, snapshot_a, snapshot_b = ctx["ua"], ctx["ub"], ctx["snapshot_a"], ctx["snapshot_b"]
    async with await _client(ua) as c:
        room = await _create_room(c)
        rid = room["id"]
        opt = (await c.post(
            f"/api/decision-rooms/{rid}/options",
            json=_option_payload(manual_price_cents=39900, selected_price_source="manual"),
        )).json()["options"][0]
        assert opt["selected_display_price_cents"] == 39900  # manual wins while source == manual

        attached = await c.post(
            f"/api/decision-rooms/{rid}/options/{opt['id']}/pricing-snapshot/attach", json={"pricing_snapshot_id": snapshot_a["id"]},
        )
        assert attached.status_code == 200
        updated = next(o for o in attached.json()["options"] if o["id"] == opt["id"])
        assert updated["suggested_price_cents"] == 45000
        assert updated["selected_display_price_cents"] == 39900  # still manual-selected — snapshot never overwrites silently

        switched = await c.patch(f"/api/decision-rooms/{rid}/options/{opt['id']}", json={"selected_price_source": "snapshot"})
        updated2 = next(o for o in switched.json()["options"] if o["id"] == opt["id"])
        assert updated2["selected_display_price_cents"] == 45000  # now reflects the frozen snapshot value

        detached = await c.post(f"/api/decision-rooms/{rid}/options/{opt['id']}/pricing-snapshot/detach")
        updated3 = next(o for o in detached.json()["options"] if o["id"] == opt["id"])
        assert updated3["pricing_snapshot_id"] is None and updated3["suggested_price_cents"] is None
        assert updated3["selected_display_price_cents"] is None  # source still "snapshot", now no snapshot value — never invented

    _clear()
    async with await _client(ub) as c2:
        room_b = await _create_room(c2)
        opt_b = (await c2.post(f"/api/decision-rooms/{room_b['id']}/options", json=_option_payload())).json()["options"][0]
        cross = await c2.post(
            f"/api/decision-rooms/{room_b['id']}/options/{opt_b['id']}/pricing-snapshot/attach", json={"pricing_snapshot_id": snapshot_a["id"]},
        )
        assert cross.status_code == 404
        own_tenant_snapshot = await c2.post(
            f"/api/decision-rooms/{room_b['id']}/options/{opt_b['id']}/pricing-snapshot/attach", json={"pricing_snapshot_id": snapshot_b["id"]},
        )
        assert own_tenant_snapshot.status_code == 200


@pytest.mark.asyncio
async def test_readiness_report_and_minimum_active_options(ctx):
    ua, customer_a = ctx["ua"], ctx["customer_a"]
    async with await _client(ua) as c:
        room = await _create_room(c)
        rid = room["id"]
        report = (await c.get(f"/api/decision-rooms/{rid}/readiness")).json()
        assert report["ready"] is False
        assert "customer_required" in report["errors"]
        assert "commercial_or_intake_context_required" in report["errors"]
        assert "at_least_two_active_options_required" in report["errors"]

        await c.patch(f"/api/decision-rooms/{rid}", json={"customer_id": customer_a["id"], "quote_id": None})
        opt1 = (await c.post(f"/api/decision-rooms/{rid}/options", json=_option_payload(customer_label="Only one", manual_price_cents=1000))).json()["options"][0]
        report2 = (await c.get(f"/api/decision-rooms/{rid}/readiness")).json()
        assert "at_least_two_active_options_required" in report2["errors"]  # still only 1 active option

        opt2 = (await c.post(f"/api/decision-rooms/{rid}/options", json=_option_payload(customer_label="Second one", manual_price_cents=2000))).json()
        await c.patch(f"/api/decision-rooms/{rid}", json={"order_id": ctx["order_a"]["id"]})
        report3 = (await c.get(f"/api/decision-rooms/{rid}/readiness")).json()
        assert report3["ready"] is True


@pytest.mark.asyncio
async def test_option_label_and_price_required_for_readiness(ctx):
    ua, customer_a, order_a = ctx["ua"], ctx["customer_a"], ctx["order_a"]
    async with await _client(ua) as c:
        room = await _create_room(c, customer_id=customer_a["id"], order_id=order_a["id"])
        rid = room["id"]
        await c.post(f"/api/decision-rooms/{rid}/options", json={"customer_label": None, "internal_name": None})
        await c.post(f"/api/decision-rooms/{rid}/options", json=_option_payload(customer_label="Priced", price_display_mode="show_price"))
        report = (await c.get(f"/api/decision-rooms/{rid}/readiness")).json()
        errors_joined = " ".join(report["errors"])
        assert "label_required" in errors_joined
        assert "price_required" in errors_joined


@pytest.mark.asyncio
async def test_ready_transition_accepted_and_invalid_transition_rejected(ctx):
    ua, customer_a, order_a = ctx["ua"], ctx["customer_a"], ctx["order_a"]
    async with await _client(ua) as c:
        room = await _create_room(c, customer_id=customer_a["id"], order_id=order_a["id"])
        rid = room["id"]

        not_ready = await c.post(f"/api/decision-rooms/{rid}/transition", json={"target": "ready"})
        assert not_ready.status_code == 400  # readiness_failed — no options yet

        await c.post(f"/api/decision-rooms/{rid}/options", json=_option_payload(customer_label="A", manual_price_cents=1000))
        await c.post(f"/api/decision-rooms/{rid}/options", json=_option_payload(customer_label="B", manual_price_cents=2000))
        ready = await c.post(f"/api/decision-rooms/{rid}/transition", json={"target": "ready"})
        assert ready.status_code == 200 and ready.json()["status"] == "ready"

        # draft/ready cannot jump straight to "published" via the generic transition endpoint
        invalid = await c.post(f"/api/decision-rooms/{rid}/transition", json={"target": "published"})
        assert invalid.status_code == 400


@pytest.mark.asyncio
async def test_publish_creates_immutable_version_and_edit_bumps_current_version(ctx):
    ua, customer_a, order_a = ctx["ua"], ctx["customer_a"], ctx["order_a"]
    async with await _client(ua) as c:
        room = await _create_room(c, customer_id=customer_a["id"], order_id=order_a["id"], title="Original title")
        rid = room["id"]
        opt1 = (await c.post(f"/api/decision-rooms/{rid}/options", json=_option_payload(customer_label="A", manual_price_cents=1000))).json()["options"][0]
        await c.post(f"/api/decision-rooms/{rid}/options", json=_option_payload(customer_label="B", manual_price_cents=2000))
        await c.post(f"/api/decision-rooms/{rid}/transition", json={"target": "ready"})

        published = await c.post(f"/api/decision-rooms/{rid}/publish")
        assert published.status_code == 200
        body = published.json()
        assert body["status"] == "published" and body["current_version"] == 1 and body["published_version"] == 1

        v1 = (await c.get(f"/api/decision-rooms/{rid}/versions")).json()["items"]
        assert len(v1) == 1 and v1[0]["version_number"] == 1
        v1_detail = (await c.get(f"/api/decision-rooms/{rid}/versions/{v1[0]['id']}")).json()
        assert v1_detail["title"] == "Original title"

        # Edit after publication — bumps current_version without creating a new frozen version row
        await c.patch(f"/api/decision-rooms/{rid}/options/{opt1['id']}", json={"customer_label": "A renamed"})
        room_after_edit = (await c.get(f"/api/decision-rooms/{rid}")).json()
        assert room_after_edit["current_version"] == 2 and room_after_edit["published_version"] == 1
        versions_still_one = (await c.get(f"/api/decision-rooms/{rid}/versions")).json()["items"]
        assert len(versions_still_one) == 1  # no new frozen version was created by a plain edit

        # Publish again -> new frozen version; prior version remains byte-identical
        published2 = await c.post(f"/api/decision-rooms/{rid}/publish")
        assert published2.status_code == 200
        assert published2.json()["current_version"] == 2 and published2.json()["published_version"] == 2
        versions_now_two = (await c.get(f"/api/decision-rooms/{rid}/versions")).json()["items"]
        assert len(versions_now_two) == 2
        v1_reread = (await c.get(f"/api/decision-rooms/{rid}/versions/{v1[0]['id']}")).json()
        assert v1_reread["title"] == "Original title"
        opt_in_v1 = v1_reread["options_snapshot"][0]
        assert opt_in_v1["customer_label"] == "A"  # unchanged — the rename happened after v1 was frozen


@pytest.mark.asyncio
async def test_internal_preview_excludes_internal_fields(ctx):
    ua, customer_a, order_a = ctx["ua"], ctx["customer_a"], ctx["order_a"]
    async with await _client(ua) as c:
        room = await _create_room(
            c, customer_id=customer_a["id"], order_id=order_a["id"], internal_name="Internal codename ZZZ",
        )
        rid = room["id"]
        await c.post(f"/api/decision-rooms/{rid}/options", json=_option_payload(
            customer_label="Standard", internal_name="Internal Std", internal_notes="Cost is $12, margin 40%",
            manual_price_cents=5000, selected_price_source="manual",
        ))

        preview = await c.get(f"/api/decision-rooms/{rid}/preview")
        assert preview.status_code == 200
        body = preview.json()
        assert "internal_name" not in body and "created_by_user_id" not in body
        opt = body["options"][0]
        for forbidden in ("internal_notes", "internal_name", "created_by_user_id", "updated_by_user_id",
                           "pricing_snapshot_id", "suggested_price_cents", "manual_price_cents",
                           "selected_price_source", "proof_id", "quote_line_item_id", "order_item_id"):
            assert forbidden not in opt
        assert opt["customer_label"] == "Standard"
        assert opt["displayed_price_cents"] == 5000


@pytest.mark.asyncio
async def test_tenant_isolation(ctx):
    ua, ub = ctx["ua"], ctx["ub"]
    async with await _client(ua) as c:
        room = await _create_room(c)
        rid = room["id"]
    _clear()
    async with await _client(ub) as c2:
        assert (await c2.get(f"/api/decision-rooms/{rid}")).status_code == 404
        assert (await c2.patch(f"/api/decision-rooms/{rid}", json={"title": "hacked"})).status_code == 404
        assert (await c2.post(f"/api/decision-rooms/{rid}/options", json=_option_payload())).status_code == 404
        assert (await c2.get(f"/api/decision-rooms/{rid}/preview")).status_code == 404


@pytest.mark.asyncio
async def test_permission_enforcement(ctx):
    ua, staff_a, customer_role_a = ctx["ua"], ctx["staff_a"], ctx["customer_role_a"]
    async with await _client(ua) as c:
        room = await _create_room(c)
        rid = room["id"]
    _clear()
    async with await _client(staff_a) as cs:
        ok = await cs.get(f"/api/decision-rooms/{rid}")
        assert ok.status_code == 200  # staff has decision_room:read/write
        write_ok = await cs.post(f"/api/decision-rooms/{rid}/options", json=_option_payload())
        assert write_ok.status_code == 201
        publish_denied = await cs.post(f"/api/decision-rooms/{rid}/publish")
        assert publish_denied.status_code == 403  # publish requires decision_room:publish — staff lacks it
        archive_denied = await cs.post(f"/api/decision-rooms/{rid}/archive")
        assert archive_denied.status_code == 403  # archive requires decision_room:archive
        transition_archive_denied = await cs.post(f"/api/decision-rooms/{rid}/transition", json={"target": "archived"})
        assert transition_archive_denied.status_code == 403  # generic transition also gates "archived" on the archive perm
    _clear()
    async with await _client(customer_role_a) as cc:
        denied = await cc.get(f"/api/decision-rooms/{rid}")
        assert denied.status_code == 403  # a non-staff role can never satisfy a staff Perm check


@pytest.mark.asyncio
async def test_audit_events_emitted_without_bulky_content(ctx):
    ua, ta, customer_a, order_a = ctx["ua"], ctx["ta"], ctx["customer_a"], ctx["order_a"]
    async with await _client(ua) as c:
        room = await _create_room(c, customer_id=customer_a["id"], order_id=order_a["id"])
        rid = room["id"]
        opt = (await c.post(f"/api/decision-rooms/{rid}/options", json=_option_payload(customer_label="A", manual_price_cents=1000, customer_safe_description="x" * 500))).json()["options"][0]
        await c.post(f"/api/decision-rooms/{rid}/options", json=_option_payload(customer_label="B", manual_price_cents=2000))
        await c.post(f"/api/decision-rooms/{rid}/transition", json={"target": "ready"})
        await c.post(f"/api/decision-rooms/{rid}/publish")
        await c.post(f"/api/decision-rooms/{rid}/archive")

    events = [e async for e in db.audit_events.find({"tenant_id": ta, "entity_type": "decision_room", "entity_id": rid}, {"_id": 0})]
    actions = {e["action"] for e in events}
    assert {
        "decision_room.created", "decision_room.option_added", "decision_room.ready",
        "decision_room.published_version_created", "decision_room.archived",
    } <= actions
    for e in events:
        diff_str = str(e.get("diff") or {})
        assert "options_snapshot" not in diff_str
        assert ("x" * 500) not in diff_str  # bulky customer-safe description never dumped into audit diff


@pytest.mark.asyncio
async def test_no_quote_order_orderitem_mutation_and_no_pricing_recalculation(ctx):
    ua, quote_a, order_a, order_item_a, snapshot_a = ctx["ua"], ctx["quote_a"], ctx["order_a"], ctx["order_item_a"], ctx["snapshot_a"]
    before_quote = await db.quotes.find_one({"id": quote_a["id"]}, {"_id": 0})
    before_order = await db.orders.find_one({"id": order_a["id"]}, {"_id": 0})
    before_item = await db.order_items.find_one({"id": order_item_a["id"]}, {"_id": 0})
    before_snapshot = await db.pricing_snapshot_records.find_one({"id": snapshot_a["id"]}, {"_id": 0})

    async with await _client(ua) as c:
        room = await _create_room(c, quote_id=quote_a["id"], order_id=order_a["id"], order_item_id=order_item_a["id"])
        rid = room["id"]
        opt = (await c.post(f"/api/decision-rooms/{rid}/options", json=_option_payload(order_item_id=order_item_a["id"], quote_line_item_id=ctx["quote_line_item_a"]["id"]))).json()["options"][0]
        await c.post(f"/api/decision-rooms/{rid}/options/{opt['id']}/pricing-snapshot/attach", json={"pricing_snapshot_id": snapshot_a["id"]})

    after_quote = await db.quotes.find_one({"id": quote_a["id"]}, {"_id": 0})
    after_order = await db.orders.find_one({"id": order_a["id"]}, {"_id": 0})
    after_item = await db.order_items.find_one({"id": order_item_a["id"]}, {"_id": 0})
    after_snapshot = await db.pricing_snapshot_records.find_one({"id": snapshot_a["id"]}, {"_id": 0})
    assert before_quote == after_quote
    assert before_order == after_order
    assert before_item == after_item
    assert before_snapshot == after_snapshot  # the immutable pricing snapshot itself was never mutated


@pytest.mark.asyncio
async def test_room_locked_when_archived_and_restorable(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        room = await _create_room(c)
        rid = room["id"]
        await c.post(f"/api/decision-rooms/{rid}/archive")
        locked = await c.post(f"/api/decision-rooms/{rid}/options", json=_option_payload())
        assert locked.status_code == 400
        locked_update = await c.patch(f"/api/decision-rooms/{rid}", json={"title": "new"})
        assert locked_update.status_code == 400

        restored = await c.post(f"/api/decision-rooms/{rid}/restore")
        assert restored.status_code == 200 and restored.json()["status"] == "draft"
        now_editable = await c.post(f"/api/decision-rooms/{rid}/options", json=_option_payload())
        assert now_editable.status_code == 201


@pytest.mark.asyncio
async def test_no_public_or_unauthenticated_customer_access(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        room = await _create_room(c)
        rid = room["id"]
    _clear()
    # No bearer token at all — real, un-overridden auth dependency must reject.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anon:
        unauthenticated = await anon.get(f"/api/decision-rooms/{rid}")
        assert unauthenticated.status_code in (401, 403)
        no_public_route = await anon.get(f"/api/p/decision-rooms/{rid}")
        assert no_public_route.status_code == 404  # no public/customer route registered anywhere
        no_portal_route = await anon.get(f"/api/portal/decision-rooms/{rid}")
        assert no_portal_route.status_code == 404
