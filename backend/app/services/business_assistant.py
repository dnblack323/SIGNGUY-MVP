"""EC18 Business Assistant service.

The assistant owns conversation, action-safety, voice-session metadata, and
deterministic BI contracts. AI governance and metering remain owned by EC16.
"""
from __future__ import annotations

from datetime import timedelta
import uuid
from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.assistant_voices import VOICE_KEYS, voice_options, voice_policy
from ..core.config import get_settings
from ..core.db import db
from ..core.permissions import Perm, permissions_for_role
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.ai_gateway import AICapability, AIModelProfile, AIPromptVersion, AIProviderConfig
from ..models.ai_studio import AIStudioEditableDraft
from ..models.user import AssistantPreferences
from . import assistant_context, assistant_personality
from ..models.business_assistant import (
    AssistantActionProposal,
    AssistantContextSnapshot,
    AssistantConversation,
    AssistantInsight,
    AssistantMessage,
    AssistantRoutine,
    AssistantSourceCitation,
)
from . import ai_gateway, communication_service, task_service
from .activity import record_activity_with_audit
from .entitlements import has_entitlement


BUSINESS_ASSISTANT_ENTITLEMENT_FEATURE_KEY = "business_assistant"
LOCAL_PROVIDER_KEY = "ec18_assistant_local"
LOCAL_MODEL_KEY = "ec18_assistant_contract_model"
LOCAL_PROMPT_VERSION = "ec18-local-1"
CREDIT_DISPLAY = "AI credits apply"

ASSISTANT_CAPABILITY_KEYS = [
    "assistant.email_draft",
    "assistant.chat",
    "assistant.action_parse",
    "assistant.voice_transcription",
    "assistant.voice_reply",
    "assistant.intent_classify",
    "assistant.navigation_classify",
    "assistant.memory_compress",
]

DEFERRED_CAPABILITY_KEYS = [
    "integration.facebook.message_classify",
    "integration.facebook.order_extract",
    "order.service_prefill",
    "studio.text.bulk_followup",
]

ASSISTANT_MODES = [
    {"mode_key": "owner", "name": "Owner", "purpose": "Shop-wide priorities, money, customers, and decisions."},
    {"mode_key": "operations", "name": "Operations", "purpose": "Orders, follow-ups, schedules, blockers, and customer communication."},
    {"mode_key": "finance", "name": "Finance", "purpose": "Invoices, overdue balances, revenue basis, margins, and missing data."},
    {"mode_key": "production", "name": "Production", "purpose": "Work orders, production stages, late jobs, and shop capacity."},
    {"mode_key": "workforce", "name": "Workforce", "purpose": "Workers, shifts, tasks, time-off, and schedule coverage."},
]

CONTEXT_TARGETS: dict[str, dict[str, str]] = {
    "customer": {"collection": "customers", "read_perm": Perm.CUSTOMER_READ.value, "route": "/customers/{id}", "label": "Customer"},
    "quote": {"collection": "quotes", "read_perm": Perm.QUOTE_READ.value, "route": "/quotes/{id}", "label": "Quote"},
    "order": {"collection": "orders", "read_perm": Perm.ORDER_READ.value, "route": "/orders/{id}", "label": "Order"},
    "invoice": {"collection": "invoices", "read_perm": Perm.INVOICE_READ.value, "route": "/invoices/{id}", "label": "Invoice"},
    "work_order": {"collection": "work_orders", "read_perm": Perm.WORK_ORDER_READ.value, "route": "/work-orders/{id}", "label": "Work Order"},
    "webstore": {"collection": "webstores", "read_perm": Perm.WEBSTORE_READ.value, "route": "/webstores/{id}", "label": "Webstore"},
    "wrap_project": {"collection": "wrap_projects", "read_perm": Perm.WRAP_LAB_READ.value, "route": "/wrap-lab/{id}", "label": "Wrap Project"},
    "employee": {"collection": "employees", "read_perm": Perm.EMPLOYEE_READ.value, "route": "/team/employees/{id}", "label": "Employee"},
    "task": {"collection": "tasks", "read_perm": Perm.TASK_READ.value, "route": "/team/tasks", "label": "Task"},
}

ACTION_PERMISSIONS: dict[str, list[str]] = {
    "email_draft": [Perm.EMAIL_SEND.value],
    "document_draft": [Perm.DOCUMENT_WRITE.value],
    "navigation": [],
    "bulk_email_draft": [Perm.EMAIL_SEND.value],
    "internal_task": [Perm.TASK_CREATE.value],
    "internal_note": [Perm.NOTE_CREATE.value],
    "report_draft": [Perm.REPORT_WRITE.value],
    "studio_delegation": [Perm.AI_TOOL_USE.value],
}


class BusinessAssistantError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _now_iso() -> str:
    return utc_now().isoformat()


def _has_perm(user: dict[str, Any], perm: str) -> bool:
    if user.get("role") in {"owner", "admin"}:
        return True
    return perm in set(user.get("permissions") or permissions_for_role(user.get("role", "staff")))


def _require_perm(user: dict[str, Any], perm: str) -> None:
    if not _has_perm(user, perm):
        raise BusinessAssistantError("permission_required", f"Missing permission: {perm}", 403)


async def _require_assistant_access(user: dict[str, Any]) -> None:
    _require_perm(user, Perm.AI_ASSISTANT_USE.value)
    if not await has_entitlement(tenant_id=user["tenant_id"], feature_key=BUSINESS_ASSISTANT_ENTITLEMENT_FEATURE_KEY):
        raise BusinessAssistantError("feature_not_entitled", f"Feature not entitled: {BUSINESS_ASSISTANT_ENTITLEMENT_FEATURE_KEY}", 402)


async def assert_assistant_access(user: dict[str, Any]) -> None:
    await _require_assistant_access(user)


