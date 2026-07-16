"""EC11 Phase 11A - production workflow definitions and stage contracts.

Owns reusable workflow definitions only. It deliberately does not generate
live Work Order stages, production timer sessions, payroll records, or
analytics rows.
"""
from __future__ import annotations

import copy
import re
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.production_workflow import ProductionWorkflowDefinition
from .audit import record_audit

STAGE_STATUSES = ("not_started", "in_progress", "waiting", "blocked", "completed", "skipped")

STAGE_TRANSITIONS: dict[str, set[str]] = {
    "not_started": {"in_progress", "waiting", "blocked", "completed", "skipped"},
    "in_progress": {"waiting", "blocked", "completed", "skipped"},
    "waiting": {"in_progress", "blocked", "completed", "skipped"},
    "blocked": {"in_progress", "waiting", "completed", "skipped"},
    "completed": set(),
    "skipped": set(),
}

REOPENABLE_STAGE_STATUSES = {"completed", "skipped"}


class ProductionWorkflowError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_]{1,63}$")


def _slug(value: str) -> str:
    raw = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")
    return raw[:64] or "workflow"


def _now() -> str:
    return utc_now().isoformat()


def _stage_payload(stage: dict[str, Any], *, sequence: Optional[int] = None, existing: Optional[dict] = None) -> dict:
    display = (stage.get("display_name") or stage.get("name") or (existing or {}).get("display_name") or "").strip()
    key = (stage.get("stage_key") or (existing or {}).get("stage_key") or _slug(display)).strip()
    if not display:
        raise ProductionWorkflowError("stage_name_required", "Stage display name is required")
    if not _KEY_RE.match(key):
        raise ProductionWorkflowError("invalid_stage_key", "Stage key must be lowercase letters, numbers, and underscores")
    seq = int(stage.get("sequence") if stage.get("sequence") is not None else (sequence if sequence is not None else (existing or {}).get("sequence", 1)))
    if seq < 1:
        raise ProductionWorkflowError("invalid_stage_order", "Stage sequence must be positive")
    now = _now()
    base = dict(existing or {})
    def val(field: str, default: Any = None) -> Any:
        picked = stage.get(field, None)
        if picked is None:
            return base.get(field, default)
        return picked
    base.update({
        "stage_key": key,
        "display_name": display,
        "description": val("description"),
        "sequence": seq,
        "active": bool(val("active", True)),
        "required": bool(val("required", True)),
        "may_skip": bool(val("may_skip", True)),
        "requires_reason_to_skip": bool(val("requires_reason_to_skip", False)),
        "default_role": val("default_role"),
        "default_estimated_duration_minutes": val("default_estimated_duration_minutes"),
        "due_date_offset_days": val("due_date_offset_days"),
        "customer_visible": bool(val("customer_visible", False)),
        "employee_visible": bool(val("employee_visible", True)),
        "requires_previous_stage_complete": bool(val("requires_previous_stage_complete", True)),
        "proof_gate_type": val("proof_gate_type"),
        "equipment_requirement_ids": list(val("equipment_requirement_ids", []) or []),
        "certification_requirement_ids": list(val("certification_requirement_ids", []) or []),
        "checklist_template_ids": list(val("checklist_template_ids", []) or []),
        "color": val("color"),
        "icon": val("icon"),
        "metadata": dict(val("metadata", {}) or {}),
        "updated_at": now,
    })
    base.setdefault("id", stage.get("id") or key)
    base.setdefault("created_at", now)
    return base


def _validate_stage_set(stages: list[dict]) -> list[dict]:
    seen_keys: set[str] = set()
    seen_active_seq: set[int] = set()
    normalized = []
    for idx, stage in enumerate(stages, start=1):
        s = _stage_payload(stage, sequence=stage.get("sequence") or idx)
        if s["stage_key"] in seen_keys:
            raise ProductionWorkflowError("duplicate_stage_key", "Stage keys must be unique within a workflow")
        if s.get("active", True) and s["sequence"] in seen_active_seq:
            raise ProductionWorkflowError("invalid_stage_order", "Stage sequences must be unique")
        seen_keys.add(s["stage_key"])
        if s.get("active", True):
            seen_active_seq.add(s["sequence"])
        normalized.append(s)
    return sorted(normalized, key=lambda s: (not s.get("active", True), s["sequence"]))


