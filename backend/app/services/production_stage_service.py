"""EC11 Phase 11C - live Work Order / Order Item production stages.

This layer snapshots Phase 11A workflow definitions into live instances tied
to Work Orders and production-required Order Items. Timer sessions are scoped
to production work only; payroll, labor ledgers, kiosk, and analytics records
are intentionally outside this service.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.production_workflow import (
    OrderItemWorkflowOverride,
    ProductionPricingFeedback,
    ProductionStageInstance,
    ProductionTimerEvent,
    ProductionTimerSession,
    ProductionWorkflowInstance,
)
from .audit import record_audit
from .certification_service import check_work_order_assignment
from .notifications import notify
from .pricing import get_or_init_pricing_settings, update_category, update_shop_defaults
from .production_workflow_service import resolve_workflow
from ..core.permissions import permissions_for_role

ACTIVE_STATUSES = {"not_started", "in_progress", "waiting", "blocked"}
TERMINAL_STATUSES = {"completed", "skipped"}
STAGE_TRANSITIONS = {
    "not_started": {"in_progress", "skipped"},
    "in_progress": {"waiting", "blocked", "completed", "skipped"},
    "waiting": {"in_progress", "blocked"},
    "blocked": {"in_progress", "waiting"},
    "completed": set(),
    "skipped": set(),
}


class ProductionStageError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _now() -> str:
    return utc_now().isoformat()


def _is_manager(user: dict) -> bool:
    return user.get("role") in {"owner", "admin", "production_manager"}


def _user_permissions(user: dict) -> set[str]:
    if "permissions" in user:
        return {str(p) for p in (user.get("permissions") or [])}
    return set(permissions_for_role(user.get("role", "staff")))


def _can_override_production(user: dict) -> bool:
    return _is_manager(user) and "work_order:write" in _user_permissions(user)


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _clean_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _timer_paused_seconds(session: dict, now: Optional[str] = None) -> int:
    total = 0
    now_dt = _parse_dt(now or _now())
    for segment in session.get("pause_segments") or []:
        paused_at = segment.get("paused_at")
        if not paused_at:
            continue
        resumed_at = segment.get("resumed_at")
        end = _parse_dt(resumed_at) if resumed_at else now_dt
        total += max(0, int((end - _parse_dt(paused_at)).total_seconds()))
    return total


def _timer_effective_seconds(session: dict, now: Optional[str] = None) -> int:
    if session.get("status") == "voided":
        return 0
    if session.get("corrected_elapsed_seconds") is not None:
        return max(0, int(session.get("corrected_elapsed_seconds") or 0))
    if session.get("status") == "completed":
        return max(0, int(session.get("effective_elapsed_seconds") or session.get("elapsed_seconds") or 0))
    end = _parse_dt(now or _now())
    raw = max(0, int((end - _parse_dt(session["started_at"])).total_seconds()))
    return max(0, raw - _timer_paused_seconds(session, now=now))


def _timer_payload(session: dict, employees: dict[str, dict], now: Optional[str] = None) -> dict:
    employee = employees.get(session.get("employee_id"), {})
    effective = _timer_effective_seconds(session, now=now)
    paused = _timer_paused_seconds(session, now=now)
    return {
        "id": session["id"],
        "status": session.get("status"),
        "employee_id": session.get("employee_id"),
        "employee_name": employee.get("name"),
        "employee_user_id": session.get("employee_user_id"),
        "started_at": session.get("started_at"),
        "paused_at": session.get("paused_at"),
        "stopped_at": session.get("stopped_at"),
        "stage_id": session.get("stage_id"),
        "effective_elapsed_seconds": effective,
        "paused_duration_seconds": paused,
        "corrected_elapsed_seconds": session.get("corrected_elapsed_seconds"),
        "voided_at": session.get("voided_at"),
        "corrections": session.get("corrections") or [],
        "pause_segments": session.get("pause_segments") or [],
    }


async def _assert_timer_control_allowed(session: dict, tenant_id: str, user: dict, action: str) -> None:
    own_employee = await db.employees.find_one({"tenant_id": tenant_id, "linked_user_id": user["id"]}, {"_id": 0})
    if session.get("employee_id") == (own_employee or {}).get("id"):
        return
    if _can_override_production(user):
        return
    raise ProductionStageError("timer_control_forbidden", f"Only the timer owner or a production manager may {action} this timer")


def _require_manager(user: dict, *, code: str = "timer_manager_required") -> None:
    if not _can_override_production(user):
        raise ProductionStageError(code, "Production manager authority is required")


async def _employee_for_timer(tenant_id: str, user: dict, employee_id: Optional[str]) -> dict:
    query: dict[str, Any] = {"tenant_id": tenant_id}
    if employee_id:
        if not _is_manager(user):
            own = await db.employees.find_one({"tenant_id": tenant_id, "linked_user_id": user["id"]}, {"_id": 0})
            if not own or own.get("id") != employee_id:
                raise ProductionStageError("timer_employee_forbidden", "Users may only start their own production timer")
        query["id"] = employee_id
    else:
        query["linked_user_id"] = user["id"]
    employee = await db.employees.find_one(query, {"_id": 0})
    if not employee:
        raise ProductionStageError("employee_not_found", "Employee not found")
    if employee.get("status") != "active":
        raise ProductionStageError("employee_inactive", "Employee is not active")
    return serialize_doc(employee)


async def _record_timer_event(
    *,
    tenant_id: str,
    session: dict,
    event_type: str,
    actor_user_id: str,
    reason: Optional[str] = None,
    notes: Optional[str] = None,
    elapsed_seconds: Optional[int] = None,
) -> None:
    event = ProductionTimerEvent(
        tenant_id=tenant_id,
        session_id=session["id"],
        event_type=event_type,
        work_order_id=session["work_order_id"],
        order_id=session["order_id"],
        order_item_id=session["order_item_id"],
        workflow_instance_id=session["workflow_instance_id"],
        stage_id=session["stage_id"],
        employee_id=session["employee_id"],
        actor_user_id=actor_user_id,
        occurred_at=_now(),
        elapsed_seconds=elapsed_seconds,
        reason=reason,
        notes=notes,
    ).model_dump()
    await db.production_timer_events.insert_one(prepare_for_mongo(event))


async def _stage_timer_summary(tenant_id: str, stage_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not stage_ids:
        return {}
    summaries: dict[str, dict[str, Any]] = {
        stage_id: {"actual_duration_seconds": 0, "timing_entry_count": 0, "active_timer": None, "current_timer": None, "timer_history": []}
        for stage_id in stage_ids
    }
    sessions = [
        serialize_doc(s) async for s in db.production_timer_sessions.find(
            {"tenant_id": tenant_id, "stage_id": {"$in": stage_ids}},
            {"_id": 0},
        )
    ]
    employee_ids = sorted({s.get("employee_id") for s in sessions if s.get("employee_id")})
    employees = {
        e["id"]: serialize_doc(e) async for e in db.employees.find(
            {"tenant_id": tenant_id, "id": {"$in": employee_ids}},
            {"_id": 0, "id": 1, "name": 1, "linked_user_id": 1},
        )
    } if employee_ids else {}
    for session in sessions:
        stage_id = session.get("stage_id")
        if stage_id not in summaries:
            continue
        effective = _timer_effective_seconds(session)
        timer_payload = _timer_payload(session, employees)
        if session.get("status") == "completed":
            summaries[stage_id]["actual_duration_seconds"] += effective
            summaries[stage_id]["timing_entry_count"] += 1
        elif session.get("status") in {"active", "paused"}:
            summaries[stage_id]["actual_duration_seconds"] += effective
            summaries[stage_id]["current_timer"] = timer_payload
            if session.get("status") == "active":
                summaries[stage_id]["active_timer"] = timer_payload
        summaries[stage_id]["timer_history"].append(timer_payload)
    for summary in summaries.values():
        summary["timer_history"].sort(key=lambda t: t.get("started_at") or "", reverse=True)
    return summaries


async def _apply_timer_summaries(tenant_id: str, stages: list[dict]) -> list[dict]:
    summaries = await _stage_timer_summary(tenant_id, [s["id"] for s in stages if s.get("id")])
    for stage in stages:
        summary = summaries.get(stage.get("id"), {})
        stage["actual_duration_seconds"] = int(summary.get("actual_duration_seconds") or stage.get("actual_duration_seconds") or 0)
        stage["timing_entry_count"] = int(summary.get("timing_entry_count") or stage.get("timing_entry_count") or 0)
        stage["active_timer"] = summary.get("active_timer")
        stage["current_timer"] = summary.get("current_timer")
        stage["timer_history"] = summary.get("timer_history") or []
    return stages


def _apply_planned_minutes(stages: list[dict], instances: list[dict]) -> list[dict]:
    planned_by_stage: dict[tuple[str, str], Optional[int]] = {}
    for instance in instances:
        for definition in instance.get("stage_definitions") or []:
            planned_by_stage[(instance.get("id"), definition.get("stage_key"))] = definition.get("default_estimated_duration_minutes")
    for stage in stages:
        planned = planned_by_stage.get((stage.get("workflow_instance_id"), stage.get("stage_key")))
        if planned is not None:
            stage["default_estimated_duration_minutes"] = planned
    return stages


def _clean_stages(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    active = [copy.deepcopy(s) for s in stages if s.get("active", True)]
    active.sort(key=lambda s: int(s.get("sequence") or 0))
    for i, stage in enumerate(active, start=1):
        stage["sequence"] = int(stage.get("sequence") or i)
    return active


def _stage_snapshot(stage: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": stage.get("id"),
        "stage_key": stage.get("stage_key"),
        "display_name": stage.get("display_name"),
        "description": stage.get("description"),
        "sequence": int(stage.get("sequence") or 0),
        "required": bool(stage.get("required", True)),
        "may_skip": bool(stage.get("may_skip", True)),
        "requires_reason_to_skip": bool(stage.get("requires_reason_to_skip", False)),
        "default_role": stage.get("default_role"),
        "due_date_offset_days": stage.get("due_date_offset_days"),
        "customer_visible": bool(stage.get("customer_visible", False)),
        "employee_visible": bool(stage.get("employee_visible", True)),
        "requires_previous_stage_complete": bool(stage.get("requires_previous_stage_complete", True)),
        "proof_gate_type": stage.get("proof_gate_type"),
        "equipment_requirement_ids": list(stage.get("equipment_requirement_ids") or []),
        "certification_requirement_ids": list(stage.get("certification_requirement_ids") or []),
        "metadata": dict(stage.get("metadata") or {}),
    }


async def _order_item(tenant_id: str, order_id: str, item_id: str) -> dict:
    item = await db.order_items.find_one({"tenant_id": tenant_id, "order_id": order_id, "id": item_id}, {"_id": 0})
    if not item:
        raise ProductionStageError("order_item_not_found", "Order item not found")
    return serialize_doc(item)


async def _work_order(tenant_id: str, work_order_id: str) -> dict:
    wo = await db.work_orders.find_one({"tenant_id": tenant_id, "id": work_order_id}, {"_id": 0})
    if not wo:
        raise ProductionStageError("work_order_not_found", "Work order not found")
    return serialize_doc(wo)


async def _order(tenant_id: str, order_id: str) -> dict:
    order = await db.orders.find_one({"tenant_id": tenant_id, "id": order_id}, {"_id": 0})
    if not order:
        raise ProductionStageError("order_not_found", "Order not found")
    return serialize_doc(order)


async def _resolve_for_item(
    *,
    tenant_id: str,
    order_id: str,
    item_id: str,
    explicit_workflow_id: Optional[str] = None,
    seed: bool = True,
) -> dict[str, Any]:
    item = await _order_item(tenant_id, order_id, item_id)
    if not bool(item.get("production_required", True)):
        return {"source": "non_production_item", "workflow": None, "override": None, "item": item}
    override = await db.order_item_workflow_overrides.find_one({"tenant_id": tenant_id, "order_item_id": item_id}, {"_id": 0})
    if override and not explicit_workflow_id:
        return {
            "source": "order_item_override",
            "workflow": {
                "id": override["id"],
                "name": override["workflow_name"],
                "workflow_key": override["workflow_key"],
                "version": override.get("source_workflow_version"),
                "stages": override.get("stages") or [],
            },
            "override": serialize_doc(override),
            "item": item,
        }
    category_id = item.get("category") or item.get("product_type")
    resolved = await resolve_workflow(
        tenant_id=tenant_id,
        category_id=category_id,
        explicit_workflow_id=explicit_workflow_id,
        seed=seed,
    )
    return {**resolved, "override": None, "item": item}


async def preview_item_workflow(
    *, tenant_id: str, order_id: str, item_id: str, explicit_workflow_id: Optional[str] = None,
) -> dict[str, Any]:
    await _order(tenant_id, order_id)
    resolved = await _resolve_for_item(
        tenant_id=tenant_id, order_id=order_id, item_id=item_id, explicit_workflow_id=explicit_workflow_id,
    )
    workflow = resolved.get("workflow")
    return {
        "source": resolved["source"],
        "workflow": workflow,
        "stage_count": len(_clean_stages((workflow or {}).get("stages") or [])) if workflow else 0,
        "reason": None if workflow else resolved["source"],
        "override": resolved.get("override"),
    }


async def save_item_override(
    *,
    tenant_id: str,
    order_id: str,
    item_id: str,
    workflow_id: str,
    stages: Optional[list[dict[str, Any]]],
    actor_user_id: str,
    actor_email: str,
) -> dict:
    await _order(tenant_id, order_id)
    await _order_item(tenant_id, order_id, item_id)
    existing = await db.order_item_workflow_overrides.find_one({"tenant_id": tenant_id, "order_item_id": item_id}, {"_id": 0})
    if existing and existing.get("locked_at"):
        raise ProductionStageError("override_locked", "Order item workflow override is frozen after stage generation")
    resolved = await resolve_workflow(tenant_id=tenant_id, explicit_workflow_id=workflow_id)
    workflow = resolved.get("workflow")
    if not workflow:
        raise ProductionStageError("workflow_not_found", "Production workflow not found")
    snapshot_stages = _clean_stages(stages if stages is not None else workflow.get("stages") or [])
    if not snapshot_stages:
        raise ProductionStageError("workflow_has_no_stages", "Workflow has no active stages")
    now = _now()
    if existing:
        updates = {
            "source_workflow_id": workflow["id"],
            "source_workflow_version": int(workflow.get("version") or 1),
            "workflow_name": workflow["name"],
            "workflow_key": workflow["workflow_key"],
            "stages": snapshot_stages,
            "updated_by_user_id": actor_user_id,
            "updated_at": now,
        }
        await db.order_item_workflow_overrides.update_one({"id": existing["id"], "tenant_id": tenant_id}, {"$set": prepare_for_mongo(updates)})
        override_id = existing["id"]
        action = "production_item_workflow_override.updated"
        summary = f"Order item workflow override updated: {workflow['name']}"
    else:
        doc = OrderItemWorkflowOverride(
            tenant_id=tenant_id,
            order_id=order_id,
            order_item_id=item_id,
            source_workflow_id=workflow["id"],
            source_workflow_version=int(workflow.get("version") or 1),
            workflow_name=workflow["name"],
            workflow_key=workflow["workflow_key"],
            stages=snapshot_stages,
            created_by_user_id=actor_user_id,
            updated_by_user_id=actor_user_id,
        ).model_dump()
        await db.order_item_workflow_overrides.insert_one(prepare_for_mongo(doc))
        override_id = doc["id"]
        action = "production_item_workflow_override.created"
        summary = f"Order item workflow override created: {workflow['name']}"
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action=action, entity_type="order_item_workflow_override", entity_id=override_id,
        summary=summary, diff={"order_id": order_id, "item_id": item_id, "source_workflow_id": workflow["id"]},
    )
    return serialize_doc(await db.order_item_workflow_overrides.find_one({"id": override_id, "tenant_id": tenant_id}, {"_id": 0}))


async def preview_work_order_generation(*, tenant_id: str, work_order_id: str) -> dict:
    wo = await _work_order(tenant_id, work_order_id)
    rows = []
    for snap in wo.get("items_snapshot") or []:
        item_id = snap.get("order_item_id")
        if not item_id:
            continue
        try:
            resolved = await _resolve_for_item(tenant_id=tenant_id, order_id=wo["order_id"], item_id=item_id, seed=False)
        except ProductionStageError as ex:
            rows.append({"order_item_id": item_id, "source": str(ex.code), "workflow": None, "stage_count": 0})
            continue
        workflow = resolved.get("workflow")
        rows.append({
            "order_item_id": item_id,
            "source": resolved["source"],
            "workflow": workflow,
            "stage_count": len(_clean_stages((workflow or {}).get("stages") or [])) if workflow else 0,
            "reason": None if workflow else resolved["source"],
        })
    return {"work_order_id": work_order_id, "items": rows}


def _due_at_for_stage(work_order: dict, stage: dict[str, Any]) -> Optional[str]:
    if work_order.get("due_date"):
        return work_order["due_date"]
    return None


async def generate_work_order_stages(*, tenant_id: str, work_order_id: str, actor_user_id: str, actor_email: str) -> dict:
    wo = await _work_order(tenant_id, work_order_id)
    created_instances = []
    created_stages = []
    skipped = []
    for snap in wo.get("items_snapshot") or []:
        item_id = snap.get("order_item_id")
        if not item_id:
            continue
        item = await db.order_items.find_one({"tenant_id": tenant_id, "order_id": wo["order_id"], "id": item_id}, {"_id": 0})
        if not item or item.get("archived_at") or not bool(item.get("production_required", True)):
            skipped.append({"order_item_id": item_id, "reason": "non_production_or_archived"})
            continue
        existing = await db.production_workflow_instances.find_one(
            {"tenant_id": tenant_id, "work_order_id": work_order_id, "order_item_id": item_id}, {"_id": 0},
        )
        if existing:
            skipped.append({"order_item_id": item_id, "reason": "already_generated", "workflow_instance_id": existing["id"]})
            continue
        resolved = await _resolve_for_item(tenant_id=tenant_id, order_id=wo["order_id"], item_id=item_id, seed=False)
        workflow = resolved.get("workflow")
        source = resolved["source"]
        stage_defs = _clean_stages((workflow or {}).get("stages") or [])
        status = "active" if workflow and stage_defs else "manual_no_workflow"
        instance = ProductionWorkflowInstance(
            tenant_id=tenant_id,
            order_id=wo["order_id"],
            order_item_id=item_id,
            work_order_id=work_order_id,
            source_workflow_id=(workflow or {}).get("id"),
            source_workflow_version=(workflow or {}).get("version"),
            source_type=source if source in {"order_item_override", "category", "tenant_default", "manual_no_workflow"} else "explicit_workflow",
            source_name=(workflow or {}).get("name"),
            created_by_user_id=actor_user_id,
            status=status,
            resolution_source=source,
            stage_definitions=[_stage_snapshot(s) for s in stage_defs],
        ).model_dump()
        try:
            await db.production_workflow_instances.insert_one(prepare_for_mongo(instance))
        except DuplicateKeyError:
            existing = await db.production_workflow_instances.find_one(
                {"tenant_id": tenant_id, "work_order_id": work_order_id, "order_item_id": item_id}, {"_id": 0},
            )
            skipped.append({"order_item_id": item_id, "reason": "already_generated", "workflow_instance_id": existing["id"]})
            continue
        await record_audit(
            tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
            action="production_workflow_instance.resolved", entity_type="production_workflow_instance", entity_id=instance["id"],
            summary=f"Production workflow resolved: {source}",
            diff={"order_id": wo["order_id"], "item_id": item_id, "work_order_id": work_order_id, "source": source},
        )
        await record_audit(
            tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
            action="production_workflow_instance.created", entity_type="production_workflow_instance", entity_id=instance["id"],
            summary=f"Production workflow instance created for item {item_id}",
            diff={"order_id": wo["order_id"], "item_id": item_id, "work_order_id": work_order_id, "stage_count": len(stage_defs)},
        )
        if resolved.get("override"):
            await db.order_item_workflow_overrides.update_one(
                {"tenant_id": tenant_id, "order_item_id": item_id},
                {"$set": {"locked_at": _now(), "locked_workflow_instance_id": instance["id"], "updated_at": _now()}},
            )
        created_instances.append(serialize_doc(instance))
        for stage in stage_defs:
            stage_doc = ProductionStageInstance(
                tenant_id=tenant_id,
                workflow_instance_id=instance["id"],
                order_id=wo["order_id"],
                order_item_id=item_id,
                work_order_id=work_order_id,
                stage_key=stage["stage_key"],
                stage_name=stage["display_name"],
                description=stage.get("description"),
                sequence=int(stage.get("sequence") or 0),
                required=bool(stage.get("required", True)),
                may_skip=bool(stage.get("may_skip", True)),
                requires_reason_to_skip=bool(stage.get("requires_reason_to_skip", False)),
                assigned_role=stage.get("default_role"),
                due_at=_due_at_for_stage(wo, stage),
                proof_gate_type=stage.get("proof_gate_type"),
                proof_gate_snapshot={"proof_gate_type": stage.get("proof_gate_type")} if stage.get("proof_gate_type") else None,
                equipment_requirement_ids=list(stage.get("equipment_requirement_ids") or []),
                certification_requirement_ids=list(stage.get("certification_requirement_ids") or []),
                customer_visible=bool(stage.get("customer_visible", False)),
                employee_visible=bool(stage.get("employee_visible", True)),
                requires_previous_stage_complete=bool(stage.get("requires_previous_stage_complete", True)),
            ).model_dump()
            try:
                await db.production_stage_instances.insert_one(prepare_for_mongo(stage_doc))
                created_stages.append(serialize_doc(stage_doc))
            except DuplicateKeyError:
                pass
    await _derive_parent_production_state(tenant_id=tenant_id, work_order_id=work_order_id)
    return {
        "workflow_instances": created_instances,
        "stages": created_stages,
        "skipped": skipped,
        "already_generated": len(created_instances) == 0 and len(skipped) > 0,
    }


async def list_work_order_stages(*, tenant_id: str, work_order_id: str) -> dict:
    wo = await _work_order(tenant_id, work_order_id)
    instances = [serialize_doc(d) async for d in db.production_workflow_instances.find(
        {"tenant_id": tenant_id, "work_order_id": work_order_id}, {"_id": 0},
    ).sort("created_at", 1)]
    stages = [serialize_doc(d) async for d in db.production_stage_instances.find(
        {"tenant_id": tenant_id, "work_order_id": work_order_id}, {"_id": 0},
    ).sort([("order_item_id", 1), ("sequence", 1)])]
    stages = await _apply_timer_summaries(tenant_id, stages)
    stages = _apply_planned_minutes(stages, instances)
    return {"work_order_id": work_order_id, "order_id": wo["order_id"], "workflow_instances": instances, "stages": stages}


async def get_stage(*, tenant_id: str, stage_id: str) -> dict:
    stage = await db.production_stage_instances.find_one({"tenant_id": tenant_id, "id": stage_id}, {"_id": 0})
    if not stage:
        raise ProductionStageError("stage_not_found", "Production stage not found")
    stages = await _apply_timer_summaries(tenant_id, [serialize_doc(stage)])
    instance = await db.production_workflow_instances.find_one({"tenant_id": tenant_id, "id": stages[0]["workflow_instance_id"]}, {"_id": 0})
    stages = _apply_planned_minutes(stages, [serialize_doc(instance)] if instance else [])
    return stages[0]


async def _assert_stage_action_allowed(stage: dict, user: dict) -> None:
    await _work_order(user["tenant_id"], stage["work_order_id"])


async def _record_stage_audit(
    *, tenant_id: str, actor_user_id: str, actor_email: str, action: str,
    stage: dict, summary: str, diff: Optional[dict[str, Any]] = None,
) -> None:
    payload = {
        "order_id": stage.get("order_id"),
        "order_item_id": stage.get("order_item_id"),
        "work_order_id": stage.get("work_order_id"),
        "workflow_instance_id": stage.get("workflow_instance_id"),
        **(diff or {}),
    }
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action=action, entity_type="production_stage", entity_id=stage["id"],
        summary=summary, diff=payload,
    )


async def _append_history(stage_id: str, entry: dict[str, Any]) -> None:
    await db.production_stage_instances.update_one({"id": stage_id}, {"$push": {"history": entry}})


async def _prior_stage_gate(stage: dict) -> None:
    if not stage.get("requires_previous_stage_complete", True):
        return
    prior = await db.production_stage_instances.find_one(
        {
            "tenant_id": stage["tenant_id"],
            "workflow_instance_id": stage["workflow_instance_id"],
            "sequence": {"$lt": int(stage.get("sequence") or 0)},
            "required": True,
            "status": {"$ne": "completed"},
        },
        {"_id": 0},
        sort=[("sequence", -1)],
    )
    if prior:
        raise ProductionStageError("previous_stage_incomplete", f"Previous required stage is not complete: {prior.get('stage_name')}")


async def _proof_gate(stage: dict) -> None:
    gate = stage.get("proof_gate_type")
    if not gate or gate in {"none", "not_required"}:
        return
    filters = [
        {"parent_type": "order_item", "parent_id": stage["order_item_id"]},
        {"parent_type": "work_order", "parent_id": stage["work_order_id"]},
        {"parent_type": "order", "parent_id": stage["order_id"]},
    ]
    proof = await db.proofs.find_one({"tenant_id": stage["tenant_id"], "$or": filters, "status": "approved"}, {"_id": 0})
    if proof:
        return
    proof_ids = [p["id"] async for p in db.proofs.find({"tenant_id": stage["tenant_id"], "$or": filters}, {"_id": 0, "id": 1})]
    versions = [v["id"] async for v in db.proof_versions.find({"tenant_id": stage["tenant_id"], "proof_id": {"$in": proof_ids}}, {"_id": 0, "id": 1})] if proof_ids else []
    approval = await db.approvals.find_one(
        {"tenant_id": stage["tenant_id"], "parent_type": "proof_version", "parent_id": {"$in": versions}, "action": "approve"},
        {"_id": 0},
    ) if versions else None
    if not approval:
        raise ProductionStageError("proof_gate_blocked", "Approved proof or approval record is required before this stage can complete")


async def _derive_parent_production_state(*, tenant_id: str, work_order_id: str) -> None:
    wo = await db.work_orders.find_one({"tenant_id": tenant_id, "id": work_order_id}, {"_id": 0})
    if not wo:
        return
    instances = [
        serialize_doc(i) async for i in db.production_workflow_instances.find(
            {"tenant_id": tenant_id, "work_order_id": work_order_id},
            {"_id": 0},
        )
    ]
    if not instances:
        return
    stages = [
        serialize_doc(s) async for s in db.production_stage_instances.find(
            {"tenant_id": tenant_id, "work_order_id": work_order_id},
            {"_id": 0},
        )
    ]
    stages_by_instance: dict[str, list[dict]] = {}
    for stage in stages:
        stages_by_instance.setdefault(stage["workflow_instance_id"], []).append(stage)

    instance_states: dict[str, str] = {}
    for instance in instances:
        instance_stages = stages_by_instance.get(instance["id"], [])
        if instance.get("status") == "manual_no_workflow":
            state = "manual_no_workflow"
        elif instance_stages and all(s.get("status") in TERMINAL_STATUSES for s in instance_stages):
            state = "completed"
        elif any(s.get("status") == "blocked" for s in instance_stages):
            state = "blocked"
        elif any(s.get("status") == "waiting" for s in instance_stages):
            state = "waiting"
        elif any(s.get("status") == "in_progress" for s in instance_stages):
            state = "in_progress"
        else:
            state = "queued"
        instance_states[instance["id"]] = state
        instance_status = "manual_no_workflow" if state == "manual_no_workflow" else "completed" if state == "completed" else "active"
        await db.production_workflow_instances.update_one(
            {"tenant_id": tenant_id, "id": instance["id"]},
            {"$set": {"status": instance_status, "updated_at": _now()}},
        )
        await db.order_items.update_one(
            {"tenant_id": tenant_id, "id": instance["order_item_id"]},
            {"$set": {
                "production_status": state,
                "current_production_stage_id": next((s.get("id") for s in sorted(instance_stages, key=lambda x: int(x.get("sequence") or 0)) if s.get("status") not in TERMINAL_STATUSES), None),
                "updated_at": _now(),
            }},
        )

    states = set(instance_states.values())
    if "blocked" in states:
        target = "blocked"
    elif "in_progress" in states:
        target = "in_progress"
    elif "waiting" in states:
        target = "in_progress"
    elif states and states.issubset({"completed", "manual_no_workflow"}):
        target = "ready"
    else:
        target = "queued"

    if wo.get("production_status") not in {"cancelled", "superseded", "completed"}:
        updates: dict[str, Any] = {"production_status": target, "updated_at": _now()}
        if target == "ready" and not wo.get("ready_at"):
            updates["ready_at"] = _now()
        if target == "in_progress" and not wo.get("started_at"):
            updates["started_at"] = _now()
        await db.work_orders.update_one({"tenant_id": tenant_id, "id": work_order_id}, {"$set": prepare_for_mongo(updates)})
    order_target = "ready" if target == "ready" else "in_production" if target in {"in_progress", "blocked", "queued"} else None
    if order_target:
        order = await db.orders.find_one({"tenant_id": tenant_id, "id": wo["order_id"]}, {"_id": 0, "status": 1})
        if order and order.get("status") not in {"cancelled", "archived", "completed"}:
            await db.orders.update_one(
                {"tenant_id": tenant_id, "id": wo["order_id"]},
                {"$set": {"status": order_target, "production_state": target, "updated_at": _now()}},
            )


async def assign_stage(*, tenant_id: str, stage_id: str, employee_id: str, override_reason: Optional[str], user: dict) -> dict:
    if not _is_manager(user):
        raise ProductionStageError("manager_required", "Only owner/admin/production manager may assign stages")
    stage = await get_stage(tenant_id=tenant_id, stage_id=stage_id)
    employee = await db.employees.find_one({"tenant_id": tenant_id, "id": employee_id}, {"_id": 0})
    if not employee:
        raise ProductionStageError("employee_not_found", "Employee not found")
    if employee.get("status") != "active":
        raise ProductionStageError("employee_inactive", "Employee is not active")
    linked_user_id = employee.get("linked_user_id")
    has_requirements = bool(stage.get("equipment_requirement_ids") or stage.get("certification_requirement_ids") or stage.get("assigned_role"))
    if has_requirements and not linked_user_id:
        raise ProductionStageError("employee_user_link_required", "Employee must be linked to a user to verify stage requirements")
    if linked_user_id:
        check = await check_work_order_assignment(
            tenant_id=tenant_id,
            work_order={
                "required_equipment_ids": stage.get("equipment_requirement_ids") or [],
                "required_role": stage.get("assigned_role"),
                "required_skill": None,
            },
            user_ids=[linked_user_id],
        )
        if check["any_blocked"]:
            raise ProductionStageError("assignment_blocked", "Assignment blocked by eligibility requirements")
        if check["any_warning"] and not (override_reason and override_reason.strip()):
            raise ProductionStageError("assignment_warning_override_required", "Assignment warning override reason required")
    if stage.get("assigned_employee_id") == employee_id and stage.get("assigned_user_id") == linked_user_id:
        return stage
    now = _now()
    await db.production_stage_instances.update_one(
        {"tenant_id": tenant_id, "id": stage_id},
        {"$set": {
            "assigned_employee_id": employee_id,
            "assigned_user_id": linked_user_id,
            "updated_at": now,
        }},
    )
    updated = await get_stage(tenant_id=tenant_id, stage_id=stage_id)
    await _append_history(stage_id, {"action": "assigned", "employee_id": employee_id, "actor_user_id": user["id"], "at": now, "override_reason": override_reason})
    await _record_stage_audit(
        tenant_id=tenant_id, actor_user_id=user["id"], actor_email=user["email"],
        action="production_stage.assigned", stage=updated,
        summary=f"Stage assigned: {updated['stage_name']}", diff={"employee_id": employee_id, "assigned_user_id": linked_user_id, "override_reason": override_reason},
    )
    if linked_user_id:
        try:
            await notify(
                tenant_id=tenant_id, recipient_user_id=linked_user_id, module="production", kind="stage_assigned",
                title=f"Assigned stage: {updated['stage_name']}", link=f"/work-orders/{updated['work_order_id']}",
                entity_type="production_stage", entity_id=stage_id,
            )
        except Exception:
            pass
    return updated


async def unassign_stage(*, tenant_id: str, stage_id: str, user: dict) -> dict:
    if not _is_manager(user):
        raise ProductionStageError("manager_required", "Only owner/admin/production manager may unassign stages")
    stage = await get_stage(tenant_id=tenant_id, stage_id=stage_id)
    if not stage.get("assigned_employee_id") and not stage.get("assigned_user_id"):
        return stage
    now = _now()
    await db.production_stage_instances.update_one(
        {"tenant_id": tenant_id, "id": stage_id},
        {"$set": {"assigned_employee_id": None, "assigned_user_id": None, "updated_at": now}},
    )
    updated = await get_stage(tenant_id=tenant_id, stage_id=stage_id)
    await _append_history(stage_id, {"action": "unassigned", "actor_user_id": user["id"], "at": now})
    await _record_stage_audit(
        tenant_id=tenant_id, actor_user_id=user["id"], actor_email=user["email"],
        action="production_stage.unassigned", stage=updated, summary=f"Stage unassigned: {updated['stage_name']}",
    )
    return updated


async def transition_stage(
    *,
    tenant_id: str,
    stage_id: str,
    target: str,
    user: dict,
    reason: Optional[str] = None,
    completion_note: Optional[str] = None,
) -> dict:
    stage = await get_stage(tenant_id=tenant_id, stage_id=stage_id)
    await _assert_stage_action_allowed(stage, user)
    current = stage.get("status") or "not_started"
    if target == current:
        return stage
    if target == "skipped" and not _is_manager(user):
        raise ProductionStageError("manager_required", "Only owner/admin/production manager may skip stages")
    if target not in STAGE_TRANSITIONS.get(current, set()):
        raise ProductionStageError("invalid_transition", f"Invalid stage transition {current} -> {target}")
    if target == "in_progress" and current == "not_started":
        await _prior_stage_gate(stage)
    if target == "blocked" and not (reason and reason.strip()):
        raise ProductionStageError("reason_required", "Block reason is required")
    if target == "skipped":
        if not stage.get("may_skip", True):
            raise ProductionStageError("skip_not_allowed", "This stage cannot be skipped")
        if stage.get("requires_reason_to_skip") and not (reason and reason.strip()):
            raise ProductionStageError("reason_required", "Skip reason is required")
    if target == "completed":
        await _proof_gate(stage)
    now = _now()
    updates: dict[str, Any] = {"status": target, "updated_at": now}
    action_suffix = {
        "in_progress": "resumed" if current in {"waiting", "blocked"} else "started",
        "waiting": "waiting",
        "blocked": "blocked",
        "completed": "completed",
        "skipped": "skipped",
    }[target]
    if target == "in_progress" and not stage.get("started_at"):
        updates["started_at"] = now
    if target == "waiting":
        updates["waiting_since"] = now
    if target == "blocked":
        updates["blocked_at"] = now
        updates["blocker_reason"] = reason.strip()
    if target == "completed":
        updates["completed_at"] = now
        updates["completion_note"] = completion_note
    if target == "skipped":
        updates["skipped_at"] = now
        updates["skip_reason"] = reason
    if target == "in_progress" and current in {"waiting", "blocked"}:
        updates["waiting_since"] = None
        updates["blocker_reason"] = None
    await db.production_stage_instances.update_one({"tenant_id": tenant_id, "id": stage_id}, {"$set": prepare_for_mongo(updates)})
    updated = await get_stage(tenant_id=tenant_id, stage_id=stage_id)
    await _append_history(stage_id, {"action": action_suffix, "from": current, "to": target, "actor_user_id": user["id"], "at": now, "reason": reason, "completion_note": completion_note})
    await _record_stage_audit(
        tenant_id=tenant_id, actor_user_id=user["id"], actor_email=user["email"],
        action=f"production_stage.{action_suffix}", stage=updated,
        summary=f"Stage {action_suffix}: {updated['stage_name']}",
        diff={"from": current, "to": target, "reason": reason, "completion_note": completion_note},
    )
    if target == "blocked" and updated.get("assigned_user_id"):
        try:
            await notify(
                tenant_id=tenant_id, recipient_user_id=updated["assigned_user_id"], module="production", kind="stage_blocked",
                title=f"Stage blocked: {updated['stage_name']}", body=reason, link=f"/work-orders/{updated['work_order_id']}",
                entity_type="production_stage", entity_id=stage_id, severity="warning",
            )
        except Exception:
            pass
    await _derive_parent_production_state(tenant_id=tenant_id, work_order_id=updated["work_order_id"])
    return updated


async def reopen_stage(*, tenant_id: str, stage_id: str, reason: str, user: dict) -> dict:
    if not _is_manager(user):
        raise ProductionStageError("manager_required", "Only owner/admin/production manager may reopen stages")
    if not reason or not reason.strip():
        raise ProductionStageError("reason_required", "Reopen reason is required")
    stage = await get_stage(tenant_id=tenant_id, stage_id=stage_id)
    if stage.get("status") not in TERMINAL_STATUSES:
        raise ProductionStageError("stage_not_reopenable", "Only completed or skipped stages can be reopened")
    now = _now()
    previous = stage.get("status")
    await db.production_stage_instances.update_one(
        {"tenant_id": tenant_id, "id": stage_id},
        {"$set": {
            "status": "in_progress",
            "reopened_at": now,
            "reopened_by_user_id": user["id"],
            "reopen_reason": reason.strip(),
            "updated_at": now,
        }},
    )
    updated = await get_stage(tenant_id=tenant_id, stage_id=stage_id)
    await _append_history(stage_id, {"action": "reopened", "from": previous, "to": "in_progress", "actor_user_id": user["id"], "at": now, "reason": reason})
    await _record_stage_audit(
        tenant_id=tenant_id, actor_user_id=user["id"], actor_email=user["email"],
        action="production_stage.reopened", stage=updated,
        summary=f"Stage reopened: {updated['stage_name']}", diff={"from": previous, "to": "in_progress", "reason": reason},
    )
    await _derive_parent_production_state(tenant_id=tenant_id, work_order_id=updated["work_order_id"])
    return updated


async def update_stage_due_date(*, tenant_id: str, stage_id: str, due_at: Optional[str], user: dict) -> dict:
    if not _is_manager(user):
        raise ProductionStageError("manager_required", "Only owner/admin/production manager may update stage due dates")
    stage = await get_stage(tenant_id=tenant_id, stage_id=stage_id)
    if stage.get("due_at") == due_at:
        return stage
    now = _now()
    await db.production_stage_instances.update_one({"tenant_id": tenant_id, "id": stage_id}, {"$set": {"due_at": due_at, "updated_at": now}})
    updated = await get_stage(tenant_id=tenant_id, stage_id=stage_id)
    await _append_history(stage_id, {"action": "due_date_changed", "from": stage.get("due_at"), "to": due_at, "actor_user_id": user["id"], "at": now})
    await _record_stage_audit(
        tenant_id=tenant_id, actor_user_id=user["id"], actor_email=user["email"],
        action="production_stage.due_date_changed", stage=updated,
        summary=f"Stage due date changed: {updated['stage_name']}", diff={"from": stage.get("due_at"), "to": due_at},
    )
    if updated.get("assigned_user_id"):
        try:
            await notify(
                tenant_id=tenant_id, recipient_user_id=updated["assigned_user_id"], module="production", kind="stage_due_date_changed",
                title=f"Due date changed: {updated['stage_name']}", link=f"/work-orders/{updated['work_order_id']}",
                entity_type="production_stage", entity_id=stage_id,
            )
        except Exception:
            pass
    return updated


async def add_stage_note(*, tenant_id: str, stage_id: str, note: str, user: dict) -> dict:
    if not note or not note.strip():
        raise ProductionStageError("note_required", "Production note is required")
    stage = await get_stage(tenant_id=tenant_id, stage_id=stage_id)
    now = _now()
    entry = {"note": note.strip(), "created_at": now, "created_by_user_id": user["id"]}
    await db.production_stage_instances.update_one(
        {"tenant_id": tenant_id, "id": stage_id},
        {"$push": {"production_notes": entry}, "$set": {"updated_at": now}},
    )
    updated = await get_stage(tenant_id=tenant_id, stage_id=stage_id)
    await _append_history(stage_id, {"action": "production_note_added", "actor_user_id": user["id"], "at": now})
    await _record_stage_audit(
        tenant_id=tenant_id, actor_user_id=user["id"], actor_email=user["email"],
        action="production_stage.production_note_added", stage=updated,
        summary=f"Production note added: {updated['stage_name']}",
    )
    return updated


async def start_stage_timer(
    *,
    tenant_id: str,
    stage_id: str,
    user: dict,
    employee_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    if idempotency_key:
        existing = await db.production_timer_sessions.find_one(
            {"tenant_id": tenant_id, "idempotency_key": idempotency_key},
            {"_id": 0},
        )
        if existing:
            return serialize_doc(existing)
    stage = await get_stage(tenant_id=tenant_id, stage_id=stage_id)
    await _assert_stage_action_allowed(stage, user)
    if stage.get("status") in TERMINAL_STATUSES:
        raise ProductionStageError("stage_terminal", "Cannot start timing on a terminal stage")
    employee = await _employee_for_timer(tenant_id, user, employee_id)
    if stage.get("assigned_employee_id") and stage.get("assigned_employee_id") != employee["id"] and not _is_manager(user):
        raise ProductionStageError("timer_employee_forbidden", "Stage is assigned to another employee")
    duplicate = await db.production_timer_sessions.find_one(
        {
            "tenant_id": tenant_id,
            "employee_id": employee["id"],
            "order_item_id": stage["order_item_id"],
            "stage_id": stage_id,
            "status": {"$in": ["active", "paused"]},
        },
        {"_id": 0},
    )
    if duplicate:
        return serialize_doc(duplicate)
    if stage.get("status") == "not_started":
        stage = await transition_stage(tenant_id=tenant_id, stage_id=stage_id, target="in_progress", user=user)
    elif stage.get("status") != "in_progress":
        raise ProductionStageError("stage_not_in_progress", "Resume the stage before starting a timer")
    now = _now()
    session = ProductionTimerSession(
        tenant_id=tenant_id,
        work_order_id=stage["work_order_id"],
        order_id=stage["order_id"],
        order_item_id=stage["order_item_id"],
        workflow_instance_id=stage["workflow_instance_id"],
        stage_id=stage_id,
        stage_key=stage["stage_key"],
        stage_name=stage["stage_name"],
        employee_id=employee["id"],
        employee_user_id=employee.get("linked_user_id"),
        started_at=now,
        notes=notes.strip() if notes and notes.strip() else None,
        idempotency_key=idempotency_key,
        started_by_user_id=user["id"],
    ).model_dump()
    await db.production_timer_sessions.insert_one(prepare_for_mongo(session))
    await db.production_stage_instances.update_one(
        {"tenant_id": tenant_id, "id": stage_id},
        {"$set": {
            "active_timer_session_id": session["id"],
            "active_timer_employee_id": employee["id"],
            "active_timer_started_at": now,
            "updated_at": now,
        }},
    )
    await _record_timer_event(tenant_id=tenant_id, session=session, event_type="started", actor_user_id=user["id"], notes=notes)
    await _append_history(stage_id, {"action": "timer_started", "employee_id": employee["id"], "session_id": session["id"], "actor_user_id": user["id"], "at": now, "notes": notes})
    await _record_stage_audit(
        tenant_id=tenant_id, actor_user_id=user["id"], actor_email=user["email"],
        action="production_stage.timer_started", stage=stage,
        summary=f"Timer started: {stage['stage_name']}",
        diff={"employee_id": employee["id"], "session_id": session["id"], "notes": notes},
    )
    return serialize_doc(session)


async def pause_stage_timer(
    *,
    tenant_id: str,
    stage_id: str,
    user: dict,
    session_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> dict:
    clean_reason = _clean_text(reason)
    if not clean_reason:
        raise ProductionStageError("reason_required", "Pause reason is required")
    stage = await get_stage(tenant_id=tenant_id, stage_id=stage_id)
    query: dict[str, Any] = {"tenant_id": tenant_id, "stage_id": stage_id}
    if session_id:
        query["id"] = session_id
    session = await db.production_timer_sessions.find_one({**query, "status": {"$in": ["active", "paused", "completed", "voided"]}}, {"_id": 0})
    if not session:
        raise ProductionStageError("timer_not_active", "No production timer was found for this stage")
    session = serialize_doc(session)
    await _assert_timer_control_allowed(session, tenant_id, user, "pause")
    if session.get("status") == "paused":
        return session
    if session.get("status") != "active":
        raise ProductionStageError("timer_invalid_state", "Only an active timer can be paused")
    now = _now()
    segment = {"paused_at": now, "paused_by_user_id": user["id"], "reason": clean_reason}
    await db.production_timer_sessions.update_one(
        {"tenant_id": tenant_id, "id": session["id"], "status": "active"},
        {"$set": {"status": "paused", "paused_at": now, "updated_at": now}, "$push": {"pause_segments": segment}},
    )
    paused = serialize_doc(await db.production_timer_sessions.find_one({"tenant_id": tenant_id, "id": session["id"]}, {"_id": 0}))
    await db.production_stage_instances.update_one(
        {"tenant_id": tenant_id, "id": stage_id, "active_timer_session_id": session["id"]},
        {"$set": {"active_timer_session_id": None, "active_timer_employee_id": None, "active_timer_started_at": None, "updated_at": now}},
    )
    await _record_timer_event(tenant_id=tenant_id, session=paused, event_type="paused", actor_user_id=user["id"], reason=clean_reason)
    await _append_history(stage_id, {"action": "timer_paused", "employee_id": session["employee_id"], "session_id": session["id"], "actor_user_id": user["id"], "at": now, "reason": clean_reason})
    await _record_stage_audit(
        tenant_id=tenant_id, actor_user_id=user["id"], actor_email=user["email"],
        action="production_stage.timer_paused", stage=stage,
        summary=f"Timer paused: {stage['stage_name']}", diff={"session_id": session["id"], "reason": clean_reason},
    )
    return paused


async def resume_stage_timer(
    *,
    tenant_id: str,
    stage_id: str,
    user: dict,
    session_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    stage = await get_stage(tenant_id=tenant_id, stage_id=stage_id)
    query: dict[str, Any] = {"tenant_id": tenant_id, "stage_id": stage_id}
    if session_id:
        query["id"] = session_id
    session = await db.production_timer_sessions.find_one({**query, "status": {"$in": ["active", "paused", "completed", "voided"]}}, {"_id": 0})
    if not session:
        raise ProductionStageError("timer_not_active", "No production timer was found for this stage")
    session = serialize_doc(session)
    await _assert_timer_control_allowed(session, tenant_id, user, "resume")
    if session.get("status") == "active":
        return session
    if session.get("status") != "paused":
        raise ProductionStageError("timer_invalid_state", "Only a paused timer can be resumed")
    now = _now()
    segments = list(session.get("pause_segments") or [])
    if segments:
        segments[-1] = {**segments[-1], "resumed_at": now, "resumed_by_user_id": user["id"], "resume_notes": _clean_text(notes)}
    await db.production_timer_sessions.update_one(
        {"tenant_id": tenant_id, "id": session["id"], "status": "paused"},
        {"$set": {"status": "active", "paused_at": None, "pause_segments": segments, "paused_duration_seconds": _timer_paused_seconds({**session, "pause_segments": segments}, now=now), "updated_at": now}},
    )
    await db.production_stage_instances.update_one(
        {"tenant_id": tenant_id, "id": stage_id},
        {"$set": {"active_timer_session_id": session["id"], "active_timer_employee_id": session["employee_id"], "active_timer_started_at": session["started_at"], "updated_at": now}},
    )
    resumed = serialize_doc(await db.production_timer_sessions.find_one({"tenant_id": tenant_id, "id": session["id"]}, {"_id": 0}))
    await _record_timer_event(tenant_id=tenant_id, session=resumed, event_type="resumed", actor_user_id=user["id"], notes=notes)
    await _append_history(stage_id, {"action": "timer_resumed", "employee_id": session["employee_id"], "session_id": session["id"], "actor_user_id": user["id"], "at": now, "notes": notes})
    await _record_stage_audit(
        tenant_id=tenant_id, actor_user_id=user["id"], actor_email=user["email"],
        action="production_stage.timer_resumed", stage=stage,
        summary=f"Timer resumed: {stage['stage_name']}", diff={"session_id": session["id"], "notes": notes},
    )
    return resumed


async def stop_stage_timer(
    *,
    tenant_id: str,
    stage_id: str,
    user: dict,
    session_id: Optional[str] = None,
    notes: Optional[str] = None,
    interruption_reason: Optional[str] = None,
) -> dict:
    stage = await get_stage(tenant_id=tenant_id, stage_id=stage_id)
    query: dict[str, Any] = {"tenant_id": tenant_id, "stage_id": stage_id}
    if session_id:
        query["id"] = session_id
    session = await db.production_timer_sessions.find_one({**query, "status": {"$in": ["active", "paused", "completed", "voided"]}}, {"_id": 0})
    if not session:
        raise ProductionStageError("timer_not_active", "No production timer was found for this stage")
    session = serialize_doc(session)
    await _assert_timer_control_allowed(session, tenant_id, user, "stop")
    if session.get("status") == "completed":
        return session
    if session.get("status") == "voided":
        raise ProductionStageError("timer_invalid_state", "Voided timers cannot be stopped")
    now = _now()
    raw_elapsed = max(0, int((_parse_dt(now) - _parse_dt(session["started_at"])).total_seconds()))
    paused_seconds = _timer_paused_seconds(session, now=now)
    effective_elapsed = max(0, raw_elapsed - paused_seconds)
    updates = {
        "status": "completed",
        "stopped_at": now,
        "elapsed_seconds": raw_elapsed,
        "effective_elapsed_seconds": effective_elapsed,
        "paused_duration_seconds": paused_seconds,
        "notes": notes.strip() if notes and notes.strip() else session.get("notes"),
        "interruption_reason": interruption_reason.strip() if interruption_reason and interruption_reason.strip() else None,
        "stopped_by_user_id": user["id"],
        "updated_at": now,
    }
    result = await db.production_timer_sessions.update_one(
        {"tenant_id": tenant_id, "id": session["id"], "status": {"$in": ["active", "paused"]}},
        {"$set": prepare_for_mongo(updates)},
    )
    if result.modified_count == 0:
        current = await db.production_timer_sessions.find_one({"tenant_id": tenant_id, "id": session["id"]}, {"_id": 0})
        if current and current.get("status") == "completed":
            return serialize_doc(current)
        raise ProductionStageError("timer_conflict", "Timer changed before it could be stopped")
    completed = serialize_doc(await db.production_timer_sessions.find_one({"tenant_id": tenant_id, "id": session["id"]}, {"_id": 0}))
    await _record_timer_event(
        tenant_id=tenant_id, session=completed, event_type="stopped", actor_user_id=user["id"],
        reason=interruption_reason, notes=notes, elapsed_seconds=effective_elapsed,
    )
    await db.production_stage_instances.update_one(
        {"tenant_id": tenant_id, "id": stage_id},
        {"$set": {"active_timer_session_id": None, "active_timer_employee_id": None, "active_timer_started_at": None, "updated_at": now},
         "$inc": {"actual_duration_seconds": effective_elapsed, "timing_entry_count": 1}},
    )
    await _append_history(stage_id, {
        "action": "timer_stopped",
        "employee_id": session["employee_id"],
        "session_id": session["id"],
        "actor_user_id": user["id"],
        "at": now,
        "elapsed_seconds": effective_elapsed,
        "reason": interruption_reason,
        "notes": notes,
    })
    await _record_stage_audit(
        tenant_id=tenant_id, actor_user_id=user["id"], actor_email=user["email"],
        action="production_stage.timer_stopped", stage=stage,
        summary=f"Timer stopped: {stage['stage_name']}",
        diff={"employee_id": session["employee_id"], "session_id": session["id"], "elapsed_seconds": effective_elapsed, "paused_duration_seconds": paused_seconds, "reason": interruption_reason},
    )
    return completed


async def correct_stage_timer(
    *,
    tenant_id: str,
    stage_id: str,
    session_id: str,
    corrected_elapsed_seconds: int,
    reason: str,
    user: dict,
) -> dict:
    _require_manager(user)
    clean_reason = _clean_text(reason)
    if not clean_reason:
        raise ProductionStageError("reason_required", "Correction reason is required")
    found = await db.production_timer_sessions.find_one({"tenant_id": tenant_id, "stage_id": stage_id, "id": session_id}, {"_id": 0})
    session = serialize_doc(found) if found else None
    if not session:
        raise ProductionStageError("timer_not_active", "Timer session not found")
    if session.get("status") != "completed":
        raise ProductionStageError("timer_invalid_state", "Only completed timers can be corrected")
    if session.get("corrected_elapsed_seconds") is not None:
        raise ProductionStageError("timer_conflict", "Timer already has an active correction")
    stage = await get_stage(tenant_id=tenant_id, stage_id=stage_id)
    now = _now()
    original_effective = _timer_effective_seconds(session, now=now)
    corrected = max(0, int(corrected_elapsed_seconds or 0))
    correction = {
        "action": "corrected",
        "original_elapsed_seconds": original_effective,
        "corrected_elapsed_seconds": corrected,
        "reason": clean_reason,
        "actor_user_id": user["id"],
        "at": now,
        "source_session_id": session_id,
    }
    await db.production_timer_sessions.update_one(
        {"tenant_id": tenant_id, "id": session_id, "status": "completed", "corrected_elapsed_seconds": None},
        {"$set": {"corrected_elapsed_seconds": corrected, "updated_at": now}, "$push": {"corrections": correction}},
    )
    delta = corrected - original_effective
    await db.production_stage_instances.update_one({"tenant_id": tenant_id, "id": stage_id}, {"$inc": {"actual_duration_seconds": delta}, "$set": {"updated_at": now}})
    updated = serialize_doc(await db.production_timer_sessions.find_one({"tenant_id": tenant_id, "id": session_id}, {"_id": 0}))
    await _record_timer_event(tenant_id=tenant_id, session=updated, event_type="corrected", actor_user_id=user["id"], reason=clean_reason, elapsed_seconds=corrected)
    await _append_history(stage_id, {"action": "timer_corrected", "session_id": session_id, "actor_user_id": user["id"], "at": now, "reason": clean_reason, "original_elapsed_seconds": original_effective, "corrected_elapsed_seconds": corrected})
    await _record_stage_audit(
        tenant_id=tenant_id, actor_user_id=user["id"], actor_email=user["email"],
        action="production_stage.timer_corrected", stage=stage,
        summary=f"Timer corrected: {stage['stage_name']}", diff=correction,
    )
    return updated


async def void_stage_timer(
    *,
    tenant_id: str,
    stage_id: str,
    session_id: str,
    reason: str,
    confirm: bool,
    user: dict,
) -> dict:
    _require_manager(user)
    clean_reason = _clean_text(reason)
    if not clean_reason:
        raise ProductionStageError("reason_required", "Void reason is required")
    if not confirm:
        raise ProductionStageError("confirmation_required", "Void confirmation is required")
    found = await db.production_timer_sessions.find_one({"tenant_id": tenant_id, "stage_id": stage_id, "id": session_id}, {"_id": 0})
    session = serialize_doc(found) if found else None
    if not session:
        raise ProductionStageError("timer_not_active", "Timer session not found")
    if session.get("status") == "voided":
        return session
    if session.get("status") != "completed":
        raise ProductionStageError("timer_invalid_state", "Only completed timers can be voided")
    stage = await get_stage(tenant_id=tenant_id, stage_id=stage_id)
    now = _now()
    original_effective = _timer_effective_seconds(session, now=now)
    correction = {
        "action": "voided",
        "original_elapsed_seconds": original_effective,
        "effective_elapsed_seconds": 0,
        "reason": clean_reason,
        "actor_user_id": user["id"],
        "at": now,
        "source_session_id": session_id,
    }
    await db.production_timer_sessions.update_one(
        {"tenant_id": tenant_id, "id": session_id, "status": "completed"},
        {"$set": {"status": "voided", "voided_at": now, "voided_by_user_id": user["id"], "void_reason": clean_reason, "updated_at": now}, "$push": {"corrections": correction}},
    )
    await db.production_stage_instances.update_one({"tenant_id": tenant_id, "id": stage_id}, {"$inc": {"actual_duration_seconds": -original_effective, "timing_entry_count": -1}, "$set": {"updated_at": now}})
    updated = serialize_doc(await db.production_timer_sessions.find_one({"tenant_id": tenant_id, "id": session_id}, {"_id": 0}))
    await _record_timer_event(tenant_id=tenant_id, session=updated, event_type="voided", actor_user_id=user["id"], reason=clean_reason, elapsed_seconds=0)
    await _append_history(stage_id, {"action": "timer_voided", "session_id": session_id, "actor_user_id": user["id"], "at": now, "reason": clean_reason, "original_elapsed_seconds": original_effective})
    await _record_stage_audit(
        tenant_id=tenant_id, actor_user_id=user["id"], actor_email=user["email"],
        action="production_stage.timer_voided", stage=stage,
        summary=f"Timer voided: {stage['stage_name']}", diff=correction,
    )
    return updated


def _can_manage_pricing_feedback(user: dict) -> bool:
    return _is_manager(user) and "pricing:write" in _user_permissions(user)


def _area_sqft(item: dict) -> Optional[float]:
    width = item.get("width_inches")
    height = item.get("height_inches")
    try:
        if width and height:
            area = (float(width) * float(height)) / 144.0
            return area if area > 0 else None
    except (TypeError, ValueError):
        return None
    return None


def _feedback_mapping(*, settings: dict, item: dict, planned_seconds: int, actual_seconds: int) -> dict:
    category = item.get("category")
    category_defaults = ((settings.get("category_defaults") or {}).get(category) or {}) if category else {}
    quantity = max(1, int(item.get("quantity") or 1))
    actual_hours = actual_seconds / 3600 if actual_seconds else 0
    if category and "production_labor_hr_per_sqft" in category_defaults:
        area = _area_sqft(item)
        if area:
            existing = float(category_defaults.get("production_labor_hr_per_sqft") or 0)
            suggested = round(actual_hours / (area * quantity), 4)
            return {
                "mapped": True,
                "target_path": f"category_defaults.{category}.production_labor_hr_per_sqft",
                "existing_value": existing,
                "suggested_value": suggested,
                "explanation": "Suggested labor hours per square foot = effective actual production hours divided by item square footage and quantity.",
            }
    if category and "labor_hours_per_unit_default" in category_defaults:
        existing = float(category_defaults.get("labor_hours_per_unit_default") or 0)
        suggested = round(actual_hours / quantity, 4)
        return {
            "mapped": True,
            "target_path": f"category_defaults.{category}.labor_hours_per_unit_default",
            "existing_value": existing,
            "suggested_value": suggested,
            "explanation": "Suggested labor hours per unit = effective actual production hours divided by item quantity.",
        }
    return {
        "mapped": False,
        "target_path": None,
        "existing_value": None,
        "suggested_value": None,
        "explanation": "No safe Pricing Foundation labor field could be mapped from this production evidence, so no value was guessed.",
    }


async def create_pricing_feedback_from_stage(*, tenant_id: str, stage_id: str, user: dict) -> dict:
    if "pricing:read" not in _user_permissions(user):
        raise ProductionStageError("pricing_permission_required", "Pricing permission is required")
    stage = await get_stage(tenant_id=tenant_id, stage_id=stage_id)
    sessions = [
        serialize_doc(s) async for s in db.production_timer_sessions.find(
            {"tenant_id": tenant_id, "stage_id": stage_id, "status": {"$in": ["completed", "voided"]}},
            {"_id": 0},
        ).sort("started_at", 1)
    ]
    if not sessions:
        raise ProductionStageError("pricing_feedback_no_evidence", "No completed timing evidence exists for this stage")
    effective_actual = sum(_timer_effective_seconds(s) for s in sessions)
    planned_seconds = int(stage.get("default_estimated_duration_minutes") or 0) * 60
    variance = effective_actual - planned_seconds
    variance_percent = round((variance / planned_seconds) * 100, 2) if planned_seconds else None
    item = serialize_doc(await db.order_items.find_one({"tenant_id": tenant_id, "id": stage["order_item_id"]}, {"_id": 0}) or {})
    settings = await get_or_init_pricing_settings(tenant_id)
    mapping = _feedback_mapping(settings=settings, item=item, planned_seconds=planned_seconds, actual_seconds=effective_actual)
    session_ids = [s["id"] for s in sessions if s.get("status") != "voided"]
    evidence_key = f"{stage_id}:{','.join(session_ids)}:{planned_seconds}:{effective_actual}"
    existing = await db.production_pricing_feedback.find_one(
        {"tenant_id": tenant_id, "evidence_key": evidence_key, "status": {"$in": ["pending", "unmapped"]}},
        {"_id": 0},
    )
    if existing:
        return serialize_doc(existing)
    status = "pending" if mapping["mapped"] else "unmapped"
    feedback = ProductionPricingFeedback(
        tenant_id=tenant_id,
        work_order_id=stage["work_order_id"],
        order_id=stage["order_id"],
        order_item_id=stage["order_item_id"],
        workflow_instance_id=stage["workflow_instance_id"],
        stage_id=stage_id,
        stage_key=stage["stage_key"],
        stage_name=stage["stage_name"],
        timing_session_ids=session_ids,
        evidence_key=evidence_key,
        production_category=item.get("category"),
        pricing_snapshot_id=item.get("pricing_snapshot_id"),
        pricing_snapshot_summary=item.get("pricing_snapshot") or {},
        planned_seconds=planned_seconds,
        effective_actual_seconds=effective_actual,
        variance_seconds=variance,
        variance_percent=variance_percent,
        target_path=mapping["target_path"],
        existing_value=mapping["existing_value"],
        suggested_value=mapping["suggested_value"],
        suggested_adjustment=(round((mapping["suggested_value"] or 0) - (mapping["existing_value"] or 0), 4) if mapping["mapped"] else None),
        mapped=bool(mapping["mapped"]),
        mapping_status="mapped" if mapping["mapped"] else "unmapped",
        explanation=mapping["explanation"],
        status=status,
        created_by_user_id=user["id"],
        history=[{"action": "created", "actor_user_id": user["id"], "at": _now(), "status": status}],
    ).model_dump()
    try:
        await db.production_pricing_feedback.insert_one(prepare_for_mongo(feedback))
    except DuplicateKeyError:
        return serialize_doc(await db.production_pricing_feedback.find_one({"tenant_id": tenant_id, "evidence_key": evidence_key}, {"_id": 0}))
    await record_audit(
        tenant_id=tenant_id, actor_user_id=user["id"], actor_email=user["email"],
        action="production_pricing_feedback.created", entity_type="production_pricing_feedback", entity_id=feedback["id"],
        summary=f"Production pricing feedback created: {stage['stage_name']}", diff={"stage_id": stage_id, "target_path": feedback.get("target_path"), "status": status},
    )
    return serialize_doc(feedback)


async def list_pricing_feedback(*, tenant_id: str, status: Optional[str], user: dict) -> dict:
    if "pricing:read" not in _user_permissions(user):
        raise ProductionStageError("pricing_permission_required", "Pricing permission is required")
    q: dict[str, Any] = {"tenant_id": tenant_id}
    if status and status != "all":
        q["status"] = status
    items = [serialize_doc(d) async for d in db.production_pricing_feedback.find(q, {"_id": 0}).sort("created_at", -1).limit(100)]
    return {"items": items, "total": len(items)}


async def approve_pricing_feedback(*, tenant_id: str, feedback_id: str, approved_value: Optional[float], reason: Optional[str], user: dict) -> dict:
    if not _can_manage_pricing_feedback(user):
        raise ProductionStageError("pricing_permission_required", "Pricing write manager authority is required")
    feedback = serialize_doc(await db.production_pricing_feedback.find_one({"tenant_id": tenant_id, "id": feedback_id}, {"_id": 0}) or {})
    if not feedback:
        raise ProductionStageError("pricing_feedback_not_found", "Pricing feedback not found")
    if feedback.get("status") != "pending":
        raise ProductionStageError("pricing_feedback_invalid_state", "Only pending mapped feedback can be approved")
    if not feedback.get("mapped") or not feedback.get("target_path"):
        raise ProductionStageError("pricing_feedback_unmapped", "Unmapped feedback cannot be approved")
    clean_reason = _clean_text(reason) or "Approved production timing feedback"
    final_value = float(approved_value if approved_value is not None else feedback["suggested_value"])
    target = str(feedback["target_path"])
    prior_value = feedback.get("existing_value")
    if target.startswith("shop_defaults."):
        field = target.split(".", 1)[1]
        await update_shop_defaults(tenant_id, {field: final_value}, source="production_pricing_feedback")
    elif target.startswith("category_defaults."):
        _, category, field = target.split(".", 2)
        await update_category(tenant_id, category, {field: final_value}, source="production_pricing_feedback")
    else:
        raise ProductionStageError("pricing_feedback_unmapped", "Unsupported Pricing Foundation target")
    now = _now()
    history = {"action": "approved", "actor_user_id": user["id"], "at": now, "reason": clean_reason, "prior_value": prior_value, "approved_value": final_value}
    await db.production_pricing_feedback.update_one(
        {"tenant_id": tenant_id, "id": feedback_id, "status": "pending"},
        {"$set": {"status": "approved", "reviewed_by_user_id": user["id"], "reviewed_at": now, "decision_reason": clean_reason, "prior_value": prior_value, "approved_value": final_value, "applied_at": now, "updated_at": now}, "$push": {"history": history}},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=user["id"], actor_email=user["email"],
        action="production_pricing_feedback.approved", entity_type="production_pricing_feedback", entity_id=feedback_id,
        summary="Production pricing feedback approved", diff={"target_path": target, "prior_value": prior_value, "approved_value": final_value, "reason": clean_reason},
    )
    return serialize_doc(await db.production_pricing_feedback.find_one({"tenant_id": tenant_id, "id": feedback_id}, {"_id": 0}))


async def reject_pricing_feedback(*, tenant_id: str, feedback_id: str, reason: str, user: dict) -> dict:
    if not _can_manage_pricing_feedback(user):
        raise ProductionStageError("pricing_permission_required", "Pricing write manager authority is required")
    clean_reason = _clean_text(reason)
    if not clean_reason:
        raise ProductionStageError("reason_required", "Rejection reason is required")
    feedback = serialize_doc(await db.production_pricing_feedback.find_one({"tenant_id": tenant_id, "id": feedback_id}, {"_id": 0}) or {})
    if not feedback:
        raise ProductionStageError("pricing_feedback_not_found", "Pricing feedback not found")
    if feedback.get("status") not in {"pending", "unmapped"}:
        raise ProductionStageError("pricing_feedback_invalid_state", "Feedback has already been reviewed")
    now = _now()
    history = {"action": "rejected", "actor_user_id": user["id"], "at": now, "reason": clean_reason}
    await db.production_pricing_feedback.update_one(
        {"tenant_id": tenant_id, "id": feedback_id, "status": {"$in": ["pending", "unmapped"]}},
        {"$set": {"status": "rejected", "reviewed_by_user_id": user["id"], "reviewed_at": now, "decision_reason": clean_reason, "updated_at": now}, "$push": {"history": history}},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=user["id"], actor_email=user["email"],
        action="production_pricing_feedback.rejected", entity_type="production_pricing_feedback", entity_id=feedback_id,
        summary="Production pricing feedback rejected", diff={"reason": clean_reason},
    )
    return serialize_doc(await db.production_pricing_feedback.find_one({"tenant_id": tenant_id, "id": feedback_id}, {"_id": 0}))
