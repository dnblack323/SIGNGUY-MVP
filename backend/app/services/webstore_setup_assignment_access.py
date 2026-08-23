"""Webstore Owner and Manager assignments, invitations, and acceptance."""
from __future__ import annotations

from .webstore_setup_common import *
from .webstore_setup_progress import _refresh_setup_state


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

__all__ = ['_current_assignment', '_link_or_create_identity', '_create_invitation', 'create_assignment', 'list_assignments', 'resend_invitation', 'revoke_assignment', 'change_primary_owner', 'accept_invitation']
