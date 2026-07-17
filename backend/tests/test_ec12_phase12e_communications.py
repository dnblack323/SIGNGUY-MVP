"""EC12 Phase 12E - shared messages, notes, announcements, preferences, and digest."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.portal_security import create_portal_token
from app.deps import get_current_user
from server import app


def _now(days: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _date(days: int = 0) -> str:
    return (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()


def _override(user: dict):
    async def _get():
        return {**user}
    return _get


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _portal_client(token: str) -> AsyncClient:
    app.dependency_overrides.pop(get_current_user, None)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"})


@pytest_asyncio.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-12e-{suffix}"
    other_tenant_id = f"t-12e-other-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    staff = {"id": f"staff-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "role": "staff", "is_active": True}
    other_owner = {"id": f"other-owner-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "Tenant"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Other"},
    ])
    await db.users.insert_many([owner, staff, other_owner])
    employee = {"id": f"emp-{suffix}", "tenant_id": tenant_id, "name": "Alex Maker", "email": f"alex-{suffix}@example.com", "linked_user_id": staff["id"], "status": "active"}
    inactive_employee = {"id": f"inactive-{suffix}", "tenant_id": tenant_id, "name": "Inactive", "status": "inactive"}
    other_employee = {"id": f"other-emp-{suffix}", "tenant_id": other_tenant_id, "name": "Other", "status": "active"}
    await db.employees.insert_many([employee, inactive_employee, other_employee])
    customer_id = f"cust-{suffix}"
    order_id = f"order-{suffix}"
    work_order_id = f"wo-{suffix}"
    task_id = f"task-{suffix}"
    event_id = f"cal-{suffix}"
    await db.customers.insert_one({"id": customer_id, "tenant_id": tenant_id, "name": "Acme"})
    await db.orders.insert_one({"id": order_id, "tenant_id": tenant_id, "customer_id": customer_id, "number": 1001, "status": "confirmed", "created_at": _now(), "updated_at": _now()})
    await db.work_orders.insert_one({"id": work_order_id, "tenant_id": tenant_id, "number": 2001, "order_id": order_id, "customer_id": customer_id, "production_status": "released", "created_at": _now(), "updated_at": _now()})
    await db.tasks.insert_one({"id": task_id, "tenant_id": tenant_id, "title": "Due task", "status": "not_started", "priority": "normal", "assigned_user_id": owner["id"], "assigned_employee_id": employee["id"], "employee_visible": True, "due_at": _date(), "archived_at": None, "created_at": _now(), "updated_at": _now()})
    await db.calendar_events.insert_one({"id": event_id, "tenant_id": tenant_id, "title": "Install", "status": "scheduled", "employee_id": employee["id"], "start_at": _date(), "end_at": _date(1), "created_at": _now(), "updated_at": _now()})
    portal_identity = {
        "id": f"pid-{suffix}", "tenant_id": tenant_id, "portal_type": "employee",
        "employee_id": employee["id"], "email": employee["email"], "status": "active",
        "permissions": [], "permissions_preset": "custom",
    }
    await db.portal_identities.insert_one(portal_identity)
    token = create_portal_token(
        portal_identity_id=portal_identity["id"], tenant_id=tenant_id,
        portal_type="employee", employee_id=employee["id"],
    )
    yield {
        "tenant_id": tenant_id, "other_tenant_id": other_tenant_id,
        "owner": owner, "staff": staff, "other_owner": other_owner,
        "employee": employee, "inactive_employee": inactive_employee, "other_employee": other_employee,
        "customer_id": customer_id, "order_id": order_id, "work_order_id": work_order_id,
        "task_id": task_id, "event_id": event_id, "token": token,
    }
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_threads_messages_read_state_notes_preferences_digest_and_portal_filtering(ctx):
    before = {
        "community_posts": await db.community_posts.count_documents({"tenant_id": ctx["tenant_id"]}),
        "support_tickets": await db.support_tickets.count_documents({"tenant_id": ctx["tenant_id"]}),
        "template_definitions": await db.template_definitions.count_documents({"tenant_id": ctx["tenant_id"]}),
    }
    async with await _client_as(ctx["owner"]) as c:
        cross = await c.post("/api/communications/threads", json={
            "thread_type": "direct", "title": "Bad cross tenant",
            "participant_employee_ids": [ctx["other_employee"]["id"]],
            "visibility": "employee_visible",
        })
        assert cross.status_code == 404
        inactive = await c.post("/api/communications/threads", json={
            "thread_type": "direct", "title": "Bad inactive",
            "participant_employee_ids": [ctx["inactive_employee"]["id"]],
            "visibility": "employee_visible",
        })
        assert inactive.status_code == 404
        direct = await c.post("/api/communications/threads", json={
            "thread_type": "direct", "title": "Employee update",
            "participant_user_ids": [ctx["staff"]["id"]],
            "participant_employee_ids": [ctx["employee"]["id"]],
            "visibility": "employee_visible",
        })
        assert direct.status_code == 201, direct.text
        thread = direct.json()
        linked = await c.post("/api/communications/threads", json={
            "thread_type": "task_discussion", "title": "Task discussion",
            "task_id": ctx["task_id"], "participant_user_ids": [ctx["owner"]["id"]],
            "participant_employee_ids": [ctx["employee"]["id"]], "visibility": "employee_visible",
        })
        assert linked.status_code == 201
        missing_link = await c.post("/api/communications/threads", json={"thread_type": "order_discussion", "title": "Missing order"})
        assert missing_link.status_code == 400
        msg1 = await c.post(f"/api/communications/threads/{thread['id']}/messages", json={"body": "First", "idempotency_key": "m1"})
        msg2 = await c.post(f"/api/communications/threads/{thread['id']}/messages", json={"body": "First duplicate", "idempotency_key": "m1"})
        assert msg1.status_code == 201
        assert msg2.json()["id"] == msg1.json()["id"]
        assert await db.thread_messages.count_documents({"tenant_id": ctx["tenant_id"], "thread_id": thread["id"]}) == 1
        badge = await c.get("/api/communications/badge")
        assert badge.status_code == 200
        note_internal = await c.post("/api/communications/notes", json={"body": "Internal note", "task_id": ctx["task_id"], "visibility": "internal"})
        note_employee = await c.post("/api/communications/notes", json={"body": "Employee note", "employee_id": ctx["employee"]["id"], "visibility": "employee_visible"})
        note_private = await c.post("/api/communications/notes", json={"body": "Private", "visibility": "private_to_author"})
        assert note_internal.status_code == 201
        assert note_employee.status_code == 201
        assert note_private.status_code == 201
        edited = await c.patch(f"/api/communications/notes/{note_internal.json()['id']}", json={"body": "Edited", "pinned": True})
        assert edited.status_code == 200
        notes = await c.get("/api/communications/notes", params={"task_id": ctx["task_id"]})
        assert notes.json()["total"] == 1
        prefs = await c.patch("/api/communications/preferences/me", json={"daily_digest": False, "quiet_hours": {"enabled": True, "start_time": "17:00", "end_time": "08:00", "timezone": "America/New_York"}})
        assert prefs.status_code == 200
        assert prefs.json()["quiet_hours"]["enabled"] is True
        digest_1 = await c.post("/api/communications/digest/generate")
        digest_2 = await c.post("/api/communications/digest/generate")
        assert digest_1.status_code == 200
        assert digest_2.json()["id"] == digest_1.json()["id"]
        assert "payroll" not in digest_1.text.lower()
        assert "pricing" not in digest_1.text.lower()

    async with await _portal_client(ctx["token"]) as pc:
        employee_threads = await pc.get("/api/portal/employee/messages")
        assert employee_threads.status_code == 200
        assert {t["id"] for t in employee_threads.json()["items"]} >= {thread["id"], linked.json()["id"]}
        employee_messages = await pc.get(f"/api/portal/employee/messages/{thread['id']}")
        assert employee_messages.status_code == 200
        assert all(m["visibility"] == "employee_visible" for m in employee_messages.json()["messages"])
        reply = await pc.post(f"/api/portal/employee/messages/{thread['id']}/messages", json={"body": "Employee reply", "idempotency_key": "emp-r1"})
        assert reply.status_code == 201
        assert reply.json()["sender_employee_id"] == ctx["employee"]["id"]
        assert (await pc.post(f"/api/portal/employee/messages/{thread['id']}/read")).json()["unread_count"] == 0
        emp_prefs = await pc.patch("/api/portal/employee/preferences", json={"daily_digest": True, "quiet_hours": {"enabled": True, "start_time": "19:00"}})
        assert emp_prefs.status_code == 200
        emp_digest = await pc.get("/api/portal/employee/digest/preview")
        assert emp_digest.status_code == 200
        assert "payroll" not in emp_digest.text.lower()
        assert "pricing" not in emp_digest.text.lower()

    async with await _client_as(ctx["other_owner"]) as other:
        forbidden = await other.get(f"/api/communications/threads/{thread['id']}")
        assert forbidden.status_code == 404

    after = {
        "community_posts": await db.community_posts.count_documents({"tenant_id": ctx["tenant_id"]}),
        "support_tickets": await db.support_tickets.count_documents({"tenant_id": ctx["tenant_id"]}),
        "template_definitions": await db.template_definitions.count_documents({"tenant_id": ctx["tenant_id"]}),
    }
    assert after == before
