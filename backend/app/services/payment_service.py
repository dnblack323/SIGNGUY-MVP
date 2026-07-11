"""EC4 — Payment service.

Business logic for manual + Stripe payments, void, refund. Routers stay thin
and only handle HTTP concerns.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.payment import Payment
from . import stripe_core
from .audit import record_audit
from .invoice_reconciliation import reconcile


async def _invoice_balance(tenant_id: str, invoice_id: str) -> tuple[dict, int]:
    inv = await db.invoices.find_one({"id": invoice_id, "tenant_id": tenant_id})
    if not inv:
        raise ValueError("invoice_not_found")
    # Reconcile-then-read to ensure balance reflects live state.
    await reconcile(tenant_id=tenant_id, invoice_id=invoice_id)
    inv = await db.invoices.find_one({"id": invoice_id, "tenant_id": tenant_id})
    return inv, int(inv.get("balance_due_cents") or 0)


# ---------------- Manual payments ----------------


async def record_manual(
    *,
    tenant_id: str,
    invoice_id: str,
    amount_cents: int,
    method: str,
    paid_on: str,
    reference: Optional[str],
    notes: Optional[str],
    idempotency_key: Optional[str],
    actor_user_id: str,
    actor_email: str,
) -> tuple[dict, bool]:
    """Record a manual payment against an Invoice.

    Enforces:
      - Invoice exists + not void.
      - Idempotency-Key replay returns the previously created row.
      - Overpayment rejected (server-derived balance).
      - Reconciliation runs and result is returned.
    """
    inv, balance = await _invoice_balance(tenant_id, invoice_id)
    if inv.get("document_status") == "void":
        raise ValueError("invoice_void")

    # Idempotent replay
    if idempotency_key:
        prev = await db.payments.find_one(
            {"tenant_id": tenant_id, "invoice_id": invoice_id, "idempotency_key": idempotency_key},
            {"_id": 0},
        )
        if prev:
            return serialize_doc(prev), True

    if amount_cents <= 0:
        raise ValueError("amount_must_be_positive")
    if amount_cents > balance:
        raise ValueError("overpayment_rejected")

    pay = Payment(
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        customer_id=inv["customer_id"],
        order_id=inv.get("order_id"),
        source="manual",
        status="confirmed",
        amount_cents=amount_cents,
        method=method,  # type: ignore[arg-type]
        paid_on=paid_on,
        reference=reference,
        notes=notes,
        idempotency_key=idempotency_key,
        confirmed_at=utc_now(),
        created_by=actor_user_id,
    )
    try:
        await db.payments.insert_one(prepare_for_mongo(pay.model_dump()))
    except DuplicateKeyError:
        prev = await db.payments.find_one(
            {"tenant_id": tenant_id, "invoice_id": invoice_id, "idempotency_key": idempotency_key},
            {"_id": 0},
        )
        if prev:
            return serialize_doc(prev), True
        raise

    # Race-safe re-check: if concurrent inserts pushed us above total, roll back.
    _, new_balance = await _invoice_balance(tenant_id, invoice_id)
    if new_balance < 0:
        await db.payments.delete_one({"id": pay.id})
        await reconcile(tenant_id=tenant_id, invoice_id=invoice_id)
        raise ValueError("overpayment_rejected")

    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="payment_recorded_manual", entity_type="invoice", entity_id=invoice_id,
        summary=f"Manual payment ${amount_cents / 100:,.2f} recorded",
        diff={"payment_id": pay.id, "amount_cents": amount_cents, "method": method},
    )
    return serialize_doc(pay.model_dump()), False


async def void_manual(
    *,
    tenant_id: str,
    payment_id: str,
    reason: str,
    actor_user_id: str,
    actor_email: str,
) -> dict:
    doc = await db.payments.find_one({"id": payment_id, "tenant_id": tenant_id})
    if not doc:
        raise ValueError("payment_not_found")
    if doc.get("source") != "manual":
        raise ValueError("stripe_payments_cannot_be_manually_voided")
    if doc.get("status") == "voided":
        raise ValueError("payment_already_voided")
    if doc.get("status") != "confirmed":
        raise ValueError("payment_not_voidable")
    if not reason or not reason.strip():
        raise ValueError("void_reason_required")

    await db.payments.update_one(
        {"id": payment_id},
        {"$set": {
            "status": "voided",
            "voided_at": utc_now().isoformat(),
            "voided_by": actor_user_id,
            "void_reason": reason.strip(),
            "updated_at": utc_now().isoformat(),
        }},
    )
    await reconcile(tenant_id=tenant_id, invoice_id=doc["invoice_id"])
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="payment_voided_manual", entity_type="invoice", entity_id=doc["invoice_id"],
        summary=f"Manual payment voided (${doc['amount_cents'] / 100:,.2f})",
        diff={"payment_id": payment_id, "reason": reason},
    )
    updated = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    return serialize_doc(updated)


# ---------------- Stripe payments ----------------


async def initiate_stripe(
    *,
    tenant_id: str,
    invoice_id: str,
    amount_cents: int,
    actor_user_id: str,
    actor_email: str,
    idempotency_key: Optional[str] = None,
) -> dict[str, Any]:
    inv, balance = await _invoice_balance(tenant_id, invoice_id)
    if inv.get("document_status") == "void":
        raise ValueError("invoice_void")
    if amount_cents <= 0 or amount_cents > balance:
        raise ValueError("overpayment_rejected")

    ikey = idempotency_key or f"pi:{invoice_id}:{amount_cents}:{uuid.uuid4().hex}"

    # Return existing pending row if we already initiated this exact amount + ikey.
    existing = await db.payments.find_one(
        {"tenant_id": tenant_id, "invoice_id": invoice_id,
         "source": "stripe", "idempotency_key": ikey},
        {"_id": 0},
    )
    if existing:
        return {
            "payment_id": existing["id"],
            "client_secret": existing.get("stripe_client_secret"),
            "status": existing.get("status"),
            "already_exists": True,
        }

    pay = Payment(
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        customer_id=inv["customer_id"],
        order_id=inv.get("order_id"),
        source="stripe",
        status="pending",
        amount_cents=amount_cents,
        idempotency_key=ikey,
        created_by=actor_user_id,
    )
    doc = prepare_for_mongo(pay.model_dump())
    await db.payments.insert_one(doc)

    # Actually call Stripe.
    if not stripe_core.is_enabled():
        # Fail-closed for production; test mode may still proceed if key configured
        # via patched stripe_core.is_enabled(). Delete the pending row and bail.
        await db.payments.delete_one({"id": pay.id})
        raise ValueError("stripe_disabled")
    intent = stripe_core.create_payment_intent(
        amount_cents=amount_cents,
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        internal_payment_id=pay.id,
        idempotency_key=ikey,
    )
    await db.payments.update_one(
        {"id": pay.id},
        {"$set": {
            "stripe_payment_intent_id": intent["id"],
            "stripe_client_secret": intent["client_secret"],
            "updated_at": utc_now().isoformat(),
        }},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="payment_initiated_stripe", entity_type="invoice", entity_id=invoice_id,
        summary=f"Stripe payment initiated (${amount_cents / 100:,.2f})",
        diff={"payment_id": pay.id, "payment_intent_id": intent["id"]},
    )
    return {
        "payment_id": pay.id,
        "client_secret": intent["client_secret"],
        "status": "pending",
        "publishable_key": stripe_core.publishable_key(),
        "already_exists": False,
    }


async def confirm_stripe_from_webhook(
    *,
    payment_intent_id: str,
    provider_event_id: str,
    charge_id: Optional[str] = None,
) -> None:
    doc = await db.payments.find_one({"stripe_payment_intent_id": payment_intent_id})
    if not doc:
        return
    if doc.get("status") == "confirmed":
        return
    await db.payments.update_one(
        {"id": doc["id"]},
        {"$set": {
            "status": "confirmed",
            "stripe_charge_id": charge_id,
            "provider_event_id": provider_event_id,
            "confirmed_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }},
    )
    await reconcile(tenant_id=doc["tenant_id"], invoice_id=doc["invoice_id"])
    await record_audit(
        tenant_id=doc["tenant_id"], actor_user_id="webhook", actor_email="stripe",
        action="payment_confirmed_stripe", entity_type="invoice", entity_id=doc["invoice_id"],
        summary=f"Stripe payment confirmed (${doc['amount_cents'] / 100:,.2f})",
        diff={"payment_id": doc["id"], "provider_event_id": provider_event_id},
    )


async def fail_stripe_from_webhook(
    *,
    payment_intent_id: str,
    provider_event_id: str,
    reason: Optional[str] = None,
    canceled: bool = False,
) -> None:
    doc = await db.payments.find_one({"stripe_payment_intent_id": payment_intent_id})
    if not doc or doc.get("status") in {"confirmed", "voided"}:
        return
    new_status = "voided" if canceled else "failed"
    now = utc_now().isoformat()
    updates = {
        "status": new_status,
        "provider_event_id": provider_event_id,
        "updated_at": now,
    }
    if canceled:
        updates["voided_at"] = now
        updates["void_reason"] = "stripe:canceled"
    else:
        updates["failed_at"] = now
        updates["failure_reason"] = reason
    await db.payments.update_one({"id": doc["id"]}, {"$set": updates})
    await reconcile(tenant_id=doc["tenant_id"], invoice_id=doc["invoice_id"])
    await record_audit(
        tenant_id=doc["tenant_id"], actor_user_id="webhook", actor_email="stripe",
        action="payment_failed_stripe" if not canceled else "payment_voided_stripe",
        entity_type="invoice", entity_id=doc["invoice_id"],
        summary=f"Stripe payment {new_status}",
        diff={"payment_id": doc["id"], "reason": reason, "provider_event_id": provider_event_id},
    )


# ---------------- Refunds ----------------


async def initiate_refund(
    *,
    tenant_id: str,
    payment_id: str,
    amount_cents: Optional[int],
    reason: str,
    actor_user_id: str,
    actor_email: str,
) -> dict:
    src = await db.payments.find_one({"id": payment_id, "tenant_id": tenant_id})
    if not src:
        raise ValueError("payment_not_found")
    if src.get("source") != "stripe":
        raise ValueError("only_stripe_payments_can_be_refunded")
    if src.get("status") != "confirmed":
        raise ValueError("payment_not_refundable")
    if not reason or not reason.strip():
        raise ValueError("refund_reason_required")

    refundable = int(src["amount_cents"])  # net after prior refunds → future TODO
    if amount_cents is None:
        amount_cents = refundable
    if amount_cents <= 0 or amount_cents > refundable:
        raise ValueError("refund_amount_invalid")

    ikey = f"rf:{payment_id}:{amount_cents}:{uuid.uuid4().hex[:8]}"
    result = stripe_core.create_refund(
        payment_intent_id=src["stripe_payment_intent_id"],
        amount_cents=amount_cents,
        reason=reason,
        idempotency_key=ikey,
    )

    refund_row = Payment(
        tenant_id=tenant_id,
        invoice_id=src["invoice_id"],
        customer_id=src["customer_id"],
        order_id=src.get("order_id"),
        source="stripe",
        status="pending",  # webhook `charge.refunded` will flip to confirmed
        amount_cents=amount_cents,
        stripe_refund_id=result["id"],
        refund_of_payment_id=payment_id,
        refund_reason=reason.strip(),
        idempotency_key=ikey,
        created_by=actor_user_id,
    )
    await db.payments.insert_one(prepare_for_mongo(refund_row.model_dump()))
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="refund_initiated", entity_type="invoice", entity_id=src["invoice_id"],
        summary=f"Refund initiated (${amount_cents / 100:,.2f}) for payment {payment_id}",
        diff={"refund_id": refund_row.id, "stripe_refund_id": result["id"], "reason": reason},
    )
    return serialize_doc(refund_row.model_dump())


async def confirm_refund_from_webhook(*, stripe_refund_id: str, provider_event_id: str) -> None:
    doc = await db.payments.find_one({"stripe_refund_id": stripe_refund_id})
    if not doc or doc.get("status") == "confirmed":
        return
    now = utc_now().isoformat()
    await db.payments.update_one(
        {"id": doc["id"]},
        {"$set": {
            "status": "confirmed",
            "provider_event_id": provider_event_id,
            "confirmed_at": now,
            "refunded_at": now,
            "updated_at": now,
        }},
    )
    # Update the parent payment's own status marker.
    if doc.get("refund_of_payment_id"):
        parent = await db.payments.find_one({"id": doc["refund_of_payment_id"]})
        if parent:
            parent_amt = int(parent.get("amount_cents") or 0)
            refunded_total = 0
            async for r in db.payments.find({"refund_of_payment_id": parent["id"], "status": "confirmed"}):
                refunded_total += int(r.get("amount_cents") or 0)
            parent_status = "refunded" if refunded_total >= parent_amt else "partially_refunded"
            await db.payments.update_one(
                {"id": parent["id"]}, {"$set": {"status": parent_status, "updated_at": now}}
            )
    await reconcile(tenant_id=doc["tenant_id"], invoice_id=doc["invoice_id"])
