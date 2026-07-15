"""EC6 — Public single-action endpoints.

All actions are token-scoped (public_action_tokens). Tokens are single-purpose,
never grant general access, and are consumed on completion (single_use).
"""
from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from ..core.db import db
from ..core.time_utils import serialize_doc
from ..deps_portal import resolve_public_token
from ..services.approvals_signatures_service import record_approval, record_signature
from ..services.decision_room_service import DecisionRoomError, get_customer_view
from ..services.portal_tokens import consume_public_action_token
from ..services.proofs_service import transition_proof
from ..services.audit import record_audit

router = APIRouter(prefix="/public", tags=["public_actions"])


@router.get("/token/introspect")
async def introspect(request: Request, t: str = Query(...)) -> dict:
    token = await resolve_public_token(request, raw_token=t)
    token.pop("token_hash", None)
    return {"action": token["action"], "parent_type": token["parent_type"],
            "parent_id": token["parent_id"], "parent_version": token.get("parent_version"),
            "expires_at": token.get("expires_at"), "single_use": token.get("single_use", True)}


# ---- Quote view / Invoice view (multi-use OK) ----

@router.get("/quotes/{qid}")
async def public_view_quote(qid: str, request: Request, t: str = Query(...)) -> dict:
    token = await resolve_public_token(
        request, raw_token=t,
        expected_action="quote_view", expected_parent_type="quote", expected_parent_id=qid,
    )
    q = await db.quotes.find_one({"id": qid, "tenant_id": token["tenant_id"]}, {"_id": 0, "notes_internal": 0})
    if not q:
        raise HTTPException(status_code=404, detail="Quote not found")
    lines = [serialize_doc(li) async for li in db.quote_line_items.find(
        {"tenant_id": token["tenant_id"], "quote_id": qid,
         "revision_number": q.get("current_revision", q.get("revision_number", 1))},
        {"_id": 0, "cost_cents": 0, "margin_percent": 0},
    ).sort("position", 1)]
    return {"quote": serialize_doc(q), "line_items": lines}


