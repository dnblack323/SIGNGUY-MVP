from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.deps import get_current_user
from server import app


def _override(user: dict):
    async def _get():
        return {**user}

    return _get


async def _client(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear_override() -> None:
    app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def order_readiness_ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-order-ready-{suffix}"
    other_tenant_id = f"t-order-ready-other-{suffix}"
    owner = {
        "id": f"owner-{suffix}",
        "tenant_id": tenant_id,
        "email": f"owner-{suffix}@example.com",
        "role": "owner",
        "is_active": True,
    }
    staff_limited_finance = {
        **owner,
        "id": f"staff-{suffix}",
        "email": f"staff-{suffix}@example.com",
        "role": "staff",
        "permissions": ["order:read", "order:write", "work_order:read", "work_order:write"],
    }
    customer = {
        "id": f"cust-{suffix}",
        "tenant_id": tenant_id,
        "name": "Rusty Lemon Boutique",
        "email": f"rusty-{suffix}@example.com",
        "archived": False,
    }
    other_customer = {
        "id": f"cust-other-{suffix}",
        "tenant_id": other_tenant_id,
        "name": "Other Shop",
    }
    order = {
        "id": f"order-{suffix}",
        "tenant_id": tenant_id,
        "number": 91015,
        "customer_id": customer["id"],
        "job_name": "Window decals",
        "status": "confirmed",
        "total_cents": 42000,
        "created_by": owner["id"],
        "created_at": "2026-08-16T10:00:00+00:00",
    }
    production_item = {
        "id": f"item-prod-{suffix}",
        "tenant_id": tenant_id,
        "order_id": order["id"],
        "description": "Window decal production",
        "category": "window_decal",
        "quantity": 1,
        "unit_price_cents": 42000,
        "line_total_cents": 42000,
        "production_required": True,
        "position": 0,
    }
    service_item = {
        "id": f"item-service-{suffix}",
        "tenant_id": tenant_id,
        "order_id": order["id"],
        "description": "Design consultation",
        "category": "services",
        "quantity": 1,
        "unit_price_cents": 10000,
        "line_total_cents": 10000,
        "production_required": False,
        "position": 1,
    }
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "Tenant A"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Tenant B"},
    ])
    await db.users.insert_many([owner, staff_limited_finance])
    await db.customers.insert_many([customer, other_customer])
    await db.orders.insert_one(order)
    await db.order_items.insert_many([production_item, service_item])
    yield {
        "suffix": suffix,
        "tenant_id": tenant_id,
        "other_tenant_id": other_tenant_id,
        "owner": owner,
        "staff_limited_finance": staff_limited_finance,
        "customer": customer,
        "other_customer": other_customer,
        "order": order,
        "production_item": production_item,
        "service_item": service_item,
    }
    _clear_override()


