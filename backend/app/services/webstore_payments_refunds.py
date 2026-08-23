"""Refund initiation and provider refund reconciliation for Webstores."""
from __future__ import annotations

from typing import Any, Optional

from pymongo import ReturnDocument

from ..core.config import get_settings
from ..core.db import db
from ..core.time_utils import serialize_doc
from ..models.webstore import WebstoreLedgerEntry
from .webstore_context import WebstoreError
from .webstore_payment_provider import (
    PAYMENT_PROVIDER_NOT_CONFIGURED,
    ProviderAuthority,
    ProviderRefund,
    get_webstore_payment_provider,
    provider_configuration_status,
    refund_from_provider_result,
)
from .webstore_payments_core import _event_key, _existing_event, _now_iso, _require_provider_authority
from .webstore_payments_ledger import _insert_ledger_entry
from .webstore_shared import _audit

async def initiate_webstore_refund(
    *,
    tenant_id: str,
    webstore_id: str,
    payment_id: str,
    amount_cents: Optional[int],
    reason: str,
    actor_user_id: str,
    actor_email: str,
    idempotency_key: Optional[str] = None,
    provider=None,
    provider_authority: Optional[ProviderAuthority] = None,
) -> dict:
    _require_provider_authority(provider_authority)
    intent = await db.webstore_purchase_intents.find_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "canonical_payment_id": payment_id},
        {"_id": 0},
    )
    if not intent:
        raise WebstoreError("webstore_payment_not_found", "Webstore payment not found", 404)

    source_payment = await db.payments.find_one({"tenant_id": tenant_id, "id": payment_id}, {"_id": 0})
    if not source_payment or source_payment.get("source") != "stripe":
        raise WebstoreError("payment_not_refundable", "Webstore payment is not refundable", 409)
    if source_payment.get("status") not in {"confirmed", "partially_refunded"}:
        raise WebstoreError("payment_not_refundable", "Webstore payment is not refundable", 409)
    refund_amount = amount_cents
    if refund_amount is None:
        refund_amount = int(source_payment.get("amount_cents") or 0)
    provider_impl = provider or get_webstore_payment_provider(get_settings())
    provider_result = await provider_impl.create_refund(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        purchase_intent_id=intent["id"],
        provider_payment_reference=source_payment.get("stripe_payment_intent_id"),
        amount_cents=refund_amount,
        currency=str(source_payment.get("currency") or "usd").lower(),
        reason=reason,
        idempotency_key=idempotency_key or f"webstore-refund:{payment_id}:{refund_amount}",
        provider_authority=provider_authority,
    )
    if not provider_result.ok:
        code = "payment_provider_not_configured" if provider_result.code == PAYMENT_PROVIDER_NOT_CONFIGURED else "payment_provider_refund_failed"
        raise WebstoreError(code, provider_result.message, 503)
    try:
        provider_refund = refund_from_provider_result(provider_result)
    except (KeyError, TypeError, ValueError) as exc:
        raise WebstoreError("provider_refund_invalid", "Provider refund result failed reconciliation", 502) from exc
    if provider_refund.provider_payment_reference != source_payment.get("stripe_payment_intent_id"):
        raise WebstoreError("provider_refund_mismatch", "Provider refund does not match the canonical Payment", 409)
    if provider_authority is not None and (
        provider_refund.provider != provider_authority.provider
        or provider_refund.provider_mode != provider_authority.mode
        or provider_refund.provider_account_reference != provider_authority.account_reference
    ):
        raise WebstoreError("provider_refund_authority_mismatch", "Provider refund does not match provider authority", 409)
    if provider_refund.amount_cents != refund_amount:
        raise WebstoreError("provider_refund_amount_mismatch", "Provider refund amount does not match the requested amount", 409)
    requested_idempotency_key = idempotency_key or f"webstore-refund:{payment_id}:{refund_amount}"
    if provider_refund.idempotency_key != requested_idempotency_key:
        raise WebstoreError("provider_refund_idempotency_mismatch", "Provider refund does not match the requested idempotency key", 409)

    try:
        from .payment_service import record_provider_refund

        refund = await record_provider_refund(
            tenant_id=tenant_id,
            payment_id=payment_id,
            provider_refund=provider_refund,
            reason=reason,
            actor_user_id=actor_user_id,
            actor_email=actor_email,
        )
    except ValueError as exc:
        raise WebstoreError(str(exc), str(exc), 400) from exc

    entry = WebstoreLedgerEntry(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        buyer_order_id=intent["id"],
        entry_type="refund",
        amount_cents=-int(refund.get("amount_cents") or 0),
        basis_amount_cents=int(intent.get("total_cents") or 0),
        source_type="canonical_refund_payment",
        source_id=refund["id"],
        notes=reason.strip(),
    ).model_dump()
    await _insert_ledger_entry(entry)

    refunded_total = 0
    async for row in db.payments.find(
        {"tenant_id": tenant_id, "refund_of_payment_id": payment_id, "status": {"$in": ["pending", "confirmed"]}},
        {"_id": 0, "amount_cents": 1},
    ):
        refunded_total += int(row.get("amount_cents") or 0)
    total = int(intent.get("total_cents") or 0)
    refund_status = "refunded" if refunded_total >= total else "partially_refunded"
    await db.webstore_purchase_intents.update_one(
        {"tenant_id": tenant_id, "id": intent["id"]},
        {"$set": {"refund_status": refund_status, "status": refund_status, "updated_at": _now_iso()}},
    )
    await _audit(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=actor_user_id,
        actor_email=actor_email,
        action="webstore.refund_recorded",
        entity_type="payment",
        entity_id=refund["id"],
        summary="Webstore refund recorded through provider-authorized canonical Payment service",
        metadata={"source_payment_id": payment_id, "amount_cents": refund.get("amount_cents"), "refund_status": refund_status, "provider_refund_reference": provider_refund.provider_refund_reference},
    )
    ledger = await db.webstore_ledger_entries.find_one({"tenant_id": tenant_id, "source_type": "canonical_refund_payment", "source_id": refund["id"]}, {"_id": 0})
    return {"refund": refund, "ledger_entry": serialize_doc(ledger), "refund_status": refund_status}


