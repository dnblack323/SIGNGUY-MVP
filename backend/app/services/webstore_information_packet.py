"""Webstore information packet (P2-13): one email + the same Welcome content in the Owner Portal.

Content comes from the Webstore Starter pack on the central template platform
(one ``email`` template per store type, built from shared blocks). A shop can
customise a type by duplicating the template in the Templates library; the
shop's active copy wins. Delivery uses the shared logged sender, so the email
log, activity feed and SendGrid delivery events all apply.
"""
from __future__ import annotations

from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc
from ..models.template_definition import TemplateDefinition
from ..models.webstore import WEBSTORE_TYPE_LABELS, WEBSTORE_TYPES
from . import settings as settings_svc
from .email import public_url, send_logged_email
from .template_service import PLATFORM_TENANT_ID, _normalize_ec12_body, _template_channels, _template_placeholders, render_channels
from .webstore_setup_assignment_access import create_assignment, resend_invitation
from .webstore_setup_common import Perm, _audit, _email, _get_owner, _get_store, _now_iso, _require_staff_perm
from .webstore_setup_progress import _refresh_setup_state

PACKET_PACK_ID = "webstore_starter"
PACKET_VERSION = 1

_INTRO = {
    "fundraiser": "Thanks for choosing {{shop_name}} for your fundraiser store. Supporters order online, we produce and deliver everything, and your organization earns the agreed proceeds.",
    "event": "Thanks for choosing {{shop_name}} for your event store. Attendees order online before the event, and we produce and deliver everything in time.",
    "team_school": "Thanks for choosing {{shop_name}} for your team or school store. Families order online, and we handle production, sorting and delivery.",
    "b2b": "Thanks for choosing {{shop_name}} for your business store. Your team or customers order online, and we produce and deliver everything.",
    "promotional": "Thanks for choosing {{shop_name}} for your promotional store. Fans order online, and we produce and ship everything.",
    "general": "Thanks for choosing {{shop_name}} for your online store. Buyers order online, and we produce and deliver everything.",
}
_SHARED = (
    "How it works:\n"
    "1. Complete the short setup questionnaire using the link below. You can save and come back any time.\n"
    "2. We review your answers and prepare your store: products, pricing and a preview.\n"
    "3. You review and approve the store before it opens.\n"
    "4. Buyers order during the ordering window; we produce and deliver the orders.\n\n"
    "Payments and proceeds: buyers pay {{shop_name}} directly. We keep the agreed production and fulfillment price, "
    "and any proceeds your organization earns are paid to you by check or bank transfer on the agreed schedule. "
    "You never need to share bank or card details with us online.\n\n"
    "Custom merchandise is final sale, except for our mistakes, manufacturing defects, incorrect items, "
    "unfulfilled orders, approved cancellations, or where the law requires a refund.\n\n"
    "Start your questionnaire: {{questionnaire_link}}\n\n"
    "Questions? Reply to this email or call {{shop_phone}}.\n\n"
    "{{shop_name}}"
)


def _source_id(store_type: str) -> str:
    return f"{PACKET_PACK_ID}_packet_{store_type}"


def _body(store_type: str) -> dict[str, Any]:
    label = WEBSTORE_TYPE_LABELS.get(store_type, "Webstore")
    return _normalize_ec12_body({"channels": {
        "email_subject": "Your {{store_type_label}} store with {{shop_name}}: next steps",
        "email_body": "Hi {{contact_name}},\n\n" + _INTRO[store_type] + "\n\n" + _SHARED,
        "in_app": f"{label} information packet",
    }})


async def ensure_platform_packet_templates() -> None:
    for store_type in WEBSTORE_TYPES:
        body = _body(store_type)
        doc = TemplateDefinition(
            id=_source_id(store_type),
            tenant_id=PLATFORM_TENANT_ID,
            owner_scope="platform",
            name=f"Webstore information packet: {WEBSTORE_TYPE_LABELS.get(store_type, store_type)}",
            template_type="email",
            description="Webstore Starter information packet email. Duplicate it to customise your wording.",
            body=body,
            version=PACKET_VERSION,
            starter_template=True,
            pack_id=PACKET_PACK_ID,
            pack_type="starter",
            platform_managed=True,
            channels=_template_channels(body),
            placeholders=_template_placeholders(body),
            created_by_user_id="system",
            updated_by_user_id="system",
        ).model_dump()
        try:
            await db.template_definitions.insert_one(prepare_for_mongo(dict(doc)))
        except DuplicateKeyError:
            pass


