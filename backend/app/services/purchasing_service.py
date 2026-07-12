"""EC7 phase 7b — Purchasing service.

Owns PurchaseOrder + PurchaseOrderLine lifecycle:
  - create draft PO (from cart / recommendation / manual)
  - add / update / remove lines
  - backend-computed totals
  - submit via connector (idempotent)
  - cancel with reason
  - acknowledgement + tracking

Receiving lives in `receiving_service.py`.
"""
from __future__ import annotations
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import serialize_doc, utc_now
from ..models.purchase_order import PurchaseOrder, PurchaseOrderLine
from ..services.audit import record_audit
from ..services.sequence import next_number
from ..services.supplier_connectors import get_connector, ConnectorCapability


async def _recompute_po_totals(*, tenant_id: str, purchase_order_id: str) -> dict:
    """Sum line extensions + freight/handling snapshot from PO record."""
    subtotal = 0
    async for line in db.purchase_order_lines.find(
        {"tenant_id": tenant_id, "purchase_order_id": purchase_order_id}, {"_id": 0}
    ):
        subtotal += int(line.get("line_extended_cents", 0))
    po = await db.purchase_orders.find_one(
        {"tenant_id": tenant_id, "id": purchase_order_id}, {"_id": 0}
    )
    if not po:
        return {}
    shipping = int(po.get("shipping_cents", 0))
    handling = int(po.get("handling_cents", 0))
    tax = int(po.get("tax_cents", 0))
    total = subtotal + shipping + handling + tax
    await db.purchase_orders.update_one(
        {"tenant_id": tenant_id, "id": purchase_order_id},
        {"$set": {"subtotal_cents": subtotal, "total_cents": total,
                  "updated_at": utc_now().isoformat()}}
    )
    return {"subtotal_cents": subtotal, "shipping_cents": shipping,
            "handling_cents": handling, "tax_cents": tax, "total_cents": total}


async def create_draft(*, tenant_id: str, vendor_id: str, actor_user_id: str,
                       actor_email: str,
                       ship_to_location_id: Optional[str] = None,
                       source_recommendation_key: Optional[str] = None,
                       source_priority: Optional[str] = None,
                       notes: Optional[str] = None) -> dict:
    vendor = await db.vendors.find_one({"tenant_id": tenant_id, "id": vendor_id}, {"_id": 0})
    if not vendor:
        raise ValueError("vendor_not_found")
    number = await next_number(tenant_id=tenant_id, name="purchase_order")
    po = PurchaseOrder(
        tenant_id=tenant_id, number=number, vendor_id=vendor_id,
        vendor_snapshot={"id": vendor["id"], "name": vendor["name"],
                         "connector_key": vendor["connector_key"]},
        created_by_user_id=actor_user_id,
        ship_to_location_id=ship_to_location_id,
        source_recommendation_key=source_recommendation_key,
        source_priority=source_priority,
        notes=notes,
    ).model_dump()
    await db.purchase_orders.insert_one(po)
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="purchase_order.create", entity_type="purchase_order", entity_id=po["id"],
        summary=f"Created draft PO #{number} for vendor {vendor['name']}",
    )
    po.pop("_id", None)
    return serialize_doc(po)


