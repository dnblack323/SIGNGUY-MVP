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

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.customer import Customer
from ..models.order import Order, OrderItem
from ..models.payment import Payment
from ..models.webstore import WebstoreLedgerEntry, WebstorePaymentEvent
from .sequence import next_number, next_record_number
from .webstores import WebstoreError, _audit


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
        "already_processed": event.get("status") in {"processed", "duplicate"},
        "order_id": event.get("canonical_order_id"),
        "payment_id": event.get("canonical_payment_id"),
    }


async def _customer_for_intent(intent: dict, *, provider_event_id: str) -> dict:
    existing = await db.customers.find_one(
        {"tenant_id": intent["tenant_id"], "email": intent["buyer_email"]},
        {"_id": 0},
    )
    if existing:
        return serialize_doc(existing)
    customer = Customer(
        tenant_id=intent["tenant_id"],
        name=intent["buyer_name"],
        email=intent["buyer_email"],
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
    await db.orders.insert_one(prepare_for_mongo(order))
    items: list[dict] = []
    for idx, line in enumerate(intent.get("line_items") or []):
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
        await db.order_items.insert_one(prepare_for_mongo(item))
        items.append(serialize_doc(item))
    return serialize_doc(order), items


async def _create_payment(intent: dict, order: dict, customer: dict, event: WebstorePaymentEvent) -> dict:
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
        idempotency_key=f"webstore-payment:{event.provider}:{event.provider_payment_id}",
        confirmed_at=utc_now(),
        created_by="webstore-payment",
    ).model_dump()
    if event.provider == "local_test_provider":
        payment["dev_simulated"] = True
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
        )
        return "bridged", work_order["id"]
    except ValueError as exc:
        if str(exc) == "no_production_required_items":
            return "not_required", None
        return "failed", None


async def process_verified_payment_event(event_fields: dict[str, Any]) -> dict:
    provider = str(event_fields.get("provider") or "").strip().lower()
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

    event = WebstorePaymentEvent(
        tenant_id=tenant_id,
        webstore_id=intent["webstore_id"],
        purchase_intent_id=purchase_intent_id,
        provider=provider,
        provider_event_id=provider_event_id,
        provider_payment_id=provider_payment_id,
        amount_cents=int(event_fields.get("amount_cents") or 0),
        currency=str(event_fields.get("currency") or "usd").lower(),
        raw_event_snapshot=event_fields.get("raw_event_snapshot") or {},
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
) -> dict:
    intent = await db.webstore_purchase_intents.find_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "canonical_payment_id": payment_id},
        {"_id": 0},
    )
    if not intent:
        raise WebstoreError("webstore_payment_not_found", "Webstore payment not found", 404)

    from .payment_service import initiate_refund

    try:
        refund = await initiate_refund(
            tenant_id=tenant_id,
            payment_id=payment_id,
            amount_cents=amount_cents,
            reason=reason,
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            idempotency_key=idempotency_key,
        )
    except ValueError as exc:
        raise WebstoreError(str(exc), str(exc), 400) from exc

    source_payment = await db.payments.find_one({"tenant_id": tenant_id, "id": payment_id}, {"_id": 0})
    if source_payment and source_payment.get("dev_simulated"):
        now = utc_now()
        await db.payments.update_one(
            {"tenant_id": tenant_id, "id": refund["id"]},
            {"$set": {"status": "confirmed", "refunded_at": now, "updated_at": now.isoformat()}},
        )
        refund = serialize_doc(await db.payments.find_one({"tenant_id": tenant_id, "id": refund["id"]}, {"_id": 0}))

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
    if source_payment and source_payment.get("dev_simulated"):
        await db.payments.update_one(
            {"tenant_id": tenant_id, "id": payment_id},
            {"$set": {"status": refund_status, "updated_at": _now_iso()}},
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
        summary="Webstore refund recorded through canonical Payment service",
        metadata={"source_payment_id": payment_id, "amount_cents": refund.get("amount_cents"), "refund_status": refund_status},
    )
    ledger = await db.webstore_ledger_entries.find_one({"tenant_id": tenant_id, "source_type": "canonical_refund_payment", "source_id": refund["id"]}, {"_id": 0})
    return {"refund": refund, "ledger_entry": serialize_doc(ledger), "refund_status": refund_status}


async def record_webstore_payout_event(
    *,
    tenant_id: str,
    webstore_id: str,
    purchase_intent_id: str,
    amount_cents: int,
    provider_event_id: str,
    status: str,
) -> dict:
    intent = await db.webstore_purchase_intents.find_one({"tenant_id": tenant_id, "webstore_id": webstore_id, "id": purchase_intent_id}, {"_id": 0})
    if not intent or not intent.get("canonical_payment_id"):
        raise WebstoreError("paid_purchase_intent_required", "A verified paid Webstore purchase intent is required", 409)
    entry = WebstoreLedgerEntry(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        buyer_order_id=purchase_intent_id,
        entry_type="payout",
        amount_cents=amount_cents,
        basis_amount_cents=int(intent.get("total_cents") or 0),
        source_type="provider_payout_event",
        source_id=provider_event_id,
        status="posted" if status == "paid" else "adjusted",
        notes=f"Provider payout event status {status}",
    ).model_dump()
    await _insert_ledger_entry(entry)
    await db.webstore_purchase_intents.update_one(
        {"tenant_id": tenant_id, "id": purchase_intent_id},
        {"$set": {"payout_status": status, "updated_at": _now_iso()}},
    )
    saved = await db.webstore_ledger_entries.find_one({"tenant_id": tenant_id, "source_type": "provider_payout_event", "source_id": provider_event_id}, {"_id": 0})
    return {"ledger_entry": serialize_doc(saved), "payout_status": status}


async def record_webstore_dispute_event(
    *,
    tenant_id: str,
    webstore_id: str,
    purchase_intent_id: str,
    amount_cents: int,
    provider_event_id: str,
    status: str,
) -> dict:
    intent = await db.webstore_purchase_intents.find_one({"tenant_id": tenant_id, "webstore_id": webstore_id, "id": purchase_intent_id}, {"_id": 0})
    if not intent or not intent.get("canonical_payment_id"):
        raise WebstoreError("paid_purchase_intent_required", "A verified paid Webstore purchase intent is required", 409)
    entry_type = "dispute_release" if status in {"won", "released"} else "dispute_hold"
    amount = abs(amount_cents) if entry_type == "dispute_release" else -abs(amount_cents)
    entry = WebstoreLedgerEntry(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        buyer_order_id=purchase_intent_id,
        entry_type=entry_type,  # type: ignore[arg-type]
        amount_cents=amount,
        basis_amount_cents=int(intent.get("total_cents") or 0),
        source_type="provider_dispute_event",
        source_id=provider_event_id,
        notes=f"Provider dispute event status {status}",
    ).model_dump()
    await _insert_ledger_entry(entry)
    await db.webstore_purchase_intents.update_one(
        {"tenant_id": tenant_id, "id": purchase_intent_id},
        {"$set": {"dispute_status": status, "status": "disputed", "updated_at": _now_iso()}},
    )
    saved = await db.webstore_ledger_entries.find_one({"tenant_id": tenant_id, "source_type": "provider_dispute_event", "source_id": provider_event_id}, {"_id": 0})
    return {"ledger_entry": serialize_doc(saved), "dispute_status": status}