STARTER_WORKFLOWS: list[dict[str, Any]] = [
    {
        "name": "General Sign Production",
        "workflow_key": "starter_general_sign_production",
        "description": "A compact default workflow for typical sign jobs.",
        "stages": ["Design", "Proof Approval", "Production", "Quality Check", "Ready"],
    },
    {"name": "Banner Production", "workflow_key": "starter_banner_production", "category_ids": ["banners"], "stages": ["Design", "Print", "Finish", "Quality Check", "Ready"]},
    {"name": "Rigid Sign / Panel Production", "workflow_key": "starter_rigid_sign_panel", "category_ids": ["rigid_signs"], "stages": ["Design", "Print or Cut", "Mount", "Finish", "Ready"]},
    {"name": "Cut Vinyl / Lettering", "workflow_key": "starter_cut_vinyl_lettering", "category_ids": ["cut_vinyl"], "stages": ["Design", "Cut", "Weed", "Mask", "Ready"]},
    {"name": "Digital Print and Lamination", "workflow_key": "starter_digital_print_lamination", "category_ids": ["digital_print"], "stages": ["Preflight", "Print", "Laminate", "Trim", "Ready"]},
    {"name": "Apparel Production", "workflow_key": "starter_apparel_production", "category_ids": ["apparel"], "stages": ["Art Prep", "Production", "Cure or Finish", "Quality Check", "Ready"]},
    {"name": "Vehicle Graphics / Basic Wrap Production", "workflow_key": "starter_vehicle_graphics_basic_wrap", "category_ids": ["vehicle_graphics"], "stages": ["Design", "Print", "Laminate", "Install Prep", "Install"]},
    {"name": "Installation-Only Work", "workflow_key": "starter_installation_only", "category_ids": ["installation"], "stages": ["Schedule", "Prep", "Install", "Inspection", "Complete"]},
    {"name": "Custom / Manual Workflow", "workflow_key": "starter_custom_manual", "stages": ["Plan", "Do Work", "Review", "Complete"]},
]


def _starter_stage_rows(names: list[str]) -> list[dict]:
    rows = []
    for i, name in enumerate(names, start=1):
        rows.append(_stage_payload({
            "stage_key": _slug(name),
            "display_name": name,
            "sequence": i,
            "required": True,
            "may_skip": name not in {"Production", "Do Work"},
            "employee_visible": True,
            "customer_visible": name in {"Proof Approval", "Install", "Complete", "Ready"},
        }))
    return rows


async def seed_starter_workflows(*, tenant_id: str, actor_user_id: str = "system") -> int:
    inserted = 0
    for starter in STARTER_WORKFLOWS:
        existing = await db.production_workflows.find_one({"tenant_id": tenant_id, "workflow_key": starter["workflow_key"]})
        if existing:
            continue
        doc = ProductionWorkflowDefinition(
            tenant_id=tenant_id,
            name=starter["name"],
            description=starter.get("description"),
            workflow_key=starter["workflow_key"],
            scope_type="system_starter",
            category_ids=starter.get("category_ids", []),
            system_starter_key=starter["workflow_key"],
            is_tenant_default=starter["workflow_key"] == "starter_general_sign_production",
            stages=_starter_stage_rows(starter["stages"]),
            created_by_user_id=actor_user_id,
            updated_by_user_id=actor_user_id,
        ).model_dump()
        await db.production_workflows.insert_one(prepare_for_mongo(doc))
        inserted += 1
    if not await db.production_workflows.find_one({"tenant_id": tenant_id, "is_tenant_default": True, "active": True, "archived_at": None}):
        await db.production_workflows.update_one(
            {"tenant_id": tenant_id, "workflow_key": "starter_general_sign_production"},
            {"$set": {"is_tenant_default": True, "updated_at": _now()}},
        )
    return inserted


async def list_workflows(*, tenant_id: str, include_archived: bool = False, seed: bool = True) -> list[dict]:
    if seed:
        await seed_starter_workflows(tenant_id=tenant_id)
    q: dict[str, Any] = {"tenant_id": tenant_id}
    if not include_archived:
        q["archived_at"] = None
    cur = db.production_workflows.find(q, {"_id": 0}).sort([("is_tenant_default", -1), ("name", 1)])
    return [serialize_doc(d) async for d in cur]


async def get_workflow(*, tenant_id: str, workflow_id: str) -> dict:
    doc = await db.production_workflows.find_one({"id": workflow_id, "tenant_id": tenant_id}, {"_id": 0})
    if not doc:
        raise ProductionWorkflowError("workflow_not_found", "Production workflow not found")
    doc["stages"] = sorted(doc.get("stages") or [], key=lambda s: s.get("sequence", 0))
    return serialize_doc(doc)


