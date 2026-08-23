"""Branding persistence, audit, activity, and response helpers."""
from __future__ import annotations

import hashlib
from typing import Any, Optional

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.permissions import Perm, permissions_for_role
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.webstore import WebstoreBrandingRecord
from .activity import record_activity_with_audit
from .entitlements import has_entitlement
from .webstore_branding_contracts import WEBSTORES_FEATURE_KEY, WebstoreBrandingError
from .webstore_branding_defaults import default_branding
from .webstore_branding_validation import _content_hash, normalize_branding, validation_for_branding

def _now_iso() -> str:
    return utc_now().isoformat()


def _require_staff_perm(user: dict, perm: Perm) -> None:
    if perm.value not in set(permissions_for_role(user.get("role", "staff"))):
        raise WebstoreBrandingError("permission_denied", f"Missing permission: {perm.value}", 403)


def _actor_from_user(user: dict) -> dict:
    return {"type": "staff", "id": user.get("id"), "email": user.get("email")}


def _actor_from_identity(identity: dict) -> dict:
    return {"type": "portal", "id": identity.get("id"), "email": identity.get("email")}


async def _get_store(tenant_id: str, webstore_id: str) -> dict:
    store = await db.webstores.find_one({"tenant_id": tenant_id, "id": webstore_id}, {"_id": 0})
    if not store:
        raise WebstoreBrandingError("webstore_not_found", "Webstore not found", 404)
    return serialize_doc(store)


async def _active_assignment(identity: dict, webstore_id: str) -> dict:
    if identity.get("portal_type") not in {"webstore_owner", "webstore_manager"}:
        raise WebstoreBrandingError("webstore_portal_required", "Webstore portal access required", 403)
    store = await _get_store(identity["tenant_id"], webstore_id)
    assignment = await db.webstore_access_assignments.find_one(
        {
            "tenant_id": identity["tenant_id"],
            "webstore_id": webstore_id,
            "portal_identity_id": identity.get("id"),
            "status": "active",
        },
        {"_id": 0},
    )
    if not assignment:
        raise WebstoreBrandingError("webstore_assignment_scope_forbidden", "Webstore Branding is limited to active assigned stores.", 403)
    role = assignment.get("role")
    if role == "manager" and identity.get("portal_type") != "webstore_manager":
        raise WebstoreBrandingError("webstore_assignment_scope_forbidden", "Webstore manager access is assignment-scoped.", 403)
    if role == "owner" and identity.get("portal_type") != "webstore_owner":
        raise WebstoreBrandingError("webstore_assignment_scope_forbidden", "Webstore owner access is assignment-scoped.", 403)
    return {"store": store, "assignment": serialize_doc(assignment), "role": role}


async def _audit(
    *,
    tenant_id: str,
    webstore_id: str,
    actor: dict,
    action: str,
    summary: str,
    entity_id: str,
    note: Optional[str] = None,
) -> None:
    now = _now_iso()
    activity = {
        "id": f"webstore-branding-activity-{hashlib.sha1(f'{tenant_id}:{webstore_id}:{action}:{entity_id}:{now}'.encode()).hexdigest()}",
        "tenant_id": tenant_id,
        "webstore_id": webstore_id,
        "actor_type": actor["type"],
        "actor_id": actor.get("id"),
        "actor_email": actor.get("email"),
        "action": action,
        "entity_type": "webstore_branding",
        "entity_id": entity_id,
        "summary": summary,
        "metadata": {"note": note} if note else {},
        "created_at": now,
        "updated_at": now,
    }
    await db.webstore_activity_events.insert_one(prepare_for_mongo(activity))
    await record_activity_with_audit(
        tenant_id=tenant_id,
        actor_user_id=actor.get("id") or actor["type"],
        actor_email=actor.get("email") or actor["type"],
        module="webstores",
        action=action,
        entity_type="webstore",
        entity_id=webstore_id,
        summary=summary,
        metadata={"webstore_id": webstore_id, "note": note} if note else {"webstore_id": webstore_id},
    )


async def _record_for_store(store: dict) -> dict:
    record = await db.webstore_branding_records.find_one({"tenant_id": store["tenant_id"], "webstore_id": store["id"]}, {"_id": 0})
    if record:
        return serialize_doc(record)
    draft = normalize_branding(store, store.get("branding") or {})
    record_doc = WebstoreBrandingRecord(
        tenant_id=store["tenant_id"],
        webstore_id=store["id"],
        draft=draft,
        draft_hash=_content_hash(draft),
    ).model_dump()
    try:
        await db.webstore_branding_records.insert_one(prepare_for_mongo(record_doc))
        return serialize_doc(record_doc)
    except DuplicateKeyError:
        existing = await db.webstore_branding_records.find_one({"tenant_id": store["tenant_id"], "webstore_id": store["id"]}, {"_id": 0})
        return serialize_doc(existing)


async def _history(tenant_id: str, webstore_id: str) -> list[dict]:
    return [
        serialize_doc(doc)
        async for doc in db.webstore_branding_versions.find(
            {"tenant_id": tenant_id, "webstore_id": webstore_id},
            {"_id": 0},
        ).sort([("version", -1)])
    ]


async def _activity(tenant_id: str, webstore_id: str) -> list[dict]:
    return [
        serialize_doc(doc)
        async for doc in db.webstore_activity_events.find(
            {
                "tenant_id": tenant_id,
                "webstore_id": webstore_id,
                "action": {
                    "$in": [
                        "webstore.branding_draft_saved",
                        "webstore.branding_review_requested",
                        "webstore.branding_changes_requested",
                        "webstore.branding_owner_approved",
                        "webstore.branding_published",
                    ]
                },
            },
            {"_id": 0},
        ).sort([("created_at", -1)])
    ]


def _response(store: dict, record: dict, *, role: str) -> dict:
    draft = record.get("draft") or default_branding(store)
    return {
        "webstore": {
            "id": store["id"],
            "name": store.get("name"),
            "store_type": store.get("store_type"),
            "status": store.get("status"),
            "setup_state": store.get("setup_state"),
            "public_slug": store.get("public_slug"),
            "public_url": store.get("public_url"),
        },
        "branding": {
            "id": record.get("id"),
            "status": record.get("status") or "draft",
            "draft": draft,
            "draft_hash": _content_hash(draft),
            "submitted_snapshot": record.get("submitted_snapshot"),
            "submitted_hash": record.get("submitted_hash"),
            "owner_decision": record.get("owner_decision") or {},
            "feedback_note": record.get("feedback_note"),
            "published_branding": record.get("published_branding"),
            "published_version_id": record.get("published_version_id"),
            "published_at": record.get("published_at"),
            "validation": validation_for_branding(store, draft),
        },
        "history": [],
        "activity": [],
        "role": role,
        "permissions": {
            "can_save_draft": role in {"staff", "owner", "manager"},
            "can_request_review": role in {"staff", "manager"},
            "can_owner_decide": role == "owner",
            "can_publish": role == "staff",
            "can_control_whole_sections": role == "staff",
        },
    }
