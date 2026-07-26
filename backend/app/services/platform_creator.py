"""Deliberate Platform Creator assignment and removal service.

Platform Creator is a platform-level role. It is never granted by ordinary
tenant user endpoints and must be changed through this explicit service or the
guarded bootstrap script that calls it.
"""
from __future__ import annotations

from datetime import datetime
import re
import uuid
from typing import Any, Optional

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.permissions import (
    PLATFORM_CREATOR_ROLE,
    PlatformPerm,
    has_platform_admin_access,
    is_platform_creator_user,
)
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.activity import ActivityEvent
from ..models.audit import AuditEvent


class PlatformCreatorError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


SYSTEM_BOOTSTRAP_ACTOR = {
    "id": "system:platform_creator_bootstrap",
    "email": "system@signguy.local",
}

SECRET_KEY_RE = re.compile(r"(token|secret|password|credential|authorization|cookie|api_key|private_key|hash)", re.IGNORECASE)
JWT_LIKE_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
BEARER_RE = re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE)
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
HASH_LIKE_RE = re.compile(r"(\$2[aby]\$\d{2}\$[A-Za-z0-9./]{20,}|argon2(id|i|d)?\$|pbkdf2[:$]|scrypt[:$]|sha(256|512)[:$])[A-Za-z0-9$./:+_-]{16,}", re.IGNORECASE)
CREDENTIAL_VALUE_RE = re.compile(r"\b(sk-[A-Za-z0-9_-]{12,}|[A-Za-z0-9_-]{24,}\.[A-Za-z0-9_-]{12,})\b")
EMAIL_RE = re.compile(r"^[^@\s\x00-\x1f\x7f]+@[^@\s\x00-\x1f\x7f]+$")
SAFE_CONTEXT_KEYS = {"source", "method", "request_id", "ticket_id", "approval_id", "test"}
PLATFORM_CREATOR_AUDIT_SCHEMA_VERSION = 1
PLATFORM_CREATOR_METADATA_FIELDS = (
    "platform_creator_assigned_at",
    "platform_creator_assigned_by",
    "platform_creator_assignment_reason",
    "platform_creator_granted_platform_admin",
    "platform_creator_granted_platform_admin_permission",
    "platform_creator_removed_at",
    "platform_creator_removed_by",
    "platform_creator_removal_reason",
    "platform_creator_pending_audit",
)
MAX_REASON_LENGTH = 500
MAX_CONTEXT_VALUE_LENGTH = 200


def normalize_email(email: str) -> str:
    value = str(email or "").strip().lower()
    if (
        not value
        or value.count("@") != 1
        or not EMAIL_RE.fullmatch(value)
        or any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in value)
    ):
        raise PlatformCreatorError("invalid_email", "A valid target email is required", 400)
    local, domain = value.split("@", 1)
    if not local or not domain or domain.startswith(".") or domain.endswith(".") or ".." in domain:
        raise PlatformCreatorError("invalid_email", "A valid target email is required", 400)
    return value


def _require_actor(actor_user: Optional[dict], allow_system_bootstrap: bool) -> dict:
    if allow_system_bootstrap:
        return SYSTEM_BOOTSTRAP_ACTOR
    if not has_platform_admin_access(actor_user):
        raise PlatformCreatorError("platform_admin_required", "Platform admin access is required", 403)
    return actor_user or {}


async def _find_active_user_by_normalized_email(email: str) -> dict:
    normalized = normalize_email(email)
    matches = await db.users.find(
        {
            "email": {"$regex": f"^{re.escape(normalized)}$", "$options": "i"},
            "is_active": {"$ne": False},
        },
        {"_id": 0},
    ).to_list(length=2)
    if not matches:
        raise PlatformCreatorError("target_user_not_found", "Target user was not found", 404)
    if len(matches) > 1:
        raise PlatformCreatorError("target_email_ambiguous", "Target email exists in more than one user record", 409)
    return matches[0]


def _expected_field_filter(doc: dict, key: str) -> Any:
    if key in doc:
        return {"$exists": True, "$eq": doc.get(key)}
    return {"$exists": False}


def _target_identity_filter(target: dict) -> dict[str, Any]:
    normalized = normalize_email(target["email"])
    return {
        "id": target["id"],
        "tenant_id": target["tenant_id"],
        "email": {"$regex": f"^{re.escape(normalized)}$", "$options": "i"},
        "is_active": _expected_field_filter(target, "is_active"),
        "platform_role": _expected_field_filter(target, "platform_role"),
        "platform_admin": _expected_field_filter(target, "platform_admin"),
        "permissions": _expected_field_filter(target, "permissions"),
        **{field: _expected_field_filter(target, field) for field in PLATFORM_CREATOR_METADATA_FIELDS},
    }


