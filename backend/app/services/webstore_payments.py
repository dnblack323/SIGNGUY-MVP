"""Stage 1 Webstores verified-payment foundation.

This module is intentionally internal-only. It accepts already-verified provider
events from a future webhook boundary and never exposes a public fake-payment
route.
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from ..core.config import get_settings
from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.customer import Customer
from ..models.order import Order, OrderItem
from ..models.payment import Payment
from ..models.webstore import WebstoreLedgerEntry, WebstorePaymentEvent
from .sequence import next_number, next_record_number
from .webstores import WebstoreError, _audit
from .webstore_payment_provider import (
    PAYMENT_PROVIDER_NOT_CONFIGURED,
    ProviderAuthority,
    ProviderFinancialEvent,
    ProviderRefund,
    VerifiedProviderPayment,
    financial_event_from_provider_result,
    get_webstore_payment_provider,
    provider_configuration_status,
    refund_from_provider_result,
)


def _now_iso() -> str:
    return utc_now().isoformat()


def _event_key(provider: str, provider_event_id: str) -> dict[str, str]:
    return {"provider": provider, "provider_event_id": provider_event_id}


async def _existing_event(provider: str, provider_event_id: str) -> Optional[dict]:
    return serialize_doc(await db.webstore_payment_events.find_one(_event_key(provider, provider_event_id), {"_id": 0}))


async def _wait_for_terminal_event(provider: str, provider_event_id: str) -> Optional[dict]:
    for _ in range(200):
        event = await _existing_event(provider, provider_event_id)
        if event and event.get("status") != "processing":
            return event
        await asyncio.sleep(0.01)
    return await _existing_event(provider, provider_event_id)


def _event_response(event: dict) -> dict:
    return {
        "payment_event": event,
        "already_processed": event.get("status") in {"processed", "failed", "duplicate"},
        "order_id": event.get("canonical_order_id"),
        "payment_id": event.get("canonical_payment_id"),
    }


def _require_provider_authority(authority: Optional[ProviderAuthority] = None) -> None:
    if authority is not None:
        if authority.verified and authority.webhook_verified and authority.charge_model != "deferred":
            return
        raise WebstoreError(
            "payment_provider_not_configured",
            "Provider-authoritative Webstore payment processing is unavailable until provider verification is complete.",
            503,
        )
    status = provider_configuration_status()
    if not status["provider_authority"]:
        raise WebstoreError(
            "payment_provider_not_configured",
            "Provider-authoritative Webstore payment processing is unavailable until the Stripe adapter is implemented and verified.",
            503,
        )


async def _customer_for_intent(intent: dict, *, provider_event_id: str) -> dict:
    buyer_email = str(intent.get("buyer_email") or "").strip().lower()
    existing = await db.customers.find_one(
        {"tenant_id": intent["tenant_id"], "email": buyer_email},
        {"_id": 0},
    )
    if existing:
        return serialize_doc(existing)
    customer = Customer(
        tenant_id=intent["tenant_id"],
        name=intent["buyer_name"],
        email=buyer_email,
        phone=intent.get("buyer_phone"),
        notes=f"Created from verified Webstore purchase intent {intent['id']}",
    ).model_dump()
    allocation = await next_record_number(
        tenant_id=intent["tenant_id"],
        record_type="customer",
        idempotency_key=f"webstore-customer:{intent['id']}:{intent['buyer_email']}",
        issued_to_entity_type="customer",
        issued_to_entity_id=customer["id"],
        actor_user_id="webstore-payment",
        actor_email="webstore-payment",
        reason="webstore.verified_payment_customer",
        context={"purchase_intent_id": intent["id"], "provider_event_id": provider_event_id},
    )
    customer["number"] = allocation.number
    try:
        await db.customers.insert_one(prepare_for_mongo(customer))
    except DuplicateKeyError:
        existing = await db.customers.find_one(
            {"tenant_id": intent["tenant_id"], "email": intent["buyer_email"]},
            {"_id": 0},
        )
        if existing:
            return serialize_doc(existing)
        raise
    return serialize_doc(customer)


async def _create_order_graph(intent: dict, customer: dict, *, provider_event_id: str) -> tuple[dict, list[dict]]:
    existing_order = await db.orders.find_one(
        {
            "tenant_id": intent["tenant_id"],
            "source_type": "webstore_purchase_intent",
            "source_id": intent["id"],
        },
        {"_id": 0},
    )
    if existing_order:
        order = existing_order
    else:
        number = await next_number(tenant_id=intent["tenant_id"], name="order")
        order = Order(
            tenant_id=intent["tenant_id"],
            number=number,
            customer_id=customer["id"],
            job_name=f"Webstore order - {intent['buyer_name']}",
            title=f"Webstore purchase {intent['id']}",
            description="Created from verified Webstore payment",
            subtotal_cents=int(intent.get("product_subtotal_cents") or 0),
            discount_cents=0,
            tax_cents=int(intent.get("tax_cents") or 0),
            total_cents=int(intent.get("total_cents") or 0),
            amount_paid_cents=int(intent.get("total_cents") or 0),
            balance_cents=0,
            status="confirmed",
            created_by="webstore-payment",
            source_type="webstore_purchase_intent",
            source_id=intent["id"],
        ).model_dump()
        try:
            await db.orders.insert_one(prepare_for_mongo(order))
        except DuplicateKeyError:
            existing_order = await db.orders.find_one(
                {
                    "tenant_id": intent["tenant_id"],
                    "source_type": "webstore_purchase_intent",
                    "source_id": intent["id"],
                },
                {"_id": 0},
            )
            if not existing_order:
                raise
            order = existing_order
    items: list[dict] = []
    for idx, line in enumerate(intent.get("line_items") or []):
        existing_item = await db.order_items.find_one(
            {
                "tenant_id": intent["tenant_id"],
                "source_type": "webstore_purchase_intent",
                "source_id": intent["id"],
                "position": idx,
            },
            {"_id": 0},
        )
        if existing_item:
            if existing_item.get("order_id") != order["id"]:
                raise WebstoreError(
                    "canonical_order_conflict",
                    "A Webstore purchase item is linked to a different canonical Order",
                    409,
                )
            items.append(serialize_doc(existing_item))
            continue
        item = OrderItem(
            tenant_id=intent["tenant_id"],
            order_id=order["id"],
            position=idx,
            category="webstore",
            product_type="webstore_product",
            description=line["name"],
            quantity=int(line["quantity"]),
            unit_price_cents=int(line["unit_price_cents"]),
            line_subtotal_cents=int(line["line_total_cents"]),
            line_total_cents=int(line["line_total_cents"]),
            pricing_snapshot={
                "source": "webstore_purchase_intent",
                "purchase_intent_id": intent["id"],
                "provider_event_id": provider_event_id,
                "line_item": line,
            },
            production_required=True,
            source_type="webstore_purchase_intent",
            source_id=intent["id"],
        ).model_dump()
        try:
            await db.order_items.insert_one(prepare_for_mongo(item))
        except DuplicateKeyError:
            existing_item = await db.order_items.find_one(
                {
                    "tenant_id": intent["tenant_id"],
                    "source_type": "webstore_purchase_intent",
                    "source_id": intent["id"],
                    "position": idx,
                },
                {"_id": 0},
            )
            if not existing_item or existing_item.get("order_id") != order["id"]:
                raise WebstoreError(
                    "canonical_order_conflict",
                    "A Webstore purchase item could not be recovered safely",
                    409,
                )
            item = existing_item
        items.append(serialize_doc(item))
    return serialize_doc(order), items


async def _create_payment(intent: dict, order: dict, customer: dict, event: WebstorePaymentEvent) -> dict:
    idempotency_key = f"webstore-payment:{event.provider}:{event.provider_payment_id}"
    existing = await db.payments.find_one(
        {
            "tenant_id": intent["tenant_id"],
            "invoice_id": f"webstore_purchase_intent:{intent['id']}",
            "idempotency_key": idempotency_key,
        },
        {"_id": 0},
    )
    if not existing and event.provider_payment_id:
        existing = await db.payments.find_one(
            {
                "tenant_id": intent["tenant_id"],
                "stripe_payment_intent_id": event.provider_payment_id,
            },
            {"_id": 0},
        )
    if existing:
        if existing.get("order_id") != order["id"] or existing.get("customer_id") != customer["id"]:
            raise WebstoreError(
                "canonical_payment_conflict",
                "A Webstore payment is linked to a different canonical Order or Customer",
                409,
            )
        return serialize_doc(existing)

    payment = Payment(
        tenant_id=intent["tenant_id"],
        record_number_type="payment",
        invoice_id=f"webstore_purchase_intent:{intent['id']}",
        customer_id=customer["id"],
        order_id=order["id"],
        source="stripe",
        status="confirmed",
        amount_cents=event.amount_cents,
        currency=event.currency,
        stripe_payment_intent_id=event.provider_payment_id if event.provider == "stripe" else None,
        provider_event_id=event.provider_event_id,
        idempotency_key=idempotency_key,
        confirmed_at=utc_now(),
        created_by="webstore-payment",
    ).model_dump()
    allocation = await next_record_number(
        tenant_id=intent["tenant_id"],
        record_type="payment",
        idempotency_key=payment["idempotency_key"],
        issued_to_entity_type="payment",
        issued_to_entity_id=payment["id"],
        actor_user_id="webstore-payment",
        actor_email="webstore-payment",
        reason="webstore.verified_payment",
        context={"purchase_intent_id": intent["id"], "order_id": order["id"]},
    )
    payment["number"] = allocation.number
    try:
        await db.payments.insert_one(prepare_for_mongo(payment))
    except DuplicateKeyError:
        existing = await db.payments.find_one(
            {
                "tenant_id": intent["tenant_id"],
                "invoice_id": payment["invoice_id"],
                "idempotency_key": payment["idempotency_key"],
            },
            {"_id": 0},
        )
        if existing:
            if existing.get("order_id") != order["id"] or existing.get("customer_id") != customer["id"]:
                raise WebstoreError(
                    "canonical_payment_conflict",
                    "A Webstore payment is linked to a different canonical Order or Customer",
                    409,
                )
            return serialize_doc(existing)
        raise
    return serialize_doc(payment)


async def _insert_ledger_entry(entry: dict) -> None:
    existing = await db.webstore_ledger_entries.find_one(
        {
            "tenant_id": entry["tenant_id"],
            "webstore_id": entry["webstore_id"],
            "source_type": entry["source_type"],
            "source_id": entry["source_id"],
            "entry_type": entry["entry_type"],
            "reversal_of_ledger_entry_id": entry.get("reversal_of_ledger_entry_id"),
        },
        {"_id": 0, "id": 1},
    )
    if existing:
        return
    await db.webstore_ledger_entries.insert_one(prepare_for_mongo(entry))


async def _record_purchase_ledger(intent: dict, *, payment_id: str) -> None:
    snapshot = intent.get("immutable_snapshot") or {}
    financial_lines = snapshot.get("financial_lines") or []
    platform_fee = sum(int(line.get("platform_fee_cents") or 0) for line in financial_lines)
    owner_share = sum(int(line.get("store_owner_share_cents") or 0) for line in financial_lines)
    fundraiser_share = sum(int(line.get("fundraiser_share_cents") or 0) for line in financial_lines)
    production_cost = sum(int(line.get("production_cost_cents") or 0) for line in financial_lines)
    subtotal = int(intent.get("product_subtotal_cents") or 0)
    total = int(intent.get("total_cents") or 0)
    shop_gross = subtotal - platform_fee - owner_share - fundraiser_share - production_cost
    rows = [
        ("buyer_payment", total, total, None),
        ("product_subtotal", subtotal, subtotal, None),
        ("donation", int(intent.get("donation_cents") or 0), total, None),
        ("shipping", int(intent.get("shipping_cents") or 0), total, None),
        ("sales_tax", int(intent.get("tax_cents") or 0), total, None),
        ("payment_processing_fee", 0, total, None),
        ("platform_usage_fee", platform_fee, subtotal, None),
        ("store_owner_share", owner_share, subtotal, None),
        ("fundraiser_share", fundraiser_share, subtotal, None),
        ("production_cost_estimate", production_cost, subtotal, None),
        ("shop_gross_estimate", shop_gross, subtotal, None),
    ]
    for entry_type, amount, basis, bps in rows:
        entry = WebstoreLedgerEntry(
            tenant_id=intent["tenant_id"],
            webstore_id=intent["webstore_id"],
            buyer_order_id=intent["id"],
            entry_type=entry_type,  # type: ignore[arg-type]
            amount_cents=amount,
            basis_amount_cents=basis,
            snapshot_basis_points=bps,
            source_type="webstore_purchase_intent",
            source_id=intent["id"],
            notes=f"Posted from canonical payment {payment_id}",
        ).model_dump()
        await _insert_ledger_entry(entry)


async def _bridge_to_production(intent: dict, order: dict) -> tuple[str, Optional[str]]:
    try:
        from . import work_order_service

        work_order, _existing = await work_order_service.generate(
            tenant_id=intent["tenant_id"],
            order_id=order["id"],
            actor_user_id="webstore-payment",
            actor_email="webstore-payment",
            production_instructions=f"Generated from Webstore purchase intent {intent['id']}",
            source_context={"webstore_id": intent["webstore_id"], "purchase_intent_id": intent["id"]},
        )
        return "bridged", work_order["id"]
    except ValueError as exc:
        if str(exc) == "no_production_required_items":
            return "not_required", None
        return "failed", None


async def _complete_canonical_payment_handoff(
    intent: dict,
    event: WebstorePaymentEvent,
    *,
    bridge_production: bool,
) -> dict[str, Any]:
    customer = await _customer_for_intent(intent, provider_event_id=event.provider_event_id)
    order, items = await _create_order_graph(intent, customer, provider_event_id=event.provider_event_id)
    if order.get("customer_id") != customer["id"]:
        raise WebstoreError(
            "canonical_order_conflict",
            "A Webstore purchase is linked to a different canonical Customer",
            409,
        )
    payment = await _create_payment(intent, order, customer, event)
    await _record_purchase_ledger(intent, payment_id=payment["id"])
    if bridge_production:
        production_bridge_status, work_order_id = await _bridge_to_production(intent, order)
    else:
        production_bridge_status = str(intent.get("production_bridge_status") or "not_started")
        work_order_id = intent.get("work_order_id")
    return {
        "customer": customer,
        "order": order,
        "items": items,
        "payment": payment,
        "production_bridge_status": production_bridge_status,
        "work_order_id": work_order_id,
    }


async def complete_verified_payment_handoff(
    *,
    tenant_id: str,
    webstore_id: str,
    purchase_intent_id: str,
    actor_user_id: str,
    actor_email: str,
) -> dict[str, Any]:
    """Recover one verified Webstore payment into canonical records.

    Normal webhook processing completes this bridge automatically. This
    permissioned action remains as an audited, replay-safe recovery path for a
    payment event interrupted after verification or during downstream writes.
    """
    intent = await db.webstore_purchase_intents.find_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": purchase_intent_id},
        {"_id": 0},
    )
    if not intent:
        raise WebstoreError("purchase_intent_not_found", "Webstore purchase intent not found", 404)
    if intent.get("status") not in {"payment_verified", "handoff_processing", "paid_order_created"}:
        raise WebstoreError(
            "verified_payment_required",
            "Only a verified Webstore payment waiting for handoff can be processed",
            409,
        )

    event = None
    event_id = str(intent.get("verified_payment_event_id") or "").strip()
    if event_id:
        event = await db.webstore_payment_events.find_one(
            {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": event_id},
            {"_id": 0},
        )
    if not event:
        event = await db.webstore_payment_events.find_one(
            {
                "tenant_id": tenant_id,
                "webstore_id": webstore_id,
                "purchase_intent_id": purchase_intent_id,
                "status": "processed",
                "processing_state": "verified",
            },
            {"_id": 0},
        )
    if not event or event.get("status") != "processed" or event.get("processing_state") not in {"verified", "completed"}:
        raise WebstoreError(
            "verified_payment_event_not_found",
            "The verified provider event needed for this handoff was not found",
            409,
        )
    if event.get("purchase_intent_id") != purchase_intent_id:
        raise WebstoreError("payment_event_mismatch", "Provider event does not match the purchase intent", 409)
    if int(event.get("amount_cents") or 0) != int(intent.get("total_cents") or 0) or str(event.get("currency") or "usd").lower() != str(intent.get("currency") or "usd").lower():
        raise WebstoreError("payment_amount_mismatch", "Verified payment does not match the purchase intent", 409)

    was_complete = intent.get("status") == "paid_order_created" and bool(intent.get("canonical_order_id")) and bool(intent.get("canonical_payment_id"))
    if not was_complete:
        await db.webstore_purchase_intents.update_one(
            {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": purchase_intent_id, "status": {"$in": ["payment_verified", "handoff_processing"]}},
            {"$set": {"status": "handoff_processing", "recovery_state": "in_progress", "updated_at": _now_iso()}},
        )
        intent = await db.webstore_purchase_intents.find_one(
            {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": purchase_intent_id},
            {"_id": 0},
        ) or intent

    try:
        event_model = WebstorePaymentEvent.model_validate(event)
        result = await _complete_canonical_payment_handoff(intent, event_model, bridge_production=False)
        fulfillment_status = "not_required" if result["production_bridge_status"] == "not_required" else "awaiting_production_handoff"
        updates = {
            "status": "paid_order_created",
            "canonical_customer_id": result["customer"]["id"],
            "canonical_order_id": result["order"]["id"],
            "canonical_payment_id": result["payment"]["id"],
            "checkout_status": "verified_payment_processed",
            "reconciliation_state": "canonical_records_created",
            "processing_state": "completed",
            "recovery_state": "not_required",
            "production_bridge_status": result["production_bridge_status"],
            "work_order_id": result["work_order_id"],
            "fulfillment_status": fulfillment_status,
            "confirmation_token": intent.get("confirmation_token") or event_model.provider_event_id,
            "payout_status": intent.get("payout_status") or "pending",
            "updated_at": _now_iso(),
        }
        await db.webstore_purchase_intents.update_one(
            {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": purchase_intent_id},
            {"$set": updates},
        )
        await db.webstore_payment_events.update_one(
            {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": event_model.id},
            {
                "$set": {
                    "canonical_customer_id": result["customer"]["id"],
                    "canonical_order_id": result["order"]["id"],
                    "canonical_payment_id": result["payment"]["id"],
                    "reconciliation_state": "canonical_records_created",
                    "processing_state": "completed",
                    "processed_at": event.get("processed_at") or _now_iso(),
                    "updated_at": _now_iso(),
                }
            },
        )
        if not was_complete:
            await _audit(
                tenant_id=tenant_id,
                webstore_id=webstore_id,
                actor_type="staff",
                actor_id=actor_user_id,
                actor_email=actor_email,
                action="webstore.verified_payment_handoff_completed",
                entity_type="webstore_purchase_intent",
                entity_id=purchase_intent_id,
                summary="Verified Webstore payment completed canonical Order handoff",
                metadata={
                    "order_id": result["order"]["id"],
                    "payment_id": result["payment"]["id"],
                    "provider_event_id": event_model.provider_event_id,
                    "production_deferred_to_stage8c": True,
                },
            )
        return {
            "already_processed": was_complete,
            "handoff_status": "completed",
            "purchase_intent": serialize_doc(await db.webstore_purchase_intents.find_one({"tenant_id": tenant_id, "id": purchase_intent_id}, {"_id": 0})),
            **result,
        }
    except Exception:
        await db.webstore_purchase_intents.update_one(
            {"tenant_id": tenant_id, "webstore_id": webstore_id, "id": purchase_intent_id, "status": "handoff_processing"},
            {"$set": {"recovery_state": "handoff_retry_required", "updated_at": _now_iso()}},
        )
        raise


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
        payment = await _create_payment(claimed, order, customer, event)
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
