"""EC4 â€” Payment service.

Business logic for manual + Stripe payments, void, refund. Routers stay thin
and only handle HTTP concerns.
"""
from __future__ import annotations

import uuid
import asyncio
from typing import Any, Optional

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.payment import Payment
from . import stripe_core
from .audit import record_audit
from .invoice_reconciliation import reconcile
from .sequence import next_record_number
from .webstore_payment_provider import ProviderRefund


async def _invoice_balance(tenant_id: str, invoice_id: str) -> tuple[dict, int]:
    inv = await db.invoices.find_one({"id": invoice_id, "tenant_id": tenant_id})
    if not inv:
        raise ValueError("invoice_not_found")
    # Older invoice documents may not have the EC4 derived fields yet. Bring
    # those records forward once; current payment writes maintain the fields
    # with the atomic guard below so a concurrent reconcile cannot reopen the
    # read/check/write race.
    if "balance_due_cents" not in inv or "amount_paid_cents" not in inv:
        await reconcile(tenant_id=tenant_id, invoice_id=invoice_id)
        inv = await db.invoices.find_one({"id": invoice_id, "tenant_id": tenant_id})
    return inv, int(inv.get("balance_due_cents") or 0)


async def _apply_invoice_payment_guard(*, tenant_id: str, invoice_id: str, amount_cents: int) -> Optional[dict]:
    """Atomically apply a payment only while the invoice can still collect it."""
    now = utc_now().isoformat()
    return await db.invoices.find_one_and_update(
        {
            "id": invoice_id,
            "tenant_id": tenant_id,
            "balance_due_cents": {"$gte": amount_cents},
            "document_status": {"$ne": "void"},
            "status": {"$ne": "void"},
        },
        [
            {
                "$set": {
                    "amount_paid_cents": {"$add": [{"$ifNull": ["$amount_paid_cents", 0]}, amount_cents]},
                    "balance_due_cents": {"$subtract": [{"$ifNull": ["$balance_due_cents", 0]}, amount_cents]},
                    "updated_at": now,
                }
            },
            {
                "$set": {
                    "financial_status": {
                        "$cond": [
                            {"$lte": ["$balance_due_cents", 0]},
                            "paid",
                            "partial",
                        ]
                    }
                }
            },
        ],
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER,
    )


async def _mark_payment_failed(payment_id: str, tenant_id: str, reason: str) -> None:
    now = utc_now().isoformat()
    await db.payments.update_one(
        {"id": payment_id, "tenant_id": tenant_id, "status": "pending"},
        {
            "$set": {
                "status": "failed",
                "failed_at": now,
                "failure_reason": reason,
                "updated_at": now,
            },
            "$unset": {"confirmation_claim_id": "", "confirmation_claimed_at": ""},
        },
    )


async def _rollback_invoice_payment_guard(*, tenant_id: str, invoice_id: str, amount_cents: int) -> None:
    """Undo a guard reservation when the corresponding payment write fails."""
    result = await db.invoices.update_one(
        {
            "id": invoice_id,
            "tenant_id": tenant_id,
            "$expr": {
                "$gte": [{"$ifNull": ["$amount_paid_cents", 0]}, amount_cents]
            },
        },
        {
            "$inc": {"amount_paid_cents": -amount_cents, "balance_due_cents": amount_cents},
            "$set": {"updated_at": utc_now().isoformat()},
        },
    )
    if result.modified_count != 1:
        raise RuntimeError("invoice_guard_rollback_failed")
    await reconcile(tenant_id=tenant_id, invoice_id=invoice_id)


async def _finalize_pending_payment(
    *, payment_id: str, tenant_id: str, updates: dict[str, Any], claim_id: Optional[str] = None
) -> bool:
    payment_filter: dict[str, Any] = {"id": payment_id, "tenant_id": tenant_id, "status": "pending"}
    if claim_id:
        payment_filter["confirmation_claim_id"] = claim_id
    result = await db.payments.update_one(
        payment_filter,
        {"$set": updates, "$unset": {"confirmation_claim_id": "", "confirmation_claimed_at": ""}},
    )
    return result.modified_count == 1