@pytest.mark.asyncio
async def test_order_workspace_exposes_readiness_finance_approvals_and_linked_assets(order_readiness_ctx):
    ctx = order_readiness_ctx
    invoice = {
        "id": f"invoice-{ctx['suffix']}",
        "tenant_id": ctx["tenant_id"],
        "number": 3201,
        "order_id": ctx["order"]["id"],
        "customer_id": ctx["customer"]["id"],
        "title": "Window decals invoice",
        "status": "sent",
        "document_status": "issued",
        "financial_status": "partial",
        "total_cents": 42000,
        "amount_paid_cents": 12000,
        "balance_due_cents": 30000,
        "created_at": "2026-08-16T10:05:00+00:00",
    }
    file_doc = {
        "id": f"file-{ctx['suffix']}",
        "tenant_id": ctx["tenant_id"],
        "filename": "approved-artwork.pdf",
        "name": "approved-artwork.pdf",
        "archived": False,
    }
    document = {
        "id": f"doc-{ctx['suffix']}",
        "tenant_id": ctx["tenant_id"],
        "title": "Signed installation terms",
        "archived": False,
    }
    room = {
        "id": f"room-{ctx['suffix']}",
        "tenant_id": ctx["tenant_id"],
        "title": "Window decal decision",
        "customer_id": ctx["customer"]["id"],
        "order_id": ctx["order"]["id"],
        "status": "closed",
        "created_at": "2026-08-16T10:10:00+00:00",
    }
    approval = {
        "id": f"approval-{ctx['suffix']}",
        "tenant_id": ctx["tenant_id"],
        "parent_type": "order",
        "parent_id": ctx["order"]["id"],
        "action": "approve",
        "status": "current",
        "snapshot": {"order_id": ctx["order"]["id"], "customer_id": ctx["customer"]["id"]},
        "created_at": "2026-08-16T10:15:00+00:00",
    }
    proof = {
        "id": f"proof-{ctx['suffix']}",
        "tenant_id": ctx["tenant_id"],
        "parent_type": "order_item",
        "parent_id": ctx["production_item"]["id"],
        "order_id": ctx["order"]["id"],
        "customer_id": ctx["customer"]["id"],
        "title": "Window proof",
        "status": "approved",
        "created_at": "2026-08-16T10:20:00+00:00",
    }
    await db.invoices.insert_one(invoice)
    await db.files.insert_one(file_doc)
    await db.attachments.insert_one({
        "id": f"att-{ctx['suffix']}",
        "tenant_id": ctx["tenant_id"],
        "file_id": file_doc["id"],
        "parent_type": "order_item",
        "parent_id": ctx["production_item"]["id"],
    })
    await db.documents.insert_one(document)
    await db.document_links.insert_one({
        "id": f"doc-link-{ctx['suffix']}",
        "tenant_id": ctx["tenant_id"],
        "document_id": document["id"],
        "entity_type": "order",
        "entity_id": ctx["order"]["id"],
    })
    await db.decision_rooms.insert_one(room)
    await db.approvals.insert_one(approval)
    await db.proofs.insert_one(proof)

    async with await _client(ctx["owner"]) as client:
        response = await client.get(f"/api/orders/{ctx['order']['id']}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["readiness"]["summary"]["item_count"] == 2
    assert body["readiness"]["summary"]["production_required_count"] == 1
    assert body["financial_summary"]["available"] is True
    assert body["financial_summary"]["invoice_count"] == 1
    assert body["financial_summary"]["balance_due_cents"] == 30000
    assert body["decision_rooms"][0]["id"] == room["id"]
    assert body["approvals"][0]["id"] == approval["id"]
    assert body["proofs"][0]["id"] == proof["id"]
    assert body["linked_assets"]["files"][0]["id"] == file_doc["id"]
    assert body["linked_assets"]["documents"][0]["id"] == document["id"]


@pytest.mark.asyncio
async def test_readiness_blocks_inactive_customer_missing_items_and_pending_decision_room(order_readiness_ctx):
    ctx = order_readiness_ctx
    blocked_order = {
        "id": f"order-blocked-{ctx['suffix']}",
        "tenant_id": ctx["tenant_id"],
        "number": 91016,
        "customer_id": ctx["customer"]["id"],
        "job_name": "Blocked order",
        "status": "confirmed",
        "created_by": ctx["owner"]["id"],
    }
    await db.orders.insert_one(blocked_order)
    await db.customers.update_one(
        {"tenant_id": ctx["tenant_id"], "id": ctx["customer"]["id"]},
        {"$set": {"lifecycle_status": "archived", "archived": True}},
    )
    await db.decision_rooms.insert_one({
        "id": f"room-active-{ctx['suffix']}",
        "tenant_id": ctx["tenant_id"],
        "title": "Active customer question",
        "customer_id": ctx["customer"]["id"],
        "order_id": blocked_order["id"],
        "status": "published",
        "created_at": "2026-08-16T10:10:00+00:00",
    })

    async with await _client(ctx["owner"]) as client:
        response = await client.get(f"/api/orders/{blocked_order['id']}/readiness")

    assert response.status_code == 200, response.text
    codes = {blocker["code"] for blocker in response.json()["blockers"]}
    assert {"inactive_customer", "missing_items", "decision_room_pending"}.issubset(codes)
    assert response.json()["ready"] is False


@pytest.mark.asyncio
async def test_financial_summary_is_restricted_without_financial_visibility(order_readiness_ctx):
    ctx = order_readiness_ctx
    await db.invoices.insert_one({
        "id": f"invoice-restricted-{ctx['suffix']}",
        "tenant_id": ctx["tenant_id"],
        "number": 3202,
        "order_id": ctx["order"]["id"],
        "customer_id": ctx["customer"]["id"],
        "title": "Restricted invoice",
        "status": "sent",
        "total_cents": 42000,
        "amount_paid_cents": 0,
        "balance_due_cents": 42000,
    })

    async with await _client(ctx["staff_limited_finance"]) as client:
        response = await client.get(f"/api/orders/{ctx['order']['id']}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["permissions"]["financials_visible"] is False
    assert body["financial_summary"] == {"available": False, "restricted": True}


@pytest.mark.asyncio
async def test_order_items_lock_after_invoice_or_active_work_order(order_readiness_ctx):
    ctx = order_readiness_ctx
    async with await _client(ctx["owner"]) as client:
        invoice_response = await client.post("/api/invoices", json={
            "order_id": ctx["order"]["id"],
            "title": "Order invoice",
            "total_cents": 42000,
        })
        assert invoice_response.status_code == 201, invoice_response.text
        patch_response = await client.patch(
            f"/api/orders/{ctx['order']['id']}/items/{ctx['production_item']['id']}",
            json={"unit_price_cents": 43000, "manual_override_reason": "customer add-on"},
        )
        assert patch_response.status_code == 400, patch_response.text
        assert "invoice" in patch_response.json()["detail"].lower()

    second_order = {
        "id": f"order-wo-lock-{ctx['suffix']}",
        "tenant_id": ctx["tenant_id"],
        "number": 91017,
        "customer_id": ctx["customer"]["id"],
        "job_name": "Work order locked",
        "status": "confirmed",
        "created_by": ctx["owner"]["id"],
    }
    second_item = {
        "id": f"item-wo-lock-{ctx['suffix']}",
        "tenant_id": ctx["tenant_id"],
        "order_id": second_order["id"],
        "description": "Truck lettering",
        "category": "vehicle_lettering",
        "quantity": 1,
        "unit_price_cents": 55000,
        "line_total_cents": 55000,
        "production_required": True,
        "position": 0,
    }
    await db.orders.insert_one(second_order)
    await db.order_items.insert_one(second_item)
    async with await _client(ctx["owner"]) as client:
        handoff = await client.post(f"/api/orders/{second_order['id']}/production-handoff", json={})
        assert handoff.status_code == 201, handoff.text
        patch_response = await client.patch(
            f"/api/orders/{second_order['id']}/items/{second_item['id']}",
            json={"unit_price_cents": 56000, "manual_override_reason": "late change"},
        )
        assert patch_response.status_code == 400, patch_response.text
        assert "work order" in patch_response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_production_handoff_requires_override_when_readiness_is_blocked(order_readiness_ctx):
    ctx = order_readiness_ctx
    await db.order_items.update_one(
        {"tenant_id": ctx["tenant_id"], "id": ctx["production_item"]["id"]},
        {"$set": {"design_required": True, "proof_status": "sent"}},
    )

    async with await _client(ctx["owner"]) as client:
        blocked = await client.post(f"/api/orders/{ctx['order']['id']}/production-handoff", json={})
        assert blocked.status_code == 400, blocked.text
        assert "override reason" in blocked.json()["detail"].lower()

        created = await client.post(f"/api/orders/{ctx['order']['id']}/production-handoff", json={
            "override_reason": "Owner approved starting print prep while proof is still pending.",
            "priority": "high",
        })

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["override_applied"] is True
    assert body["work_order"]["priority"] == "high"
    assert body["readiness"]["ready"] is False
    assert await db.audit_events.count_documents({
        "tenant_id": ctx["tenant_id"],
        "action": "order.readiness_override",
        "entity_id": ctx["order"]["id"],
    }) == 1


@pytest.mark.asyncio
async def test_production_handoff_uses_canonical_work_order_generation_and_tenant_isolation(order_readiness_ctx):
    ctx = order_readiness_ctx
    async with await _client(ctx["owner"]) as client:
        created = await client.post(f"/api/orders/{ctx['order']['id']}/production-handoff", json={"priority": "rush"})
        assert created.status_code == 201, created.text
        repeat = await client.post(f"/api/orders/{ctx['order']['id']}/production-handoff", json={"priority": "rush"})

    body = created.json()
    assert body["override_applied"] is False
    assert body["already_exists"] is False
    assert body["readiness"]["ready"] is True
    assert len(body["work_order"]["items_snapshot"]) == 1
    assert body["work_order"]["items_snapshot"][0]["order_item_id"] == ctx["production_item"]["id"]
    assert repeat.status_code == 201, repeat.text
    assert repeat.json()["already_exists"] is True

    other_user = {
        "id": f"owner-other-{ctx['suffix']}",
        "tenant_id": ctx["other_tenant_id"],
        "email": f"owner-other-{ctx['suffix']}@example.com",
        "role": "owner",
        "is_active": True,
    }
    await db.users.insert_one(other_user)
    async with await _client(other_user) as client:
        missing = await client.get(f"/api/orders/{ctx['order']['id']}/readiness")
    assert missing.status_code == 404, missing.text
