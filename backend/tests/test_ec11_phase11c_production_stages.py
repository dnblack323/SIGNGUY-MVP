"""EC11 Phase 11C - Work Order and Order Item production stage integration."""
from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.security import create_access_token
from app.deps import get_current_user
from server import app


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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest_asyncio.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-ec11c-{suffix}"
    other_tenant_id = f"t-ec11c-other-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "full_name": "Owner", "role": "owner", "password_hash": "x", "is_active": True}
    staff = {"id": f"staff-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "full_name": "Staff", "role": "staff", "password_hash": "x", "is_active": True}
    readonly = {"id": f"read-{suffix}", "tenant_id": tenant_id, "email": f"read-{suffix}@example.com", "full_name": "Read", "role": "viewer", "password_hash": "x", "is_active": True}
    other_owner = {"id": f"owner-other-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "full_name": "Other", "role": "owner", "password_hash": "x", "is_active": True}
    user_for_employee = {"id": f"emp-user-{suffix}", "tenant_id": tenant_id, "email": f"emp-user-{suffix}@example.com", "full_name": "Employee User", "role": "staff", "password_hash": "x", "is_active": True}
    user_for_warning = {"id": f"warn-user-{suffix}", "tenant_id": tenant_id, "email": f"warn-user-{suffix}@example.com", "full_name": "Warning User", "role": "staff", "password_hash": "x", "is_active": True}
    other_emp_user = {"id": f"other-emp-user-{suffix}", "tenant_id": other_tenant_id, "email": f"other-emp-{suffix}@example.com", "full_name": "Other Employee", "role": "staff", "password_hash": "x", "is_active": True}

    customer_id = f"cust-{suffix}"
    order_id = f"order-{suffix}"
    item_a = f"item-a-{suffix}"
    item_b = f"item-b-{suffix}"
    item_default = f"item-default-{suffix}"
    item_np = f"item-np-{suffix}"
    wo_id = f"wo-{suffix}"
    employee_id = f"emp-{suffix}"
    inactive_employee_id = f"emp-inactive-{suffix}"
    warning_employee_id = f"emp-warning-{suffix}"
    other_employee_id = f"emp-other-{suffix}"
    hard_equipment_id = f"eq-hard-{suffix}"
    warning_equipment_id = f"eq-warning-{suffix}"

    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "Tenant A"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Tenant B"},
    ])
    await db.users.insert_many([owner, staff, readonly, other_owner, user_for_employee, user_for_warning, other_emp_user])
    await db.customers.insert_one({"id": customer_id, "tenant_id": tenant_id, "name": "Customer"})
    await db.orders.insert_one({
        "id": order_id, "tenant_id": tenant_id, "number": 5101, "customer_id": customer_id,
        "job_name": "Stage job", "title": "Stage job", "status": "confirmed",
        "subtotal_cents": 20000, "total_cents": 20000, "balance_cents": 20000,
        "created_by": owner["id"], "created_at": _now(), "updated_at": _now(),
    })
    await db.order_items.insert_many([
        {
            "id": item_a, "tenant_id": tenant_id, "order_id": order_id, "position": 0,
            "description": "Banner", "category": "banners", "quantity": 1, "unit_price_cents": 10000,
            "line_total_cents": 10000, "production_required": True,
            "pricing_snapshot": {"unit_price_cents": 10000}, "created_at": _now(), "updated_at": _now(),
        },
        {
            "id": item_b, "tenant_id": tenant_id, "order_id": order_id, "position": 1,
            "description": "Panel", "category": "rigid_signs", "quantity": 1, "unit_price_cents": 10000,
            "line_total_cents": 10000, "production_required": True,
            "pricing_snapshot": {"unit_price_cents": 10000}, "created_at": _now(), "updated_at": _now(),
        },
        {
            "id": item_default, "tenant_id": tenant_id, "order_id": order_id, "position": 2,
            "description": "Unknown production item", "category": "unknown", "quantity": 1, "unit_price_cents": 5000,
            "line_total_cents": 5000, "production_required": True,
            "pricing_snapshot": {"unit_price_cents": 5000}, "created_at": _now(), "updated_at": _now(),
        },
        {
            "id": item_np, "tenant_id": tenant_id, "order_id": order_id, "position": 3,
            "description": "Design service", "category": "services", "quantity": 1, "unit_price_cents": 2500,
            "line_total_cents": 2500, "production_required": False,
            "pricing_snapshot": {"unit_price_cents": 2500}, "created_at": _now(), "updated_at": _now(),
        },
    ])
    await db.work_orders.insert_one({
        "id": wo_id, "tenant_id": tenant_id, "number": 6101, "order_id": order_id,
        "customer_id": customer_id, "production_status": "released", "priority": "normal",
        "items_snapshot": [
            {"order_item_id": item_a, "description": "Banner", "quantity": 1},
            {"order_item_id": item_b, "description": "Panel", "quantity": 1},
            {"order_item_id": item_default, "description": "Unknown production item", "quantity": 1},
            {"order_item_id": item_np, "description": "Design service", "quantity": 1},
        ],
        "created_by": owner["id"], "created_at": _now(), "updated_at": _now(),
    })
    await db.employees.insert_many([
        {"id": employee_id, "tenant_id": tenant_id, "name": "Active Employee", "linked_user_id": user_for_employee["id"], "status": "active", "role_label": "Production"},
        {"id": inactive_employee_id, "tenant_id": tenant_id, "name": "Inactive Employee", "linked_user_id": f"inactive-user-{suffix}", "status": "inactive"},
        {"id": warning_employee_id, "tenant_id": tenant_id, "name": "Warning Employee", "linked_user_id": user_for_warning["id"], "status": "active"},
        {"id": other_employee_id, "tenant_id": other_tenant_id, "name": "Other Employee", "linked_user_id": other_emp_user["id"], "status": "active"},
    ])
    await db.equipment.insert_many([
        {"id": hard_equipment_id, "tenant_id": tenant_id, "name": "Hard Cutter", "access_policy": "required_no_override", "status": "active"},
        {"id": warning_equipment_id, "tenant_id": tenant_id, "name": "Warning Printer", "access_policy": "required_override_allowed", "status": "active"},
    ])

    yield {
        "tenant_id": tenant_id,
        "other_tenant_id": other_tenant_id,
        "owner": owner,
        "staff": staff,
        "readonly": readonly,
        "other_owner": other_owner,
        "order_id": order_id,
        "item_a": item_a,
        "item_b": item_b,
        "item_default": item_default,
        "item_np": item_np,
        "wo_id": wo_id,
        "employee_id": employee_id,
        "inactive_employee_id": inactive_employee_id,
        "warning_employee_id": warning_employee_id,
        "other_employee_id": other_employee_id,
        "hard_equipment_id": hard_equipment_id,
        "warning_equipment_id": warning_equipment_id,
    }
    _clear()