async def _release_payment_claim(*, payment_id: str, tenant_id: str, claim_id: str) -> None:
    await db.payments.update_one(
        {"id": payment_id, "tenant_id": tenant_id, "confirmation_claim_id": claim_id},
        {"$unset": {"confirmation_claim_id": "", "confirmation_claimed_at": ""}},
    )


async def _settle_idempotent_payment(payment: dict) -> dict:
    """Avoid returning a transient pending row for a concurrent replay."""
    if payment.get("status") != "pending":
        return payment
    for _ in range(20):
        await asyncio.sleep(0.01)
        current = await db.payments.find_one({"id": payment["id"], "tenant_id": payment["tenant_id"]}, {"_id": 0})
        if current and current.get("status") != "pending":
            return current
    return payment


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
            return serialize_doc(await _settle_idempotent_payment(prev)), True

    if amount_cents <= 0:
        raise ValueError("amount_must_be_positive")
    if amount_cents > balance:
        raise ValueError("overpayment_rejected")

    pay = Payment(
        tenant_id=tenant_id,
        record_number_type="payment",
        invoice_id=invoice_id,
        customer_id=inv["customer_id"],
        order_id=inv.get("order_id"),
        source="manual",
        status="pending",
        amount_cents=amount_cents,
        method=method,  # type: ignore[arg-type]
        paid_on=paid_on,
        reference=reference,
        notes=notes,
        idempotency_key=idempotency_key,
        created_by=actor_user_id,
    )
    allocation = await next_record_number(
        tenant_id=tenant_id,
        record_type="payment",
        idempotency_key=idempotency_key,
        issued_to_entity_type="payment",
        issued_to_entity_id=pay.id,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        reason="payment.record_manual",
        context={"invoice_id": invoice_id},
    )
    pay.number = allocation.number
    try:
        await db.payments.insert_one(prepare_for_mongo(pay.model_dump()))
    except DuplicateKeyError:
        prev = await db.payments.find_one(
            {"tenant_id": tenant_id, "invoice_id": invoice_id, "idempotency_key": idempotency_key},
            {"_id": 0},
        )
        if prev:
            return serialize_doc(await _settle_idempotent_payment(prev)), True
        raise

    guarded_invoice = await _apply_invoice_payment_guard(
        tenant_id=tenant_id, invoice_id=invoice_id, amount_cents=amount_cents
    )
    if not guarded_invoice:
        current_invoice = await db.invoices.find_one({"id": invoice_id, "tenant_id": tenant_id}, {"_id": 0})
        reason = "invoice_void" if current_invoice and (
            current_invoice.get("document_status") == "void" or current_invoice.get("status") == "void"
        ) else "overpayment_rejected"
        await _mark_payment_failed(pay.id, tenant_id, reason)
        if reason == "invoice_void":
            raise ValueError(reason)
        raise ValueError("overpayment_rejected")

    try:
        finalized = await _finalize_pending_payment(
            payment_id=pay.id,
            tenant_id=tenant_id,
            updates={"status": "confirmed", "confirmed_at": utc_now().isoformat(), "updated_at": utc_now().isoformat()},
        )
        if not finalized:
            raise RuntimeError("payment_persistence_failed")
    except Exception as exc:  # noqa: BLE001 - compensate the prior invoice guard before surfacing failure
        await _rollback_invoice_payment_guard(
            tenant_id=tenant_id, invoice_id=invoice_id, amount_cents=amount_cents
        )
        await _mark_payment_failed(pay.id, tenant_id, "payment_persistence_failed")
        if isinstance(exc, RuntimeError) and str(exc) == "invoice_guard_rollback_failed":
            raise
        raise ValueError("payment_persistence_failed") from exc
    pay_doc = await db.payments.find_one({"id": pay.id, "tenant_id": tenant_id}, {"_id": 0})

    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="payment_recorded_manual", entity_type="invoice", entity_id=invoice_id,
        summary=f"Manual payment ${amount_cents / 100:,.2f} recorded",
        diff={"payment_id": pay.id, "amount_cents": amount_cents, "method": method},
    )
    return serialize_doc(pay_doc or pay.model_dump()), False


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
        {"id": payment_id, "tenant_id": tenant_id},
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
    updated = await db.payments.find_one({"id": payment_id, "tenant_id": tenant_id}, {"_id": 0})
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

    # Server-side dedup: if a pending Stripe payment for this invoice + amount
    # already exists, reuse it. Protects against dialog re-open creating dupes.
    existing_pending = await db.payments.find_one(
        {
            "tenant_id": tenant_id, "invoice_id": invoice_id,
            "source": "stripe", "status": "pending",
            "amount_cents": amount_cents,
        },
        {"_id": 0},
    )
    if existing_pending:
        return {
            "payment_id": existing_pending["id"],
            "client_secret": existing_pending.get("stripe_client_secret"),
            "status": "pending",
            "publishable_key": stripe_core.publishable_key(),
            "already_exists": True,
        }

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
        record_number_type="payment",
        invoice_id=invoice_id,
        customer_id=inv["customer_id"],
        order_id=inv.get("order_id"),
        source="stripe",
        status="pending",
        amount_cents=amount_cents,
        idempotency_key=ikey,
        created_by=actor_user_id,
    )
    allocation = await next_record_number(
        tenant_id=tenant_id,
        record_type="payment",
        idempotency_key=ikey,
        issued_to_entity_type="payment",
        issued_to_entity_id=pay.id,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        reason="payment.initiate_stripe",
        context={"invoice_id": invoice_id},
    )
    pay.number = allocation.number
    doc = prepare_for_mongo(pay.model_dump())
    await db.payments.insert_one(doc)

    # Actually call Stripe.
    if not stripe_core.is_enabled():
        # Fail-closed for production; test mode may still proceed if key configured
        # via patched stripe_core.is_enabled(). Delete the pending row and bail.
        await db.payments.delete_one({"id": pay.id, "tenant_id": tenant_id})
        raise ValueError("stripe_disabled")
    intent = stripe_core.create_payment_intent(
        amount_cents=amount_cents,
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        internal_payment_id=pay.id,
        idempotency_key=ikey,
    ) if False else None
    try:
        intent = stripe_core.create_payment_intent(
            amount_cents=amount_cents,
            tenant_id=tenant_id,
            invoice_id=invoice_id,
            internal_payment_id=pay.id,
            idempotency_key=ikey,
        )
    except Exception as ex:  # noqa: BLE001
        import stripe as _stripe
        await db.payments.delete_one({"id": pay.id, "tenant_id": tenant_id})
        if isinstance(ex, _stripe.error.StripeError):
            raise ValueError(f"stripe_error:{getattr(ex, 'user_message', None) or str(ex)}")
        raise
    await db.payments.update_one(
        {"id": pay.id, "tenant_id": tenant_id},
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
    dev_simulated: bool = False,
) -> None:
    doc = await db.payments.find_one({"stripe_payment_intent_id": payment_intent_id})
    if not doc:
        return
    if doc.get("status") in {"confirmed", "failed", "voided"}:
        return
    claim_id = uuid.uuid4().hex
    claim_now = utc_now().isoformat()
    claimed = await db.payments.update_one(
        {
            "id": doc["id"],
            "tenant_id": doc["tenant_id"],
            "status": "pending",
            "confirmation_claim_id": {"$exists": False},
        },
        {"$set": {"confirmation_claim_id": claim_id, "confirmation_claimed_at": claim_now}},
    )
    if claimed.modified_count != 1:
        # Another delivery is already settling this payment. Its eventual
        # state is authoritative; do not apply the invoice amount twice.
        return

    guarded_invoice = await _apply_invoice_payment_guard(
        tenant_id=doc["tenant_id"], invoice_id=doc["invoice_id"], amount_cents=int(doc["amount_cents"])
    )
    if not guarded_invoice:
        current_invoice = await db.invoices.find_one(
            {"id": doc["invoice_id"], "tenant_id": doc["tenant_id"]}, {"_id": 0}
        )
        reason = "invoice_void" if current_invoice and (
            current_invoice.get("document_status") == "void" or current_invoice.get("status") == "void"
        ) else "overpayment_rejected"
        await _mark_payment_failed(doc["id"], doc["tenant_id"], reason)
        await record_audit(
            tenant_id=doc["tenant_id"], actor_user_id="webhook", actor_email="stripe",
            action="payment_rejected_stripe", entity_type="invoice", entity_id=doc["invoice_id"],
            summary="Stripe payment rejected because the invoice balance was no longer available",
            diff={"payment_id": doc["id"], "provider_event_id": provider_event_id, "reason": reason},
        )
        return
    updates: dict[str, Any] = {
        "status": "confirmed",
        "stripe_charge_id": charge_id,
        "provider_event_id": provider_event_id,
        "confirmed_at": utc_now().isoformat(),
        "updated_at": utc_now().isoformat(),
    }
    if dev_simulated:
        updates["dev_simulated"] = True
    try:
        finalized = await _finalize_pending_payment(
            payment_id=doc["id"], tenant_id=doc["tenant_id"], updates=updates, claim_id=claim_id
        )
        if not finalized:
            raise RuntimeError("payment_confirmation_persistence_failed")
    except Exception as exc:  # noqa: BLE001 - compensate and make the provider event retryable
        await _rollback_invoice_payment_guard(
            tenant_id=doc["tenant_id"], invoice_id=doc["invoice_id"], amount_cents=int(doc["amount_cents"])
        )
        await _release_payment_claim(payment_id=doc["id"], tenant_id=doc["tenant_id"], claim_id=claim_id)
        if isinstance(exc, RuntimeError) and str(exc) == "invoice_guard_rollback_failed":
            raise
        raise RuntimeError("payment_confirmation_persistence_failed") from exc
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
    await db.payments.update_one({"id": doc["id"], "tenant_id": doc["tenant_id"]}, {"$set": updates})
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
    idempotency_key: Optional[str] = None,
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

    if idempotency_key:
        existing = await db.payments.find_one(
            {"tenant_id": tenant_id, "refund_of_payment_id": payment_id, "idempotency_key": idempotency_key},
            {"_id": 0},
        )
        if existing:
            return serialize_doc(existing)

    prior_refunded = 0
    async for refund in db.payments.find(
        {
            "tenant_id": tenant_id,
            "refund_of_payment_id": payment_id,
            "status": {"$in": ["pending", "confirmed"]},
        },
        {"_id": 0, "amount_cents": 1},
    ):
        prior_refunded += int(refund.get("amount_cents") or 0)
    refundable = int(src["amount_cents"]) - prior_refunded
    if amount_cents is None:
        amount_cents = refundable
    if amount_cents <= 0 or amount_cents > refundable:
        raise ValueError("refund_amount_invalid")

    ikey = idempotency_key or f"rf:{payment_id}:{amount_cents}:{uuid.uuid4().hex[:8]}"
    # Dev-simulated payments never touched real Stripe â†’ short-circuit refund too.
    from ..core.config import get_settings
    dev_simulated_source = bool(src.get("dev_simulated")) and get_settings().auth_dev_bypass
    try:
        if dev_simulated_source:
            result = {
                "id": f"re_dev_{uuid.uuid4().hex[:20]}",
                "status": "pending",
                "amount": int(amount_cents),
            }
        else:
            result = stripe_core.create_refund(
                payment_intent_id=src["stripe_payment_intent_id"],
                amount_cents=amount_cents,
                reason=reason,
                idempotency_key=ikey,
            )
    except Exception as ex:  # noqa: BLE001 â€” catch stripe.error.StripeError family
        import stripe as _stripe
        if isinstance(ex, _stripe.error.StripeError):
            raise ValueError(f"stripe_error:{getattr(ex, 'user_message', None) or str(ex)}")
        raise

    refund_row = Payment(
        tenant_id=tenant_id,
        record_number_type="refund",
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
    allocation = await next_record_number(
        tenant_id=tenant_id,
        record_type="refund",
        idempotency_key=ikey,
        issued_to_entity_type="payment",
        issued_to_entity_id=refund_row.id,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        reason="payment.initiate_refund",
        context={"source_payment_id": payment_id, "invoice_id": src["invoice_id"]},
    )
    refund_row.number = allocation.number
    try:
        await db.payments.insert_one(prepare_for_mongo(refund_row.model_dump()))
    except DuplicateKeyError:
        if idempotency_key:
            existing = await db.payments.find_one(
                {"tenant_id": tenant_id, "refund_of_payment_id": payment_id, "idempotency_key": idempotency_key},
                {"_id": 0},
            )
            if existing:
                return serialize_doc(existing)
        raise
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="refund_initiated", entity_type="invoice", entity_id=src["invoice_id"],
        summary=f"Refund initiated (${amount_cents / 100:,.2f}) for payment {payment_id}",
        diff={"refund_id": refund_row.id, "stripe_refund_id": result["id"], "reason": reason},
    )
    return serialize_doc(refund_row.model_dump())


