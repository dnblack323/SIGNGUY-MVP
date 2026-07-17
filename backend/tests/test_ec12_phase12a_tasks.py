"""EC12 Phase 12A - shared task foundation."""
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


def _clear() -> None:
    app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-ec12a-{suffix}"
    other_tenant_id = f"t-ec12a-other-{suffix}"
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
    inactive_employee = {"id": f"emp-inactive-{suffix}", "tenant_id": tenant_id, "name": "Inactive", "status": "inactive"}
    other_employee = {"id": f"emp-other-{suffix}", "tenant_id": other_tenant_id, "name": "Other Emp", "status": "active"}
    await db.employees.insert_many([employee, inactive_employee, other_employee])

    customer_id = f"cust-{suffix}"
    other_customer_id = f"cust-other-{suffix}"
    order_id = f"order-{suffix}"
    other_order_id = f"order-other-{suffix}"
    order_item_id = f"item-{suffix}"
    work_order_id = f"wo-{suffix}"
    stage_id = f"stage-{suffix}"
    await db.customers.insert_many([
        {"id": customer_id, "tenant_id": tenant_id, "name": "Acme Signs"},
        {"id": other_customer_id, "tenant_id": other_tenant_id, "name": "Other"},
    ])
    await db.orders.insert_many([
        {"id": order_id, "tenant_id": tenant_id, "number": 1201, "customer_id": customer_id, "status": "confirmed", "created_at": _now(), "updated_at": _now()},
        {"id": other_order_id, "tenant_id": other_tenant_id, "number": 2201, "customer_id": other_customer_id, "status": "confirmed", "created_at": _now(), "updated_at": _now()},
    ])
    await db.order_items.insert_one({"id": order_item_id, "tenant_id": tenant_id, "order_id": order_id, "description": "Lobby sign", "quantity": 1, "unit_price_cents": 1, "pricing_snapshot": {}})
    await db.work_orders.insert_one({"id": work_order_id, "tenant_id": tenant_id, "number": 3301, "order_id": order_id, "customer_id": customer_id, "production_status": "released", "current_version": True, "items_snapshot": [{"order_item_id": order_item_id}], "created_at": _now(), "updated_at": _now()})
    await db.production_workflow_instances.insert_one({
        "id": f"wfi-{suffix}", "tenant_id": tenant_id, "order_id": order_id,
        "order_item_id": order_item_id, "work_order_id": work_order_id,
        "source_type": "tenant_default", "source_name": "Default", "status": "active",
        "resolution_source": "tenant_default", "stage_definitions": [], "created_by_user_id": owner["id"],
        "created_at": _now(), "updated_at": _now(),
    })
    await db.production_stage_instances.insert_one({
        "id": stage_id, "tenant_id": tenant_id, "workflow_instance_id": f"wfi-{suffix}",
        "order_id": order_id, "order_item_id": order_item_id, "work_order_id": work_order_id,
        "stage_key": "print", "stage_name": "Print", "sequence": 1, "status": "not_started",
        "employee_visible": True, "history": [], "production_notes": [], "created_at": _now(), "updated_at": _now(),
    })
    yield {
        "tenant_id": tenant_id, "other_tenant_id": other_tenant_id,
        "owner": owner, "admin": admin, "staff": staff, "viewer": viewer, "other_owner": other_owner,
        "employee": employee, "inactive_employee": inactive_employee, "other_employee": other_employee,
        "customer_id": customer_id, "other_customer_id": other_customer_id,
        "order_id": order_id, "other_order_id": other_order_id, "order_item_id": order_item_id,
        "work_order_id": work_order_id, "stage_id": stage_id,
    }
    _clear()


