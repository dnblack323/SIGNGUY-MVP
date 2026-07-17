"""EC11 Phase 11C - live Work Order / Order Item production stages.

This layer snapshots Phase 11A workflow definitions into live instances tied
to Work Orders and production-required Order Items. It remains deliberately
read/write only for stages: no timers, payroll entries, labor ledgers, kiosk,
or analytics records are created here.
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
    ProductionStageInstance,
    ProductionWorkflowInstance,
)
from .audit import record_audit
from .certification_service import check_work_order_assignment
from .notifications import notify
from .production_workflow_service import resolve_workflow

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
    return {"work_order_id": work_order_id, "order_id": wo["order_id"], "workflow_instances": instances, "stages": stages}


async def get_stage(*, tenant_id: str, stage_id: str) -> dict:
    stage = await db.production_stage_instances.find_one({"tenant_id": tenant_id, "id": stage_id}, {"_id": 0})
    if not stage:
        raise ProductionStageError("stage_not_found", "Production stage not found")
    return serialize_doc(stage)


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
