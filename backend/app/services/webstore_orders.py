"""Webstore-scoped projections over the canonical Orders data."""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import serialize_doc
from .webstore_context import WebstoreError
from .webstore_shared import _get_store, _require_staff_perm, _require_webstore_assignment_scope


def _safe_item_snapshot(item: dict[str, Any]) -> dict[str, Any]:
    source = item.get("pricing_snapshot") or {}
    line = source.get("line_item") if isinstance(source, dict) else None
    line = line if isinstance(line, dict) else {}
    allowed_line_fields = {
        "product_id",
        "variant_id",
        "category_id",
        "name",
        "variant",
        "selected_options",
        "personalization",
        "quantity",
        "unit_price_cents",
        "line_total_cents",
        "shipping_cents",
        "fulfillment_method",
        "image_reference",
        "production_mapping",
    }
    snapshot = {
        key: line[key]
        for key in allowed_line_fields
        if key in line
    }
    snapshot.setdefault("product_id", item.get("saved_item_id"))
    snapshot.setdefault("name", item.get("description") or item.get("item_name"))
    snapshot.setdefault("quantity", item.get("quantity", 0))
    snapshot.setdefault("unit_price_cents", item.get("unit_price_cents", 0))
    snapshot.setdefault("line_total_cents", item.get("line_total_cents", 0))
    return {
        "id": item.get("id"),
        "position": item.get("position", 0),
        "description": item.get("description"),
        "sku": item.get("sku"),
        "quantity": item.get("quantity", 0),
        "unit_price_cents": item.get("unit_price_cents", 0),
        "line_subtotal_cents": item.get("line_subtotal_cents", 0),
        "line_total_cents": item.get("line_total_cents", 0),
        "production_required": bool(item.get("production_required")),
        "snapshot": snapshot,
    }


def _safe_payment(payment: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not payment:
        return None
    return {
        "id": payment.get("id"),
        "status": payment.get("status"),
        "source": payment.get("source"),
        "amount_cents": payment.get("amount_cents", 0),
        "currency": payment.get("currency", "usd"),
        "confirmed_at": payment.get("confirmed_at"),
        "failed_at": payment.get("failed_at"),
    }


async def list_webstore_orders(
    user: dict[str, Any],
    webstore_id: str,
    *,
    status: Optional[str] = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Return staff-safe Webstore orders from canonical records only."""
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    await _require_webstore_assignment_scope(user, webstore_id)
    await _get_store(user["tenant_id"], webstore_id)

    intent_filter: dict[str, Any] = {
        "tenant_id": user["tenant_id"],
        "webstore_id": webstore_id,
        "canonical_order_id": {"$type": "string"},
    }
    intents = [
        serialize_doc(doc)
        async for doc in db.webstore_purchase_intents.find(intent_filter, {"_id": 0})
        .sort([("created_at", -1)])
    ]
    order_ids = [str(intent["canonical_order_id"]) for intent in intents]
    if not order_ids:
        return {
            "webstore_id": webstore_id,
            "source_of_truth": "canonical_orders",
            "items": [],
            "total": 0,
        }

    orders = {
        str(doc["id"]): serialize_doc(doc)
        async for doc in db.orders.find(
            {
                "tenant_id": user["tenant_id"],
                "id": {"$in": order_ids},
                "source_type": "webstore_purchase_intent",
            },
            {"_id": 0},
        )
    }
    if status:
        intents = [intent for intent in intents if orders.get(str(intent["canonical_order_id"]), {}).get("status") == status]
    intents = intents[:limit]

    filtered_order_ids = [str(intent["canonical_order_id"]) for intent in intents if str(intent["canonical_order_id"]) in orders]
    item_groups: dict[str, list[dict[str, Any]]] = {order_id: [] for order_id in filtered_order_ids}
    async for doc in db.order_items.find(
        {"tenant_id": user["tenant_id"], "order_id": {"$in": filtered_order_ids}},
        {"_id": 0},
    ).sort([("position", 1)]):
        if doc.get("order_id") in item_groups:
            item_groups[doc["order_id"]].append(_safe_item_snapshot(serialize_doc(doc)))

    payment_groups: dict[str, list[dict[str, Any]]] = {order_id: [] for order_id in filtered_order_ids}
    async for doc in db.payments.find(
        {"tenant_id": user["tenant_id"], "order_id": {"$in": filtered_order_ids}},
        {"_id": 0},
    ).sort([("created_at", -1)]):
        if doc.get("order_id") in payment_groups:
            payment_groups[doc["order_id"]].append(serialize_doc(doc))

    customer_ids = {str(order.get("customer_id")) for order in orders.values() if order.get("customer_id")}
    customers = {
        str(doc["id"]): serialize_doc(doc)
        async for doc in db.customers.find(
            {"tenant_id": user["tenant_id"], "id": {"$in": list(customer_ids)}},
            {"_id": 0},
        )
    }

    projections = []
    for intent in intents:
        order = orders.get(str(intent["canonical_order_id"]))
        if not order:
            continue
        customer = customers.get(str(order.get("customer_id")), {})
        payments = payment_groups.get(order["id"], [])
        projections.append(
            {
                "id": order.get("id"),
                "number": order.get("number"),
                "status": order.get("status"),
                "created_at": order.get("created_at"),
                "customer": {
                    "id": customer.get("id"),
                    "name": customer.get("name"),
                    "email": customer.get("email"),
                    "phone": customer.get("phone"),
                },
                "subtotal_cents": order.get("subtotal_cents", 0),
                "discount_cents": order.get("discount_cents", 0),
                "tax_cents": order.get("tax_cents", 0),
                "total_cents": order.get("total_cents", 0),
                "amount_paid_cents": order.get("amount_paid_cents", 0),
                "balance_cents": order.get("balance_cents", 0),
                "source": {
                    "webstore_id": webstore_id,
                    "purchase_intent_id": intent.get("id"),
                },
                "fulfillment": {
                    "method": intent.get("fulfillment_method"),
                    "status": intent.get("fulfillment_status") or "awaiting_production_handoff",
                    "production_bridge_status": intent.get("production_bridge_status") or "not_started",
                    "work_order_id": intent.get("work_order_id"),
                },
                "payment": _safe_payment(payments[0] if payments else None),
                "items": item_groups.get(order["id"], []),
            }
        )
    return {
        "webstore_id": webstore_id,
        "source_of_truth": "canonical_orders",
        "items": projections,
        "total": len(projections),
    }