async def _packet_template(tenant_id: str, store_type: str) -> dict[str, Any]:
    await ensure_platform_packet_templates()
    store_type = store_type if store_type in WEBSTORE_TYPES else "general"
    shop_copy = await db.template_definitions.find_one(
        {"tenant_id": tenant_id, "source_template_id": _source_id(store_type), "active": True, "archived_at": None},
        {"_id": 0}, sort=[("updated_at", -1)],
    )
    return shop_copy or await db.template_definitions.find_one({"id": _source_id(store_type)}, {"_id": 0})


async def _context(store: dict, owner: dict, link: str) -> dict[str, str]:
    company = await settings_svc.list_namespace(tenant_id=store["tenant_id"], namespace="company_profile")
    tenant = await db.tenants.find_one({"id": store["tenant_id"]}, {"_id": 0, "name": 1})
    customer = await db.customers.find_one({"tenant_id": store["tenant_id"], "id": owner.get("customer_id")}, {"_id": 0, "name": 1}) if owner.get("customer_id") else None
    return {
        "shop_name": str(company.get("shop_name") or (tenant or {}).get("name") or "Our shop"),
        "shop_email": str(company.get("email") or ""),
        "shop_phone": str(company.get("phone") or "us"),
        "contact_name": str(owner.get("name") or (customer or {}).get("name") or "there"),
        "customer_name": str((customer or {}).get("name") or owner.get("name") or ""),
        "store_name": str(store.get("name") or ""),
        "store_type_label": WEBSTORE_TYPE_LABELS.get(store.get("store_type") or "general", "Webstore"),
        "questionnaire_link": link,
    }


async def _render(store: dict, owner: dict, link: str) -> dict[str, Any]:
    template = await _packet_template(store["tenant_id"], store.get("store_type") or "general")
    context = await _context(store, owner, link)
    rendered = render_channels(template.get("body") or {}, context)
    return {
        "subject": rendered.get("email_subject", ""),
        "body": rendered.get("email_body", ""),
        "reply_to": context["shop_email"] or None,
        "template_id": template["id"],
        "template_version": template.get("version"),
        "customised": template.get("tenant_id") != PLATFORM_TENANT_ID,
    }


async def _delivery_status(tenant_id: str, packet: dict) -> dict[str, Any]:
    log_id = packet.get("last_email_log_id")
    if not log_id:
        return {"status": "prepared"}
    log = await db.email_logs.find_one({"tenant_id": tenant_id, "id": log_id}, {"_id": 0, "status": 1, "error_message": 1, "created_at": 1, "to_email": 1})
    event = await db.email_activity.find_one(
        {"tenant_id": tenant_id, "email_log_id": log_id, "provider": "sendgrid"}, {"_id": 0, "event": 1, "event_timestamp": 1},
        sort=[("event_timestamp", -1)],
    )
    status = "sent" if (log or {}).get("status") == "sent" else "failed"
    if event and event.get("event") in {"bounce", "dropped", "spamreport"}:
        status = "failed"
    elif event and event.get("event") in {"delivered", "open", "click"}:
        status = "delivered"
    return {
        "status": status,
        "provider_event": (event or {}).get("event"),
        "error": (log or {}).get("error_message"),
        "to_email": (log or {}).get("to_email"),
        "sent_at": (log or {}).get("created_at"),
    }


async def packet_preview(user: dict, webstore_id: str) -> dict[str, Any]:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _get_store(user["tenant_id"], webstore_id)
    owner = await _get_owner(user["tenant_id"], store["owner_id"])
    packet = store.get("information_packet") or {}
    preview = await _render(store, owner, "[secure questionnaire link is added when sent]")
    return {
        "webstore_id": webstore_id,
        "recipient_email": owner.get("email"),
        "preview": preview,
        "sent_count": int(packet.get("sent_count") or 0),
        "delivery": await _delivery_status(user["tenant_id"], packet),
    }