async def create_workflow(*, tenant_id: str, payload: dict[str, Any], actor_user_id: str, actor_email: str) -> dict:
    name = (payload.get("name") or "").strip()
    if not name:
        raise ProductionWorkflowError("workflow_name_required", "Workflow name is required")
    key = (payload.get("workflow_key") or _slug(name)).strip()
    if not _KEY_RE.match(key):
        raise ProductionWorkflowError("invalid_workflow_key", "Workflow key must be lowercase letters, numbers, and underscores")
    if await db.production_workflows.find_one({"tenant_id": tenant_id, "workflow_key": key}):
        raise ProductionWorkflowError("workflow_key_exists", "Workflow key already exists")
    stages = _validate_stage_set(payload.get("stages") or [])
    doc = ProductionWorkflowDefinition(
        tenant_id=tenant_id,
        name=name,
        description=payload.get("description"),
        workflow_key=key,
        scope_type=payload.get("scope_type") or "reusable_custom",
        category_ids=list(payload.get("category_ids") or []),
        stages=stages,
        created_by_user_id=actor_user_id,
        updated_by_user_id=actor_user_id,
    ).model_dump()
    await db.production_workflows.insert_one(prepare_for_mongo(doc))
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="production_workflow.created", entity_type="production_workflow", entity_id=doc["id"],
        summary=f"Production workflow created: {name}", diff={"workflow_key": key, "stage_count": len(stages)},
    )
    return serialize_doc(doc)


def _assert_content_editable(doc: dict) -> None:
    if doc.get("scope_type") == "system_starter":
        raise ProductionWorkflowError("starter_workflow_immutable", "Duplicate a starter workflow before editing its contents")


async def update_workflow(*, tenant_id: str, workflow_id: str, changes: dict[str, Any], actor_user_id: str, actor_email: str) -> dict:
    doc = await get_workflow(tenant_id=tenant_id, workflow_id=workflow_id)
    _assert_content_editable(doc)
    allowed = {"name", "description", "workflow_key"}
    updates = {k: v for k, v in changes.items() if k in allowed}
    if "name" in updates and not str(updates["name"]).strip():
        raise ProductionWorkflowError("workflow_name_required", "Workflow name is required")
    if "workflow_key" in updates:
        key = str(updates["workflow_key"]).strip()
        if not _KEY_RE.match(key):
            raise ProductionWorkflowError("invalid_workflow_key", "Workflow key must be lowercase letters, numbers, and underscores")
        existing = await db.production_workflows.find_one({"tenant_id": tenant_id, "workflow_key": key, "id": {"$ne": workflow_id}})
        if existing:
            raise ProductionWorkflowError("workflow_key_exists", "Workflow key already exists")
        updates["workflow_key"] = key
    if not updates:
        return doc
    updates.update({"updated_at": _now(), "updated_by_user_id": actor_user_id, "version": int(doc.get("version") or 1) + 1})
    await db.production_workflows.update_one({"id": workflow_id, "tenant_id": tenant_id}, {"$set": updates})
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="production_workflow.updated", entity_type="production_workflow", entity_id=workflow_id,
        summary=f"Production workflow updated: {updates.get('name') or doc['name']}", diff={"fields": sorted(updates.keys())},
    )
    return await get_workflow(tenant_id=tenant_id, workflow_id=workflow_id)


async def duplicate_workflow(*, tenant_id: str, workflow_id: str, actor_user_id: str, actor_email: str, name: Optional[str] = None) -> dict:
    src = await get_workflow(tenant_id=tenant_id, workflow_id=workflow_id)
    base_key = _slug(name or f"{src['workflow_key']}_copy")
    key = base_key
    i = 2
    while await db.production_workflows.find_one({"tenant_id": tenant_id, "workflow_key": key}):
        key = f"{base_key}_{i}"[:64]
        i += 1
    now = _now()
    stages = copy.deepcopy(src.get("stages") or [])
    for s in stages:
        s["created_at"] = now
        s["updated_at"] = now
    doc = ProductionWorkflowDefinition(
        tenant_id=tenant_id,
        name=name or f"Copy of {src['name']}",
        description=src.get("description"),
        workflow_key=key,
        scope_type="reusable_custom",
        source_template_id=src["id"],
        stages=stages,
        created_by_user_id=actor_user_id,
        updated_by_user_id=actor_user_id,
    ).model_dump()
    await db.production_workflows.insert_one(prepare_for_mongo(doc))
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="production_workflow.duplicated", entity_type="production_workflow", entity_id=doc["id"],
        summary=f"Production workflow duplicated from {src['name']}", diff={"source_workflow_id": workflow_id},
    )
    return serialize_doc(doc)


