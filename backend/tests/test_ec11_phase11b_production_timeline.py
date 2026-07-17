"""EC11 Phase 11B - production timeline and event history foundation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.security import create_access_token
from app.deps import get_current_user
from server import app


def _override(u):
    async def _get():
        return {**u}
    return _get


async def _staff_client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _token_client(token: str):
    app.dependency_overrides.pop(get_current_user, None)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"})


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


def _ts(base: datetime, minutes: int) -> str:
    return (base + timedelta(minutes=minutes)).isoformat()


@pytest_asyncio.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-ec11b-{suffix}"
    other_tenant_id = f"t-ec11b-other-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "full_name": "Owner", "role": "owner", "password_hash": "x", "is_active": True}
    staff = {"id": f"staff-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "full_name": "Staff", "role": "staff", "password_hash": "x", "is_active": True}
    other_owner = {"id": f"owner-other-{suffix}", "tenant_id": other_tenant_id, "email": f"owner-other-{suffix}@example.com", "full_name": "Other", "role": "owner", "password_hash": "x", "is_active": True}
    base = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)

    customer_id = f"cust-{suffix}"
    order_id = f"order-{suffix}"
    item_id = f"item-{suffix}"
    other_item_id = f"item-other-{suffix}"
    wo_id = f"wo-{suffix}"
    proof_id = f"proof-{suffix}"
    version_id = f"proof-version-{suffix}"
    approval_id = f"approval-{suffix}"
    revision_id = f"approval-revision-{suffix}"
    file_id = f"file-{suffix}"
    attachment_id = f"attachment-{suffix}"
    invoice_id = f"invoice-{suffix}"
    payment_id = f"payment-{suffix}"

    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "Tenant A"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Tenant B"},
    ])
    await db.users.insert_many([owner, staff, other_owner])
    await db.customers.insert_one({"id": customer_id, "tenant_id": tenant_id, "name": "Customer A"})
    await db.orders.insert_one({
        "id": order_id, "tenant_id": tenant_id, "number": 1101, "customer_id": customer_id,
        "job_name": "Wall graphics", "title": "Wall graphics", "status": "confirmed",
        "created_by": owner["id"], "created_at": _ts(base, 0), "updated_at": _ts(base, 14),
    })
    await db.order_items.insert_many([
        {
            "id": item_id, "tenant_id": tenant_id, "order_id": order_id, "position": 0,
            "description": "Lobby wall graphic", "quantity": 1, "unit_price_cents": 10000,
            "line_total_cents": 10000, "production_required": True,
            "created_at": _ts(base, 1), "updated_at": _ts(base, 13),
        },
        {
            "id": other_item_id, "tenant_id": tenant_id, "order_id": order_id, "position": 1,
            "description": "Install kit", "quantity": 1, "unit_price_cents": 2500,
            "line_total_cents": 2500, "production_required": True,
            "created_at": _ts(base, 2), "updated_at": _ts(base, 2),
        },
    ])
    await db.work_orders.insert_one({
        "id": wo_id, "tenant_id": tenant_id, "number": 2101, "order_id": order_id,
        "customer_id": customer_id, "production_status": "released", "priority": "normal",
        "assigned_user_ids": [staff["id"]], "assigned_to": staff["id"],
        "items_snapshot": [{"order_item_id": item_id, "description": "Lobby wall graphic", "quantity": 1}],
        "created_by": owner["id"], "created_at": _ts(base, 3), "updated_at": _ts(base, 11),
    })
    await db.proofs.insert_one({
        "id": proof_id, "tenant_id": tenant_id, "number": 3101, "parent_type": "order_item",
        "parent_id": item_id, "customer_id": customer_id, "title": "Proof A",
        "status": "changes_requested", "current_version": 1, "current_file_id": file_id,
        "created_by": owner["id"], "created_at": _ts(base, 4), "updated_at": _ts(base, 10),
        "last_sent_at": _ts(base, 6), "approved_at": _ts(base, 8),
        "changes_requested_at": _ts(base, 10), "changes_requested_reason": "Move logo left",
    })
    await db.proof_versions.insert_one({
        "id": version_id, "tenant_id": tenant_id, "proof_id": proof_id, "version": 1,
        "file_id": file_id, "created_by": owner["id"], "created_at": _ts(base, 5), "updated_at": _ts(base, 5),
    })
    await db.approvals.insert_many([
        {
            "id": approval_id, "tenant_id": tenant_id, "parent_type": "proof_version",
            "parent_id": version_id, "parent_version": 1, "action": "approve",
            "actor_type": "portal_customer", "actor_ref": customer_id,
            "actor_display": "Customer A", "created_at": _ts(base, 8), "updated_at": _ts(base, 8),
        },
        {
            "id": revision_id, "tenant_id": tenant_id, "parent_type": "proof_version",
            "parent_id": version_id, "parent_version": 1, "action": "request_changes",
            "reason": "Move logo left", "actor_type": "portal_customer", "actor_ref": customer_id,
            "actor_display": "Customer A", "created_at": _ts(base, 10), "updated_at": _ts(base, 10),
        },
    ])
    await db.files.insert_one({
        "id": file_id, "tenant_id": tenant_id,
        "storage_key": f"/tenants/{tenant_id}/private/proof.pdf",
        "original_filename": "proof.pdf", "mime_type": "application/pdf", "size_bytes": 12,
        "uploaded_by": owner["id"], "visibility": "customer_visible",
        "created_at": _ts(base, 5), "updated_at": _ts(base, 5),
    })
    await db.attachments.insert_one({
        "id": attachment_id, "tenant_id": tenant_id, "file_id": file_id,
        "parent_type": "order_item", "parent_id": item_id, "attached_by": owner["id"],
        "created_at": _ts(base, 5), "updated_at": _ts(base, 5),
    })
    await db.invoices.insert_one({
        "id": invoice_id, "tenant_id": tenant_id, "number": 4101, "order_id": order_id,
        "customer_id": customer_id, "title": "Invoice", "document_status": "issued",
        "financial_status": "partial", "total_cents": 12500, "created_by": owner["id"],
        "created_at": _ts(base, 7), "updated_at": _ts(base, 7),
    })
    await db.payments.insert_one({
        "id": payment_id, "tenant_id": tenant_id, "invoice_id": invoice_id,
        "order_id": order_id, "customer_id": customer_id, "source": "manual",
        "status": "confirmed", "amount_cents": 5000, "method": "cash",
        "created_by": owner["id"], "created_at": _ts(base, 9), "updated_at": _ts(base, 9),
    })
    await db.audit_events.insert_many([
        {
            "id": f"a-status-{suffix}", "tenant_id": tenant_id, "actor_user_id": owner["id"],
            "actor_email": owner["email"], "action": "order.status.confirmed",
            "entity_type": "order", "entity_id": order_id, "summary": "Order confirmed",
            "diff": {"from": "draft", "to": "confirmed"}, "created_at": _ts(base, 12), "updated_at": _ts(base, 12),
        },
        {
            "id": f"a-item-add-{suffix}", "tenant_id": tenant_id, "actor_user_id": owner["id"],
            "actor_email": owner["email"], "action": "order.item_added",
            "entity_type": "order", "entity_id": order_id, "summary": "Item added",
            "diff": {"item_id": item_id}, "created_at": _ts(base, 1), "updated_at": _ts(base, 1),
        },
        {
            "id": f"a-wo-assign-{suffix}", "tenant_id": tenant_id, "actor_user_id": owner["id"],
            "actor_email": owner["email"], "action": "work_order.assign",
            "entity_type": "work_order", "entity_id": wo_id, "summary": "Assigned",
            "diff": {"user_ids": [staff["id"]]}, "created_at": _ts(base, 11), "updated_at": _ts(base, 11),
        },
        {
            "id": f"a-wo-status-{suffix}", "tenant_id": tenant_id, "actor_user_id": staff["id"],
            "actor_email": staff["email"], "action": "work_order.released",
            "entity_type": "work_order", "entity_id": wo_id, "summary": "Released",
            "diff": {"from": "draft", "to": "released"}, "created_at": _ts(base, 12), "updated_at": _ts(base, 12),
        },
        {
            "id": f"a-proof-create-{suffix}", "tenant_id": tenant_id, "actor_user_id": owner["id"],
            "actor_email": owner["email"], "action": "proof.create",
            "entity_type": "proof", "entity_id": proof_id, "summary": "Proof P-3101 created",
            "diff": {"parent_type": "order_item", "parent_id": item_id}, "created_at": _ts(base, 4), "updated_at": _ts(base, 4),
        },
        {
            "id": f"a-payment-{suffix}", "tenant_id": tenant_id, "actor_user_id": owner["id"],
            "actor_email": owner["email"], "action": "invoice.payment_added",
            "entity_type": "invoice", "entity_id": invoice_id, "summary": "Payment added",
            "diff": {"payment_id": payment_id, "amount_cents": 5000}, "created_at": _ts(base, 9), "updated_at": _ts(base, 9),
        },
    ])

    yield {
        "tenant_id": tenant_id, "other_tenant_id": other_tenant_id, "owner": owner, "staff": staff,
        "other_owner": other_owner, "order_id": order_id, "item_id": item_id,
        "other_item_id": other_item_id, "wo_id": wo_id, "proof_id": proof_id, "payment_id": payment_id,
        "base": base,
    }
    _clear()


@pytest.mark.asyncio
async def test_order_timeline_projects_sources_filters_paginates_and_dedupes(ctx):
    async with await _staff_client(ctx["owner"]) as c:
        res = await c.get(f"/api/orders/{ctx['order_id']}/timeline")
        assert res.status_code == 200, res.text
        body = res.json()
        items = body["items"]
        event_types = [e["event_type"] for e in items]
        assert event_types == [e["event_type"] for e in sorted(items, key=lambda x: x["occurred_at"], reverse=True)]
        assert {
            "order_created",
            "order_item_created",
            "order_item_updated",
            "work_order_created",
            "work_order_assigned",
            "work_order_status_changed",
            "artwork_uploaded",
            "artwork_version_uploaded",
            "proof_created",
            "proof_sent",
            "proof_approved",
            "proof_revision_requested",
            "invoice_created",
            "payment_recorded",
            "order_status_changed",
        } <= set(event_types)
        assert event_types.count("order_item_created") == 2
        assert event_types.count("proof_created") == 1
        assert event_types.count("payment_recorded") == 1
        assert all("storage_key" not in str(e) for e in items)
        assert all("estimated_cost_cents" not in str(e) and "margin" not in str(e) for e in items)

        filtered = await c.get(f"/api/orders/{ctx['order_id']}/timeline", params={"event_type": "proof_approved"})
        assert filtered.status_code == 200
        approved = filtered.json()["items"]
        assert approved and {e["event_type"] for e in approved} == {"proof_approved"}
        assert any(e["actor_type"] == "portal_customer" and e["actor_customer_id"] for e in approved)

        customer_safe = await c.get(f"/api/orders/{ctx['order_id']}/timeline", params={"visibility": "customer_visible"})
        assert customer_safe.status_code == 200
        assert customer_safe.json()["items"]
        assert all(e["visibility"] == "customer_visible" for e in customer_safe.json()["items"])

        page = await c.get(f"/api/orders/{ctx['order_id']}/timeline", params={"limit": 2, "offset": 0})
        assert page.status_code == 200
        assert len(page.json()["items"]) == 2
        assert page.json()["next_offset"] == 2

        later = (ctx["base"] + timedelta(minutes=8)).isoformat()
        dated = await c.get(f"/api/orders/{ctx['order_id']}/timeline", params={"date_from": later})
        assert dated.status_code == 200
        assert all(e["occurred_at"] >= later for e in dated.json()["items"])

        actor = await c.get(f"/api/orders/{ctx['order_id']}/timeline", params={"actor": ctx["staff"]["id"]})
        assert actor.status_code == 200
        assert {e["actor_user_id"] for e in actor.json()["items"]} == {ctx["staff"]["id"]}


@pytest.mark.asyncio
async def test_item_and_work_order_timelines_are_scoped_and_staff_readable(ctx):
    async with await _staff_client(ctx["staff"]) as c:
        item_res = await c.get(f"/api/orders/{ctx['order_id']}/items/{ctx['item_id']}/timeline")
        assert item_res.status_code == 200, item_res.text
        item_events = item_res.json()["items"]
        assert item_events
        assert all(e.get("order_item_id") in {ctx["item_id"], None} for e in item_events)
        assert "proof_approved" in {e["event_type"] for e in item_events}

        mismatch = await c.get(f"/api/orders/{ctx['order_id']}/items/not-real/timeline")
        assert mismatch.status_code == 404

        wo_res = await c.get(f"/api/work-orders/{ctx['wo_id']}/timeline")
        assert wo_res.status_code == 200, wo_res.text
        wo_types = {e["event_type"] for e in wo_res.json()["items"]}
        assert {"work_order_created", "work_order_assigned", "work_order_status_changed"} <= wo_types

        by_category = await c.get(f"/api/work-orders/{ctx['wo_id']}/timeline", params={"event_category": "work_order"})
        assert by_category.status_code == 200
        assert all(e["event_category"] == "work_order" for e in by_category.json()["items"])


@pytest.mark.asyncio
async def test_tenant_isolation_portal_denial_and_no_live_side_effects(ctx):
    before = {
        "work_order_stages": await db.work_order_stages.count_documents({"tenant_id": ctx["tenant_id"]}),
        "production_timer_sessions": await db.production_timer_sessions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "production_timer_events": await db.production_timer_events.count_documents({"tenant_id": ctx["tenant_id"]}),
        "time_entries": await db.time_entries.count_documents({"tenant_id": ctx["tenant_id"]}),
        "timesheets": await db.timesheets.count_documents({"tenant_id": ctx["tenant_id"]}),
        "pricing_snapshot_records": await db.pricing_snapshot_records.count_documents({"tenant_id": ctx["tenant_id"]}),
        "payments": await db.payments.count_documents({"tenant_id": ctx["tenant_id"]}),
    }

    async with await _staff_client(ctx["other_owner"]) as c:
        isolated = await c.get(f"/api/orders/{ctx['order_id']}/timeline")
        assert isolated.status_code == 404

    employee_portal_token = create_access_token(
        subject="portal-employee", tenant_id=ctx["tenant_id"],
        extra={"sub_scope": "portal", "typ": "portal_access", "portal_type": "employee"},
    )
    async with await _token_client(employee_portal_token) as c:
        denied = await c.get(f"/api/work-orders/{ctx['wo_id']}/timeline")
        assert denied.status_code == 401

    customer_portal_token = create_access_token(
        subject="portal-customer", tenant_id=ctx["tenant_id"],
        extra={"sub_scope": "portal", "typ": "portal_access", "portal_type": "customer"},
    )
    async with await _token_client(customer_portal_token) as c:
        denied = await c.get(f"/api/orders/{ctx['order_id']}/timeline")
        assert denied.status_code == 401

    async with await _staff_client(ctx["owner"]) as c:
        ok = await c.get(f"/api/orders/{ctx['order_id']}/timeline")
        assert ok.status_code == 200

    after = {
        "work_order_stages": await db.work_order_stages.count_documents({"tenant_id": ctx["tenant_id"]}),
        "production_timer_sessions": await db.production_timer_sessions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "production_timer_events": await db.production_timer_events.count_documents({"tenant_id": ctx["tenant_id"]}),
        "time_entries": await db.time_entries.count_documents({"tenant_id": ctx["tenant_id"]}),
        "timesheets": await db.timesheets.count_documents({"tenant_id": ctx["tenant_id"]}),
        "pricing_snapshot_records": await db.pricing_snapshot_records.count_documents({"tenant_id": ctx["tenant_id"]}),
        "payments": await db.payments.count_documents({"tenant_id": ctx["tenant_id"]}),
    }
    assert after == before
