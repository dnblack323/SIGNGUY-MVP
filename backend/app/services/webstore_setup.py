"""Webstores Stage 2 - setup workflow, owner intake, and safe answer application."""
from __future__ import annotations

import mimetypes
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.permissions import Perm, permissions_for_role
from ..core.portal_security import create_portal_token, generate_raw_token, hash_token
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.portal_identity import WEBSTORE_MANAGER_PORTAL_PERMS, WEBSTORE_OWNER_PORTAL_PERMS
from ..models.webstore import (
    WEBSTORE_TYPES,
    WebstoreAccessAssignment,
    WebstoreAnswerApplication,
    WebstoreInvitation,
    WebstoreQuestionnaireSubmission,
    WebstoreQuestionnaireTemplate,
    WebstoreSetupFile,
)
from . import storage
from .activity import record_activity_with_audit
from .email import record_processed_activity, send_email

WEBSTORE_SETUP_STATES = (
    "not_started",
    "invitation_pending",
    "questionnaire_in_progress",
    "questionnaire_submitted",
    "staff_review",
    "changes_requested",
    "setup_in_progress",
    "blocked",
    "setup_complete",
)
ACTIVE_ASSIGNMENT_STATUSES = {"invited", "active"}
ACCEPTABLE_INVITATION_STATUSES = {"pending", "sent", "send_failed"}
MAX_SETUP_FILE_BYTES = 50 * 1024 * 1024
SAFE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "pdf", "svg", "ai", "eps", "csv", "xlsx", "docx"}
DOWNLOAD_ONLY_EXTENSIONS = {"ai", "eps", "csv", "xlsx", "docx"}
BLOCKED_EXTENSIONS = {
    "exe",
    "bat",
    "cmd",
    "com",
    "msi",
    "ps1",
    "sh",
    "js",
    "jar",
    "zip",
    "rar",
    "7z",
    "tar",
    "gz",
    "html",
    "htm",
}
LOCKED_ANSWER_FIELDS = {
    "production_cost_cents",
    "selling_price_cents",
    "store_owner_share_cents",
    "platform_fee_basis_points",
    "fees",
    "shipping_cents",
    "tax_cents",
    "stripe_payment_ready",
    "stripe_onboarding_required",
    "direct_owner_payout_required",
    "launch_ready",
    "launch_readiness",
}
SAFE_ANSWER_MAPPING = {
    "store_name": {"target": "name", "label": "Store name"},
    "description": {"target": "description", "label": "Description"},
    "target_launch_at": {"target": "target_launch_at", "label": "Target launch"},
    "deadline_at": {"target": "deadline_at", "label": "Order deadline"},
    "event_start_at": {"target": "event_start_at", "label": "Event date"},
    "event_location": {"target": "event_location", "label": "Event location"},
    "audience": {"target": "setup_profile.audience", "label": "Audience"},
    "goals": {"target": "setup_profile.goals", "label": "Goals"},
    "notes": {"target": "setup_profile.owner_notes", "label": "Owner notes"},
    "pickup_instructions": {"target": "setup_profile.pickup_instructions", "label": "Pickup instructions"},
}

DEFAULT_TEMPLATE_SECTIONS = {
    "base": [
        {
            "id": "store_basics",
            "title": "Store basics",
            "questions": [
                {"key": "store_name", "label": "Store name", "type": "text", "required": True},
                {"key": "description", "label": "Store description", "type": "textarea", "required": False},
                {"key": "target_launch_at", "label": "Target launch date", "type": "date", "required": False},
                {"key": "deadline_at", "label": "Order deadline", "type": "date", "required": False},
                {"key": "audience", "label": "Audience", "type": "textarea", "required": False},
                {"key": "goals", "label": "Goals", "type": "textarea", "required": False},
            ],
        }
    ],
    "b2b": [{"id": "b2b", "title": "B2B", "questions": [{"key": "pickup_instructions", "label": "Pickup or delivery instructions", "type": "textarea", "required": False}]}],
    "fundraiser": [{"id": "fundraiser", "title": "Fundraiser", "questions": [{"key": "goals", "label": "Fundraising goals", "type": "textarea", "required": False}]}],
    "event": [{"id": "event", "title": "Event", "questions": [{"key": "event_start_at", "label": "Event date", "type": "date", "required": False}, {"key": "event_location", "label": "Event location", "type": "text", "required": False}]}],
    "promotional": [{"id": "promotional", "title": "Promotion", "questions": [{"key": "goals", "label": "Promotion goal", "type": "textarea", "required": False}]}],
    "employee": [{"id": "employee", "title": "Employee store", "questions": [{"key": "audience", "label": "Employee audience", "type": "textarea", "required": False}]}],
    "general": [{"id": "general", "title": "General", "questions": [{"key": "notes", "label": "Anything else?", "type": "textarea", "required": False}]}],
}


class WebstoreSetupError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _now_iso() -> str:
    return utc_now().isoformat()


def _require_staff_perm(user: dict, perm: Perm) -> None:
    if perm.value not in set(permissions_for_role(user.get("role", "staff"))):
        raise WebstoreSetupError("permission_denied", f"Missing permission: {perm.value}", 403)


def _email(value: Any) -> str:
    email = str(value or "").strip().lower()
    if not email or "@" not in email:
        raise WebstoreSetupError("email_required", "A valid email is required", 400)
    return email


def _clean_text(value: Any, field: str, *, limit: int = 200) -> str:
    text = str(value or "").strip()
    if not text:
        raise WebstoreSetupError(f"{field}_required", f"{field} is required", 400)
    if len(text) > limit:
        raise WebstoreSetupError(f"{field}_too_long", f"{field} must be {limit} characters or fewer", 400)
    return text


def _portal_type_for_role(role: str) -> str:
    if role == "manager":
        return "webstore_manager"
    return "webstore_owner"


def _portal_perms_for_role(role: str) -> list[str]:
    return list(WEBSTORE_MANAGER_PORTAL_PERMS if role == "manager" else WEBSTORE_OWNER_PORTAL_PERMS)


def _token_response(invitation: dict, raw_token: str) -> dict:
    response = serialize_doc(invitation)
    response.pop("token_hash", None)
    response["invitation_url"] = f"/portal/webstores/invitations/accept?t={raw_token}"
    return response