async def _create_workflow(c: AsyncClient, name: str, key: str, stages: list[dict], categories: list[str] | None = None) -> dict:
    res = await c.post("/api/production-workflows", json={"name": name, "workflow_key": key, "stages": stages})
    assert res.status_code == 201, res.text
    workflow = res.json()
    if categories:
        assigned = await c.post(f"/api/production-workflows/{workflow['id']}/assign-category", json={"category_ids": categories})
        assert assigned.status_code == 200, assigned.text
        workflow = assigned.json()
    return workflow


@pytest.mark.asyncio
async def test_workflow_generation_override_snapshot_idempotency_and_no_commercial_mutation(ctx):
    async with await _client_as(ctx["owner"]) as c:
        category_wf = await _create_workflow(c, "Banner Flow", f"banner_flow_{uuid.uuid4().hex[:6]}", [
            {"stage_key": "design", "display_name": "Design", "sequence": 1, "may_skip": False},
            {"stage_key": "proof_gate", "display_name": "Proof Gate", "sequence": 2, "proof_gate_type": "approval_required", "may_skip": False},
            {"stage_key": "finish", "display_name": "Finish", "sequence": 3, "may_skip": True, "requires_reason_to_skip": True},
        ], ["banners"])
        override_wf = await _create_workflow(c, "Override Flow", f"override_flow_{uuid.uuid4().hex[:6]}", [
            {"stage_key": "custom_prep", "display_name": "Custom Prep", "sequence": 1},
            {"stage_key": "custom_done", "display_name": "Custom Done", "sequence": 2, "may_skip": True},
        ])
        await _create_workflow(c, "Default Flow", f"default_flow_{uuid.uuid4().hex[:6]}", [
            {"stage_key": "default_stage", "display_name": "Default Stage", "sequence": 1},
        ])
        await c.post(f"/api/production-workflows/{category_wf['id']}/set-default")

        preview = await c.get(f"/api/orders/{ctx['order_id']}/items/{ctx['item_a']}/production-workflow-preview")
        assert preview.status_code == 200
        assert preview.json()["source"] == "category"

        override = await c.post(
            f"/api/orders/{ctx['order_id']}/items/{ctx['item_b']}/production-workflow-override",
            json={
                "workflow_id": override_wf["id"],
                "stages": [
                    {**override_wf["stages"][0], "display_name": "Frozen Prep", "sequence": 1},
                    {**override_wf["stages"][1], "display_name": "Frozen Done", "sequence": 2},
                ],
            },
        )
        assert override.status_code == 200, override.text

        before_order = await db.orders.find_one({"id": ctx["order_id"]}, {"_id": 0})
        before_item = await db.order_items.find_one({"id": ctx["item_a"]}, {"_id": 0})
        before_snapshot_count = await db.pricing_snapshot_records.count_documents({"tenant_id": ctx["tenant_id"]})

        generated = await c.post(f"/api/work-orders/{ctx['wo_id']}/stages/generate")
        assert generated.status_code == 200, generated.text
        body = generated.json()
        assert len(body["workflow_instances"]) == 3
        assert any(s["reason"] == "non_production_or_archived" for s in body["skipped"])
        assert {i["resolution_source"] for i in body["workflow_instances"]} == {"category", "order_item_override", "tenant_default"}
        assert {s["stage_name"] for s in body["stages"]} >= {"Design", "Proof Gate", "Finish", "Frozen Prep", "Frozen Done"}

        again = await c.post(f"/api/work-orders/{ctx['wo_id']}/stages/generate")
        assert again.status_code == 200
        assert again.json()["stages"] == []
        assert await db.production_workflow_instances.count_documents({"tenant_id": ctx["tenant_id"], "work_order_id": ctx["wo_id"]}) == 3
        persisted_stages = [
            s async for s in db.production_stage_instances.find(
                {"tenant_id": ctx["tenant_id"], "work_order_id": ctx["wo_id"]},
                {"_id": 0, "workflow_instance_id": 1, "stage_key": 1},
            )
        ]
        assert len(persisted_stages) == len(body["stages"])
        assert len({(s["workflow_instance_id"], s["stage_key"]) for s in persisted_stages}) == len(persisted_stages)

        await db.production_workflows.update_one({"id": category_wf["id"]}, {"$set": {"stages.0.display_name": "Edited Template Name"}})
        listed = await c.get(f"/api/work-orders/{ctx['wo_id']}/stages")
        assert listed.status_code == 200
        assert "Design" in {s["stage_name"] for s in listed.json()["stages"]}
        assert "Edited Template Name" not in {s["stage_name"] for s in listed.json()["stages"]}

        locked = await c.post(
            f"/api/orders/{ctx['order_id']}/items/{ctx['item_b']}/production-workflow-override",
            json={"workflow_id": override_wf["id"]},
        )
        assert locked.status_code == 400

        after_order = await db.orders.find_one({"id": ctx["order_id"]}, {"_id": 0})
        after_item = await db.order_items.find_one({"id": ctx["item_a"]}, {"_id": 0})
        assert after_order["total_cents"] == before_order["total_cents"]
        assert after_order["balance_cents"] == before_order["balance_cents"]
        assert after_item["unit_price_cents"] == before_item["unit_price_cents"]
        assert after_item["pricing_snapshot"] == before_item["pricing_snapshot"]
        assert await db.pricing_snapshot_records.count_documents({"tenant_id": ctx["tenant_id"]}) == before_snapshot_count