@pytest.mark.asyncio
async def test_task_crud_lifecycle_comments_reminders_and_idempotency(ctx, monkeypatch):
    before = {
        "schedules": await db.schedules.count_documents({"tenant_id": ctx["tenant_id"]}),
        "payroll_transactions": await db.payroll_transactions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "production_stage_instances": await db.production_stage_instances.count_documents({"tenant_id": ctx["tenant_id"]}),
        "calendar_events": await db.calendar_events.count_documents({"tenant_id": ctx["tenant_id"]}),
        "message_threads": await db.message_threads.count_documents({"tenant_id": ctx["tenant_id"]}),
        "community_posts": await db.community_posts.count_documents({"tenant_id": ctx["tenant_id"]}),
        "onboarding_progress": await db.onboarding_progress.count_documents({"tenant_id": ctx["tenant_id"]}),
    }

    async with await _client_as(ctx["owner"]) as c:
        payload = {
            "title": "Prepare install packet",
            "description": "Print work order and prep crew notes.",
            "priority": "high",
            "task_type": "production_handoff",
            "customer_id": ctx["customer_id"],
            "order_id": ctx["order_id"],
            "order_item_id": ctx["order_item_id"],
            "work_order_id": ctx["work_order_id"],
            "production_stage_id": ctx["stage_id"],
            "assigned_employee_id": ctx["employee"]["id"],
            "due_at": _date(1),
            "employee_visible": True,
            "idempotency_key": f"idem-{uuid.uuid4().hex}",
        }
        created = await c.post("/api/tasks", json=payload)
        assert created.status_code == 201, created.text
        task = created.json()
        duplicate = await c.post("/api/tasks", json=payload)
        assert duplicate.status_code == 201
        assert duplicate.json()["id"] == task["id"]
        assert await db.tasks.count_documents({"tenant_id": ctx["tenant_id"], "idempotency_key": payload["idempotency_key"]}) == 1

        listed = await c.get("/api/tasks", params={"priority": "high", "assigned_employee_id": ctx["employee"]["id"], "q": "install"})
        assert listed.status_code == 200
        assert listed.json()["total"] == 1
        got = await c.get(f"/api/tasks/{task['id']}")
        assert got.status_code == 200
        forbidden_related = {"customer", "order", "order_item", "work_order", "pricing_snapshot", "cost", "profit", "margin"}
        assert forbidden_related.isdisjoint(set(got.json().keys()))

        updated = await c.patch(f"/api/tasks/{task['id']}", json={"title": "Prepare install packet v2", "priority": "rush"})
        assert updated.status_code == 200
        assert updated.json()["version"] == 2
        assert updated.json()["priority"] == "rush"

        invalid = await c.post(f"/api/tasks/{task['id']}/complete", json={})
        assert invalid.status_code == 400
        assert (await c.post(f"/api/tasks/{task['id']}/start", json={})).status_code == 200
        assert (await c.post(f"/api/tasks/{task['id']}/wait", json={"reason": "Need permit"})).status_code == 200
        assert (await c.post(f"/api/tasks/{task['id']}/resume", json={})).status_code == 200
        assert (await c.post(f"/api/tasks/{task['id']}/block", json={"reason": "Missing ladder"})).status_code == 200
        assert (await c.post(f"/api/tasks/{task['id']}/resume", json={})).status_code == 200
        complete = await c.post(f"/api/tasks/{task['id']}/complete", json={})
        assert complete.status_code == 200
        assert complete.json()["status"] == "completed"
        duplicate_complete = await c.post(f"/api/tasks/{task['id']}/complete", json={})
        assert duplicate_complete.status_code == 200
        stored = await db.tasks.find_one({"id": task["id"]}, {"_id": 0})
        assert len(stored["completion_history"]) == 1
        assert (await c.post(f"/api/tasks/{task['id']}/start", json={})).status_code == 400
        assert (await c.post(f"/api/tasks/{task['id']}/reopen", json={"reason": "More work needed"})).status_code == 200
        assert (await c.post(f"/api/tasks/{task['id']}/cancel", json={"reason": "No longer needed"})).status_code == 200
        assert (await c.post(f"/api/tasks/{task['id']}/reopen", json={"reason": "Reopened"})).status_code == 200

        c1 = await c.post(f"/api/tasks/{task['id']}/comments", json={"body": "Internal note", "visibility": "internal"})
        assert c1.status_code == 201
        c2 = await c.post(f"/api/tasks/{task['id']}/comments", json={"body": "Employee can see this", "visibility": "employee"})
        assert c2.status_code == 201
        edit = await c.patch(f"/api/tasks/{task['id']}/comments/{c2.json()['id']}", json={"body": "Edited employee-visible note"})
        assert edit.status_code == 200
        comments = await c.get(f"/api/tasks/{task['id']}/comments")
        assert len(comments.json()["items"]) == 2

        rp = await c.patch(f"/api/tasks/{task['id']}/reminder-policy", json={"reminder_policy": {"due": True, "overdue": True}})
        assert rp.status_code == 200
        due_1 = await c.post(f"/api/tasks/{task['id']}/reminders/due")
        due_2 = await c.post(f"/api/tasks/{task['id']}/reminders/due")
        overdue_1 = await c.post(f"/api/tasks/{task['id']}/reminders/overdue")
        overdue_2 = await c.post(f"/api/tasks/{task['id']}/reminders/overdue")
        assert due_1.json()["created"] is True
        assert due_2.json()["created"] is False
        assert overdue_1.json()["created"] is True
        assert overdue_2.json()["created"] is False

        async def broken_notify(**kwargs):
            raise RuntimeError("notification outage")

        monkeypatch.setattr(task_service.notifications, "notify", broken_notify)
        no_rollback = await c.post(f"/api/tasks/{task['id']}/assign", json={"assigned_user_id": ctx["staff"]["id"], "assigned_employee_id": ctx["employee"]["id"]})
        assert no_rollback.status_code == 200
        assert no_rollback.json()["assigned_user_id"] == ctx["staff"]["id"]

        archived = await c.post(f"/api/tasks/{task['id']}/archive")
        assert archived.status_code == 200
        assert archived.json()["archived_at"]
        assert (await c.get("/api/tasks")).json()["total"] == 0
        restored = await c.post(f"/api/tasks/{task['id']}/restore")
        assert restored.status_code == 200
        assert restored.json()["archived_at"] is None

    after = {
        "schedules": await db.schedules.count_documents({"tenant_id": ctx["tenant_id"]}),
        "payroll_transactions": await db.payroll_transactions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "production_stage_instances": await db.production_stage_instances.count_documents({"tenant_id": ctx["tenant_id"]}),
        "calendar_events": await db.calendar_events.count_documents({"tenant_id": ctx["tenant_id"]}),
        "message_threads": await db.message_threads.count_documents({"tenant_id": ctx["tenant_id"]}),
        "community_posts": await db.community_posts.count_documents({"tenant_id": ctx["tenant_id"]}),
        "onboarding_progress": await db.onboarding_progress.count_documents({"tenant_id": ctx["tenant_id"]}),
    }
    assert after == before
    audit_actions = [a["action"] async for a in db.audit_events.find({"tenant_id": ctx["tenant_id"], "entity_type": "task"}, {"_id": 0, "action": 1})]
    assert "task.created" in audit_actions
    assert "task.assignment_changed" in audit_actions
    assert "task.comment_added" in audit_actions
    assert "task.reminder_policy_changed" in audit_actions