async def record_provider_refund(
    *,
    tenant_id: str,
    payment_id: str,
    provider_refund: ProviderRefund,
    reason: str,
    actor_user_id: str,
    actor_email: str,
) -> dict:
    """Record a refund after a Webstore provider has already approved it.

    This is deliberately separate from ``initiate_refund``. EC4 owns the
    canonical Payment record, while the Webstore provider boundary owns the
    external refund operation and supplies the reconciled reference.
    """
    src = await db.payments.find_one({"id": payment_id, "tenant_id": tenant_id})
    if not src:
        raise ValueError("payment_not_found")
    if src.get("source") != "stripe":
        raise ValueError("only_stripe_payments_can_be_refunded")
    if src.get("status") not in {"confirmed", "partially_refunded"}:
        raise ValueError("payment_not_refundable")
    if not reason or not reason.strip():
        raise ValueError("refund_reason_required")
    if provider_refund.provider_payment_reference != src.get("stripe_payment_intent_id"):
        raise ValueError("provider_payment_reference_mismatch")
    if provider_refund.currency != str(src.get("currency") or "usd").lower():
        raise ValueError("provider_refund_currency_mismatch")
    if provider_refund.amount_cents <= 0:
        raise ValueError("refund_amount_invalid")

    existing = await db.payments.find_one(
        {"tenant_id": tenant_id, "refund_of_payment_id": payment_id, "idempotency_key": provider_refund.idempotency_key},
        {"_id": 0},
    )
    if existing:
        return serialize_doc(existing)

    prior_refunded = 0
    async for refund in db.payments.find(
        {"tenant_id": tenant_id, "refund_of_payment_id": payment_id, "status": {"$in": ["pending", "confirmed"]}},
        {"_id": 0, "amount_cents": 1},
    ):
        prior_refunded += int(refund.get("amount_cents") or 0)
    if provider_refund.amount_cents > int(src.get("amount_cents") or 0) - prior_refunded:
        raise ValueError("refund_amount_invalid")

    refund_row = Payment(
        tenant_id=tenant_id,
        record_number_type="refund",
        invoice_id=src["invoice_id"],
        customer_id=src["customer_id"],
        order_id=src.get("order_id"),
        source="stripe",
        status="pending",
        amount_cents=provider_refund.amount_cents,
        currency=provider_refund.currency,
        stripe_refund_id=provider_refund.provider_refund_reference,
        refund_of_payment_id=payment_id,
        refund_reason=reason.strip(),
        idempotency_key=provider_refund.idempotency_key,
        created_by=actor_user_id,
    )
    allocation = await next_record_number(
        tenant_id=tenant_id,
        record_type="refund",
        idempotency_key=provider_refund.idempotency_key,
        issued_to_entity_type="payment",
        issued_to_entity_id=refund_row.id,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        reason="payment.record_provider_refund",
        context={"source_payment_id": payment_id, "provider_refund_reference": provider_refund.provider_refund_reference},
    )
    refund_row.number = allocation.number
    try:
        await db.payments.insert_one(prepare_for_mongo(refund_row.model_dump()))
    except DuplicateKeyError:
        existing = await db.payments.find_one(
            {"tenant_id": tenant_id, "refund_of_payment_id": payment_id, "idempotency_key": provider_refund.idempotency_key},
            {"_id": 0},
        )
        if existing:
            return serialize_doc(existing)
        raise
    await record_audit(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        action="refund_recorded_provider_authority",
        entity_type="invoice",
        entity_id=src["invoice_id"],
        summary=f"Provider-authorized refund recorded (${provider_refund.amount_cents / 100:,.2f})",
        diff={
            "refund_id": refund_row.id,
            "provider_refund_reference": provider_refund.provider_refund_reference,
            "provider_event_status": provider_refund.status,
        },
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
