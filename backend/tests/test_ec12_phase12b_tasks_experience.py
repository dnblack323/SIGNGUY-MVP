"""EC12 Phase 12B - task list, Kanban, My Tasks, portal, and handoffs."""
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
from app.services import task_service
from server import app


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _date(days: int = 0) -> str:
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
    tenant_id = f"t-ec12b-{suffix}"
    other_tenant_id = f"t-ec12b-other-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    admin = {"id": f"admin-{suffix}", "tenant_id": tenant_id, "email": f"admin-{suffix}@example.com", "role": "admin", "is_active": True}
    staff = {"id": f"staff-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "role": "staff", "is_active": True}
    viewer = {"id": f"viewer-{suffix}", "tenant_id": tenant_id, "email": f"viewer-{suffix}@example.com", "role": "viewer", "is_active": True}
    other_owner = {"id": f"other-owner-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "Tenant"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Other"},
    ])
    await db.users.insert_many([owner, admin, staff, viewer, other_owner])
    employee = {"id": f"emp-{suffix}", "tenant_id": tenant_id, "name": "Alex Maker", "email": f"alex-{suffix}@example.com", "linked_user_id": staff["id"], "status": "active"}
    other_employee = {"id": f"emp-other-{suffix}", "tenant_id": tenant_id, "name": "Taylor Other", "email": f"taylor-{suffix}@example.com", "status": "active"}
    await db.employees.insert_many([employee, other_employee])
    customer_id = f"cust-{suffix}"
    other_customer_id = f"cust-other-{suffix}"
    order_id = f"order-{suffix}"
    work_order_id = f"wo-{suffix}"
    stage_id = f"stage-{suffix}"
    await db.customers.insert_many([
        {"id": customer_id, "tenant_id": tenant_id, "name": "Acme Signs"},
        {"id": other_customer_id, "tenant_id": other_tenant_id, "name": "Other"},
    ])
    await db.orders.insert_one({"id": order_id, "tenant_id": tenant_id, "number": 1201, "customer_id": customer_id, "status": "confirmed", "created_at": _now(), "updated_at": _now()})
    await db.order_items.insert_one({"id": f"item-{suffix}", "tenant_id": tenant_id, "order_id": order_id, "description": "Lobby sign", "quantity": 1, "unit_price_cents": 1, "pricing_snapshot": {}})
    await db.work_orders.insert_one({"id": work_order_id, "tenant_id": tenant_id, "number": 3301, "order_id": order_id, "customer_id": customer_id, "production_status": "released", "current_version": True, "items_snapshot": [], "created_at": _now(), "updated_at": _now()})
    await db.production_stage_instances.insert_one({"id": stage_id, "tenant_id": tenant_id, "order_id": order_id, "work_order_id": work_order_id, "stage_key": "print", "stage_name": "Print", "sequence": 1, "status": "not_started", "history": [], "created_at": _now(), "updated_at": _now()})
    yield {
        "tenant_id": tenant_id, "other_tenant_id": other_tenant_id,
        "owner": owner, "admin": admin, "staff": staff, "viewer": viewer, "other_owner": other_owner,
        "employee": employee, "other_employee": other_employee,
        "customer_id": customer_id, "other_customer_id": other_customer_id,
        "order_id": order_id, "work_order_id": work_order_id, "stage_id": stage_id,
    }
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_staff_list_filters_sort_pagination_kanban_and_my_tasks(ctx):
    async with await _client_as(ctx["owner"]) as c:
        a = (await c.post("/api/tasks", json={"title": "Alpha install", "priority": "high", "task_type": "install", "assigned_user_id": ctx["staff"]["id"], "due_at": _date(-1), "customer_id": ctx["customer_id"]})).json()
        b = (await c.post("/api/tasks", json={"title": "Beta proof", "priority": "low", "task_type": "proof", "due_at": _date(0)})).json()
        g = (await c.post("/api/tasks", json={"title": "Gamma work order", "priority": "rush", "task_type": "production", "assigned_employee_id": ctx["employee"]["id"], "due_at": _date(3), "work_order_id": ctx["work_order_id"]})).json()
        await c.post(f"/api/tasks/{g['id']}/start", json={})
        await c.post(f"/api/tasks/{g['id']}/block", json={"reason": "Need substrate"})
        archived = (await c.post("/api/tasks", json={"title": "Archived hidden", "priority": "normal"})).json()
        await c.post(f"/api/tasks/{archived['id']}/archive")

        assert (await c.get("/api/tasks", params={"status": "blocked"})).json()["total"] == 1
        assert (await c.get("/api/tasks", params={"priority": "high"})).json()["items"][0]["id"] == a["id"]
        assert (await c.get("/api/tasks", params={"assigned_user_id": ctx["staff"]["id"]})).json()["total"] == 1
        assert (await c.get("/api/tasks", params={"overdue": True})).json()["items"][0]["id"] == a["id"]
        assert (await c.get("/api/tasks", params={"unassigned": True})).json()["total"] == 1
        assert (await c.get("/api/tasks", params={"linked_entity_type": "work_order"})).json()["items"][0]["id"] == g["id"]
        assert (await c.get("/api/tasks", params={"q": "proof"})).json()["items"][0]["id"] == b["id"]
        assert len((await c.get("/api/tasks", params={"sort": "newest", "limit": 2, "skip": 0})).json()["items"]) == 2
        assert (await c.get("/api/tasks")).json()["total"] == 3
        assert (await c.get("/api/tasks", params={"include_archived": True})).json()["total"] == 4

        kanban = await c.get("/api/tasks/kanban")
        assert kanban.status_code == 200
        assert any(t["id"] == a["id"] for t in kanban.json()["columns"]["not_started"])
        assert any(t["id"] == g["id"] for t in kanban.json()["columns"]["blocked"])
        valid = await c.post(f"/api/tasks/{a['id']}/start", json={"reason": "Drag to in progress"})
        assert valid.status_code == 200
        duplicate = await c.post(f"/api/tasks/{a['id']}/start", json={"reason": "duplicate drag"})
        assert duplicate.status_code == 200
        invalid = await c.post(f"/api/tasks/{b['id']}/complete", json={})
        assert invalid.status_code == 400
        await c.post(f"/api/tasks/{a['id']}/complete", json={})
        completed_visible = await c.get("/api/tasks/kanban", params={"include_completed": True})
        assert any(t["id"] == a["id"] for t in completed_visible.json()["columns"]["completed"])

    async with await _client_as(ctx["staff"]) as c:
        mine = await c.get("/api/tasks/my")
        assert mine.status_code == 200
        assert any(t["id"] == a["id"] for t in mine.json()["items"])
        assert mine.json()["summary"]["assigned_to_me"] >= 1