async def _audit(
    *,
    tenant_id: str,
    webstore_id: str,
    actor_type: str,
    action: str,
    entity_type: str,
    entity_id: str,
    summary: str,
    actor_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    await db.webstore_activity_events.insert_one(
        prepare_for_mongo(
            {
                "id": secrets.token_hex(16),
                "created_at": utc_now(),
                "updated_at": utc_now(),
                "tenant_id": tenant_id,
                "webstore_id": webstore_id,
                "actor_type": actor_type,
                "actor_id": actor_id,
                "actor_email": actor_email,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "summary": summary,
                "metadata": metadata or {},
            }
        )
    )
    await record_activity_with_audit(
        tenant_id=tenant_id,
        actor_user_id=actor_id or actor_type,
        actor_email=actor_email or actor_type,
        module="webstores",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        metadata={"webstore_id": webstore_id, **(metadata or {})},
    )


async def _get_store(tenant_id: str, webstore_id: str) -> dict:
    store = await db.webstores.find_one({"tenant_id": tenant_id, "id": webstore_id}, {"_id": 0})
    if not store:
        raise WebstoreSetupError("webstore_not_found", "Webstore not found", 404)
    return serialize_doc(store)


async def _get_owner(tenant_id: str, owner_id: str) -> dict:
    owner = await db.webstore_owners.find_one({"tenant_id": tenant_id, "id": owner_id}, {"_id": 0})
    if not owner:
        raise WebstoreSetupError("webstore_owner_not_found", "Webstore owner not found", 404)
    return serialize_doc(owner)


async def _current_assignment(tenant_id: str, webstore_id: str, email: str, role: str) -> Optional[dict]:
    doc = await db.webstore_access_assignments.find_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "email": email, "role": role, "status": {"$in": list(ACTIVE_ASSIGNMENT_STATUSES)}},
        {"_id": 0},
    )
    return serialize_doc(doc) if doc else None


async def _link_or_create_identity(*, tenant_id: str, owner_id: str, webstore_id: str, role: str, email: str, name: Optional[str]) -> dict:
    portal_type = _portal_type_for_role(role)
    existing = await db.portal_identities.find_one({"tenant_id": tenant_id, "email": email}, {"_id": 0})
    updates = {
        "portal_type": portal_type,
        "webstore_owner_id": owner_id,
        "webstore_id": webstore_id if role == "manager" else None,
        "full_name": name or email,
        "role_label": "Store Manager" if role == "manager" else "Store Owner",
        "permissions_preset": "webstore_manager_ops" if role == "manager" else "webstore_owner_admin",
        "permissions": _portal_perms_for_role(role),
        "magic_link_only": True,
        "status": "active",
        "updated_at": _now_iso(),
    }
    if existing:
        if existing.get("portal_type") != portal_type:
            raise WebstoreSetupError(
                "portal_identity_role_conflict",
                "An existing portal identity for this email uses a different portal role.",
                409,
            )
        await db.portal_identities.update_one({"tenant_id": tenant_id, "id": existing["id"]}, {"$set": updates})
        linked = await db.portal_identities.find_one({"tenant_id": tenant_id, "id": existing["id"]}, {"_id": 0})
        return serialize_doc(linked or existing)
    doc = {
        "id": secrets.token_hex(16),
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "tenant_id": tenant_id,
        "portal_type": portal_type,
        "customer_id": None,
        "employee_id": None,
        "webstore_owner_id": owner_id,
        "webstore_id": webstore_id if role == "manager" else None,
        "email": email,
        "full_name": name or email,
        "phone": None,
        "role_label": updates["role_label"],
        "permissions_preset": updates["permissions_preset"],
        "permissions": updates["permissions"],
        "magic_link_only": True,
        "password_hash": None,
        "status": "active",
        "failed_login_count": 0,
        "locked_until": None,
    }
    await db.portal_identities.insert_one(prepare_for_mongo(doc))
    return serialize_doc(doc)


async def _create_invitation(
    *,
    tenant_id: str,
    webstore_id: str,
    assignment_id: str,
    role: str,
    email: str,
    name: Optional[str],
    user: dict,
    send: bool = True,
) -> dict:
    raw_token = generate_raw_token()
    invitation_url = f"/portal/webstores/invitations/accept?t={raw_token}"
    invitation = WebstoreInvitation(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        assignment_id=assignment_id,
        role=role,  # type: ignore[arg-type]
        email=email,
        name=name,
        token_hash=hash_token(raw_token),
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=48)).isoformat(),
        created_by_user_id=user.get("id"),
    ).model_dump()
    if send:
        ok, msg_id, error = send_email(
            to_email=email,
            subject="You're invited to a SignGuy Webstore setup workspace",
            body_text=(
                f"You have been invited as a Webstore {role}. "
                f"Use this 48-hour link to continue setup: {invitation_url}"
            ),
        )
        invitation["status"] = "sent" if ok else "send_failed"
        invitation["sent_at"] = _now_iso() if ok else None
        invitation["delivery_message_id"] = msg_id
        invitation["delivery_error"] = error
        await record_processed_activity(
            tenant_id=tenant_id,
            email_log_id=invitation["id"],
            to_email=email,
            sendgrid_message_id=msg_id,
            related_entity_type="webstore_invitation",
            related_entity_id=invitation["id"],
            ok=ok,
            error=error,
        )
    await db.webstore_invitations.insert_one(prepare_for_mongo(invitation))
    await _audit(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.invitation_created",
        entity_type="webstore_invitation",
        entity_id=invitation["id"],
        summary=f"Webstore {role} invitation created",
        metadata={"role": role, "status": invitation["status"], "delivery_error": invitation.get("delivery_error")},
    )
    return _token_response(invitation, raw_token)


