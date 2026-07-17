"""EC11 Phase 11E - employee production portal / shop-floor kiosk surface."""
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _date(days: int = 0) -> str:
    return (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


async def _portal_client(token: str) -> AsyncClient:
    app.dependency_overrides.pop(get_current_user, None)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"})


def _workflow_instance(tenant_id: str, order_id: str, item_id: str, wo_id: str) -> dict:
    return {
        "id": f"wfi-{uuid.uuid4().hex}",
        "tenant_id": tenant_id,
        "order_id": order_id,
        "order_item_id": item_id,
        "work_order_id": wo_id,
        "source_workflow_id": f"wf-{uuid.uuid4().hex}",
        "source_workflow_version": 1,
        "source_type": "tenant_default",
        "source_name": "Production Flow",
        "resolution_source": "tenant_default",
        "status": "active",
        "stage_definitions": [],
        "created_by_user_id": "seed",
        "created_at": _now(),
        "updated_at": _now(),
    }


def _stage(tenant_id: str, instance: dict, key: str, name: str, sequence: int, status: str = "not_started", **extra) -> dict:
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
        "due_at": _date(1),
        "proof_gate_type": None,
        "proof_gate_snapshot": None,
        "equipment_requirement_ids": [],
        "certification_requirement_ids": [],
        "customer_visible": False,
        "employee_visible": True,
        "requires_previous_stage_complete": True,
        "production_notes": [],
        "history": [],
        "created_at": _now(),
        "updated_at": _now(),
    }
    doc.update(extra)
    return doc


