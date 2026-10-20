"""Webstore request: the one-minute start of the customer journey (P2-10, P2-11, P2-14).

One action, from the Webstores area, a Customer page, or an existing Intake:
link or create the canonical Customer (exact email/phone duplicate check),
reuse or create the Webstore owner contact, and create the draft Webstore
(shown as "Request Received"). Nothing is emailed here; staff send the
information packet next. The Customer owns organization details; the
Webstore owner record holds only the Webstore contact and portal access.
"""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import utc_now
from ..services.audit import record_audit
from .customer_service import create_customer, find_matching_customers, normalize_email
from .webstore_shared import WebstoreError, _clean_optional_text, _clean_text, _normalize_store_type, _require_staff_perm
from .webstore_shared import Perm
from .webstore_staff_stores import create_owner, create_webstore

PRESETS = {"employee_company": {"store_type": "b2b", "setup_profile": {"b2b_preset": "employee_company"}}}


async def customer_matches(user: dict, *, name: Any = None, email: Any = None, phone: Any = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    return {"items": await find_matching_customers(tenant_id=user["tenant_id"], name=name, email=email, phone=phone)}


async def _resolve_customer(user: dict, fields: dict[str, Any]) -> dict:
    tenant_id = user["tenant_id"]
    if fields.get("customer_id"):
        customer = await db.customers.find_one({"tenant_id": tenant_id, "id": fields["customer_id"], "merged_into": None}, {"_id": 0})
        if not customer:
            raise WebstoreError("customer_not_found", "Customer not found", 404)
        return customer
    new = fields.get("new_customer") or {}
    name = _clean_text(new.get("name"), "customer_name")
    matches = await find_matching_customers(tenant_id=tenant_id, name=name, email=new.get("email"), phone=new.get("phone"))
    strong = [m for m in matches if m["strong"]]
    if strong and not fields.get("confirm_new_customer"):
        raise WebstoreError(
            "possible_duplicate_customer",
            "A customer with this email or phone already exists. Choose it, or confirm this is a different customer.",
            409,
        )
    data = {k: v for k, v in {
        "name": name,
        "company": _clean_optional_text(new.get("company")),
        "email": normalize_email(new.get("email")) or None,
        "phone": _clean_optional_text(new.get("phone"), limit=40),
        "customer_type": new.get("customer_type") or "business",
    }.items() if v not in (None, "")}
    return await create_customer(tenant_id=tenant_id, actor=user, data=data)


async def _resolve_owner(user: dict, customer: dict, contact: dict[str, Any]) -> dict:
    email = normalize_email(contact.get("email") or customer.get("email"))
    if not email:
        raise WebstoreError("contact_email_required", "A contact email is needed to send the information packet", 400)
    existing = await db.webstore_owners.find_one({"tenant_id": user["tenant_id"], "email": email}, {"_id": 0})
    if existing:
        if existing.get("customer_id") and existing["customer_id"] != customer["id"]:
            raise WebstoreError("contact_belongs_to_other_customer", "That contact email is already the Webstore contact for a different customer", 409)
        if not existing.get("customer_id"):
            await db.webstore_owners.update_one(
                {"tenant_id": user["tenant_id"], "id": existing["id"]},
                {"$set": {"customer_id": customer["id"], "updated_at": utc_now().isoformat()}},
            )
            existing["customer_id"] = customer["id"]
        return existing
    return await create_owner(user, {
        "name": _clean_text(contact.get("name") or customer.get("name"), "contact_name"),
        "email": email,
        "phone": contact.get("phone") or customer.get("phone"),
        "customer_id": customer["id"],
        "create_portal_identity": False,
    })


async def _link_intake(user: dict, intake_id: Optional[str]) -> Optional[dict]:
    if not intake_id:
        return None
    intake = await db.intake_submissions.find_one({"tenant_id": user["tenant_id"], "id": intake_id}, {"_id": 0})
    if not intake:
        raise WebstoreError("intake_not_found", "Intake not found", 404)
    if intake.get("webstore_id"):
        raise WebstoreError("intake_already_converted", "This intake already started a Webstore request", 409)
    if intake.get("status") not in {"submitted", "under_review", "accepted"}:
        raise WebstoreError("intake_not_convertible", "Only a submitted, in-review or accepted intake can start a Webstore request", 409)
    return intake


async def create_webstore_request(user: dict, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    intake = await _link_intake(user, fields.get("intake_id"))
    if intake and not fields.get("customer_id") and intake.get("customer_id"):
        fields = {**fields, "customer_id": intake["customer_id"]}
    preset = PRESETS.get(str(fields.get("store_type") or ""), {})
    store_type = _normalize_store_type(preset.get("store_type") or fields.get("store_type") or "general")
    customer = await _resolve_customer(user, fields)
    owner = await _resolve_owner(user, customer, fields.get("contact") or {})
    name = _clean_text(fields.get("store_name") or f"{customer.get('company') or customer['name']} Store", "store_name")
    store = await create_webstore(user, {
        "owner_id": owner["id"],
        "name": name,
        "store_type": store_type,
        "description": fields.get("purpose"),
        "target_launch_at": fields.get("target_launch_at"),
        "deadline_at": fields.get("deadline_at"),
        "event_start_at": fields.get("event_start_at"),
        "setup_profile": {
            **(preset.get("setup_profile") or {}),
            "store_purpose": fields.get("purpose") or "",
            "request_notes": fields.get("notes") or "",
        },
        "idempotency_key": fields.get("idempotency_key"),
        "send_owner_invitation": False,
    })
    if intake:
        now = utc_now().isoformat()
        await db.webstores.update_one({"tenant_id": user["tenant_id"], "id": store["id"]}, {"$set": {"source_intake_id": intake["id"]}})
        store["source_intake_id"] = intake["id"]
        await db.intake_submissions.update_one(
            {"tenant_id": user["tenant_id"], "id": intake["id"], "webstore_id": None},
            {"$set": {"webstore_id": store["id"], "status": "converted_to_webstore", "converted_at": now, "updated_at": now},
             "$push": {"status_history": {"from": intake.get("status"), "to": "converted_to_webstore", "actor_user_id": user["id"], "actor_email": user.get("email"), "at": now}}},
        )
        await record_audit(
            tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user.get("email") or "",
            action="intake.converted_to_webstore", entity_type="intake_submission", entity_id=intake["id"],
            summary=f"Intake IN-{intake.get('intake_number')} started Webstore request {store['name']}",
            diff={"webstore_id": store["id"]},
        )
    return {"webstore": store, "customer_id": customer["id"], "owner_id": owner["id"]}