def _contains_secret_value(value: str) -> bool:
    return bool(
        JWT_LIKE_RE.search(value)
        or BEARER_RE.search(value)
        or PRIVATE_KEY_RE.search(value)
        or HASH_LIKE_RE.search(value)
        or CREDENTIAL_VALUE_RE.search(value)
    )


def _assert_no_secret_in_context(value: Any, path: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            if SECRET_KEY_RE.search(key_text):
                raise PlatformCreatorError("unsafe_audit_context", f"Audit context key '{path}.{key_text}' is not allowed", 400)
            _assert_no_secret_in_context(item, f"{path}.{key_text}")
        return
    if isinstance(value, (list, tuple, set)):
        for index, item in enumerate(value):
            _assert_no_secret_in_context(item, f"{path}[{index}]")
        return
    if value is not None and _contains_secret_value(str(value)):
        raise PlatformCreatorError("unsafe_audit_context", f"Audit context value at {path} cannot contain credentials or secrets", 400)


def _clean_audit_string(value: Any, field: str, *, max_length: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise PlatformCreatorError(f"{field}_required", f"{field} is required", 400)
    if SECRET_KEY_RE.search(field) or _contains_secret_value(text):
        raise PlatformCreatorError(f"{field}_unsafe", f"{field} cannot contain credentials or secrets", 400)
    return text[:max_length]


def _sanitize_context_value(value: Any, path: str) -> Any:
    _assert_no_secret_in_context(value, path)
    if isinstance(value, (dict, list, tuple, set)):
        raise PlatformCreatorError(
            "unsupported_audit_context",
            f"Audit context value at {path} must be a scalar approved value",
            400,
        )
    if value is None:
        return None
    if isinstance(value, str):
        return value[:MAX_CONTEXT_VALUE_LENGTH]
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    raise PlatformCreatorError(
        "unsupported_audit_context",
        f"Audit context value at {path} must be a scalar approved value",
        400,
    )


def _sanitize_context(context: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not context:
        return {}
    safe: dict[str, Any] = {}
    for key, value in dict(context).items():
        key_text = str(key)
        if SECRET_KEY_RE.search(key_text):
            raise PlatformCreatorError("unsafe_audit_context", f"Audit context key '{key_text}' is not allowed", 400)
        if key_text not in SAFE_CONTEXT_KEYS:
            continue
        safe[key_text[:64]] = _sanitize_context_value(value, key_text)
    return safe


def _sanitize_audit_inputs(reason: str, context: Optional[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    return _clean_audit_string(reason, "reason", max_length=MAX_REASON_LENGTH), _sanitize_context(context)


def _parse_pending_timestamp(value: Any, field: str) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise PlatformCreatorError("malformed_audit_outbox", f"Pending audit field {field} is malformed", 409)


def _logical_doc(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if doc is None:
        return None
    cleaned = dict(doc)
    cleaned.pop("_id", None)
    return serialize_doc(cleaned)


def _assert_logical_document_matches(*, existing: dict[str, Any] | None, expected: dict[str, Any], collection_name: str) -> None:
    expected_logical = _logical_doc(expected)
    existing_logical = _logical_doc(existing)
    if existing_logical != expected_logical:
        raise PlatformCreatorError(
            "audit_outbox_conflict",
            f"Existing {collection_name} record does not match the pending Platform Creator outbox",
            409,
        )


def _build_pending_audit(
    *,
    actor: dict,
    target: dict,
    action: str,
    summary: str,
    reason: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    event_timestamp = utc_now().isoformat()
    outcome = "assigned" if action.endswith(".assigned") else "removed"
    return {
        "schema_version": PLATFORM_CREATOR_AUDIT_SCHEMA_VERSION,
        "audit_event_id": str(uuid.uuid4()),
        "activity_event_id": str(uuid.uuid4()),
        "audit_created_at": event_timestamp,
        "audit_updated_at": event_timestamp,
        "activity_created_at": event_timestamp,
        "activity_updated_at": event_timestamp,
        "tenant_id": target["tenant_id"],
        "actor_user_id": actor["id"],
        "actor_email": actor["email"],
        "module": "platform_security",
        "action": action,
        "outcome": outcome,
        "entity_type": "user",
        "entity_id": target["id"],
        "summary": summary,
        "severity": "info",
        "diff": {
            "schema_version": PLATFORM_CREATOR_AUDIT_SCHEMA_VERSION,
            "outcome": outcome,
            "target_email": normalize_email(target["email"]),
            "target_tenant_id": target["tenant_id"],
            "reason": reason,
            "context": context,
        },
    }


async def _insert_pending_audit_documents(pending: dict[str, Any]) -> None:
    audit_evt = AuditEvent(
        id=pending["audit_event_id"],
        created_at=_parse_pending_timestamp(pending["audit_created_at"], "audit_created_at"),
        updated_at=_parse_pending_timestamp(pending["audit_updated_at"], "audit_updated_at"),
        tenant_id=pending["tenant_id"],
        actor_user_id=pending["actor_user_id"],
        actor_email=pending["actor_email"],
        action=pending["action"],
        entity_type=pending["entity_type"],
        entity_id=pending["entity_id"],
        summary=pending["summary"],
        diff=pending.get("diff"),
    )
    expected_audit = prepare_for_mongo(audit_evt.model_dump())
    try:
        await db.audit_events.insert_one(expected_audit)
    except DuplicateKeyError:
        existing = await db.audit_events.find_one({"id": pending["audit_event_id"]}, {"_id": 0})
        _assert_logical_document_matches(existing=existing, expected=expected_audit, collection_name="audit_events")

    activity = ActivityEvent(
        id=pending["activity_event_id"],
        created_at=_parse_pending_timestamp(pending["activity_created_at"], "activity_created_at"),
        updated_at=_parse_pending_timestamp(pending["activity_updated_at"], "activity_updated_at"),
        tenant_id=pending["tenant_id"],
        module=pending["module"],
        action=pending["action"],
        summary=pending["summary"],
        entity_type=pending["entity_type"],
        entity_id=pending["entity_id"],
        actor_user_id=pending["actor_user_id"],
        actor_email=pending["actor_email"],
        audit_event_id=pending["audit_event_id"],
        severity=pending.get("severity", "info"),
        metadata={
            "schema_version": pending["schema_version"],
            "outcome": pending["outcome"],
        },
    )
    expected_activity = prepare_for_mongo(activity.model_dump())
    try:
        await db.activity_events.insert_one(expected_activity)
    except DuplicateKeyError:
        existing = await db.activity_events.find_one({"id": pending["activity_event_id"]}, {"_id": 0})
        _assert_logical_document_matches(existing=existing, expected=expected_activity, collection_name="activity_events")


async def _deliver_pending_platform_creator_audit(target: dict) -> tuple[dict, bool]:
    pending = target.get("platform_creator_pending_audit")
    if not pending:
        return target, False

    await _insert_pending_audit_documents(pending)
    updated = await db.users.find_one_and_update(
        {
            "id": target["id"],
            "tenant_id": target["tenant_id"],
            "platform_creator_pending_audit": pending,
        },
        {"$unset": {"platform_creator_pending_audit": ""}},
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        reread = await db.users.find_one({"id": target["id"], "tenant_id": target["tenant_id"]}, {"_id": 0})
        if not reread:
            raise PlatformCreatorError("audit_outbox_clear_failed", "Platform Creator audit outbox delivery could not be finalized", 409)
        current_pending = reread.get("platform_creator_pending_audit")
        if current_pending is None:
            await _insert_pending_audit_documents(pending)
            return reread, True
        raise PlatformCreatorError("audit_outbox_clear_failed", "Platform Creator audit outbox changed before delivery could be finalized", 409)
    return updated, True


async def assign_platform_creator_by_email(
    *,
    actor_user: Optional[dict],
    email: str,
    reason: str,
    allow_system_bootstrap: bool = False,
    context: Optional[dict[str, Any]] = None,
) -> dict:
    safe_reason, safe_context = _sanitize_audit_inputs(reason, context)
    actor = _require_actor(actor_user, allow_system_bootstrap)
    target = await _find_active_user_by_normalized_email(email)
    target, recovered_audit = await _deliver_pending_platform_creator_audit(target)
    existing_perms = set(target.get("permissions") or [])
    required_perms = {PlatformPerm.PLATFORM_CREATOR.value, PlatformPerm.PLATFORM_ADMIN.value}
    already_complete = (
        is_platform_creator_user(target)
        and bool(target.get("platform_admin"))
        and required_perms.issubset(existing_perms)
    )
    if already_complete:
        return {"changed": False, "audit_recovered": recovered_audit, "user": serialize_doc(target)}

    pending_audit = _build_pending_audit(
        actor=actor,
        target=target,
        action="platform_creator.assigned",
        summary=f"Assigned Platform Creator to {normalize_email(target['email'])}",
        reason=safe_reason,
        context=safe_context,
    )
    updates = {
        "platform_role": PLATFORM_CREATOR_ROLE,
        "platform_admin": True,
        "permissions": sorted(existing_perms | required_perms),
        "platform_creator_assigned_at": utc_now().isoformat(),
        "platform_creator_assigned_by": actor["id"],
        "platform_creator_assignment_reason": safe_reason,
        "platform_creator_granted_platform_admin": not bool(target.get("platform_admin")),
        "platform_creator_granted_platform_admin_permission": PlatformPerm.PLATFORM_ADMIN.value not in existing_perms,
        "platform_creator_pending_audit": pending_audit,
    }
    updated = await db.users.find_one_and_update(
        _target_identity_filter(target),
        {"$set": updates},
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise PlatformCreatorError("target_changed", "Target user changed before Platform Creator assignment could be applied", 409)
    updated_perms = set(updated.get("permissions") or [])
    if not (
        updated.get("platform_role") == PLATFORM_CREATOR_ROLE
        and updated.get("platform_admin") is True
        and required_perms.issubset(updated_perms)
        and updated.get("platform_creator_pending_audit", {}).get("audit_event_id") == pending_audit["audit_event_id"]
    ):
        raise PlatformCreatorError("assignment_not_verified", "Platform Creator assignment could not be verified", 409)
    delivered, _ = await _deliver_pending_platform_creator_audit(updated)
    return {"changed": True, "audit_recovered": recovered_audit, "user": serialize_doc(delivered)}


async def remove_platform_creator_by_email(
    *,
    actor_user: Optional[dict],
    email: str,
    reason: str,
    allow_system_bootstrap: bool = False,
    context: Optional[dict[str, Any]] = None,
) -> dict:
    safe_reason, safe_context = _sanitize_audit_inputs(reason, context)
    actor = _require_actor(actor_user, allow_system_bootstrap)
    target = await _find_active_user_by_normalized_email(email)
    target, recovered_audit = await _deliver_pending_platform_creator_audit(target)
    if not is_platform_creator_user(target):
        return {"changed": False, "audit_recovered": recovered_audit, "user": serialize_doc(target)}

    existing_perms = set(target.get("permissions") or [])
    next_perms = set(existing_perms)
    next_perms.discard(PlatformPerm.PLATFORM_CREATOR.value)
    if target.get("platform_creator_granted_platform_admin_permission"):
        next_perms.discard(PlatformPerm.PLATFORM_ADMIN.value)

    pending_audit = _build_pending_audit(
        actor=actor,
        target=target,
        action="platform_creator.removed",
        summary=f"Removed Platform Creator from {normalize_email(target['email'])}",
        reason=safe_reason,
        context=safe_context,
    )
    set_updates: dict[str, Any] = {
        "permissions": sorted(next_perms),
        "platform_creator_removed_at": utc_now().isoformat(),
        "platform_creator_removed_by": actor["id"],
        "platform_creator_removal_reason": safe_reason,
        "platform_creator_pending_audit": pending_audit,
    }
    unset_updates = {
        "platform_creator_assigned_at": "",
        "platform_creator_assigned_by": "",
        "platform_creator_assignment_reason": "",
        "platform_creator_granted_platform_admin": "",
        "platform_creator_granted_platform_admin_permission": "",
    }
    if target.get("platform_role") == PLATFORM_CREATOR_ROLE:
        unset_updates["platform_role"] = ""
    if target.get("platform_creator_granted_platform_admin"):
        set_updates["platform_admin"] = False

    updated = await db.users.find_one_and_update(
        _target_identity_filter(target),
        {"$set": set_updates, "$unset": unset_updates},
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise PlatformCreatorError("target_changed", "Target user changed before Platform Creator removal could be applied", 409)
    if (
        is_platform_creator_user(updated)
        or updated.get("platform_creator_pending_audit", {}).get("audit_event_id") != pending_audit["audit_event_id"]
    ):
        raise PlatformCreatorError("removal_not_verified", "Platform Creator removal could not be verified", 409)
    delivered, _ = await _deliver_pending_platform_creator_audit(updated)
    return {"changed": True, "audit_recovered": recovered_audit, "user": serialize_doc(delivered)}
