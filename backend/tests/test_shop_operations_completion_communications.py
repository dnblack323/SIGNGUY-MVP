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
async def completion_ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-completion-{suffix}"
    other_tenant_id = f"t-completion-other-{suffix}"
    owner = {
        "id": f"owner-{suffix}",
        "tenant_id": tenant_id,
        "email": f"owner-{suffix}@example.com",
        "role": "owner",
        "is_active": True,
    }
    staff = {
        "id": f"staff-{suffix}",
        "tenant_id": tenant_id,
        "email": f"staff-{suffix}@example.com",
        "role": "staff",
        "is_active": True,
    }
    other_owner = {
        "id": f"other-owner-{suffix}",
        "tenant_id": other_tenant_id,
        "email": f"other-owner-{suffix}@example.com",
        "role": "owner",
        "is_active": True,
    }
    customer = {
        "id": f"cust-{suffix}",
        "tenant_id": tenant_id,
        "name": "Rusty Lemon Boutique",
        "email": f"customer-{suffix}@example.com",
    }
    order = {
        "id": f"order-{suffix}",
        "tenant_id": tenant_id,
        "number": 92001,
        "customer_id": customer["id"],
        "job_name": "Window decals",
        "status": "ready",
        "created_by": owner["id"],
        "created_at": "2026-08-17T10:00:00+00:00",
    }
    item = {
        "id": f"item-{suffix}",
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
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "Tenant A"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Tenant B"},
    ])
    await db.users.insert_many([owner, staff, other_owner])
    await db.customers.insert_one(customer)
    await db.orders.insert_one(order)
    await db.order_items.insert_one(item)
    yield {
        "suffix": suffix,
        "tenant_id": tenant_id,
        "other_tenant_id": other_tenant_id,
        "owner": owner,
        "staff": staff,
        "other_owner": other_owner,
        "customer": customer,
        "order": order,
        "item": item,
    }
    _clear_override()