async def reconcile_webstore_refund_event(
    *,
    tenant_id: str,
    webstore_id: str,
    provider_result,
    provider_authority: Optional[ProviderAuthority] = None,
) -> dict:
    """Reconcile a signed Stripe refund without creating new commerce graphs."""
    _require_provider_authority(provider_authority)
    data = dict(provider_result.data or {}) if getattr(provider_result, "ok", False) else {}
    status = str(data.get("status") or "").lower()
    provider = str(data.get("provider") or "").strip().lower()
    provider_mode = str(data.get("provider_mode") or "").strip().lower()
    provider_event_id = str(data.get("provider_event_id") or "").strip()
    refund_reference = str(data.get("provider_refund_reference") or "").strip()
    payment_reference = str(data.get("provider_payment_reference") or "").strip()
    result_tenant_id = str(data.get("tenant_id") or "").strip()
    result_webstore_id = str(data.get("webstore_id") or "").strip()
    provider_account_reference = data.get("provider_account_reference")
    if (
        not all([provider, provider_mode, provider_event_id, refund_reference, payment_reference, result_tenant_id, result_webstore_id])
        or result_tenant_id != tenant_id
        or result_webstore_id != webstore_id
        or provider_mode not in {"test", "live"}
        or int(data.get("amount_cents") or 0) <= 0
        or not str(data.get("currency") or "").strip()
    ):
        raise WebstoreError("provider_refund_invalid", "Provider refund event is incomplete", 400)
    if provider_authority is not None and (
        provider != provider_authority.provider
        or provider_mode != provider_authority.mode
        or provider_account_reference != provider_authority.account_reference
    ):
        raise WebstoreError("provider_refund_authority_mismatch", "Provider refund does not match provider authority", 409)
    if status in {"failed", "canceled"}:
        existing_failure = await db.webstore_activity_events.find_one(
            {
                "tenant_id": tenant_id,
                "webstore_id": webstore_id,
                "action": "webstore.refund_failed",
                "entity_id": refund_reference,
            },
            {"_id": 0},
        )
        if existing_failure:
            return {"accepted": True, "refund_status": status, "already_processed": True}
        await _audit(
            tenant_id=tenant_id,
            webstore_id=webstore_id,
            actor_type="provider",
            actor_id="stripe",
            actor_email="stripe",
            action="webstore.refund_failed",
            entity_type="provider_refund",
            entity_id=refund_reference,
            summary="Provider refund failed; no refund or ledger record was created",
            metadata={
                "provider_event_id": provider_event_id,
                "provider_payment_reference": payment_reference,
                "provider_account_reference": provider_account_reference,
                "status": status,
                "raw_event_snapshot": data.get("raw_event_snapshot") or {},
            },
        )
        return {"accepted": True, "refund_status": status, "already_processed": False}
    try:
        provider_refund = refund_from_provider_result(provider_result)
    except (KeyError, TypeError, ValueError) as exc:
        raise WebstoreError("provider_refund_invalid", "Provider refund result failed reconciliation", 502) from exc
    intent = await db.webstore_purchase_intents.find_one(
        {
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "provider_payment_id": payment_reference,
        },
        {"_id": 0},
    )
    if not intent or not intent.get("canonical_payment_id"):
        raise WebstoreError("paid_purchase_intent_required", "A canonical paid Webstore payment is required for refund reconciliation", 409)
    source_payment = await db.payments.find_one(
        {"tenant_id": tenant_id, "id": intent["canonical_payment_id"], "stripe_payment_intent_id": payment_reference},
        {"_id": 0},
    )
    if not source_payment:
        raise WebstoreError("webstore_payment_not_found", "Canonical Webstore payment was not found", 404)
    existing_refund = await db.payments.find_one(
        {"tenant_id": tenant_id, "stripe_refund_id": refund_reference},
        {"_id": 0},
    )
    if existing_refund:
        refund = existing_refund
    else:
        try:
            from .payment_service import record_provider_refund

            refund = await record_provider_refund(
                tenant_id=tenant_id,
                payment_id=source_payment["id"],
                provider_refund=provider_refund,
                reason="Provider-confirmed Webstore refund",
                actor_user_id="stripe-webhook",
                actor_email="stripe-webhook",
            )
        except ValueError as exc:
            raise WebstoreError(str(exc), str(exc), 409) from exc
    if status in {"succeeded", "confirmed"}:
        from .payment_service import confirm_refund_from_webhook

        await confirm_refund_from_webhook(
            stripe_refund_id=refund_reference,
            provider_event_id=str(data.get("provider_event_id") or refund_reference),
        )
        refund = await db.payments.find_one({"tenant_id": tenant_id, "id": refund["id"]}, {"_id": 0}) or refund
    ledger = await db.webstore_ledger_entries.find_one(
        {"tenant_id": tenant_id, "source_type": "canonical_refund_payment", "source_id": refund["id"]},
        {"_id": 0},
    )
    ledger_was_existing = bool(ledger)
    if not ledger:
        ledger = WebstoreLedgerEntry(
            tenant_id=tenant_id,
            webstore_id=webstore_id,
            buyer_order_id=intent["id"],
            entry_type="refund",
            amount_cents=-int(refund.get("amount_cents") or 0),
            basis_amount_cents=int(intent.get("total_cents") or 0),
            source_type="canonical_refund_payment",
            source_id=refund["id"],
            provider_event_type="refund",
            provider_mode=provider_refund.provider_mode,
            provider_account_reference=provider_refund.provider_account_reference,
            provider_payment_reference=provider_refund.provider_payment_reference,
            notes="Provider-confirmed Webstore refund",
        ).model_dump()
        await _insert_ledger_entry(ledger)
    if not ledger_was_existing:
        await _audit(
            tenant_id=tenant_id,
            webstore_id=webstore_id,
            actor_type="provider",
            actor_id=provider,
            actor_email=provider,
            action="webstore.refund_reconciled",
            entity_type="provider_refund",
            entity_id=refund_reference,
            summary="Provider Webstore refund reconciled into canonical payment and ledger history",
            metadata={
                "provider_event_id": provider_event_id,
                "provider_payment_reference": payment_reference,
                "amount_cents": provider_refund.amount_cents,
                "currency": provider_refund.currency,
                "status": status,
                "raw_event_snapshot": data.get("raw_event_snapshot") or {},
            },
        )
    refunded_total = 0
    async for row in db.payments.find(
        {"tenant_id": tenant_id, "refund_of_payment_id": source_payment["id"], "status": {"$in": ["pending", "confirmed"]}},
        {"_id": 0, "amount_cents": 1},
    ):
        refunded_total += int(row.get("amount_cents") or 0)
    total = int(source_payment.get("amount_cents") or intent.get("total_cents") or 0)
    refund_status = "refunded" if refunded_total >= total else "partially_refunded"
    await db.webstore_purchase_intents.update_one(
        {"tenant_id": tenant_id, "id": intent["id"]},
        {"$set": {"refund_status": refund_status, "status": refund_status, "updated_at": _now_iso()}},
    )
    return {"refund": serialize_doc(refund), "ledger_entry": serialize_doc(ledger), "refund_status": refund_status, "already_processed": bool(existing_refund)}