async def create_assignment(
    user: dict,
    webstore_id: str,
    fields: dict[str, Any],
    *,
    primary: bool = False,
    send: bool = True,
) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    store = await _get_store(user["tenant_id"], webstore_id)
    role = fields.get("role", "owner")
    if role not in {"owner", "manager"}:
        raise WebstoreSetupError("invalid_assignment_role", "Assignment role must be owner or manager", 400)
    email = _email(fields.get("email"))
    if await _current_assignment(user["tenant_id"], webstore_id, email, role):
        raise WebstoreSetupError("duplicate_active_assignment", "That Webstore assignment is already active or invited", 409)
    owner_id = fields.get("owner_id") or store["owner_id"]
    await _get_owner(user["tenant_id"], owner_id)
    existing_identity = await db.portal_identities.find_one({"tenant_id": user["tenant_id"], "email": email, "status": "active"}, {"_id": 0})
    if existing_identity and existing_identity.get("portal_type") not in {_portal_type_for_role(role)}:
        raise WebstoreSetupError(
            "portal_identity_role_conflict",
            "An existing portal identity for this email uses a different portal role.",
            409,
        )
    status = "active" if existing_identity and existing_identity.get("portal_type") == _portal_type_for_role(role) else "invited"
    assignment = WebstoreAccessAssignment(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        owner_id=owner_id,
        role=role,  # type: ignore[arg-type]
        email=email,
        name=fields.get("name") or fields.get("full_name"),
        portal_identity_id=(existing_identity or {}).get("id"),
        is_primary_owner=bool(primary or fields.get("is_primary_owner")),
        status=status,  # type: ignore[arg-type]
        invited_at=_now_iso(),
        accepted_at=_now_iso() if status == "active" else None,
    ).model_dump()
    if assignment["is_primary_owner"]:
        await db.webstore_access_assignments.update_many(
            {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "role": "owner", "is_primary_owner": True},
            {"$set": {"is_primary_owner": False, "updated_at": _now_iso()}},
        )
    await db.webstore_access_assignments.insert_one(prepare_for_mongo(assignment))
    invitation = None
    if status == "invited":
        invitation = await _create_invitation(
            tenant_id=user["tenant_id"],
            webstore_id=webstore_id,
            assignment_id=assignment["id"],
            role=role,
            email=email,
            name=assignment.get("name"),
            user=user,
            send=send,
        )
        assignment["invitation_id"] = invitation["id"]
        await db.webstore_access_assignments.update_one(
            {"tenant_id": user["tenant_id"], "id": assignment["id"]},
            {"$set": {"invitation_id": invitation["id"], "updated_at": _now_iso()}},
        )
    await _refresh_setup_state(user["tenant_id"], webstore_id)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.assignment_created",
        entity_type="webstore_access_assignment",
        entity_id=assignment["id"],
        summary=f"Webstore {role} assignment created",
        metadata={"role": role, "status": status, "primary": assignment["is_primary_owner"]},
    )
    return {"assignment": serialize_doc(assignment), "invitation": invitation}


async def initialize_store_setup(user: dict, store: dict, owner: dict, fields: dict[str, Any]) -> None:
    await db.webstores.update_one(
        {"tenant_id": store["tenant_id"], "id": store["id"]},
        {
            "$set": {
                "setup_state": "not_started",
                "setup_profile": fields.get("setup_profile") or {},
                "setup_requirements": fields.get("setup_requirements") or {},
                "target_launch_at": fields.get("target_launch_at"),
                "event_start_at": fields.get("event_start_at"),
                "event_location": fields.get("event_location"),
                "creation_idempotency_key": fields.get("idempotency_key"),
                "updated_at": _now_iso(),
            }
        },
    )
    primary = await create_assignment(
        user,
        store["id"],
        {"role": "owner", "owner_id": owner["id"], "email": owner["email"], "name": owner.get("name"), "is_primary_owner": True},
        primary=True,
        send=bool(fields.get("send_owner_invitation", True)),
    )
    await db.webstores.update_one(
        {"tenant_id": store["tenant_id"], "id": store["id"]},
        {"$set": {"primary_owner_assignment_id": primary["assignment"]["id"], "updated_at": _now_iso()}},
    )
    for raw in fields.get("additional_owner_emails") or []:
        await create_assignment(user, store["id"], {"role": "owner", "email": raw, "name": raw}, send=True)
    for raw in fields.get("manager_emails") or []:
        await create_assignment(user, store["id"], {"role": "manager", "email": raw, "name": raw}, send=True)
    await bind_questionnaire_templates(user, store["id"])
    await _refresh_setup_state(store["tenant_id"], store["id"])


async def list_assignments(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    await _get_store(user["tenant_id"], webstore_id)
    items = [serialize_doc(d) async for d in db.webstore_access_assignments.find({"tenant_id": user["tenant_id"], "webstore_id": webstore_id}, {"_id": 0}).sort([("created_at", 1)])]
    return {"items": items}


async def resend_invitation(user: dict, webstore_id: str, assignment_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    assignment = await db.webstore_access_assignments.find_one({"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": assignment_id}, {"_id": 0})
    if not assignment or assignment.get("status") not in {"invited", "expired"}:
        raise WebstoreSetupError("assignment_not_invitable", "Only invited or expired assignments can be resent", 409)
    await db.webstore_invitations.update_many(
        {"tenant_id": user["tenant_id"], "assignment_id": assignment_id, "status": {"$in": list(ACCEPTABLE_INVITATION_STATUSES)}},
        {"$set": {"status": "superseded", "superseded_at": _now_iso(), "updated_at": _now_iso()}},
    )
    invite = await _create_invitation(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        assignment_id=assignment_id,
        role=assignment["role"],
        email=assignment["email"],
        name=assignment.get("name"),
        user=user,
        send=True,
    )
    await db.webstore_access_assignments.update_one(
        {"tenant_id": user["tenant_id"], "id": assignment_id},
        {"$set": {"status": "invited", "invitation_id": invite["id"], "invited_at": _now_iso(), "updated_at": _now_iso()}},
    )
    await _refresh_setup_state(user["tenant_id"], webstore_id)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.invitation_resent",
        entity_type="webstore_access_assignment",
        entity_id=assignment_id,
        summary="Webstore invitation resent and prior pending invitation superseded",
        metadata={"new_invitation_id": invite["id"]},
    )
    return {"invitation": invite}


async def revoke_assignment(user: dict, webstore_id: str, assignment_id: str, reason: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    assignment = await db.webstore_access_assignments.find_one({"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": assignment_id}, {"_id": 0})
    if not assignment:
        raise WebstoreSetupError("assignment_not_found", "Assignment not found", 404)
    if assignment.get("is_primary_owner"):
        raise WebstoreSetupError("primary_owner_revoke_blocked", "Change the primary owner before revoking this assignment", 409)
    await db.webstore_access_assignments.update_one(
        {"tenant_id": user["tenant_id"], "id": assignment_id},
        {"$set": {"status": "revoked", "revoked_at": _now_iso(), "updated_at": _now_iso()}},
    )
    await db.webstore_invitations.update_many(
        {"tenant_id": user["tenant_id"], "assignment_id": assignment_id, "status": {"$in": list(ACCEPTABLE_INVITATION_STATUSES)}},
        {"$set": {"status": "revoked", "revoked_at": _now_iso(), "updated_at": _now_iso()}},
    )
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.assignment_revoked",
        entity_type="webstore_access_assignment",
        entity_id=assignment_id,
        summary="Webstore assignment revoked",
        metadata={"reason": reason},
    )
    await _refresh_setup_state(user["tenant_id"], webstore_id)
    return {"assignment_id": assignment_id, "status": "revoked"}


async def change_primary_owner(user: dict, webstore_id: str, assignment_id: str, confirm: bool, reason: Optional[str]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    if not confirm or not reason:
        raise WebstoreSetupError("primary_owner_confirmation_required", "A confirmation and reason are required to change primary owner", 400)
    assignment = await db.webstore_access_assignments.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": assignment_id, "role": "owner", "status": "active"},
        {"_id": 0},
    )
    if not assignment:
        raise WebstoreSetupError("active_owner_assignment_required", "Primary owner must be an active owner assignment", 409)
    await db.webstore_access_assignments.update_many(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "role": "owner", "is_primary_owner": True},
        {"$set": {"is_primary_owner": False, "updated_at": _now_iso()}},
    )
    await db.webstore_access_assignments.update_one(
        {"tenant_id": user["tenant_id"], "id": assignment_id},
        {"$set": {"is_primary_owner": True, "updated_at": _now_iso()}},
    )
    await db.webstores.update_one(
        {"tenant_id": user["tenant_id"], "id": webstore_id},
        {"$set": {"owner_id": assignment["owner_id"], "primary_owner_assignment_id": assignment_id, "updated_at": _now_iso()}},
    )
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.primary_owner_changed",
        entity_type="webstore_access_assignment",
        entity_id=assignment_id,
        summary="Primary Webstore owner changed",
        metadata={"reason": reason},
    )
    return {"assignment_id": assignment_id, "primary": True}