async def set_archive_state(*, tenant_id: str, workflow_id: str, archived: bool, actor_user_id: str, actor_email: str) -> dict:
    doc = await get_workflow(tenant_id=tenant_id, workflow_id=workflow_id)
    now = _now()
    updates = {
        "archived_at": now if archived else None,
        "active": not archived,
        "is_tenant_default": False if archived else bool(doc.get("is_tenant_default", False)),
        "updated_at": now,
        "updated_by_user_id": actor_user_id,
    }
    await db.production_workflows.update_one({"id": workflow_id, "tenant_id": tenant_id}, {"$set": updates})
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="production_workflow.archived" if archived else "production_workflow.restored",
        entity_type="production_workflow", entity_id=workflow_id,
        summary=f"Production workflow {'archived' if archived else 'restored'}: {doc['name']}",
    )
    return await get_workflow(tenant_id=tenant_id, workflow_id=workflow_id)


async def set_tenant_default(*, tenant_id: str, workflow_id: str, actor_user_id: str, actor_email: str) -> dict:
    doc = await get_workflow(tenant_id=tenant_id, workflow_id=workflow_id)
    if doc.get("archived_at") or not doc.get("active", True):
        raise ProductionWorkflowError("workflow_archived", "Archived workflows cannot be tenant default")
    await db.production_workflows.update_many({"tenant_id": tenant_id, "is_tenant_default": True}, {"$set": {"is_tenant_default": False, "updated_at": _now()}})
    await db.production_workflows.update_one(
        {"id": workflow_id, "tenant_id": tenant_id},
        {"$set": {"is_tenant_default": True, "updated_at": _now(), "updated_by_user_id": actor_user_id}},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="production_workflow.tenant_default_changed", entity_type="production_workflow", entity_id=workflow_id,
        summary=f"Tenant default production workflow changed to {doc['name']}",
    )
    return await get_workflow(tenant_id=tenant_id, workflow_id=workflow_id)


async def assign_categories(*, tenant_id: str, workflow_id: str, category_ids: list[str], actor_user_id: str, actor_email: str) -> dict:
    doc = await get_workflow(tenant_id=tenant_id, workflow_id=workflow_id)
    if doc.get("archived_at") or not doc.get("active", True):
        raise ProductionWorkflowError("workflow_archived", "Archived workflows cannot be assigned to categories")
    clean = sorted({c.strip() for c in category_ids if c and c.strip()})
    for cat in clean:
        await db.production_workflows.update_many(
            {"tenant_id": tenant_id, "id": {"$ne": workflow_id}, "category_ids": cat},
            {"$pull": {"category_ids": cat}, "$set": {"updated_at": _now()}},
        )
    scope = "category" if clean else ("tenant_default" if doc.get("is_tenant_default") else "reusable_custom")
    await db.production_workflows.update_one(
        {"id": workflow_id, "tenant_id": tenant_id},
        {"$set": {"category_ids": clean, "scope_type": scope, "updated_at": _now(), "updated_by_user_id": actor_user_id}},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="production_workflow.category_assignment_changed", entity_type="production_workflow", entity_id=workflow_id,
        summary=f"Production workflow category assignment changed: {doc['name']}", diff={"category_ids": clean},
    )
    return await get_workflow(tenant_id=tenant_id, workflow_id=workflow_id)


async def resolve_workflow(*, tenant_id: str, category_id: Optional[str] = None, explicit_workflow_id: Optional[str] = None, seed: bool = True) -> dict:
    if seed:
        await seed_starter_workflows(tenant_id=tenant_id)
    base_q = {"tenant_id": tenant_id, "active": True, "archived_at": None}
    if explicit_workflow_id:
        doc = await db.production_workflows.find_one({**base_q, "id": explicit_workflow_id}, {"_id": 0})
        if doc:
            return {"source": "order_item_override", "workflow": serialize_doc(doc)}
    if category_id:
        doc = await db.production_workflows.find_one({**base_q, "category_ids": category_id}, {"_id": 0}, sort=[("updated_at", -1)])
        if doc:
            return {"source": "category", "workflow": serialize_doc(doc)}
    doc = await db.production_workflows.find_one({**base_q, "is_tenant_default": True}, {"_id": 0}, sort=[("updated_at", -1)])
    if doc:
        return {"source": "tenant_default", "workflow": serialize_doc(doc)}
    return {"source": "manual_no_workflow", "workflow": None}


