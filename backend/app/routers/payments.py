"""EC4 — Payments router.

Dedicated Payment endpoints for EC4. Existing `POST /api/invoices/{id}/payments`
remains as a compatibility shim (routed here internally). New endpoints:

- POST   /api/invoices/{id}/manual-payments      — Record a manual payment.
- POST   /api/payments/{id}/void                 — Void a manual payment.
- POST   /api/invoices/{id}/stripe-intents       — Initiate a Stripe payment.
- POST   /api/payments/{id}/refund               — Server-initiated refund.
- GET    /api/invoices/{id}/payment-history      — Paginated payment history.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import serialize_doc
from ..deps import require_permission
from ..services.payment_service import (
    initiate_refund,
    initiate_stripe,
    record_manual,
    void_manual,
)
from ..services.invoice_reconciliation import reconcile

router = APIRouter(tags=["payments"])


class ManualPaymentIn(BaseModel):
    amount_cents: int = Field(gt=0)
    method: str = "other"
    paid_on: str  # ISO date
    reference: Optional[str] = None
    notes: Optional[str] = None


class VoidIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class StripeIntentIn(BaseModel):
    amount_cents: int = Field(gt=0)


class RefundIn(BaseModel):
    amount_cents: Optional[int] = None
    reason: str = Field(min_length=1, max_length=500)


_ERR_MAP = {
    "invoice_not_found": (404, "Invoice not found"),
    "invoice_void": (400, "Invoice is void"),
    "amount_must_be_positive": (400, "Amount must be positive"),
    "overpayment_rejected": (400, "Amount exceeds current balance"),
    "payment_not_found": (404, "Payment not found"),
    "stripe_payments_cannot_be_manually_voided": (400, "Stripe payments cannot be voided manually — issue a refund instead"),
    "payment_already_voided": (400, "Payment already voided"),
    "payment_not_voidable": (400, "Payment cannot be voided in its current state"),
    "void_reason_required": (400, "Void reason is required"),
    "only_stripe_payments_can_be_refunded": (400, "Only Stripe payments can be refunded here — void manual payments instead"),
    "payment_not_refundable": (400, "Payment cannot be refunded"),
    "refund_reason_required": (400, "Refund reason is required"),
    "refund_amount_invalid": (400, "Refund amount is invalid"),
    "stripe_disabled": (400, "Stripe writes are disabled — set STRIPE_WRITES_ENABLED=true"),
}


def _raise(ex: Exception) -> None:
    msg = str(ex)
    status, detail = _ERR_MAP.get(msg, (400, msg))
    raise HTTPException(status_code=status, detail=detail)


@router.post("/invoices/{invoice_id}/manual-payments", status_code=201)
async def add_manual_payment(
    invoice_id: str,
    payload: ManualPaymentIn,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: dict = Depends(require_permission(Perm.PAYMENT_WRITE)),
) -> dict:
    inv = await db.invoices.find_one({"id": invoice_id, "tenant_id": user["tenant_id"]})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    try:
        pay, already = await record_manual(
            tenant_id=user["tenant_id"], invoice_id=invoice_id,
            amount_cents=payload.amount_cents, method=payload.method,
            paid_on=payload.paid_on, reference=payload.reference,
            notes=payload.notes, idempotency_key=idempotency_key,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except ValueError as ex:
        _raise(ex)
    return {"payment": pay, "already_exists": already}


@router.post("/payments/{payment_id}/void")
async def void_payment(
    payment_id: str,
    payload: VoidIn,
    user: dict = Depends(require_permission(Perm.PAYMENT_VOID)),
) -> dict:
    try:
        return await void_manual(
            tenant_id=user["tenant_id"], payment_id=payment_id,
            reason=payload.reason,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except ValueError as ex:
        _raise(ex)


@router.post("/invoices/{invoice_id}/stripe-intents", status_code=201)
async def initiate_stripe_payment(
    invoice_id: str,
    payload: StripeIntentIn,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: dict = Depends(require_permission(Perm.PAYMENT_WRITE)),
) -> dict:
    inv = await db.invoices.find_one({"id": invoice_id, "tenant_id": user["tenant_id"]})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    try:
        return await initiate_stripe(
            tenant_id=user["tenant_id"], invoice_id=invoice_id,
            amount_cents=payload.amount_cents,
            actor_user_id=user["id"], actor_email=user["email"],
            idempotency_key=idempotency_key,
        )
    except ValueError as ex:
        _raise(ex)
    except RuntimeError as ex:
        if str(ex) == "stripe_not_configured":
            raise HTTPException(status_code=400, detail="Stripe not configured. Set STRIPE_API_KEY.")
        raise HTTPException(status_code=502, detail=f"Stripe error: {ex}")


@router.post("/payments/{payment_id}/refund", status_code=201)
async def refund_payment(
    payment_id: str,
    payload: RefundIn,
    user: dict = Depends(require_permission(Perm.PAYMENT_REFUND)),
) -> dict:
    try:
        return await initiate_refund(
            tenant_id=user["tenant_id"], payment_id=payment_id,
            amount_cents=payload.amount_cents, reason=payload.reason,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except ValueError as ex:
        _raise(ex)
    except RuntimeError as ex:
        raise HTTPException(status_code=502, detail=f"Stripe error: {ex}")


@router.get("/invoices/{invoice_id}/payment-history")
async def payment_history(
    invoice_id: str,
    user: dict = Depends(require_permission(Perm.PAYMENT_READ)),
) -> dict:
    inv = await db.invoices.find_one({"id": invoice_id, "tenant_id": user["tenant_id"]})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    await reconcile(tenant_id=user["tenant_id"], invoice_id=invoice_id)
    cursor = db.payments.find(
        {"tenant_id": user["tenant_id"], "invoice_id": invoice_id}, {"_id": 0}
    ).sort("created_at", -1)
    items = [serialize_doc(d) async for d in cursor]
    inv = await db.invoices.find_one({"id": invoice_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    return {"items": items, "invoice_totals": {
        "total_cents": int(inv.get("total_cents") or 0),
        "amount_paid_cents": int(inv.get("amount_paid_cents") or 0),
        "amount_refunded_cents": int(inv.get("amount_refunded_cents") or 0),
        "balance_due_cents": int(inv.get("balance_due_cents") or 0),
        "financial_status": inv.get("financial_status") or "unpaid",
        "document_status": inv.get("document_status") or "draft",
    }}
