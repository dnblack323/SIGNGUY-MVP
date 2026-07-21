"""EC6 — Portal Customer routes.

Scope: portal identity's tenant + customer only. No client trusts.
All queries filter by BOTH tenant_id AND customer_id from the JWT.
"""
from __future__ import annotations
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field

from ..core.db import db
from ..core.time_utils import serialize_doc, utc_now
from ..deps_portal import get_current_portal_identity, require_portal_permission
from ..services.approvals_signatures_service import record_approval
from ..services.proofs_service import transition_proof
from ..services.audit import record_audit
from ..services.email import send_email
from ..services.payment_service import initiate_stripe

router = APIRouter(prefix="/portal", tags=["portal_customer"])


def _scope(identity: dict) -> dict:
    return {"tenant_id": identity["tenant_id"], "customer_id": identity["customer_id"]}


def _pick(doc: dict, fields: set[str]) -> dict:
    return {k: serialize_doc(doc).get(k) for k in fields if k in doc}


_QUOTE_FIELDS = {
    "id", "number", "title", "job_name", "description", "status", "document_status", "financial_status",
    "subtotal_cents", "discount_cents", "tax_cents", "total_cents", "balance_due_cents", "currency",
    "created_at", "updated_at", "sent_at", "expires_at", "approved_at", "declined_at", "current_revision",
    "revision_number",
}
_QUOTE_LINE_FIELDS = {
    "id", "quote_id", "revision_number", "position", "category", "product_type", "description", "quantity",
    "unit", "width", "height", "unit_price_cents", "line_subtotal_cents", "line_total_cents", "taxable",
}
_ORDER_FIELDS = {
    "id", "number", "title", "job_name", "description", "status", "production_status", "financial_status",
    "subtotal_cents", "discount_cents", "tax_cents", "total_cents", "balance_cents", "currency",
    "created_at", "updated_at", "due_date", "confirmed_at", "completed_at",
}
_ORDER_ITEM_FIELDS = {
    "id", "order_id", "position", "category", "product_type", "description", "quantity", "unit",
    "width", "height", "unit_price_cents", "line_subtotal_cents", "line_total_cents", "production_status",
}
_INVOICE_FIELDS = {
    "id", "number", "title", "document_status", "financial_status", "subtotal_cents", "discount_cents",
    "tax_cents", "total_cents", "amount_paid_cents", "amount_refunded_cents", "balance_due_cents",
    "currency", "issued_at", "due_date", "paid_at", "created_at", "updated_at",
}
_PAYMENT_FIELDS = {
    "id", "invoice_id", "amount_cents", "currency", "method", "source", "status", "paid_on",
    "received_at", "confirmed_at", "reference", "created_at",
}
_DOCUMENT_FIELDS = {
    "id", "title", "category", "source_type", "source_id", "current_file_id", "version", "visibility",
    "created_at", "updated_at",
}
_PROOF_FIELDS = {
    "id", "number", "title", "status", "current_version", "current_file_id", "sent_at", "approved_at",
    "changes_requested_at", "created_at", "updated_at",
}
_MESSAGE_FIELDS = {
    "id", "from_email", "to_email", "subject", "body", "related_type", "related_id", "status",
    "created_at", "sent_at",
}


@router.get("/quotes")
async def portal_quotes(
    limit: int = Query(50, le=200),
    identity: dict = Depends(require_portal_permission("portal:view_quotes")),
) -> dict:
    cur = db.quotes.find({**_scope(identity)}, {"_id": 0}).sort("created_at", -1).limit(limit)
    return {"items": [_pick(d, _QUOTE_FIELDS) async for d in cur]}


@router.get("/quotes/{qid}")
async def portal_quote_detail(qid: str, identity: dict = Depends(require_portal_permission("portal:view_quotes"))) -> dict:
    q = await db.quotes.find_one({"id": qid, **_scope(identity)}, {"_id": 0})
    if not q:
        raise HTTPException(status_code=404, detail="Quote not found")
    lines = [_pick(li, _QUOTE_LINE_FIELDS) async for li in db.quote_line_items.find(
        {"tenant_id": identity["tenant_id"], "quote_id": qid, "revision_number": q.get("current_revision", q.get("revision_number", 1))},
        {"_id": 0},
    ).sort("position", 1)]
    return {"quote": _pick(q, _QUOTE_FIELDS), "line_items": lines}


