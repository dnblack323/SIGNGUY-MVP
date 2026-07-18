"""EC12 Phase 12F - Employee Portal account/productivity completion."""
from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.portal_security import create_portal_token
from app.deps import get_current_user
from server import app


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _override(user: dict):
    async def _get():
        return {**user}
    return _get


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _token_client(token: str) -> AsyncClient:
    app.dependency_overrides.pop(get_current_user, None)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"})


@pytest_asyncio.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-12f-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "Tenant"})
    await db.users.insert_one(owner)
    employee = {
        "id": f"emp-{suffix}", "tenant_id": tenant_id, "name": "Alex Maker",
        "email": f"alex-{suffix}@example.com", "phone": "555-1000",
        "role_label": "Installer", "status": "active", "hourly_rate_cents": 2500,
        "availability_blocks": [], "created_at": _now(), "updated_at": _now(),
    }
    other_employee = {
        "id": f"emp2-{suffix}", "tenant_id": tenant_id, "name": "Blair",
        "email": f"blair-{suffix}@example.com", "status": "active",
    }
    await db.employees.insert_many([employee, other_employee])
    file_id = f"file-{suffix}"
    await db.files.insert_one({"id": file_id, "tenant_id": tenant_id, "filename": "avatar.png", "storage_path": "tenant/avatar.png", "content_type": "image/png"})
    task_id = f"task-{suffix}"
    await db.tasks.insert_one({"id": task_id, "tenant_id": tenant_id, "title": "Employee task", "status": "not_started", "priority": "normal", "assigned_employee_id": employee["id"], "employee_visible": True, "archived_at": None, "created_at": _now(), "updated_at": _now()})
    await db.calendar_events.insert_one({"id": f"cal-{suffix}", "tenant_id": tenant_id, "title": "Appointment", "employee_id": employee["id"], "status": "scheduled", "start_at": _now(), "end_at": _now(), "created_at": _now(), "updated_at": _now()})
    portal_identity = {
        "id": f"pid-{suffix}", "tenant_id": tenant_id, "portal_type": "employee",
        "employee_id": employee["id"], "email": employee["email"], "phone": employee["phone"],
        "full_name": employee["name"], "status": "active", "permissions": [], "permissions_preset": "custom",
    }
    customer_identity = {
        "id": f"custpid-{suffix}", "tenant_id": tenant_id, "portal_type": "customer",
        "customer_id": f"cust-{suffix}", "email": f"cust-{suffix}@example.com", "status": "active",
        "permissions": ["portal:view_quotes"], "permissions_preset": "viewer_only",
    }
    await db.customers.insert_one({"id": customer_identity["customer_id"], "tenant_id": tenant_id, "name": "Customer"})
    await db.portal_identities.insert_many([portal_identity, customer_identity])
    employee_token = create_portal_token(
        portal_identity_id=portal_identity["id"], tenant_id=tenant_id,
        portal_type="employee", employee_id=employee["id"],
    )
    customer_token = create_portal_token(
        portal_identity_id=customer_identity["id"], tenant_id=tenant_id,
        portal_type="customer", customer_id=customer_identity["customer_id"],
    )
    yield {"tenant_id": tenant_id, "owner": owner, "employee": employee, "other_employee": other_employee,
           "file_id": file_id, "task_id": task_id, "employee_token": employee_token, "customer_token": customer_token}
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_employee_profile_availability_messages_preferences_and_safety(ctx):
    before = {
        "payroll_transactions": await db.payroll_transactions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "shifts": await db.shifts.count_documents({"tenant_id": ctx["tenant_id"]}),
        "time_off_requests": await db.time_off_requests.count_documents({"tenant_id": ctx["tenant_id"]}),
        "community_posts": await db.community_posts.count_documents({"tenant_id": ctx["tenant_id"]}),
        "support_tickets": await db.support_tickets.count_documents({"tenant_id": ctx["tenant_id"]}),
        "template_definitions": await db.template_definitions.count_documents({"tenant_id": ctx["tenant_id"]}),
    }

    async with await _client_as(ctx["owner"]) as staff:
        thread = await staff.post("/api/communications/threads", json={
            "thread_type": "direct", "title": "Portal thread",
            "participant_user_ids": [ctx["owner"]["id"]],
            "participant_employee_ids": [ctx["employee"]["id"]],
            "visibility": "employee_visible",
        })
        assert thread.status_code == 201
        hidden = await staff.post("/api/communications/threads", json={
            "thread_type": "direct", "title": "Staff only",
            "participant_user_ids": [ctx["owner"]["id"]],
            "visibility": "internal",
        })
        assert hidden.status_code == 201
        assert (await staff.post(f"/api/communications/threads/{thread.json()['id']}/messages", json={"body": "Visible"})).status_code == 201

    async with await _token_client(ctx["employee_token"]) as c:
        profile = await c.get("/api/portal/employee/profile")
        assert profile.status_code == 200
        assert profile.json()["employee"]["id"] == ctx["employee"]["id"]
        assert "hourly_rate_cents" not in profile.text
        assert "password" not in profile.text.lower()
        protected = await c.patch("/api/portal/employee/profile", json={"hourly_rate_cents": 999999})
        assert protected.status_code in {400, 422}
        base64_image = await c.patch("/api/portal/employee/profile", json={"profile_image_file_id": "data:image/png;base64,abc"})
        assert base64_image.status_code == 400
        missing_image = await c.patch("/api/portal/employee/profile", json={"profile_image_file_id": "missing"})
        assert missing_image.status_code == 404
        update = await c.patch("/api/portal/employee/profile", json={
            "phone": "555-2222", "preferred_name": "Alex", "contact_email": "alex.portal@example.com",
            "profile_image_file_id": ctx["file_id"], "availability": "Prefers morning installs",
            "timezone": "America/New_York",
            "availability_blocks": [{"kind": "unavailable", "day_of_week": 1, "start_time": "15:00", "end_time": "17:00", "note": "Class"}],
        })
        assert update.status_code == 200, update.text
        emp = await db.employees.find_one({"tenant_id": ctx["tenant_id"], "id": ctx["employee"]["id"]}, {"_id": 0})
        assert emp["phone"] == "555-2222"
        assert emp["profile_image_file_id"] == ctx["file_id"]
        assert emp["availability_blocks"][0]["kind"] == "unavailable"
        assert emp["hourly_rate_cents"] == 2500
        assert emp["status"] == "active"
        messages = await c.get("/api/portal/employee/messages")
        assert messages.status_code == 200
        ids = {t["id"] for t in messages.json()["items"]}
        assert thread.json()["id"] in ids
        assert hidden.json()["id"] not in ids
        reply = await c.post(f"/api/portal/employee/messages/{thread.json()['id']}/messages", json={"body": "Reply from portal"})
        assert reply.status_code == 201
        prefs = await c.patch("/api/portal/employee/preferences", json={"announcements": False, "daily_digest": True, "quiet_hours": {"enabled": True, "start_time": "20:00", "timezone": "America/New_York"}})
        assert prefs.status_code == 200
        assert prefs.json()["announcements"] is False
        digest = await c.get("/api/portal/employee/digest/preview")
        assert digest.status_code == 200
        assert digest.json()["sections"]["tasks"]["due_today"] >= 0
        assert "payroll" not in digest.text.lower()
        assert "pricing" not in digest.text.lower()
        staff_route = await c.get("/api/communications/threads")
        assert staff_route.status_code in {401, 403}

    async with await _token_client(ctx["customer_token"]) as customer:
        denied = await customer.get("/api/portal/employee/profile")
        assert denied.status_code == 403

    after = {
        "payroll_transactions": await db.payroll_transactions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "shifts": await db.shifts.count_documents({"tenant_id": ctx["tenant_id"]}),
        "time_off_requests": await db.time_off_requests.count_documents({"tenant_id": ctx["tenant_id"]}),
        "community_posts": await db.community_posts.count_documents({"tenant_id": ctx["tenant_id"]}),
        "support_tickets": await db.support_tickets.count_documents({"tenant_id": ctx["tenant_id"]}),
        "template_definitions": await db.template_definitions.count_documents({"tenant_id": ctx["tenant_id"]}),
    }
    assert after == before