async def get_preferences(user: dict) -> dict:
    await _require_assistant_access(user)
    row = await db.users.find_one({"tenant_id": user["tenant_id"], "id": user["id"]}, {"_id": 0, "assistant_preferences": 1})
    saved = (row or {}).get("assistant_preferences") or {}
    try:
        preferences = AssistantPreferences.model_validate(saved).model_dump()
    except ValueError:
        # Legacy unknown preferences are preserved in storage, not trusted as instructions.
        preferences = AssistantPreferences().model_dump()
    return {"preferences": preferences, "options": assistant_personality.options(), "source": "user" if saved else "system",
            "voices": voice_options(), "effective_voice": preferences.get("voice") if preferences.get("voice") in VOICE_KEYS else "alloy",
            "voice_policy": voice_policy()}


async def update_preferences(user: dict, updates: dict) -> dict:
    await _require_assistant_access(user)
    if "voice" in updates and updates["voice"] is not None and updates["voice"] not in VOICE_KEYS:
        raise BusinessAssistantError("invalid_assistant_voice", "Select an available assistant voice", 422)
    current = (await get_preferences(user))["preferences"]
    AssistantPreferences.model_validate({**current, **updates})
    if updates:
        result = await db.users.update_one({"tenant_id": user["tenant_id"], "id": user["id"]},
            {"$set": {f"assistant_preferences.{key}": value for key, value in updates.items()}})
        if not result.matched_count:
            raise BusinessAssistantError("user_not_found", "User not found", 404)
    return await get_preferences(user)


async def _audit(user: dict[str, Any], action: str, entity_type: str, entity_id: str, summary: str, metadata: Optional[dict[str, Any]] = None) -> None:
    await record_activity_with_audit(
        tenant_id=user["tenant_id"],
        actor_user_id=user["id"],
        actor_email=user.get("email", "assistant"),
        module="business_assistant",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        metadata=metadata or {},
    )


def _mode_key(mode: Optional[str]) -> str:
    candidate = (mode or "owner").strip().lower()
    return candidate if candidate in {m["mode_key"] for m in ASSISTANT_MODES} else "owner"


def list_catalog() -> dict[str, Any]:
    return {
        "entitlement_feature_key": BUSINESS_ASSISTANT_ENTITLEMENT_FEATURE_KEY,
        "credit_display": CREDIT_DISPLAY,
        "modes": ASSISTANT_MODES,
        "capability_keys": ASSISTANT_CAPABILITY_KEYS,
        "deferred_capability_keys": DEFERRED_CAPABILITY_KEYS,
        "action_lifecycle": ["proposed", "edited", "confirmed", "canceled", "expired", "executing", "succeeded", "failed", "stale", "unsupported"],
        "voice": {"provider": "openai", "architecture": "realtime_webrtc", "configured_by_backend": True},
    }


async def bootstrap_platform_catalog(user: dict[str, Any]) -> dict[str, Any]:
    ai_gateway.require_platform_ai_admin(user)
    provider = await _ensure_local_provider()
    model = await _ensure_local_model(provider)
    capability_keys: list[str] = []
    prompt_ids: list[str] = []
    for capability_key in ASSISTANT_CAPABILITY_KEYS:
        cap = await _ensure_local_capability(capability_key, model["id"])
        prompt = await _ensure_local_prompt(capability_key)
        capability_keys.append(cap["capability_key"])
        prompt_ids.append(prompt["id"])
    await _audit(user, "assistant.catalog_bootstrapped", "assistant_catalog", "ec18", "EC18 assistant capabilities bootstrapped")
    return {
        "provider_key": provider["provider_key"],
        "model_key": model["model_key"],
        "capability_keys": capability_keys,
        "prompt_version_ids": prompt_ids,
        "deferred_capability_keys": DEFERRED_CAPABILITY_KEYS,
        "external_provider_calls": 0,
    }


async def _ensure_local_provider() -> dict[str, Any]:
    query = {"provider_key": LOCAL_PROVIDER_KEY}
    existing = await db.ai_provider_configs.find_one(query, {"_id": 0})
    if existing:
        return serialize_doc(existing)
    doc = AIProviderConfig(
        provider_key=LOCAL_PROVIDER_KEY,
        display_name="EC18 Assistant Local Contract Provider",
        status="active",
        credential_mode="none",
        supported_modalities=["text", "voice", "tool_call", "classification"],
        metadata={"ec18_local_contract": True, "external_provider_calls": 0},
    ).model_dump()
    try:
        await db.ai_provider_configs.insert_one(prepare_for_mongo(doc))
    except DuplicateKeyError:
        existing = await db.ai_provider_configs.find_one(query, {"_id": 0})
        if existing:
            return serialize_doc(existing)
        raise
    return serialize_doc(doc)


async def _ensure_local_model(provider: dict[str, Any]) -> dict[str, Any]:
    query = {"provider_config_id": provider["id"], "model_key": LOCAL_MODEL_KEY}
    existing = await db.ai_model_profiles.find_one(query, {"_id": 0})
    if existing:
        return serialize_doc(existing)
    doc = AIModelProfile(
        provider_config_id=provider["id"],
        provider_key=provider["provider_key"],
        model_key=LOCAL_MODEL_KEY,
        display_name="EC18 Assistant Contract Model",
        task_category="business_assistant",
        intensity="local_contract",
        status="active",
        metadata={"ec18_local_contract": True, "external_provider_calls": 0},
    ).model_dump()
    try:
        await db.ai_model_profiles.insert_one(prepare_for_mongo(doc))
    except DuplicateKeyError:
        existing = await db.ai_model_profiles.find_one(query, {"_id": 0})
        if existing:
            return serialize_doc(existing)
        raise
    return serialize_doc(doc)


