"""EC12 Phase 12D - shared calendar, appointments, and shop schedule feed."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.portal_security import create_portal_token
from app.deps import get_current_user
from app.services.portal_identity import create_portal_identity
from server import app


def _iso(days: int, hour: int = 9) -> str:
    d = datetime.now(timezone.utc).replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=days)
    return d.isoformat()


def _date(days: int) -> str:
    return (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()


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
    tenant_id = f"t-ec12d-{suffix}"
    other_tenant_id = f"t-ec12d-other-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    staff = {"id": f"staff-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "role": "staff", "is_active": True}
    other_owner = {"id": f"other-owner-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "Tenant"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Other"},
    ])
    await db.users.insert_many([owner, staff, other_owner])
    employee = {"id": f"emp-{suffix}", "tenant_id": tenant_id, "name": "Alex Maker", "email": f"alex-{suffix}@example.com", "linked_user_id": staff["id"], "status": "active"}
    await db.employees.insert_one(employee)
    customer_id = f"cust-{suffix}"
    order_id = f"order-{suffix}"
    wo_id = f"wo-{suffix}"
    stage_id = f"stage-{suffix}"
    await db.customers.insert_one({"id": customer_id, "tenant_id": tenant_id, "name": "Acme"})
    await db.customers.insert_one({"id": f"other-cust-{suffix}", "tenant_id": other_tenant_id, "name": "Other"})
    await db.orders.insert_one({"id": order_id, "tenant_id": tenant_id, "number": 1201, "customer_id": customer_id, "status": "confirmed", "created_at": _iso(0), "updated_at": _iso(0)})
    await db.work_orders.insert_one({"id": wo_id, "tenant_id": tenant_id, "number": 3301, "order_id": order_id, "customer_id": customer_id, "production_status": "released", "current_version": True, "items_snapshot": [], "created_at": _iso(0), "updated_at": _iso(0)})
    await db.production_stage_instances.insert_one({"id": stage_id, "tenant_id": tenant_id, "order_id": order_id, "order_item_id": f"item-{suffix}", "work_order_id": wo_id, "workflow_instance_id": f"wf-{suffix}", "stage_key": "print", "stage_name": "Print", "sequence": 1, "status": "not_started", "assigned_employee_id": employee["id"], "due_at": _iso(2, 14), "history": [], "created_at": _iso(0), "updated_at": _iso(0)})
    await db.tasks.insert_one({"id": f"task-{suffix}", "tenant_id": tenant_id, "title": "Call customer", "status": "not_started", "priority": "normal", "task_type": "general", "assigned_employee_id": employee["id"], "employee_visible": True, "due_at": _iso(2, 11), "created_at": _iso(0), "updated_at": _iso(0)})
    schedule_id = f"schedule-{suffix}"
    await db.schedules.insert_one({"id": schedule_id, "tenant_id": tenant_id, "period_start": _date(2), "period_end": _date(8), "status": "published", "version": 1, "created_by": owner["id"], "updated_by": owner["id"]})
    await db.shifts.insert_one({"id": f"shift-{suffix}", "tenant_id": tenant_id, "schedule_id": schedule_id, "employee_id": employee["id"], "shift_date": _date(2), "start_at": _iso(2, 9), "end_at": _iso(2, 17), "status": "scheduled", "created_by": owner["id"], "updated_by": owner["id"]})
    identity = await create_portal_identity(tenant_id=tenant_id, portal_type="employee", employee_id=employee["id"], email=f"portal-{suffix}@example.com")
    yield {
        "tenant_id": tenant_id, "other_tenant_id": other_tenant_id, "owner": owner, "staff": staff,
        "other_owner": other_owner, "employee": employee, "customer_id": customer_id, "order_id": order_id,
        "work_order_id": wo_id, "stage_id": stage_id,
        "token": create_portal_token(portal_identity_id=identity["id"], tenant_id=tenant_id, portal_type="employee", employee_id=employee["id"]),
        "other_customer_id": f"other-cust-{suffix}",
    }
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_appointment_crud_conflicts_projection_filters_and_security(ctx):
    before = {
        "payroll": await db.payroll_transactions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "sms": await db.get_collection("sms_messages").count_documents({"tenant_id": ctx["tenant_id"]}),
    }
    async with await _client_as(ctx["owner"]) as c:
        conflict = await c.post("/api/calendar/events", json={
            "title": "Install consult",
            "event_type": "installation",
            "start_at": _iso(2, 10),
            "end_at": _iso(2, 12),
            "employee_id": ctx["employee"]["id"],
            "customer_id": ctx["customer_id"],
            "order_id": ctx["order_id"],
            "work_order_id": ctx["work_order_id"],
            "location": "Bay 1",
        })
        assert conflict.status_code == 409
        created = await c.post("/api/calendar/events", json={
            "title": "Install consult",
            "event_type": "installation",
            "start_at": _iso(2, 10),
            "end_at": _iso(2, 12),
            "employee_id": ctx["employee"]["id"],
            "customer_id": ctx["customer_id"],
            "order_id": ctx["order_id"],
            "work_order_id": ctx["work_order_id"],
            "location": "Bay 1",
            "conflict_override_reason": "Manager approved overlap",
        })
        assert created.status_code == 201
        event = created.json()
        assert "conflict_overrides" not in event
        assert any(conf["kind"] in {"employee_shift_overlap", "approved_absence"} for conf in event["conflicts"])
        assert (await c.get(f"/api/calendar/events/{event['source_id']}")).status_code == 200
        bad_link = await c.post("/api/calendar/events", json={"title": "Bad", "start_at": _iso(3), "end_at": _iso(3, 10), "customer_id": ctx["other_customer_id"]})
        assert bad_link.status_code == 404

        rescheduled = await c.post(f"/api/calendar/events/{event['source_id']}/reschedule", json={"start_at": _iso(3, 8), "end_at": _iso(3, 9)})
        assert rescheduled.status_code == 200
        assert rescheduled.json()["status"] == "rescheduled"
        updated = await c.patch(f"/api/calendar/events/{event['source_id']}", json={"title": "Updated install consult"})
        assert updated.status_code == 200
        canceled = await c.post(f"/api/calendar/events/{event['source_id']}/cancel", json={"reason": "Customer changed"})
        assert canceled.status_code == 200
        duplicate_cancel = await c.post(f"/api/calendar/events/{event['source_id']}/cancel", json={})
        assert duplicate_cancel.status_code == 200
        assert (await c.post(f"/api/calendar/events/{event['source_id']}/archive")).status_code == 200
        assert (await c.post(f"/api/calendar/events/{event['source_id']}/restore")).status_code == 200

        feed = await c.get("/api/calendar/feed", params={"start_at": _iso(2, 0), "end_at": _iso(4, 0), "employee_id": ctx["employee"]["id"]})
        items = feed.json()["items"]
        assert any(i["source_type"] == "shift" for i in items)
        assert any(i["source_type"] == "task" for i in items)
        assert any(i["source_type"] == "production_stage" for i in items)
        assert any(i["source_type"] == "calendar_event" for i in items)
        assert all("private_reason" not in i and "profit" not in i and "pricing" not in i for i in items)
        assert (await c.get("/api/calendar/feed", params={"start_at": _iso(2, 0), "end_at": _iso(4, 0), "event_type": "task_due"})).json()["total"] >= 1
        assert (await c.get("/api/calendar/feed", params={"start_at": _iso(2, 0), "end_at": _iso(4, 0), "source_type": "shift"})).json()["total"] >= 1

    async with await _token_client(ctx["token"]) as c:
        self_feed = await c.get("/api/portal/employee/calendar", params={"start_at": _iso(2, 0), "end_at": _iso(4, 0)})
        assert self_feed.status_code == 200
        assert all(item.get("employee_id") in {None, ctx["employee"]["id"]} for item in self_feed.json()["items"])
        assert (await c.get("/api/calendar/feed", params={"start_at": _iso(2, 0), "end_at": _iso(4, 0)})).status_code == 401

    async with await _client_as(ctx["other_owner"]) as c:
        isolated = await c.get("/api/calendar/feed", params={"start_at": _iso(2, 0), "end_at": _iso(4, 0)})
        assert isolated.status_code == 200
        assert isolated.json()["total"] == 0

    after = {
        "payroll": await db.payroll_transactions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "sms": await db.get_collection("sms_messages").count_documents({"tenant_id": ctx["tenant_id"]}),
    }
    assert after == before
    assert await db.activity_events.count_documents({"tenant_id": ctx["tenant_id"], "entity_type": "calendar_event"}) >= 4
    assert await db.notifications.count_documents({"tenant_id": ctx["tenant_id"], "module": "calendar"}) >= 1