async def accept_invitation(raw_token: str) -> dict:
    if not raw_token:
        raise WebstoreSetupError("invitation_token_required", "Invitation token is required", 400)
    token_hash = hash_token(raw_token)
    invitation = await db.webstore_invitations.find_one({"token_hash": token_hash}, {"_id": 0})
    if not invitation:
        raise WebstoreSetupError("invitation_not_found", "Invitation is invalid or expired", 404)
    if invitation.get("status") not in ACCEPTABLE_INVITATION_STATUSES:
        raise WebstoreSetupError("invitation_not_available", "Invitation has already been used or revoked", 410)
    expires_at = invitation.get("expires_at")
    expires_dt = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
    if expires_dt <= datetime.now(timezone.utc):
        await db.webstore_invitations.update_one({"id": invitation["id"]}, {"$set": {"status": "expired", "updated_at": _now_iso()}})
        await db.webstore_access_assignments.update_one(
            {"tenant_id": invitation["tenant_id"], "id": invitation["assignment_id"]},
            {"$set": {"status": "expired", "expired_at": _now_iso(), "updated_at": _now_iso()}},
        )
        raise WebstoreSetupError("invitation_expired", "Invitation has expired", 410)
    assignment = await db.webstore_access_assignments.find_one(
        {"tenant_id": invitation["tenant_id"], "id": invitation["assignment_id"], "webstore_id": invitation["webstore_id"]},
        {"_id": 0},
    )
    if not assignment or assignment.get("status") not in {"invited", "expired"}:
        raise WebstoreSetupError("assignment_not_available", "Invitation assignment is not available", 410)
    identity = await _link_or_create_identity(
        tenant_id=invitation["tenant_id"],
        owner_id=assignment["owner_id"],
        webstore_id=invitation["webstore_id"],
        role=assignment["role"],
        email=invitation["email"],
        name=invitation.get("name") or assignment.get("name"),
    )
    now = _now_iso()
    result = await db.webstore_invitations.update_one(
        {"id": invitation["id"], "status": {"$in": list(ACCEPTABLE_INVITATION_STATUSES)}},
        {"$set": {"status": "accepted", "accepted_at": now, "updated_at": now}},
    )
    if result.modified_count != 1:
        raise WebstoreSetupError("invitation_replayed", "Invitation has already been used", 410)
    await db.webstore_access_assignments.update_one(
        {"tenant_id": invitation["tenant_id"], "id": assignment["id"]},
        {"$set": {"status": "active", "accepted_at": now, "portal_identity_id": identity["id"], "updated_at": now}},
    )
    await _audit(
        tenant_id=invitation["tenant_id"],
        webstore_id=invitation["webstore_id"],
        actor_type="portal",
        actor_id=identity["id"],
        actor_email=identity.get("email"),
        action="webstore.invitation_accepted",
        entity_type="webstore_invitation",
        entity_id=invitation["id"],
        summary="Webstore invitation accepted",
        metadata={"role": assignment["role"]},
    )
    if assignment.get("is_primary_owner"):
        await db.webstores.update_one(
            {"tenant_id": invitation["tenant_id"], "id": invitation["webstore_id"]},
            {"$set": {"owner_id": assignment["owner_id"], "primary_owner_assignment_id": assignment["id"], "updated_at": now}},
        )
    await _refresh_setup_state(invitation["tenant_id"], invitation["webstore_id"])
    token = create_portal_token(
        portal_identity_id=identity["id"],
        tenant_id=identity["tenant_id"],
        customer_id=identity.get("customer_id"),
        portal_type=identity.get("portal_type"),
        employee_id=identity.get("employee_id"),
    )
    return {"token": token, "identity": serialize_doc(identity), "webstore_id": invitation["webstore_id"]}


async def ensure_default_questionnaire_templates(tenant_id: str) -> None:
    for store_type in ("base", *WEBSTORE_TYPES):
        exists = await db.webstore_questionnaire_templates.find_one(
            {"tenant_id": tenant_id, "scope": "tenant_default", "store_type": store_type, "version": 1},
            {"_id": 0, "id": 1},
        )
        if exists:
            continue
        doc = WebstoreQuestionnaireTemplate(
            tenant_id=tenant_id,
            scope="tenant_default",
            store_type=store_type,
            version=1,
            title="Base Webstore Intake" if store_type == "base" else f"{store_type.replace('_', ' ').title()} Webstore Intake",
            sections=DEFAULT_TEMPLATE_SECTIONS[store_type],
            status="active",
        ).model_dump()
        await db.webstore_questionnaire_templates.insert_one(prepare_for_mongo(doc))


async def list_questionnaire_templates(user: dict, *, store_type: Optional[str] = None, active_only: bool = False) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    await ensure_default_questionnaire_templates(user["tenant_id"])
    filters: dict[str, Any] = {}
    if store_type:
        filters["store_type"] = store_type
    if active_only:
        filters["status"] = "active"
    items = [serialize_doc(d) async for d in db.webstore_questionnaire_templates.find({"tenant_id": user["tenant_id"], **filters}, {"_id": 0}).sort([("store_type", 1), ("version", -1)])]
    return {"items": items}