@pytest.mark.asyncio
async def test_employee_portal_self_scope_and_module_handoffs(ctx):
    before = {
        "schedules": await db.schedules.count_documents({"tenant_id": ctx["tenant_id"]}),
        "payroll_transactions": await db.payroll_transactions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "calendar_events": await db.calendar_events.count_documents({"tenant_id": ctx["tenant_id"]}),
        "message_threads": await db.message_threads.count_documents({"tenant_id": ctx["tenant_id"]}),
        "community_posts": await db.community_posts.count_documents({"tenant_id": ctx["tenant_id"]}),
        "onboarding_progress": await db.onboarding_progress.count_documents({"tenant_id": ctx["tenant_id"]}),
    }
    async with await _client_as(ctx["owner"]) as c:
        customer_task = (await c.post("/api/tasks", json={"title": "Customer handoff", "source_type": "customer", "source_id": ctx["customer_id"]})).json()
        order_task = (await c.post("/api/tasks", json={"title": "Order handoff", "source_type": "order", "source_id": ctx["order_id"]})).json()
        wo_task = (await c.post("/api/tasks", json={"title": "WO handoff", "source_type": "work_order", "source_id": ctx["work_order_id"]})).json()
        stage_task = (await c.post("/api/tasks", json={"title": "Stage handoff", "source_type": "production_stage", "source_id": ctx["stage_id"], "assigned_employee_id": ctx["employee"]["id"], "employee_visible": True})).json()
        assert customer_task["customer_id"] == ctx["customer_id"]
        assert order_task["order_id"] == ctx["order_id"]
        assert wo_task["work_order_id"] == ctx["work_order_id"]
        assert stage_task["production_stage_id"] == ctx["stage_id"]
        assert (await c.post("/api/tasks", json={"title": "Bad source", "source_type": "customer", "source_id": ctx["other_customer_id"]})).status_code == 404
        assert (await c.post("/api/tasks", json={"title": "Missing source", "source_type": "work_order", "source_id": "missing"})).status_code == 404
        source_wo = await db.work_orders.find_one({"id": ctx["work_order_id"]}, {"_id": 0})
        assert source_wo["production_status"] == "released"
        await c.post(f"/api/tasks/{stage_task['id']}/comments", json={"body": "Internal", "visibility": "internal"})
        await c.post(f"/api/tasks/{stage_task['id']}/comments", json={"body": "Visible", "visibility": "employee"})

    identity = await create_portal_identity(tenant_id=ctx["tenant_id"], portal_type="employee", employee_id=ctx["employee"]["id"], email=f"emp-{uuid.uuid4().hex[:5]}@example.com")
    other_identity = await create_portal_identity(tenant_id=ctx["tenant_id"], portal_type="employee", employee_id=ctx["other_employee"]["id"], email=f"other-{uuid.uuid4().hex[:5]}@example.com")
    token = create_portal_token(portal_identity_id=identity["id"], tenant_id=ctx["tenant_id"], portal_type="employee", employee_id=ctx["employee"]["id"])
    other_token = create_portal_token(portal_identity_id=other_identity["id"], tenant_id=ctx["tenant_id"], portal_type="employee", employee_id=ctx["other_employee"]["id"])
    async with await _token_client(token) as c:
        listing = await c.get("/api/portal/employee/tasks", params={"view": "all_active"})
        assert listing.status_code == 200
        assert [t["id"] for t in listing.json()["items"]] == [stage_task["id"]]
        detail = await c.get(f"/api/portal/employee/tasks/{stage_task['id']}")
        assert [m["body"] for m in detail.json()["comments"]] == ["Visible"]
        assert (await c.post(f"/api/portal/employee/tasks/{stage_task['id']}/start", json={})).status_code == 200
        assert (await c.post(f"/api/portal/employee/tasks/{stage_task['id']}/wait", json={"reason": "Waiting"})).status_code == 200
        assert (await c.post(f"/api/portal/employee/tasks/{stage_task['id']}/resume", json={})).status_code == 200
        assert (await c.post(f"/api/portal/employee/tasks/{stage_task['id']}/complete", json={})).status_code == 200
        assert (await c.get("/api/tasks")).status_code == 401
    async with await _token_client(other_token) as c:
        assert (await c.get(f"/api/portal/employee/tasks/{stage_task['id']}")).status_code == 403

    after = {
        "schedules": await db.schedules.count_documents({"tenant_id": ctx["tenant_id"]}),
        "payroll_transactions": await db.payroll_transactions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "calendar_events": await db.calendar_events.count_documents({"tenant_id": ctx["tenant_id"]}),
        "message_threads": await db.message_threads.count_documents({"tenant_id": ctx["tenant_id"]}),
        "community_posts": await db.community_posts.count_documents({"tenant_id": ctx["tenant_id"]}),
        "onboarding_progress": await db.onboarding_progress.count_documents({"tenant_id": ctx["tenant_id"]}),
    }
    assert after == before


