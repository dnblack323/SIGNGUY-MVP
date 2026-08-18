"""Initial setup orchestration and staff-triggered questionnaire delivery."""
from __future__ import annotations

from .webstore_setup_common import *
from .webstore_setup_assignment_access import create_assignment, resend_invitation
from .webstore_setup_questionnaires import bind_questionnaire_templates
from .webstore_setup_progress import _refresh_setup_state


async def initialize_store_setup(user: dict, store: dict, owner: dict, fields: dict[str, Any]) -> None:
    await db.webstores.update_one(
        {"tenant_id": store["tenant_id"], "id": store["id"]},
        {
            "$set": {
                "setup_state": "not_started",
                "setup_profile": fields.get("setup_profile") or {},
                "setup_requirements": fields.get("setup_requirements") or {},
                "store_settings": default_store_settings(store.get("store_type"), fields.get("store_settings") or store.get("store_settings") or {}),
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


async def send_questionnaire_to_owner(user: dict, webstore_id: str, fields: Optional[dict[str, Any]] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    fields = fields or {}
    store = await _get_store(user["tenant_id"], webstore_id)
    owner = await _get_owner(user["tenant_id"], store["owner_id"])
    templates = await bind_questionnaire_templates(user, webstore_id)
    email = _email(fields.get("email") or owner.get("email"))
    name = fields.get("name") or owner.get("name") or email
    assignment = await db.webstore_access_assignments.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "role": "owner", "email": email, "status": {"$in": ["invited", "active", "expired"]}},
        {"_id": 0},
        sort=[("is_primary_owner", -1), ("created_at", 1)],
    )
    invitation = None
    email_sent = False
    delivery_error = None
    portal_path = f"/portal/webstores/{webstore_id}"
    if assignment and assignment.get("status") in {"invited", "expired"}:
        result = await resend_invitation(user, webstore_id, assignment["id"])
        invitation = result.get("invitation")
        email_sent = invitation.get("status") == "sent" if invitation else False
        delivery_error = invitation.get("delivery_error") if invitation else None
    elif assignment and assignment.get("status") == "active":
        subject = f"{store.get('name')} setup questionnaire is ready"
        body = (
            f"Your SignGuy Webstore setup questionnaire is ready. "
            f"Open your secure Store Owner portal to answer it: {portal_path}\n\n"
            "After you submit it, the shop will review your answers, add product mockups, prepare the store, and send you a launch packet for approval."
        )
        ok, msg_id, error = send_email(to_email=email, subject=subject, body_text=body)
        email_sent = ok
        delivery_error = error
        await record_processed_activity(
            tenant_id=user["tenant_id"],
            email_log_id=f"webstore-questionnaire-active-owner-{webstore_id}-{assignment['id']}",
            to_email=email,
            sendgrid_message_id=msg_id,
            related_entity_type="webstore_questionnaire",
            related_entity_id=webstore_id,
            ok=ok,
            error=error,
        )
    else:
        result = await create_assignment(
            user,
            webstore_id,
            {"role": "owner", "owner_id": owner["id"], "email": email, "name": name, "is_primary_owner": False},
            send=True,
        )
        assignment = result.get("assignment")
        invitation = result.get("invitation")
        email_sent = invitation.get("status") == "sent" if invitation else False
        delivery_error = invitation.get("delivery_error") if invitation else None

    status_update = {"updated_at": _now_iso()}
    if store.get("status") in {"draft", "questionnaire_sent", "waiting_on_store_owner", "changes_requested"}:
        status_update["status"] = "questionnaire_sent"
    await db.webstores.update_one(
        {"tenant_id": user["tenant_id"], "id": webstore_id},
        {"$set": status_update},
    )
    await _refresh_setup_state(user["tenant_id"], webstore_id)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.questionnaire_sent",
        entity_type="webstore",
        entity_id=webstore_id,
        summary="Webstore setup questionnaire sent to owner",
        metadata={"email": email, "email_sent": email_sent, "template_count": len(templates.get("templates") or [])},
    )
    return {
        "success": True,
        "webstore_id": webstore_id,
        "email": email,
        "email_sent": email_sent,
        "delivery_error": delivery_error,
        "templates": templates.get("templates") or [],
        "portal_path": portal_path,
        "invitation": invitation,
        "link": (invitation or {}).get("invitation_url") or portal_path,
        "summary": (
            "The owner will complete the type-specific setup questionnaire. "
            "After submission, staff will be notified so answers can be reviewed, safely applied, and used for product mockups and store setup."
        ),
    }

__all__ = ['initialize_store_setup', 'send_questionnaire_to_owner']
