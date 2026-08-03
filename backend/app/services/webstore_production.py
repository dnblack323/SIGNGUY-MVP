"""Webstore adapter for the canonical Work Order and production system."""
from __future__ import annotations

from typing import Any

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import serialize_doc
from . import work_order_service
from .webstores import WebstoreError, _audit, _get_store, _require_staff_perm, _require_webstore_assignment_scope


async def handoff_webstore_order_to_production(
    user: dict[str, Any],
    webstore_id: str,
    order_id: str,
) -> dict[str, Any]:
    """Create or reuse the current canonical Work Order for one paid order."""
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    _require_staff_perm(user, Perm.WORK_ORDER_WRITE)
    await _require_webstore_assignment_scope(user, webstore_id)
    await _get_store(user["tenant_id"], webstore_id)

    intent = await db.webstore_purchase_intents.find_one(
        {
            "tenant_id": user["tenant_id"],
            "webstore_id": webstore_id,
            "canonical_order_id": order_id,
        },
        {"_id": 0},
    )
    if not intent:
        raise WebstoreError("webstore_order_not_found", "Canonical Webstore order not found", 404)
    if intent.get("status") not in {"paid_order_created", "handoff_processing"}:
        raise WebstoreError("paid_order_required", "Only a verified paid Webstore order can enter production", 409)

    order = await db.orders.find_one(
        {
            "tenant_id": user["tenant_id"],
            "id": order_id,
            "source_type": "webstore_purchase_intent",
            "source_id": intent["id"],
        },
        {"_id": 0},
    )
    if not order:
        raise WebstoreError("canonical_order_not_found", "Canonical Webstore Order not found", 404)

    existing_work_order = await db.work_orders.find_one(
        {"tenant_id": user["tenant_id"], "order_id": order_id, "current_version": True},
        {"_id": 0},
    )
    if existing_work_order:
        await db.webstore_purchase_intents.update_one(
            {"tenant_id": user["tenant_id"], "id": intent["id"]},
            {
                "$set": {
                    "production_bridge_status": "bridged",
                    "fulfillment_status": "in_production",
                    "work_order_id": existing_work_order["id"],
                }
            },
        )
        return {
            "already_bridged": True,
            "order_id": order_id,
            "work_order": serialize_doc(existing_work_order),
        }

    try:
        work_order, already_exists = await work_order_service.generate(
            tenant_id=user["tenant_id"],
            order_id=order_id,
            actor_user_id=user["id"],
            actor_email=user.get("email") or "",
            production_instructions=f"Generated from Webstore purchase intent {intent['id']}",
            source_context={"webstore_id": webstore_id, "purchase_intent_id": intent["id"]},
        )
    except ValueError as exc:
        if str(exc) == "no_production_required_items":
            await db.webstore_purchase_intents.update_one(
                {"tenant_id": user["tenant_id"], "id": intent["id"]},
                {
                    "$set": {
                        "production_bridge_status": "not_required",
                        "fulfillment_status": "not_required",
                    }
                },
            )
            await _audit(
                tenant_id=user["tenant_id"],
                webstore_id=webstore_id,
                actor_type="staff",
                actor_id=user["id"],
                actor_email=user.get("email"),
                action="webstore.production_handoff_not_required",
                entity_type="order",
                entity_id=order_id,
                summary="Webstore order has no production-required items",
                metadata={"purchase_intent_id": intent["id"]},
            )
            return {"already_bridged": False, "not_required": True, "order_id": order_id, "work_order": None}
        raise

    await db.webstore_purchase_intents.update_one(
        {"tenant_id": user["tenant_id"], "id": intent["id"]},
        {
            "$set": {
                "production_bridge_status": "bridged",
                "fulfillment_status": "in_production",
                "work_order_id": work_order["id"],
            }
        },
    )
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user["id"],
        actor_email=user.get("email"),
        action="webstore.production_handoff_completed",
        entity_type="order",
        entity_id=order_id,
        summary="Webstore order sent to canonical production",
        metadata={"purchase_intent_id": intent["id"], "work_order_id": work_order["id"]},
    )
    return {
        "already_bridged": already_exists,
        "order_id": order_id,
        "work_order": work_order,
    }