async def save_questionnaire_template(user: dict, fields: dict[str, Any], template_id: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    store_type = fields.get("store_type", "general")
    if store_type not in {"base", *WEBSTORE_TYPES}:
        raise WebstoreSetupError("invalid_template_store_type", "Unsupported questionnaire store type", 400)
    if template_id:
        existing = await db.webstore_questionnaire_templates.find_one({"tenant_id": user["tenant_id"], "id": template_id}, {"_id": 0})
        if not existing:
            raise WebstoreSetupError("questionnaire_template_not_found", "Questionnaire template not found", 404)
        updates = {k: v for k, v in fields.items() if k in {"title", "sections", "status"}}
        updates["updated_at"] = _now_iso()
        await db.webstore_questionnaire_templates.update_one({"tenant_id": user["tenant_id"], "id": template_id}, {"$set": updates})
        updated = await db.webstore_questionnaire_templates.find_one({"tenant_id": user["tenant_id"], "id": template_id}, {"_id": 0})
        return serialize_doc(updated or {})
    doc = WebstoreQuestionnaireTemplate(
        tenant_id=user["tenant_id"],
        scope="tenant",
        store_type=store_type,
        version=int(fields.get("version") or 1),
        title=_clean_text(fields.get("title"), "title"),
        sections=fields.get("sections") or [],
        status=fields.get("status", "active"),
    ).model_dump()
    await db.webstore_questionnaire_templates.insert_one(prepare_for_mongo(doc))
    return serialize_doc(doc)


async def bind_questionnaire_templates(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    await ensure_default_questionnaire_templates(user["tenant_id"])
    template_types = ["base", store.get("store_type") or "general"]
    templates = [
        serialize_doc(d)
        async for d in db.webstore_questionnaire_templates.find(
            {"tenant_id": user["tenant_id"], "store_type": {"$in": template_types}, "status": "active"},
            {"_id": 0},
        ).sort([("store_type", 1), ("version", -1)])
    ]
    await db.webstores.update_one(
        {"tenant_id": user["tenant_id"], "id": webstore_id},
        {"$set": {"setup_requirements.questionnaire_template_ids": [t["id"] for t in templates], "updated_at": _now_iso()}},
    )
    return {"webstore_id": webstore_id, "templates": templates}


async def owner_questionnaire(identity: dict, webstore_id: str) -> dict:
    store = await _owner_store(identity, webstore_id)
    templates = await _bound_templates(store)
    submission = await db.webstore_questionnaire_submissions.find_one(
        {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id, "portal_identity_id": identity["id"], "status": {"$in": ["draft", "returned_for_changes"]}},
        {"_id": 0},
    )
    return {"webstore": _owner_safe_store(store), "templates": templates, "submission": serialize_doc(submission) if submission else None}


async def _bound_templates(store: dict) -> list[dict]:
    tenant_id = store["tenant_id"]
    ids = ((store.get("setup_requirements") or {}).get("questionnaire_template_ids") or [])
    if ids:
        return [serialize_doc(d) async for d in db.webstore_questionnaire_templates.find({"tenant_id": tenant_id, "id": {"$in": ids}, "status": "active"}, {"_id": 0})]
    await ensure_default_questionnaire_templates(tenant_id)
    return [
        serialize_doc(d)
        async for d in db.webstore_questionnaire_templates.find(
            {"tenant_id": tenant_id, "store_type": {"$in": ["base", store.get("store_type") or "general"]}, "status": "active"},
            {"_id": 0},
        )
    ]


async def save_questionnaire_draft(identity: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    store = await _owner_store(identity, webstore_id)
    owner_id = identity.get("webstore_owner_id") or store["owner_id"]
    templates = await _bound_templates(store)
    payload = {
        "answers": fields.get("answers") or {},
        "known_products": fields.get("known_products") or [],
        "open_to_suggestions": bool(fields.get("open_to_suggestions", True)),
        "missing_info_flags": fields.get("missing_info_flags") or [],
        "status": "draft",
        "portal_identity_id": identity["id"],
        "template_ids": [t["id"] for t in templates],
        "template_version_ids": [f"{t['id']}:v{t.get('version', 1)}" for t in templates],
        "template_snapshot": {"templates": templates},
        "updated_at": _now_iso(),
    }
    existing = await db.webstore_questionnaire_submissions.find_one(
        {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id, "portal_identity_id": identity["id"], "status": "draft"},
        {"_id": 0},
    )
    if existing:
        await db.webstore_questionnaire_submissions.update_one({"tenant_id": identity["tenant_id"], "id": existing["id"]}, {"$set": payload})
        doc = await db.webstore_questionnaire_submissions.find_one({"tenant_id": identity["tenant_id"], "id": existing["id"]}, {"_id": 0})
    else:
        doc = WebstoreQuestionnaireSubmission(
            tenant_id=identity["tenant_id"],
            webstore_id=webstore_id,
            owner_id=owner_id,
            **payload,
        ).model_dump()
        await db.webstore_questionnaire_submissions.insert_one(prepare_for_mongo(doc))
    await _refresh_setup_state(identity["tenant_id"], webstore_id)
    return serialize_doc(doc or {})


async def submit_questionnaire(identity: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    existing_submitted = await db.webstore_questionnaire_submissions.find_one(
        {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id, "portal_identity_id": identity["id"], "status": {"$in": ["submitted", "reviewed"]}},
        {"_id": 0},
        sort=[("submitted_at", -1), ("updated_at", -1)],
    )
    if existing_submitted:
        return serialize_doc(existing_submitted)
    draft = await save_questionnaire_draft(identity, webstore_id, fields)
    missing_required = _missing_required_answers(draft.get("template_snapshot", {}).get("templates") or [], draft.get("answers") or {})
    if missing_required:
        raise WebstoreSetupError("questionnaire_required_answers_missing", f"Missing required answers: {', '.join(missing_required)}", 400)
    now = _now_iso()
    snapshot = {
        "answers": draft.get("answers") or {},
        "known_products": draft.get("known_products") or [],
        "template_snapshot": draft.get("template_snapshot") or {},
        "submitted_at": now,
    }
    await db.webstore_questionnaire_submissions.update_one(
        {"tenant_id": identity["tenant_id"], "id": draft["id"]},
        {"$set": {"status": "submitted", "submitted_at": now, "submitted_snapshot": snapshot, "updated_at": now}},
    )
    await db.webstores.update_one(
        {"tenant_id": identity["tenant_id"], "id": webstore_id},
        {"$set": {"setup_state": "questionnaire_submitted", "updated_at": now}},
    )
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal",
        actor_id=identity["id"],
        actor_email=identity.get("email"),
        action="webstore.questionnaire_submitted",
        entity_type="webstore_questionnaire_submission",
        entity_id=draft["id"],
        summary="Webstore setup questionnaire submitted",
    )
    submitted = await db.webstore_questionnaire_submissions.find_one({"tenant_id": identity["tenant_id"], "id": draft["id"]}, {"_id": 0})
    return serialize_doc(submitted or {})


def _missing_required_answers(templates: list[dict], answers: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for template in templates:
        for section in template.get("sections") or []:
            for question in section.get("questions") or []:
                key = question.get("key")
                if question.get("required") and (answers.get(key) in (None, "")):
                    missing.append(key)
    return missing


async def return_questionnaire(user: dict, webstore_id: str, submission_id: str, reason: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    reason = _clean_text(reason, "reason", limit=1000)
    submission = await db.webstore_questionnaire_submissions.find_one({"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": submission_id}, {"_id": 0})
    if not submission:
        raise WebstoreSetupError("questionnaire_submission_not_found", "Questionnaire submission not found", 404)
    await db.webstore_questionnaire_submissions.update_one(
        {"tenant_id": user["tenant_id"], "id": submission_id},
        {"$set": {"status": "returned_for_changes", "returned_reason": reason, "updated_at": _now_iso()}},
    )
    await _refresh_setup_state(user["tenant_id"], webstore_id)
    return {"submission_id": submission_id, "status": "returned_for_changes", "reason": reason}


async def latest_questionnaire_response(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    await _get_store(user["tenant_id"], webstore_id)
    doc = await db.webstore_questionnaire_submissions.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id},
        {"_id": 0},
        sort=[("updated_at", -1)],
    )
    return {"submission": serialize_doc(doc) if doc else None}


async def _owner_store(identity: dict, webstore_id: str) -> dict:
    if identity.get("portal_type") not in {"webstore_owner", "webstore_manager"}:
        raise WebstoreSetupError("webstore_portal_required", "Webstore portal access required", 403)
    assignment_filter: dict[str, Any] = {
        "tenant_id": identity["tenant_id"],
        "webstore_id": webstore_id,
        "portal_identity_id": identity["id"],
        "status": "active",
    }
    assignment = await db.webstore_access_assignments.find_one(assignment_filter, {"_id": 0})
    if not assignment:
        raise WebstoreSetupError("webstore_assignment_required", "This Webstore is not assigned to your portal account", 403)
    return await _get_store(identity["tenant_id"], webstore_id)


def _owner_safe_store(store: dict) -> dict:
    allowed = {
        "id",
        "name",
        "slug",
        "public_slug",
        "store_type",
        "status",
        "description",
        "branding",
        "deadline_at",
        "public_url",
        "checkout_enabled",
        "terms_fee_acknowledged",
        "owner_approved_at",
        "launch_packet_id",
        "setup_state",
        "setup_profile",
        "target_launch_at",
        "event_start_at",
        "event_location",
    }
    safe = {k: v for k, v in store.items() if k in allowed}
    safe["checkout_enabled"] = False
    safe["checkout_unavailable_reason"] = "Real verified provider checkout is not connected yet."
    return safe


async def setup_progress_for_staff(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _get_store(user["tenant_id"], webstore_id)
    return await _setup_progress(store, staff=True)


async def setup_progress_for_portal(identity: dict, webstore_id: str) -> dict:
    store = await _owner_store(identity, webstore_id)
    return await _setup_progress(store, staff=False)


async def _setup_progress(store: dict, *, staff: bool) -> dict:
    tenant_id = store["tenant_id"]
    webstore_id = store["id"]
    invited_count = await db.webstore_access_assignments.count_documents(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "status": "invited"}
    )
    active_owner_count = await db.webstore_access_assignments.count_documents(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "role": "owner", "status": "active"}
    )
    draft_count = await db.webstore_questionnaire_submissions.count_documents(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "status": "draft"}
    )
    submitted_count = await db.webstore_questionnaire_submissions.count_documents(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "status": "submitted"}
    )
    reviewed_count = await db.webstore_questionnaire_submissions.count_documents(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "status": "reviewed"}
    )
    file_count = await db.webstore_setup_files.count_documents({"tenant_id": tenant_id, "webstore_id": webstore_id, "status": "active"})
    state = await _derive_setup_state(store, invited_count, active_owner_count, draft_count, submitted_count, reviewed_count, file_count)
    steps = [
        {"key": "primary_owner", "label": "Primary Store Owner assigned", "status": "complete" if active_owner_count else "blocked"},
        {"key": "invitations", "label": "Owner and manager invitations", "status": "waiting" if invited_count else "complete"},
        {"key": "questionnaire", "label": "Owner intake questionnaire", "status": "review" if submitted_count else "complete" if reviewed_count else "in_progress" if draft_count else "not_started"},
        {"key": "files", "label": "Setup files", "status": "complete" if file_count else "not_started"},
        {"key": "staff_review", "label": "Staff setup review", "status": "complete" if reviewed_count else "not_started"},
        {"key": "branding", "label": "Branding editor", "status": "deferred"},
        {"key": "products", "label": "Product catalog buildout", "status": "deferred"},
        {"key": "stripe", "label": "Verified Stripe checkout", "status": "deferred"},
    ]
    response = {"webstore_id": webstore_id, "setup_state": state, "steps": steps, "read_only": True}
    if staff:
        response["counts"] = {
            "invited_assignments": invited_count,
            "active_owners": active_owner_count,
            "draft_questionnaires": draft_count,
            "submitted_questionnaires": submitted_count,
            "reviewed_questionnaires": reviewed_count,
            "setup_files": file_count,
        }
    return response


