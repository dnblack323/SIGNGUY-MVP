"""Webstores Phase 3c: one shop <-> owner message thread per Webstore."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db, ensure_indexes
from app.deps import get_current_user
from server import app


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
    tenant_id = f"t-ws-p3c-{suffix}"
    other_tenant = f"t-ws-p3c-other-{suffix}"
    user = {"id": f"user-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "name": "Sam Staff", "role": "owner", "is_active": True}
    outsider = {"id": f"out-{suffix}", "tenant_id": other_tenant, "email": f"out-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([{"id": tenant_id, "slug": f"p3c-{suffix}", "name": f"Print Shop {suffix}"}, {"id": other_tenant, "slug": f"p3c-o-{suffix}", "name": "Other"}])
    await db.users.insert_many([user, outsider])
    yield {"suffix": suffix, "tenant_id": tenant_id, "user": user, "outsider": outsider}
    app.dependency_overrides.pop(get_current_user, None)


async def _store_with_owner_token(ctx) -> tuple[dict, str]:
    async with await _staff(ctx["user"]) as client:
        resp = await client.post("/api/webstores/requests", json={
            "new_customer": {"name": f"Club {ctx['suffix']}", "email": f"club-{ctx['suffix']}@example.com"},
            "store_type": "event", "store_name": f"Club Store {ctx['suffix']}",
        })
        store = resp.json()["webstore"]
        sent = (await client.post(f"/api/webstores/{store['id']}/information-packet/send", json={})).json()
    raw = sent["questionnaire_link"].split("t=", 1)[1]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as public:
        token = (await public.post("/api/portal/webstores/invitations/accept", json={"token": raw})).json()["token"]
    return store, token


async def test_shop_and_owner_share_one_thread_without_email(ctx):
    store, token = await _store_with_owner_token(ctx)
    emails_before = await db.email_logs.count_documents({"tenant_id": ctx["tenant_id"]})

    async with _portal(token) as portal:
        assert (await portal.get(f"/api/portal/webstores/{store['id']}/messages")).json()["items"] == []
        first = await portal.post(f"/api/portal/webstores/{store['id']}/messages", json={"body": "Can we add a hoodie?"})
        assert first.status_code == 201, first.text
    async with await _staff(ctx["user"]) as client:
        staff_view = (await client.get(f"/api/webstores/{store['id']}/messages")).json()["items"]
        assert [(m["from"], m["body"]) for m in staff_view] == [("owner", "Can we add a hoodie?")]
        reply = await client.post(f"/api/webstores/{store['id']}/messages", json={"body": "Yes - adding it to the draft."})
        assert reply.status_code == 201
        feed = {item["action"] for item in (await client.get(f"/api/webstores/{store['id']}/activity")).json()["items"]}
    assert {"webstore.message_received", "webstore.message_sent"} <= feed
    async with _portal(token) as portal:
        owner_view = (await portal.get(f"/api/portal/webstores/{store['id']}/messages")).json()["items"]
    # Owners see the shop's name, never individual staff accounts.
    assert [(m["from"], m["sender_name"]) for m in owner_view] == [("owner", "Store owner"), ("shop", f"Print Shop {ctx['suffix']}")]
    assert "staff-" not in str(owner_view)

    threads = [t async for t in db.message_threads.find({"tenant_id": ctx["tenant_id"], "webstore_id": store["id"]}, {"_id": 0})]
    assert len(threads) == 1 and threads[0]["thread_type"] == "webstore_discussion"
    notice = await db.notifications.find_one({"tenant_id": ctx["tenant_id"], "kind": "webstore.message_received"}, {"_id": 0})
    assert notice and notice["link"] == f"/webstores/{store['id']}"
    assert await db.email_logs.count_documents({"tenant_id": ctx["tenant_id"]}) == emails_before  # in-app only, no email


async def test_messages_are_scoped_to_the_tenant_and_validated(ctx):
    store, token = await _store_with_owner_token(ctx)
    async with await _staff(ctx["outsider"]) as other:
        assert (await other.get(f"/api/webstores/{store['id']}/messages")).status_code == 404
        assert (await other.post(f"/api/webstores/{store['id']}/messages", json={"body": "hi"})).status_code == 404
    async with await _staff(ctx["user"]) as client:
        assert (await client.post(f"/api/webstores/{store['id']}/messages", json={"body": ""})).status_code == 422
        assert (await client.post(f"/api/webstores/{store['id']}/messages", json={"body": "   "})).status_code == 400
    async with _portal(token) as portal:
        assert (await portal.get(f"/api/portal/webstores/not-{store['id']}/messages")).status_code in {403, 404}
