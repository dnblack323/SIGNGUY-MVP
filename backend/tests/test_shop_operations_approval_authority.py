from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.deps import get_current_user
from server import app


def _override(user):
    async def _get():
        return {**user}
    return _get


async def _client(user):
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear_override():
    app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def approval_ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_a = f"t-approval-a-{suffix}"
    tenant_b = f"t-approval-b-{suffix}"
    owner_a = {"id": f"owner-a-{suffix}", "tenant_id": tenant_a, "email": f"owner-a-{suffix}@example.com", "role": "owner", "is_active": True}
    owner_b = {"id": f"owner-b-{suffix}", "tenant_id": tenant_b, "email": f"owner-b-{suffix}@example.com", "role": "owner", "is_active": True}
    customer = {"id": f"cust-{suffix}", "tenant_id": tenant_a, "name": "Rusty Lemon Boutique", "archived": False}
    quote = {
        "id": f"quote-{suffix}",
        "tenant_id": tenant_a,
        "number": 1048,
        "customer_id": customer["id"],
        "job_name": "Window decals",
        "status": "sent",
        "revision_number": 1,
        "total_cents": 42000,
    }
    quote_line_item = {
        "id": f"quote-line-{suffix}",
        "tenant_id": tenant_a,
        "quote_id": quote["id"],
        "description": "Front window decal",
        "category": "window_decal",
        "quantity": 1,
        "unit_price_cents": 42000,
    }
    order = {
        "id": f"order-{suffix}",
        "tenant_id": tenant_a,
        "number": 91015,
        "customer_id": customer["id"],
        "job_name": "Trailer graphics",
        "status": "confirmed",
    }
    order_item = {
        "id": f"order-item-{suffix}",
        "tenant_id": tenant_a,
        "order_id": order["id"],
        "description": "Full wrap graphics",
        "quantity": 1,
        "unit_price_cents": 42000,
    }
    work_order = {
        "id": f"work-order-{suffix}",
        "tenant_id": tenant_a,
        "number": 1042,
        "order_id": order["id"],
        "customer_id": customer["id"],
        "title": "Trailer graphics production",
        "production_status": "in_progress",
    }
    room = {
        "id": f"room-{suffix}",
        "tenant_id": tenant_a,
        "title": "Trailer wrap approval",
        "customer_id": customer["id"],
        "order_id": order["id"],
        "status": "published",
        "options": [{"id": f"option-{suffix}", "customer_label": "Premium wrap"}],
        "created_at": "2026-08-16T10:00:00+00:00",
    }
    decision = {
        "id": f"decision-{suffix}",
        "tenant_id": tenant_a,
        "decision_room_id": room["id"],
        "published_version_id": f"version-{suffix}",
        "customer_id": customer["id"],
        "option_id": room["options"][0]["id"],
        "action_type": "option_selected",
        "internal_review_status": "pending_review",
        "submitted_at": "2026-08-16T10:15:00+00:00",
    }
    await db.tenants.insert_many([
        {"id": tenant_a, "slug": tenant_a, "name": "Tenant A"},
        {"id": tenant_b, "slug": tenant_b, "name": "Tenant B"},
    ])
    await db.users.insert_many([owner_a, owner_b])
    await db.customers.insert_one(customer)
    await db.quotes.insert_one(quote)
    await db.quote_line_items.insert_one(quote_line_item)
    await db.orders.insert_one(order)
    await db.order_items.insert_one(order_item)
    await db.work_orders.insert_one(work_order)
    await db.decision_rooms.insert_one(room)
    await db.customer_decisions.insert_one(decision)
    yield {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "owner_a": owner_a,
        "owner_b": owner_b,
        "customer": customer,
        "quote": quote,
        "quote_line_item": quote_line_item,
        "order": order,
        "order_item": order_item,
        "work_order": work_order,
        "room": room,
        "decision": decision,
    }
    _clear_override()