async def add_stage(*, tenant_id: str, workflow_id: str, payload: dict[str, Any], actor_user_id: str, actor_email: str) -> dict:
    doc = await get_workflow(tenant_id=tenant_id, workflow_id=workflow_id)
    _assert_content_editable(doc)
    stages = list(doc.get("stages") or [])
    next_seq = max([int(s.get("sequence", 0)) for s in stages] or [0]) + 1
    new_stage = _stage_payload(payload, sequence=payload.get("sequence") or next_seq)
    if any(s["stage_key"] == new_stage["stage_key"] for s in stages):
        raise ProductionWorkflowError("duplicate_stage_key", "Stage keys must be unique within a workflow")
    stages.append(new_stage)
    stages = _validate_stage_set(stages)
    await _save_stages(tenant_id, workflow_id, stages, actor_user_id)
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="production_workflow.stage_added", entity_type="production_workflow", entity_id=workflow_id,
        summary=f"Stage added: {new_stage['display_name']}", diff={"stage_key": new_stage["stage_key"]},
    )
    return await get_workflow(tenant_id=tenant_id, workflow_id=workflow_id)


async def update_stage(*, tenant_id: str, workflow_id: str, stage_key: str, payload: dict[str, Any], actor_user_id: str, actor_email: str) -> dict:
    doc = await get_workflow(tenant_id=tenant_id, workflow_id=workflow_id)
    _assert_content_editable(doc)
    stages = list(doc.get("stages") or [])
    idx = next((i for i, s in enumerate(stages) if s.get("stage_key") == stage_key), None)
    if idx is None:
        raise ProductionWorkflowError("stage_not_found", "Stage not found")
    updated = _stage_payload(payload, existing=stages[idx])
    for i, s in enumerate(stages):
        if i != idx and s.get("stage_key") == updated["stage_key"]:
            raise ProductionWorkflowError("duplicate_stage_key", "Stage keys must be unique within a workflow")
    stages[idx] = updated
    stages = _validate_stage_set(stages)
    await _save_stages(tenant_id, workflow_id, stages, actor_user_id)
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="production_workflow.stage_updated", entity_type="production_workflow", entity_id=workflow_id,
        summary=f"Stage updated: {updated['display_name']}", diff={"stage_key": updated["stage_key"]},
    )
    return await get_workflow(tenant_id=tenant_id, workflow_id=workflow_id)


async def reorder_stages(*, tenant_id: str, workflow_id: str, stage_keys: list[str], actor_user_id: str, actor_email: str) -> dict:
    doc = await get_workflow(tenant_id=tenant_id, workflow_id=workflow_id)
    _assert_content_editable(doc)
    stages = list(doc.get("stages") or [])
    active_keys = [s["stage_key"] for s in stages if s.get("active", True)]
    if set(stage_keys) != set(active_keys) or len(stage_keys) != len(active_keys):
        raise ProductionWorkflowError("invalid_stage_order", "Reorder must include each active stage exactly once")
    order = {key: i + 1 for i, key in enumerate(stage_keys)}
    for s in stages:
        if s.get("active", True):
            s["sequence"] = order[s["stage_key"]]
            s["updated_at"] = _now()
    stages = _validate_stage_set(stages)
    await _save_stages(tenant_id, workflow_id, stages, actor_user_id)
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="production_workflow.stage_reordered", entity_type="production_workflow", entity_id=workflow_id,
        summary=f"Stages reordered for {doc['name']}", diff={"stage_keys": stage_keys},
    )
    return await get_workflow(tenant_id=tenant_id, workflow_id=workflow_id)


async def archive_stage(*, tenant_id: str, workflow_id: str, stage_key: str, actor_user_id: str, actor_email: str) -> dict:
    doc = await get_workflow(tenant_id=tenant_id, workflow_id=workflow_id)
    _assert_content_editable(doc)
    stages = list(doc.get("stages") or [])
    found = False
    for s in stages:
        if s.get("stage_key") == stage_key:
            s["active"] = False
            s["updated_at"] = _now()
            found = True
            break
    if not found:
        raise ProductionWorkflowError("stage_not_found", "Stage not found")
    await _save_stages(tenant_id, workflow_id, stages, actor_user_id)
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="production_workflow.stage_archived", entity_type="production_workflow", entity_id=workflow_id,
        summary=f"Stage archived: {stage_key}", diff={"stage_key": stage_key},
    )
    return await get_workflow(tenant_id=tenant_id, workflow_id=workflow_id)


async def _save_stages(tenant_id: str, workflow_id: str, stages: list[dict], actor_user_id: str) -> None:
    await db.production_workflows.update_one(
        {"id": workflow_id, "tenant_id": tenant_id},
        {
            "$set": {
                "stages": [prepare_for_mongo(s) for s in stages],
                "updated_at": _now(),
                "updated_by_user_id": actor_user_id,
            },
            "$inc": {"version": 1},
        },
    )