async def _derive_setup_state(store: dict, invited: int, owners: int, drafts: int, submitted: int, reviewed: int, files: int) -> str:
    if owners <= 0:
        state = "blocked"
    elif invited:
        state = "invitation_pending"
    elif submitted:
        state = "staff_review"
    elif reviewed and files:
        state = "setup_complete"
    elif reviewed or files:
        state = "setup_in_progress"
    elif drafts:
        state = "questionnaire_in_progress"
    else:
        state = store.get("setup_state") if store.get("setup_state") in WEBSTORE_SETUP_STATES else "not_started"
    if state != store.get("setup_state"):
        await db.webstores.update_one({"tenant_id": store["tenant_id"], "id": store["id"]}, {"$set": {"setup_state": state, "updated_at": _now_iso()}})
    return state


async def _refresh_setup_state(tenant_id: str, webstore_id: str) -> None:
    store = await _get_store(tenant_id, webstore_id)
    await _setup_progress(store, staff=False)


def _extension(filename: str) -> str:
    return Path(filename or "").suffix.lower().lstrip(".")


def _looks_like(content: bytes, ext: str) -> bool:
    head = content[:256].lstrip()
    if ext in {"jpg", "jpeg"}:
        return content.startswith(b"\xff\xd8")
    if ext == "png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == "webp":
        return content.startswith(b"RIFF") and b"WEBP" in content[:16]
    if ext == "pdf":
        return content.startswith(b"%PDF")
    if ext == "svg":
        lower = head.lower()
        return lower.startswith(b"<svg") or (lower.startswith(b"<?xml") and b"<svg" in lower[:512])
    if ext in DOWNLOAD_ONLY_EXTENSIONS:
        return True
    return False


