"""Webstores Phase 3a: one stage, one next action, idempotent tasks, one history."""
from __future__ import annotations

import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db, ensure_indexes
from app.deps import get_current_user
from app.services.webstore_context import WebstoreError
from app.services.webstore_next_action import TASK_TYPE
from app.services.webstore_stage import apply_store_status
from server import app
from tests.webstore_questionnaire_answers import complete_answers


def _override(user: dict):
    async def _get():
        return {**user}

    return _get


async def _staff(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _portal(token: str) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"})


@pytest.fixture
async def ctx():
    await ensure_indexes()
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-ws-p3a-{suffix}"
    other_tenant = f"t-ws-p3a-other-{suffix}"
    user = {"id": f"user-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "role": "owner", "is_active": True}
    teammate = {"id": f"mate-{suffix}", "tenant_id": tenant_id, "email": f"mate-{suffix}@example.com", "role": "admin", "is_active": True}
    outsider = {"id": f"out-{suffix}", "tenant_id": other_tenant, "email": f"out-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([{"id": tenant_id, "slug": f"p3a-{suffix}", "name": f"Shop {suffix}"}, {"id": other_tenant, "slug": f"p3a-o-{suffix}", "name": "Other"}])
    await db.users.insert_many([user, teammate, outsider])
    yield {"suffix": suffix, "tenant_id": tenant_id, "user": user, "teammate": teammate, "outsider": outsider}
    app.dependency_overrides.pop(get_current_user, None)


async def _request(client: AsyncClient, suffix: str, store_type: str = "event") -> dict:
    resp = await client.post("/api/webstores/requests", json={
        "new_customer": {"name": f"Club {suffix}", "email": f"club-{suffix}@example.com"},
        "store_type": store_type, "store_name": f"Club Store {suffix}",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["webstore"]


async def _open_tasks(tenant_id: str, webstore_id: str) -> list[dict]:
    return [t async for t in db.tasks.find(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "task_type": TASK_TYPE, "status": {"$nin": ["completed", "canceled"]}}, {"_id": 0}
    )]


async def test_one_next_action_drives_one_task_and_reads_never_change_the_store(ctx):
    async with await _staff(ctx["user"]) as client:
        store = await _request(client, ctx["suffix"])
        assert store["stage"] == "draft"
        first = (await client.get(f"/api/webstores/{store['id']}/next-action")).json()
        assert first["stage"]["key"] == "draft" and first["stage"]["staff_label"] == "Request received"
        assert first["next_action"]["key"] == "send_information_packet" and first["next_action"]["actor"] == "shop"
        tasks = await _open_tasks(ctx["tenant_id"], store["id"])
        assert [t["title"] for t in tasks] == [f"Club Store {ctx['suffix']}: Send the information packet"]

        before = await db.webstores.find_one({"id": store["id"]}, {"_id": 0, "updated_at": 1, "stage": 1})
        for path in ("next-action", "setup-progress", ""):
            assert (await client.get(f"/api/webstores/{store['id']}/{path}".rstrip("/"))).status_code == 200
        listed = (await client.get("/api/webstores")).json()["items"]
        assert [i["next_action"]["key"] for i in listed if i["id"] == store["id"]] == ["send_information_packet"]
        after = await db.webstores.find_one({"id": store["id"]}, {"_id": 0, "updated_at": 1, "stage": 1})
        assert after == before  # reading never writes
        # A retried save does not duplicate the task.
        await client.patch(f"/api/webstores/{store['id']}", json={"description": "Spring fair merch"})
        await client.patch(f"/api/webstores/{store['id']}", json={"description": "Spring fair merch"})
        assert len(await _open_tasks(ctx["tenant_id"], store["id"])) == 1

        sent = (await client.post(f"/api/webstores/{store['id']}/information-packet/send", json={})).json()
        staff_after_send = (await client.get(f"/api/webstores/{store['id']}/next-action")).json()
    assert staff_after_send["stage"]["key"] == "intake_pending"
    assert staff_after_send["next_action"] == {**staff_after_send["next_action"], "key": "owner_complete_questionnaire", "actor": "owner"}
    assert await _open_tasks(ctx["tenant_id"], store["id"]) == []  # shop task closed automatically; owner steps make no task
    closed = await db.tasks.find_one({"tenant_id": ctx["tenant_id"], "webstore_id": store["id"], "task_type": TASK_TYPE}, {"_id": 0})
    assert closed["status"] == "completed"
    events = [e async for e in db.webstore_lifecycle_events.find({"webstore_id": store["id"]}, {"_id": 0})]
    assert [(e["from_state"], e["to_state"], e["metadata"]["source"]) for e in events if e["to_status"] == "questionnaire_sent"] == [
        ("draft", "intake_pending", "information_packet_sent")]

    raw = sent["questionnaire_link"].split("t=", 1)[1]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as public:
        token = (await public.post("/api/portal/webstores/invitations/accept", json={"token": raw})).json()["token"]
    async with _portal(token) as portal:
        owner = (await portal.get(f"/api/portal/webstores/{store['id']}/next-action")).json()
        assert owner["stage"] == {"key": "intake_pending", "label": "Complete your questionnaire"}
        assert owner["next_action"] == {"key": "owner_complete_questionnaire", "for_you": True, "text": "Complete your store questionnaire."}
        submitted = (await portal.post(f"/api/portal/webstores/{store['id']}/questionnaire", json={"answers": complete_answers("event")})).json()
        detail = (await portal.get(f"/api/portal/webstores/{store['id']}")).json()
    assert detail["journey"]["next_action"]["for_you"] is False and "blockers" not in str(detail["journey"])

    async with await _staff(ctx["user"]) as client:
        review = (await client.get(f"/api/webstores/{store['id']}/next-action")).json()
        assert review["next_action"]["key"] == "review_questionnaire"
        assert [t["idempotency_key"] for t in await _open_tasks(ctx["tenant_id"], store["id"])] == [f"webstore:{store['id']}:next:review_questionnaire:1"]
        await client.post(f"/api/webstores/{store['id']}/questionnaire/{submitted['id']}/return", json={"reason": "Fix the venue"})
        returned = (await client.get(f"/api/webstores/{store['id']}/next-action")).json()
        assert returned["next_action"]["key"] == "owner_update_questionnaire"
        assert returned["stage"]["key"] == "intake_pending"  # stage and next action agree
        assert await _open_tasks(ctx["tenant_id"], store["id"]) == []
    async with _portal(token) as portal:
        rev2 = (await portal.post(f"/api/portal/webstores/{store['id']}/questionnaire", json={"answers": complete_answers("event", event_location="Gym")})).json()
    assert (await db.webstores.find_one({"id": store["id"]}, {"_id": 0, "stage": 1}))["stage"] == "setup_in_progress"
    async with await _staff(ctx["user"]) as client:
        assert [t["idempotency_key"] for t in await _open_tasks(ctx["tenant_id"], store["id"])] == [f"webstore:{store['id']}:next:review_questionnaire:2"]
        await client.post(f"/api/webstores/{store['id']}/questionnaire/{rev2['id']}/approve")
        after_apply = (await client.get(f"/api/webstores/{store['id']}/next-action")).json()
        feed = (await client.get(f"/api/webstores/{store['id']}/activity")).json()["items"]
    # After review the launch gates decide; staff see blockers, the owner does not.
    assert after_apply["next_action"]["actor"] == "shop" and after_apply["next_action"]["key"] not in {"review_questionnaire", "send_information_packet"}
    assert after_apply["next_action"]["blockers"]
    actions = {item["action"] for item in feed}
    assert {"webstore.questionnaire_submitted", "webstore.information_packet_sent"} <= actions
    assert await db.webstore_activity_events.count_documents({"webstore_id": store["id"]}) == 0  # one history store


async def test_assignee_owns_the_next_action_task(ctx):
    async with await _staff(ctx["user"]) as client:
        store = await _request(client, ctx["suffix"])
        bad = await client.patch(f"/api/webstores/{store['id']}", json={"assignee_user_id": ctx["outsider"]["id"]})
        assert bad.status_code == 400
        ok = await client.patch(f"/api/webstores/{store['id']}", json={"assignee_user_id": ctx["teammate"]["id"]})
        assert ok.status_code == 200, ok.text
        detail = (await client.get(f"/api/webstores/{store['id']}")).json()
    assert detail["assignee_user_id"] == ctx["teammate"]["id"]
    # The open task created before assignment keeps its key; a new step is assigned on creation.
    async with await _staff(ctx["user"]) as client:
        await client.post(f"/api/webstores/{store['id']}/information-packet/send", json={})
        await apply_store_status(tenant_id=ctx["tenant_id"], webstore_id=store["id"], status="questionnaire_sent", source="test", validate=False)
    await db.webstores.update_one({"id": store["id"]}, {"$set": {"information_packet.sent_count": 0}})
    from app.services.webstore_next_action import sync_next_action_side_effects

    await sync_next_action_side_effects(ctx["tenant_id"], store["id"])
    tasks = await _open_tasks(ctx["tenant_id"], store["id"])
    assert len(tasks) == 1 and tasks[0]["assigned_user_id"] == ctx["teammate"]["id"]
    assert tasks[0]["status"] == "in_progress" and tasks[0].get("completed_at") is None

    # An assignee who left the shop never blocks the next task.
    await db.users.update_one({"id": ctx["teammate"]["id"]}, {"$set": {"is_active": False}})
    await db.webstores.update_one({"id": store["id"]}, {"$set": {"information_packet.sent_count": 1}})
    await sync_next_action_side_effects(ctx["tenant_id"], store["id"])
    assert await _open_tasks(ctx["tenant_id"], store["id"]) == []  # owner's turn now
    await db.webstores.update_one({"id": store["id"]}, {"$set": {"information_packet.sent_count": 0}})
    await sync_next_action_side_effects(ctx["tenant_id"], store["id"])
    tasks = await _open_tasks(ctx["tenant_id"], store["id"])
    assert len(tasks) == 1 and tasks[0]["assigned_user_id"] is None


async def test_concurrent_syncs_keep_exactly_one_open_task(ctx):
    from app.services.webstore_next_action import sync_next_action_side_effects

    async with await _staff(ctx["user"]) as client:
        store = await _request(client, ctx["suffix"])
    await db.tasks.delete_many({"tenant_id": ctx["tenant_id"], "webstore_id": store["id"]})
    await asyncio.gather(*(sync_next_action_side_effects(ctx["tenant_id"], store["id"]) for _ in range(6)))
    assert len(await _open_tasks(ctx["tenant_id"], store["id"])) == 1
    lock = await db.webstore_next_action_locks.find_one({"_id": f"{ctx['tenant_id']}:{store['id']}"})
    assert lock["until"] == ""  # released


async def test_noop_lifecycle_request_reports_no_event(ctx):
    async with await _staff(ctx["user"]) as client:
        store = await _request(client, ctx["suffix"])
        before = await db.webstore_lifecycle_events.count_documents({"webstore_id": store["id"]})
        resp = await client.post(f"/api/webstores/{store['id']}/lifecycle", json={"state": "draft"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["event"] is None
    assert await db.webstore_lifecycle_events.count_documents({"webstore_id": store["id"]}) == before


async def test_history_written_before_phase3_keeps_its_actor_type(ctx):
    from app.services.webstore_shared_audit import webstore_activity_feed

    store_id = f"hist-{ctx['suffix']}"
    await db.activity_events.insert_many([
        {"id": f"a1-{ctx['suffix']}", "tenant_id": ctx["tenant_id"], "module": "webstores", "action": "webstore.packet_approved", "actor_user_id": "portal-owner-1",
         "actor_email": "owner@example.com", "metadata": {"webstore_id": store_id}, "created_at": "2026-10-01T00:00:00+00:00"},
        {"id": f"a2-{ctx['suffix']}", "tenant_id": ctx["tenant_id"], "module": "webstores", "action": "webstore.refund_failed", "actor_user_id": "system",
         "actor_email": "system", "metadata": {"webstore_id": store_id}, "created_at": "2026-10-02T00:00:00+00:00"},
    ])
    await db.webstore_activity_events.insert_one({"id": f"l1-{ctx['suffix']}", "tenant_id": ctx["tenant_id"], "webstore_id": store_id,
                                                  "actor_type": "portal_webstore_owner", "actor_id": "portal-owner-1", "action": "webstore.packet_approved"})
    feed = {item["action"]: item["actor_type"] for item in await webstore_activity_feed(ctx["tenant_id"], store_id)}
    assert feed == {"webstore.packet_approved": "portal_webstore_owner", "webstore.refund_failed": "system"}


async def test_old_records_derive_stage_and_retired_statuses_are_refused(ctx):
    store_id = f"legacy-{ctx['suffix']}"
    await db.webstores.insert_one({"id": store_id, "tenant_id": ctx["tenant_id"], "owner_id": "o", "name": "Old Store", "slug": f"old-{ctx['suffix']}",
                                   "public_slug": f"old-{ctx['suffix']}", "store_type": "general", "status": "store_packet_generated"})
    async with await _staff(ctx["user"]) as client:
        view = (await client.get(f"/api/webstores/{store_id}/next-action")).json()
    assert view["stage"]["key"] == "owner_review"
    assert view["next_action"]["key"] != "send_information_packet"  # Phase 2 journey steps end before owner review
    raw = await db.webstores.find_one({"id": store_id}, {"_id": 0})
    assert "stage" not in raw and "updated_at" not in raw  # derived on read, not migrated
    async with await _staff(ctx["user"]) as client:
        assert (await client.get("/api/webstores")).status_code == 200
        assert (await client.get(f"/api/webstores/{store_id}")).status_code == 200
    assert await db.webstores.find_one({"id": store_id}, {"_id": 0}) == raw  # no slug allocated, nothing written
    # A status written outside the stage service (old data) still yields the matching stage,
    # and the list ignores a snapshot taken in another stage.
    await db.webstores.update_one({"id": store_id}, {"$set": {"stage": "draft", "status": "live", "next_action_snapshot": {
        "key": "send_information_packet", "actor": "shop", "staff_text": "Send the information packet", "tab": "setup", "stage": "draft"}}})
    async with await _staff(ctx["user"]) as client:
        assert (await client.get(f"/api/webstores/{store_id}/next-action")).json()["stage"]["key"] == "live"
        listed = [i for i in (await client.get("/api/webstores")).json()["items"] if i["id"] == store_id]
    assert listed[0]["next_action"]["key"] == "monitor_orders"
    with pytest.raises(WebstoreError):
        await apply_store_status(tenant_id=ctx["tenant_id"], webstore_id=store_id, status="mockups_generated", source="test")
    async with await _staff(ctx["outsider"]) as other:
        assert (await other.get(f"/api/webstores/{store_id}/next-action")).status_code == 404


async def test_tasks_restore_reassign_and_link_through_the_task_service(ctx):
    from app.services.task_service import get_task
    from app.services.webstore_next_action import sync_next_action_side_effects

    async with await _staff(ctx["user"]) as client:
        store = await _request(client, ctx["suffix"])
        task = (await _open_tasks(ctx["tenant_id"], store["id"]))[0]
        assert (await get_task(tenant_id=ctx["tenant_id"], task_id=task["id"]))["linked_record_label"].startswith("webstore ")
        # Archived by hand while still pending: the next sync restores it.
        await db.tasks.update_one({"id": task["id"]}, {"$set": {"archived_at": "2026-10-20T00:00:00+00:00"}})
        await sync_next_action_side_effects(ctx["tenant_id"], store["id"])
        assert (await db.tasks.find_one({"id": task["id"]}, {"_id": 0}))["archived_at"] is None
        # A new assignee is applied through assign_task (history recorded).
        assert (await client.patch(f"/api/webstores/{store['id']}", json={"assignee_user_id": ctx["teammate"]["id"]})).status_code == 200
    moved = await db.tasks.find_one({"id": task["id"]}, {"_id": 0})
    assert moved["assigned_user_id"] == ctx["teammate"]["id"] and moved["assignment_history"]


async def test_closed_stage_statuses_and_external_gate_changes(ctx):
    from app.services.webstore_next_action import compute_next_action

    base = {"tenant_id": ctx["tenant_id"], "id": f"closed-{ctx['suffix']}", "owner_id": "o", "name": "Closed", "slug": f"closed-{ctx['suffix']}",
            "public_slug": f"closed-{ctx['suffix']}", "store_type": "general", "information_packet": {"sent_count": 1}}
    await db.webstores.insert_one({**base, "status": "relaunch_ready"})
    assert (await compute_next_action({**base, "status": "completed"}))["actor"] == "none"  # no fulfillment task
    assert (await compute_next_action({**base, "status": "closed"}))["key"] == "review_closed_orders"
    assert (await compute_next_action({**base, "status": "relaunch_ready"}))["key"] != "review_closed_orders"

    async with await _staff(ctx["user"]) as client:
        store = await _request(client, ctx["suffix"])
        await db.webstores.update_one({"id": store["id"]}, {"$set": {"information_packet.sent_count": 1, "status": "questionnaire_submitted"}})
        await db.webstore_questionnaire_submissions.insert_one({"id": f"s-{ctx['suffix']}", "tenant_id": ctx["tenant_id"], "webstore_id": store["id"], "status": "reviewed", "revision": 1})
        await client.patch(f"/api/webstores/{store['id']}", json={"description": "sync"})  # snapshot taken without the entitlement
        before = [i for i in (await client.get("/api/webstores")).json()["items"] if i["id"] == store["id"]][0]
        assert before["next_action"]["key"] == "entitlement"
        # The subscription projection enables the feature outside any Webstore route.
        await db.feature_entitlements.insert_one({"tenant_id": ctx["tenant_id"], "feature_key": "webstores", "enabled": True})
        after = [i for i in (await client.get("/api/webstores")).json()["items"] if i["id"] == store["id"]][0]
    assert after["next_action"]["key"] != "entitlement"
    assert after["setup_state"] != "not_started"  # computed, not the stale stored value


async def test_status_write_never_overwrites_a_concurrent_change(ctx, monkeypatch):
    import app.services.webstore_stage as stage_mod

    async with await _staff(ctx["user"]) as client:
        store = await _request(client, ctx["suffix"])
    real_db = stage_mod.db
    calls = {"n": 0}

    class RacingStores:
        def __getattr__(self, name):
            return getattr(real_db.webstores, name)

        async def find_one(self, *args, **kwargs):
            doc = await real_db.webstores.find_one(*args, **kwargs)
            calls["n"] += 1
            if calls["n"] == 1:  # another request moves the store right after our read
                await real_db.webstores.update_one({"id": store["id"]}, {"$set": {"status": "questionnaire_sent"}})
            return doc

    class RacingDb:
        webstores = RacingStores()

        def __getattr__(self, name):
            return getattr(real_db, name)

    monkeypatch.setattr(stage_mod, "db", RacingDb())
    result = await apply_store_status(tenant_id=ctx["tenant_id"], webstore_id=store["id"], status="questionnaire_sent",
                                      source="test", validate=False, only_from={"draft"})
    monkeypatch.undo()
    assert calls["n"] >= 2  # the stale decision was retried
    assert result["status"] == "questionnaire_sent"
    # The retry saw the newer status, so no second transition was recorded from the stale "draft".
    events = [e async for e in db.webstore_lifecycle_events.find({"webstore_id": store["id"], "metadata.source": "test"}, {"_id": 0})]
    assert events == []


async def test_terminal_owner_view_rename_and_task_source(ctx):
    from app.services.task_service import update_task
    from app.services.webstore_next_action import owner_view

    view = owner_view({"status": "archived"}, {"key": "none", "actor": "none", "owner_text": "This store is archived."})
    assert view["next_action"]["key"] == "none" and view["next_action"]["for_you"] is False

    async with await _staff(ctx["user"]) as client:
        store = await _request(client, ctx["suffix"])
        task = (await _open_tasks(ctx["tenant_id"], store["id"]))[0]
        await client.patch(f"/api/webstores/{store['id']}", json={"name": "Renamed Store"})
    assert (await db.tasks.find_one({"id": task["id"]}, {"_id": 0}))["title"].startswith("Renamed Store:")

    other = await _request(await _staff(ctx["user"]), f"{ctx['suffix']}b")
    moved = await update_task(tenant_id=ctx["tenant_id"], task_id=task["id"], actor_user_id="u", actor_email="e",
                              updates={"source_type": "webstore", "source_id": other["id"]})
    assert moved["webstore_id"] == other["id"]
