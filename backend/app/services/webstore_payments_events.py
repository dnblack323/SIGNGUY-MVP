"""Provider-verified payment event processing for Webstores."""
from __future__ import annotations

from typing import Any, Optional

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc
from ..models.webstore import WebstorePaymentEvent
from .webstore_context import WebstoreError
from .webstore_payment_provider import ProviderAuthority, VerifiedProviderPayment
from .webstore_payments_core import _event_key, _event_response, _existing_event, _now_iso, _require_provider_authority, _wait_for_terminal_event
from .webstore_payments_handoff import (
    _bridge_to_production,
    _create_order_graph,
    _create_payment_for_handoff,
    _customer_for_intent,
)
from .webstore_payments_ledger import _record_purchase_ledger
from .webstore_shared import _audit

async def process_verified_payment_event(
    event_fields: Optional[dict[str, Any]] = None,
    *,
    verified_payment: Optional[VerifiedProviderPayment] = None,
    provider_authority: Optional[ProviderAuthority] = None,
    create_downstream_records: bool = True,
) -> dict:
    _require_provider_authority(provider_authority)
    if verified_payment is not None:
        if not isinstance(verified_payment, VerifiedProviderPayment):
            raise WebstoreError("payment_event_invalid", "Verified provider payment result is invalid", 400)
        event_fields = verified_payment.as_internal_fields()
    elif provider_authority is not None:
        raise WebstoreError(
            "payment_event_requires_typed_result",
            "Provider-authorized payment processing requires a typed provider result",
            400,
        )
    if not isinstance(event_fields, dict):
        raise WebstoreError("payment_event_incomplete", "Verified payment event is incomplete", 400)
    provider = str(event_fields.get("provider") or "").strip().lower()
    provider_mode = str(event_fields.get("provider_mode") or "test").strip().lower()
    provider_account_reference = event_fields.get("provider_account_reference")
    if provider_authority is not None and (
        provider != provider_authority.provider
        or provider_mode != provider_authority.mode
        or (
            provider_authority.account_reference
            and event_fields.get("provider_account_reference") != provider_authority.account_reference
        )
    ):
        raise WebstoreError("provider_event_authority_mismatch", "Provider event does not match provider authority", 409)
    provider_event_id = str(event_fields.get("provider_event_id") or "").strip()
    provider_payment_id = str(event_fields.get("provider_payment_id") or "").strip()
    purchase_intent_id = str(event_fields.get("purchase_intent_id") or "").strip()
    tenant_id = str(event_fields.get("tenant_id") or "").strip()
    if not all([provider, provider_event_id, provider_payment_id, purchase_intent_id, tenant_id]):
        raise WebstoreError("payment_event_incomplete", "Verified payment event is incomplete", 400)

    existing_event = await _existing_event(provider, provider_event_id)
    if existing_event:
        return _event_response(await _wait_for_terminal_event(provider, provider_event_id) or existing_event)

    intent = await db.webstore_purchase_intents.find_one({"tenant_id": tenant_id, "id": purchase_intent_id}, {"_id": 0})
    if not intent:
        raise WebstoreError("purchase_intent_not_found", "Webstore purchase intent not found", 404)
    event_webstore_id = str(event_fields.get("webstore_id") or "").strip()
    if provider_authority is not None and not event_webstore_id:
        raise WebstoreError("payment_event_incomplete", "Provider payment event is missing the Webstore reference", 400)
    if event_webstore_id and event_webstore_id != str(intent.get("webstore_id") or ""):
        raise WebstoreError("webstore_event_mismatch", "Provider payment event does not match the purchase Webstore", 409)

    event = WebstorePaymentEvent(
        tenant_id=tenant_id,
        webstore_id=intent["webstore_id"],
        purchase_intent_id=purchase_intent_id,
        provider=provider,
        provider_event_id=provider_event_id,
        provider_payment_id=provider_payment_id,
        provider_mode=provider_mode,
        provider_account_reference=provider_account_reference,
        amount_cents=int(event_fields.get("amount_cents") or 0),
        currency=str(event_fields.get("currency") or "usd").lower(),
    )
    raw_event_snapshot = event_fields.get("raw_event_snapshot")
    try:
        event_document = event.model_dump(exclude={"raw_event_snapshot"})
        if isinstance(raw_event_snapshot, dict) and raw_event_snapshot:
            event_document["raw_event_snapshot"] = raw_event_snapshot
        await db.webstore_payment_events.insert_one(prepare_for_mongo(event_document))
    except DuplicateKeyError:
        existing_event = await _existing_event(provider, provider_event_id)
        if existing_event:
            return _event_response(await _wait_for_terminal_event(provider, provider_event_id) or existing_event)
        existing_same_payment = await db.webstore_payment_events.find_one(
            {
                "tenant_id": tenant_id,
                "purchase_intent_id": purchase_intent_id,
                "provider": provider,
                "provider_payment_id": provider_payment_id,
            },
            {"_id": 0},
        )
        if existing_same_payment:
            existing_same_payment = serialize_doc(existing_same_payment)
            return _event_response(existing_same_payment)
        raise

    try:
        if event.amount_cents != int(intent.get("total_cents") or 0) or event.currency != str(intent.get("currency") or "usd").lower():
            raise WebstoreError("payment_amount_mismatch", "Verified payment amount or currency does not match the purchase intent", 409)

        claimed = await db.webstore_purchase_intents.find_one_and_update(
            {
                "tenant_id": tenant_id,
                "id": purchase_intent_id,
                "status": "pending_payment",
                "canonical_order_id": {"$in": [None, ""]},
            },
            {
                "$set": {
                    "status": "payment_processing",
                    "provider": provider,
                    "provider_payment_id": provider_payment_id,
                    "verified_payment_event_id": event.id,
                    "updated_at": _now_iso(),
                }
            },
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        if not claimed:
            current = await db.webstore_purchase_intents.find_one({"tenant_id": tenant_id, "id": purchase_intent_id}, {"_id": 0})
            if current and current.get("canonical_order_id") and current.get("canonical_payment_id"):
                await db.webstore_payment_events.update_one(
                    {"id": event.id, "tenant_id": tenant_id},
                    {
                        "$set": {
                            "status": "duplicate",
                            "canonical_customer_id": current.get("canonical_customer_id"),
                            "canonical_order_id": current.get("canonical_order_id"),
                            "canonical_payment_id": current.get("canonical_payment_id"),
                            "processed_at": _now_iso(),
                            "updated_at": _now_iso(),
                        }
                    },
                )
                duplicate = await db.webstore_payment_events.find_one({"id": event.id}, {"_id": 0})
                return _event_response(serialize_doc(duplicate))
            raise WebstoreError("purchase_intent_not_processable", "Purchase intent is not available for payment processing", 409)

        if not create_downstream_records:
            updates = {
                "status": "payment_verified",
                "provider": provider,
                "provider_payment_id": provider_payment_id,
                "provider_mode": provider_mode,
                "provider_account_reference": provider_account_reference,
                "provider_payment_reference": provider_payment_id,
                "checkout_status": "verified_payment_received",
                "reconciliation_state": "verified_pending_stage8",
                "processing_state": "verified",
                "payout_status": "pending",
                "updated_at": _now_iso(),
            }
            await db.webstore_purchase_intents.update_one(
                {"tenant_id": tenant_id, "id": purchase_intent_id},
                {"$set": updates},
            )
            await db.webstore_payment_events.update_one(
                {"id": event.id, "tenant_id": tenant_id},
                {
                    "$set": {
                        "status": "processed",
                        "reconciliation_state": "verified_pending_stage8",
                        "processing_state": "verified",
                        "processed_at": _now_iso(),
                        "updated_at": _now_iso(),
                    }
                },
            )
            await _audit(
                tenant_id=tenant_id,
                webstore_id=claimed["webstore_id"],
                actor_type="provider",
                actor_id=provider,
                actor_email=provider,
                action="webstore.verified_payment_received",
                entity_type="webstore_purchase_intent",
                entity_id=purchase_intent_id,
                summary="Verified Webstore payment received and held for Stage 8 order handoff",
                metadata={"provider": provider, "provider_event_id": provider_event_id, "stage8_handoff": True},
            )
            processed = await db.webstore_payment_events.find_one({"id": event.id}, {"_id": 0})
            return {"payment_event": serialize_doc(processed), "already_processed": False, "stage8_handoff": True}

        customer = await _customer_for_intent(claimed, provider_event_id=provider_event_id)
        order, _items = await _create_order_graph(claimed, customer, provider_event_id=provider_event_id)
        payment = await _create_payment_for_handoff()(claimed, order, customer, event)
        await _record_purchase_ledger(claimed, payment_id=payment["id"])
        production_bridge_status, work_order_id = await _bridge_to_production(claimed, order)
        updates = {
            "status": "paid_order_created",
            "canonical_customer_id": customer["id"],
            "canonical_order_id": order["id"],
            "canonical_payment_id": payment["id"],
            "checkout_status": "verified_payment_processed",
            "reconciliation_state": "canonical_records_created",
            "processing_state": "completed",
            "production_bridge_status": production_bridge_status,
            "work_order_id": work_order_id,
            "fulfillment_status": "ready_for_production" if work_order_id else "not_required",
            "confirmation_token": claimed.get("confirmation_token") or event.id,
            "payout_status": "pending",
            "updated_at": _now_iso(),
        }
        await db.webstore_purchase_intents.update_one({"tenant_id": tenant_id, "id": purchase_intent_id}, {"$set": updates})
        await db.webstore_payment_events.update_one(
            {"id": event.id, "tenant_id": tenant_id},
            {
                "$set": {
                    "status": "processed",
                    "canonical_customer_id": customer["id"],
                    "canonical_order_id": order["id"],
                    "canonical_payment_id": payment["id"],
                    "reconciliation_state": "canonical_records_created",
                    "processing_state": "completed",
                    "processed_at": _now_iso(),
                    "updated_at": _now_iso(),
                }
            },
        )
        await _audit(
            tenant_id=tenant_id,
            webstore_id=claimed["webstore_id"],
            actor_type="provider",
            actor_id=provider,
            actor_email=provider,
            action="webstore.verified_payment_processed",
            entity_type="webstore_purchase_intent",
            entity_id=purchase_intent_id,
            summary="Verified Webstore payment created canonical commerce records",
            metadata={
                "provider": provider,
                "provider_event_id": provider_event_id,
                "order_id": order["id"],
                "payment_id": payment["id"],
                "work_order_id": work_order_id,
                "production_bridge_status": production_bridge_status,
            },
        )
        processed = await db.webstore_payment_events.find_one({"id": event.id}, {"_id": 0})
        return {
            "payment_event": serialize_doc(processed),
            "already_processed": False,
            "customer": customer,
            "order": order,
            "payment": payment,
        }
    except Exception as exc:
        code = getattr(exc, "code", "payment_processing_failed")
        await db.webstore_payment_events.update_one(
            {"id": event.id, "tenant_id": tenant_id},
            {"$set": {"status": "failed", "failure_code": code, "failure_reason": str(exc), "updated_at": _now_iso()}},
        )
        await db.webstore_purchase_intents.update_one(
            {"tenant_id": tenant_id, "id": purchase_intent_id, "status": "payment_processing"},
            {"$set": {"status": "payment_failed", "updated_at": _now_iso()}},
        )
        raise


async def reconcile_webstore_payment_status_event(
    *,
    tenant_id: str,
    webstore_id: str,
    provider_result,
    provider_authority: Optional[ProviderAuthority] = None,
) -> dict:
    """Record signed Stripe pending/failure state without creating commerce records."""
    _require_provider_authority(provider_authority)
    if not getattr(provider_result, "ok", False) or not isinstance(provider_result.data, dict):
        raise WebstoreError("provider_event_invalid", "Provider payment status event is invalid", 400)
    data = dict(provider_result.data)
    event_kind = str(data.get("event_kind") or "")
    if event_kind not in {"payment_failure", "payment_pending"}:
        raise WebstoreError("provider_event_invalid", "Provider payment status event type is invalid", 400)
    provider = str(data.get("provider") or "").strip().lower()
    provider_mode = str(data.get("provider_mode") or "").strip().lower()
    provider_event_id = str(data.get("provider_event_id") or "").strip()
    provider_payment_id = str(data.get("provider_payment_id") or "").strip()
    purchase_intent_id = str(data.get("purchase_intent_id") or "").strip()
    result_tenant_id = str(data.get("tenant_id") or "").strip()
    result_webstore_id = str(data.get("webstore_id") or "").strip()
    if (
        not all([provider, provider_event_id, provider_payment_id, purchase_intent_id, result_tenant_id, result_webstore_id])
        or result_tenant_id != tenant_id
        or result_webstore_id != webstore_id
        or provider_mode not in {"test", "live"}
    ):
        raise WebstoreError("provider_event_incomplete", "Provider payment status event is incomplete", 400)
    provider_account_reference = data.get("provider_account_reference")
    if provider_authority is not None and (
        provider != provider_authority.provider
        or provider_mode != provider_authority.mode
        or provider_account_reference != provider_authority.account_reference
    ):
        raise WebstoreError("provider_event_authority_mismatch", "Provider event does not match provider authority", 409)

    intent = await db.webstore_purchase_intents.find_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": purchase_intent_id},
        {"_id": 0},
    )
    if not intent:
        raise WebstoreError("purchase_intent_not_found", "Webstore purchase intent not found", 404)
    amount_cents = int(data.get("amount_cents") or 0)
    currency = str(data.get("currency") or "usd").lower()
    if amount_cents != int(intent.get("total_cents") or 0) or currency != str(intent.get("currency") or "usd").lower():
        raise WebstoreError("payment_amount_mismatch", "Provider payment status does not match the purchase intent", 409)

    existing_event = await _existing_event(provider, provider_event_id)
    if existing_event:
        return _event_response(await _wait_for_terminal_event(provider, provider_event_id) or existing_event)
    existing_same_payment = await db.webstore_payment_events.find_one(
        {
            "tenant_id": tenant_id,
            "purchase_intent_id": purchase_intent_id,
            "provider": provider,
            "provider_payment_id": provider_payment_id,
        },
        {"_id": 0},
    )
    if existing_same_payment:
        existing_same_payment = serialize_doc(existing_same_payment)
        if event_kind == "payment_failure" and existing_same_payment.get("reconciliation_state") == "provider_pending":
            failure_updates = {
                "status": "failed",
                "failure_code": data.get("failure_code") or str(data.get("status") or "payment_failed"),
                "failure_reason": data.get("failure_reason"),
                "reconciliation_state": "failed",
                "processed_at": _now_iso(),
                "updated_at": _now_iso(),
            }
            await db.webstore_payment_events.update_one(
                {"id": existing_same_payment["id"], "tenant_id": tenant_id},
                {"$set": failure_updates},
            )
            existing_same_payment.update(failure_updates)
        return _event_response(existing_same_payment)

    event_status = "failed" if event_kind == "payment_failure" else "processing"
    reconciliation_state = "failed" if event_kind == "payment_failure" else "provider_pending"
    event = WebstorePaymentEvent(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        purchase_intent_id=purchase_intent_id,
        provider=provider,
        provider_event_id=provider_event_id,
        provider_payment_id=provider_payment_id,
        provider_mode=provider_mode,
        provider_account_reference=provider_account_reference,
        amount_cents=amount_cents,
        currency=currency,
        status=event_status,  # type: ignore[arg-type]
        failure_code=data.get("failure_code"),
        failure_reason=data.get("failure_reason"),
        reconciliation_state=reconciliation_state,
        processing_state="status_recorded",
        processed_at=_now_iso(),
        raw_event_snapshot=data.get("raw_event_snapshot") or {},
    )
    try:
        await db.webstore_payment_events.insert_one(prepare_for_mongo(event.model_dump()))
    except DuplicateKeyError:
        existing_event = await _existing_event(provider, provider_event_id)
        if existing_event:
            return _event_response(await _wait_for_terminal_event(provider, provider_event_id) or existing_event)
        existing_same_payment = await db.webstore_payment_events.find_one(
            {
                "tenant_id": tenant_id,
                "purchase_intent_id": purchase_intent_id,
                "provider": provider,
                "provider_payment_id": provider_payment_id,
            },
            {"_id": 0},
        )
        if existing_same_payment:
            return _event_response(serialize_doc(existing_same_payment))
        raise

    intent_updates = {
        "provider": provider,
        "provider_payment_id": provider_payment_id,
        "provider_mode": provider_mode,
        "provider_account_reference": provider_account_reference,
        "provider_payment_reference": provider_payment_id,
        "checkout_status": "payment_failed" if event_kind == "payment_failure" else "provider_pending",
        "reconciliation_state": reconciliation_state,
        "updated_at": _now_iso(),
    }
    if event_kind == "payment_failure" and intent.get("status") in {"pending_payment", "payment_processing"}:
        failure_status = str(data.get("status") or "payment_failed")
        intent_updates["status"] = failure_status if failure_status in {"payment_failed", "expired", "canceled"} else "payment_failed"
    await db.webstore_purchase_intents.update_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": purchase_intent_id},
        {"$set": intent_updates},
    )
    await _audit(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        actor_type="provider",
        actor_id=provider,
        actor_email=provider,
        action="webstore.payment_status_recorded",
        entity_type="webstore_purchase_intent",
        entity_id=purchase_intent_id,
        summary="Provider payment status recorded without creating commerce records",
        metadata={"provider_event_id": provider_event_id, "event_kind": event_kind, "status": data.get("status")},
    )
    recorded = await db.webstore_payment_events.find_one({"id": event.id, "tenant_id": tenant_id}, {"_id": 0})
    return {"payment_event": serialize_doc(recorded), "already_processed": False, "commerce_created": False}