async def _ensure_local_capability(capability_key: str, model_profile_id: str) -> dict[str, Any]:
    query = {"capability_key": capability_key}
    existing = await db.ai_capabilities.find_one(query, {"_id": 0})
    if existing:
        updates: dict[str, Any] = {}
        ids = list(existing.get("allowed_model_profile_ids") or [])
        if model_profile_id not in ids:
            ids.append(model_profile_id)
            updates["allowed_model_profile_ids"] = ids
        if existing.get("status") != "active":
            updates["status"] = "active"
        if updates:
            updates["updated_at"] = _now_iso()
            await db.ai_capabilities.update_one({"id": existing["id"]}, {"$set": prepare_for_mongo(updates)})
            existing.update(updates)
        return serialize_doc(existing)
    doc = AICapability(
        capability_key=capability_key,
        display_name=capability_key.replace(".", " ").replace("_", " ").title(),
        feature_key=BUSINESS_ASSISTANT_ENTITLEMENT_FEATURE_KEY,
        action_key=capability_key.split(".")[-1],
        entitlement_feature_key=BUSINESS_ASSISTANT_ENTITLEMENT_FEATURE_KEY,
        status="active",
        billable=True,
        default_credit_charge=1,
        allowed_model_profile_ids=[model_profile_id],
        metadata={"ec18_assistant": True, "credit_display": CREDIT_DISPLAY, "no_final_numeric_credit_price": True},
    ).model_dump()
    try:
        await db.ai_capabilities.insert_one(prepare_for_mongo(doc))
    except DuplicateKeyError:
        existing = await db.ai_capabilities.find_one(query, {"_id": 0})
        if existing:
            return await _ensure_local_capability(capability_key, model_profile_id)
        raise
    return serialize_doc(doc)


async def _ensure_local_prompt(capability_key: str) -> dict[str, Any]:
    prompt_key = f"{capability_key}.ec18_local"
    query = {"prompt_key": prompt_key, "version": LOCAL_PROMPT_VERSION}
    existing = await db.ai_prompt_versions.find_one(query, {"_id": 0})
    if existing:
        return serialize_doc(existing)
    doc = AIPromptVersion(
        capability_key=capability_key,
        prompt_key=prompt_key,
        version=LOCAL_PROMPT_VERSION,
        status="published",
        template="EC18 deterministic local assistant contract prompt. No external provider call.",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        published_by_user_id="system",
        published_at=_now_iso(),
    ).model_dump()
    try:
        await db.ai_prompt_versions.insert_one(prepare_for_mongo(doc))
    except DuplicateKeyError:
        existing = await db.ai_prompt_versions.find_one(query, {"_id": 0})
        if existing:
            return serialize_doc(existing)
        raise
    return serialize_doc(doc)