async def add_line(*, tenant_id: str, purchase_order_id: str, actor_user_id: str,
                   actor_email: str, payload: dict) -> dict:
    po = await db.purchase_orders.find_one(
        {"tenant_id": tenant_id, "id": purchase_order_id}, {"_id": 0}
    )
    if not po:
        raise ValueError("purchase_order_not_found")
    if po["status"] not in ("draft",):
        raise ValueError("purchase_order_not_editable")
    line = PurchaseOrderLine(
        tenant_id=tenant_id, purchase_order_id=purchase_order_id,
        position=int(payload.get("position", 0)),
        material_id=payload.get("material_id"),
        supplier_product_id=payload.get("supplier_product_id"),
        supplier_warehouse_id=payload.get("supplier_warehouse_id"),
        order_id=payload.get("order_id"),
        order_item_id=payload.get("order_item_id"),
        supplier_sku=payload.get("supplier_sku"),
        description=payload["description"],
        manufacturer=payload.get("manufacturer"),
        brand=payload.get("brand"),
        variant=payload.get("variant", {}),
        quantity_ordered=float(payload["quantity_ordered"]),
        unit_of_measure=payload.get("unit_of_measure", "each"),
        package_qty=int(payload.get("package_qty", 1)),
        unit_price_cents=int(payload.get("unit_price_cents", 0)),
        line_extended_cents=int(payload.get("unit_price_cents", 0)) * int(payload["quantity_ordered"]),
    ).model_dump()
    await db.purchase_order_lines.insert_one(line)
    await _recompute_po_totals(tenant_id=tenant_id, purchase_order_id=purchase_order_id)
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="purchase_order.line_add", entity_type="purchase_order",
        entity_id=purchase_order_id, summary=f"Added line: {line['description']}",
        diff={"quantity": line["quantity_ordered"], "unit_price_cents": line["unit_price_cents"]},
    )
    line.pop("_id", None)
    return serialize_doc(line)


async def set_freight(*, tenant_id: str, purchase_order_id: str,
                      shipping_cents: int = 0, handling_cents: int = 0,
                      tax_cents: int = 0,
                      warehouse_splits: Optional[list[dict]] = None) -> dict:
    await db.purchase_orders.update_one(
        {"tenant_id": tenant_id, "id": purchase_order_id},
        {"$set": {"shipping_cents": int(shipping_cents),
                  "handling_cents": int(handling_cents),
                  "tax_cents": int(tax_cents),
                  "warehouse_splits": warehouse_splits or [],
                  "updated_at": utc_now().isoformat()}}
    )
    return await _recompute_po_totals(tenant_id=tenant_id, purchase_order_id=purchase_order_id)


async def submit(*, tenant_id: str, purchase_order_id: str, actor_user_id: str,
                 actor_email: str, idempotency_key: str,
                 confirm: bool = True) -> dict:
    """Submit the PO to the supplier connector. Requires explicit confirm=True."""
    if not confirm:
        raise ValueError("explicit_confirmation_required")
    if not idempotency_key:
        raise ValueError("idempotency_key_required")
    # Idempotency replay: if a supplier-order log already exists for this key,
    # short-circuit BEFORE any status check so re-submit of the same request
    # is safe even after the PO transitioned to acknowledged.
    replay = await db.supplier_order_log.find_one(
        {"tenant_id": tenant_id, "idempotency_key": idempotency_key}, {"_id": 0}
    )
    if replay:
        return {
            "status": "duplicate_replay",
            "supplier_order_id": replay.get("supplier_order_id"),
            "tracking_number": replay.get("tracking_number"),
            "log_id": replay.get("id"),
        }
    po = await db.purchase_orders.find_one(
        {"tenant_id": tenant_id, "id": purchase_order_id}, {"_id": 0}
    )
    if not po:
        raise ValueError("purchase_order_not_found")
    if po["status"] not in ("draft", "submitted"):
        raise ValueError(f"purchase_order_status_not_submittable:{po['status']}")
    vendor = await db.vendors.find_one({"id": po["vendor_id"], "tenant_id": tenant_id}, {"_id": 0})
    connector = get_connector(vendor["connector_key"])
    lines = [
        d async for d in db.purchase_order_lines.find(
            {"tenant_id": tenant_id, "purchase_order_id": purchase_order_id}, {"_id": 0}
        )
    ]
    submit_capable = connector.supports(ConnectorCapability.SUBMIT_ORDER)
    if not submit_capable:
        # Manual / feed-only: mark as submitted (handoff) with a NULL supplier order id.
        await db.purchase_orders.update_one(
            {"tenant_id": tenant_id, "id": purchase_order_id},
            {"$set": {"status": "submitted", "submitted_at": utc_now().isoformat(),
                      "updated_at": utc_now().isoformat()}}
        )
        return {"status": "submitted_manual_handoff", "supplier_order_id": None}
    result = await connector.create_supplier_order(
        tenant_id=tenant_id, vendor_id=po["vendor_id"],
        purchase_order={**po, "lines": lines},
        idempotency_key=idempotency_key,
        actor_user_id=actor_user_id,
    )
    log = result.get("log") or {}
    updates = {
        "status": "acknowledged" if result.get("status") == "accepted" else "submitted",
        "submitted_at": utc_now().isoformat(),
        "acknowledged_at": utc_now().isoformat() if result.get("status") == "accepted" else None,
        "supplier_order_id": log.get("supplier_order_id"),
        "tracking_number": log.get("tracking_number"),
        "tracking_status": log.get("tracking_status"),
        "updated_at": utc_now().isoformat(),
    }
    if log.get("id"):
        updates["supplier_order_log_ids"] = po.get("supplier_order_log_ids", []) + [log["id"]]
    await db.purchase_orders.update_one(
        {"tenant_id": tenant_id, "id": purchase_order_id}, {"$set": updates}
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="purchase_order.submit", entity_type="purchase_order",
        entity_id=purchase_order_id,
        summary=f"Submitted PO #{po['number']} to {vendor['name']} (status={result.get('status')})",
        diff={"idempotency_key": idempotency_key, "supplier_order_id": log.get("supplier_order_id")},
    )
    return {"status": result.get("status"), "supplier_order_id": log.get("supplier_order_id"),
            "tracking_number": log.get("tracking_number"),
            "log_id": log.get("id")}