def _detect_content_type(filename: str, provided: Optional[str]) -> str:
    guessed = mimetypes.guess_type(filename)[0]
    return guessed or provided or "application/octet-stream"


def _safe_file_record(doc: dict, *, staff: bool = False) -> dict:
    allowed = {
        "id",
        "webstore_id",
        "category",
        "file_name",
        "extension",
        "content_type",
        "detected_content_type",
        "size_bytes",
        "uploaded_by_actor_type",
        "status",
        "version",
        "replaces_file_id",
        "replaced_by_file_id",
        "safe_preview_available",
        "inline_preview_allowed",
        "private_download_only",
        "svg_sanitized",
        "notes",
        "created_at",
        "updated_at",
    }
    if staff:
        allowed.add("uploaded_by_id")
    return {k: v for k, v in doc.items() if k in allowed}


def _svg_is_safe(data: bytes) -> bool:
    lower = data[:200_000].lower()
    blocked = [b"<script", b"javascript:", b" onload=", b" onerror=", b"<foreignobject", b"http://", b"https://", b"xlink:href="]
    return not any(marker in lower for marker in blocked)


async def store_setup_file(
    *,
    tenant_id: str,
    webstore_id: str,
    actor_type: str,
    actor_id: Optional[str],
    filename: str,
    content_type: Optional[str],
    data: bytes,
    category: str,
    notes: Optional[str] = None,
    replaces_file_id: Optional[str] = None,
) -> dict:
    await _get_store(tenant_id, webstore_id)
    if not data:
        raise WebstoreSetupError("file_empty", "File is empty", 400)
    if len(data) > MAX_SETUP_FILE_BYTES:
        raise WebstoreSetupError("file_too_large", "Setup files must be 50 MB or smaller", 413)
    ext = _extension(filename)
    if ext in BLOCKED_EXTENSIONS or ext not in SAFE_EXTENSIONS:
        raise WebstoreSetupError("file_type_not_allowed", "That setup file type is not allowed", 400)
    if not _looks_like(data, ext):
        raise WebstoreSetupError("file_content_mismatch", "File content does not match the allowed file type", 400)
    detected = _detect_content_type(filename, content_type)
    if ext == "svg" and not _svg_is_safe(data):
        raise WebstoreSetupError("unsafe_svg_not_allowed", "SVG setup files cannot contain scripts, remote references, or unsafe inline markup", 400)
    svg_safe = ext == "svg"
    inline = ext in {"png", "jpg", "jpeg", "webp", "pdf"} or svg_safe
    key = storage.build_key(tenant_id, filename)
    storage.put_bytes(key, data, detected)
    version = 1
    if replaces_file_id:
        previous = await db.webstore_setup_files.find_one({"tenant_id": tenant_id, "webstore_id": webstore_id, "id": replaces_file_id}, {"_id": 0})
        if not previous:
            raise WebstoreSetupError("setup_file_not_found", "Setup file to replace was not found", 404)
        version = int(previous.get("version") or 1) + 1
    doc = WebstoreSetupFile(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        category=_clean_text(category, "category", limit=80),
        file_name=filename,
        extension=ext,
        content_type=content_type or detected,
        detected_content_type=detected,
        size_bytes=len(data),
        storage_key=key,
        uploaded_by_actor_type=actor_type,
        uploaded_by_id=actor_id,
        version=version,
        replaces_file_id=replaces_file_id,
        safe_preview_available=inline,
        inline_preview_allowed=inline,
        private_download_only=not inline,
        svg_sanitized=svg_safe,
        notes=notes,
    ).model_dump()
    await db.webstore_setup_files.insert_one(prepare_for_mongo(doc))
    if replaces_file_id:
        await db.webstore_setup_files.update_one(
            {"tenant_id": tenant_id, "id": replaces_file_id},
            {"$set": {"status": "replaced", "replaced_by_file_id": doc["id"], "updated_at": _now_iso()}},
        )
    await _refresh_setup_state(tenant_id, webstore_id)
    await _audit(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action="webstore.setup_file_uploaded" if not replaces_file_id else "webstore.setup_file_replaced",
        entity_type="webstore_setup_file",
        entity_id=doc["id"],
        summary="Webstore setup file uploaded" if not replaces_file_id else "Webstore setup file replaced",
        metadata={"category": category, "extension": ext, "size_bytes": len(data), "version": version},
    )
    return _safe_file_record(serialize_doc(doc), staff=actor_type == "staff")