async def create_conversation(user: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    await _require_assistant_access(user)
    doc = AssistantConversation(
        tenant_id=user["tenant_id"],
        user_id=user["id"],
        title=(fields.get("title") or "Business Assistant")[:160],
        mode=_mode_key(fields.get("mode")),  # type: ignore[arg-type]
    ).model_dump()
    await db.assistant_conversations.insert_one(prepare_for_mongo(doc))
    await _audit(user, "assistant.conversation_created", "assistant_conversation", doc["id"], "Assistant conversation created")
    return serialize_doc(doc)


async def _conversation(user: dict[str, Any], conversation_id: Optional[str], *, mode: Optional[str] = None) -> dict[str, Any]:
    if conversation_id:
        doc = await db.assistant_conversations.find_one({"tenant_id": user["tenant_id"], "user_id": user["id"], "id": conversation_id, "status": {"$ne": "deleted"}}, {"_id": 0})
        if not doc:
            raise BusinessAssistantError("conversation_not_found", "Assistant conversation not found", 404)
        return serialize_doc(doc)
    return await create_conversation(user, {"mode": mode})


async def list_conversations(user: dict[str, Any], *, limit: int = 50) -> dict[str, Any]:
    await _require_assistant_access(user)
    cursor = db.assistant_conversations.find(
        {"tenant_id": user["tenant_id"], "user_id": user["id"], "status": {"$ne": "deleted"}},
        {"_id": 0},
    ).sort("updated_at", -1).limit(limit)
    items = [serialize_doc(d) async for d in cursor]
    return {"items": items, "total": len(items)}


async def get_conversation(user: dict[str, Any], conversation_id: str) -> dict[str, Any]:
    from .assistant_actions import actor, list_for_conversation
    user = await actor(user)
    await _require_assistant_access(user)
    convo = await _conversation(user, conversation_id)
    messages = [
        serialize_doc(d)
        async for d in db.assistant_messages.find({"tenant_id": user["tenant_id"], "conversation_id": conversation_id}, {"_id": 0}).sort("created_at", -1).limit(100)
    ]
    messages.reverse()
    for message in messages:
        if not await assistant_context.visible(user, message):
            message["content_text"] = "Earlier message hidden because its current access cannot be verified."
            message["metadata"] = {}
            message["source_citation_ids"] = []
            message["parts"] = []
            message["context_snapshot_id"] = None
            message["action_proposal_ids"] = []
    return {"conversation": {k: v for k, v in convo.items() if k != "active_turn"}, "messages": messages[-100:], "proposals": await list_for_conversation(user, conversation_id)}


async def _insert_message(user: dict[str, Any], *, conversation_id: str, role: str, content_text: str, mode: str, context_snapshot_id: Optional[str] = None, action_request_id: Optional[str] = None, citation_ids: Optional[list[str]] = None, proposal_ids: Optional[list[str]] = None, voice_session_id: Optional[str] = None, metadata: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    msg = AssistantMessage(
        tenant_id=user["tenant_id"],
        conversation_id=conversation_id,
        user_id=user["id"],
        role=role,  # type: ignore[arg-type]
        content_text=content_text[:12000],
        mode=mode,  # type: ignore[arg-type]
        context_snapshot_id=context_snapshot_id,
        action_request_id=action_request_id,
        source_citation_ids=citation_ids or [],
        action_proposal_ids=proposal_ids or [],
        voice_session_id=voice_session_id,
        metadata=metadata or {},
    ).model_dump()
    await db.assistant_messages.insert_one(prepare_for_mongo(msg))
    await db.assistant_conversations.update_one(
        {"tenant_id": user["tenant_id"], "id": conversation_id},
        {"$set": {"last_message_at": _now_iso(), "updated_at": _now_iso()}},
    )
    return serialize_doc(msg)


async def _validate_context(user: dict[str, Any], fields: dict[str, Any], *, conversation_id: Optional[str], mode: str) -> Optional[dict[str, Any]]:
    source_type = fields.get("source_entity_type") or fields.get("context_type")
    source_id = fields.get("source_entity_id") or fields.get("context_id")
    if not source_type and not source_id:
        return None
    if source_type not in CONTEXT_TARGETS or not source_id:
        raise BusinessAssistantError("unsupported_context", "Assistant context is not supported", 400)
    target = CONTEXT_TARGETS[source_type]
    _require_perm(user, target["read_perm"])
    coll = getattr(db, target["collection"])
    record = await coll.find_one({"tenant_id": user["tenant_id"], "id": source_id}, {"_id": 0})
    if not record:
        raise BusinessAssistantError("context_not_found", "Context record not found", 404)
    source_updated_at = record.get("updated_at") or record.get("created_at")
    route = target["route"].format(id=source_id)
    snapshot = AssistantContextSnapshot(
        tenant_id=user["tenant_id"],
        user_id=user["id"],
        conversation_id=conversation_id,
        mode=mode,  # type: ignore[arg-type]
        source_entity_type=source_type,
        source_entity_id=source_id,
        source_route=route,
        source_updated_at=str(source_updated_at) if source_updated_at else None,
        payload_summary={
            "label": target["label"],
            "number": record.get("number"),
            "name": record.get("name") or record.get("title"),
            "status": record.get("status") or record.get("document_status") or record.get("financial_status"),
        },
        source_links=[{"source_type": source_type, "source_id": source_id, "route": route, "source_updated_at": str(source_updated_at) if source_updated_at else None}],
        expires_at=(utc_now() + timedelta(hours=24)).isoformat(),
    ).model_dump()
    await db.assistant_context_snapshots.insert_one(prepare_for_mongo(snapshot))
    return serialize_doc(snapshot)


async def _create_citation(tenant_id: str, *, conversation_id: str, source_type: str, source_id: str, source_label: str, route: Optional[str] = None, calculation: Optional[dict[str, Any]] = None, missing_data: Optional[list[str]] = None, date_range: Optional[dict[str, Any]] = None, source_updated_at: Optional[str] = None) -> dict[str, Any]:
    cite = AssistantSourceCitation(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        source_type=source_type,
        source_id=source_id,
        source_label=source_label,
        route=route,
        calculation=calculation,
        missing_data=missing_data or [],
        date_range=date_range,
        source_updated_at=source_updated_at,
    ).model_dump()
    await db.assistant_source_citations.insert_one(prepare_for_mongo(cite))
    return serialize_doc(cite)


async def ask_assistant(user: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    from .assistant_conversation import ask
    return await ask(user, fields)


async def propose_action(user: dict, fields: dict) -> dict:
    from .assistant_actions import propose
    return await propose(user, fields)


async def _save_proposal(user: dict[str, Any], conversation_id: str, mode: str, fields: dict[str, Any], *, status: str, warnings: list[str], required_permissions: list[str]) -> dict[str, Any]:
    action_type = str(fields.get("action_type") or "unsupported")
    preview = fields.get("preview") or _default_preview(action_type, fields)
    proposal = AssistantActionProposal(
        tenant_id=user["tenant_id"],
        conversation_id=conversation_id,
        user_id=user["id"],
        capability_key="assistant.email_draft" if "email" in action_type else "assistant.action_parse",
        action_type=action_type,
        title=str(fields.get("title") or action_type.replace("_", " ").title())[:160],
        summary=str(fields.get("summary") or preview.get("summary") or "Review this proposed action before anything happens.")[:1000],
        status=status,  # type: ignore[arg-type]
        mode=mode,  # type: ignore[arg-type]
        target_refs=fields.get("target_refs") or [],
        required_permissions=required_permissions,
        preview=preview,
        editable_payload=fields.get("editable_payload") or preview,
        warnings=warnings,
        idempotency_key=fields.get("idempotency_key"),
        expires_at=fields.get("expires_at") or (utc_now() + timedelta(hours=24)).isoformat(),
        input_fingerprint=fields.get("input_fingerprint"),
        permission_signature=fields.get("permission_signature"),
    ).model_dump()
    try:
        await db.assistant_action_proposals.insert_one(prepare_for_mongo(proposal))
    except DuplicateKeyError:
        existing = await db.assistant_action_proposals.find_one({"tenant_id": user["tenant_id"], "user_id": user["id"], "idempotency_key": fields.get("idempotency_key")}, {"_id": 0})
        if existing:
            if fields.get("input_fingerprint") and existing.get("input_fingerprint") != fields["input_fingerprint"]:
                raise BusinessAssistantError("proposal_key_conflict", "This proposal key belongs to different content", 409)
            return serialize_doc(existing)
        raise BusinessAssistantError("proposal_key_conflict", "This proposal request key is already in use", 409)
    return serialize_doc(proposal)


def _default_preview(action_type: str, fields: dict[str, Any]) -> dict[str, Any]:
    if action_type == "email_draft":
        return {
            "draft_type": "email",
            "subject": fields.get("subject") or "Draft email",
            "body": fields.get("body") or fields.get("instructions") or "",
            "summary": "Editable email draft only. It will not be sent automatically.",
        }
    if action_type == "navigation":
        return {"route": fields.get("route") or "/", "summary": "Navigation suggestion only."}
    if action_type == "bulk_email_draft":
        targets = fields.get("target_refs") or []
        return {"count": len(targets), "affected_refs": targets, "summary": "Bulk draft proposal only. No email will be sent automatically."}
    if action_type == "internal_task":
        return {
            "title": fields.get("title") or "Assistant-created task",
            "description": fields.get("description") or fields.get("instructions") or "",
            "priority": fields.get("priority") or "normal",
            "due_at": fields.get("due_at"),
            "affected_refs": fields.get("target_refs") or [],
            "summary": "Creates one internal task after explicit confirmation.",
        }
    if action_type == "internal_note":
        return {
            "title": fields.get("title") or "Assistant note",
            "body": fields.get("body") or fields.get("instructions") or "",
            "visibility": fields.get("visibility") or "internal",
            "affected_refs": fields.get("target_refs") or [],
            "summary": "Creates one internal note after explicit confirmation.",
        }
    if action_type == "report_draft":
        return {
            "title": fields.get("title") or "Assistant report draft",
            "body": fields.get("body") or fields.get("instructions") or "",
            "summary": "Creates an editable report draft only.",
        }
    if action_type == "studio_delegation":
        return {
            "tool_key": fields.get("tool_key") or "social_post_builder",
            "mode_key": fields.get("mode_key") or "completed_work_showcase",
            "affected_refs": fields.get("target_refs") or [],
            "summary": "Prepares an existing EC17 Studio tool link with validated context.",
        }
    return {"summary": "Unsupported action. No data will be changed."}


def _proposal_warnings(action_type: str, target_refs: list[dict[str, Any]]) -> list[str]:
    if action_type == "email_draft":
        return ["Draft only. Nothing is sent until a human sends it through the canonical email workflow."]
    if action_type == "bulk_email_draft":
        return [f"Bulk proposal affects {len(target_refs)} target(s). Review every recipient before confirming.", "No email will be sent automatically."]
    if action_type == "internal_task":
        return ["Creates an internal task only after confirmation. No customer communication, pricing, invoice, payment, or production status changes occur."]
    if action_type == "internal_note":
        return ["Creates an internal note only after confirmation. It is not shown to customers."]
    if action_type == "report_draft":
        return ["Creates an editable report draft only. Nothing is exported, printed, emailed, or published."]
    if action_type == "studio_delegation":
        return ["Opens the existing EC17 Studio tool with validated context. No Studio asset is generated automatically."]
    return []


def _first_target_ref(proposal: dict[str, Any]) -> dict[str, Any]:
    refs = proposal.get("target_refs") or []
    return refs[0] if refs else {}


def _task_link_payload(ref: dict[str, Any]) -> dict[str, Any]:
    ref_type = ref.get("type")
    ref_id = ref.get("id")
    mapping = {
        "customer": "customer_id",
        "quote": "quote_id",
        "order": "order_id",
        "order_item": "order_item_id",
        "work_order": "work_order_id",
        "invoice": "invoice_id",
        "production_stage": "production_stage_id",
    }
    field = mapping.get(ref_type)
    if not field or not ref_id:
        return {}
    return {"source_type": ref_type, "source_id": ref_id, field: ref_id}


def _note_link_payload(ref: dict[str, Any]) -> dict[str, Any]:
    ref_type = ref.get("type")
    ref_id = ref.get("id")
    mapping = {
        "customer": "customer_id",
        "order": "order_id",
        "order_item": "order_item_id",
        "work_order": "work_order_id",
        "production_stage": "production_stage_id",
        "task": "task_id",
        "employee": "employee_id",
    }
    field = mapping.get(ref_type)
    return {field: ref_id} if field and ref_id else {}


async def edit_proposal(user: dict, proposal_id: str, fields: dict) -> dict:
    from .assistant_actions import edit
    return await edit(user, proposal_id, fields)


async def confirm_proposal(user: dict, proposal_id: str, revision=None) -> dict:
    from .assistant_actions import confirm
    return await confirm(user, proposal_id, revision)


async def cancel_proposal(user: dict, proposal_id: str) -> dict:
    from .assistant_actions import cancel
    return await cancel(user, proposal_id)


async def execute_proposal(user: dict, proposal_id: str, *, idempotency_key=None) -> dict:
    from .assistant_actions import execute
    return await execute(user, proposal_id, idempotency_key)


async def _proposal(user: dict[str, Any], proposal_id: str) -> dict[str, Any]:
    doc = await db.assistant_action_proposals.find_one({"tenant_id": user["tenant_id"], "user_id": user["id"], "id": proposal_id}, {"_id": 0})
    if not doc:
        raise BusinessAssistantError("proposal_not_found", "Assistant action proposal not found", 404)
    return serialize_doc(doc)


async def _execute_safe_canonical_action(user: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    action_type = proposal.get("action_type")
    payload = proposal.get("editable_payload") or {}
    if action_type == "email_draft":
        draft_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"assistant-draft:{user['tenant_id']}:{proposal['id']}"))
        draft = AIStudioEditableDraft(
            id=draft_id,
            tenant_id=user["tenant_id"],
            creator_user_id=user["id"],
            tool_key="business_assistant",
            mode_key="email_draft",
            family_key="business_assistant",
            capability_key="assistant.email_draft",
            usage_band="standard",
            draft_type="email",
            title=payload.get("subject") or proposal.get("title") or "Assistant email draft",
            content_text=payload.get("body") or "",
            content_json={"subject": payload.get("subject") or "", "recipients": payload.get("recipients") or [], "assistant_proposal_id": proposal["id"]},
            warnings=["Draft only. No email was sent."],
        ).model_dump()
        await db.ai_studio_editable_drafts.update_one({"tenant_id": user["tenant_id"], "id": draft_id}, {"$setOnInsert": prepare_for_mongo(draft)}, upsert=True)
        return {"status": "succeeded", "canonical_service": "ai_studio_editable_drafts", "draft_id": draft["id"], "route": f"/studio/generated-assets?draft={draft_id}", "sent": False, "assistant_summary": "Email draft saved. No email was sent."}
    if action_type == "document_draft":
        draft = AIStudioEditableDraft(
            tenant_id=user["tenant_id"],
            creator_user_id=user["id"],
            tool_key="business_assistant",
            mode_key="document_draft",
            family_key="business_assistant",
            capability_key="assistant.chat",
            usage_band="heavy",
            draft_type="document",
            title=payload.get("title") or proposal.get("title") or "Assistant document draft",
            content_text=payload.get("body") or payload.get("content_text") or "",
            content_json={"assistant_proposal_id": proposal["id"]},
            warnings=["Draft only. No document was exported, printed, or emailed."],
        ).model_dump()
        await db.ai_studio_editable_drafts.insert_one(prepare_for_mongo(draft))
        return {"status": "succeeded", "canonical_service": "ai_studio_editable_drafts", "draft_id": draft["id"], "exported": False, "assistant_summary": "Document draft created. Nothing was exported, printed, or emailed."}
    if action_type == "navigation":
        return {"status": "succeeded", "canonical_service": "navigation_suggestion", "route": payload.get("route") or proposal.get("preview", {}).get("route") or "/", "mutated": False, "assistant_summary": "Navigation suggestion prepared. No records were changed."}
    if action_type == "bulk_email_draft":
        drafts = []
        for idx, ref in enumerate(proposal.get("target_refs") or []):
            draft = AIStudioEditableDraft(
                tenant_id=user["tenant_id"],
                creator_user_id=user["id"],
                tool_key="business_assistant",
                mode_key="bulk_email_draft",
                family_key="business_assistant",
                capability_key="assistant.email_draft",
                usage_band="heavy",
                draft_type="email",
                title=f"{payload.get('subject') or proposal.get('title') or 'Assistant bulk email draft'} #{idx + 1}",
                content_text=payload.get("body") or "",
                content_json={"subject": payload.get("subject") or "", "target_ref": ref, "assistant_proposal_id": proposal["id"]},
                warnings=["Draft only. No email was sent."],
            ).model_dump()
            await db.ai_studio_editable_drafts.insert_one(prepare_for_mongo(draft))
            drafts.append({"target_ref": ref, "draft_id": draft["id"], "status": "draft_created", "sent": False})
        return {"status": "succeeded", "canonical_service": "ai_studio_editable_drafts", "results": drafts, "sent": False, "assistant_summary": f"{len(drafts)} email draft(s) created. No emails were sent."}
    if action_type == "internal_task":
        _require_perm(user, Perm.TASK_CREATE.value)
        task_payload = {
            "title": payload.get("title") or proposal.get("title") or "Assistant-created task",
            "description": payload.get("description") or payload.get("body") or proposal.get("summary"),
            "priority": payload.get("priority") or "normal",
            "task_type": payload.get("task_type") or "assistant_followup",
            "due_at": payload.get("due_at"),
            "visibility": "staff",
            "assigned_user_id": user["id"],
            "internal_only": True,
            "employee_visible": False,
            "idempotency_key": f"assistant-task:{proposal['id']}",
            **_task_link_payload(_first_target_ref(proposal)),
        }
        try:
            task = await task_service.create_task(
                tenant_id=user["tenant_id"],
                actor_user_id=user["id"],
                actor_email=user.get("email") or "assistant",
                payload={k: v for k, v in task_payload.items() if v is not None},
            )
        except task_service.TaskError as exc:
            raise BusinessAssistantError(exc.code, exc.detail, exc.status_code) from exc
        return {
            "status": "succeeded",
            "canonical_service": "tasks",
            "task_id": task["id"],
            "route": "/team/tasks",
            "mutated": True,
            "assistant_summary": "Internal task created after confirmation.",
        }
    if action_type == "internal_note":
        _require_perm(user, Perm.NOTE_CREATE.value)
        note_payload = {
            "title": payload.get("title") or proposal.get("title") or "Assistant note",
            "body": payload.get("body") or payload.get("content_text") or proposal.get("summary"),
            "visibility": "internal",
            "pinned": False,
            **_note_link_payload(_first_target_ref(proposal)),
        }
        try:
            note = await communication_service.create_note(
                tenant_id=user["tenant_id"],
                actor_user_id=user["id"],
                actor_email=user.get("email") or "assistant",
                payload={k: v for k, v in note_payload.items() if v is not None},
                record_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"assistant-note:{user['tenant_id']}:{proposal['id']}")),
            )
        except communication_service.CommunicationError as exc:
            raise BusinessAssistantError(exc.code, exc.detail, exc.status_code) from exc
        return {
            "status": "succeeded",
            "canonical_service": "internal_notes",
            "note_id": note["id"],
            "route": f"/team/notes?note={note['id']}",
            "mutated": True,
            "assistant_summary": "Internal note created after confirmation.",
        }
    if action_type == "report_draft":
        draft = AIStudioEditableDraft(
            tenant_id=user["tenant_id"],
            creator_user_id=user["id"],
            tool_key="business_assistant",
            mode_key="report_draft",
            family_key="business_assistant",
            capability_key="assistant.chat",
            usage_band="heavy",
            draft_type="document",
            title=payload.get("title") or proposal.get("title") or "Assistant report draft",
            content_text=payload.get("body") or payload.get("content_text") or "",
            content_json={"assistant_proposal_id": proposal["id"], "report_type": payload.get("report_type") or "internal"},
            warnings=["Editable report draft only. Nothing was exported, printed, emailed, or published."],
        ).model_dump()
        await db.ai_studio_editable_drafts.insert_one(prepare_for_mongo(draft))
        return {"status": "succeeded", "canonical_service": "ai_studio_editable_drafts", "draft_id": draft["id"], "exported": False, "assistant_summary": "Report draft created. Nothing was exported, printed, emailed, or published."}
    if action_type == "studio_delegation":
        tool_key = payload.get("tool_key") or proposal.get("preview", {}).get("tool_key") or "social_post_builder"
        mode_key = payload.get("mode_key") or proposal.get("preview", {}).get("mode_key") or "completed_work_showcase"
        ref = _first_target_ref(proposal)
        query = f"tool={tool_key}&mode={mode_key}"
        if ref.get("type") and ref.get("id"):
            query += f"&context_type={ref['type']}&context_id={ref['id']}"
        return {
            "status": "succeeded",
            "canonical_service": "ai_studio_delegation",
            "route": f"/studio?{query}",
            "created_record": False,
            "mutated": False,
            "assistant_summary": "Existing AI Studio tool delegation prepared. No Studio asset was generated automatically.",
        }
    return {"status": "unsupported", "canonical_service": None, "mutated": False, "assistant_summary": "Unsupported action. No records were changed."}


