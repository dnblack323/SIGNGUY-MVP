"""Provider financial-event reconciliation for Webstore ledger and payouts."""
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
    ProviderFinancialEvent,
    financial_event_from_provider_result,
    get_webstore_payment_provider,
)
from .webstore_payments_core import _event_key, _existing_event, _now_iso, _require_provider_authority
from .webstore_payments_ledger import _insert_ledger_entry
from .webstore_shared import _audit

async def reconcile_webstore_financial_event(
    *,
    tenant_id: str,
    webstore_id: str,
    provider_event: Optional[ProviderFinancialEvent] = None,
    provider=None,
    provider_authority: Optional[ProviderAuthority] = None,
) -> dict:
    """Reconcile only typed, provider-authoritative payout/dispute events."""
    _require_provider_authority(provider_authority)
    if provider_event is None:
        provider_impl = provider or get_webstore_payment_provider(get_settings())
        result = await provider_impl.reconcile_provider_event(
            tenant_id=tenant_id,
            webstore_id=webstore_id,
            provider_authority=provider_authority,
        )
        if not result.ok:
            code = "payment_provider_not_configured" if result.code == PAYMENT_PROVIDER_NOT_CONFIGURED else "provider_event_reconciliation_failed"
            raise WebstoreError(code, result.message, 503)
        try:
            provider_event = financial_event_from_provider_result(result)
        except (KeyError, TypeError, ValueError) as exc:
            raise WebstoreError("provider_event_invalid", "Provider event failed reconciliation", 502) from exc
    if not isinstance(provider_event, ProviderFinancialEvent):
        raise WebstoreError("provider_event_invalid", "Provider event is not a typed provider result", 400)

    intent = await db.webstore_purchase_intents.find_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "provider_payment_id": provider_event.provider_payment_reference},
        {"_id": 0},
    )
    if not intent or not intent.get("canonical_payment_id"):
        raise WebstoreError("paid_purchase_intent_required", "A verified paid Webstore purchase intent is required", 409)
    if provider_event.amount_cents < 0 or provider_event.amount_cents > int(intent.get("total_cents") or 0):
        raise WebstoreError("provider_event_amount_invalid", "Provider event amount is outside the canonical purchase", 409)
    if provider_event.currency != str(intent.get("currency") or "usd").lower():
        raise WebstoreError("provider_event_currency_mismatch", "Provider event currency does not match the purchase", 409)
    if provider_authority is not None and (
        provider_event.provider != provider_authority.provider
        or provider_event.provider_mode != provider_authority.mode
        or provider_event.provider_account_reference != provider_authority.account_reference
    ):
        raise WebstoreError("provider_event_authority_mismatch", "Provider event does not match provider authority", 409)

    source_type = "provider_dispute_event" if provider_event.event_type == "dispute" else f"provider_{provider_event.event_type}_event"
    existing = await db.webstore_ledger_entries.find_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "source_type": source_type, "source_id": provider_event.provider_event_id},
        {"_id": 0},
    )
    if existing:
        same = all(
            [
                existing.get("amount_cents") == provider_event.amount_cents,
                existing.get("currency") == provider_event.currency,
                existing.get("provider_event_type") == provider_event.event_type,
                existing.get("provider_payment_reference") == provider_event.provider_payment_reference,
            ]
        )
        if not same:
            raise WebstoreError("provider_event_conflict", "Conflicting provider event was rejected", 409)
        return {"ledger_entry": serialize_doc(existing), "already_processed": True}

    sequence_field = "dispute_provider_event_sequence" if provider_event.event_type == "dispute" else "payout_provider_event_sequence"
    current_sequence = intent.get(sequence_field)
    if provider_event.sequence is not None and current_sequence is not None and provider_event.sequence <= int(current_sequence):
        raise WebstoreError("provider_event_out_of_order", "Out-of-order provider event was rejected", 409)

    if provider_event.event_type == "dispute":
        entry_type = "dispute_release" if provider_event.status in {"won", "released", "closed"} else "dispute_hold"
        amount_cents = abs(provider_event.amount_cents) if entry_type == "dispute_release" else -abs(provider_event.amount_cents)
        intent_updates = {"dispute_status": provider_event.status, "status": "disputed"}
    else:
        entry_type = "payout"
        amount_cents = provider_event.amount_cents
        intent_updates = {"payout_status": provider_event.status}
    entry = WebstoreLedgerEntry(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        buyer_order_id=intent["id"],
        entry_type=entry_type,  # type: ignore[arg-type]
        amount_cents=amount_cents,
        currency=provider_event.currency,
        basis_amount_cents=int(intent.get("total_cents") or 0),
        source_type=source_type,
        source_id=provider_event.provider_event_id,
        provider_event_type=provider_event.event_type,
        provider_mode=provider_event.provider_mode,
        provider_account_reference=provider_event.provider_account_reference,
        provider_payment_reference=provider_event.provider_payment_reference,
        provider_event_sequence=provider_event.sequence,
        notes=f"Provider event status {provider_event.status}",
    ).model_dump()
    await _insert_ledger_entry(entry)
    if provider_event.sequence is not None:
        intent_updates[sequence_field] = provider_event.sequence
    intent_updates["updated_at"] = _now_iso()
    await db.webstore_purchase_intents.update_one({"tenant_id": tenant_id, "id": intent["id"]}, {"$set": intent_updates})
    await _audit(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        actor_type="provider",
        actor_id=provider_event.provider,
        actor_email=provider_event.provider,
        action="webstore.provider_financial_event_reconciled",
        entity_type=f"provider_{provider_event.event_type}_event",
        entity_id=provider_event.provider_event_id,
        summary="Provider financial event reconciled into the Webstore ledger",
        metadata={
            "provider_mode": provider_event.provider_mode,
            "provider_account_reference": provider_event.provider_account_reference,
            "provider_payment_reference": provider_event.provider_payment_reference,
            "amount_cents": provider_event.amount_cents,
            "currency": provider_event.currency,
            "status": provider_event.status,
            "sequence": provider_event.sequence,
            "raw_event_snapshot": provider_event.raw_event_snapshot or {},
        },
    )
    return {"ledger_entry": serialize_doc(entry), "already_processed": False}