@router.get("/invoices/{iid}")
async def public_view_invoice(iid: str, request: Request, t: str = Query(...)) -> dict:
    token = await resolve_public_token(
        request, raw_token=t,
        expected_action="invoice_view", expected_parent_type="invoice", expected_parent_id=iid,
    )
    inv = await db.invoices.find_one({"id": iid, "tenant_id": token["tenant_id"]}, {"_id": 0, "notes_internal": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {"invoice": serialize_doc(inv)}


# ---- EC10 Phase 10E-1 — Decision Room view (multi-use OK; published-version-only) ----

@router.get("/decision-rooms/{room_id}")
async def public_view_decision_room(room_id: str, request: Request, t: str = Query(...)) -> dict:
    token = await resolve_public_token(
        request, raw_token=t,
        expected_action="decision_room_view", expected_parent_type="decision_room", expected_parent_id=room_id,
    )
    try:
        return await get_customer_view(tenant_id=token["tenant_id"], room_id=room_id, customer_id=None)
    except DecisionRoomError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


# ---- Proof approve / request changes (single-use) ----

class ProofApprovalIn(BaseModel):
    action: str   # approve | request_changes
    reason: Optional[str] = None
    signer_name: Optional[str] = None


@router.get("/proofs/{pid}")
async def public_view_proof(pid: str, request: Request, t: str = Query(...)) -> dict:
    token = await resolve_public_token(
        request, raw_token=t, expected_parent_type="proof", expected_parent_id=pid,
    )
    if token["action"] not in {"proof_approve", "proof_request_changes"}:
        raise HTTPException(status_code=403, detail="Token action mismatch")
    proof = await db.proofs.find_one({"id": pid, "tenant_id": token["tenant_id"]}, {"_id": 0})
    if not proof:
        raise HTTPException(status_code=404, detail="Proof not found")
    return {"proof": serialize_doc(proof)}


@router.post("/proofs/{pid}/action", status_code=201)
async def public_proof_action(pid: str, payload: ProofApprovalIn, request: Request, t: str = Query(...)) -> dict:
    expected = "proof_approve" if payload.action == "approve" else "proof_request_changes"
    token = await resolve_public_token(
        request, raw_token=t,
        expected_action=expected, expected_parent_type="proof", expected_parent_id=pid,
    )
    proof = await db.proofs.find_one({"id": pid, "tenant_id": token["tenant_id"]})
    if not proof:
        raise HTTPException(status_code=404, detail="Proof not found")
    try:
        approval = await record_approval(
            tenant_id=token["tenant_id"], parent_type="proof_version", parent_id=pid,
            parent_version=proof.get("current_version", 1),
            action=payload.action, actor_type="public_token", actor_ref=f"token:{token['id']}",
            actor_display=payload.signer_name, reason=payload.reason,
            ip=(request.client.host if request.client else None),
            user_agent=request.headers.get("user-agent"),
        )
        if payload.action == "approve":
            await transition_proof(
                tenant_id=token["tenant_id"], proof_id=pid, target="approved",
                actor_kind="public_token", actor_email=payload.signer_name,
            )
        else:
            await transition_proof(
                tenant_id=token["tenant_id"], proof_id=pid, target="changes_requested",
                reason=payload.reason, actor_kind="public_token", actor_email=payload.signer_name,
            )
        await consume_public_action_token(token["id"])
        return approval
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


# ---- Signatures (single-use) ----

class PublicSignIn(BaseModel):
    signer_name: str
    signer_email: str
    signature_type: str          # drawn | typed
    typed_text: Optional[str] = None
    signature_data_ref: Optional[str] = None  # for drawn, requires an uploaded file_id


@router.get("/signatures/{rid}")
async def public_view_sig_request(rid: str, request: Request, t: str = Query(...)) -> dict:
    token = await resolve_public_token(
        request, raw_token=t, expected_action="sign",
        expected_parent_type="signature_request", expected_parent_id=rid,
    )
    req = await db.signature_requests.find_one({"id": rid, "tenant_id": token["tenant_id"]}, {"_id": 0})
    if not req:
        raise HTTPException(status_code=404, detail="Signature request not found")
    return {"request": serialize_doc(req)}


@router.post("/signatures/{rid}/sign", status_code=201)
async def public_sign(rid: str, payload: PublicSignIn, request: Request, t: str = Query(...)) -> dict:
    token = await resolve_public_token(
        request, raw_token=t, expected_action="sign",
        expected_parent_type="signature_request", expected_parent_id=rid,
    )
    if token.get("audience_email") and token["audience_email"].lower() != payload.signer_email.lower():
        raise HTTPException(status_code=403, detail="Signer email mismatch")
    try:
        sig = await record_signature(
            tenant_id=token["tenant_id"], request_id=rid,
            signer_email=payload.signer_email, signer_name=payload.signer_name,
            signature_type=payload.signature_type, typed_text=payload.typed_text,
            signature_data_ref=payload.signature_data_ref,
            token_id=token["id"],
            ip=(request.client.host if request.client else None),
            user_agent=request.headers.get("user-agent"),
        )
        await consume_public_action_token(token["id"])
        return sig
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


# ---- Public Quote Request (open form, spam-protected) ----

class PublicQuoteRequestIn(BaseModel):
    tenant_slug: str
    contact_name: str
    contact_email: str
    contact_phone: Optional[str] = None
    company: Optional[str] = None
    project_title: Optional[str] = None
    project_description: Optional[str] = None
    desired_due_date: Optional[str] = None
    consent_marketing: bool = False
    file_ids: list[str] = []       # optional; must belong to a session upload endpoint (not implemented here)


import time as _time
_QR_BUCKET: dict[str, list[float]] = {}
_QR_WINDOW = 60
_QR_MAX = 5


def _qr_rate(ip: str) -> None:
    now = _time.time()
    bucket = [t for t in _QR_BUCKET.get(ip, []) if now - t < _QR_WINDOW]
    if len(bucket) >= _QR_MAX:
        raise HTTPException(status_code=429, detail="Too many requests")
    bucket.append(now)
    _QR_BUCKET[ip] = bucket


@router.post("/quote-request", status_code=201)
async def public_quote_request(payload: PublicQuoteRequestIn, request: Request) -> dict:
    ip = (request.client.host if request.client else "?") or "?"
    _qr_rate(ip)
    tenant = await db.tenants.find_one({"slug": payload.tenant_slug}, {"_id": 0, "id": 1})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    from ..services.sequence import next_number
    from ..models.public_intake import QuoteRequest
    num = await next_number(tenant_id=tenant["id"], name="quote_request")
    doc = QuoteRequest(
        tenant_id=tenant["id"], number=num,
        contact_name=payload.contact_name, contact_email=payload.contact_email.lower(),
        contact_phone=payload.contact_phone, company=payload.company,
        project_title=payload.project_title, project_description=payload.project_description,
        desired_due_date=payload.desired_due_date, consent_marketing=payload.consent_marketing,
        source="public_web", ip=ip, user_agent=request.headers.get("user-agent"),
        file_ids=payload.file_ids or [],
    ).model_dump()
    await db.quote_requests.insert_one(doc)
    await record_audit(
        tenant_id=tenant["id"], actor_user_id="public", actor_email=payload.contact_email,
        action="quote_request.submit", entity_type="quote_request", entity_id=doc["id"],
        summary=f"Public quote request #{num}",
    )
    return {"status": "received", "reference": f"QR-{num}"}


# ---- Public Customer Intake (token-scoped) ----

class CustomerIntakeSubmitIn(BaseModel):
    response: dict


@router.post("/customer-intake/{intake_id}/submit", status_code=201)
async def submit_customer_intake(intake_id: str, payload: CustomerIntakeSubmitIn, request: Request, t: str = Query(...)) -> dict:
    token = await resolve_public_token(
        request, raw_token=t,
        expected_action="customer_intake", expected_parent_type="customer_intake", expected_parent_id=intake_id,
    )
    intake = await db.customer_intakes.find_one({"id": intake_id, "tenant_id": token["tenant_id"]})
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    if intake.get("status") == "applied":
        raise HTTPException(status_code=410, detail="Intake already applied")
    # Compute staged changes (diff against authoritative customer — no silent overwrite)
    cust = await db.customers.find_one({"id": intake["customer_id"], "tenant_id": token["tenant_id"]}, {"_id": 0}) or {}
    staged: dict = {}
    for field, val in (payload.response or {}).items():
        if field in {"tenant_id", "id"}:
            continue
        current = cust.get(field)
        if val is not None and val != current:
            staged[field] = {"from": current, "to": val}
    from ..core.time_utils import utc_now
    await db.customer_intakes.update_one(
        {"id": intake_id, "tenant_id": token["tenant_id"]},
        {"$set": {
            "response": payload.response, "staged_changes": staged,
            "submitted_at": utc_now().isoformat(),
            "submitted_ip": (request.client.host if request.client else None),
            "submitted_user_agent": request.headers.get("user-agent"),
            "status": "submitted",
        }},
    )
    await consume_public_action_token(token["id"])
    await record_audit(
        tenant_id=token["tenant_id"], actor_user_id=f"token:{token['id']}", actor_email=(intake.get("customer_id") or "public@intake"),
        action="customer_intake.submit", entity_type="customer_intake", entity_id=intake_id,
        summary=f"Customer intake submitted", diff={"staged_fields": list(staged.keys())},
    )
    return {"status": "submitted"}