@pytest.mark.asyncio
async def test_approval_center_queue_combines_approvals_and_decision_room_activity(approval_ctx):
    async with await _client(approval_ctx["owner_a"]) as client:
        status = await client.post(f"/api/quotes/{approval_ctx['quote']['id']}/status", json={"status": "approved", "source": "staff"})
        assert status.status_code == 200, status.text
        await db.approvals.insert_one({
            "id": f"wo-approval-{uuid.uuid4().hex}",
            "tenant_id": approval_ctx["tenant_a"],
            "parent_type": "work_order_summary",
            "parent_id": approval_ctx["work_order"]["id"],
            "action": "approve",
            "status": "current",
            "actor_type": "staff",
            "actor_ref": approval_ctx["owner_a"]["id"],
            "actor_display": "Owner A",
            "snapshot": {"order_id": approval_ctx["order"]["id"], "customer_id": approval_ctx["customer"]["id"]},
            "created_at": "2026-08-16T10:20:00+00:00",
        })
        await db.signature_requests.insert_one({
            "id": f"sig-{uuid.uuid4().hex}",
            "tenant_id": approval_ctx["tenant_a"],
            "number": 1,
            "parent_type": "quote",
            "parent_id": approval_ctx["quote"]["id"],
            "title": "Quote signature",
            "required_signers": [{"name": "Rusty", "email": "rusty@example.com", "signed": False}],
            "status": "sent",
            "created_at": "2026-08-16T10:25:00+00:00",
        })
        await db.proofs.insert_one({
            "id": f"proof-{uuid.uuid4().hex}",
            "tenant_id": approval_ctx["tenant_a"],
            "number": 1,
            "parent_type": "order",
            "parent_id": approval_ctx["order"]["id"],
            "order_id": approval_ctx["order"]["id"],
            "customer_id": approval_ctx["customer"]["id"],
            "title": "Window proof",
            "status": "sent",
            "created_at": "2026-08-16T10:30:00+00:00",
        })
        queue = await client.get("/api/approval-center/queue", params={"unresolved_only": False})

    assert queue.status_code == 200, queue.text
    items = queue.json()["items"]
    queue_types = {item["queue_type"] for item in items}
    assert "approval_record" in queue_types
    assert "decision_room_activity" in queue_types
    assert "signature_request" in queue_types
    assert "proof" in queue_types
    assert any(item["target_type"] == "work_order_summary" and item["source_url"] == f"/work-orders/{approval_ctx['work_order']['id']}" for item in items)
    approval_item = next(item for item in items if item["queue_type"] == "approval_record" and item["target_type"] == "quote_revision")
    assert approval_item["target_type"] == "quote_revision"
    assert approval_item["quote_id"] == approval_ctx["quote"]["id"]
    decision_item = next(item for item in items if item["queue_type"] == "decision_room_activity")
    assert decision_item["title"] == "Trailer wrap approval"
    assert decision_item["source_url"] == f"/decision-rooms/{approval_ctx['room']['id']}"


@pytest.mark.asyncio
async def test_approval_center_searches_targets_and_creates_order_item_work_tenant_safely(approval_ctx):
    async with await _client(approval_ctx["owner_a"]) as client:
        targets = await client.get("/api/approval-center/targets", params={"target_type": "order_item", "search": "wrap"})
        assert targets.status_code == 200, targets.text
        assert [item["id"] for item in targets.json()["items"]] == [approval_ctx["order_item"]["id"]]

        created = await client.post("/api/approval-center/work", json={
            "target_type": "order_item",
            "target_id": approval_ctx["order_item"]["id"],
            "title": "Approve full wrap artwork",
        })
        assert created.status_code == 201, created.text
        room = created.json()
        assert room["order_id"] == approval_ctx["order"]["id"]
        assert room["order_item_id"] == approval_ctx["order_item"]["id"]
        assert room["customer_id"] == approval_ctx["customer"]["id"]

    async with await _client(approval_ctx["owner_b"]) as client:
        denied = await client.post("/api/approval-center/work", json={
            "target_type": "order_item",
            "target_id": approval_ctx["order_item"]["id"],
            "title": "Cross-tenant attempt",
        })
        assert denied.status_code == 404


