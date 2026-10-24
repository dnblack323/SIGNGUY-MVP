"""Guided Onboarding V1 — tenant-scoped progress engine.

Onboarding never stores shop configuration. Each step is owned by a real MVP
feature (settings, Pricing Foundation, employees, production workflows,
customers, orders); this service only

* records the owner's position and the skipped/deferred/reviewed choices
  (`tenant_onboarding_instances`, `onboarding_task_states`), and
* derives completion by *reading* the owning collections, so a change made later in
  Settings (or anywhere else) is reflected here without any sync step.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.permissions import has_platform_admin_access
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.onboarding import (
    OnboardingProgramDefinition,
    OnboardingTaskState,
    TenantOnboardingInstance,
)
from . import settings as settings_service
from .activity import record_activity_with_audit
from .entitlements import has_entitlement
from .onboarding_catalog import ONBOARDING_TASKS, STAGES, TASKS_BY_KEY

PROGRAM_KEY = "shop_launch_v1"
PROGRAM_VERSION = 2
OPEN_STATUSES = {"not_started", "in_progress"}
VALID_STATUSES = {"not_started", "in_progress", "completed", "skipped", "deferred", "blocked"}


class OnboardingError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _now_iso() -> str:
    return utc_now().isoformat()


def _is_platform_admin(user: dict) -> bool:
    return has_platform_admin_access(user)


def _is_tenant_admin(user: dict) -> bool:
    return user.get("role") in {"owner", "admin"} or _is_platform_admin(user)


def _require_tenant_admin(user: dict) -> None:
    if not _is_tenant_admin(user):
        raise OnboardingError("onboarding_write_required", "Owner or admin access is required", 403)


def _require_platform_admin(user: dict) -> None:
    if not _is_platform_admin(user):
        raise OnboardingError("platform_admin_required", "Platform admin access is required", 403)


async def _audit(user: dict, action: str, entity_type: str, entity_id: str, summary: str, diff: Optional[dict[str, Any]] = None) -> None:
    await record_activity_with_audit(
        tenant_id=user["tenant_id"],
        actor_user_id=user["id"],
        actor_email=user.get("email", "onboarding"),
        module="onboarding",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        diff=diff or {},
    )


def _program_doc() -> dict[str, Any]:
    return OnboardingProgramDefinition(
        program_key=PROGRAM_KEY,
        version=PROGRAM_VERSION,
        status="active",
        title="Guided shop setup",
        description="Three-stage guided setup for SignGuy AI.",
        tasks=deepcopy(ONBOARDING_TASKS),
        effective_at=_now_iso(),
    ).model_dump()


async def bootstrap_platform(user: dict) -> dict:
    _require_platform_admin(user)
    inserted = {"program_definitions": 0, "help_articles": 0, "contextual_help": 0}
    res = await db.onboarding_program_definitions.update_one(
        {"program_key": PROGRAM_KEY, "version": PROGRAM_VERSION},
        {"$setOnInsert": prepare_for_mongo(_program_doc())},
        upsert=True,
    )
    inserted["program_definitions"] += int(bool(res.upserted_id))
    from . import help_center

    help_result = await help_center.bootstrap_help_content(user)
    inserted["help_articles"] = help_result["inserted"].get("help_articles", 0)
    inserted["contextual_help"] = help_result["inserted"].get("contextual_help", 0)
    return {"program_key": PROGRAM_KEY, "program_version": PROGRAM_VERSION, "inserted": inserted}


async def _ensure_instance(user: dict) -> dict[str, Any]:
    existing = await db.tenant_onboarding_instances.find_one({"tenant_id": user["tenant_id"], "program_key": PROGRAM_KEY}, {"_id": 0})
    if existing:
        return serialize_doc(existing)
    doc = TenantOnboardingInstance(
        tenant_id=user["tenant_id"],
        program_key=PROGRAM_KEY,
        program_version=PROGRAM_VERSION,
        status="in_progress",
        started_at=_now_iso(),
        created_by_user_id=user.get("id"),
        updated_by_user_id=user.get("id"),
    ).model_dump()
    try:
        await db.tenant_onboarding_instances.insert_one(prepare_for_mongo(doc))
    except DuplicateKeyError:
        doc = await db.tenant_onboarding_instances.find_one({"tenant_id": user["tenant_id"], "program_key": PROGRAM_KEY}, {"_id": 0})
    return serialize_doc(doc)


def _has_source(field_sources: dict[str, Any], prefix: str, suffix: str = "") -> bool:
    return any(k.startswith(prefix) and k.endswith(suffix) for k in field_sources)


async def _canonical_completion(tenant_id: str) -> dict[str, bool]:
    """Completion read from the records that own each setting (no onboarding copy)."""
    settings = await settings_service.list_all(tenant_id=tenant_id)
    company = settings.get("company_profile") or {}
    branding = settings.get("branding") or {}
    portal = settings.get("portal") or {}
    notifications = settings.get("notifications") or {}
    invoicing = settings.get("invoicing_defaults") or {}
    pricing = await db.pricing_settings.find_one({"tenant_id": tenant_id}, {"_id": 0, "field_sources": 1}) or {}
    sources = pricing.get("field_sources") or {}
    # Only fields an owner (or the pricing quiz) actually wrote have a source entry; starter values do not.
    labor_done = _has_source(sources, "shop_defaults.", "_hourly_rate")
    pricing_config_done = _has_source(sources, "category_defaults.") or _has_source(sources, "shop_defaults.default_overhead_percent") or _has_source(sources, "shop_defaults.target_profit_margin_percent")

    async def count(collection: str, filt: Optional[dict[str, Any]] = None) -> int:
        return await db[collection].count_documents({"tenant_id": tenant_id, **(filt or {})})

    employees = await count("employees", {"status": {"$nin": ["terminated", "archived", "inactive"]}})
    return {
        "company_profile": bool(company.get("shop_name") or company.get("legal_name")),
        "company_contact": bool((company.get("phone") or company.get("email")) and company.get("address_line1")),
        "branding": bool(branding.get("primary_color") or branding.get("logo_file_id") or branding.get("email_signature")),
        "labor_rates": labor_done,
        "production_workflow": await count("production_workflows", {"is_tenant_default": True, "active": True, "archived_at": None}) > 0,
        "first_employee": employees > 0,
        "payment_preferences": bool(invoicing.get("payment_terms") or invoicing.get("invoice_footer")),
        "portal_preferences": "enabled" in portal,
        "first_customer": await count("customers", {"archived": {"$ne": True}}) > 0,
        "first_order": await count("orders") > 0,
        "employees_permissions": employees > 1 or await count("users", {"is_active": True}) > 1,
        "pricing_foundation": pricing_config_done,
        "materials": await count("materials") > 0,
        "equipment": await count("equipment") > 0,
        "categories": _has_source(sources, "category_defaults."),
        "documents": await count("documents") > 0 or bool(branding.get("logo_file_id")),
        "notifications": bool(notifications),
        "customer_portal": await count("portal_identities", {"status": "active"}) > 0,
        "invoice_deposit": _has_source(sources, "shop_defaults.deposit_percentage") or bool(invoicing),
    }


async def _availability(tenant_id: str, task: dict[str, Any]) -> dict[str, Any]:
    key = task.get("feature_key")
    if not key:
        return {"available": True, "message": None}
    if await has_entitlement(tenant_id=tenant_id, feature_key=key):
        return {"available": True, "message": None}
    return {"available": False, "message": "Not included in your current plan. You can finish onboarding without it."}


def _merge_tasks(tasks: list[dict[str, Any]], states: dict[str, dict[str, Any]], canonical: dict[str, bool], availability: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for task in tasks:
        state = states.get(task["task_key"]) or {}
        stored = state.get("status", "not_started")
        derived = task["detect"] == "canonical" and canonical.get(task["task_key"], False)
        status = "completed" if derived else stored
        if task["detect"] == "canonical" and not derived and stored == "completed":
            status = "not_started"  # setup was undone elsewhere — completion must reflect real records
        blocked_reason = state.get("blocked_reason") if status == "blocked" else None
        merged[task["task_key"]] = {
            **task,
            "status": status,
            "skipped_reason": state.get("skipped_reason"),
            "deferred_until": state.get("deferred_until"),
            "blocked_reason": blocked_reason,
            "completed_at": state.get("completed_at"),
            "canonical_complete": bool(derived),
            "availability": availability[task["task_key"]],
        }
    for task in merged.values():
        if task["status"] not in OPEN_STATUSES:
            continue
        waiting = [merged[d]["title"] for d in task["dependencies"] if d in merged and merged[d]["status"] != "completed"]
        if waiting:
            task["status"] = "blocked"
            task["blocked_reason"] = f"Finish {', '.join(waiting)} first."
        elif not task["availability"]["available"]:
            task["status"] = "blocked"
            task["blocked_reason"] = task["availability"]["message"]
    return [merged[t["task_key"]] for t in tasks]


def _stage_progress(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for stage in STAGES:
        rows = [t for t in tasks if t["stage"] == stage["key"]]
        required = [t for t in rows if t["level"] == "required"]
        done = [t for t in rows if t["status"] == "completed"]
        required_done = [t for t in required if t["status"] == "completed"]
        out.append({
            **stage,
            "total_tasks": len(rows),
            "completed_tasks": len(done),
            "required_tasks": len(required),
            "completed_required_tasks": len(required_done),
            "required_complete": len(required_done) == len(required),
            "percent_complete": round(len(done) / max(len(rows), 1) * 100),
        })
    return out


async def dashboard(user: dict) -> dict[str, Any]:
    instance = await _ensure_instance(user)
    tenant_id = user["tenant_id"]
    canonical = await _canonical_completion(tenant_id)
    states = {
        doc["task_key"]: serialize_doc(doc)
        async for doc in db.onboarding_task_states.find({"tenant_id": tenant_id, "program_key": PROGRAM_KEY}, {"_id": 0})
    }
    availability = {t["task_key"]: await _availability(tenant_id, t) for t in ONBOARDING_TASKS}
    tasks = _merge_tasks(ONBOARDING_TASKS, states, canonical, availability)
    stages = _stage_progress(tasks)
    completed = [t for t in tasks if t["status"] == "completed"]
    required = [t for t in tasks if t["level"] == "required"]
    required_done = [t for t in required if t["status"] == "completed"]
    progress = {
        "total_tasks": len(tasks),
        "completed_tasks": len(completed),
        "required_tasks": len(required),
        "completed_required_tasks": len(required_done),
        "percent_complete": round(len(completed) / max(len(tasks), 1) * 100),
    }
    next_task = next((t for t in tasks if t["status"] in OPEN_STATUSES and t["level"] == "required"), None) \
        or next((t for t in tasks if t["status"] in OPEN_STATUSES), None)
    quick = stages[0]
    # A gentle, dismissible invitation — never an automatic redirect.
    prompt = {
        "show": bool(not quick["required_complete"] and not instance.get("prompt_dismissed_at")),
        "resume_task_key": instance.get("current_task_key"),
    }
    return {
        "instance": instance,
        "stages": stages,
        "tasks": tasks,
        "progress": progress,
        "recommended_next_task": next_task,
        "prompt": prompt,
    }


async def update_task_status(user: dict, task_key: str, status: str, *, reason: Optional[str] = None, deferred_until: Optional[str] = None) -> dict:
    _require_tenant_admin(user)
    task = TASKS_BY_KEY.get(task_key)
    if not task:
        raise OnboardingError("task_not_found", "Onboarding task not found", 404)
    if status not in VALID_STATUSES:
        raise OnboardingError("invalid_status", "Invalid onboarding task status", 400)
    if status == "completed" and task["detect"] == "canonical":
        raise OnboardingError("completion_is_derived", "This step completes when the setup is saved in its feature area; it cannot be marked done by hand.", 409)
    if status == "skipped" and task["level"] == "required":
        raise OnboardingError("required_step_cannot_skip", "Required steps can be deferred but not skipped.", 400)
    await _ensure_instance(user)
    patch: dict[str, Any] = {
        "status": status,
        "updated_at": _now_iso(),
        "updated_by_user_id": user["id"],
        "skipped_reason": (reason or "").strip() or None if status == "skipped" else None,
        "deferred_until": deferred_until if status == "deferred" else None,
        "blocked_reason": (reason or "").strip() or None if status == "blocked" else None,
        "completed_at": _now_iso() if status == "completed" else None,
    }
    state = OnboardingTaskState(
        tenant_id=user["tenant_id"], program_key=PROGRAM_KEY, program_version=PROGRAM_VERSION, task_key=task_key, level=task["level"],
    ).model_dump()
    for key in patch:
        state.pop(key, None)
    await db.onboarding_task_states.update_one(
        {"tenant_id": user["tenant_id"], "program_key": PROGRAM_KEY, "task_key": task_key},
        {"$set": patch, "$setOnInsert": prepare_for_mongo(state)},
        upsert=True,
    )
    await _audit(user, "onboarding.task_status_updated", "onboarding_task_state", task_key, "Onboarding task status updated", {"status": status, "reason": reason})
    return serialize_doc(await db.onboarding_task_states.find_one({"tenant_id": user["tenant_id"], "program_key": PROGRAM_KEY, "task_key": task_key}, {"_id": 0}))


async def set_position(user: dict, *, task_key: Optional[str] = None, dismiss_prompt: Optional[bool] = None) -> dict:
    """Remember where the owner left off (Resume Later) and whether the invitation was dismissed."""
    _require_tenant_admin(user)
    if task_key is not None and task_key not in TASKS_BY_KEY:
        raise OnboardingError("task_not_found", "Onboarding task not found", 404)
    await _ensure_instance(user)
    patch: dict[str, Any] = {"updated_at": _now_iso(), "updated_by_user_id": user["id"]}
    if task_key is not None:
        patch["current_task_key"] = task_key
    if dismiss_prompt is not None:
        patch["prompt_dismissed_at"] = _now_iso() if dismiss_prompt else None
    await db.tenant_onboarding_instances.update_one({"tenant_id": user["tenant_id"], "program_key": PROGRAM_KEY}, {"$set": patch})
    return serialize_doc(await db.tenant_onboarding_instances.find_one({"tenant_id": user["tenant_id"], "program_key": PROGRAM_KEY}, {"_id": 0}))


async def setup_package_handoff(user: dict, purchase_id: Optional[str] = None, status: Optional[str] = None, notes: Optional[str] = None) -> dict:
    _require_tenant_admin(user)
    filt: dict[str, Any] = {"tenant_id": user["tenant_id"]}
    if purchase_id:
        filt["id"] = purchase_id
    purchase = await db.setup_package_purchases.find_one(filt, {"_id": 0}, sort=[("created_at", -1)])
    if not purchase:
        return {"available": False, "purchase": None, "handoff_status": "not_available", "message": "No setup package purchase is recorded for this tenant."}
    if status:
        if status not in {"not_started", "ready_for_intake", "in_progress", "blocked", "complete"}:
            raise OnboardingError("invalid_handoff_status", "Invalid setup package handoff status", 400)
        await db.setup_package_purchases.update_one(
            {"tenant_id": user["tenant_id"], "id": purchase["id"]},
            {"$set": {"ec19_handoff_status": status, "ec19_handoff_notes": notes, "updated_at": _now_iso()}},
        )
        purchase = await db.setup_package_purchases.find_one({"tenant_id": user["tenant_id"], "id": purchase["id"]}, {"_id": 0})
    return {"available": True, "purchase": serialize_doc(purchase), "handoff_status": purchase.get("ec19_handoff_status", "not_started")}
