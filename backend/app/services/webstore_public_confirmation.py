"""Public token-bound Webstore confirmation receipts."""
from __future__ import annotations

from .webstore_shared import *

async def public_confirmation(slug: str, confirmation_token: str) -> dict:
    # Historical receipts remain available after close/archive, but only with
    # the token issued for that purchase. No arbitrary Order ID is accepted.
    full_store = await db.webstores.find_one({"public_slug": slug}, {"_id": 0})
    if not full_store:
        raise WebstoreError("confirmation_not_found", "Webstore confirmation was not found", 404)
    intent = await db.webstore_purchase_intents.find_one(
        {
            "tenant_id": full_store["tenant_id"],
            "webstore_id": full_store["id"],
            "public_slug": slug,
            "confirmation_token": confirmation_token,
            "canonical_order_id": {"$type": "string"},
        },
        {"_id": 0},
    )
    if not intent:
        raise WebstoreError("confirmation_not_found", "Webstore confirmation was not found", 404)
    order = await db.orders.find_one({"tenant_id": full_store["tenant_id"], "id": intent.get("canonical_order_id")}, {"_id": 0})
    return {
        "purchase_intent": {
            "id": intent.get("id"),
            "buyer_name": intent.get("buyer_name"),
            "buyer_email": intent.get("buyer_email"),
            "total_cents": int(intent.get("total_cents") or 0),
            "currency": intent.get("currency") or "usd",
            "status": intent.get("status"),
            "fulfillment_status": intent.get("fulfillment_status"),
        },
        "order": {
            "number": (order or {}).get("number"),
            "status": (order or {}).get("status"),
            "total_cents": int(intent.get("total_cents") or 0),
        },
        "payment_status": intent.get("status"),
        "fulfillment_status": intent.get("fulfillment_status"),
    }
