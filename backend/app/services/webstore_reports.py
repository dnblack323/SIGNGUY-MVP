"""Canonical, Webstore-scoped report projections."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import serialize_doc
from .webstore_shared import _get_store, _require_staff_perm, _require_webstore_assignment_scope


async def _canonical_records(
    tenant_id: str,
    webstore_id: str,
    *,
    status: Optional[str] = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    intents = [
        serialize_doc(doc)
        async for doc in db.webstore_purchase_intents.find(
            {
                "tenant_id": tenant_id,
                "webstore_id": webstore_id,
                "canonical_order_id": {"$type": "string"},
            },
            {"_id": 0},
        )
    ]
    order_ids = [str(intent["canonical_order_id"]) for intent in intents]
    orders = [
        serialize_doc(doc)
        async for doc in db.orders.find(
            {
                "tenant_id": tenant_id,
                "id": {"$in": order_ids},
                "source_type": "webstore_purchase_intent",
            },
            {"_id": 0},
        )
    ] if order_ids else []
    order_map = {str(order["id"]): order for order in orders}
    if status:
        intents = [intent for intent in intents if order_map.get(str(intent["canonical_order_id"]), {}).get("status") == status]
    filtered_order_ids = [str(intent["canonical_order_id"]) for intent in intents if str(intent["canonical_order_id"]) in order_map]
    items = [
        serialize_doc(doc)
        async for doc in db.order_items.find(
            {"tenant_id": tenant_id, "order_id": {"$in": filtered_order_ids}},
            {"_id": 0},
        )
    ] if filtered_order_ids else []
    payments = [
        serialize_doc(doc)
        async for doc in db.payments.find(
            {"tenant_id": tenant_id, "order_id": {"$in": filtered_order_ids}},
            {"_id": 0},
        )
    ] if filtered_order_ids else []
    return intents, [order_map[order_id] for order_id in filtered_order_ids], items, payments


def _canonical_ledger_totals(ledger: list[dict[str, Any]]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for entry in ledger:
        entry_type = str(entry.get("entry_type") or "unknown")
        totals[entry_type] = totals.get(entry_type, 0) + int(entry.get("amount_cents") or 0)
    return totals


async def staff_report(
    user: dict[str, Any],
    webstore_id: str,
    *,
    status: Optional[str] = None,
) -> dict[str, Any]:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    await _require_webstore_assignment_scope(user, webstore_id)
    await _get_store(user["tenant_id"], webstore_id)
    intents, orders, items, payments = await _canonical_records(user["tenant_id"], webstore_id, status=status)
    intent_ids = [str(intent["id"]) for intent in intents]
    ledger = [
        serialize_doc(doc)
        async for doc in db.webstore_ledger_entries.find(
            {
                "tenant_id": user["tenant_id"],
                "webstore_id": webstore_id,
                "$or": [
                    {"source_id": {"$in": intent_ids}},
                    {"buyer_order_id": {"$in": intent_ids}},
                ],
            },
            {"_id": 0},
        )
    ] if intent_ids else []
    order_by_id = {str(order["id"]): order for order in orders}
    payment_by_order: dict[str, list[dict[str, Any]]] = {}
    for payment in payments:
        payment_by_order.setdefault(str(payment.get("order_id")), []).append(payment)
    quantities: Counter[str] = Counter()
    for item in items:
        snapshot = (item.get("pricing_snapshot") or {}).get("line_item") or {}
        key = str(snapshot.get("product_id") or item.get("description") or "unknown")
        quantities[key] += int(item.get("quantity") or 0)
    fulfillment_counts = Counter(str(intent.get("fulfillment_status") or "not_started") for intent in intents)
    production_counts = Counter(str(intent.get("production_bridge_status") or "not_started") for intent in intents)
    failed_payments = sum(1 for payment in payments if payment.get("status") == "failed")
    paid_total = sum(
        int(order.get("amount_paid_cents") or 0)
        for order in orders
    )
    gross = sum(int(order.get("total_cents") or 0) for order in orders)
    ledger_totals = _canonical_ledger_totals(ledger)
    return {
        "webstore_id": webstore_id,
        "source_of_truth": "canonical_orders_payments_and_provider_ledger",
        "order_count": len(orders),
        "canonical_order_count": len(orders),
        "legacy_order_count": 0,
        "gross_sales_cents": gross,
        "paid_total_cents": paid_total,
        "refund_total_cents": abs(ledger_totals.get("refund", 0)),
        "payout_total_cents": ledger_totals.get("payout", 0),
        "provider_fee_cents": abs(ledger_totals.get("payment_processing_fee", 0)),
        "platform_fee_cents": abs(ledger_totals.get("platform_usage_fee", 0)),
        "dispute_hold_cents": abs(ledger_totals.get("dispute_hold", 0)),
        "failed_payment_count": failed_payments,
        "fulfillment_counts": dict(fulfillment_counts),
        "production_bridge_counts": dict(production_counts),
        "product_quantities": dict(quantities),
        "ledger_totals_cents": ledger_totals,
        "production_load": {
            "production_required_items": sum(1 for item in items if item.get("production_required")),
            "orders_awaiting_handoff": production_counts.get("not_started", 0),
            "orders_bridged": production_counts.get("bridged", 0),
        },
        "deadline_risk_count": sum(
            1
            for order in orders
            if order.get("due_date")
            and str(order["due_date"]) < datetime.now(timezone.utc).isoformat()
            and order.get("status") not in {"completed", "cancelled", "archived"}
        ),
        "payment_order_ids": sorted(order_by_id),
    }


async def owner_summary(tenant_id: str, webstore_id: str) -> dict[str, Any]:
    """Return only owner-safe canonical commerce summary fields."""
    intents, orders, _items, _payments = await _canonical_records(tenant_id, webstore_id)
    intent_ids = [str(intent["id"]) for intent in intents]
    ledger = [
        serialize_doc(doc)
        async for doc in db.webstore_ledger_entries.find(
            {
                "tenant_id": tenant_id,
                "webstore_id": webstore_id,
                "$or": [
                    {"source_id": {"$in": intent_ids}},
                    {"buyer_order_id": {"$in": intent_ids}},
                ],
            },
            {"_id": 0},
        )
    ] if intent_ids else []
    ledger_totals = _canonical_ledger_totals(ledger)
    quantities: Counter[str] = Counter()
    for intent in intents:
        for line in intent.get("line_items") or []:
            key = str(line.get("product_id") or line.get("name") or "unknown")
            quantities[key] += int(line.get("quantity") or 0)
    payout_statuses = Counter(str(intent.get("payout_status") or "pending") for intent in intents)
    return {
        "order_count": len(orders),
        "gross_sales_cents": sum(int(order.get("total_cents") or 0) for order in orders),
        "refund_total_cents": abs(ledger_totals.get("refund", 0)),
        "payout_total_cents": ledger_totals.get("payout", 0),
        "provider_fee_cents": abs(ledger_totals.get("payment_processing_fee", 0)),
        "payout_status_counts": dict(payout_statuses),
        "dispute_hold_cents": abs(ledger_totals.get("dispute_hold", 0)),
        "product_quantities": dict(quantities),
        "source_of_truth": "canonical_orders_and_provider_ledger",
    }
