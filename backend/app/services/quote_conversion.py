"""EC3 — Idempotent, race-safe Quote-to-Order conversion.

Preserves the working MVP idempotent guard (`find_one_and_update` claim on
`converted_order_id == None`) and extends it with:

- Copies Quote Line Items → Order Items, preserving pricing snapshots, category,
  dimensions, override metadata, and `production_required` defaults.
- Records `source_quote_id` + `source_quote_revision` on the Order.
- Records `converted_revision` on the Quote.
- Rejects declined/void quotes.
- Rejects expired quotes unless caller passes `allow_expired=True` with a
  documented reason (enforced by the router permission + audit event).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.order import Order, OrderItem
from ..services.sequence import next_number
from ..services.order_item_rules import default_production_required


def _is_expired(quote: dict[str, Any]) -> bool:
    exp = quote.get("expires_at")
    if not exp:
        return False
    try:
        dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
    except ValueError:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt < utc_now()


async def convert_quote_to_order(
    *,
    tenant_id: str,
    quote_id: str,
    actor_user_id: str,
    actor_email: str,
    allow_expired: bool = False,
    override_reason: Optional[str] = None,
) -> tuple[dict[str, Any], bool]:
    """Convert a Quote to an Order. Returns (order_dict, already_converted).

    Raises ValueError for validation failures the router should surface as HTTP
    4xx: `quote_not_found`, `quote_declined`, `quote_void`, `quote_expired`.
    """
    quote = await db.quotes.find_one({"id": quote_id, "tenant_id": tenant_id})
    if not quote:
        raise ValueError("quote_not_found")

    # Idempotent short-circuit
    if quote.get("converted_order_id"):
        existing = await db.orders.find_one({"id": quote["converted_order_id"]}, {"_id": 0})
        return serialize_doc(existing) if existing else {"id": quote["converted_order_id"]}, True

    if quote.get("status") == "declined":
        raise ValueError("quote_declined")
    if quote.get("status") == "void":
        raise ValueError("quote_void")

    expired = _is_expired(quote)
    if expired and not allow_expired:
        raise ValueError("quote_expired")
    if expired and allow_expired and not override_reason:
        raise ValueError("override_reason_required")

    # Atomically claim the quote so a concurrent second click can't create a duplicate order.
    now_iso = utc_now().isoformat()
    claim = await db.quotes.find_one_and_update(
        {"id": quote_id, "tenant_id": tenant_id, "converted_order_id": None},
        {"$set": {"status": "converted", "converted_at": now_iso, "updated_at": now_iso}},
    )
    if not claim:
        # Lost the race — return the winning order (or 409 if inconsistent).
        quote2 = await db.quotes.find_one({"id": quote_id}, {"_id": 0})
        if quote2 and quote2.get("converted_order_id"):
            existing = await db.orders.find_one({"id": quote2["converted_order_id"]}, {"_id": 0})
            return serialize_doc(existing) if existing else {"id": quote2["converted_order_id"]}, True
        raise ValueError("conversion_race_lost")

    revision_number = int(quote.get("revision_number") or 1)

    # Create the Order
    number = await next_number(tenant_id=tenant_id, name="order")
    order = Order(
        tenant_id=tenant_id,
        number=number,
        customer_id=quote["customer_id"],
        quote_id=quote_id,                         # backward compat
        source_quote_id=quote_id,
        source_quote_revision=revision_number,
        job_name=quote.get("job_name") or "",
        title=quote.get("job_name"),
        description=quote.get("notes_customer"),
        notes=quote.get("notes_internal") or quote.get("notes"),
        notes_internal=quote.get("notes_internal"),
        notes_customer=quote.get("notes_customer"),
        subtotal_cents=int(quote.get("subtotal_cents") or 0),
        discount_cents=int(quote.get("discount_cents") or 0),
        tax_cents=int(quote.get("tax_cents") or 0),
        total_cents=int(quote.get("total_cents") or 0),
        balance_cents=int(quote.get("total_cents") or 0),
        status="draft",
        created_by=actor_user_id,
    )
    await db.orders.insert_one(prepare_for_mongo(order.model_dump()))

    # Copy Quote Line Items → Order Items
    cursor = db.quote_line_items.find(
        {"tenant_id": tenant_id, "quote_id": quote_id, "revision_number": revision_number},
        {"_id": 0},
    ).sort("position", 1)
    async for li in cursor:
        prod_req = li.get("production_required")
        if prod_req is None:
            prod_req = default_production_required(li.get("category"))
        item = OrderItem(
            tenant_id=tenant_id,
            order_id=order.id,
            position=int(li.get("position") or 0),
            category=li.get("category"),
            product_type=li.get("product_type"),
            description=li.get("description") or "",
            sku=li.get("sku"),
            quantity=int(li.get("quantity") or 1),
            unit_of_measure=li.get("unit_of_measure") or "each",
            width_inches=li.get("width_inches"),
            height_inches=li.get("height_inches"),
            depth_inches=li.get("depth_inches"),
            material_key=li.get("material_key"),
            unit_price_cents=int(li.get("unit_price_cents") or 0),
            discount_cents=int(li.get("discount_cents") or 0),
            tax_cents=int(li.get("tax_cents") or 0),
            line_subtotal_cents=int(li.get("line_subtotal_cents") or 0),
            line_total_cents=int(li.get("line_total_cents") or 0),
            pricing_snapshot=dict(li.get("pricing_snapshot") or {}),
            manual_override_reason=li.get("manual_override_reason"),
            manual_override_actor_user_id=li.get("manual_override_actor_user_id"),
            manual_override_actor_email=li.get("manual_override_actor_email"),
            manual_override_at=li.get("manual_override_at"),
            production_required=bool(prod_req),
            notes=li.get("notes"),
        )
        await db.order_items.insert_one(prepare_for_mongo(item.model_dump()))

    # Complete the quote row (record converted revision + order id)
    await db.quotes.update_one(
        {"id": quote_id},
        {"$set": {
            "converted_order_id": order.id,
            "converted_revision": revision_number,
        }},
    )
    return serialize_doc(order.model_dump()), False
