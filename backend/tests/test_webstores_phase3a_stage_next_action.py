"""Webstores Phase 3a: one stage, one next action, idempotent tasks, one history."""
from __future__ import annotations

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
        assert (await client.get(f"/api/webstores/{store['id']}/next-action")).json()["next_action"]["key"] == "owner_update_questionnaire"
        assert await _open_tasks(ctx["tenant_id"], store["id"]) == []
    async with _portal(token) as portal:
        rev2 = (await portal.post(f"/api/portal/webstores/{store['id']}/questionnaire", json={"answers": complete_answers("event", event_location="Gym")})).json()
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


async def test_old_records_derive_stage_and_retired_statuses_are_refused(ctx):
    store_id = f"legacy-{ctx['suffix']}"
    await db.webstores.insert_one({"id": store_id, "tenant_id": ctx["tenant_id"], "owner_id": "o", "name": "Old Store", "slug": f"old-{ctx['suffix']}",
                                   "public_slug": f"old-{ctx['suffix']}", "store_type": "general", "status": "store_packet_generated"})
    async with await _staff(ctx["user"]) as client:
        view = (await client.get(f"/api/webstores/{store_id}/next-action")).json()
    assert view["stage"]["key"] == "owner_review"
    assert "stage" not in (await db.webstores.find_one({"id": store_id}, {"_id": 0}))  # derived on read, not migrated
    with pytest.raises(WebstoreError):
        await apply_store_status(tenant_id=ctx["tenant_id"], webstore_id=store_id, status="mockups_generated", source="test")
    async with await _staff(ctx["outsider"]) as other:
        assert (await other.get(f"/api/webstores/{store_id}/next-action")).status_code == 404