@pytest.mark.asyncio
async def test_order_completion_packet_review_link_public_acceptance_and_tenant_isolation(completion_ctx):
    ctx = completion_ctx
    async with await _client(ctx["owner"]) as client:
        packet_response = await client.post(
            f"/api/orders/{ctx['order']['id']}/completion/packets",
            json={"notes": "Clean with mild soap only."},
        )
        assert packet_response.status_code == 201, packet_response.text
        packet = packet_response.json()
        assert packet["version"] == 1
        assert packet["snapshot"]["aftercare_instructions"][0]["instruction"]

        link_response = await client.post(
            f"/api/orders/{ctx['order']['id']}/completion/review-links",
            json={"packet_id": packet["id"], "recipient_email": ctx["customer"]["email"]},
        )
        assert link_response.status_code == 201, link_response.text
        link = link_response.json()
        assert link["token"]["delivery_history"][0]["status"] == "manual_link_ready"
        assert "raw_token" in link

        completion = await client.get(f"/api/orders/{ctx['order']['id']}/completion")
        assert completion.status_code == 200, completion.text
        body = completion.json()
        assert body["packets"][0]["id"] == packet["id"]
        assert body["review_links"][0]["status"] == "active"

        pdf = await client.get(f"/api/orders/{ctx['order']['id']}/completion/packets/{packet['id']}/download")
        assert pdf.status_code == 200, pdf.text
        assert pdf.headers["content-type"] == "application/pdf"
        assert pdf.content.startswith(b"%PDF")

    async with await _client(ctx["other_owner"]) as client:
        isolated = await client.get(f"/api/orders/{ctx['order']['id']}/completion")
    assert isolated.status_code == 404, isolated.text

    raw_token = link["raw_token"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as public_client:
        public_view = await public_client.get(
            f"/api/public/order-completions/{ctx['order']['id']}",
            params={"t": raw_token},
        )
    assert public_view.status_code == 200, public_view.text
    assert public_view.json()["packet"]["snapshot"]["order"]["job_name"] == "Window decals"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as public_client:
        public_ack = await public_client.post(
            f"/api/public/order-completions/{ctx['order']['id']}/acknowledgement",
            params={"t": raw_token},
            json={"signer_name": "Rusty Customer", "signer_email": ctx["customer"]["email"], "signature_data": "Rusty Customer"},
        )
    assert public_ack.status_code == 201, public_ack.text
    order = await db.orders.find_one({"tenant_id": ctx["tenant_id"], "id": ctx["order"]["id"]}, {"_id": 0})
    assert order["status"] == "completed"
    assert await db.signatures.count_documents({"tenant_id": ctx["tenant_id"]}) == 1
    assert await db.order_completion_records.count_documents({"tenant_id": ctx["tenant_id"], "target_status": "customer_accepted"}) == 1
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as public_client:
        repeated_ack = await public_client.post(
            f"/api/public/order-completions/{ctx['order']['id']}/acknowledgement",
            params={"t": raw_token},
            json={"signer_name": "Rusty Customer", "signer_email": ctx["customer"]["email"], "signature_data": "Rusty Customer"},
        )
    assert repeated_ack.status_code == 409, repeated_ack.text


@pytest.mark.asyncio
async def test_completion_transitions_require_manager_authority_for_overrides(completion_ctx):
    ctx = completion_ctx
    async with await _client(ctx["staff"]) as client:
        ready = await client.post(
            f"/api/orders/{ctx['order']['id']}/completion/transitions",
            json={"target_status": "completed", "reason": "Customer accepted ready order."},
        )
    assert ready.status_code == 201, ready.text
    assert ready.json()["override_applied"] is False
    order = await db.orders.find_one({"tenant_id": ctx["tenant_id"], "id": ctx["order"]["id"]}, {"_id": 0})
    assert order["status"] == "completed"

    await db.orders.update_one(
        {"tenant_id": ctx["tenant_id"], "id": ctx["order"]["id"]},
        {"$set": {"status": "ready", "completion_status": None, "completed_at": None}},
    )
    await db.order_completion_records.delete_many({"tenant_id": ctx["tenant_id"], "order_id": ctx["order"]["id"]})
    await db.order_completion_issues.insert_one({
        "id": f"issue-override-{ctx['suffix']}",
        "tenant_id": ctx["tenant_id"],
        "order_id": ctx["order"]["id"],
        "title": "Open rework",
        "description": "Still needs customer review.",
        "status": "open",
        "created_at": "2026-08-17T10:15:00+00:00",
    })

    async with await _client(ctx["staff"]) as client:
        denied = await client.post(
            f"/api/orders/{ctx['order']['id']}/completion/transitions",
            json={"target_status": "completed", "reason": "Override anyway."},
        )
    assert denied.status_code == 403, denied.text
    order = await db.orders.find_one({"tenant_id": ctx["tenant_id"], "id": ctx["order"]["id"]}, {"_id": 0})
    assert order["status"] == "ready"
    assert await db.order_completion_records.count_documents({"tenant_id": ctx["tenant_id"], "order_id": ctx["order"]["id"]}) == 0

    async with await _client(ctx["owner"]) as client:
        missing_reason = await client.post(
            f"/api/orders/{ctx['order']['id']}/completion/transitions",
            json={"target_status": "completed"},
        )
    assert missing_reason.status_code == 400, missing_reason.text

    async with await _client(ctx["owner"]) as client:
        override = await client.post(
            f"/api/orders/{ctx['order']['id']}/completion/transitions",
            json={"target_status": "completed", "reason": "Owner-approved completion override."},
        )
    assert override.status_code == 201, override.text
    assert override.json()["override_applied"] is True
    audit = await db.audit_events.find_one({"tenant_id": ctx["tenant_id"], "action": "order.completion.completed", "actor_user_id": ctx["owner"]["id"]}, {"_id": 0})
    assert audit
    assert audit["diff"]["override_applied"] is True
    assert audit["diff"]["readiness_blockers"]

    async with await _client(ctx["staff"]) as client:
        reopen_denied = await client.post(
            f"/api/orders/{ctx['order']['id']}/completion/transitions",
            json={"target_status": "reopened", "reason": "Customer called back."},
        )
    assert reopen_denied.status_code == 403, reopen_denied.text
    assert await db.order_completion_records.count_documents({"tenant_id": ctx["tenant_id"], "order_id": ctx["order"]["id"], "target_status": "reopened"}) == 0

    async with await _client(ctx["owner"]) as client:
        reopen = await client.post(
            f"/api/orders/{ctx['order']['id']}/completion/transitions",
            json={"target_status": "reopened", "reason": "Owner-approved rework reopening."},
        )
    assert reopen.status_code == 201, reopen.text
    assert reopen.json()["override_applied"] is True
    reopened = await db.orders.find_one({"tenant_id": ctx["tenant_id"], "id": ctx["order"]["id"]}, {"_id": 0})
    assert reopened["status"] == "in_production"
    assert await db.audit_events.count_documents({"tenant_id": ctx["tenant_id"], "action": "order.completion.reopened"}) == 1

    async with await _client(ctx["other_owner"]) as client:
        isolated = await client.post(
            f"/api/orders/{ctx['order']['id']}/completion/transitions",
            json={"target_status": "completed", "reason": "Cross-tenant attempt."},
        )
    assert isolated.status_code == 404, isolated.text


@pytest.mark.asyncio
async def test_customer_communication_timeline_issue_rework_and_analytics(completion_ctx):
    ctx = completion_ctx
    await db.production_stage_instances.insert_many([
        {"id": f"stage-blocked-{ctx['suffix']}", "tenant_id": ctx["tenant_id"], "work_order_id": "wo-1", "workflow_instance_id": f"wf-a-{ctx['suffix']}", "stage_key": "print", "stage_name": "Print", "status": "blocked", "created_at": "2026-08-17T08:00:00+00:00", "started_at": "2026-08-17T09:00:00+00:00"},
        {"id": f"stage-wait-{ctx['suffix']}", "tenant_id": ctx["tenant_id"], "work_order_id": "wo-2", "workflow_instance_id": f"wf-b-{ctx['suffix']}", "stage_key": "install", "stage_name": "Install", "status": "waiting", "created_at": "2026-08-17T08:30:00+00:00", "started_at": "2026-08-17T09:30:00+00:00"},
        {"id": f"stage-wait-repeat-{ctx['suffix']}", "tenant_id": ctx["tenant_id"], "work_order_id": "wo-4", "workflow_instance_id": f"wf-d-{ctx['suffix']}", "stage_key": "install-two", "stage_name": "Install", "status": "waiting", "created_at": "2026-08-17T07:30:00+00:00", "started_at": "2026-08-17T08:30:00+00:00"},
        {"id": f"stage-completed-{ctx['suffix']}", "tenant_id": ctx["tenant_id"], "work_order_id": "wo-3", "workflow_instance_id": f"wf-c-{ctx['suffix']}", "stage_key": "install-review", "stage_name": "Install", "status": "completed", "created_at": "2026-08-16T08:00:00+00:00", "started_at": "2026-08-16T09:00:00+00:00", "completed_at": "2026-08-16T11:00:00+00:00"},
    ])
    await db.production_time_entries.insert_one({
        "id": f"time-{ctx['suffix']}",
        "tenant_id": ctx["tenant_id"],
        "stage_id": f"stage-completed-{ctx['suffix']}",
        "status": "completed",
        "effective_elapsed_seconds": 3600,
    })
    async with await _client(ctx["owner"]) as client:
        msg = await client.post(
            f"/api/orders/{ctx['order']['id']}/communications/manual",
            json={"subject": "Pickup ready", "body": "Your order is ready for pickup."},
        )
        assert msg.status_code == 201, msg.text
        assert msg.json()["delivery_status"] == "manual_delivery_ready"

        issue = await client.post(
            f"/api/orders/{ctx['order']['id']}/completion/issues",
            json={"title": "Scratch", "description": "Customer reported a scratch.", "status": "open"},
        )
        assert issue.status_code == 201, issue.text

        completion = await client.get(f"/api/orders/{ctx['order']['id']}/completion")
        assert completion.status_code == 200, completion.text
        blockers = {b["code"] for b in completion.json()["readiness"]["blockers"]}
        assert "open_completion_issue" in blockers

        timeline = await client.get(f"/api/orders/{ctx['order']['id']}/communications/timeline")
        assert timeline.status_code == 200, timeline.text
        kinds = {item["kind"] for item in timeline.json()["items"]}
        assert {"manual_customer_message", "issue"}.issubset(kinds)

        analytics = await client.get("/api/dashboard/shop-operations/analytics")
        assert analytics.status_code == 200, analytics.text
        body = analytics.json()
        assert body["counts"]["open_completion_issues"] == 1
        assert body["counts"]["blocked_stages"] == 1
        assert body["counts"]["waiting_stages"] == 2
        assert body["time_summary"]["average_queue_minutes"] == 60
        assert body["time_summary"]["average_active_minutes"] == 60
        assert body["time_summary"]["average_cycle_minutes"] == 180
        assert body["time_summary"]["repeated_delay_count"] == 1
        assert body["restricted_financial_data"] is False
        assert "total_cents" not in str(body)
