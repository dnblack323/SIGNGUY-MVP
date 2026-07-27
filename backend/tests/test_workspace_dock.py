from __future__ import annotations

import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from server import app
from app.deps import get_current_user


def _override(user: dict):
    async def _dep():
        return user
    return _dep


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


async def _seed_order(db, tenant_id: str, suffix: str, **extra) -> dict:
    doc = {
        "id": f"order-{suffix}",
        "tenant_id": tenant_id,
        "number": "000127",
        "job_name": "Fayette EMS",
        "status": "active",
        "total_cents": 25000,
        **extra,
    }
    await db.orders.insert_one(doc.copy())
    return doc


def _open_order_payload(order_id: str, pathname: str | None = None) -> dict:
    return {
        "workspace_type": "order",
        "record_id": order_id,
        "pathname": pathname or f"/orders/{order_id}",
        "query_params": {"tab": "items"},
        "view_state": {"selected_tab": "items"},
        "scroll_position": 120,
    }


@pytest.mark.asyncio
async def test_workspace_dock_requires_authentication():
    _clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/workspaces")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_open_workspace_persists_and_duplicate_open_updates_existing(seeded_users, clean_db):
    user = seeded_users["user_a"]
    order = await _seed_order(clean_db, user["tenant_id"], uuid.uuid4().hex[:8])

    async with await _client_as(user) as client:
        response = await client.post("/api/workspaces/open", json=_open_order_payload(order["id"]))
        assert response.status_code == 201, response.text
        state = response.json()
        assert len(state["open_workspaces"]) == 1
        item = state["open_workspaces"][0]
        assert item["workspace_type"] == "order"
        assert item["record_id"] == order["id"]
        assert item["label"] == "O-000127 - Fayette EMS"
        assert item["active"] is True

        response = await client.post("/api/workspaces/open", json={**_open_order_payload(order["id"]), "query_params": {"tab": "summary"}, "scroll_position": 240})
        assert response.status_code == 201, response.text
        state = response.json()
        assert len(state["open_workspaces"]) == 1
        assert state["open_workspaces"][0]["id"] == item["id"]
        assert state["open_workspaces"][0]["query_params"] == {"tab": "summary"}
        assert state["open_workspaces"][0]["scroll_position"] == 240


@pytest.mark.asyncio
async def test_user_and_tenant_ownership_are_enforced(seeded_users, clean_db):
    user_a = seeded_users["user_a"]
    user_b = seeded_users["user_b"]
    same_tenant_other_user = {
        "id": f"user-peer-{uuid.uuid4().hex[:8]}",
        "tenant_id": user_a["tenant_id"],
        "email": "peer@example.com",
        "role": "owner",
        "is_active": True,
    }
    await clean_db.users.insert_one(same_tenant_other_user)
    order = await _seed_order(clean_db, user_a["tenant_id"], uuid.uuid4().hex[:8])

    async with await _client_as(user_a) as client:
        created = await client.post("/api/workspaces/open", json=_open_order_payload(order["id"]))
        assert created.status_code == 201
        workspace_id = created.json()["open_workspaces"][0]["id"]

    async with await _client_as(same_tenant_other_user) as client:
        listing = await client.get("/api/workspaces")
        assert listing.status_code == 200
        assert listing.json()["open_workspaces"] == []
        response = await client.post(f"/api/workspaces/{workspace_id}/close")
        assert response.status_code == 404

    async with await _client_as(user_b) as client:
        response = await client.post("/api/workspaces/open", json=_open_order_payload(order["id"]))
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_workspace_limit_pin_reorder_close_recent_and_reopen(seeded_users, clean_db):
    user = seeded_users["user_a"]
    order_ids = []
    for idx in range(9):
        order = await _seed_order(clean_db, user["tenant_id"], f"{uuid.uuid4().hex[:6]}-{idx}", number=f"{idx:06d}", job_name=f"Job {idx}")
        order_ids.append(order["id"])

    async with await _client_as(user) as client:
        for order_id in order_ids[:8]:
            response = await client.post("/api/workspaces/open", json=_open_order_payload(order_id))
            assert response.status_code == 201, response.text
        ninth = await client.post("/api/workspaces/open", json=_open_order_payload(order_ids[8]))
        assert ninth.status_code == 409
        assert len(ninth.json()["detail"]["open_workspaces"]) == 8

        state = (await client.get("/api/workspaces")).json()
        first, second = state["open_workspaces"][0], state["open_workspaces"][1]
        pinned = await client.post(f"/api/workspaces/{second['id']}/pin")
        assert pinned.status_code == 200
        assert next(item for item in pinned.json()["open_workspaces"] if item["id"] == second["id"])["pinned"] is True

        ids = [item["id"] for item in pinned.json()["open_workspaces"]]
        reversed_ids = list(reversed(ids))
        reordered = await client.post("/api/workspaces/reorder", json={"workspace_ids": reversed_ids})
        assert reordered.status_code == 200, reordered.text
        assert [item["id"] for item in reordered.json()["open_workspaces"]] == reversed_ids

        closed = await client.post(f"/api/workspaces/{first['id']}/close")
        assert closed.status_code == 200
        assert len(closed.json()["open_workspaces"]) == 7
        assert closed.json()["recent_workspaces"][0]["id"] == first["id"]

        reopened = await client.post(f"/api/workspaces/recent/{first['id']}/reopen")
        assert reopened.status_code == 200, reopened.text
        assert any(item["id"] == first["id"] for item in reopened.json()["open_workspaces"])