async def cancel(*, tenant_id: str, purchase_order_id: str, actor_user_id: str,
                 actor_email: str, reason: str) -> dict:
    if not reason or not reason.strip():
        raise ValueError("cancel_reason_required")
    po = await db.purchase_orders.find_one(
        {"tenant_id": tenant_id, "id": purchase_order_id}, {"_id": 0}
    )
    if not po:
        raise ValueError("purchase_order_not_found")
    if po["status"] in ("received", "cancelled"):
        raise ValueError(f"purchase_order_status_not_cancellable:{po['status']}")
    if po.get("supplier_order_id"):
        vendor = await db.vendors.find_one({"id": po["vendor_id"], "tenant_id": tenant_id}, {"_id": 0})
        try:
            connector = get_connector(vendor["connector_key"])
            if connector.supports(ConnectorCapability.CANCEL):
                await connector.cancel_order(
                    tenant_id=tenant_id, vendor_id=po["vendor_id"],
                    supplier_order_id=po["supplier_order_id"], reason=reason,
                )
        except Exception:
            pass
    await db.purchase_orders.update_one(
        {"tenant_id": tenant_id, "id": purchase_order_id},
        {"$set": {"status": "cancelled", "cancelled_at": utc_now().isoformat(),
                  "cancelled_reason": reason, "updated_at": utc_now().isoformat()}}
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="purchase_order.cancel", entity_type="purchase_order",
        entity_id=purchase_order_id, summary=f"Cancelled PO #{po['number']}",
        diff={"reason": reason},
    )
    return {"cancelled": True}


async def poll_tracking(*, tenant_id: str, purchase_order_id: str) -> dict:
    po = await db.purchase_orders.find_one(
        {"tenant_id": tenant_id, "id": purchase_order_id}, {"_id": 0}
    )
    if not po or not po.get("supplier_order_id"):
        return {"status": "no_supplier_order"}
    vendor = await db.vendors.find_one({"id": po["vendor_id"], "tenant_id": tenant_id}, {"_id": 0})
    connector = get_connector(vendor["connector_key"])
    if not connector.supports(ConnectorCapability.TRACKING):
        return {"status": "not_supported"}
    tr = await connector.retrieve_tracking(
        tenant_id=tenant_id, vendor_id=po["vendor_id"],
        supplier_order_id=po["supplier_order_id"]
    )
    await db.purchase_orders.update_one(
        {"tenant_id": tenant_id, "id": purchase_order_id},
        {"$set": {"tracking_status": tr.get("status"),
                  "tracking_number": tr.get("tracking_number"),
                  "updated_at": utc_now().isoformat()}}
    )
    return tr
