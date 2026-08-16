"""Shop Operations Batch 5 - production timing and item flow."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.deps import get_current_user
from server import app


def _now(offset_seconds: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)).isoformat()


def _override(user: dict):
    async def _get():
        return {**user}

    return _get


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


def _workflow_instance(tenant_id: str, order_id: str, item_id: str, wo_id: str, suffix: str) -> dict:
    return {
        "id": f"wfi-{item_id}",
        "tenant_id": tenant_id,
        "order_id": order_id,
        "order_item_id": item_id,
        "work_order_id": wo_id,
        "source_workflow_id": f"wf-{suffix}",
        "source_workflow_version": 1,
        "source_type": "tenant_default",
        "source_name": "Production Flow",
        "resolution_source": "tenant_default",
        "status": "active",
        "stage_definitions": [
            {"stage_key": "print", "display_name": "Print", "sequence": 1, "default_estimated_duration_minutes": 30}
        ],
        "created_by_user_id": "seed",
        "created_at": _now(),
        "updated_at": _now(),
    }


def _stage(tenant_id: str, instance: dict, suffix: str, *, assigned_employee_id: str | None = None) -> dict:
    return {
        "id": f"stage-{instance['order_item_id']}-{suffix}",
        "tenant_id": tenant_id,
        "workflow_instance_id": instance["id"],
        "order_id": instance["order_id"],
        "order_item_id": instance["order_item_id"],
        "work_order_id": instance["work_order_id"],
        "stage_key": "print",
        "stage_name": "Print",
        "sequence": 1,
        "required": True,
        "may_skip": False,
        "requires_reason_to_skip": False,
        "status": "not_started",
        "assigned_employee_id": assigned_employee_id,
        "assigned_user_id": None,
        "assigned_role": "Production",
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
        "created_at": _now(),
        "updated_at": _now(),
    }


@pytest_asyncio.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-prod-time-{suffix}"
    other_tenant_id = f"t-prod-time-other-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "full_name": "Owner", "role": "owner", "password_hash": "x", "is_active": True}
    financial_user = {"id": f"fin-{suffix}", "tenant_id": tenant_id, "email": f"fin-{suffix}@example.com", "role": "staff", "permissions": ["work_order:read", "invoice:read"], "is_active": True}
    production_user = {"id": f"prod-{suffix}", "tenant_id": tenant_id, "email": f"prod-{suffix}@example.com", "role": "staff", "permissions": ["work_order:read", "work_order:write"], "is_active": True}
    pricing_manager = {"id": f"pricing-{suffix}", "tenant_id": tenant_id, "email": f"pricing-{suffix}@example.com", "role": "owner", "permissions": ["work_order:read", "work_order:write", "pricing:read", "pricing:write"], "is_active": True}
    other_prod_user = {"id": f"other-prod-{suffix}", "tenant_id": tenant_id, "email": f"other-prod-{suffix}@example.com", "role": "staff", "permissions": ["work_order:read", "work_order:write"], "is_active": True}
    other_owner = {"id": f"other-owner-{suffix}", "tenant_id": other_tenant_id, "email": f"other-owner-{suffix}@example.com", "role": "owner", "is_active": True}
    employee_id = f"emp-{suffix}"
    pricing_employee_id = f"emp-pricing-{suffix}"
    other_employee_id = f"emp-other-{suffix}"
    customer_id = f"cust-{suffix}"
    order_id = f"order-{suffix}"
    wo_id = f"wo-{suffix}"
    item_ids = [f"item-a-{suffix}", f"item-b-{suffix}"]

    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "Tenant"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Other"},
    ])
    await db.users.insert_many([owner, financial_user, production_user, pricing_manager, other_prod_user, other_owner])
    await db.employees.insert_many([
        {"id": employee_id, "tenant_id": tenant_id, "name": "Alex Maker", "linked_user_id": production_user["id"], "status": "active", "role_label": "Production"},
        {"id": pricing_employee_id, "tenant_id": tenant_id, "name": "Priya Manager", "linked_user_id": pricing_manager["id"], "status": "active", "role_label": "Production Manager"},
        {"id": other_employee_id, "tenant_id": tenant_id, "name": "Blair Maker", "linked_user_id": other_prod_user["id"], "status": "active", "role_label": "Production"},
    ])
    await db.customers.insert_one({"id": customer_id, "tenant_id": tenant_id, "name": "Acme"})
    await db.orders.insert_one({"id": order_id, "tenant_id": tenant_id, "number": 901, "customer_id": customer_id, "status": "in_production", "created_at": _now(), "updated_at": _now()})
    await db.order_items.insert_many([
        {"id": item_ids[0], "tenant_id": tenant_id, "order_id": order_id, "description": "Banner", "category": "banners", "width_inches": 120, "height_inches": 60, "quantity": 1, "production_required": True, "unit_price_cents": 5000, "line_total_cents": 5000, "pricing_snapshot": {"unit_price_cents": 5000, "category": "banners"}},
        {"id": item_ids[1], "tenant_id": tenant_id, "order_id": order_id, "description": "Panel", "category": "unknown_custom", "quantity": 1, "production_required": True, "unit_price_cents": 7000, "line_total_cents": 7000, "pricing_snapshot": {"unit_price_cents": 7000, "category": "unknown_custom"}},
    ])
    await db.work_orders.insert_one({
        "id": wo_id,
        "tenant_id": tenant_id,
        "number": 9101,
        "order_id": order_id,
        "customer_id": customer_id,
        "production_status": "queued",
        "current_version": True,
        "items_snapshot": [
            {"order_item_id": item_ids[0], "description": "Banner", "category": "banners", "width_inches": 120, "height_inches": 60, "quantity": 1, "unit_price_cents": 5000, "pricing_snapshot": {"unit_price_cents": 5000, "category": "banners"}},
            {"order_item_id": item_ids[1], "description": "Panel", "category": "unknown_custom", "quantity": 1, "unit_price_cents": 7000, "pricing_snapshot": {"unit_price_cents": 7000, "category": "unknown_custom"}},
        ],
        "created_at": _now(),
        "updated_at": _now(),
    })
    instances = [_workflow_instance(tenant_id, order_id, item_id, wo_id, suffix) for item_id in item_ids]
    await db.production_workflow_instances.insert_many(instances)
    stages = [_stage(tenant_id, instances[0], suffix, assigned_employee_id=employee_id), _stage(tenant_id, instances[1], suffix)]
    await db.production_stage_instances.insert_many(stages)

    other_instance = _workflow_instance(other_tenant_id, f"order-other-{suffix}", f"item-other-{suffix}", f"wo-other-{suffix}", suffix)
    other_stage = _stage(other_tenant_id, other_instance, suffix)
    await db.production_workflow_instances.insert_one(other_instance)
    await db.production_stage_instances.insert_one(other_stage)

    yield {
        "tenant_id": tenant_id,
        "owner": owner,
        "financial_user": financial_user,
        "production_user": production_user,
        "pricing_manager": pricing_manager,
        "other_prod_user": other_prod_user,
        "other_owner": other_owner,
        "employee_id": employee_id,
        "order_id": order_id,
        "wo_id": wo_id,
        "item_ids": item_ids,
        "stages": stages,
        "other_stage_id": other_stage["id"],
    }
    _clear()


@pytest.mark.asyncio
async def test_work_order_detail_financials_are_backend_restricted_for_production_users(ctx):
    async with await _client_as(ctx["production_user"]) as c:
        res = await c.get(f"/api/work-orders/{ctx['wo_id']}")
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["financials_restricted"] is True
        assert "unit_price_cents" not in body["items_snapshot"][0]
        assert "pricing_snapshot" not in body["items_snapshot"][0]
        summary = await c.get(f"/api/work-orders/{ctx['wo_id']}/summary")
        assert summary.status_code == 200, summary.text
        assert "unit_price_cents" not in summary.json()["items"][0]

    async with await _client_as(ctx["financial_user"]) as c:
        res = await c.get(f"/api/work-orders/{ctx['wo_id']}")
        assert res.status_code == 200, res.text
        assert res.json()["items_snapshot"][0]["unit_price_cents"] == 5000


@pytest.mark.asyncio
async def test_stage_timers_are_owned_paused_audited_idempotent_and_do_not_touch_payroll(ctx, monkeypatch):
    import app.services.production_stage_service as stage_service

    stage_id = ctx["stages"][0]["id"]
    before_payroll = await db.payroll_transactions.count_documents({"tenant_id": ctx["tenant_id"]})
    current_time = {"value": "2026-08-16T10:00:00+00:00"}
    monkeypatch.setattr(stage_service, "_now", lambda: current_time["value"])

    async with await _client_as(ctx["production_user"]) as c:
        started = await c.post(f"/api/production-stages/{stage_id}/timer/start", json={"idempotency_key": "key-1", "notes": "Started print"})
        assert started.status_code == 200, started.text
        session = started.json()
        assert session["status"] == "active"
        assert session["employee_id"] == ctx["employee_id"]

        again = await c.post(f"/api/production-stages/{stage_id}/timer/start", json={"idempotency_key": "key-1"})
        assert again.status_code == 200, again.text
        assert again.json()["id"] == session["id"]
        assert await db.production_timer_sessions.count_documents({"tenant_id": ctx["tenant_id"], "stage_id": stage_id}) == 1

        current_time["value"] = "2026-08-16T10:05:00+00:00"
        paused = await c.post(f"/api/production-stages/{stage_id}/timer/pause", json={"session_id": session["id"], "reason": "Material check"})
        assert paused.status_code == 200, paused.text
        assert paused.json()["status"] == "paused"
        again_paused = await c.post(f"/api/production-stages/{stage_id}/timer/pause", json={"session_id": session["id"], "reason": "Retry"})
        assert again_paused.status_code == 200, again_paused.text
        assert again_paused.json()["status"] == "paused"

        current_time["value"] = "2026-08-16T10:20:00+00:00"
        resumed = await c.post(f"/api/production-stages/{stage_id}/timer/resume", json={"session_id": session["id"]})
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["status"] == "active"

    async with await _client_as(ctx["other_prod_user"]) as c:
        blocked = await c.post(f"/api/production-stages/{stage_id}/timer/stop", json={"session_id": session["id"]})
        assert blocked.status_code == 403, blocked.text

    async with await _client_as(ctx["owner"]) as c:
        current_time["value"] = "2026-08-16T10:30:00+00:00"
        stopped = await c.post(f"/api/production-stages/{stage_id}/timer/stop", json={"session_id": session["id"], "interruption_reason": "Manager check-in"})
        assert stopped.status_code == 200, stopped.text
        stopped_body = stopped.json()
        assert stopped_body["status"] == "completed"
        assert stopped_body["elapsed_seconds"] == 1800
        assert stopped_body["paused_duration_seconds"] == 900
        assert stopped_body["effective_elapsed_seconds"] == 900
        stages = await c.get(f"/api/work-orders/{ctx['wo_id']}/stages")
        assert stages.status_code == 200, stages.text
        stage = next(s for s in stages.json()["stages"] if s["id"] == stage_id)
        assert stage["active_timer"] is None
        assert stage["timing_entry_count"] == 1
        assert stage["actual_duration_seconds"] == 900
        assert stage["default_estimated_duration_minutes"] == 30

    events = [e async for e in db.production_timer_events.find({"tenant_id": ctx["tenant_id"], "stage_id": stage_id}, {"_id": 0})]
    assert {e["event_type"] for e in events} == {"started", "paused", "resumed", "stopped"}
    audits = [a async for a in db.audit_events.find({"tenant_id": ctx["tenant_id"], "entity_id": stage_id}, {"_id": 0})]
    assert {"production_stage.timer_started", "production_stage.timer_paused", "production_stage.timer_resumed", "production_stage.timer_stopped"}.issubset({a["action"] for a in audits})
    assert await db.payroll_transactions.count_documents({"tenant_id": ctx["tenant_id"]}) == before_payroll


@pytest.mark.asyncio
async def test_timer_corrections_voids_and_pricing_feedback_are_manager_controlled(ctx, monkeypatch):
    import app.services.production_stage_service as stage_service

    current_time = {"value": "2026-08-16T11:00:00+00:00"}
    monkeypatch.setattr(stage_service, "_now", lambda: current_time["value"])
    stage_id = ctx["stages"][0]["id"]

    async with await _client_as(ctx["production_user"]) as c:
        started = await c.post(f"/api/production-stages/{stage_id}/timer/start")
        assert started.status_code == 200, started.text
        session_id = started.json()["id"]
        current_time["value"] = "2026-08-16T11:30:00+00:00"
        stopped = await c.post(f"/api/production-stages/{stage_id}/timer/stop", json={"session_id": session_id})
        assert stopped.status_code == 200, stopped.text
        denied = await c.post(f"/api/production-stages/{stage_id}/timer/correct", json={"session_id": session_id, "corrected_elapsed_seconds": 1200, "reason": "Reviewed"})
        assert denied.status_code == 403, denied.text
        denied_feedback = await c.post(f"/api/production-stages/{stage_id}/pricing-feedback")
        assert denied_feedback.status_code == 403, denied_feedback.text

    async with await _client_as(ctx["owner"]) as c:
        corrected = await c.post(f"/api/production-stages/{stage_id}/timer/correct", json={"session_id": session_id, "corrected_elapsed_seconds": 1200, "reason": "Removed setup wait"})
        assert corrected.status_code == 200, corrected.text
        assert corrected.json()["corrected_elapsed_seconds"] == 1200
        repeated = await c.post(f"/api/production-stages/{stage_id}/timer/correct", json={"session_id": session_id, "corrected_elapsed_seconds": 1100, "reason": "Retry"})
        assert repeated.status_code == 409, repeated.text

    async with await _client_as(ctx["pricing_manager"]) as c:
        feedback = await c.post(f"/api/production-stages/{stage_id}/pricing-feedback")
        assert feedback.status_code == 200, feedback.text
        feedback_body = feedback.json()
        assert feedback_body["status"] == "pending"
        assert feedback_body["mapped"] is True
        assert feedback_body["effective_actual_seconds"] == 1200
        duplicate = await c.post(f"/api/production-stages/{stage_id}/pricing-feedback")
        assert duplicate.status_code == 200, duplicate.text
        assert duplicate.json()["id"] == feedback_body["id"]
        approved = await c.post(f"/api/production/pricing-feedback/{feedback_body['id']}/approve", json={"approved_value": feedback_body["suggested_value"], "reason": "Use measured output"})
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved"

        unmapped_stage_id = ctx["stages"][1]["id"]
        current_time["value"] = "2026-08-16T12:00:00+00:00"
        unmapped_start = await c.post(f"/api/production-stages/{unmapped_stage_id}/timer/start")
        assert unmapped_start.status_code == 200, unmapped_start.text
        current_time["value"] = "2026-08-16T12:20:00+00:00"
        unmapped_stop = await c.post(f"/api/production-stages/{unmapped_stage_id}/timer/stop", json={"session_id": unmapped_start.json()["id"]})
        assert unmapped_stop.status_code == 200, unmapped_stop.text
        unmapped_feedback = await c.post(f"/api/production-stages/{unmapped_stage_id}/pricing-feedback")
        assert unmapped_feedback.status_code == 200, unmapped_feedback.text
        assert unmapped_feedback.json()["status"] == "unmapped"
        rejected = await c.post(f"/api/production/pricing-feedback/{unmapped_feedback.json()['id']}/reject", json={"reason": "No safe pricing field"})
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["status"] == "rejected"

    async with await _client_as(ctx["owner"]) as c:
        voided = await c.post(f"/api/production-stages/{stage_id}/timer/void", json={"session_id": session_id, "reason": "Duplicate entry", "confirm": True})
        assert voided.status_code == 200, voided.text
        assert voided.json()["status"] == "voided"
        stages = await c.get(f"/api/work-orders/{ctx['wo_id']}/stages")
        assert stages.status_code == 200, stages.text
        stage = next(s for s in stages.json()["stages"] if s["id"] == stage_id)
        assert stage["actual_duration_seconds"] == 0
        assert stage["timing_entry_count"] == 0

    audits = [a["action"] async for a in db.audit_events.find({"tenant_id": ctx["tenant_id"]}, {"_id": 0, "action": 1})]
    assert "production_stage.timer_corrected" in audits
    assert "production_stage.timer_voided" in audits
    assert "production_pricing_feedback.approved" in audits
    assert "production_pricing_feedback.rejected" in audits


@pytest.mark.asyncio
async def test_item_stage_completion_derives_work_order_and_order_production_state(ctx):
    async with await _client_as(ctx["owner"]) as c:
        for index, stage in enumerate(ctx["stages"]):
            start = await c.post(f"/api/production-stages/{stage['id']}/start")
            assert start.status_code == 200, start.text
            complete = await c.post(f"/api/production-stages/{stage['id']}/complete", json={"completion_note": f"done {index}"})
            assert complete.status_code == 200, complete.text
            wo = await db.work_orders.find_one({"tenant_id": ctx["tenant_id"], "id": ctx["wo_id"]}, {"_id": 0})
            order = await db.orders.find_one({"tenant_id": ctx["tenant_id"], "id": ctx["order_id"]}, {"_id": 0})
            if index == 0:
                assert wo["production_status"] == "queued"
                assert order["status"] == "in_production"
            else:
                assert wo["production_status"] == "ready"
                assert order["status"] == "ready"
                assert order["production_state"] == "ready"

        items = [i async for i in db.order_items.find({"tenant_id": ctx["tenant_id"], "order_id": ctx["order_id"]}, {"_id": 0})]
        assert {i["production_status"] for i in items} == {"completed"}
        assert all(i.get("current_production_stage_id") is None for i in items)


@pytest.mark.asyncio
async def test_timer_routes_remain_tenant_isolated(ctx):
    async with await _client_as(ctx["owner"]) as c:
        missing = await c.post(f"/api/production-stages/{ctx['other_stage_id']}/timer/start")
        assert missing.status_code == 404, missing.text