@pytest.mark.asyncio
async def test_concurrent_open_enforces_limit_without_eviction(seeded_users, clean_db):
    user = seeded_users["user_a"]
    order_ids = []
    for idx in range(9):
        order = await _seed_order(clean_db, user["tenant_id"], f"{uuid.uuid4().hex[:6]}-race-{idx}", number=f"C{idx}", job_name=f"Concurrent {idx}")
        order_ids.append(order["id"])

    async with await _client_as(user) as client:
        responses = await asyncio.gather(
            *[client.post("/api/workspaces/open", json=_open_order_payload(order_id)) for order_id in order_ids]
        )
        status_codes = sorted(response.status_code for response in responses)
        assert status_codes.count(201) == 8
        assert status_codes.count(409) == 1

        state = (await client.get("/api/workspaces")).json()
        assert len(state["open_workspaces"]) == 8
        opened_ids = {item["record_id"] for item in state["open_workspaces"]}
        assert opened_ids.issubset(set(order_ids))


@pytest.mark.asyncio
async def test_recent_limit_and_deleted_record_fail_safely(seeded_users, clean_db):
    user = seeded_users["user_a"]
    async with await _client_as(user) as client:
        for idx in range(21):
            order = await _seed_order(clean_db, user["tenant_id"], f"{uuid.uuid4().hex[:6]}-recent-{idx}", number=f"R{idx}", job_name=f"Recent {idx}")
            opened = await client.post("/api/workspaces/open", json=_open_order_payload(order["id"]))
            assert opened.status_code == 201
            workspace_id = opened.json()["open_workspaces"][0]["id"]
            closed = await client.post(f"/api/workspaces/{workspace_id}/close")
            assert closed.status_code == 200
        state = (await client.get("/api/workspaces")).json()
        assert len(state["recent_workspaces"]) == 20

        inaccessible = state["recent_workspaces"][0]
        await clean_db.orders.delete_one({"tenant_id": user["tenant_id"], "id": inaccessible["record_id"]})
        response = await client.post(f"/api/workspaces/recent/{inaccessible['id']}/reopen")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_workspace_mutations_do_not_change_underlying_business_record(seeded_users, clean_db):
    user = seeded_users["user_a"]
    order = await _seed_order(clean_db, user["tenant_id"], uuid.uuid4().hex[:8])
    before = await clean_db.orders.find_one({"tenant_id": user["tenant_id"], "id": order["id"]}, {"_id": 0})

    async with await _client_as(user) as client:
        opened = await client.post("/api/workspaces/open", json=_open_order_payload(order["id"]))
        workspace_id = opened.json()["open_workspaces"][0]["id"]
        await client.patch(f"/api/workspaces/{workspace_id}", json={"dirty": True, "scroll_position": 400})
        await client.post(f"/api/workspaces/{workspace_id}/pin")
        await client.post(f"/api/workspaces/{workspace_id}/close")

    after = await clean_db.orders.find_one({"tenant_id": user["tenant_id"], "id": order["id"]}, {"_id": 0})
    assert after == before


@pytest.mark.asyncio
async def test_workspace_dock_indexes_are_registered(clean_db):
    indexes = await clean_db.workspace_docks.index_information()
    key_sets = {tuple(spec["key"]) for spec in indexes.values()}
    assert (("id", 1),) in key_sets
    assert (("tenant_id", 1), ("user_id", 1)) in key_sets
    assert (("tenant_id", 1), ("user_id", 1), ("open_workspaces.workspace_key", 1)) in key_sets
    assert (("tenant_id", 1), ("user_id", 1), ("recent_workspaces.last_opened_at", -1)) in key_sets
