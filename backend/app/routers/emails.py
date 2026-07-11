"""Emails: send + list history.

One shared send endpoint used by all modules. 5 templates. Fails gracefully when
SendGrid is not configured (log with status='failed' and error_message).
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..deps import require_permission
from ..models.email import EmailLog
from ..services.audit import record_audit
from ..services.email import is_configured as email_configured, send_email, record_processed_activity

router = APIRouter(prefix="/emails", tags=["emails"])


TEMPLATES: dict[str, dict[str, str]] = {
    "quote_sent": {
        "subject": "Your quote from {shop}",
        "body": (
            "Hi {customer_name},\n\n"
            "Please find your quote {reference} attached.\n"
            "Total: ${total}\n\n"
            "Let us know if you have any questions.\n\n"
            "— {shop}"
        ),
    },
    "invoice_sent": {
        "subject": "Invoice {reference} from {shop}",
        "body": (
            "Hi {customer_name},\n\n"
            "Attached is invoice {reference} totaling ${total}.\n"
            "Due date: {due_date}\n\n"
            "Thank you for your business.\n\n"
            "— {shop}"
        ),
    },
    "invoice_reminder": {
        "subject": "Friendly reminder: Invoice {reference}",
        "body": (
            "Hi {customer_name},\n\n"
            "This is a friendly reminder that invoice {reference} for ${total} is outstanding.\n"
            "Balance due: ${balance}\n\n"
            "Please let us know if you have any questions.\n\n"
            "— {shop}"
        ),
    },
    "document_sent": {
        "subject": "Documents from {shop}",
        "body": (
            "Hi {customer_name},\n\n"
            "Attached are the documents we discussed.\n\n"
            "— {shop}"
        ),
    },
    "general": {
        "subject": "Message from {shop}",
        "body": "Hi {customer_name},\n\n{body}\n\n— {shop}",
    },
}


class EmailSendIn(BaseModel):
    to_email: EmailStr
    subject: str = Field(min_length=1, max_length=250)
    body: str = Field(min_length=1, max_length=20000)
    template: Literal["quote_sent", "invoice_sent", "invoice_reminder", "document_sent", "general"] = "general"
    customer_id: Optional[str] = None
    related_type: Literal["quote", "order", "work_order", "invoice", "document", "customer", "general"] = "general"
    related_id: Optional[str] = None
    attachment_file_ids: list[str] = Field(default_factory=list)


@router.get("/templates")
async def list_templates(user: dict = Depends(require_permission(Perm.EMAIL_READ))) -> dict:
    return {"templates": TEMPLATES, "configured": email_configured()}


@router.get("/history")
async def email_history(
    customer_id: Optional[str] = Query(None),
    related_type: Optional[str] = Query(None),
    related_id: Optional[str] = Query(None),
    limit: int = Query(100, le=500), skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.EMAIL_READ)),
) -> dict:
    q: dict = {"tenant_id": user["tenant_id"]}
    if customer_id:
        q["customer_id"] = customer_id
    if related_type:
        q["related_type"] = related_type
    if related_id:
        q["related_id"] = related_id
    total = await db.email_logs.count_documents(q)
    cursor = db.email_logs.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    return {"items": [serialize_doc(d) async for d in cursor], "total": total, "limit": limit, "skip": skip,
            "configured": email_configured()}


@router.post("/send", status_code=201)
async def send(
    payload: EmailSendIn,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: dict = Depends(require_permission(Perm.EMAIL_SEND)),
) -> dict:
    # Idempotency check
    if idempotency_key:
        prev = await db.email_logs.find_one(
            {"tenant_id": user["tenant_id"], "idempotency_key": idempotency_key}, {"_id": 0}
        )
        if prev:
            return {"email": serialize_doc(prev), "already_sent": True}

    # Verify customer (if provided) belongs to tenant
    if payload.customer_id:
        cust = await db.customers.find_one({"id": payload.customer_id, "tenant_id": user["tenant_id"]})
        if not cust:
            raise HTTPException(status_code=404, detail="Customer not found")

    # Verify related record belongs to tenant
    if payload.related_id and payload.related_type != "general":
        rel_coll = {
            "quote": "quotes", "order": "orders", "work_order": "work_orders",
            "invoice": "invoices", "customer": "customers", "document": "files",
        }.get(payload.related_type)
        if rel_coll:
            r = await db[rel_coll].find_one({"id": payload.related_id, "tenant_id": user["tenant_id"]})
            if not r:
                raise HTTPException(status_code=404, detail="Related record not found")

    # Verify all attachments belong to tenant
    for fid in payload.attachment_file_ids:
        f = await db.files.find_one({"id": fid, "tenant_id": user["tenant_id"]})
        if not f:
            raise HTTPException(status_code=404, detail=f"Attachment file not found: {fid}")

    # NOTE: SendGrid attachment binaries would be attached here in a fuller build.
    # For MVP we send the message body only; attachment references are logged in the EmailLog
    # so the shop can trace what was included.
    ok, msg_id, err = send_email(
        to_email=str(payload.to_email), subject=payload.subject, body_text=payload.body,
    )

    from ..core.config import get_settings
    _s = get_settings()
    log = EmailLog(
        tenant_id=user["tenant_id"],
        customer_id=payload.customer_id,
        related_type=payload.related_type,
        related_id=payload.related_id,
        template=payload.template,
        to_email=payload.to_email,
        from_email=_s.sendgrid_from_email or "unset@localhost",
        subject=payload.subject,
        body=payload.body,
        status="sent" if ok else ("failed" if err else "queued"),
        error_message=err,
        sent_by=user["id"],
        attachment_file_ids=payload.attachment_file_ids,
        idempotency_key=idempotency_key,
        sendgrid_message_id=msg_id,
    )
    await db.email_logs.insert_one(prepare_for_mongo(log.model_dump()))
    # EC2 — mirror to email_activity so observability shows outbound sends
    await record_processed_activity(
        tenant_id=user["tenant_id"],
        email_log_id=log.id,
        to_email=str(payload.to_email),
        sendgrid_message_id=msg_id,
        related_entity_type=payload.related_type,
        related_entity_id=payload.related_id,
        ok=ok,
        error=err,
    )
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="email.send", entity_type=payload.related_type or "general",
        entity_id=payload.related_id or log.id,
        summary=f"Email '{payload.subject}' to {payload.to_email} — {log.status}",
        diff={"template": payload.template, "attachments": payload.attachment_file_ids, "error": err},
    )
    return {"email": serialize_doc(log.model_dump()), "already_sent": False, "ok": ok, "error": err}