async def _questionnaire_link(user: dict, store: dict, owner: dict) -> str:
    """A fresh 48-hour invitation link, or the portal link when the owner already has access."""
    email = _email(owner.get("email"))
    assignment = await db.webstore_access_assignments.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": store["id"], "role": "owner", "email": email, "status": {"$in": ["invited", "active", "expired"]}},
        {"_id": 0}, sort=[("is_primary_owner", -1), ("created_at", 1)],
    )
    if assignment and assignment.get("status") == "active":
        return public_url(f"/portal/webstores/{store['id']}")
    if assignment:
        invite = (await resend_invitation(user, store["id"], assignment["id"], send=False))["invitation"]
    else:
        invite = (await create_assignment(
            user, store["id"], {"role": "owner", "owner_id": owner["id"], "email": email, "name": owner.get("name") or email, "is_primary_owner": True},
            primary=True, send=False,
        ))["invitation"]
    return invite["invitation_url"]


async def send_information_packet(user: dict, webstore_id: str, *, resend: bool = False) -> dict[str, Any]:
    """Send the packet once. A repeat call without ``resend`` returns the existing status (no duplicate email)."""
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    store = await _get_store(user["tenant_id"], webstore_id)
    owner = await _get_owner(user["tenant_id"], store["owner_id"])
    packet = store.get("information_packet") or {}
    if packet.get("last_email_log_id") and not resend:
        result = await packet_preview(user, webstore_id)
        return {**result, "already_sent": True, "questionnaire_link": None}
    link = await _questionnaire_link(user, store, owner)
    rendered = await _render(store, owner, link)
    sequence = int(packet.get("sent_count") or 0) + 1
    log = await send_logged_email(
        tenant_id=user["tenant_id"],
        to_email=_email(owner.get("email")),
        subject=rendered["subject"],
        body_text=rendered["body"],
        reply_to=rendered["reply_to"],
        sent_by=user.get("id") or "system",
        template="webstore_information_packet",
        related_type="webstore",
        related_id=webstore_id,
        related_entity_type="webstore_information_packet",
        customer_id=owner.get("customer_id"),
        idempotency_key=f"webstore-packet:{webstore_id}:{sequence}",
    )
    now = _now_iso()
    updates: dict[str, Any] = {
        "information_packet": {
            "sent_count": sequence,
            "last_sent_at": now,
            "last_email_log_id": log["id"],
            "last_status": log["status"],
            "template_id": rendered["template_id"],
            "template_version": rendered["template_version"],
        },
        "updated_at": now,
    }
    if store.get("status") in {"draft", "questionnaire_sent", "waiting_on_store_owner"}:
        updates["status"] = "questionnaire_sent"
    await db.webstores.update_one({"tenant_id": user["tenant_id"], "id": webstore_id}, {"$set": updates})
    await _refresh_setup_state(user["tenant_id"], webstore_id)
    await _audit(
        tenant_id=user["tenant_id"], webstore_id=webstore_id, actor_type="staff", actor_id=user.get("id"), actor_email=user.get("email"),
        action="webstore.information_packet_resent" if resend else "webstore.information_packet_sent",
        entity_type="webstore", entity_id=webstore_id, summary=f"Information packet {'resent' if resend else 'sent'} ({log['status']})",
        metadata={"email_log_id": log["id"], "status": log["status"], "sequence": sequence},
    )
    result = await packet_preview(user, webstore_id)
    # The raw link is returned once so staff can copy it if email delivery fails.
    return {**result, "already_sent": False, "questionnaire_link": link}


async def owner_welcome(store: dict, owner: Optional[dict]) -> Optional[dict[str, str]]:
    """Packet content for the Owner Portal Welcome card (same text as the email)."""
    if not owner:
        return None
    rendered = await _render(store, owner, public_url(f"/portal/webstores/{store['id']}"))
    return {"title": rendered["subject"], "body": rendered["body"]}


async def packet_email_logs(tenant_id: str, webstore_id: str) -> list[dict[str, Any]]:
    cursor = db.email_logs.find(
        {"tenant_id": tenant_id, "related_type": "webstore", "related_id": webstore_id, "template": "webstore_information_packet"},
        {"_id": 0, "body": 0},
    ).sort("created_at", -1).limit(20)
    return [serialize_doc(d) async for d in cursor]


__all__ = ["ensure_platform_packet_templates", "packet_preview", "send_information_packet", "owner_welcome", "packet_email_logs"]