async def list_memory(user: dict[str, Any]) -> dict[str, Any]:
    from .assistant_actions import actor
    user = await actor(user)
    await _require_assistant_access(user)
    cursor = db.assistant_memory_entries.find({"tenant_id": user["tenant_id"], "user_id": user["id"], "status": "active"}, {"_id": 0}).sort("updated_at", -1)
    items = [serialize_doc(d) async for d in cursor if await assistant_context.memory_visible(user, d)]
    return {"items": items, "total": len(items)}


async def upsert_memory(user: dict, fields: dict) -> dict:
    from .assistant_memory import save
    return await save(user, fields)


async def delete_memory(user: dict[str, Any], memory_id: str) -> dict[str, Any]:
    from .assistant_actions import actor
    user = await actor(user)
    await _require_assistant_access(user)
    doc = await db.assistant_memory_entries.find_one({"tenant_id": user["tenant_id"], "user_id": user["id"], "id": memory_id}, {"_id": 0})
    if not doc:
        raise BusinessAssistantError("memory_not_found", "Assistant memory not found", 404)
    await db.assistant_memory_entries.update_one({"tenant_id": user["tenant_id"], "user_id": user["id"], "id": memory_id}, {"$set": {"status": "deleted", "deleted_at": _now_iso(), "updated_at": _now_iso()}})
    await _audit(user, "assistant.memory_deleted", "assistant_memory_entry", memory_id, "Assistant memory deleted")
    return {"deleted": True, "id": memory_id}


