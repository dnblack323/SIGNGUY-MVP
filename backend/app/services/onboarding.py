"""EC19 onboarding engine and setup assistant service."""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.onboarding import (
    OnboardingImportRecord,
    OnboardingProgramDefinition,
    OnboardingStepResponse,
    OnboardingTaskState,
    OnboardingTemplateExercise,
    TenantOnboardingInstance,
)
from . import pricing_quiz, settings as settings_service, template_service
from .activity import record_activity_with_audit

PROGRAM_KEY = "shop_launch_v1"
PROGRAM_VERSION = 1
PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z0-9_.-]+)\s*}}")


class OnboardingError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


ONBOARDING_TASKS: list[dict[str, Any]] = [
    {"task_key": "company_profile", "title": "Company profile", "level": "required", "family": "core", "dependencies": []},
    {"task_key": "stripe_payments", "title": "Stripe payments", "level": "recommended", "family": "billing", "dependencies": ["company_profile"], "conditional": "when_payments_used"},
    {"task_key": "employees_roles", "title": "Employees and roles", "level": "recommended", "family": "team", "dependencies": ["company_profile"]},
    {"task_key": "production_workflow", "title": "Production workflow", "level": "recommended", "family": "production", "dependencies": ["company_profile"]},
    {"task_key": "pricing_setup_assistant", "title": "Pricing Setup Assistant", "level": "required", "family": "pricing", "dependencies": ["company_profile"]},
    {"task_key": "historical_invoice_import", "title": "Historical invoice import", "level": "optional", "family": "pricing", "dependencies": ["pricing_setup_assistant"]},
    {"task_key": "categories", "title": "Product and service categories", "level": "recommended", "family": "pricing", "dependencies": ["pricing_setup_assistant"]},
    {"task_key": "order_templates", "title": "Order templates", "level": "recommended", "family": "templates", "dependencies": []},
    {"task_key": "customer_portal", "title": "Customer portal", "level": "recommended", "family": "portal", "dependencies": ["company_profile"]},
    {"task_key": "documents", "title": "Documents", "level": "recommended", "family": "documents", "dependencies": ["company_profile"]},
    {"task_key": "questionnaires", "title": "Questionnaires", "level": "recommended", "family": "templates", "dependencies": ["customer_portal"]},
    {"task_key": "notifications", "title": "Notifications", "level": "recommended", "family": "communications", "dependencies": ["company_profile"]},
    {"task_key": "test_portal", "title": "Test portal", "level": "recommended", "family": "portal", "dependencies": ["customer_portal", "documents"]},
    {"task_key": "first_order", "title": "First order", "level": "required", "family": "operations", "dependencies": ["pricing_setup_assistant", "production_workflow"]},
    {"task_key": "ai_credits_limits", "title": "AI credits and limits", "level": "recommended", "family": "ai", "dependencies": []},
    {"task_key": "setup_package_handoff", "title": "Setup package handoff", "level": "optional", "family": "commercial", "dependencies": []},
]


def _now_iso() -> str:
    return utc_now().isoformat()


def _is_platform_admin(user: dict) -> bool:
    return bool(user.get("platform_admin") or user.get("platform_role") in {"admin", "owner"} or "platform:admin" in set(user.get("permissions") or []))


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
        title="Shop launch onboarding",
        description="Guided setup for SignGuy AI shop launch.",
        tasks=deepcopy(ONBOARDING_TASKS),
        effective_at=_now_iso(),
    ).model_dump()


async def bootstrap_platform(user: dict) -> dict:
    _require_platform_admin(user)
    inserted = {"program_definitions": 0, "help_articles": 0, "contextual_help": 0}
    program = _program_doc()
    res = await db.onboarding_program_definitions.update_one(
        {"program_key": PROGRAM_KEY, "version": PROGRAM_VERSION},
        {"$setOnInsert": prepare_for_mongo(program)},
        upsert=True,
    )
    inserted["program_definitions"] += int(bool(res.upserted_id))
    from . import help_center

    help_result = await help_center.bootstrap_help_content(user)
    inserted["help_articles"] = help_result["inserted"].get("help_articles", 0)
    inserted["contextual_help"] = help_result["inserted"].get("contextual_help", 0)
    return {"program_key": PROGRAM_KEY, "program_version": PROGRAM_VERSION, "inserted": inserted}


async def _active_program() -> dict[str, Any]:
    doc = await db.onboarding_program_definitions.find_one({"program_key": PROGRAM_KEY, "version": PROGRAM_VERSION}, {"_id": 0})
    if not doc:
        doc = _program_doc()
        await db.onboarding_program_definitions.insert_one(prepare_for_mongo(doc))
    return serialize_doc(doc)