async def upload_setup_file(user: dict, webstore_id: str, *, filename: str, content_type: str, data: bytes, category: str, notes: Optional[str] = None, replaces_file_id: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    file_doc = await store_setup_file(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        filename=filename,
        content_type=content_type,
        data=data,
        category=category,
        notes=notes,
        replaces_file_id=replaces_file_id,
    )
    return {"file": file_doc}


async def portal_upload_setup_file(identity: dict, webstore_id: str, *, filename: str, content_type: str, data: bytes, category: str, notes: Optional[str] = None, replaces_file_id: Optional[str] = None) -> dict:
    await _owner_store(identity, webstore_id)
    file_doc = await store_setup_file(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal",
        actor_id=identity.get("id"),
        filename=filename,
        content_type=content_type,
        data=data,
        category=category,
        notes=notes,
        replaces_file_id=replaces_file_id,
    )
    return {"file": file_doc}


async def list_setup_files(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    await _get_store(user["tenant_id"], webstore_id)
    items = [_safe_file_record(serialize_doc(d), staff=True) async for d in db.webstore_setup_files.find({"tenant_id": user["tenant_id"], "webstore_id": webstore_id}, {"_id": 0, "storage_key": 0}).sort([("created_at", -1)])]
    return {"items": items}


async def portal_list_setup_files(identity: dict, webstore_id: str) -> dict:
    await _owner_store(identity, webstore_id)
    items = [_safe_file_record(serialize_doc(d), staff=False) async for d in db.webstore_setup_files.find({"tenant_id": identity["tenant_id"], "webstore_id": webstore_id, "status": {"$ne": "removed"}}, {"_id": 0, "storage_key": 0}).sort([("created_at", -1)])]
    return {"items": items}


async def download_setup_file(tenant_id: str, webstore_id: str, file_id: str) -> tuple[dict, bytes, str]:
    doc = await db.webstore_setup_files.find_one({"tenant_id": tenant_id, "webstore_id": webstore_id, "id": file_id, "status": {"$ne": "removed"}}, {"_id": 0})
    if not doc:
        raise WebstoreSetupError("setup_file_not_found", "Setup file not found", 404)
    data, content_type = storage.get_bytes(doc["storage_key"])
    return serialize_doc(doc), data, doc.get("detected_content_type") or content_type


async def remove_setup_file(user: dict, webstore_id: str, file_id: str, reason: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    result = await db.webstore_setup_files.update_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": file_id, "status": {"$ne": "removed"}},
        {"$set": {"status": "removed", "notes": reason, "updated_at": _now_iso()}},
    )
    if result.matched_count != 1:
        raise WebstoreSetupError("setup_file_not_found", "Setup file not found", 404)
    await _refresh_setup_state(user["tenant_id"], webstore_id)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.setup_file_removed",
        entity_type="webstore_setup_file",
        entity_id=file_id,
        summary="Webstore setup file removed",
        metadata={"reason": reason},
    )
    return {"file_id": file_id, "status": "removed"}


def _get_path(data: dict, path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _set_path(updates: dict, path: str, value: Any) -> None:
    current = updates
    parts = path.split(".")
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def _field_updates_from_changes(changes: list[dict[str, Any]]) -> dict:
    updates: dict[str, Any] = {}
    for change in changes:
        updates[change["target"]] = change["to"]
    return updates


async def answer_application_preview(user: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    submission_id = fields.get("submission_id")
    submission = await db.webstore_questionnaire_submissions.find_one({"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": submission_id}, {"_id": 0})
    if not submission or submission.get("status") not in {"submitted", "reviewed"}:
        raise WebstoreSetupError("submitted_questionnaire_required", "A submitted questionnaire is required", 409)
    answers = submission.get("submitted_snapshot", {}).get("answers") or submission.get("answers") or {}
    selected = fields.get("selected_answer_keys") or []
    if not selected:
        raise WebstoreSetupError("selected_answers_required", "Select at least one questionnaire answer to apply", 400)
    proposed: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    proposed_values = fields.get("proposed_values") or {}
    for key in selected:
        if key not in answers:
            rejected.append({"answer_key": key, "reason": "answer_not_found"})
            continue
        if key in LOCKED_ANSWER_FIELDS:
            rejected.append({"answer_key": key, "reason": "locked_field"})
            continue
        mapping = SAFE_ANSWER_MAPPING.get(key)
        if not mapping:
            rejected.append({"answer_key": key, "reason": "no_safe_mapping"})
            continue
        value = proposed_values.get(key, answers.get(key))
        if value is None or value == "":
            continue
        target = mapping["target"]
        proposed.append(
            {
                "answer_key": key,
                "target": target,
                "label": mapping["label"],
                "from": _get_path(store, target),
                "to": value,
            }
        )
    return {"webstore_id": webstore_id, "submission_id": submission_id, "proposed_changes": proposed, "rejected_changes": rejected, "dry_run": True}


async def apply_questionnaire_answers(user: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    reason = _clean_text(fields.get("reason"), "reason", limit=1000)
    key = _clean_text(fields.get("idempotency_key"), "idempotency_key", limit=200)
    existing = await db.webstore_answer_applications.find_one({"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "idempotency_key": key}, {"_id": 0})
    if existing:
        return {"application": serialize_doc(existing), "idempotent_replay": True}
    preview = await answer_application_preview(user, webstore_id, fields)
    updates = _field_updates_from_changes(preview["proposed_changes"])
    if not updates:
        raise WebstoreSetupError("no_safe_answers_to_apply", "No safe questionnaire answers were selected for application", 409)
    updates["updated_at"] = _now_iso()
    await db.webstores.update_one({"tenant_id": user["tenant_id"], "id": webstore_id}, {"$set": updates})
    await db.webstore_questionnaire_submissions.update_one(
        {"tenant_id": user["tenant_id"], "id": fields.get("submission_id")},
        {"$set": {"status": "reviewed", "reviewed_at": _now_iso(), "updated_at": _now_iso()}},
    )
    app_doc = WebstoreAnswerApplication(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        submission_id=fields.get("submission_id"),
        idempotency_key=key,
        actor_user_id=user.get("id"),
        actor_email=user.get("email"),
        reason=reason,
        proposed_changes=preview["proposed_changes"],
        applied_changes=preview["proposed_changes"],
        rejected_changes=preview["rejected_changes"],
    ).model_dump()
    await db.webstore_answer_applications.insert_one(prepare_for_mongo(app_doc))
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.questionnaire_answers_applied",
        entity_type="webstore_answer_application",
        entity_id=app_doc["id"],
        summary="Safe Webstore questionnaire answers applied",
        metadata={"idempotency_key": key},
    )
    await _refresh_setup_state(user["tenant_id"], webstore_id)
    return {"application": serialize_doc(app_doc), "idempotent_replay": False}


async def reverse_answer_application(user: dict, webstore_id: str, application_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    reason = _clean_text(fields.get("reason"), "reason", limit=1000)
    original = await db.webstore_answer_applications.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": application_id, "status": "applied"},
        {"_id": 0},
    )
    if not original:
        raise WebstoreSetupError("answer_application_not_found", "Applied answer application not found", 404)
    reversal_changes = [{**change, "from": change.get("to"), "to": change.get("from")} for change in original.get("applied_changes", [])]
    current_store = await _get_store(user["tenant_id"], webstore_id)
    conflicts = [
        change
        for change in original.get("applied_changes", [])
        if _get_path(current_store, change["target"]) != change.get("to")
    ]
    if conflicts:
        raise WebstoreSetupError("answer_reversal_conflict", "Answer application cannot be reversed because newer changes touched the same fields", 409)
    updates = _field_updates_from_changes(reversal_changes)
    updates["updated_at"] = _now_iso()
    await db.webstores.update_one({"tenant_id": user["tenant_id"], "id": webstore_id}, {"$set": updates})
    await db.webstore_answer_applications.update_one(
        {"tenant_id": user["tenant_id"], "id": application_id},
        {"$set": {"status": "reversed", "reversed_at": _now_iso(), "updated_at": _now_iso()}},
    )
    key = fields.get("idempotency_key") or f"reverse:{application_id}"
    reversal = WebstoreAnswerApplication(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        submission_id=original["submission_id"],
        idempotency_key=key,
        actor_user_id=user.get("id"),
        actor_email=user.get("email"),
        reason=reason,
        proposed_changes=reversal_changes,
        applied_changes=reversal_changes,
        rejected_changes=[],
        reversal_of_application_id=application_id,
    ).model_dump()
    await db.webstore_answer_applications.insert_one(prepare_for_mongo(reversal))
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.questionnaire_answers_reversed",
        entity_type="webstore_answer_application",
        entity_id=reversal["id"],
        summary="Webstore questionnaire answer application reversed",
        metadata={"reversal_of_application_id": application_id},
    )
    return {"application": serialize_doc(reversal)}
