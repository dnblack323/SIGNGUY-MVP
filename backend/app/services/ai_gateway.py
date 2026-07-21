"""EC16 shared AI gateway service.

This module implements local metering, ledger, governance, and provider-boundary
contracts only. It never calls an external AI provider.
"""
from __future__ import annotations

from datetime import timezone
import re
from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.permissions import PlatformPerm, has_platform_admin_access
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.ai_gateway import (
    AIActionRequest,
    AIBudgetAlert,
    AICapability,
    AICreditAccount,
    AICreditLedgerEntry,
    AIGovernancePolicy,
    AIModelProfile,
    AIPromptVersion,
    AIProviderConfig,
    AIProviderCostLedgerEntry,
    AIProviderHealthEvent,
    AIUsageLedgerEntry,
)
from .activity import record_activity_with_audit
from .entitlements import has_entitlement


class AIGatewayError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
PUBLISHED_PROMPT_LOCKED_FIELDS = {"capability_key", "prompt_key", "version", "template", "input_schema", "output_schema", "checksum"}


def _now_iso() -> str:
    return utc_now().isoformat()


def _day_start_iso() -> str:
    now = utc_now().astimezone(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def _is_platform_ai_admin(user: dict) -> bool:
    return has_platform_admin_access(
        user,
        extra_permissions={PlatformPerm.PLATFORM_AI_CREDIT_ADMIN.value},
    )


def require_platform_ai_admin(user: dict) -> None:
    if not _is_platform_ai_admin(user):
        raise AIGatewayError("platform_ai_admin_required", "Platform AI admin access is required", 403)


def _has_staff_perm(user: dict, perm: str) -> bool:
    if user.get("role") in {"owner", "admin"}:
        return True
    return perm in set(user.get("permissions") or [])


def _clean_key(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if not KEY_RE.match(text):
        raise AIGatewayError(f"invalid_{field}", f"{field} must be a lowercase key", 400)
    return text


def _clean_text(value: Any, field: str, *, limit: int = 160) -> str:
    text = str(value or "").strip()
    if not text:
        raise AIGatewayError(f"{field}_required", f"{field} is required", 400)
    if len(text) > limit:
        raise AIGatewayError(f"{field}_too_long", f"{field} must be {limit} characters or fewer", 400)
    return text


async def _audit(user: dict, action: str, entity_type: str, entity_id: str, summary: str, metadata: Optional[dict] = None) -> None:
    await record_activity_with_audit(
        tenant_id=user["tenant_id"],
        actor_user_id=user["id"],
        actor_email=user.get("email", "ai-admin"),
        module="ai_gateway",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        metadata=metadata or {},
    )


async def create_provider_config(user: dict, fields: dict[str, Any]) -> dict[str, Any]:
    require_platform_ai_admin(user)
    doc = AIProviderConfig(
        provider_key=_clean_key(fields.get("provider_key"), "provider_key"),
        display_name=_clean_text(fields.get("display_name"), "display_name"),
        status=fields.get("status", "draft"),
        credential_mode=fields.get("credential_mode") or "platform_managed",
        supported_modalities=fields.get("supported_modalities") or [],
        byok_supported=bool(fields.get("byok_supported", False)),
        credential_reference=fields.get("credential_reference"),
        metadata=fields.get("metadata") or {},
    ).model_dump()
    try:
        await db.ai_provider_configs.insert_one(prepare_for_mongo(doc))
    except DuplicateKeyError:
        raise AIGatewayError("duplicate_provider_key", "Provider key already exists", 409)
    await _audit(user, "ai.provider_created", "ai_provider_config", doc["id"], f"AI provider created: {doc['provider_key']}")
    return serialize_doc(doc)


async def list_provider_configs() -> dict[str, Any]:
    items = [serialize_doc(d) async for d in db.ai_provider_configs.find({}, {"_id": 0}).sort("provider_key", 1)]
    return {"items": items, "total": len(items)}


async def update_provider_config(user: dict, provider_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    require_platform_ai_admin(user)
    doc = await db.ai_provider_configs.find_one({"id": provider_id}, {"_id": 0})
    if not doc:
        raise AIGatewayError("provider_not_found", "AI provider not found", 404)
    allowed = {k: v for k, v in updates.items() if k in {"display_name", "status", "credential_mode", "supported_modalities", "byok_supported", "credential_reference", "metadata"}}
    if not allowed:
        raise AIGatewayError("no_updates", "No supported updates provided", 400)
    if "display_name" in allowed:
        allowed["display_name"] = _clean_text(allowed["display_name"], "display_name")
    allowed["updated_at"] = _now_iso()
    await db.ai_provider_configs.update_one({"id": provider_id}, {"$set": prepare_for_mongo(allowed)})
    await _audit(user, "ai.provider_updated", "ai_provider_config", provider_id, "AI provider updated", {"fields": sorted(allowed)})
    return serialize_doc(await db.ai_provider_configs.find_one({"id": provider_id}, {"_id": 0}))


async def create_model_profile(user: dict, fields: dict[str, Any]) -> dict[str, Any]:
    require_platform_ai_admin(user)
    provider = await db.ai_provider_configs.find_one({"id": fields.get("provider_config_id")}, {"_id": 0})
    if not provider:
        raise AIGatewayError("provider_not_found", "AI provider not found", 404)
    doc = AIModelProfile(
        provider_config_id=provider["id"],
        provider_key=provider["provider_key"],
        model_key=_clean_key(fields.get("model_key"), "model_key"),
        display_name=_clean_text(fields.get("display_name"), "display_name"),
        task_category=_clean_key(fields.get("task_category"), "task_category"),
        intensity=_clean_key(fields.get("intensity", "standard"), "intensity"),
        status=fields.get("status", "draft"),
        input_unit_label=fields.get("input_unit_label") or "input_token",
        output_unit_label=fields.get("output_unit_label") or "output_token",
        estimated_input_cost_micros_per_unit=fields.get("estimated_input_cost_micros_per_unit", 0),
        estimated_output_cost_micros_per_unit=fields.get("estimated_output_cost_micros_per_unit", 0),
        metadata=fields.get("metadata") or {},
    ).model_dump()
    try:
        await db.ai_model_profiles.insert_one(prepare_for_mongo(doc))
    except DuplicateKeyError:
        raise AIGatewayError("duplicate_model_key", "Model key already exists for provider", 409)
    await _audit(user, "ai.model_profile_created", "ai_model_profile", doc["id"], f"AI model profile created: {doc['model_key']}")
    return serialize_doc(doc)


async def list_model_profiles() -> dict[str, Any]:
    items = [serialize_doc(d) async for d in db.ai_model_profiles.find({}, {"_id": 0}).sort([("provider_key", 1), ("model_key", 1)])]
    return {"items": items, "total": len(items)}


async def create_capability(user: dict, fields: dict[str, Any]) -> dict[str, Any]:
    require_platform_ai_admin(user)
    for model_id in fields.get("allowed_model_profile_ids") or []:
        if not await db.ai_model_profiles.find_one({"id": model_id}, {"_id": 0}):
            raise AIGatewayError("model_not_found", "Allowed model profile not found", 404)
    doc = AICapability(
        capability_key=_clean_key(fields.get("capability_key"), "capability_key"),
        display_name=_clean_text(fields.get("display_name"), "display_name"),
        feature_key=_clean_key(fields.get("feature_key"), "feature_key"),
        action_key=_clean_key(fields.get("action_key"), "action_key"),
        entitlement_feature_key=fields.get("entitlement_feature_key"),
        status=fields.get("status", "draft"),
        billable=bool(fields.get("billable", True)),
        default_credit_charge=fields.get("default_credit_charge", 1),
        allowed_model_profile_ids=fields.get("allowed_model_profile_ids") or [],
        context_requirements=fields.get("context_requirements") or {},
        metadata=fields.get("metadata") or {},
    ).model_dump()
    try:
        await db.ai_capabilities.insert_one(prepare_for_mongo(doc))
    except DuplicateKeyError:
        raise AIGatewayError("duplicate_capability_key", "Capability key already exists", 409)
    await _audit(user, "ai.capability_created", "ai_capability", doc["id"], f"AI capability created: {doc['capability_key']}")
    return serialize_doc(doc)


async def list_capabilities(*, status: Optional[str] = None) -> dict[str, Any]:
    filt = {"status": status} if status else {}
    items = [serialize_doc(d) async for d in db.ai_capabilities.find(filt, {"_id": 0}).sort("capability_key", 1)]
    return {"items": items, "total": len(items)}


async def create_prompt_version(user: dict, fields: dict[str, Any]) -> dict[str, Any]:
    require_platform_ai_admin(user)
    capability_key = _clean_key(fields.get("capability_key"), "capability_key")
    if not await db.ai_capabilities.find_one({"capability_key": capability_key}, {"_id": 0}):
        raise AIGatewayError("capability_not_found", "AI capability not found", 404)
    doc = AIPromptVersion(
        capability_key=capability_key,
        prompt_key=_clean_key(fields.get("prompt_key"), "prompt_key"),
        version=_clean_text(fields.get("version"), "version", limit=80),
        status=fields.get("status", "draft"),
        template=_clean_text(fields.get("template"), "template", limit=20000),
        input_schema=fields.get("input_schema") or {},
        output_schema=fields.get("output_schema") or {},
        checksum=fields.get("checksum"),
    ).model_dump()
    try:
        await db.ai_prompt_versions.insert_one(prepare_for_mongo(doc))
    except DuplicateKeyError:
        raise AIGatewayError("duplicate_prompt_version", "Prompt version already exists", 409)
    await _audit(user, "ai.prompt_version_created", "ai_prompt_version", doc["id"], f"AI prompt version created: {doc['prompt_key']} {doc['version']}")
    return serialize_doc(doc)


async def publish_prompt_version(user: dict, prompt_id: str) -> dict[str, Any]:
    require_platform_ai_admin(user)
    prompt = await db.ai_prompt_versions.find_one({"id": prompt_id}, {"_id": 0})
    if not prompt:
        raise AIGatewayError("prompt_not_found", "Prompt version not found", 404)
    if prompt["status"] == "published":
        return serialize_doc(prompt)
    if prompt["status"] != "draft":
        raise AIGatewayError("prompt_not_publishable", "Only draft prompt versions may be published", 409)
    now = _now_iso()
    await db.ai_prompt_versions.update_one(
        {"id": prompt_id},
        {"$set": {"status": "published", "published_by_user_id": user["id"], "published_at": now, "updated_at": now}},
    )
    await _audit(user, "ai.prompt_version_published", "ai_prompt_version", prompt_id, "AI prompt version published")
    return serialize_doc(await db.ai_prompt_versions.find_one({"id": prompt_id}, {"_id": 0}))


async def update_prompt_version(user: dict, prompt_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    require_platform_ai_admin(user)
    prompt = await db.ai_prompt_versions.find_one({"id": prompt_id}, {"_id": 0})
    if not prompt:
        raise AIGatewayError("prompt_not_found", "Prompt version not found", 404)
    if prompt["status"] == "published" and PUBLISHED_PROMPT_LOCKED_FIELDS.intersection(updates):
        raise AIGatewayError("published_prompt_immutable", "Published prompt versions are immutable; create a new version", 409)
    allowed = {k: v for k, v in updates.items() if k in PUBLISHED_PROMPT_LOCKED_FIELDS | {"status", "retired_at"}}
    if not allowed:
        raise AIGatewayError("no_updates", "No supported updates provided", 400)
    allowed["updated_at"] = _now_iso()
    await db.ai_prompt_versions.update_one({"id": prompt_id}, {"$set": prepare_for_mongo(allowed)})
    await _audit(user, "ai.prompt_version_updated", "ai_prompt_version", prompt_id, "AI prompt version updated", {"fields": sorted(allowed)})
    return serialize_doc(await db.ai_prompt_versions.find_one({"id": prompt_id}, {"_id": 0}))


async def _ensure_credit_account(tenant_id: str) -> dict[str, Any]:
    doc = await db.ai_credit_accounts.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if doc:
        return serialize_doc(doc)
    account = AICreditAccount(tenant_id=tenant_id).model_dump()
    try:
        await db.ai_credit_accounts.insert_one(prepare_for_mongo(account))
    except DuplicateKeyError:
        return serialize_doc(await db.ai_credit_accounts.find_one({"tenant_id": tenant_id}, {"_id": 0}))
    return serialize_doc(account)


async def get_credit_account(tenant_id: str) -> dict[str, Any]:
    account = await _ensure_credit_account(tenant_id)
    account["available_credits"] = max(
        0,
        int(account.get("included_balance_credits", 0)) + int(account.get("purchased_balance_credits", 0)) - int(account.get("reserved_credits", 0)),
    )
    return account


async def list_credit_ledger(tenant_id: str, *, limit: int = 100) -> dict[str, Any]:
    items = [
        serialize_doc(d)
        async for d in db.ai_credit_ledger_entries.find({"tenant_id": tenant_id}, {"_id": 0}).sort("created_at", -1).limit(limit)
    ]
    return {"items": items, "total": len(items)}


async def _insert_credit_ledger(account: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    entry = AICreditLedgerEntry(
        tenant_id=account["tenant_id"],
        credit_account_id=account["id"],
        balance_after_included_credits=account["included_balance_credits"],
        balance_after_purchased_credits=account["purchased_balance_credits"],
        reserved_after_credits=account["reserved_credits"],
        **fields,
    ).model_dump()
    try:
        await db.ai_credit_ledger_entries.insert_one(prepare_for_mongo(entry))
    except DuplicateKeyError:
        if entry.get("idempotency_key"):
            existing = await db.ai_credit_ledger_entries.find_one(
                {"tenant_id": account["tenant_id"], "idempotency_key": entry["idempotency_key"]},
                {"_id": 0},
            )
            if existing:
                return serialize_doc(existing)
        raise
    return serialize_doc(entry)


async def grant_credits(user: dict, tenant_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    require_platform_ai_admin(user)
    included = int(fields.get("included_credits") or 0)
    purchased = int(fields.get("purchased_credits") or 0)
    reason = _clean_text(fields.get("reason"), "reason", limit=500)
    if included < 0 or purchased < 0 or included + purchased <= 0:
        raise AIGatewayError("invalid_credit_grant", "Grant must add included or purchased credits", 400)
    existing_idempotency = fields.get("idempotency_key")
    if existing_idempotency:
        existing = await db.ai_credit_ledger_entries.find_one({"tenant_id": tenant_id, "idempotency_key": existing_idempotency}, {"_id": 0})
        if existing:
            return serialize_doc(existing)
    account = await _ensure_credit_account(tenant_id)
    updates = {
        "included_balance_credits": account["included_balance_credits"] + included,
        "purchased_balance_credits": account["purchased_balance_credits"] + purchased,
        "updated_at": _now_iso(),
    }
    await db.ai_credit_accounts.update_one({"tenant_id": tenant_id}, {"$set": updates})
    account = await _ensure_credit_account(tenant_id)
    entry = await _insert_credit_ledger(account, {
        "entry_type": "grant",
        "amount_credits": included + purchased,
        "included_credits_delta": included,
        "purchased_credits_delta": purchased,
        "idempotency_key": existing_idempotency,
        "source_type": fields.get("source_type") or "platform_manual_grant",
        "source_id": fields.get("source_id"),
        "reason": reason,
        "created_by_user_id": user["id"],
    })
    await _audit(user, "ai.credits_granted", "ai_credit_account", account["id"], "AI credits granted", {"tenant_id": tenant_id, "included": included, "purchased": purchased})
    return entry


async def adjust_credits(user: dict, tenant_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    require_platform_ai_admin(user)
    included_delta = int(fields.get("included_credits_delta") or 0)
    purchased_delta = int(fields.get("purchased_credits_delta") or 0)
    reason = _clean_text(fields.get("reason"), "reason", limit=500)
    account = await _ensure_credit_account(tenant_id)
    new_included = account["included_balance_credits"] + included_delta
    new_purchased = account["purchased_balance_credits"] + purchased_delta
    if new_included < 0 or new_purchased < 0:
        raise AIGatewayError("negative_credit_balance", "Credit adjustment cannot make balances negative", 409)
    existing_idempotency = fields.get("idempotency_key")
    if existing_idempotency:
        existing = await db.ai_credit_ledger_entries.find_one({"tenant_id": tenant_id, "idempotency_key": existing_idempotency}, {"_id": 0})
        if existing:
            return serialize_doc(existing)
    await db.ai_credit_accounts.update_one(
        {"tenant_id": tenant_id},
        {"$set": {"included_balance_credits": new_included, "purchased_balance_credits": new_purchased, "updated_at": _now_iso()}},
    )
    account = await _ensure_credit_account(tenant_id)
    entry = await _insert_credit_ledger(account, {
        "entry_type": "adjustment",
        "amount_credits": included_delta + purchased_delta,
        "included_credits_delta": included_delta,
        "purchased_credits_delta": purchased_delta,
        "idempotency_key": existing_idempotency,
        "source_type": fields.get("source_type") or "platform_manual_adjustment",
        "source_id": fields.get("source_id"),
        "reason": reason,
        "created_by_user_id": user["id"],
    })
    await _audit(user, "ai.credits_adjusted", "ai_credit_account", account["id"], "AI credits adjusted", {"tenant_id": tenant_id})
    return entry


async def _reserve_credits(tenant_id: str, action_request_id: str, amount: int, *, idempotency_key: Optional[str]) -> Optional[dict[str, Any]]:
    if amount <= 0:
        return None
    existing_key = f"{idempotency_key}:reserve" if idempotency_key else None
    if existing_key:
        existing = await db.ai_credit_ledger_entries.find_one({"tenant_id": tenant_id, "idempotency_key": existing_key}, {"_id": 0})
        if existing:
            return serialize_doc(existing)
    account = await _ensure_credit_account(tenant_id)
    available = account["included_balance_credits"] + account["purchased_balance_credits"] - account["reserved_credits"]
    if account["status"] != "active":
        raise AIGatewayError("credit_account_not_active", "AI credit account is not active", 402)
    if available < amount:
        await _open_alert(tenant_id, "zero_credit", f"AI request blocked: {amount} credits required", observed=available, threshold=amount, action_request_id=action_request_id)
        raise AIGatewayError("insufficient_ai_credits", "Insufficient AI credits", 402)
    await db.ai_credit_accounts.update_one(
        {"tenant_id": tenant_id},
        {"$inc": {"reserved_credits": amount}, "$set": {"updated_at": _now_iso()}},
    )
    account = await _ensure_credit_account(tenant_id)
    return await _insert_credit_ledger(account, {
        "entry_type": "reserve",
        "amount_credits": -amount,
        "reserved_credits_delta": amount,
        "action_request_id": action_request_id,
        "idempotency_key": existing_key,
        "source_type": "ai_action_request",
        "source_id": action_request_id,
    })


async def _commit_credits(tenant_id: str, action_request_id: str, amount: int, *, idempotency_key: Optional[str]) -> Optional[dict[str, Any]]:
    if amount <= 0:
        return None
    existing_key = f"{idempotency_key}:commit" if idempotency_key else None
    if existing_key:
        existing = await db.ai_credit_ledger_entries.find_one({"tenant_id": tenant_id, "idempotency_key": existing_key}, {"_id": 0})
        if existing:
            return serialize_doc(existing)
    account = await _ensure_credit_account(tenant_id)
    included_used = min(account["included_balance_credits"], amount)
    purchased_used = amount - included_used
    if account["purchased_balance_credits"] < purchased_used:
        raise AIGatewayError("insufficient_ai_credits", "Insufficient AI credits", 402)
    await db.ai_credit_accounts.update_one(
        {"tenant_id": tenant_id},
        {
            "$set": {
                "included_balance_credits": account["included_balance_credits"] - included_used,
                "purchased_balance_credits": account["purchased_balance_credits"] - purchased_used,
                "reserved_credits": max(0, account["reserved_credits"] - amount),
                "updated_at": _now_iso(),
            }
        },
    )
    account = await _ensure_credit_account(tenant_id)
    return await _insert_credit_ledger(account, {
        "entry_type": "commit",
        "amount_credits": -amount,
        "included_credits_delta": -included_used,
        "purchased_credits_delta": -purchased_used,
        "reserved_credits_delta": -amount,
        "action_request_id": action_request_id,
        "idempotency_key": existing_key,
        "source_type": "ai_action_request",
        "source_id": action_request_id,
    })


async def _release_credits(tenant_id: str, action_request_id: str, amount: int, *, idempotency_key: Optional[str], reason: str) -> Optional[dict[str, Any]]:
    if amount <= 0:
        return None
    existing_key = f"{idempotency_key}:release" if idempotency_key else None
    if existing_key:
        existing = await db.ai_credit_ledger_entries.find_one({"tenant_id": tenant_id, "idempotency_key": existing_key}, {"_id": 0})
        if existing:
            return serialize_doc(existing)
    account = await _ensure_credit_account(tenant_id)
    await db.ai_credit_accounts.update_one(
        {"tenant_id": tenant_id},
        {"$set": {"reserved_credits": max(0, account["reserved_credits"] - amount), "updated_at": _now_iso()}},
    )
    account = await _ensure_credit_account(tenant_id)
    return await _insert_credit_ledger(account, {
        "entry_type": "release",
        "amount_credits": amount,
        "reserved_credits_delta": -amount,
        "action_request_id": action_request_id,
        "idempotency_key": existing_key,
        "source_type": "ai_action_request",
        "source_id": action_request_id,
        "reason": reason,
    })


async def _open_alert(
    tenant_id: str,
    alert_type: str,
    summary: str,
    *,
    observed: Optional[int] = None,
    threshold: Optional[int] = None,
    capability_key: Optional[str] = None,
    action_request_id: Optional[str] = None,
) -> dict[str, Any]:
    existing = await db.ai_budget_alerts.find_one(
        {"tenant_id": tenant_id, "alert_type": alert_type, "status": "open", "capability_key": capability_key},
        {"_id": 0},
    )
    if existing:
        return serialize_doc(existing)
    alert = AIBudgetAlert(
        tenant_id=tenant_id,
        alert_type=alert_type,
        summary=summary,
        threshold_value=threshold,
        observed_value=observed,
        capability_key=capability_key,
        action_request_id=action_request_id,
    ).model_dump()
    await db.ai_budget_alerts.insert_one(prepare_for_mongo(alert))
    return serialize_doc(alert)


async def list_budget_alerts(user: dict, *, status: Optional[str] = None) -> dict[str, Any]:
    filt: dict[str, Any] = {}
    if not _is_platform_ai_admin(user):
        filt["tenant_id"] = user["tenant_id"]
    if status:
        filt["status"] = status
    items = [serialize_doc(d) async for d in db.ai_budget_alerts.find(filt, {"_id": 0}).sort("created_at", -1)]
    return {"items": items, "total": len(items)}


async def update_budget_alert(user: dict, alert_id: str, status: str) -> dict[str, Any]:
    if status not in {"acknowledged", "resolved"}:
        raise AIGatewayError("invalid_alert_status", "Alert status must be acknowledged or resolved", 400)
    filt: dict[str, Any] = {"id": alert_id}
    if not _is_platform_ai_admin(user):
        if not _has_staff_perm(user, "ai_credit:admin"):
            raise AIGatewayError("ai_credit_admin_required", "AI credit admin permission is required", 403)
        filt["tenant_id"] = user["tenant_id"]
    alert = await db.ai_budget_alerts.find_one(filt, {"_id": 0})
    if not alert:
        raise AIGatewayError("alert_not_found", "AI budget alert not found", 404)
    now = _now_iso()
    updates = {"status": status, "updated_at": now}
    if status == "acknowledged":
        updates.update({"acknowledged_by_user_id": user["id"], "acknowledged_at": now})
    else:
        updates.update({"resolved_by_user_id": user["id"], "resolved_at": now})
    await db.ai_budget_alerts.update_one({"id": alert_id}, {"$set": updates})
    await _audit(user, f"ai.budget_alert_{status}", "ai_budget_alert", alert_id, f"AI budget alert {status}")
    return serialize_doc(await db.ai_budget_alerts.find_one({"id": alert_id}, {"_id": 0}))


async def create_governance_policy(user: dict, fields: dict[str, Any]) -> dict[str, Any]:
    require_platform_ai_admin(user)
    doc = AIGovernancePolicy(
        scope_type=fields.get("scope_type", "global"),
        scope_key=fields.get("scope_key"),
        tenant_id=fields.get("tenant_id"),
        capability_key=fields.get("capability_key"),
        model_profile_id=fields.get("model_profile_id"),
        status=fields.get("status", "draft"),
        zero_credit_behavior=fields.get("zero_credit_behavior", "block"),
        disabled_capability_keys=fields.get("disabled_capability_keys") or [],
        max_requests_per_day=fields.get("max_requests_per_day"),
        max_credits_per_day=fields.get("max_credits_per_day"),
        max_cost_micros_per_day=fields.get("max_cost_micros_per_day"),
        low_credit_threshold_credits=fields.get("low_credit_threshold_credits"),
        effective_at=fields.get("effective_at"),
        retired_at=fields.get("retired_at"),
        created_by_user_id=user["id"],
    ).model_dump()
    await db.ai_governance_policies.insert_one(prepare_for_mongo(doc))
    await _audit(user, "ai.governance_policy_created", "ai_governance_policy", doc["id"], "AI governance policy created")
    return serialize_doc(doc)


async def list_governance_policies(user: dict) -> dict[str, Any]:
    require_platform_ai_admin(user)
    items = [serialize_doc(d) async for d in db.ai_governance_policies.find({}, {"_id": 0}).sort("created_at", -1)]
    return {"items": items, "total": len(items)}


async def _active_policies(tenant_id: str, capability_key: str, model_profile_id: Optional[str]) -> list[dict[str, Any]]:
    filters = [
        {"status": "active", "scope_type": "global"},
        {"status": "active", "scope_type": "tenant", "tenant_id": tenant_id},
        {"status": "active", "scope_type": "capability", "capability_key": capability_key},
    ]
    if model_profile_id:
        filters.append({"status": "active", "scope_type": "model", "model_profile_id": model_profile_id})
    policies: list[dict[str, Any]] = []
    for filt in filters:
        async for doc in db.ai_governance_policies.find(filt, {"_id": 0}):
            policies.append(doc)
    return policies


async def _enforce_governance(tenant_id: str, capability_key: str, model_profile_id: Optional[str], requested_credits: int, requested_cost_micros: int) -> None:
    day_start = _day_start_iso()
    for policy in await _active_policies(tenant_id, capability_key, model_profile_id):
        if capability_key in set(policy.get("disabled_capability_keys") or []):
            await _open_alert(tenant_id, "rate_limit", "AI capability disabled by governance policy", capability_key=capability_key)
            raise AIGatewayError("capability_disabled_by_policy", "AI capability is disabled by governance policy", 403)
        max_requests = policy.get("max_requests_per_day")
        if max_requests is not None:
            count = await db.ai_action_requests.count_documents({"tenant_id": tenant_id, "capability_key": capability_key, "created_at": {"$gte": day_start}})
            if count >= max_requests:
                await _open_alert(tenant_id, "rate_limit", "AI request blocked by daily request limit", observed=count, threshold=max_requests, capability_key=capability_key)
                raise AIGatewayError("ai_rate_limit_exceeded", "AI daily request limit exceeded", 429)
        max_credits = policy.get("max_credits_per_day")
        if max_credits is not None:
            used = 0
            async for row in db.ai_credit_ledger_entries.find(
                {"tenant_id": tenant_id, "entry_type": "commit", "created_at": {"$gte": day_start}},
                {"_id": 0, "amount_credits": 1},
            ):
                used += abs(int(row.get("amount_credits") or 0))
            if used + requested_credits > max_credits:
                await _open_alert(tenant_id, "spend_cap", "AI request blocked by daily credit limit", observed=used + requested_credits, threshold=max_credits, capability_key=capability_key)
                raise AIGatewayError("ai_credit_limit_exceeded", "AI daily credit limit exceeded", 429)
        max_cost = policy.get("max_cost_micros_per_day")
        if max_cost is not None:
            pipeline = [
                {"$match": {"tenant_id": tenant_id, "created_at": {"$gte": day_start}}},
                {"$group": {"_id": None, "cost": {"$sum": "$actual_cost_micros"}}},
            ]
            used_cost = 0
            async for row in db.ai_provider_cost_ledger_entries.aggregate(pipeline):
                used_cost = int(row.get("cost") or 0)
            if used_cost + requested_cost_micros > max_cost:
                await _open_alert(tenant_id, "spend_cap", "AI request blocked by provider cost cap", observed=used_cost + requested_cost_micros, threshold=max_cost, capability_key=capability_key)
                raise AIGatewayError("ai_cost_limit_exceeded", "AI provider cost limit exceeded", 429)


async def create_gateway_request(user: dict, fields: dict[str, Any]) -> dict[str, Any]:
    if not (_has_staff_perm(user, "ai_tool:use") or _has_staff_perm(user, "ai_assistant:use")):
        raise AIGatewayError("ai_use_permission_required", "AI tool or assistant permission is required", 403)
    idempotency_key = fields.get("idempotency_key")
    if idempotency_key:
        existing = await db.ai_action_requests.find_one({"tenant_id": user["tenant_id"], "idempotency_key": idempotency_key}, {"_id": 0})
        if existing:
            return serialize_doc(existing)
    capability_key = _clean_key(fields.get("capability_key"), "capability_key")
    capability = await db.ai_capabilities.find_one({"capability_key": capability_key}, {"_id": 0})
    if not capability or capability.get("status") != "active":
        raise AIGatewayError("capability_not_available", "AI capability is not available", 404)
    entitlement_key = capability.get("entitlement_feature_key")
    if entitlement_key and not await has_entitlement(tenant_id=user["tenant_id"], feature_key=entitlement_key):
        raise AIGatewayError("feature_not_entitled", f"Feature not entitled: {entitlement_key}", 402)
    model_profile = await _select_model_profile(capability, fields.get("model_profile_id"))
    credit_charge = int(fields.get("credit_charge_credits", capability.get("default_credit_charge", 0)) or 0)
    if not capability.get("billable"):
        credit_charge = 0
    estimated_cost_micros = int(fields.get("estimated_cost_micros") or _estimate_cost(model_profile, fields))
    await _enforce_governance(user["tenant_id"], capability_key, model_profile["id"], credit_charge, estimated_cost_micros)
    action = AIActionRequest(
        tenant_id=user["tenant_id"],
        user_id=user["id"],
        capability_key=capability_key,
        feature_key=capability["feature_key"],
        action_key=capability["action_key"],
        provider_key=model_profile["provider_key"],
        model_key=model_profile["model_key"],
        model_profile_id=model_profile["id"],
        prompt_version_id=fields.get("prompt_version_id"),
        context_packet_id=fields.get("context_packet_id"),
        idempotency_key=idempotency_key,
        session_id=fields.get("session_id"),
        background=bool(fields.get("background", False)),
        status="received",
        credit_charge_credits=credit_charge,
        source_links=fields.get("source_links") or [],
    ).model_dump()
    try:
        await db.ai_action_requests.insert_one(prepare_for_mongo(action))
    except DuplicateKeyError:
        if idempotency_key:
            return serialize_doc(await db.ai_action_requests.find_one({"tenant_id": user["tenant_id"], "idempotency_key": idempotency_key}, {"_id": 0}))
        raise
    try:
        reserve = await _reserve_credits(user["tenant_id"], action["id"], credit_charge, idempotency_key=idempotency_key)
    except AIGatewayError as exc:
        await db.ai_action_requests.update_one({"id": action["id"]}, {"$set": {"status": "blocked", "failure_reason": exc.code, "updated_at": _now_iso()}})
        raise
    if reserve:
        action["reserved_credit_ledger_entry_id"] = reserve["id"]
    await db.ai_action_requests.update_one({"id": action["id"]}, {"$set": {"status": "executing", "reserved_credit_ledger_entry_id": action.get("reserved_credit_ledger_entry_id"), "updated_at": _now_iso()}})
    simulate = fields.get("simulate_result", "success")
    if simulate == "provider_failure":
        usage = await _record_usage(user, action, model_profile, fields, result_status="failed", credits_charged=0)
        cost = await _record_provider_cost(action, model_profile, usage["id"], fields, actual_cost_micros=0)
        release = await _release_credits(user["tenant_id"], action["id"], credit_charge, idempotency_key=idempotency_key, reason="provider_failure")
        await db.ai_action_requests.update_one(
            {"id": action["id"]},
            {"$set": {"status": "failed", "result_status": "failed", "failure_reason": "provider_failure", "usage_ledger_entry_id": usage["id"], "provider_cost_ledger_entry_id": cost["id"], "updated_at": _now_iso()}},
        )
        await _audit(user, "ai.gateway_request_failed", "ai_action_request", action["id"], "AI gateway request failed without external provider call")
        result = await db.ai_action_requests.find_one({"id": action["id"]}, {"_id": 0})
        result["released_credit_ledger_entry_id"] = release["id"] if release else None
        return serialize_doc(result)
    usage = await _record_usage(user, action, model_profile, fields, result_status="succeeded", credits_charged=credit_charge)
    cost = await _record_provider_cost(action, model_profile, usage["id"], fields, actual_cost_micros=estimated_cost_micros)
    commit = await _commit_credits(user["tenant_id"], action["id"], credit_charge, idempotency_key=idempotency_key)
    await db.ai_action_requests.update_one(
        {"id": action["id"]},
        {"$set": {"status": "succeeded", "result_status": "succeeded", "result_summary": "local_contract_execution", "usage_ledger_entry_id": usage["id"], "provider_cost_ledger_entry_id": cost["id"], "committed_credit_ledger_entry_id": commit["id"] if commit else None, "duration_ms": int(fields.get("duration_ms") or 0), "updated_at": _now_iso()}},
    )
    await _maybe_low_credit_alert(user["tenant_id"], capability_key)
    await _audit(user, "ai.gateway_request_metered", "ai_action_request", action["id"], "AI gateway request metered without external provider call")
    return serialize_doc(await db.ai_action_requests.find_one({"id": action["id"]}, {"_id": 0}))


async def _select_model_profile(capability: dict[str, Any], requested_model_profile_id: Optional[str]) -> dict[str, Any]:
    allowed = capability.get("allowed_model_profile_ids") or []
    model_id = requested_model_profile_id or (allowed[0] if allowed else None)
    if not model_id or model_id not in allowed:
        raise AIGatewayError("model_not_allowed", "No allowed model profile is available for capability", 409)
    model = await db.ai_model_profiles.find_one({"id": model_id}, {"_id": 0})
    if not model or model.get("status") != "active":
        raise AIGatewayError("model_not_active", "AI model profile is not active", 409)
    provider = await db.ai_provider_configs.find_one({"id": model["provider_config_id"]}, {"_id": 0})
    if not provider or provider.get("status") != "active":
        raise AIGatewayError("provider_not_active", "AI provider is not active", 409)
    return model


def _estimate_cost(model_profile: dict[str, Any], fields: dict[str, Any]) -> int:
    input_units = int(fields.get("input_units") or 0)
    output_units = int(fields.get("output_units") or 0)
    return (
        input_units * int(model_profile.get("estimated_input_cost_micros_per_unit") or 0)
        + output_units * int(model_profile.get("estimated_output_cost_micros_per_unit") or 0)
    )


async def _record_usage(user: dict, action: dict[str, Any], model_profile: dict[str, Any], fields: dict[str, Any], *, result_status: str, credits_charged: int) -> dict[str, Any]:
    usage = AIUsageLedgerEntry(
        tenant_id=user["tenant_id"],
        user_id=user["id"],
        action_request_id=action["id"],
        capability_key=action["capability_key"],
        feature_key=action["feature_key"],
        action_key=action["action_key"],
        provider_key=model_profile["provider_key"],
        model_key=model_profile["model_key"],
        input_units=int(fields.get("input_units") or 0),
        output_units=int(fields.get("output_units") or 0),
        duration_ms=int(fields.get("duration_ms") or 0),
        credits_charged=credits_charged,
        result_status=result_status,
        session_id=fields.get("session_id"),
        background=bool(fields.get("background", False)),
        source_links=fields.get("source_links") or [],
        idempotency_key=f"{fields.get('idempotency_key')}:usage" if fields.get("idempotency_key") else None,
    ).model_dump()
    await db.ai_usage_ledger_entries.insert_one(prepare_for_mongo(usage))
    return serialize_doc(usage)


async def _record_provider_cost(action: dict[str, Any], model_profile: dict[str, Any], usage_id: str, fields: dict[str, Any], *, actual_cost_micros: int) -> dict[str, Any]:
    cost = AIProviderCostLedgerEntry(
        tenant_id=action["tenant_id"],
        action_request_id=action["id"],
        usage_ledger_entry_id=usage_id,
        provider_key=model_profile["provider_key"],
        model_key=model_profile["model_key"],
        estimated_cost_micros=int(fields.get("estimated_cost_micros") or _estimate_cost(model_profile, fields)),
        actual_cost_micros=actual_cost_micros,
        actual_cost_cents=fields.get("actual_cost_cents"),
        input_units=int(fields.get("input_units") or 0),
        output_units=int(fields.get("output_units") or 0),
        provider_event_id=fields.get("provider_event_id"),
        idempotency_key=f"{fields.get('idempotency_key')}:cost" if fields.get("idempotency_key") else None,
    ).model_dump()
    await db.ai_provider_cost_ledger_entries.insert_one(prepare_for_mongo(cost))
    return serialize_doc(cost)


async def _maybe_low_credit_alert(tenant_id: str, capability_key: str) -> None:
    account = await get_credit_account(tenant_id)
    threshold = int(account.get("low_credit_threshold_credits") or 0)
    for policy in await _active_policies(tenant_id, capability_key, None):
        if policy.get("low_credit_threshold_credits") is not None:
            threshold = max(threshold, int(policy["low_credit_threshold_credits"]))
    if threshold > 0 and account["available_credits"] <= threshold:
        await _open_alert(tenant_id, "low_credit", "AI credits are below configured threshold", observed=account["available_credits"], threshold=threshold, capability_key=capability_key)


async def list_action_history(user: dict, *, limit: int = 100) -> dict[str, Any]:
    if not _has_staff_perm(user, "ai_history:read"):
        raise AIGatewayError("ai_history_read_required", "AI history read permission is required", 403)
    items = [
        serialize_doc(d)
        async for d in db.ai_action_requests.find({"tenant_id": user["tenant_id"]}, {"_id": 0}).sort("created_at", -1).limit(limit)
    ]
    return {"items": items, "total": len(items)}


async def platform_dashboard(user: dict) -> dict[str, Any]:
    require_platform_ai_admin(user)
    tenants = await db.ai_credit_accounts.count_documents({})
    open_alerts = await db.ai_budget_alerts.count_documents({"status": "open"})
    actions = await db.ai_action_requests.count_documents({})
    usage = await db.ai_usage_ledger_entries.count_documents({})
    cost_pipeline = [{"$group": {"_id": None, "actual_cost_micros": {"$sum": "$actual_cost_micros"}}}]
    total_cost = 0
    async for row in db.ai_provider_cost_ledger_entries.aggregate(cost_pipeline):
        total_cost = int(row.get("actual_cost_micros") or 0)
    return {
        "tenant_credit_accounts": tenants,
        "open_alerts": open_alerts,
        "action_requests": actions,
        "usage_events": usage,
        "actual_provider_cost_micros": total_cost,
        "external_provider_calls": 0,
    }


async def record_provider_health(user: dict, fields: dict[str, Any]) -> dict[str, Any]:
    require_platform_ai_admin(user)
    doc = AIProviderHealthEvent(
        provider_key=_clean_key(fields.get("provider_key"), "provider_key"),
        model_key=fields.get("model_key"),
        status=fields.get("status"),
        reason=fields.get("reason"),
        metadata=fields.get("metadata") or {},
        created_by_user_id=user["id"],
    ).model_dump()
    await db.ai_provider_health_events.insert_one(prepare_for_mongo(doc))
    await _audit(user, "ai.provider_health_recorded", "ai_provider_health_event", doc["id"], "AI provider health recorded")
    return serialize_doc(doc)