class QuoteApprovalIn(BaseModel):
    action: str  # approve | request_changes | decline
    reason: Optional[str] = None


@router.post("/quotes/{qid}/approval", status_code=201)
async def portal_quote_approval(qid: str, payload: QuoteApprovalIn, request: Request,
                                identity: dict = Depends(require_portal_permission("portal:approve_quotes"))) -> dict:
    q = await db.quotes.find_one({"id": qid, **_scope(identity)})
    if not q:
        raise HTTPException(status_code=404, detail="Quote not found")
    try:
        return await record_approval(
            tenant_id=identity["tenant_id"], parent_type="quote_revision", parent_id=qid,
            parent_version=q.get("current_revision", q.get("revision_number", 1)),
            action=payload.action, actor_type="portal_customer", actor_ref=identity["id"],
            actor_display=identity.get("full_name") or identity["email"],
            reason=payload.reason,
            ip=(request.client.host if request.client else None),
            user_agent=request.headers.get("user-agent"),
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@router.get("/orders")
async def portal_orders(
    limit: int = Query(50, le=200),
    identity: dict = Depends(require_portal_permission("portal:view_orders")),
) -> dict:
    cur = db.orders.find({**_scope(identity)}, {"_id": 0}).sort("created_at", -1).limit(limit)
    return {"items": [_pick(d, _ORDER_FIELDS) async for d in cur]}


@router.get("/orders/{oid}")
async def portal_order_detail(oid: str, identity: dict = Depends(require_portal_permission("portal:view_orders"))) -> dict:
    o = await db.orders.find_one({"id": oid, **_scope(identity)}, {"_id": 0})
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    items = [_pick(it, _ORDER_ITEM_FIELDS) async for it in db.order_items.find(
        {"tenant_id": identity["tenant_id"], "order_id": oid}, {"_id": 0}
    ).sort("position", 1)]
    return {"order": _pick(o, _ORDER_FIELDS), "items": items}


@router.get("/invoices")
async def portal_invoices(
    limit: int = Query(50, le=200),
    identity: dict = Depends(require_portal_permission("portal:view_invoices")),
) -> dict:
    cur = db.invoices.find({**_scope(identity), "document_status": {"$ne": "draft"}}, {"_id": 0}).sort("created_at", -1).limit(limit)
    return {"items": [_pick(d, _INVOICE_FIELDS) async for d in cur]}


@router.get("/invoices/{iid}")
async def portal_invoice_detail(iid: str, identity: dict = Depends(require_portal_permission("portal:view_invoices"))) -> dict:
    inv = await db.invoices.find_one({"id": iid, **_scope(identity)}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    payments = [_pick(p, _PAYMENT_FIELDS) async for p in db.payments.find(
        {"tenant_id": identity["tenant_id"], "invoice_id": iid, "status": {"$in": ["confirmed", "refunded"]}},
        {"_id": 0, "idempotency_key": 0, "stripe_client_secret": 0},
    ).sort("received_at", -1)]
    return {"invoice": _pick(inv, _INVOICE_FIELDS), "payments": payments}


class PortalInvoiceIntentIn(BaseModel):
    amount_cents: int = Field(gt=0)


@router.post("/invoices/{iid}/stripe-intents", status_code=201)
async def portal_initiate_stripe(
    iid: str, payload: PortalInvoiceIntentIn, request: Request,
    identity: dict = Depends(require_portal_permission("portal:pay_invoices")),
) -> dict:
    """Portal-scoped Stripe intent initiation.

    Reuses EC4 `initiate_stripe` — no parallel Payment system. All authorization
    (tenant, customer, balance, void guard, dedup) is enforced by the shared
    service. The publishable_key is returned for Stripe.js consumption only;
    it is never rendered as visible text (see PortalInvoicePayPage).
    """
    inv = await db.invoices.find_one({"id": iid, **_scope(identity)})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    try:
        result = await initiate_stripe(
            tenant_id=identity["tenant_id"], invoice_id=iid,
            amount_cents=payload.amount_cents,
            actor_user_id=f"portal:{identity['id']}", actor_email=identity["email"],
            idempotency_key=(request.headers.get("Idempotency-Key") or f"portal:{identity['id']}:{iid}:{payload.amount_cents}"),
        )
    except ValueError as ex:
        msg = str(ex)
        if msg == "invoice_void": raise HTTPException(status_code=400, detail="Invoice is void")
        if msg == "overpayment_rejected": raise HTTPException(status_code=400, detail="Amount exceeds current balance")
        if msg == "stripe_disabled": raise HTTPException(status_code=400, detail="Stripe not configured")
        if msg.startswith("stripe_error:"): raise HTTPException(status_code=400, detail=msg[len("stripe_error:"):])
        raise HTTPException(status_code=400, detail=msg)
    return {k: result.get(k) for k in {"payment_id", "client_secret", "publishable_key", "status", "already_exists"} if k in result}


@router.post("/payments/{payment_id}/dev-simulate-confirm")
async def portal_dev_simulate_confirm(payment_id: str,
                                       identity: dict = Depends(require_portal_permission("portal:pay_invoices"))) -> dict:
    """DEV-ONLY: simulate a Stripe webhook confirmation from the portal.

    Gated by AUTH_DEV_BYPASS=true. Never available in production.
    Exercises the real EC4 confirm_stripe_from_webhook reconciliation path.
    """
    from ..core.config import get_settings
    if not get_settings().auth_dev_bypass:
        raise HTTPException(status_code=404, detail="Not found")
    doc = await db.payments.find_one({"id": payment_id, "tenant_id": identity["tenant_id"],
                                       "customer_id": identity["customer_id"]})
    if not doc or doc.get("source") != "stripe" or not doc.get("stripe_payment_intent_id"):
        raise HTTPException(status_code=404, detail="Stripe payment not found")
    if doc.get("status") == "confirmed":
        return {"already_confirmed": True}
    from ..services.payment_service import confirm_stripe_from_webhook
    await confirm_stripe_from_webhook(
        payment_intent_id=doc["stripe_payment_intent_id"],
        provider_event_id=f"portal_dev_simulate_{payment_id}",
        charge_id=f"ch_portal_dev_{payment_id}",
        dev_simulated=True,
    )
    return {"confirmed": True}


@router.get("/documents")
async def portal_documents(
    identity: dict = Depends(require_portal_permission("portal:view_documents")),
) -> dict:
    # Show only documents explicitly marked customer_visible AND matching this customer
    q = {**_scope(identity), "visibility": "customer_visible", "archived": False}
    cur = db.documents.find(q, {"_id": 0}).sort("created_at", -1).limit(200)
    return {"items": [_pick(d, _DOCUMENT_FIELDS) async for d in cur]}


@router.get("/proofs")
async def portal_proofs(
    identity: dict = Depends(require_portal_permission("portal:view_proofs")),
) -> dict:
    q = {"tenant_id": identity["tenant_id"], "customer_id": identity["customer_id"]}
    cur = db.proofs.find(q, {"_id": 0}).sort("created_at", -1).limit(200)
    return {"items": [_pick(d, _PROOF_FIELDS) async for d in cur]}


class ProofApprovalIn(BaseModel):
    action: str  # approve | request_changes
    reason: Optional[str] = None


@router.post("/proofs/{pid}/approval", status_code=201)
async def portal_proof_approval(pid: str, payload: ProofApprovalIn, request: Request,
                                identity: dict = Depends(require_portal_permission("portal:approve_proofs"))) -> dict:
    proof = await db.proofs.find_one({"id": pid, "tenant_id": identity["tenant_id"], "customer_id": identity["customer_id"]})
    if not proof:
        raise HTTPException(status_code=404, detail="Proof not found")
    try:
        approval = await record_approval(
            tenant_id=identity["tenant_id"], parent_type="proof_version",
            parent_id=pid, parent_version=proof.get("current_version", 1),
            action=payload.action, actor_type="portal_customer", actor_ref=identity["id"],
            actor_display=identity.get("full_name") or identity["email"],
            reason=payload.reason,
            ip=(request.client.host if request.client else None),
            user_agent=request.headers.get("user-agent"),
        )
        # Transition proof through the owning service (audited)
        if payload.action == "approve":
            await transition_proof(
                tenant_id=identity["tenant_id"], proof_id=pid, target="approved",
                actor_user_id=None, actor_email=identity["email"], actor_kind="portal_customer",
            )
        elif payload.action == "request_changes":
            await transition_proof(
                tenant_id=identity["tenant_id"], proof_id=pid, target="changes_requested",
                reason=payload.reason, actor_user_id=None, actor_email=identity["email"],
                actor_kind="portal_customer",
            )
        return approval
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


# ---- Messages (read + send via existing email service) ----

@router.get("/messages")
async def portal_messages(identity: dict = Depends(require_portal_permission("portal:view_messages"))) -> dict:
    # Only email_logs that were sent TO the customer and are marked customer-visible
    q = {"tenant_id": identity["tenant_id"], "customer_id": identity["customer_id"]}
    cur = db.email_logs.find(q, {"_id": 0}).sort("created_at", -1).limit(100)
    return {"items": [_pick(d, _MESSAGE_FIELDS) async for d in cur]}


class PortalMessageIn(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[str] = None


# Per-identity rate limiter for portal-send
_PORTAL_SEND_BUCKET: dict[str, list[float]] = {}
_PORTAL_SEND_WINDOW = 300
_PORTAL_SEND_MAX = 5


def _portal_send_rate(identity_id: str) -> None:
    now = time.time()
    bucket = [t for t in _PORTAL_SEND_BUCKET.get(identity_id, []) if now - t < _PORTAL_SEND_WINDOW]
    if len(bucket) >= _PORTAL_SEND_MAX:
        raise HTTPException(status_code=429, detail="Message rate limit exceeded. Try again shortly.")
    bucket.append(now)
    _PORTAL_SEND_BUCKET[identity_id] = bucket


@router.post("/messages", status_code=201)
async def portal_send_message(payload: PortalMessageIn, request: Request,
                              identity: dict = Depends(require_portal_permission("portal:send_messages"))) -> dict:
    _portal_send_rate(identity["id"])
    # Server-resolves recipients — client CANNOT supply.
    tenant = await db.tenants.find_one({"id": identity["tenant_id"]}, {"_id": 0})
    # Resolve staff recipient — support name, contact_email, email (backwards compat)
    to_email = (tenant or {}).get("contact_email") or (tenant or {}).get("email")
    if not to_email:
        # Fallback: first owner user's email
        owner = await db.users.find_one({"tenant_id": identity["tenant_id"], "role": "owner", "is_active": True}, {"_id": 0, "email": 1})
        to_email = owner["email"] if owner else None
    if not to_email:
        raise HTTPException(status_code=400, detail="Tenant contact email not configured")
    body_text = (
        f"From customer portal — {identity.get('full_name') or identity['email']}\n\n"
        f"{payload.body}\n"
    )
    ok, msg_id, err = send_email(
        to_email=to_email,
        subject=f"[Portal] {payload.subject}",
        body_text=body_text,
        reply_to=identity["email"],
    )
    # Log to email_logs for staff visibility + audit
    import uuid
    log = {
        "id": str(uuid.uuid4()),
        "tenant_id": identity["tenant_id"],
        "to_email": to_email,
        "from_email": identity["email"],
        "subject": payload.subject,
        "body": body_text,
        "template": "general",
        "related_type": payload.related_entity_type or "general",
        "related_id": payload.related_entity_id,
        "customer_id": identity["customer_id"],
        "status": "sent" if ok else "failed",
        "sendgrid_message_id": msg_id,
        "error_message": err,
        "sent_by": f"portal:{identity['id']}",
        "created_at": utc_now().isoformat(),
        "updated_at": utc_now().isoformat(),
    }
    await db.email_logs.insert_one(log)
    await record_audit(
        tenant_id=identity["tenant_id"], actor_user_id=f"portal:{identity['id']}", actor_email=identity["email"],
        action="portal.message_send", entity_type="email_log", entity_id=log["id"],
        summary=f"Portal message: {payload.subject}",
        diff={"related": [payload.related_entity_type, payload.related_entity_id]},
    )
    return {"status": "sent" if ok else "queued", "id": log["id"]}


# ---- Profile ----

class PortalProfileIn(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None


@router.patch("/profile")
async def portal_update_profile(payload: PortalProfileIn,
                                identity: dict = Depends(require_portal_permission("portal:manage_profile"))) -> dict:
    upd = payload.model_dump(exclude_none=True)
    if not upd:
        raise HTTPException(status_code=400, detail="No updates")
    upd["updated_at"] = utc_now().isoformat()
    await db.portal_identities.update_one(
        {"id": identity["id"], "tenant_id": identity["tenant_id"]}, {"$set": upd},
    )
    doc = await db.portal_identities.find_one({"id": identity["id"], "tenant_id": identity["tenant_id"]}, {"_id": 0, "password_hash": 0})
    return _pick(doc or {}, {"id", "email", "full_name", "phone", "role_label", "permissions", "updated_at"})