async def create_routine(user: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    await _require_assistant_access(user)
    doc = AssistantRoutine(
        tenant_id=user["tenant_id"],
        user_id=user["id"],
        name=str(fields.get("name") or "Assistant routine")[:160],
        prompt=str(fields.get("prompt") or ""),
        mode=_mode_key(fields.get("mode")),  # type: ignore[arg-type]
        schedule=fields.get("schedule") or {},
        next_run_at=fields.get("next_run_at"),
        generated_proposal_only=True,
    ).model_dump()
    await db.assistant_routines.insert_one(prepare_for_mongo(doc))
    await _audit(user, "assistant.routine_created", "assistant_routine", doc["id"], "Assistant routine created")
    return serialize_doc(doc)


async def list_routines(user: dict[str, Any]) -> dict[str, Any]:
    await _require_assistant_access(user)
    cursor = db.assistant_routines.find({"tenant_id": user["tenant_id"], "user_id": user["id"], "status": {"$ne": "archived"}}, {"_id": 0}).sort("next_run_at", 1)
    items = [serialize_doc(d) async for d in cursor]
    return {"items": items, "total": len(items)}


async def _routine(user: dict[str, Any], routine_id: str) -> dict[str, Any]:
    doc = await db.assistant_routines.find_one({"tenant_id": user["tenant_id"], "user_id": user["id"], "id": routine_id}, {"_id": 0})
    if not doc:
        raise BusinessAssistantError("routine_not_found", "Assistant routine not found", 404)
    return serialize_doc(doc)


async def update_routine(user: dict[str, Any], routine_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    await _require_assistant_access(user)
    routine = await _routine(user, routine_id)
    if routine.get("status") == "archived":
        raise BusinessAssistantError("routine_archived", "Archived routines cannot be updated", 409)
    updates: dict[str, Any] = {}
    if "name" in fields and fields.get("name"):
        updates["name"] = str(fields["name"])[:160]
    if "prompt" in fields:
        updates["prompt"] = str(fields.get("prompt") or "")
    if "mode" in fields:
        updates["mode"] = _mode_key(fields.get("mode"))
    if "schedule" in fields:
        updates["schedule"] = fields.get("schedule") or {}
    if "next_run_at" in fields:
        updates["next_run_at"] = fields.get("next_run_at")
    if not updates:
        raise BusinessAssistantError("routine_no_updates", "No routine updates provided", 400)
    updates["updated_at"] = _now_iso()
    await db.assistant_routines.update_one({"tenant_id": user["tenant_id"], "user_id": user["id"], "id": routine_id}, {"$set": prepare_for_mongo(updates)})
    await _audit(user, "assistant.routine_updated", "assistant_routine", routine_id, "Assistant routine updated")
    return await _routine(user, routine_id)


async def set_routine_status(user: dict[str, Any], routine_id: str, status: str) -> dict[str, Any]:
    await _require_assistant_access(user)
    if status not in {"active", "paused", "archived"}:
        raise BusinessAssistantError("invalid_routine_status", "Unsupported routine status", 400)
    await _routine(user, routine_id)
    updates = {"status": status, "updated_at": _now_iso()}
    await db.assistant_routines.update_one({"tenant_id": user["tenant_id"], "user_id": user["id"], "id": routine_id}, {"$set": updates})
    action = "assistant.routine_deleted" if status == "archived" else f"assistant.routine_{status}"
    await _audit(user, action, "assistant_routine", routine_id, f"Assistant routine {status}")
    return await _routine(user, routine_id)


def _quick_action(label: str, prompt: str, *, mode: str, required_permissions: list[str], action_type: Optional[str] = None) -> dict[str, Any]:
    return {"label": label, "prompt": prompt, "mode": mode, "required_permissions": required_permissions, "action_type": action_type}


async def list_quick_actions(user: dict[str, Any], *, mode: Optional[str] = None) -> dict[str, Any]:
    await _require_assistant_access(user)
    selected = _mode_key(mode)
    actions = [
        _quick_action("Latest invoice", "What is the latest invoice?", mode="finance", required_permissions=[Perm.INVOICE_READ.value]),
        _quick_action("Overdue invoices", "Show overdue invoices.", mode="finance", required_permissions=[Perm.INVOICE_READ.value]),
        _quick_action("Money this week", "How much money this week?", mode="finance", required_permissions=[Perm.FINANCE_READ.value]),
        _quick_action("Quote follow-ups", "Which quotes need follow-up?", mode="operations", required_permissions=[Perm.QUOTE_READ.value]),
        _quick_action("Production blockers", "What production blockers need attention?", mode="production", required_permissions=[Perm.WORK_ORDER_READ.value]),
        _quick_action("Workers today", "Who is working today?", mode="workforce", required_permissions=[Perm.SCHEDULE_READ.value]),
        _quick_action("Draft customer email", "Draft an email to this customer.", mode="operations", required_permissions=[Perm.EMAIL_SEND.value], action_type="email_draft"),
        _quick_action("Completed wrap post", "Open the Studio social-post tool for a completed wrap.", mode="operations", required_permissions=[Perm.AI_TOOL_USE.value, Perm.WRAP_LAB_READ.value], action_type="studio_delegation"),
    ]
    visible = [
        action for action in actions
        if (selected == "owner" or action["mode"] == selected or action["mode"] == "finance" and selected == "owner")
        and all(_has_perm(user, perm) for perm in action["required_permissions"])
    ]
    return {"items": visible, "total": len(visible), "mode": selected}


async def create_studio_delegation(user: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    await _require_assistant_access(user)
    _require_perm(user, Perm.AI_TOOL_USE.value)
    context = await _validate_context(user, fields.get("context") or {}, conversation_id=fields.get("conversation_id"), mode=_mode_key(fields.get("mode")))
    tool_key = str(fields.get("tool_key") or "social_post_builder")
    mode_key = str(fields.get("mode_key") or "completed_work_showcase")
    query = f"tool={tool_key}&mode={mode_key}"
    if context:
        query += f"&context_type={context['source_entity_type']}&context_id={context['source_entity_id']}"
    route = f"/studio?{query}"
    await _audit(user, "assistant.studio_delegation_created", "assistant_delegation", tool_key, "Assistant delegated to existing AI Studio tool")
    return {
        "delegation_type": "ai_studio",
        "route": route,
        "tool_key": tool_key,
        "mode_key": mode_key,
        "context_snapshot": context,
        "created_record": False,
        "message": "Open the existing AI Studio tool with this validated context. No Studio result was created automatically.",
    }


async def list_insights(user: dict[str, Any], *, generate: bool = False) -> dict[str, Any]:
    await _require_assistant_access(user)
    if generate:
        await _generate_proactive_insights(user)
    cursor = db.assistant_insights.find({"tenant_id": user["tenant_id"], "user_id": user["id"], "status": "new"}, {"_id": 0}).sort("created_at", -1).limit(100)
    items = [serialize_doc(d) async for d in cursor if _insight_visible(user, d)]
    return {"items": items, "total": len(items)}


def _insight_visible(user: dict, insight: dict) -> bool:
    return all(ref.get("source_type") in CONTEXT_TARGETS and _has_perm(user, CONTEXT_TARGETS[ref["source_type"]]["read_perm"])
               for ref in insight.get("source_citations", []))


async def _generate_proactive_insights(user: dict[str, Any]) -> None:
    if not _has_perm(user, Perm.INVOICE_READ.value):
        return
    count = await db.invoices.count_documents({"tenant_id": user["tenant_id"], "document_status": {"$ne": "void"}, "financial_status": {"$nin": ["paid", "refunded", "voided"]}})
    if count <= 0:
        return
    dedupe = f"{user['tenant_id']}:{user['id']}:open-invoices:{utc_now().date().isoformat()}"
    existing = await db.assistant_insights.find_one({"tenant_id": user["tenant_id"], "dedupe_key": dedupe, "status": "new"}, {"_id": 0})
    if existing:
        return
    doc = AssistantInsight(
        tenant_id=user["tenant_id"],
        user_id=user["id"],
        insight_key="open_invoices",
        title="Open invoices need review",
        summary=f"{count} open non-paid invoice(s) need follow-up review.",
        severity="warning",
        source_citations=[{"source_type": "invoice", "source_id": "invoice_list", "route": "/invoices", "calculation": {"count": count}}],
        dedupe_key=dedupe,
        window={"date": utc_now().date().isoformat()},
    ).model_dump()
    await db.assistant_insights.insert_one(prepare_for_mongo(doc))


async def dismiss_insight(user: dict[str, Any], insight_id: str) -> dict[str, Any]:
    await _require_assistant_access(user)
    filt = {"tenant_id": user["tenant_id"], "user_id": user["id"], "id": insight_id}
    doc = await db.assistant_insights.find_one(filt, {"_id": 0})
    if not doc or not _insight_visible(user, doc):
        raise BusinessAssistantError("insight_not_found", "Assistant insight not found", 404)
    await db.assistant_insights.update_one(filt, {"$set": {"status": "dismissed", "dismissed_by_user_id": user["id"], "dismissed_at": _now_iso(), "updated_at": _now_iso()}})
    return serialize_doc(await db.assistant_insights.find_one(filt, {"_id": 0}))


def voice_config() -> dict[str, Any]:
    from . import assistant_realtime
    settings = get_settings()
    return {
        **voice_policy(),
        "stage": "realtime",
        "interactions_available": assistant_realtime.configured(),
        "max_seconds": settings.assistant_voice_max_seconds,
        "idle_seconds": settings.assistant_voice_idle_seconds,
        "max_responses": settings.assistant_voice_max_responses,
        "message": "Voice is available when an authorized compatible model, credits and server budget are configured. Text remains available.",
        "voices": voice_options(),
        "provider": "openai",
        "architecture": "realtime_webrtc",
        "enabled": bool(settings.openai_realtime_enabled),
        "configured": bool(settings.openai_api_key and settings.openai_realtime_enabled),
        "model": settings.openai_realtime_model,
        "voice": settings.openai_realtime_voice,
        "turn_detection": settings.openai_realtime_turn_detection,
        "push_to_talk_default": settings.openai_realtime_push_to_talk_default,
        "transcript_retention": settings.assistant_transcript_retention,
        "raw_audio_stored": False,
    }


async def create_realtime_session(user: dict, fields: dict) -> dict:
    from . import assistant_realtime
    return await assistant_realtime.start(user, fields)










async def record_voice_usage(user: dict, voice_session_id: str, fields: dict) -> dict:
    await _require_assistant_access(user)
    raise BusinessAssistantError("client_voice_usage_rejected", "Voice usage is observed by the backend; browser billing events are not accepted", 403)
