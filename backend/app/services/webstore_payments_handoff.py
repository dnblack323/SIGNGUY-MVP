"""Canonical Customer, Order, Payment, and production handoff helpers."""
from __future__ import annotations

import sys
from typing import Any

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.customer import Customer
from ..models.order import Order, OrderItem
from ..models.payment import Payment
from ..models.webstore import WebstorePaymentEvent
from .sequence import next_number, next_record_number
from .webstore_context import WebstoreError
from .webstore_shared import _audit
from .webstore_payments_core import _now_iso
from .webstore_payments_ledger import _record_purchase_ledger

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


def _create_payment_for_handoff():
    facade = sys.modules.get(f"{__package__}.webstore_payments")
    if facade is not None:
        return getattr(facade, "_create_payment", _create_payment)
    return _create_payment


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
    payment = await _create_payment_for_handoff()(intent, order, customer, event)
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