@pytest.mark.asyncio
async def test_notifications_security_and_no_sms(ctx, monkeypatch):
    async with await _client_as(ctx["owner"]) as c:
        task = (await c.post("/api/tasks", json={"title": "Notify me", "assigned_user_id": ctx["staff"]["id"], "due_at": _date(1)})).json()
        assert await db.notifications.count_documents({"tenant_id": ctx["tenant_id"], "module": "tasks", "kind": "task.assigned"}) == 1
        same = await c.post(f"/api/tasks/{task['id']}/assign", json={"assigned_user_id": ctx["staff"]["id"]})
        assert same.status_code == 200
        assert await db.notifications.count_documents({"tenant_id": ctx["tenant_id"], "module": "tasks", "kind": "task.assigned"}) == 1
        due = await c.patch(f"/api/tasks/{task['id']}", json={"due_at": _date(2)})
        assert due.status_code == 200
        assert await db.notifications.count_documents({"tenant_id": ctx["tenant_id"], "module": "tasks", "kind": "task.due_date_changed"}) == 1

        async def broken_notify(**kwargs):
            raise RuntimeError("notification outage")

        monkeypatch.setattr(task_service.notifications, "notify", broken_notify)
        changed = await c.post(f"/api/tasks/{task['id']}/assign", json={"assigned_user_id": ctx["admin"]["id"]})
        assert changed.status_code == 200
        assert changed.json()["assigned_user_id"] == ctx["admin"]["id"]
        assert await db.get_collection("sms_messages").count_documents({"tenant_id": ctx["tenant_id"]}) == 0

    async with await _client_as(ctx["viewer"]) as c:
        assert (await c.post("/api/tasks", json={"title": "Denied"})).status_code == 403
    async with await _client_as(ctx["other_owner"]) as c:
        isolated = await c.get("/api/tasks")
        assert isolated.status_code == 200
        assert isolated.json()["total"] == 0