async def _ensure_instance(user: dict) -> dict[str, Any]:
    program = await _active_program()
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
        return serialize_doc(await db.tenant_onboarding_instances.find_one({"tenant_id": user["tenant_id"], "program_key": PROGRAM_KEY}, {"_id": 0}))
    for task in program["tasks"]:
        state = OnboardingTaskState(
            tenant_id=user["tenant_id"],
            program_key=PROGRAM_KEY,
            program_version=PROGRAM_VERSION,
            task_key=task["task_key"],
            level=task.get("level", "recommended"),
        ).model_dump()
        try:
            await db.onboarding_task_states.insert_one(prepare_for_mongo(state))
        except DuplicateKeyError:
            pass
    return serialize_doc(doc)


async def _canonical_completion(tenant_id: str) -> dict[str, bool]:
    settings = await settings_service.list_all(tenant_id=tenant_id)
    company = settings.get("company_profile") or {}
    branding = settings.get("branding") or {}
    portal = settings.get("portal") or {}
    notifications = settings.get("notifications") or {}
    documents = settings.get("documents") or {}
    pricing_applied = await db.pricing_quiz_submissions.count_documents({"tenant_id": tenant_id, "status": "applied"}) > 0
    setup_imports = await db.onboarding_import_records.count_documents({"tenant_id": tenant_id, "import_type": "historical_invoice"}) > 0
    templates = await db.template_definitions.count_documents({"tenant_id": tenant_id, "owner_scope": {"$in": [None, "tenant"]}, "active": True}) > 0
    return {
        "company_profile": bool(company.get("shop_name") or company.get("legal_name")),
        "stripe_payments": await db.tenant_billing_accounts.count_documents({"tenant_id": tenant_id, "stripe_customer_id": {"$type": "string"}}) > 0,
        "employees_roles": await db.users.count_documents({"tenant_id": tenant_id, "is_active": True}) > 1,
        "production_workflow": await db.production_workflows.count_documents({"tenant_id": tenant_id, "active": True}) > 0,
        "pricing_setup_assistant": pricing_applied,
        "historical_invoice_import": setup_imports,
        "categories": bool(pricing_applied),
        "order_templates": templates,
        "customer_portal": bool(portal.get("enabled") or await db.portal_identities.count_documents({"tenant_id": tenant_id, "status": "active"}) > 0),
        "documents": bool(documents or branding.get("logo_file_id")),
        "questionnaires": await db.template_definitions.count_documents({"tenant_id": tenant_id, "template_type": "questionnaire", "active": True}) > 0,
        "notifications": bool(notifications),
        "test_portal": await db.onboarding_step_responses.count_documents({"tenant_id": tenant_id, "task_key": "test_portal", "applied": True}) > 0,
        "first_order": await db.orders.count_documents({"tenant_id": tenant_id}) > 0,
        "ai_credits_limits": await db.ai_governance_policies.count_documents({"tenant_id": tenant_id, "status": {"$ne": "archived"}}) > 0,
        "setup_package_handoff": await db.setup_package_purchases.count_documents({"tenant_id": tenant_id, "ec19_handoff_status": {"$ne": "not_started"}}) > 0,
    }


def _merge_task(task: dict[str, Any], state: Optional[dict[str, Any]], canonical_done: bool) -> dict[str, Any]:
    merged = deepcopy(task)
    status = (state or {}).get("status", "not_started")
    if canonical_done and status not in {"completed", "skipped", "deferred"}:
        status = "completed"
    merged.update({
        "status": status,
        "skipped_reason": (state or {}).get("skipped_reason"),
        "deferred_until": (state or {}).get("deferred_until"),
        "blocked_reason": (state or {}).get("blocked_reason"),
        "completed_at": (state or {}).get("completed_at"),
        "canonical_complete": canonical_done,
    })
    return merged


async def dashboard(user: dict) -> dict[str, Any]:
    instance = await _ensure_instance(user)
    program = await _active_program()
    canonical = await _canonical_completion(user["tenant_id"])
    state_docs = {
        doc["task_key"]: serialize_doc(doc)
        async for doc in db.onboarding_task_states.find({"tenant_id": user["tenant_id"], "program_key": PROGRAM_KEY}, {"_id": 0})
    }
    tasks = [_merge_task(task, state_docs.get(task["task_key"]), canonical.get(task["task_key"], False)) for task in program["tasks"]]
    required = [t for t in tasks if t["level"] == "required"]
    completed = [t for t in tasks if t["status"] == "completed"]
    required_done = [t for t in required if t["status"] == "completed"]
    progress = {
        "total_tasks": len(tasks),
        "completed_tasks": len(completed),
        "required_tasks": len(required),
        "completed_required_tasks": len(required_done),
        "percent_complete": round((len(completed) / max(len(tasks), 1)) * 100),
    }
    next_task = next((t for t in tasks if t["status"] in {"not_started", "in_progress", "blocked"} and t["level"] == "required"), None)
    if not next_task:
        next_task = next((t for t in tasks if t["status"] in {"not_started", "in_progress", "blocked"}), None)
    return {"instance": instance, "program": program, "tasks": tasks, "progress": progress, "recommended_next_task": next_task}