@pytest.mark.asyncio
async def test_approval_center_creates_quote_line_item_work_and_records_history(approval_ctx):
    async with await _client(approval_ctx["owner_a"]) as client:
        targets = await client.get("/api/approval-center/targets", params={"target_type": "quote_line_item", "search": "decal"})
        assert targets.status_code == 200, targets.text
        body = targets.json()
        assert body["items"][0]["id"] == approval_ctx["quote_line_item"]["id"]
        assert body["items"][0]["quote_id"] == approval_ctx["quote"]["id"]

        created = await client.post("/api/approval-center/work", json={
            "target_type": "quote_line_item",
            "target_id": approval_ctx["quote_line_item"]["id"],
            "title": "Approve window decal line",
        })
        assert created.status_code == 201, created.text
        room = created.json()
        assert room["quote_id"] == approval_ctx["quote"]["id"]
        assert room["customer_id"] == approval_ctx["customer"]["id"]
        assert room["metadata"]["target_type"] == "quote_line_item"
        assert room["metadata"]["quote_line_item_id"] == approval_ctx["quote_line_item"]["id"]

        await client.post(f"/api/quotes/{approval_ctx['quote']['id']}/status", json={"status": "approved", "source": "staff"})
        history = await client.get("/api/approval-center/history", params={"source_type": "quote", "source_id": approval_ctx["quote"]["id"]})
        assert history.status_code == 200, history.text
        assert any(item["parent_type"] == "quote_revision" for item in history.json()["items"])

    async with await _client(approval_ctx["owner_b"]) as client:
        denied = await client.get("/api/approval-center/targets", params={"target_type": "quote_line_item", "search": "decal"})
        assert denied.status_code == 200
        assert denied.json()["items"] == []


@pytest.mark.asyncio
async def test_decision_room_share_tokens_are_listed_and_revoked_without_hashes(approval_ctx):
    async with await _client(approval_ctx["owner_a"]) as client:
        minted = await client.post(f"/api/decision-rooms/{approval_ctx['room']['id']}/share", json={
            "audience_email": "rusty@example.com",
            "ttl_hours": 24,
            "single_use": False,
        })
        assert minted.status_code == 201, minted.text
        token_id = minted.json()["record"]["id"]
        assert minted.json()["token"]
        assert "token_hash" not in minted.json()["record"]

        listed = await client.get(f"/api/decision-rooms/{approval_ctx['room']['id']}/share-tokens")
        assert listed.status_code == 200, listed.text
        token = listed.json()["items"][0]
        assert token["id"] == token_id
        assert token["audience_email"] == "rusty@example.com"
        assert "token_hash" not in token

        revoked = await client.delete(f"/api/decision-rooms/share-tokens/{token_id}")
        assert revoked.status_code == 204, revoked.text
        listed_again = await client.get(f"/api/decision-rooms/{approval_ctx['room']['id']}/share-tokens")
        assert listed_again.json()["items"][0]["revoked"] is True


@pytest.mark.asyncio
async def test_quote_approval_and_decline_record_canonical_approval_rows(approval_ctx):
    async with await _client(approval_ctx["owner_a"]) as client:
        approved = await client.post(f"/api/quotes/{approval_ctx['quote']['id']}/status", json={"status": "approved", "source": "staff"})
        assert approved.status_code == 200, approved.text
        approval = await db.approvals.find_one({
            "tenant_id": approval_ctx["tenant_a"],
            "parent_type": "quote_revision",
            "parent_id": approval_ctx["quote"]["id"],
            "action": "approve",
        }, {"_id": 0})
        assert approval
        assert approved.json()["approved_approval_id"] == approval["id"]

        decline_quote = {k: v for k, v in approval_ctx["quote"].items() if k != "_id"}
        decline_quote.update({"id": f"decline-{uuid.uuid4().hex}", "number": 2048, "status": "sent"})
        await db.quotes.insert_one(decline_quote)
        declined = await client.post(f"/api/quotes/{decline_quote['id']}/status", json={
            "status": "declined",
            "reason": "Customer chose another option",
            "source": "staff",
        })
        assert declined.status_code == 200, declined.text
        decline_approval = await db.approvals.find_one({
            "tenant_id": approval_ctx["tenant_a"],
            "parent_type": "quote_revision",
            "parent_id": decline_quote["id"],
            "action": "decline",
        }, {"_id": 0})
        assert decline_approval
        assert decline_approval["reason"] == "Customer chose another option"