@pytest.mark.asyncio
async def test_assignments_relations_permissions_and_tenant_isolation(ctx):
    async with await _client_as(ctx["owner"]) as c:
        base = {"title": "Link validation task", "order_id": ctx["order_id"], "employee_visible": True}
        task = (await c.post("/api/tasks", json={**base, "assigned_employee_id": ctx["employee"]["id"]})).json()
        staff_assign = await c.post(f"/api/tasks/{task['id']}/assign", json={"assigned_user_id": ctx["staff"]["id"], "assigned_employee_id": ctx["employee"]["id"]})
        assert staff_assign.status_code == 200
        inactive = await c.post(f"/api/tasks/{task['id']}/assign", json={"assigned_employee_id": ctx["inactive_employee"]["id"]})
        assert inactive.status_code == 404
        cross_emp = await c.post(f"/api/tasks/{task['id']}/assign", json={"assigned_employee_id": ctx["other_employee"]["id"]})
        assert cross_emp.status_code == 404
        unsafe_dual = await c.post(f"/api/tasks/{task['id']}/assign", json={"assigned_user_id": ctx["admin"]["id"], "assigned_employee_id": ctx["employee"]["id"]})
        assert unsafe_dual.status_code == 400

        assert (await c.post("/api/tasks/validate-link", json={"customer_id": ctx["customer_id"]})).status_code == 200
        assert (await c.post("/api/tasks/validate-link", json={"order_id": ctx["order_id"]})).status_code == 200
        assert (await c.post("/api/tasks/validate-link", json={"order_item_id": ctx["order_item_id"]})).status_code == 200
        assert (await c.post("/api/tasks/validate-link", json={"work_order_id": ctx["work_order_id"]})).status_code == 200
        assert (await c.post("/api/tasks/validate-link", json={"production_stage_id": ctx["stage_id"]})).status_code == 200
        assert (await c.post("/api/tasks/validate-link", json={"customer_id": ctx["other_customer_id"]})).status_code == 404
        assert (await c.post("/api/tasks/validate-link", json={"customer_id": "missing"})).status_code == 404
        mismatch = await c.post("/api/tasks", json={"title": "Bad link", "order_id": ctx["other_order_id"], "order_item_id": ctx["order_item_id"]})
        assert mismatch.status_code in (400, 404)

    async with await _client_as(ctx["staff"]) as c:
        read = await c.get("/api/tasks")
        assert read.status_code == 200
        denied = await c.post("/api/tasks", json={"title": "No mutation"})
        assert denied.status_code == 403
    async with await _client_as(ctx["viewer"]) as c:
        assert (await c.get("/api/tasks")).status_code == 403
    async with await _client_as(ctx["other_owner"]) as c:
        isolated = await c.get("/api/tasks")
        assert isolated.status_code == 200
        assert isolated.json()["total"] == 0

    emp_identity = await create_portal_identity(
        tenant_id=ctx["tenant_id"], portal_type="employee", employee_id=ctx["employee"]["id"],
        email=f"emp-{uuid.uuid4().hex[:5]}@example.com",
    )
    emp_token = create_portal_token(portal_identity_id=emp_identity["id"], tenant_id=ctx["tenant_id"], portal_type="employee", employee_id=ctx["employee"]["id"])
    cust_identity = await create_portal_identity(
        tenant_id=ctx["tenant_id"], portal_type="customer", customer_id=ctx["customer_id"],
        email=f"cust-{uuid.uuid4().hex[:5]}@example.com", permissions_preset="viewer_only",
    )
    cust_token = create_portal_token(portal_identity_id=cust_identity["id"], tenant_id=ctx["tenant_id"], portal_type="customer", customer_id=ctx["customer_id"])
    async with await _token_client(emp_token) as c:
        assert (await c.get("/api/tasks")).status_code == 401
    async with await _token_client(cust_token) as c:
        assert (await c.get("/api/tasks")).status_code == 401
        assert (await c.get("/api/portal/employee/tasks")).status_code == 403


