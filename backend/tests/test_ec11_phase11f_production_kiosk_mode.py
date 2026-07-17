"""EC11 Phase 11F - restricted shop-floor production kiosk mode."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.deps import get_current_user
from app.services.portal_identity import create_portal_identity
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


async def _kiosk_client(device_token: str, employee_token: str | None = None) -> AsyncClient:
    app.dependency_overrides.pop(get_current_user, None)
    headers = {"X-Kiosk-Device-Token": device_token}
    if employee_token:
        headers["X-Kiosk-Employee-Token"] = employee_token
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers)


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


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
    tenant_id = f"t-ec11f-{suffix}"
    other_tenant_id = f"t-ec11f-other-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "full_name": "Owner", "role": "owner", "password_hash": "x", "is_active": True}
    viewer = {"id": f"viewer-{suffix}", "tenant_id": tenant_id, "email": f"viewer-{suffix}@example.com", "full_name": "Viewer", "role": "viewer", "password_hash": "x", "is_active": True}
    employee_id = f"emp-{suffix}"
    other_employee_id = f"emp-other-{suffix}"
    customer_id = f"cust-{suffix}"
    order_id = f"order-{suffix}"

    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "Tenant"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Other Tenant"},
    ])
    await db.users.insert_many([owner, viewer])
    await db.customers.insert_one({"id": customer_id, "tenant_id": tenant_id, "name": "Acme Signs"})
    await db.orders.insert_one({"id": order_id, "tenant_id": tenant_id, "number": 1111, "customer_id": customer_id, "status": "in_production", "total_cents": 50000, "balance_cents": 50000, "created_at": _now(), "updated_at": _now()})
    await db.employees.insert_many([
        {"id": employee_id, "tenant_id": tenant_id, "name": "Alex Maker", "status": "active", "role_label": "Production"},
        {"id": other_employee_id, "tenant_id": tenant_id, "name": "Taylor Other", "status": "active", "role_label": "Production"},
    ])
    identity = await create_portal_identity(
        tenant_id=tenant_id, portal_type="employee", employee_id=employee_id,
        email=f"alex-{suffix}@example.com", full_name="Alex Maker",
    )

    item_ids = [f"item-{name}-{suffix}" for name in ["assigned", "ready", "hidden", "waiting", "done"]]
    await db.order_items.insert_many([
        {"id": item_ids[0], "tenant_id": tenant_id, "order_id": order_id, "description": "Lobby Banner", "category": "banners", "production_required": True, "unit_price_cents": 10000, "pricing_snapshot": {"unit_price_cents": 10000}},
        {"id": item_ids[1], "tenant_id": tenant_id, "order_id": order_id, "description": "Window Vinyl", "category": "vinyl", "production_required": True, "unit_price_cents": 20000, "pricing_snapshot": {"unit_price_cents": 20000}},
        {"id": item_ids[2], "tenant_id": tenant_id, "order_id": order_id, "description": "Hidden Task", "category": "vinyl", "production_required": True, "unit_price_cents": 30000, "pricing_snapshot": {"unit_price_cents": 30000}},
        {"id": item_ids[3], "tenant_id": tenant_id, "order_id": order_id, "description": "Waiting Panel", "category": "rigid", "production_required": True, "unit_price_cents": 40000, "pricing_snapshot": {"unit_price_cents": 40000}},
        {"id": item_ids[4], "tenant_id": tenant_id, "order_id": order_id, "description": "Completed Decal", "category": "decals", "production_required": True, "unit_price_cents": 50000, "pricing_snapshot": {"unit_price_cents": 50000}},
    ])
    wo_ids = [f"wo-{name}-{suffix}" for name in ["assigned", "ready", "hidden", "waiting", "done"]]
    await db.work_orders.insert_many([
        {"id": wo_ids[0], "tenant_id": tenant_id, "number": 9101, "order_id": order_id, "customer_id": customer_id, "production_status": "released", "priority": "rush", "due_date": _date(1), "current_version": True, "items_snapshot": [{"order_item_id": item_ids[0]}], "created_at": _now(), "updated_at": _now()},
        {"id": wo_ids[1], "tenant_id": tenant_id, "number": 9102, "order_id": order_id, "customer_id": customer_id, "production_status": "released", "priority": "normal", "due_date": _date(2), "current_version": True, "items_snapshot": [{"order_item_id": item_ids[1]}], "created_at": _now(), "updated_at": _now()},
        {"id": wo_ids[2], "tenant_id": tenant_id, "number": 9103, "order_id": order_id, "customer_id": customer_id, "production_status": "released", "priority": "normal", "due_date": _date(2), "current_version": True, "items_snapshot": [{"order_item_id": item_ids[2]}], "created_at": _now(), "updated_at": _now()},
        {"id": wo_ids[3], "tenant_id": tenant_id, "number": 9104, "order_id": order_id, "customer_id": customer_id, "production_status": "released", "priority": "normal", "due_date": _date(2), "current_version": True, "items_snapshot": [{"order_item_id": item_ids[3]}], "created_at": _now(), "updated_at": _now()},
        {"id": wo_ids[4], "tenant_id": tenant_id, "number": 9105, "order_id": order_id, "customer_id": customer_id, "production_status": "completed", "priority": "low", "due_date": _date(-1), "current_version": True, "items_snapshot": [{"order_item_id": item_ids[4]}], "created_at": _now(), "updated_at": _now()},
    ])
    instances = [_workflow_instance(tenant_id, order_id, item_ids[i], wo_ids[i]) for i in range(5)]
    await db.production_workflow_instances.insert_many(instances)
    assigned_stage = _stage(tenant_id, instances[0], "print", "Print", 1, assigned_employee_id=employee_id)
    ready_stage = _stage(tenant_id, instances[1], "cut", "Cut", 1)
    hidden_stage = _stage(tenant_id, instances[2], "hide", "Hidden", 1, assigned_employee_id=employee_id, employee_visible=False)
    waiting_stage = _stage(tenant_id, instances[3], "wait", "Wait", 1, "waiting", assigned_employee_id=employee_id, waiting_since=_now())
    done_stage = _stage(tenant_id, instances[4], "done", "Done", 1, "completed", assigned_employee_id=employee_id, completed_at=_now())
    await db.production_stage_instances.insert_many([assigned_stage, ready_stage, hidden_stage, waiting_stage, done_stage])

    yield {
        "tenant_id": tenant_id,
        "owner": owner,
        "viewer": viewer,
        "employee_id": employee_id,
        "identity_id": identity["id"],
        "order_id": order_id,
        "assigned_stage_id": assigned_stage["id"],
        "ready_stage_id": ready_stage["id"],
        "hidden_stage_id": hidden_stage["id"],
        "waiting_stage_id": waiting_stage["id"],
        "done_stage_id": done_stage["id"],
    }
    _clear()


async def _activate_and_identify(ctx) -> tuple[str, str]:
    async with await _client_as(ctx["owner"]) as c:
        cred = await c.post(f"/api/production-kiosk/employees/{ctx['employee_id']}/credential", json={"pin": "2468"})
        assert cred.status_code == 200, cred.text
        assert "kiosk_pin_hash" not in str(cred.json())
        activated = await c.post("/api/production-kiosk/sessions/activate", json={"device_label": "Shop Tablet"})
        assert activated.status_code == 200, activated.text
        device_token = activated.json()["device_token"]
        assert "device_token_hash" not in str(activated.json())
    async with await _kiosk_client(device_token) as c:
        identified = await c.post("/api/production-kiosk/identify", json={"employee_id": ctx["employee_id"], "pin": "2468"})
        assert identified.status_code == 200, identified.text
        employee_token = identified.json()["employee_token"]
        assert "kiosk_pin_hash" not in str(identified.json())
        assert "employee_session_token_hash" not in str(identified.json())
    return device_token, employee_token


@pytest.mark.asyncio
async def test_kiosk_device_activation_employee_pin_session_and_safe_work_contract(ctx):
    async with await _client_as(ctx["viewer"]) as c:
        denied = await c.post("/api/production-kiosk/sessions/activate", json={"device_label": "Viewer Tablet"})
        assert denied.status_code == 403

    async with await _client_as(ctx["owner"]) as c:
        config = await c.put("/api/production-kiosk/config", json={"shop_queue_visibility": "full_safe_production_queue", "customer_name_visible": False})
        assert config.status_code == 200

    device_token, employee_token = await _activate_and_identify(ctx)
    async with await _kiosk_client(device_token, employee_token) as c:
        work = await c.get("/api/production-kiosk/work")
        assert work.status_code == 200, work.text
        data = work.json()
        assigned_ids = {t["stage_id"] for t in data["assigned_tasks"]}
        assert ctx["assigned_stage_id"] in assigned_ids
        assert ctx["hidden_stage_id"] not in assigned_ids
        assert ctx["waiting_stage_id"] in {t["stage_id"] for t in data["blocked_waiting"]}
        assert ctx["done_stage_id"] in {t["stage_id"] for t in data["recently_completed_by_me"]}
        assert data["shop_queue_visibility"] == "full_safe_production_queue"
        assert ctx["ready_stage_id"] in {t["stage_id"] for t in data["shop_queue"]}
        assert data["assigned_tasks"][0]["customer_name"] is None
        forbidden = {"unit_price_cents", "pricing_snapshot", "hourly_rate_cents", "cost", "profit", "margin", "raw_storage_path", "device_token_hash", "employee_session_token_hash"}
        assert forbidden.isdisjoint(set(data["assigned_tasks"][0].keys()))


@pytest.mark.asyncio
async def test_kiosk_identification_rate_limits_and_session_switch_clears_employee(ctx):
    async with await _client_as(ctx["owner"]) as c:
        await c.post(f"/api/production-kiosk/employees/{ctx['employee_id']}/credential", json={"pin": "2468"})
        activated = await c.post("/api/production-kiosk/sessions/activate", json={"device_label": "Lock Tablet"})
        device_token = activated.json()["device_token"]

    async with await _kiosk_client(device_token) as c:
        last = None
        for _ in range(5):
            last = await c.post("/api/production-kiosk/identify", json={"employee_id": ctx["employee_id"], "pin": "0000"})
        assert last.status_code == 401
        locked = await c.post("/api/production-kiosk/identify", json={"employee_id": ctx["employee_id"], "pin": "2468"})
        assert locked.status_code == 429

    await db.production_kiosk_sessions.update_one({"tenant_id": ctx["tenant_id"]}, {"$set": {"identification_locked_until": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}})
    async with await _kiosk_client(device_token) as c:
        ok = await c.post("/api/production-kiosk/identify", json={"employee_id": ctx["employee_id"], "pin": "2468"})
        assert ok.status_code == 200
        end = await c.post("/api/production-kiosk/employee/end")
        assert end.status_code == 200
        assert "employee_id" not in end.json()["session"]


@pytest.mark.asyncio
async def test_kiosk_actions_reuse_stage_service_and_do_not_create_timer_or_commercial_records(ctx):
    device_token, employee_token = await _activate_and_identify(ctx)
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

    async with await _kiosk_client(device_token, employee_token) as c:
        start = await c.post(f"/api/production-kiosk/stages/{ctx['assigned_stage_id']}/start", json={})
        assert start.status_code == 200, start.text
        duplicate = await c.post(f"/api/production-kiosk/stages/{ctx['assigned_stage_id']}/start", json={})
        assert duplicate.status_code == 200
        block_missing_reason = await c.post(f"/api/production-kiosk/stages/{ctx['assigned_stage_id']}/block", json={})
        assert block_missing_reason.status_code == 400
        block = await c.post(f"/api/production-kiosk/stages/{ctx['assigned_stage_id']}/block", json={"reason": "Material missing"})
        assert block.status_code == 200
        resume = await c.post(f"/api/production-kiosk/stages/{ctx['assigned_stage_id']}/resume", json={})
        assert resume.status_code == 200
        note = await c.post(f"/api/production-kiosk/stages/{ctx['assigned_stage_id']}/notes", json={"note": "Checked print settings"})
        assert note.status_code == 200
        complete = await c.post(f"/api/production-kiosk/stages/{ctx['assigned_stage_id']}/complete", json={"completion_note": "Done"})
        assert complete.status_code == 200
        unassigned = await c.post(f"/api/production-kiosk/stages/{ctx['ready_stage_id']}/start", json={})
        assert unassigned.status_code == 403

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


@pytest.mark.asyncio
async def test_time_clock_panel_is_separate_from_stage_status(ctx):
    device_token, employee_token = await _activate_and_identify(ctx)
    async with await _kiosk_client(device_token, employee_token) as c:
        status = await c.get("/api/production-kiosk/time-clock")
        assert status.status_code == 200
        clock_in = await c.post("/api/production-kiosk/time-clock/clock-in", json={})
        assert clock_in.status_code == 200, clock_in.text
        stage_before = await db.production_stage_instances.find_one({"tenant_id": ctx["tenant_id"], "id": ctx["assigned_stage_id"]}, {"_id": 0})
        assert stage_before["status"] == "not_started"
        clock_out = await c.post("/api/production-kiosk/time-clock/clock-out", json={})
        assert clock_out.status_code == 200
        stage_after = await db.production_stage_instances.find_one({"tenant_id": ctx["tenant_id"], "id": ctx["assigned_stage_id"]}, {"_id": 0})
        assert stage_after["status"] == "not_started"
        assert await db.time_entries.count_documents({"tenant_id": ctx["tenant_id"], "source": "kiosk"}) == 1


@pytest.mark.asyncio
async def test_supervisor_override_is_action_specific_audited_and_one_time(ctx):
    device_token, employee_token = await _activate_and_identify(ctx)
    async with await _client_as(ctx["owner"]) as c:
        override = await c.post(
            "/api/production-kiosk/supervisor-overrides",
            headers={"X-Kiosk-Device-Token": device_token},
            json={"employee_id": ctx["employee_id"], "stage_id": ctx["ready_stage_id"], "action": "start", "reason": "Supervisor assigned at kiosk"},
        )
        assert override.status_code == 200, override.text
        token = override.json()["override_token"]
        assert "override_token_hash" not in str(override.json())

    async with await _kiosk_client(device_token, employee_token) as c:
        start = await c.post(f"/api/production-kiosk/stages/{ctx['ready_stage_id']}/start", json={"supervisor_override_token": token})
        assert start.status_code == 200, start.text
        reuse = await c.post(f"/api/production-kiosk/stages/{ctx['ready_stage_id']}/start", json={"supervisor_override_token": token})
        assert reuse.status_code == 403

    stage = await db.production_stage_instances.find_one({"tenant_id": ctx["tenant_id"], "id": ctx["ready_stage_id"]}, {"_id": 0})
    assert stage["assigned_employee_id"] == ctx["employee_id"]
    actions = {a["action"] async for a in db.audit_events.find({"tenant_id": ctx["tenant_id"]}, {"_id": 0, "action": 1})}
    assert "production_kiosk.supervisor_override_created" in actions
    assert "production_kiosk.supervisor_override_consumed" in actions


@pytest.mark.asyncio
async def test_revoked_device_and_expired_employee_session_are_denied(ctx):
    device_token, employee_token = await _activate_and_identify(ctx)
    await db.production_kiosk_sessions.update_one(
        {"tenant_id": ctx["tenant_id"]},
        {"$set": {"employee_session_expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}},
    )
    async with await _kiosk_client(device_token, employee_token) as c:
        expired = await c.get("/api/production-kiosk/work")
        assert expired.status_code == 401

    device_token, employee_token = await _activate_and_identify(ctx)
    session = await db.production_kiosk_sessions.find_one({"tenant_id": ctx["tenant_id"], "status": "active"}, {"_id": 0}, sort=[("activated_at", -1)])
    async with await _client_as(ctx["owner"]) as c:
        revoked = await c.post(f"/api/production-kiosk/sessions/{session['id']}/revoke", json={"reason": "Lost tablet"})
        assert revoked.status_code == 200
    async with await _kiosk_client(device_token, employee_token) as c:
        denied = await c.get("/api/production-kiosk/work")
        assert denied.status_code == 401