async def update_task_status(user: dict, task_key: str, status: str, *, reason: Optional[str] = None, deferred_until: Optional[str] = None) -> dict:
    _require_tenant_admin(user)
    task_keys = {t["task_key"] for t in ONBOARDING_TASKS}
    if task_key not in task_keys:
        raise OnboardingError("task_not_found", "Onboarding task not found", 404)
    if status not in {"not_started", "in_progress", "completed", "skipped", "deferred", "blocked"}:
        raise OnboardingError("invalid_status", "Invalid onboarding task status", 400)
    await _ensure_instance(user)
    patch: dict[str, Any] = {"status": status, "updated_at": _now_iso(), "updated_by_user_id": user["id"]}
    if status == "completed":
        patch["completed_at"] = _now_iso()
    if status == "skipped":
        patch["skipped_reason"] = (reason or "").strip() or None
    if status == "deferred":
        patch["deferred_until"] = deferred_until
    if status == "blocked":
        patch["blocked_reason"] = (reason or "").strip() or None
    await db.onboarding_task_states.update_one(
        {"tenant_id": user["tenant_id"], "program_key": PROGRAM_KEY, "task_key": task_key},
        {"$set": patch},
    )
    await _audit(user, "onboarding.task_status_updated", "onboarding_task_state", task_key, "Onboarding task status updated", {"status": status, "reason": reason})
    return serialize_doc(await db.onboarding_task_states.find_one({"tenant_id": user["tenant_id"], "program_key": PROGRAM_KEY, "task_key": task_key}, {"_id": 0}))


async def save_response(user: dict, *, task_key: str, response_type: str, payload: dict[str, Any], idempotency_key: Optional[str] = None) -> dict:
    _require_tenant_admin(user)
    existing = None
    if idempotency_key:
        existing = await db.onboarding_step_responses.find_one({"tenant_id": user["tenant_id"], "idempotency_key": idempotency_key}, {"_id": 0})
    if existing:
        return serialize_doc(existing)
    doc = OnboardingStepResponse(
        tenant_id=user["tenant_id"],
        task_key=task_key,
        response_type=response_type,
        payload=payload,
        idempotency_key=idempotency_key,
        created_by_user_id=user["id"],
    ).model_dump()
    await db.onboarding_step_responses.insert_one(prepare_for_mongo(doc))
    await update_task_status(user, task_key, "in_progress")
    return serialize_doc(doc)


async def apply_company_profile(user: dict, payload: dict[str, Any]) -> dict:
    _require_tenant_admin(user)
    allowed_company = {"shop_name", "legal_name", "phone", "email", "website", "address", "timezone"}
    allowed_branding = {"brand_color", "logo_file_id"}
    company = {k: v for k, v in (payload.get("company_profile") or payload).items() if k in allowed_company and v not in (None, "")}
    branding = {k: v for k, v in (payload.get("branding") or {}).items() if k in allowed_branding and v not in (None, "")}
    if not company and not branding:
        raise OnboardingError("no_company_fields", "No approved company profile fields were provided", 400)
    result: dict[str, Any] = {}
    if company:
        result["company_profile"] = await settings_service.set_many(tenant_id=user["tenant_id"], namespace="company_profile", values=company, updated_by=user["id"])
    if branding:
        result["branding"] = await settings_service.set_many(tenant_id=user["tenant_id"], namespace="branding", values=branding, updated_by=user["id"])
    response = await save_response(user, task_key="company_profile", response_type="company_profile_approved", payload={"company_profile": company, "branding": branding})
    await db.onboarding_step_responses.update_one({"id": response["id"]}, {"$set": {"applied": True, "updated_at": _now_iso()}})
    await update_task_status(user, "company_profile", "completed")
    return {"settings": result, "response": response}


async def pricing_scenario(user: dict, answers: dict[str, Any]) -> dict:
    _require_tenant_admin(user)
    doc = await pricing_quiz.submit_quiz(user["tenant_id"], answers)
    await save_response(user, task_key="pricing_setup_assistant", response_type="pricing_quiz_submission", payload={"submission_id": doc["id"]})
    return serialize_doc(doc)


async def apply_pricing_scenario(user: dict, submission_id: str, accepted_shop_defaults: dict[str, Any]) -> dict:
    _require_tenant_admin(user)
    numeric = {k: float(v) for k, v in accepted_shop_defaults.items() if v is not None}
    doc = await pricing_quiz.apply_quiz_suggestions(user["tenant_id"], submission_id, numeric, actor_user_id=user["id"])
    await update_task_status(user, "pricing_setup_assistant", "completed")
    return serialize_doc(doc)