@pytest.mark.asyncio
async def test_employee_portal_self_scope_actions_and_comment_filtering(ctx):
    other_employee = {"id": f"emp-2-{uuid.uuid4().hex[:6]}", "tenant_id": ctx["tenant_id"], "name": "Taylor Other", "status": "active"}
    await db.employees.insert_one(other_employee)
    identity = await create_portal_identity(
        tenant_id=ctx["tenant_id"], portal_type="employee", employee_id=ctx["employee"]["id"],
        email=f"portal-{uuid.uuid4().hex[:5]}@example.com",
    )
    other_identity = await create_portal_identity(
        tenant_id=ctx["tenant_id"], portal_type="employee", employee_id=other_employee["id"],
        email=f"portal-other-{uuid.uuid4().hex[:5]}@example.com",
    )
    token = create_portal_token(portal_identity_id=identity["id"], tenant_id=ctx["tenant_id"], portal_type="employee", employee_id=ctx["employee"]["id"])
    other_token = create_portal_token(portal_identity_id=other_identity["id"], tenant_id=ctx["tenant_id"], portal_type="employee", employee_id=other_employee["id"])
    async with await _client_as(ctx["owner"]) as c:
        visible = (await c.post("/api/tasks", json={
            "title": "Portal visible task", "assigned_employee_id": ctx["employee"]["id"],
            "employee_visible": True, "due_at": _date(2),
        })).json()
        hidden = (await c.post("/api/tasks", json={
            "title": "Internal employee task", "assigned_employee_id": ctx["employee"]["id"],
            "employee_visible": False,
        })).json()
        await c.post(f"/api/tasks/{visible['id']}/comments", json={"body": "Internal only", "visibility": "internal"})
        await c.post(f"/api/tasks/{visible['id']}/comments", json={"body": "Employee visible", "visibility": "employee"})

    async with await _token_client(token) as c:
        listing = await c.get("/api/portal/employee/tasks")
        assert listing.status_code == 200
        ids = [t["id"] for t in listing.json()["items"]]
        assert visible["id"] in ids
        assert hidden["id"] not in ids
        detail = await c.get(f"/api/portal/employee/tasks/{visible['id']}")
        assert detail.status_code == 200
        assert [cmt["body"] for cmt in detail.json()["comments"]] == ["Employee visible"]
        assert (await c.post(f"/api/portal/employee/tasks/{visible['id']}/start", json={})).status_code == 200
        assert (await c.post(f"/api/portal/employee/tasks/{visible['id']}/block", json={"reason": "Need material"})).status_code == 200
        assert (await c.post(f"/api/portal/employee/tasks/{visible['id']}/resume", json={})).status_code == 200
        assert (await c.post(f"/api/portal/employee/tasks/{visible['id']}/wait", json={"reason": "Waiting"})).status_code == 200
        assert (await c.post(f"/api/portal/employee/tasks/{visible['id']}/resume", json={})).status_code == 200
        assert (await c.post(f"/api/portal/employee/tasks/{visible['id']}/complete", json={})).status_code == 200
        add_comment = await c.post(f"/api/portal/employee/tasks/{visible['id']}/comments", json={"body": "Done from portal"})
        assert add_comment.status_code == 201
        stored = await db.tasks.find_one({"id": visible["id"]}, {"_id": 0})
        assert stored["completed_by_employee_id"] == ctx["employee"]["id"]

    async with await _token_client(other_token) as c:
        assert (await c.get(f"/api/portal/employee/tasks/{visible['id']}")).status_code == 403
        assert (await c.post(f"/api/portal/employee/tasks/{visible['id']}/start", json={})).status_code == 403
