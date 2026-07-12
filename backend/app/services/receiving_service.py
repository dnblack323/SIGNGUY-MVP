"""EC7 phase 7b — Receiving service.

Receives against a PO — partial or full. Every receive action creates:
  1. An immutable `receiving_records` row (idempotency-key unique per master
     plan §7 — replay is a no-op).
  2. One `inventory_movements` row per line via `inventory_service.receive`.
  3. A `material_cost_history` row when unit_price differs from the current
     material cost (preserves historical pricing snapshots).

Double-receive prevention: quantity_received on the PO line is monotonic and
capped at quantity_ordered.
"""
from __future__ import annotations
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import serialize_doc, utc_now
from ..models.material import MaterialCostHistory
from ..models.purchase_order import ReceivingRecord
from ..services import inventory_service
from ..services.audit import record_audit


async def receive(*, tenant_id: str, purchase_order_id: str, actor_user_id: str,
                  actor_email: str, idempotency_key: str,
                  lines: list[dict[str, Any]], default_location_id: Optional[str] = None,
                  notes: Optional[str] = None) -> dict:
    """
    :param lines: list of {"po_line_id": str, "quantity": float, "location_id"?}
        `location_id` defaults to `default_location_id` or the PO ship_to.
    """
    if not idempotency_key:
        raise ValueError("idempotency_key_required")
    if not lines:
        raise ValueError("no_lines_to_receive")
    # Idempotency replay: return existing record verbatim.
    existing = await db.receiving_records.find_one(
        {"tenant_id": tenant_id, "purchase_order_id": purchase_order_id,
         "idempotency_key": idempotency_key}, {"_id": 0}
    )
    if existing:
        existing.pop("_id", None)
        return {"replayed": True, "record": serialize_doc(existing)}

    po = await db.purchase_orders.find_one(
        {"tenant_id": tenant_id, "id": purchase_order_id}, {"_id": 0}
    )
    if not po:
        raise ValueError("purchase_order_not_found")
    if po["status"] in ("cancelled",):
        raise ValueError("purchase_order_cancelled")
    ship_to = default_location_id or po.get("ship_to_location_id")
    if not ship_to:
        # If no location, resolve any "shop" location as a safe default.
        default = await db.inventory_locations.find_one(
            {"tenant_id": tenant_id, "kind": "shop", "active": True}, {"_id": 0}
        )
        if not default:
            default = await db.inventory_locations.find_one({"tenant_id": tenant_id}, {"_id": 0})
        if not default:
            raise ValueError("no_inventory_location_available")
        ship_to = default["id"]

    processed_lines: list[dict[str, Any]] = []
    for entry in lines:
        po_line_id = entry["po_line_id"]
        qty = float(entry["quantity"])
        if qty <= 0:
            continue
        po_line = await db.purchase_order_lines.find_one(
            {"tenant_id": tenant_id, "purchase_order_id": purchase_order_id, "id": po_line_id},
            {"_id": 0}
        )
        if not po_line:
            raise ValueError(f"po_line_not_found:{po_line_id}")
        remaining = float(po_line.get("quantity_ordered", 0.0)) - float(po_line.get("quantity_received", 0.0))
        if qty > remaining + 1e-9:
            raise ValueError(f"receive_exceeds_ordered:{po_line_id}")
        material_id = po_line.get("material_id")
        if not material_id:
            raise ValueError(f"po_line_missing_material:{po_line_id}")
        location_id = entry.get("location_id") or ship_to
        unit_price = int(po_line.get("unit_price_cents", 0))
        # 1) Inventory movement (receiving) — race-safe.
        mv = await inventory_service.receive(
            tenant_id=tenant_id, material_id=material_id, location_id=location_id,
            quantity=qty, actor_user_id=actor_user_id,
            source_entity_type="purchase_order", source_entity_id=purchase_order_id,
            idempotency_key=f"{idempotency_key}:{po_line_id}",
            unit_of_measure=po_line.get("unit_of_measure", "each"),
            reason=f"PO #{po['number']} line {po_line.get('position', 0)}",
        )
        # 2) Cost history if unit_price changed vs current material cost.
        mat = await db.materials.find_one(
            {"tenant_id": tenant_id, "id": material_id}, {"_id": 0}
        )
        cost_history_id = None
        if mat is not None and unit_price and int(mat.get("current_cost_cents", 0)) != unit_price:
            ch = MaterialCostHistory(
                tenant_id=tenant_id, material_id=material_id,
                cost_cents=unit_price, cost_unit=po_line.get("unit_of_measure", "each"),
                vendor_id=po["vendor_id"], source="receiving",
                source_ref=purchase_order_id, effective_at=utc_now().isoformat(),
                actor_user_id=actor_user_id,
            ).model_dump()
            await db.material_cost_history.insert_one(ch)
            cost_history_id = ch["id"]
            # Move current_cost to the new value (preserves history rows).
            await db.materials.update_one(
                {"tenant_id": tenant_id, "id": material_id},
                {"$set": {"current_cost_cents": unit_price,
                          "effective_at": utc_now().isoformat(),
                          "updated_at": utc_now().isoformat()}}
            )
        # 3) Bump PO line + inventory_item's last_received_at
        await db.purchase_order_lines.update_one(
            {"tenant_id": tenant_id, "id": po_line_id},
            {"$inc": {"quantity_received": qty},
             "$set": {"updated_at": utc_now().isoformat()}}
        )
        await db.inventory_items.update_one(
            {"tenant_id": tenant_id, "material_id": material_id, "location_id": location_id},
            {"$set": {"last_received_at": utc_now().isoformat(),
                      "updated_at": utc_now().isoformat()}}
        )
        processed_lines.append({
            "po_line_id": po_line_id, "quantity": qty, "location_id": location_id,
            "inventory_movement_id": mv.get("id"),
            "material_cost_history_id": cost_history_id,
        })

    # 4) Update PO status based on remaining balances
    all_lines = [
        d async for d in db.purchase_order_lines.find(
            {"tenant_id": tenant_id, "purchase_order_id": purchase_order_id}, {"_id": 0}
        )
    ]
    fully_received = all(
        float(l.get("quantity_received", 0.0)) >= float(l.get("quantity_ordered", 0.0)) - 1e-9
        for l in all_lines
    ) and len(all_lines) > 0
    any_received = any(float(l.get("quantity_received", 0.0)) > 0 for l in all_lines)
    new_status = "received" if fully_received else ("partially_received" if any_received else po["status"])
    await db.purchase_orders.update_one(
        {"tenant_id": tenant_id, "id": purchase_order_id},
        {"$set": {"status": new_status, "updated_at": utc_now().isoformat()}}
    )

    # 5) Persist ReceivingRecord
    rec = ReceivingRecord(
        tenant_id=tenant_id, purchase_order_id=purchase_order_id,
        idempotency_key=idempotency_key, received_by_user_id=actor_user_id,
        received_at=utc_now().isoformat(), lines=processed_lines, notes=notes,
    ).model_dump()
    await db.receiving_records.insert_one(rec)
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="purchase_order.receive", entity_type="purchase_order",
        entity_id=purchase_order_id,
        summary=f"Received {len(processed_lines)} line(s) on PO #{po['number']}",
        diff={"idempotency_key": idempotency_key, "new_status": new_status},
    )
    rec.pop("_id", None)
    return {"replayed": False, "record": serialize_doc(rec), "po_status": new_status}