@pytest.mark.asyncio
async def test_stage_lifecycle_gates_reopen_assignment_and_timeline(ctx):
    async with await _client_as(ctx["owner"]) as c:
        workflow = await _create_workflow(c, "Lifecycle Flow", f"lifecycle_flow_{uuid.uuid4().hex[:6]}", [
            {"stage_key": "design", "display_name": "Design", "sequence": 1, "may_skip": False},
            {"stage_key": "proof_gate", "display_name": "Proof Gate", "sequence": 2, "proof_gate_type": "approval_required", "may_skip": False},
            {"stage_key": "finish", "display_name": "Finish", "sequence": 3, "may_skip": True, "requires_reason_to_skip": True},
            {"stage_key": "hard_eq", "display_name": "Hard Equipment", "sequence": 4, "may_skip": False, "equipment_requirement_ids": [ctx["hard_equipment_id"]]},
            {"stage_key": "warn_eq", "display_name": "Warning Equipment", "sequence": 5, "equipment_requirement_ids": [ctx["warning_equipment_id"]]},
        ], ["banners"])
        await c.post(f"/api/production-workflows/{workflow['id']}/set-default")
        generated = await c.post(f"/api/work-orders/{ctx['wo_id']}/stages/generate")
        assert generated.status_code == 200, generated.text
        stages = (await c.get(f"/api/work-orders/{ctx['wo_id']}/stages")).json()["stages"]
        by_key = {s["stage_key"]: s for s in stages if s["order_item_id"] == ctx["item_a"]}

        blocked_by_prior = await c.post(f"/api/production-stages/{by_key['proof_gate']['id']}/start")
        assert blocked_by_prior.status_code == 409

        start = await c.post(f"/api/production-stages/{by_key['design']['id']}/start")
        assert start.status_code == 200
        wait = await c.post(f"/api/production-stages/{by_key['design']['id']}/wait", json={})
        assert wait.status_code == 200
        resume = await c.post(f"/api/production-stages/{by_key['design']['id']}/resume")
        assert resume.status_code == 200
        no_reason_block = await c.post(f"/api/production-stages/{by_key['design']['id']}/block", json={})
        assert no_reason_block.status_code == 400
        block = await c.post(f"/api/production-stages/{by_key['design']['id']}/block", json={"reason": "Waiting for material"})
        assert block.status_code == 200
        resume2 = await c.post(f"/api/production-stages/{by_key['design']['id']}/resume")
        assert resume2.status_code == 200
        complete = await c.post(f"/api/production-stages/{by_key['design']['id']}/complete", json={"completion_note": "Design ready"})
        assert complete.status_code == 200

        await c.post(f"/api/production-stages/{by_key['proof_gate']['id']}/start")
        gate_blocked = await c.post(f"/api/production-stages/{by_key['proof_gate']['id']}/complete", json={})
        assert gate_blocked.status_code == 409
        proof_id = f"proof-{uuid.uuid4().hex}"
        await db.proofs.insert_one({
            "id": proof_id, "tenant_id": ctx["tenant_id"], "number": 7101,
            "parent_type": "order_item", "parent_id": ctx["item_a"], "status": "approved",
            "title": "Approved proof", "created_at": _now(), "updated_at": _now(),
        })
        gate_ok = await c.post(f"/api/production-stages/{by_key['proof_gate']['id']}/complete", json={})
        assert gate_ok.status_code == 200

        skip_disallowed = await c.post(f"/api/production-stages/{by_key['hard_eq']['id']}/skip", json={"reason": "No"})
        assert skip_disallowed.status_code == 400
        finish_start = await c.post(f"/api/production-stages/{by_key['finish']['id']}/start")
        assert finish_start.status_code == 200
        skip_needs_reason = await c.post(f"/api/production-stages/{by_key['finish']['id']}/skip", json={})
        assert skip_needs_reason.status_code == 400
        skip_ok = await c.post(f"/api/production-stages/{by_key['finish']['id']}/skip", json={"reason": "Customer waived finish"})
        assert skip_ok.status_code == 200
        reopen_no_reason = await c.post(f"/api/production-stages/{by_key['finish']['id']}/reopen", json={})
        assert reopen_no_reason.status_code == 400

    async with await _client_as(ctx["staff"]) as c:
        staff_reopen = await c.post(f"/api/production-stages/{by_key['finish']['id']}/reopen", json={"reason": "Need it"})
        assert staff_reopen.status_code == 403

    async with await _client_as(ctx["owner"]) as c:
        reopen_skip = await c.post(f"/api/production-stages/{by_key['finish']['id']}/reopen", json={"reason": "Need finish after all"})
        assert reopen_skip.status_code == 200
        reopen_complete = await c.post(f"/api/production-stages/{by_key['design']['id']}/reopen", json={"reason": "Design changed"})
        assert reopen_complete.status_code == 200
        due = await c.patch(f"/api/production-stages/{by_key['design']['id']}/due-date", json={"due_at": "2026-07-20"})
        assert due.status_code == 200
        note = await c.post(f"/api/production-stages/{by_key['design']['id']}/notes", json={"note": "Use matte laminate"})
        assert note.status_code == 200

        inactive = await c.post(f"/api/production-stages/{by_key['design']['id']}/assign", json={"employee_id": ctx["inactive_employee_id"]})
        assert inactive.status_code == 400
        cross_tenant = await c.post(f"/api/production-stages/{by_key['design']['id']}/assign", json={"employee_id": ctx["other_employee_id"]})
        assert cross_tenant.status_code == 404
        valid = await c.post(f"/api/production-stages/{by_key['design']['id']}/assign", json={"employee_id": ctx["employee_id"]})
        assert valid.status_code == 200
        hard_block = await c.post(f"/api/production-stages/{by_key['hard_eq']['id']}/assign", json={"employee_id": ctx["employee_id"], "override_reason": "Manager override"})
        assert hard_block.status_code == 409
        warning_no_reason = await c.post(f"/api/production-stages/{by_key['warn_eq']['id']}/assign", json={"employee_id": ctx["warning_employee_id"]})
        assert warning_no_reason.status_code == 409
        warning_override = await c.post(f"/api/production-stages/{by_key['warn_eq']['id']}/assign", json={"employee_id": ctx["warning_employee_id"], "override_reason": "Supervised run"})
        assert warning_override.status_code == 200

        timeline = await c.get(f"/api/work-orders/{ctx['wo_id']}/timeline", params={"event_category": "production"})
        assert timeline.status_code == 200
        event_types = {e["event_type"] for e in timeline.json()["items"]}
        assert {
            "workflow_instance_created",
            "stage_started",
            "stage_waiting",
            "stage_blocked",
            "stage_resumed",
            "stage_completed",
            "stage_skipped",
            "stage_reopened",
            "stage_assigned",
            "due_date_changed",
            "production_note_added",
        } <= event_types

    actions = {a["action"] async for a in db.audit_events.find({"tenant_id": ctx["tenant_id"], "entity_type": {"$in": ["production_stage", "production_workflow_instance", "order_item_workflow_override"]}}, {"_id": 0})}
    assert "production_workflow_instance.created" in actions
    assert "production_stage.assigned" in actions
    assert "production_stage.completed" in actions


