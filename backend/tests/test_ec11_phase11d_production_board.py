"""EC11 Phase 11D - Production Board manager workflow."""
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _date(days: int = 0) -> str:
    return (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()


def _override(u):
    async def _get():
        return {**u}
    return _get


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _token_client(token: str) -> AsyncClient:
    app.dependency_overrides.pop(get_current_user, None)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"})


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


def _workflow_instance(tenant_id: str, order_id: str, item_id: str, wo_id: str, name: str, source: str = "tenant_default") -> dict:
    return {
        "id": f"wfi-{uuid.uuid4().hex}",
        "tenant_id": tenant_id,
        "order_id": order_id,
        "order_item_id": item_id,
        "work_order_id": wo_id,
        "source_workflow_id": f"wf-{uuid.uuid4().hex}",
        "source_workflow_version": 1,
        "source_type": source,
        "source_name": name,
        "resolution_source": source,
        "status": "active",
        "stage_definitions": [],
        "created_by_user_id": "seed",
        "created_at": _now(),
        "updated_at": _now(),
    }


def _stage(tenant_id: str, instance: dict, key: str, name: str, sequence: int, status: str = "not_started", **extra) -> dict:
    now = _now()
    doc = {
        "id": f"stage-{uuid.uuid4().hex}",
        "tenant_id": tenant_id,
        "workflow_instance_id": instance["id"],
        "order_id": instance["order_id"],
        "order_item_id": instance["order_item_id"],
        "work_order_id": instance["work_order_id"],
        "stage_key": key,
        "stage_name": name,
        "sequence": sequence,
        "status": status,
        "required": True,
        "may_skip": True,
        "requires_reason_to_skip": False,
        "assigned_role": None,
        "due_at": None,
        "proof_gate_type": None,
        "proof_gate_snapshot": None,
        "equipment_requirement_ids": [],
        "certification_requirement_ids": [],
        "customer_visible": False,
        "employee_visible": True,
        "requires_previous_stage_complete": True,
        "production_notes": [],
        "history": [],
        "created_at": now,
        "updated_at": now,
    }
    doc.update(extra)
    return doc


@pytest_asyncio.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-ec11d-{suffix}"
    other_tenant_id = f"t-ec11d-other-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "full_name": "Owner", "role": "owner", "password_hash": "x", "is_active": True}
    staff = {"id": f"staff-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "full_name": "Staff", "role": "staff", "password_hash": "x", "is_active": True}
    viewer = {"id": f"viewer-{suffix}", "tenant_id": tenant_id, "email": f"viewer-{suffix}@example.com", "full_name": "Viewer", "role": "viewer", "password_hash": "x", "is_active": True}
    other_owner = {"id": f"other-owner-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "full_name": "Other", "role": "owner", "password_hash": "x", "is_active": True}
    employee_user = {"id": f"emp-user-{suffix}", "tenant_id": tenant_id, "email": f"emp-user-{suffix}@example.com", "full_name": "Employee User", "role": "staff", "password_hash": "x", "is_active": True}
    blocked_user = {"id": f"blocked-user-{suffix}", "tenant_id": tenant_id, "email": f"blocked-user-{suffix}@example.com", "full_name": "Blocked User", "role": "staff", "password_hash": "x", "is_active": True}

    customer_id = f"cust-{suffix}"
    other_customer_id = f"cust-other-{suffix}"
    order_id = f"order-{suffix}"
    other_order_id = f"order-other-{suffix}"
    employee_id = f"emp-{suffix}"
    blocked_employee_id = f"emp-blocked-{suffix}"
    equipment_id = f"eq-hard-{suffix}"

    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "Tenant"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Other"},
    ])
    await db.users.insert_many([owner, staff, viewer, other_owner, employee_user, blocked_user])
    await db.customers.insert_many([
        {"id": customer_id, "tenant_id": tenant_id, "name": "Acme Signs"},
        {"id": other_customer_id, "tenant_id": other_tenant_id, "name": "Other Customer"},
    ])
    await db.orders.insert_many([
        {"id": order_id, "tenant_id": tenant_id, "number": 8101, "customer_id": customer_id, "status": "in_production", "created_at": _now(), "updated_at": _now()},
        {"id": other_order_id, "tenant_id": other_tenant_id, "number": 9101, "customer_id": other_customer_id, "status": "in_production", "created_at": _now(), "updated_at": _now()},
    ])
    await db.employees.insert_many([
        {"id": employee_id, "tenant_id": tenant_id, "name": "Alex Maker", "linked_user_id": employee_user["id"], "status": "active", "role_label": "Production"},
        {"id": blocked_employee_id, "tenant_id": tenant_id, "name": "No Cert", "linked_user_id": blocked_user["id"], "status": "active", "role_label": "Production"},
    ])
    await db.equipment.insert_one({"id": equipment_id, "tenant_id": tenant_id, "name": "Locked Printer", "access_policy": "required_no_override", "status": "active"})

    item_ids = [f"item-{name}-{suffix}" for name in ["print", "install", "wait", "ready", "done", "manual", "hard"]]
    await db.order_items.insert_many([
        {"id": item_ids[0], "tenant_id": tenant_id, "order_id": order_id, "description": "Lobby Banner", "category": "banners", "production_required": True, "unit_price_cents": 1, "pricing_snapshot": {"unit_price_cents": 1}},
        {"id": item_ids[1], "tenant_id": tenant_id, "order_id": order_id, "description": "Window Vinyl", "category": "vinyl", "production_required": True, "unit_price_cents": 1, "pricing_snapshot": {"unit_price_cents": 1}},
        {"id": item_ids[2], "tenant_id": tenant_id, "order_id": order_id, "description": "Wall Graphic", "category": "vinyl", "production_required": True, "unit_price_cents": 1, "pricing_snapshot": {"unit_price_cents": 1}},
        {"id": item_ids[3], "tenant_id": tenant_id, "order_id": order_id, "description": "Ready Panel", "category": "rigid_signs", "production_required": True, "unit_price_cents": 1, "pricing_snapshot": {"unit_price_cents": 1}},
        {"id": item_ids[4], "tenant_id": tenant_id, "order_id": order_id, "description": "Completed Decal", "category": "decals", "production_required": True, "unit_price_cents": 1, "pricing_snapshot": {"unit_price_cents": 1}},
        {"id": item_ids[5], "tenant_id": tenant_id, "order_id": order_id, "description": "Manual Build", "category": "custom", "production_required": True, "unit_price_cents": 1, "pricing_snapshot": {"unit_price_cents": 1}},
        {"id": item_ids[6], "tenant_id": tenant_id, "order_id": order_id, "description": "Hard Gate", "category": "equipment", "production_required": True, "unit_price_cents": 1, "pricing_snapshot": {"unit_price_cents": 1}},
    ])

    wo_ids = [f"wo-{name}-{suffix}" for name in ["a", "b", "c", "d", "e", "manual", "hard"]]
    await db.work_orders.insert_many([
        {"id": wo_ids[0], "tenant_id": tenant_id, "number": 7101, "order_id": order_id, "customer_id": customer_id, "production_status": "released", "priority": "high", "due_date": _date(-1), "current_version": True, "items_snapshot": [{"order_item_id": item_ids[0], "description": "Lobby Banner"}], "created_at": _now(), "updated_at": _now()},
        {"id": wo_ids[1], "tenant_id": tenant_id, "number": 7102, "order_id": order_id, "customer_id": customer_id, "production_status": "in_progress", "priority": "rush", "due_date": _date(-2), "current_version": True, "items_snapshot": [{"order_item_id": item_ids[1], "description": "Window Vinyl"}], "created_at": _now(), "updated_at": _now()},
        {"id": wo_ids[2], "tenant_id": tenant_id, "number": 7103, "order_id": order_id, "customer_id": customer_id, "production_status": "in_progress", "priority": "normal", "due_date": _date(1), "current_version": True, "items_snapshot": [{"order_item_id": item_ids[2], "description": "Wall Graphic"}], "created_at": _now(), "updated_at": _now()},
        {"id": wo_ids[3], "tenant_id": tenant_id, "number": 7104, "order_id": order_id, "customer_id": customer_id, "production_status": "queued", "priority": "normal", "due_date": _date(2), "current_version": True, "items_snapshot": [{"order_item_id": item_ids[3], "description": "Ready Panel"}], "created_at": _now(), "updated_at": _now()},
        {"id": wo_ids[4], "tenant_id": tenant_id, "number": 7105, "order_id": order_id, "customer_id": customer_id, "production_status": "completed", "priority": "low", "due_date": _date(-1), "current_version": True, "items_snapshot": [{"order_item_id": item_ids[4], "description": "Completed Decal"}], "created_at": _now(), "updated_at": _now()},
        {"id": wo_ids[5], "tenant_id": tenant_id, "number": 7106, "order_id": order_id, "customer_id": customer_id, "production_status": "released", "priority": "normal", "due_date": _date(3), "current_version": True, "items_snapshot": [{"order_item_id": item_ids[5], "description": "Manual Build"}], "created_at": _now(), "updated_at": _now()},
        {"id": wo_ids[6], "tenant_id": tenant_id, "number": 7107, "order_id": order_id, "customer_id": customer_id, "production_status": "queued", "priority": "normal", "due_date": _date(4), "current_version": True, "items_snapshot": [{"order_item_id": item_ids[6], "description": "Hard Gate"}], "created_at": _now(), "updated_at": _now()},
    ])

    instances = [_workflow_instance(tenant_id, order_id, item_ids[i], wo_ids[i], f"Workflow {i}") for i in range(5)]
    manual_instance = _workflow_instance(tenant_id, order_id, item_ids[5], wo_ids[5], "Manual", "manual_no_workflow")
    manual_instance["status"] = "manual_no_workflow"
    hard_instance = _workflow_instance(tenant_id, order_id, item_ids[6], wo_ids[6], "Hard Workflow")
    await db.production_workflow_instances.insert_many(instances + [manual_instance, hard_instance])

    print_stage = _stage(tenant_id, instances[0], "print", "Print", 2, "in_progress", assigned_employee_id=employee_id, assigned_user_id=employee_user["id"], started_at=_now(), due_at=_date(-1), proof_gate_type="approval_required")
    blocked_stage = _stage(tenant_id, instances[1], "install", "Install", 2, "blocked", blocker_reason="Missing substrate", blocked_at=_now(), due_at=_date(-2))
    waiting_stage = _stage(tenant_id, instances[2], "laminate", "Laminate", 1, "waiting", waiting_since=_now(), due_at=_date(1))
    ready_stage = _stage(tenant_id, instances[3], "pack", "Pack", 1, "not_started", due_at=_date(2))
    done_stage = _stage(tenant_id, instances[4], "ship", "Ship", 1, "completed", completed_at=_now(), due_at=_date(-1))
    hard_stage = _stage(tenant_id, hard_instance, "hard", "Hard Equipment", 1, "not_started", due_at=_date(4), equipment_requirement_ids=[equipment_id])
    await db.production_stage_instances.insert_many([
        _stage(tenant_id, instances[0], "design", "Design", 1, "completed", completed_at=_now()),
        print_stage,
        blocked_stage,
        waiting_stage,
        ready_stage,
        done_stage,
        hard_stage,
    ])
    other_instance = _workflow_instance(other_tenant_id, other_order_id, f"other-item-{suffix}", f"other-wo-{suffix}", "Other")
    other_stage = _stage(other_tenant_id, other_instance, "other", "Other", 1, "not_started")
    await db.production_workflow_instances.insert_one(other_instance)
    await db.production_stage_instances.insert_one(other_stage)

    yield {
        "tenant_id": tenant_id,
        "owner": owner,
        "staff": staff,
        "viewer": viewer,
        "other_owner": other_owner,
        "customer_id": customer_id,
        "employee_id": employee_id,
        "blocked_employee_id": blocked_employee_id,
        "print_stage_id": print_stage["id"],
        "blocked_stage_id": blocked_stage["id"],
        "waiting_stage_id": waiting_stage["id"],
        "ready_stage_id": ready_stage["id"],
        "hard_stage_id": hard_stage["id"],
        "other_stage_id": other_stage["id"],
        "wo_id": wo_ids[0],
    }
    _clear()


@pytest.mark.asyncio
async def test_production_board_projection_filters_sorting_pagination_and_safe_fields(ctx):
    async with await _client_as(ctx["staff"]) as c:
        res = await c.get("/api/production/board", params={"group_by": "status", "sort": "priority"})
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["total"] == 7
        rows = data["items"]
        by_stage = {r["current_stage_key"]: r for r in rows if r.get("current_stage_key")}
        assert by_stage["print"]["current_stage_status"] == "in_progress"
        assert by_stage["install"]["current_stage_status"] == "blocked"
        assert by_stage["install"]["blocker_reason"] == "Missing substrate"
        assert by_stage["laminate"]["current_stage_status"] == "waiting"
        assert by_stage["pack"]["current_stage_status"] == "not_started"
        assert by_stage["ship"]["workflow_complete"] is True
        assert any(r["current_stage_status"] == "manual_no_workflow" for r in rows)
        assert by_stage["print"]["completed_stage_count"] == 1
        assert by_stage["print"]["total_stage_count"] == 2
        assert by_stage["print"]["progress_percent"] == 50
        assert by_stage["print"]["overdue"] is True
        assert by_stage["install"]["assigned_employee_id"] is None
        assert by_stage["print"]["proof_or_approval_gate_state"] == "approval_required"
        assert by_stage["hard"]["eligibility_warning"]
        forbidden = {"pricing_snapshot", "unit_price_cents", "payroll", "hourly_rate_cents", "cost", "profit", "margin", "raw_storage_path", "audit_metadata"}
        assert forbidden.isdisjoint(set(by_stage["print"].keys()))

        assert (await c.get("/api/production/board", params={"stage": "print"})).json()["total"] == 1
        assert (await c.get("/api/production/board", params={"stage_status": "blocked"})).json()["total"] == 1
        assert (await c.get("/api/production/board", params={"employee": ctx["employee_id"]})).json()["total"] == 1
        assert (await c.get("/api/production/board", params={"blocked": "true"})).json()["summary_counts"]["blocked"] == 1
        assert (await c.get("/api/production/board", params={"waiting": "true"})).json()["total"] == 1
        assert (await c.get("/api/production/board", params={"overdue": "true"})).json()["summary_counts"]["overdue"] >= 2
        assert (await c.get("/api/production/board", params={"unassigned": "true"})).json()["total"] >= 4
        assert (await c.get("/api/production/board", params={"priority": "rush"})).json()["total"] == 1
        assert (await c.get("/api/production/board", params={"customer": ctx["customer_id"]})).json()["total"] == 7
        assert (await c.get("/api/production/board", params={"due_from": _date(1), "due_to": _date(2)})).json()["total"] == 2
        assert (await c.get("/api/production/board", params={"search": "Lobby"})).json()["total"] == 1
        assert (await c.get("/api/production/board", params={"production_category": "vinyl"})).json()["total"] == 2
        page = (await c.get("/api/production/board", params={"limit": 2, "skip": 1, "sort": "work_order_number"})).json()
        assert page["limit"] == 2
        assert len(page["items"]) == 2
        grouped = (await c.get("/api/production/board", params={"group_by": "stage"})).json()
        assert "print" in grouped["columns"]


@pytest.mark.asyncio
async def test_production_board_permissions_actions_bulk_and_safety(ctx):
    before = {
        "payroll_transactions": await db.payroll_transactions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "pricing_snapshot_records": await db.pricing_snapshot_records.count_documents({"tenant_id": ctx["tenant_id"]}),
        "production_timer_sessions": await db.production_timer_sessions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "production_timer_events": await db.production_timer_events.count_documents({"tenant_id": ctx["tenant_id"]}),
        "analytics_events": await db.analytics_events.count_documents({"tenant_id": ctx["tenant_id"]}),
    }

    async with await _client_as(ctx["staff"]) as c:
        read = await c.get("/api/production/board")
        assert read.status_code == 200
    async with await _client_as(ctx["viewer"]) as c:
        denied = await c.post("/api/production/board/bulk-note", json={"stage_ids": [ctx["print_stage_id"]], "note": "No"})
        assert denied.status_code == 403
    async with await _client_as(ctx["other_owner"]) as c:
        isolated = await c.get("/api/production/board")
        assert isolated.status_code == 200
        assert isolated.json()["total"] == 0

    employee_portal_token = create_access_token(
        subject="portal-employee", tenant_id=ctx["tenant_id"],
        extra={"sub_scope": "portal", "typ": "portal_access", "portal_type": "employee"},
    )
    async with await _token_client(employee_portal_token) as c:
        denied = await c.get("/api/production/board")
        assert denied.status_code == 401
    customer_portal_token = create_access_token(
        subject="portal-customer", tenant_id=ctx["tenant_id"],
        extra={"sub_scope": "portal", "typ": "portal_access", "portal_type": "customer"},
    )
    async with await _token_client(customer_portal_token) as c:
        denied = await c.get("/api/production/board")
        assert denied.status_code == 401

    async with await _client_as(ctx["owner"]) as c:
        assign = await c.post("/api/production/board/bulk-assign", json={"stage_ids": [ctx["blocked_stage_id"]], "employee_id": ctx["employee_id"]})
        assert assign.status_code == 200, assign.text
        assert assign.json()["success_count"] == 1
        mixed = await c.post(
            "/api/production/board/bulk-assign",
            json={"stage_ids": [ctx["hard_stage_id"], ctx["other_stage_id"]], "employee_id": ctx["blocked_employee_id"], "override_reason": "Try"},
        )
        assert mixed.status_code == 200
        assert mixed.json()["success_count"] == 0
        assert mixed.json()["failure_count"] == 2
        due = await c.post("/api/production/board/bulk-due-date", json={"stage_ids": [ctx["blocked_stage_id"]], "due_at": _date(5)})
        assert due.status_code == 200
        wait = await c.post("/api/production/board/bulk-wait", json={"stage_ids": [ctx["print_stage_id"]], "reason": "Batch hold"})
        assert wait.status_code == 200
        note = await c.post("/api/production/board/bulk-note", json={"stage_ids": [ctx["print_stage_id"]], "note": "Batch note"})
        assert note.status_code == 200
        duplicate = await c.post("/api/production/board/bulk-assign", json={"stage_ids": [ctx["blocked_stage_id"], ctx["blocked_stage_id"]], "employee_id": ctx["employee_id"]})
        assert duplicate.status_code == 200
        assert len(duplicate.json()["results"]) == 1
        invalid = await c.post(f"/api/production-stages/{ctx['ready_stage_id']}/complete", json={})
        assert invalid.status_code == 400
        complete = await c.post("/api/production/board/bulk-action", json={"action": "complete", "stage_ids": [ctx["print_stage_id"]]})
        assert complete.status_code == 400
        skip = await c.post("/api/production/board/bulk-action", json={"action": "skip", "stage_ids": [ctx["print_stage_id"]]})
        assert skip.status_code == 400

        timeline = await c.get(f"/api/work-orders/{ctx['wo_id']}/timeline", params={"event_category": "production"})
        assert timeline.status_code == 200
        event_types = [e["event_type"] for e in timeline.json()["items"]]
        assert "stage_waiting" in event_types
        assert "production_note_added" in event_types
        assert event_types.count("production_note_added") == 1

    after = {
        "payroll_transactions": await db.payroll_transactions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "pricing_snapshot_records": await db.pricing_snapshot_records.count_documents({"tenant_id": ctx["tenant_id"]}),
        "production_timer_sessions": await db.production_timer_sessions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "production_timer_events": await db.production_timer_events.count_documents({"tenant_id": ctx["tenant_id"]}),
        "analytics_events": await db.analytics_events.count_documents({"tenant_id": ctx["tenant_id"]}),
    }
    assert after == before
    actions = [a["action"] async for a in db.audit_events.find({"tenant_id": ctx["tenant_id"], "entity_type": "production_stage"}, {"_id": 0, "action": 1})]
    assert "production_stage.assigned" in actions
    assert "production_stage.waiting" in actions
    assert "production_stage.due_date_changed" in actions
    assert "production_stage.production_note_added" in actions