@pytest_asyncio.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-ec11e-{suffix}"
    other_tenant_id = f"t-ec11e-other-{suffix}"
    employee_id = f"emp-{suffix}"
    other_employee_id = f"emp-other-{suffix}"
    customer_id = f"cust-{suffix}"
    order_id = f"order-{suffix}"
    other_order_id = f"order-other-{suffix}"

    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "Tenant"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Other Tenant"},
    ])
    await db.customers.insert_one({"id": customer_id, "tenant_id": tenant_id, "name": "Acme Signs"})
    await db.orders.insert_many([
        {"id": order_id, "tenant_id": tenant_id, "number": 8801, "customer_id": customer_id, "status": "in_production", "total_cents": 50000, "balance_cents": 50000, "created_at": _now(), "updated_at": _now()},
        {"id": other_order_id, "tenant_id": other_tenant_id, "number": 9901, "customer_id": f"cust-other-{suffix}", "status": "in_production", "created_at": _now(), "updated_at": _now()},
    ])
    await db.employees.insert_many([
        {"id": employee_id, "tenant_id": tenant_id, "name": "Alex Maker", "status": "active", "role_label": "Production"},
        {"id": other_employee_id, "tenant_id": tenant_id, "name": "Taylor Other", "status": "active", "role_label": "Production"},
    ])

    item_ids = [f"item-{name}-{suffix}" for name in ["assigned", "queue", "hidden", "other"]]
    await db.order_items.insert_many([
        {"id": item_ids[0], "tenant_id": tenant_id, "order_id": order_id, "description": "Lobby Banner", "category": "banners", "production_required": True, "unit_price_cents": 10000, "pricing_snapshot": {"unit_price_cents": 10000}},
        {"id": item_ids[1], "tenant_id": tenant_id, "order_id": order_id, "description": "Window Vinyl", "category": "vinyl", "production_required": True, "unit_price_cents": 20000, "pricing_snapshot": {"unit_price_cents": 20000}},
        {"id": item_ids[2], "tenant_id": tenant_id, "order_id": order_id, "description": "Hidden Task", "category": "vinyl", "production_required": True, "unit_price_cents": 30000, "pricing_snapshot": {"unit_price_cents": 30000}},
        {"id": item_ids[3], "tenant_id": other_tenant_id, "order_id": other_order_id, "description": "Other Tenant Task", "category": "banners", "production_required": True, "unit_price_cents": 1, "pricing_snapshot": {"unit_price_cents": 1}},
    ])

    wo_ids = [f"wo-{name}-{suffix}" for name in ["assigned", "queue", "hidden", "other"]]
    await db.work_orders.insert_many([
        {"id": wo_ids[0], "tenant_id": tenant_id, "number": 7801, "order_id": order_id, "customer_id": customer_id, "production_status": "released", "priority": "rush", "due_date": _date(1), "current_version": True, "items_snapshot": [{"order_item_id": item_ids[0], "description": "Lobby Banner"}], "created_at": _now(), "updated_at": _now()},
        {"id": wo_ids[1], "tenant_id": tenant_id, "number": 7802, "order_id": order_id, "customer_id": customer_id, "production_status": "released", "priority": "normal", "due_date": _date(2), "current_version": True, "items_snapshot": [{"order_item_id": item_ids[1], "description": "Window Vinyl"}], "created_at": _now(), "updated_at": _now()},
        {"id": wo_ids[2], "tenant_id": tenant_id, "number": 7803, "order_id": order_id, "customer_id": customer_id, "production_status": "released", "priority": "normal", "due_date": _date(2), "current_version": True, "items_snapshot": [{"order_item_id": item_ids[2], "description": "Hidden Task"}], "created_at": _now(), "updated_at": _now()},
        {"id": wo_ids[3], "tenant_id": other_tenant_id, "number": 9902, "order_id": other_order_id, "customer_id": f"cust-other-{suffix}", "production_status": "released", "priority": "normal", "current_version": True, "items_snapshot": [{"order_item_id": item_ids[3], "description": "Other Tenant Task"}], "created_at": _now(), "updated_at": _now()},
    ])

    instances = [_workflow_instance(tenant_id, order_id, item_ids[i], wo_ids[i]) for i in range(3)]
    other_instance = _workflow_instance(other_tenant_id, other_order_id, item_ids[3], wo_ids[3])
    await db.production_workflow_instances.insert_many(instances + [other_instance])
    assigned_stage = _stage(tenant_id, instances[0], "print", "Print", 1, assigned_employee_id=employee_id)
    queue_stage = _stage(tenant_id, instances[1], "cut", "Cut", 1, assigned_employee_id=other_employee_id)
    hidden_stage = _stage(tenant_id, instances[2], "hide", "Hidden", 1, assigned_employee_id=employee_id, employee_visible=False)
    other_stage = _stage(other_tenant_id, other_instance, "other", "Other", 1)
    await db.production_stage_instances.insert_many([assigned_stage, queue_stage, hidden_stage, other_stage])

    identity = await create_portal_identity(
        tenant_id=tenant_id, portal_type="employee", employee_id=employee_id,
        email=f"alex-{suffix}@example.com", full_name="Alex Maker",
    )
    token = create_portal_token(portal_identity_id=identity["id"], tenant_id=tenant_id, portal_type="employee", employee_id=employee_id)
    customer_identity = await create_portal_identity(
        tenant_id=tenant_id, portal_type="customer", customer_id=customer_id,
        email=f"customer-{suffix}@example.com", permissions_preset="viewer_only",
    )
    customer_token = create_portal_token(portal_identity_id=customer_identity["id"], tenant_id=tenant_id, portal_type="customer", customer_id=customer_id)

    yield {
        "tenant_id": tenant_id,
        "order_id": order_id,
        "employee_id": employee_id,
        "token": token,
        "customer_token": customer_token,
        "assigned_stage_id": assigned_stage["id"],
        "queue_stage_id": queue_stage["id"],
        "hidden_stage_id": hidden_stage["id"],
        "other_stage_id": other_stage["id"],
    }
    _clear()


@pytest.mark.asyncio
async def test_employee_production_projection_is_self_scoped_tenant_safe_and_filtered(ctx):
    async with await _portal_client(ctx["token"]) as c:
        res = await c.get("/api/portal/employee/production")
        assert res.status_code == 200, res.text
        data = res.json()
        assert [t["stage_id"] for t in data["assigned_tasks"]] == [ctx["assigned_stage_id"]]
        assert ctx["queue_stage_id"] in {t["stage_id"] for t in data["shop_queue"]}
        assert ctx["hidden_stage_id"] not in {t["stage_id"] for t in data["assigned_tasks"] + data["shop_queue"]}
        assert ctx["other_stage_id"] not in {t["stage_id"] for t in data["assigned_tasks"] + data["shop_queue"]}
        assigned = data["assigned_tasks"][0]
        assert assigned["allowed_actions"] == ["start", "add_note"]
        forbidden = {"unit_price_cents", "pricing_snapshot", "hourly_rate_cents", "cost", "profit", "margin", "raw_storage_path", "audit_metadata"}
        assert forbidden.isdisjoint(set(assigned.keys()))

        search = await c.get("/api/portal/employee/production", params={"search": "Window"})
        assert search.status_code == 200
        assert search.json()["assigned_tasks"] == []
        assert ctx["queue_stage_id"] in {t["stage_id"] for t in search.json()["shop_queue"]}

    async with await _portal_client(ctx["customer_token"]) as c:
        denied = await c.get("/api/portal/employee/production")
        assert denied.status_code == 403


