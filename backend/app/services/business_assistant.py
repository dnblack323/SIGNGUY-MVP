"""EC18 Business Assistant service.

The assistant owns conversation, action-safety, voice-session metadata, and
deterministic BI contracts. AI governance and metering remain owned by EC16.
"""
from __future__ import annotations

from datetime import timedelta
import hashlib
from typing import Any, Optional

import httpx
from pymongo.errors import DuplicateKeyError

from ..core.config import get_settings
from ..core.db import db
from ..core.permissions import Perm, permissions_for_role
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.ai_gateway import AICapability, AIModelProfile, AIPromptVersion, AIProviderConfig
from ..models.ai_studio import AIStudioEditableDraft
from ..models.business_assistant import (
    AssistantActionExecution,
    AssistantActionProposal,
    AssistantContextSnapshot,
    AssistantConversation,
    AssistantInsight,
    AssistantMemoryEntry,
    AssistantMessage,
    AssistantRoutine,
    AssistantSourceCitation,
    AssistantVoiceSession,
)
from . import ai_gateway
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
    existing = await db.ai_provider_configs.find_one({"provider_key": LOCAL_PROVIDER_KEY}, {"_id": 0})
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
    await db.ai_provider_configs.insert_one(prepare_for_mongo(doc))
    return serialize_doc(doc)


async def _ensure_local_model(provider: dict[str, Any]) -> dict[str, Any]:
    existing = await db.ai_model_profiles.find_one({"provider_config_id": provider["id"], "model_key": LOCAL_MODEL_KEY}, {"_id": 0})
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
    await db.ai_model_profiles.insert_one(prepare_for_mongo(doc))
    return serialize_doc(doc)


async def _ensure_local_capability(capability_key: str, model_profile_id: str) -> dict[str, Any]:
    existing = await db.ai_capabilities.find_one({"capability_key": capability_key}, {"_id": 0})
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
    await db.ai_capabilities.insert_one(prepare_for_mongo(doc))
    return serialize_doc(doc)


async def _ensure_local_prompt(capability_key: str) -> dict[str, Any]:
    prompt_key = f"{capability_key}.ec18_local"
    existing = await db.ai_prompt_versions.find_one({"prompt_key": prompt_key, "version": LOCAL_PROMPT_VERSION}, {"_id": 0})
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
    await db.ai_prompt_versions.insert_one(prepare_for_mongo(doc))
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
        doc = await db.assistant_conversations.find_one({"tenant_id": user["tenant_id"], "id": conversation_id, "status": {"$ne": "deleted"}}, {"_id": 0})
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
    await _require_assistant_access(user)
    convo = await _conversation(user, conversation_id)
    messages = [
        serialize_doc(d)
        async for d in db.assistant_messages.find({"tenant_id": user["tenant_id"], "conversation_id": conversation_id}, {"_id": 0}).sort("created_at", 1)
    ]
    return {"conversation": convo, "messages": messages}