async def create_historical_import(user: dict, payload: dict[str, Any]) -> dict:
    _require_tenant_admin(user)
    file_name = (payload.get("file_name") or "").strip()
    if not file_name:
        raise OnboardingError("file_name_required", "file_name is required", 400)
    doc = OnboardingImportRecord(
        tenant_id=user["tenant_id"],
        import_type="historical_invoice",
        file_name=file_name[:240],
        file_type=payload.get("file_type"),
        file_size_bytes=payload.get("file_size_bytes"),
        status="pending_provider" if payload.get("request_analysis") else "uploaded",
        analysis_status="unavailable" if payload.get("request_analysis") else "not_requested",
        warnings=["Live invoice analysis provider is deferred; no OpenAI/OCR/provider call was made."] if payload.get("request_analysis") else [],
        created_by_user_id=user["id"],
    ).model_dump()
    await db.onboarding_import_records.insert_one(prepare_for_mongo(doc))
    await save_response(user, task_key="historical_invoice_import", response_type="historical_invoice_import", payload={"import_record_id": doc["id"]})
    return serialize_doc(doc)


def placeholder_registry() -> dict:
    placeholders = sorted(template_service.VALID_PLACEHOLDERS)
    return {
        "placeholders": [{"key": key, "token": "{{" + key + "}}"} for key in placeholders],
        "families": {
            "customer": [p for p in placeholders if p.startswith("customer") or p == "contact_name"],
            "order": [p for p in placeholders if "order" in p],
            "shop": [p for p in placeholders if p.startswith("shop")],
            "date": [p for p in placeholders if "date" in p or "time" in p],
        },
    }


def preview_placeholders(content: str, context: dict[str, Any]) -> dict:
    found = sorted(set(PLACEHOLDER_RE.findall(content or "")))
    allowed = set(template_service.VALID_PLACEHOLDERS)
    unknown = sorted(set(found) - allowed)
    if unknown:
        raise OnboardingError("unknown_placeholder", f"Unsupported placeholders: {', '.join(unknown)}", 400)
    missing = sorted(key for key in found if context.get(key) in (None, ""))
    rendered = content or ""
    for key in found:
        rendered = re.sub(r"{{\s*" + re.escape(key) + r"\s*}}", str(context.get(key) or ""), rendered)
    return {"rendered": rendered, "placeholders": found, "missing_placeholders": missing}


async def template_exercise(user: dict, payload: dict[str, Any]) -> dict:
    _require_tenant_admin(user)
    template_type = payload.get("template_type") or "email"
    body = payload.get("body") or {}
    name = (payload.get("name") or "Onboarding sample template").strip()
    await template_service.validate_template_payload(template_type=template_type, body=body)
    preview = template_service.render_channels(body, payload.get("context") or {})
    template_id = None
    status = "previewed"
    if payload.get("save_as_template"):
        created = await template_service.create_template(
            tenant_id=user["tenant_id"],
            payload={"name": name, "template_type": template_type, "body": body, "description": "Created from EC19 onboarding exercise."},
            actor_user_id=user["id"],
            actor_email=user.get("email", "onboarding"),
        )
        template_id = created["id"]
        status = "saved"
    missing = sorted({p for v in preview.values() for p in PLACEHOLDER_RE.findall(v or "")})
    exercise = OnboardingTemplateExercise(
        tenant_id=user["tenant_id"],
        template_id=template_id,
        template_type=template_type,
        name=name,
        body=body,
        preview=preview,
        missing_placeholders=missing,
        status=status,
        created_by_user_id=user["id"],
    ).model_dump()
    await db.onboarding_template_exercises.insert_one(prepare_for_mongo(exercise))
    if template_id:
        await update_task_status(user, "order_templates", "completed")
    return serialize_doc(exercise)


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
        await update_task_status(user, "setup_package_handoff", "completed" if status == "complete" else "in_progress")
    return {"available": True, "purchase": serialize_doc(purchase), "handoff_status": purchase.get("ec19_handoff_status", "not_started")}


async def record_test_portal(user: dict, payload: dict[str, Any]) -> dict:
    _require_tenant_admin(user)
    response = await save_response(user, task_key="test_portal", response_type="test_portal_result", payload={"result": payload})
    await db.onboarding_step_responses.update_one({"id": response["id"]}, {"$set": {"applied": True, "updated_at": _now_iso()}})
    await update_task_status(user, "test_portal", "completed")
    return serialize_doc(await db.onboarding_step_responses.find_one({"id": response["id"]}, {"_id": 0}))