@pytest.mark.asyncio
async def test_employee_production_actions_reuse_stage_service_and_do_not_create_timer_or_commercial_records(ctx):
    before = {
        "time_entries": await db.time_entries.count_documents({"tenant_id": ctx["tenant_id"]}),
        "timesheets": await db.timesheets.count_documents({"tenant_id": ctx["tenant_id"]}),
        "payroll_transactions": await db.payroll_transactions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "pricing_snapshot_records": await db.pricing_snapshot_records.count_documents({"tenant_id": ctx["tenant_id"]}),
        "production_timer_sessions": await db.production_timer_sessions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "production_timer_events": await db.production_timer_events.count_documents({"tenant_id": ctx["tenant_id"]}),
        "analytics_events": await db.analytics_events.count_documents({"tenant_id": ctx["tenant_id"]}),
    }
    before_order = await db.orders.find_one({"id": ctx["order_id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})

    async with await _portal_client(ctx["token"]) as c:
        start = await c.post(f"/api/portal/employee/production/stages/{ctx['assigned_stage_id']}/start", json={})
        assert start.status_code == 200, start.text
        assert start.json()["status"] == "in_progress"
        blocked_missing_reason = await c.post(f"/api/portal/employee/production/stages/{ctx['assigned_stage_id']}/block", json={})
        assert blocked_missing_reason.status_code == 400
        block = await c.post(f"/api/portal/employee/production/stages/{ctx['assigned_stage_id']}/block", json={"reason": "Material missing"})
        assert block.status_code == 200
        assert block.json()["status"] == "blocked"
        resume = await c.post(f"/api/portal/employee/production/stages/{ctx['assigned_stage_id']}/resume", json={})
        assert resume.status_code == 200
        note = await c.post(f"/api/portal/employee/production/stages/{ctx['assigned_stage_id']}/notes", json={"note": "Checked print settings"})
        assert note.status_code == 200
        complete = await c.post(f"/api/portal/employee/production/stages/{ctx['assigned_stage_id']}/complete", json={"completion_note": "Done"})
        assert complete.status_code == 200
        assert complete.json()["status"] == "completed"

    after = {
        "time_entries": await db.time_entries.count_documents({"tenant_id": ctx["tenant_id"]}),
        "timesheets": await db.timesheets.count_documents({"tenant_id": ctx["tenant_id"]}),
        "payroll_transactions": await db.payroll_transactions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "pricing_snapshot_records": await db.pricing_snapshot_records.count_documents({"tenant_id": ctx["tenant_id"]}),
        "production_timer_sessions": await db.production_timer_sessions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "production_timer_events": await db.production_timer_events.count_documents({"tenant_id": ctx["tenant_id"]}),
        "analytics_events": await db.analytics_events.count_documents({"tenant_id": ctx["tenant_id"]}),
    }
    after_order = await db.orders.find_one({"id": ctx["order_id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})
    assert after == before
    assert after_order["total_cents"] == before_order["total_cents"]
    assert after_order["balance_cents"] == before_order["balance_cents"]
    actions = {a["action"] async for a in db.audit_events.find({"tenant_id": ctx["tenant_id"], "entity_type": "production_stage"}, {"_id": 0, "action": 1})}
    assert {"production_stage.started", "production_stage.blocked", "production_stage.resumed", "production_stage.production_note_added", "production_stage.completed"} <= actions


@pytest.mark.asyncio
async def test_employee_production_actions_reject_unassigned_hidden_and_cross_tenant_stages(ctx):
    async with await _portal_client(ctx["token"]) as c:
        unassigned = await c.post(f"/api/portal/employee/production/stages/{ctx['queue_stage_id']}/start", json={})
        assert unassigned.status_code == 403
        hidden = await c.post(f"/api/portal/employee/production/stages/{ctx['hidden_stage_id']}/start", json={})
        assert hidden.status_code == 404
        other = await c.post(f"/api/portal/employee/production/stages/{ctx['other_stage_id']}/start", json={})
        assert other.status_code == 404