async def _insert_message(user: dict[str, Any], *, conversation_id: str, role: str, content_text: str, mode: str, context_snapshot_id: Optional[str] = None, action_request_id: Optional[str] = None, citation_ids: Optional[list[str]] = None, proposal_ids: Optional[list[str]] = None, voice_session_id: Optional[str] = None, metadata: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    msg = AssistantMessage(
        tenant_id=user["tenant_id"],
        conversation_id=conversation_id,
        user_id=user["id"] if role == "user" else None,
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


async def _meter_assistant(user: dict[str, Any], *, capability_key: str, conversation_id: str, prompt: str, source_links: Optional[list[dict[str, Any]]] = None, idempotency_key: Optional[str] = None) -> dict[str, Any]:
    capability = await db.ai_capabilities.find_one({"capability_key": capability_key, "status": "active"}, {"_id": 0})
    if not capability:
        raise BusinessAssistantError("assistant_capability_not_bootstrapped", "Platform AI admin must bootstrap EC18 assistant capabilities before execution", 409)
    prompt_doc = await db.ai_prompt_versions.find_one({"capability_key": capability_key, "status": "published"}, {"_id": 0}, sort=[("published_at", -1)])
    try:
        return await ai_gateway.create_gateway_request(
            user,
            {
                "capability_key": capability_key,
                "prompt_version_id": prompt_doc.get("id") if prompt_doc else None,
                "session_id": conversation_id,
                "idempotency_key": idempotency_key,
                "input_units": max(1, len(prompt) // 4),
                "output_units": 1,
                "estimated_cost_micros": 0,
                "duration_ms": 0,
                "source_links": source_links or [],
                "simulate_result": "success",
            },
        )
    except ai_gateway.AIGatewayError as exc:
        raise BusinessAssistantError(exc.code, exc.detail, exc.status_code)


async def ask_assistant(user: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    await _require_assistant_access(user)
    prompt = str(fields.get("message") or "").strip()
    if not prompt:
        raise BusinessAssistantError("message_required", "Message is required", 400)
    mode = _mode_key(fields.get("mode"))
    convo = await _conversation(user, fields.get("conversation_id"), mode=mode)
    context = await _validate_context(user, fields.get("context") or {}, conversation_id=convo["id"], mode=mode)
    user_msg = await _insert_message(user, conversation_id=convo["id"], role="user", content_text=prompt, mode=mode, context_snapshot_id=context.get("id") if context else None)
    action = await _meter_assistant(
        user,
        capability_key="assistant.chat",
        conversation_id=convo["id"],
        prompt=prompt,
        source_links=(context.get("source_links") if context else []),
        idempotency_key=fields.get("idempotency_key"),
    )
    answer, citations, missing = await _answer_business_question(user, conversation_id=convo["id"], prompt=prompt, mode=mode, context=context)
    assistant_msg = await _insert_message(
        user,
        conversation_id=convo["id"],
        role="assistant",
        content_text=answer,
        mode=mode,
        context_snapshot_id=context.get("id") if context else None,
        action_request_id=action["id"],
        citation_ids=[c["id"] for c in citations],
        metadata={"missing_data": missing, "credit_display": CREDIT_DISPLAY},
    )
    for citation in citations:
        await db.assistant_source_citations.update_one({"id": citation["id"]}, {"$set": {"message_id": assistant_msg["id"]}})
    await _audit(user, "assistant.message_answered", "assistant_conversation", convo["id"], "Assistant answered with source-linked context")
    return {
        "conversation": await _conversation(user, convo["id"]),
        "user_message": user_msg,
        "assistant_message": assistant_msg,
        "answer": answer,
        "sources": citations,
        "missing_data": missing,
        "action_request": action,
        "credit_display": CREDIT_DISPLAY,
    }


async def _answer_business_question(user: dict[str, Any], *, conversation_id: str, prompt: str, mode: str, context: Optional[dict[str, Any]]) -> tuple[str, list[dict[str, Any]], list[str]]:
    text = prompt.lower()
    citations: list[dict[str, Any]] = []
    missing: list[str] = []
    tenant_id = user["tenant_id"]
    if "latest invoice" in text or ("last" in text and "invoice" in text):
        _require_perm(user, Perm.INVOICE_READ.value)
        invoice = await db.invoices.find_one({"tenant_id": tenant_id}, {"_id": 0}, sort=[("created_at", -1)])
        if not invoice:
            return "I could not find any invoices for this tenant.", [], ["invoices"]
        route = f"/invoices/{invoice['id']}"
        citations.append(await _create_citation(tenant_id, conversation_id=conversation_id, source_type="invoice", source_id=invoice["id"], source_label=f"Invoice {invoice.get('number') or invoice['id']}", route=route, source_updated_at=str(invoice.get("updated_at") or invoice.get("created_at"))))
        total = int(invoice.get("total_cents") or 0)
        return f"Latest invoice: {invoice.get('number') or invoice['id']} for ${total / 100:.2f}. Status: {invoice.get('financial_status') or invoice.get('document_status') or 'unknown'}.", citations, []
    if "overdue invoice" in text or "unpaid invoice" in text:
        _require_perm(user, Perm.INVOICE_READ.value)
        filt = {"tenant_id": tenant_id, "document_status": {"$ne": "void"}, "financial_status": {"$nin": ["paid", "refunded", "voided"]}}
        invoices = [d async for d in db.invoices.find(filt, {"_id": 0}).sort("created_at", -1).limit(25)]
        total = sum(int(inv.get("balance_due_cents", inv.get("total_cents", 0)) or 0) for inv in invoices)
        citations.append(await _create_citation(tenant_id, conversation_id=conversation_id, source_type="invoice", source_id="invoice_list", source_label="Invoice list", route="/invoices", calculation={"basis": "open_non_paid_invoices", "count": len(invoices), "amount_cents": total}, missing_data=["due dates"] if invoices else []))
        return f"I found {len(invoices)} open non-paid invoice(s) totaling about ${total / 100:.2f}. This is invoice-basis and may not equal cash collected.", citations, ["due dates"] if invoices else []
    if "money this week" in text or "revenue" in text:
        _require_perm(user, Perm.FINANCE_READ.value)
        week_start = (utc_now() - timedelta(days=7)).isoformat()
        invoices = [d async for d in db.invoices.find({"tenant_id": tenant_id, "document_status": "issued", "created_at": {"$gte": week_start}}, {"_id": 0}).limit(200)]
        total = sum(int(inv.get("total_cents") or 0) for inv in invoices)
        citations.append(await _create_citation(tenant_id, conversation_id=conversation_id, source_type="invoice", source_id="invoice_week", source_label="Issued invoices this week", route="/finance", date_range={"start": week_start, "end": _now_iso()}, calculation={"basis": "issued_invoices_created_last_7_days", "count": len(invoices), "amount_cents": total}, missing_data=["payments received", "cost of goods", "labor cost"]))
        return f"Invoice-basis revenue for issued invoices created in the last 7 days is ${total / 100:.2f} across {len(invoices)} invoice(s). This is an estimate because payment and cost categories are not included.", citations, ["payments received", "cost of goods", "labor cost"]
    if "quote follow" in text or (("follow up" in text or "follow-up" in text or "followup" in text) and "quote" in text):
        _require_perm(user, Perm.QUOTE_READ.value)
        quotes = [d async for d in db.quotes.find({"tenant_id": tenant_id, "status": {"$nin": ["accepted", "declined", "converted"]}}, {"_id": 0}).sort("updated_at", -1).limit(25)]
        citations.append(await _create_citation(tenant_id, conversation_id=conversation_id, source_type="quote", source_id="quote_followup_list", source_label="Quote follow-up list", route="/quotes", calculation={"basis": "open_non_converted_quotes", "count": len(quotes)}, missing_data=["last customer contact"] if quotes else []))
        return f"I found {len(quotes)} open quote(s) that may need follow-up. Create a bulk email-draft proposal if you want a reviewable draft list; no emails are sent automatically.", citations, ["last customer contact"] if quotes else []
    if "margin" in text or "profit" in text or "losing money" in text or "apparel" in text:
        if _has_perm(user, Perm.FINANCE_READ.value):
            _require_perm(user, Perm.FINANCE_READ.value)
        elif _has_perm(user, Perm.PRICING_READ.value):
            _require_perm(user, Perm.PRICING_READ.value)
        else:
            _require_perm(user, Perm.FINANCE_READ.value)
        count = await db.pricing_snapshots.count_documents({"tenant_id": tenant_id})
        citations.append(await _create_citation(tenant_id, conversation_id=conversation_id, source_type="pricing_snapshot", source_id="pricing_snapshot_list", source_label="Pricing snapshots", route="/pricing-foundation", calculation={"basis": "pricing_snapshot_count", "count": count}, missing_data=["actual labor time", "actual material usage", "overhead allocation", "refunds/discounts"]))
        return "Profit and margin require complete cost inputs. I can treat this as an estimate only because actual labor, material usage, overhead allocation, and refunds/discounts may be missing.", citations, ["actual labor time", "actual material usage", "overhead allocation", "refunds/discounts"]
    if "late job" in text or "production blocker" in text or "production report" in text:
        _require_perm(user, Perm.WORK_ORDER_READ.value)
        work_orders = [d async for d in db.work_orders.find({"tenant_id": tenant_id}, {"_id": 0}).sort("updated_at", -1).limit(25)]
        citations.append(await _create_citation(tenant_id, conversation_id=conversation_id, source_type="work_order", source_id="work_order_list", source_label="Work order list", route="/work-orders", calculation={"basis": "recent_work_orders", "count": len(work_orders)}, missing_data=["stage due dates"] if work_orders else []))
        return f"I found {len(work_orders)} recent work order(s). I can summarize blockers only where production stages or due dates are present; missing stage dates are called out as incomplete data.", citations, ["stage due dates"] if work_orders else []
    if "worker" in text or "working today" in text or "staff" in text:
        _require_perm(user, Perm.SCHEDULE_READ.value)
        today = utc_now().date().isoformat()
        shifts = [d async for d in db.schedule_shifts.find({"tenant_id": tenant_id, "start_at": {"$regex": f"^{today}"}}, {"_id": 0}).limit(100)]
        citations.append(await _create_citation(tenant_id, conversation_id=conversation_id, source_type="schedule_shift", source_id="today", source_label="Today's schedule", route="/team/schedule", date_range={"date": today}, calculation={"basis": "schedule_shifts_starting_today", "count": len(shifts)}, missing_data=[]))
        return f"{len(shifts)} shift(s) are scheduled today based on shop schedule records.", citations, []
    if context:
        citations.append(await _create_citation(
            tenant_id,
            conversation_id=conversation_id,
            source_type=context["source_entity_type"],
            source_id=context["source_entity_id"],
            source_label=context["payload_summary"].get("label") or context["source_entity_type"],
            route=context.get("source_route"),
            source_updated_at=context.get("source_updated_at"),
            missing_data=[],
        ))
        return f"I found the selected {context['source_entity_type'].replace('_', ' ')} and can use it as context. Ask for a specific summary, draft, follow-up, schedule, invoice, or production question.", citations, []
    return "I can answer shop questions when the answer is supported by tenant records. Try asking about latest invoice, overdue invoices, money this week, workers today, late jobs, quote follow-ups, or production blockers.", [], []


async def propose_action(user: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    await _require_assistant_access(user)
    mode = _mode_key(fields.get("mode"))
    convo = await _conversation(user, fields.get("conversation_id"), mode=mode)
    action_type = str(fields.get("action_type") or "").strip()
    if not action_type:
        raise BusinessAssistantError("action_type_required", "Action type is required", 400)
    if action_type not in ACTION_PERMISSIONS:
        proposal = await _save_proposal(user, convo["id"], mode, fields, status="unsupported", warnings=["Unsupported action. No app data was changed."], required_permissions=[])
        await _audit(user, "assistant.action_unsupported", "assistant_action_proposal", proposal["id"], "Unsupported assistant action rejected")
        return proposal
    required = ACTION_PERMISSIONS[action_type]
    for perm in required:
        _require_perm(user, perm)
    target_refs = fields.get("target_refs") or []
    source_links = []
    for ref in target_refs:
        snap = await _validate_context(user, {"source_entity_type": ref.get("type"), "source_entity_id": ref.get("id")}, conversation_id=convo["id"], mode=mode)
        if snap:
            source_links.extend(snap.get("source_links") or [])
    await _meter_assistant(user, capability_key="assistant.action_parse", conversation_id=convo["id"], prompt=str(fields), source_links=source_links, idempotency_key=fields.get("metering_idempotency_key"))
    proposal = await _save_proposal(user, convo["id"], mode, fields, status="proposed", warnings=_proposal_warnings(action_type, target_refs), required_permissions=required)
    await _insert_message(user, conversation_id=convo["id"], role="assistant", content_text=f"Action proposal ready: {proposal['title']}", mode=mode, proposal_ids=[proposal["id"]])
    await _audit(user, "assistant.action_proposed", "assistant_action_proposal", proposal["id"], "Assistant action proposal created")
    return proposal


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
        expires_at=(utc_now() + timedelta(hours=24)).isoformat(),
    ).model_dump()
    try:
        await db.assistant_action_proposals.insert_one(prepare_for_mongo(proposal))
    except DuplicateKeyError:
        existing = await db.assistant_action_proposals.find_one({"tenant_id": user["tenant_id"], "idempotency_key": fields.get("idempotency_key")}, {"_id": 0})
        if existing:
            return serialize_doc(existing)
        raise
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
    return {"summary": "Unsupported action. No data will be changed."}


def _proposal_warnings(action_type: str, target_refs: list[dict[str, Any]]) -> list[str]:
    if action_type == "email_draft":
        return ["Draft only. Nothing is sent until a human sends it through the canonical email workflow."]
    if action_type == "bulk_email_draft":
        return [f"Bulk proposal affects {len(target_refs)} target(s). Review every recipient before confirming.", "No email will be sent automatically."]
    return []


async def edit_proposal(user: dict[str, Any], proposal_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    await _require_assistant_access(user)
    proposal = await _proposal(user, proposal_id)
    if proposal["status"] not in {"proposed", "edited"}:
        raise BusinessAssistantError("proposal_not_editable", "Only proposed or edited actions can be changed", 409)
    updates = {"editable_payload": fields.get("editable_payload") or proposal.get("editable_payload") or {}, "status": "edited", "updated_at": _now_iso()}
    if fields.get("title"):
        updates["title"] = str(fields["title"])[:160]
    if fields.get("summary"):
        updates["summary"] = str(fields["summary"])[:1000]
    await db.assistant_action_proposals.update_one({"tenant_id": user["tenant_id"], "id": proposal_id}, {"$set": prepare_for_mongo(updates)})
    await _audit(user, "assistant.action_edited", "assistant_action_proposal", proposal_id, "Assistant action proposal edited")
    return await _proposal(user, proposal_id)


async def confirm_proposal(user: dict[str, Any], proposal_id: str) -> dict[str, Any]:
    await _require_assistant_access(user)
    proposal = await _proposal(user, proposal_id)
    if proposal["status"] not in {"proposed", "edited"}:
        raise BusinessAssistantError("proposal_not_confirmable", "Only proposed or edited actions can be confirmed", 409)
    for perm in proposal.get("required_permissions") or []:
        _require_perm(user, perm)
    await _check_stale_targets(user, proposal)
    await db.assistant_action_proposals.update_one(
        {"tenant_id": user["tenant_id"], "id": proposal_id},
        {"$set": {"status": "confirmed", "confirmed_by_user_id": user["id"], "confirmed_at": _now_iso(), "updated_at": _now_iso()}},
    )
    await _audit(user, "assistant.action_confirmed", "assistant_action_proposal", proposal_id, "Assistant action proposal confirmed")
    return await _proposal(user, proposal_id)


async def cancel_proposal(user: dict[str, Any], proposal_id: str) -> dict[str, Any]:
    await _require_assistant_access(user)
    proposal = await _proposal(user, proposal_id)
    if proposal["status"] in {"succeeded", "failed", "canceled"}:
        return proposal
    await db.assistant_action_proposals.update_one(
        {"tenant_id": user["tenant_id"], "id": proposal_id},
        {"$set": {"status": "canceled", "canceled_by_user_id": user["id"], "canceled_at": _now_iso(), "updated_at": _now_iso()}},
    )
    await _audit(user, "assistant.action_canceled", "assistant_action_proposal", proposal_id, "Assistant action proposal canceled")
    return await _proposal(user, proposal_id)


async def execute_proposal(user: dict[str, Any], proposal_id: str, *, idempotency_key: Optional[str] = None) -> dict[str, Any]:
    await _require_assistant_access(user)
    proposal = await _proposal(user, proposal_id)
    if proposal["status"] != "confirmed":
        raise BusinessAssistantError("proposal_confirmation_required", "Action must be confirmed before execution", 409)
    for perm in proposal.get("required_permissions") or []:
        _require_perm(user, perm)
    await _check_stale_targets(user, proposal)
    if idempotency_key:
        existing = await db.assistant_action_executions.find_one({"tenant_id": user["tenant_id"], "idempotency_key": idempotency_key}, {"_id": 0})
        if existing:
            return serialize_doc(existing)
    await db.assistant_action_proposals.update_one({"tenant_id": user["tenant_id"], "id": proposal_id}, {"$set": {"status": "executing", "updated_at": _now_iso()}})
    action = await _meter_assistant(user, capability_key=proposal.get("capability_key") or "assistant.action_parse", conversation_id=proposal["conversation_id"], prompt=str(proposal.get("editable_payload") or proposal.get("preview") or {}), idempotency_key=idempotency_key)
    result = await _execute_safe_canonical_action(user, proposal)
    execution = AssistantActionExecution(
        tenant_id=user["tenant_id"],
        proposal_id=proposal_id,
        conversation_id=proposal["conversation_id"],
        user_id=user["id"],
        status=result["status"],  # type: ignore[arg-type]
        idempotency_key=idempotency_key,
        canonical_service=result["canonical_service"],
        canonical_result=result,
        action_request_id=action["id"],
        executed_at=_now_iso(),
    ).model_dump()
    await db.assistant_action_executions.insert_one(prepare_for_mongo(execution))
    await db.assistant_action_proposals.update_one(
        {"tenant_id": user["tenant_id"], "id": proposal_id},
        {"$set": {"status": result["status"], "updated_at": _now_iso()}},
    )
    await _insert_message(user, conversation_id=proposal["conversation_id"], role="assistant", content_text=result["assistant_summary"], mode=proposal.get("mode", "owner"), action_request_id=action["id"])
    await _audit(user, f"assistant.action_{result['status']}", "assistant_action_proposal", proposal_id, result["assistant_summary"])
    return serialize_doc(execution)


async def _proposal(user: dict[str, Any], proposal_id: str) -> dict[str, Any]:
    doc = await db.assistant_action_proposals.find_one({"tenant_id": user["tenant_id"], "id": proposal_id}, {"_id": 0})
    if not doc:
        raise BusinessAssistantError("proposal_not_found", "Assistant action proposal not found", 404)
    return serialize_doc(doc)


async def _check_stale_targets(user: dict[str, Any], proposal: dict[str, Any]) -> None:
    for ref in proposal.get("target_refs") or []:
        ref_type = ref.get("type")
        ref_id = ref.get("id")
        if ref_type not in CONTEXT_TARGETS or not ref_id:
            continue
        target = CONTEXT_TARGETS[ref_type]
        coll = getattr(db, target["collection"])
        doc = await coll.find_one({"tenant_id": user["tenant_id"], "id": ref_id}, {"_id": 0, "updated_at": 1})
        if not doc:
            await db.assistant_action_proposals.update_one({"id": proposal["id"]}, {"$set": {"status": "stale", "stale_reason": "target_missing", "updated_at": _now_iso()}})
            raise BusinessAssistantError("proposal_stale", "Action target changed or disappeared; reconfirmation is required", 409)
        previous = ref.get("source_updated_at")
        if previous and str(doc.get("updated_at")) != str(previous):
            await db.assistant_action_proposals.update_one({"id": proposal["id"]}, {"$set": {"status": "stale", "stale_reason": "target_updated", "updated_at": _now_iso()}})
            raise BusinessAssistantError("proposal_stale", "Action target changed; reconfirmation is required", 409)


async def _execute_safe_canonical_action(user: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    action_type = proposal.get("action_type")
    payload = proposal.get("editable_payload") or {}
    if action_type == "email_draft":
        draft = AIStudioEditableDraft(
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
        await db.ai_studio_editable_drafts.insert_one(prepare_for_mongo(draft))
        return {"status": "succeeded", "canonical_service": "ai_studio_editable_drafts", "draft_id": draft["id"], "sent": False, "assistant_summary": "Email draft created. No email was sent."}
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
    return {"status": "unsupported", "canonical_service": None, "mutated": False, "assistant_summary": "Unsupported action. No records were changed."}


async def list_memory(user: dict[str, Any]) -> dict[str, Any]:
    await _require_assistant_access(user)
    cursor = db.assistant_memory_entries.find({"tenant_id": user["tenant_id"], "user_id": user["id"], "status": "active"}, {"_id": 0}).sort("updated_at", -1)
    items = [serialize_doc(d) async for d in cursor]
    return {"items": items, "total": len(items)}


async def upsert_memory(user: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    await _require_assistant_access(user)
    key = str(fields.get("memory_key") or "").strip().lower()
    content = str(fields.get("content_text") or "").strip()
    if not key or not content:
        raise BusinessAssistantError("memory_required", "Memory key and content are required", 400)
    if "api key" in content.lower() or "password" in content.lower() or "secret" in content.lower():
        raise BusinessAssistantError("secret_memory_rejected", "Secrets and credentials cannot be saved as assistant memory", 400)
    existing = await db.assistant_memory_entries.find_one({"tenant_id": user["tenant_id"], "user_id": user["id"], "memory_key": key, "status": "active"}, {"_id": 0})
    if existing:
        await db.assistant_memory_entries.update_one({"id": existing["id"]}, {"$set": {"content_text": content, "updated_at": _now_iso()}})
        return serialize_doc(await db.assistant_memory_entries.find_one({"id": existing["id"]}, {"_id": 0}))
    doc = AssistantMemoryEntry(tenant_id=user["tenant_id"], user_id=user["id"], memory_key=key, content_text=content).model_dump()
    await db.assistant_memory_entries.insert_one(prepare_for_mongo(doc))
    await _audit(user, "assistant.memory_saved", "assistant_memory_entry", doc["id"], "Assistant memory saved")
    return serialize_doc(doc)


async def delete_memory(user: dict[str, Any], memory_id: str) -> dict[str, Any]:
    await _require_assistant_access(user)
    doc = await db.assistant_memory_entries.find_one({"tenant_id": user["tenant_id"], "user_id": user["id"], "id": memory_id}, {"_id": 0})
    if not doc:
        raise BusinessAssistantError("memory_not_found", "Assistant memory not found", 404)
    await db.assistant_memory_entries.update_one({"id": memory_id}, {"$set": {"status": "deleted", "deleted_at": _now_iso(), "updated_at": _now_iso()}})
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
    cursor = db.assistant_insights.find({"tenant_id": user["tenant_id"], "status": "new"}, {"_id": 0}).sort("created_at", -1).limit(100)
    items = [serialize_doc(d) async for d in cursor]
    return {"items": items, "total": len(items)}


async def _generate_proactive_insights(user: dict[str, Any]) -> None:
    if not _has_perm(user, Perm.INVOICE_READ.value):
        return
    count = await db.invoices.count_documents({"tenant_id": user["tenant_id"], "document_status": {"$ne": "void"}, "financial_status": {"$nin": ["paid", "refunded", "voided"]}})
    if count <= 0:
        return
    dedupe = f"{user['tenant_id']}:open-invoices:{utc_now().date().isoformat()}"
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
    doc = await db.assistant_insights.find_one({"tenant_id": user["tenant_id"], "id": insight_id}, {"_id": 0})
    if not doc:
        raise BusinessAssistantError("insight_not_found", "Assistant insight not found", 404)
    await db.assistant_insights.update_one({"id": insight_id}, {"$set": {"status": "dismissed", "dismissed_by_user_id": user["id"], "dismissed_at": _now_iso(), "updated_at": _now_iso()}})
    return serialize_doc(await db.assistant_insights.find_one({"id": insight_id}, {"_id": 0}))


def voice_config() -> dict[str, Any]:
    settings = get_settings()
    return {
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


async def create_realtime_session(user: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    await _require_assistant_access(user)
    settings = get_settings()
    mode = _mode_key(fields.get("mode"))
    convo = await _conversation(user, fields.get("conversation_id"), mode=mode)
    config = voice_config()
    if not config["configured"]:
        voice_doc = AssistantVoiceSession(
            tenant_id=user["tenant_id"],
            user_id=user["id"],
            conversation_id=convo["id"],
            status="unavailable",
            model_key=settings.openai_realtime_model,
            voice=settings.openai_realtime_voice,
            unavailable_reason="OpenAI Voice is not configured",
        ).model_dump()
        await db.assistant_voice_sessions.insert_one(prepare_for_mongo(voice_doc))
        return {"configured": False, "status": "unavailable", "message": "OpenAI Voice is not configured", "voice_session": serialize_doc(voice_doc)}
    await _require_voice_credit_authorized(user)
    await _voice_rate_limit(user)
    safety_id = _safety_identifier(user)
    payload = {
        "session": {
            "type": "realtime",
            "model": settings.openai_realtime_model,
            "audio": {
                "output": {"voice": settings.openai_realtime_voice},
            },
            "turn_detection": {"type": settings.openai_realtime_turn_detection} if settings.openai_realtime_turn_detection else None,
            "instructions": "You are SignGuy AI Business Assistant. Use tool calls only to request backend proposals; never claim external actions succeeded without backend confirmation.",
        }
    }
    payload["session"] = {k: v for k, v in payload["session"].items() if v is not None}
    try:
        secret = await _request_openai_realtime_client_secret(settings=settings, safety_id=safety_id, payload=payload)
    except httpx.HTTPError as exc:
        voice_doc = AssistantVoiceSession(
            tenant_id=user["tenant_id"],
            user_id=user["id"],
            conversation_id=convo["id"],
            status="failed",
            model_key=settings.openai_realtime_model,
            voice=settings.openai_realtime_voice,
            unavailable_reason="OpenAI Realtime session creation failed",
            metadata={"error_type": exc.__class__.__name__},
        ).model_dump()
        await db.assistant_voice_sessions.insert_one(prepare_for_mongo(voice_doc))
        await _audit(user, "assistant.voice_session_failed", "assistant_voice_session", voice_doc["id"], "OpenAI Realtime session creation failed")
        raise BusinessAssistantError("voice_session_failed", "OpenAI Realtime session creation failed", 502)
    provider_session_id = secret.get("id") or secret.get("session", {}).get("id")
    voice_doc = AssistantVoiceSession(
        tenant_id=user["tenant_id"],
        user_id=user["id"],
        conversation_id=convo["id"],
        status="created",
        model_key=settings.openai_realtime_model,
        voice=settings.openai_realtime_voice,
        provider_session_id=provider_session_id,
        metadata={"ephemeral_credential_issued": True, "raw_audio_stored": False},
    ).model_dump()
    await db.assistant_voice_sessions.insert_one(prepare_for_mongo(voice_doc))
    await _audit(user, "assistant.voice_session_created", "assistant_voice_session", voice_doc["id"], "OpenAI Realtime voice session credential created")
    return {
        "configured": True,
        "voice_session": serialize_doc(voice_doc),
        "realtime": secret,
        "model": settings.openai_realtime_model,
        "voice": settings.openai_realtime_voice,
    }


async def _request_openai_realtime_client_secret(*, settings: Any, safety_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=settings.openai_realtime_timeout_seconds) as client:
        response = await client.post(
            "https://api.openai.com/v1/realtime/client_secrets",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
                "OpenAI-Safety-Identifier": safety_id,
            },
            json=payload,
        )
        response.raise_for_status()
        return response.json()


def _safety_identifier(user: dict[str, Any]) -> str:
    raw = f"{user['tenant_id']}:{user['id']}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


async def _voice_rate_limit(user: dict[str, Any]) -> None:
    settings = get_settings()
    window_start = (utc_now() - timedelta(seconds=settings.openai_realtime_rate_limit_window_seconds)).isoformat()
    count = await db.assistant_voice_sessions.count_documents({"tenant_id": user["tenant_id"], "user_id": user["id"], "created_at": {"$gte": window_start}})
    if count >= settings.openai_realtime_rate_limit_sessions:
        raise BusinessAssistantError("voice_rate_limit", "Too many voice sessions. Try again shortly.", 429)


async def _require_voice_credit_authorized(user: dict[str, Any]) -> None:
    capability = await db.ai_capabilities.find_one({"capability_key": "assistant.voice_reply", "status": "active"}, {"_id": 0})
    if not capability:
        raise BusinessAssistantError("assistant_capability_not_bootstrapped", "Platform AI admin must bootstrap EC18 assistant capabilities before voice activation", 409)
    try:
        account = await ai_gateway.get_credit_account(user["tenant_id"])
    except ai_gateway.AIGatewayError as exc:
        raise BusinessAssistantError(exc.code, exc.detail, exc.status_code)
    if account.get("status") != "active" or int(account.get("available_credits") or 0) <= 0:
        raise BusinessAssistantError("insufficient_ai_credits", "Insufficient AI credits", 402)


async def record_voice_usage(user: dict[str, Any], voice_session_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    await _require_assistant_access(user)
    voice = await db.assistant_voice_sessions.find_one({"tenant_id": user["tenant_id"], "id": voice_session_id}, {"_id": 0})
    if not voice:
        raise BusinessAssistantError("voice_session_not_found", "Voice session not found", 404)
    provider_event_id = fields.get("provider_event_id")
    if not provider_event_id:
        raise BusinessAssistantError("provider_event_required", "Provider usage event id is required", 400)
    action = await _meter_assistant(
        user,
        capability_key="assistant.voice_reply",
        conversation_id=voice.get("conversation_id") or voice_session_id,
        prompt="voice usage event",
        idempotency_key=f"voice:{voice_session_id}:{provider_event_id}",
    )
    updates = {
        "input_audio_seconds": int(fields.get("input_audio_seconds") or 0),
        "output_audio_seconds": int(fields.get("output_audio_seconds") or 0),
        "usage_event_ids": list(set((voice.get("usage_event_ids") or []) + [action["id"]])),
        "updated_at": _now_iso(),
    }
    await db.assistant_voice_sessions.update_one({"id": voice_session_id}, {"$set": updates})
    return {"voice_session": serialize_doc(await db.assistant_voice_sessions.find_one({"id": voice_session_id}, {"_id": 0})), "action_request": action}