@pytest.mark.asyncio
async def test_no_workflow_fallback_permissions_portal_denial_and_no_side_effects(ctx):
    async with await _client_as(ctx["owner"]) as c:
        await _create_workflow(c, "Temp Flow", f"temp_flow_{uuid.uuid4().hex[:6]}", [
            {"stage_key": "temp", "display_name": "Temp", "sequence": 1},
        ])
        await db.production_workflows.update_many({"tenant_id": ctx["tenant_id"]}, {"$set": {"active": False, "archived_at": _now(), "is_tenant_default": False}})
        second_wo_id = f"wo-manual-{uuid.uuid4().hex[:6]}"
        second_item_id = f"manual-item-{uuid.uuid4().hex[:6]}"
        await db.order_items.insert_one({
            "id": second_item_id, "tenant_id": ctx["tenant_id"], "order_id": ctx["order_id"],
            "description": "Manual item", "category": "unknown", "quantity": 1, "unit_price_cents": 1,
            "line_total_cents": 1, "production_required": True, "pricing_snapshot": {"unit_price_cents": 1},
            "created_at": _now(), "updated_at": _now(),
        })
        await db.work_orders.insert_one({
            "id": second_wo_id, "tenant_id": ctx["tenant_id"], "number": 6201, "order_id": ctx["order_id"],
            "customer_id": "cust", "production_status": "released", "items_snapshot": [{"order_item_id": second_item_id, "description": "Manual item"}],
            "created_by": ctx["owner"]["id"], "created_at": _now(), "updated_at": _now(),
        })

        before = {
            "time_entries": await db.time_entries.count_documents({"tenant_id": ctx["tenant_id"]}),
            "timesheets": await db.timesheets.count_documents({"tenant_id": ctx["tenant_id"]}),
            "production_timer_sessions": await db.production_timer_sessions.count_documents({"tenant_id": ctx["tenant_id"]}),
            "production_timer_events": await db.production_timer_events.count_documents({"tenant_id": ctx["tenant_id"]}),
            "payroll_transactions": await db.payroll_transactions.count_documents({"tenant_id": ctx["tenant_id"]}),
            "pricing_snapshot_records": await db.pricing_snapshot_records.count_documents({"tenant_id": ctx["tenant_id"]}),
        }
        manual = await c.post(f"/api/work-orders/{second_wo_id}/stages/generate")
        assert manual.status_code == 200, manual.text
        assert manual.json()["workflow_instances"][0]["status"] == "manual_no_workflow"
        assert manual.json()["stages"] == []

        other = await c.get(f"/api/work-orders/{second_wo_id}/stages")
        assert other.status_code == 200

        after = {
            "time_entries": await db.time_entries.count_documents({"tenant_id": ctx["tenant_id"]}),
            "timesheets": await db.timesheets.count_documents({"tenant_id": ctx["tenant_id"]}),
            "production_timer_sessions": await db.production_timer_sessions.count_documents({"tenant_id": ctx["tenant_id"]}),
            "production_timer_events": await db.production_timer_events.count_documents({"tenant_id": ctx["tenant_id"]}),
            "payroll_transactions": await db.payroll_transactions.count_documents({"tenant_id": ctx["tenant_id"]}),
            "pricing_snapshot_records": await db.pricing_snapshot_records.count_documents({"tenant_id": ctx["tenant_id"]}),
        }
        assert after == before

    async with await _client_as(ctx["readonly"]) as c:
        denied = await c.get(f"/api/work-orders/{ctx['wo_id']}/stages")
        assert denied.status_code == 403

    async with await _client_as(ctx["other_owner"]) as c:
        isolated = await c.get(f"/api/work-orders/{ctx['wo_id']}/stages")
        assert isolated.status_code == 404

    employee_portal_token = create_access_token(
        subject="portal-employee", tenant_id=ctx["tenant_id"],
        extra={"sub_scope": "portal", "typ": "portal_access", "portal_type": "employee"},
    )
    async with await _token_client(employee_portal_token) as c:
        denied = await c.get(f"/api/work-orders/{ctx['wo_id']}/stages")
        assert denied.status_code == 401

    customer_portal_token = create_access_token(
        subject="portal-customer", tenant_id=ctx["tenant_id"],
        extra={"sub_scope": "portal", "typ": "portal_access", "portal_type": "customer"},
    )
    async with await _token_client(customer_portal_token) as c:
        denied = await c.get(f"/api/work-orders/{ctx['wo_id']}/stages")
        assert denied.status_code == 401
