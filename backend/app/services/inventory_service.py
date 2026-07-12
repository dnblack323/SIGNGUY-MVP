"""EC7 phase 7a — Inventory service.

Rules:
- All stock changes create an immutable InventoryMovement row.
- Balances change only through this service (never direct writes).
- Race-safe via find-and-modify with expected-quantity check.
- Idempotency-key uniqueness on movements where applicable.
- Negative stock rejected unless explicit `allow_negative=True` policy hook.
- Reservation reduces available (= on_hand - reserved) but not on_hand.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from ..core.db import db
from ..core.time_utils import serialize_doc, utc_now
from ..models.inventory import InventoryItem, InventoryMovement, InventoryReservation
from ..services.audit import record_audit


async def _get_or_create_item(*, tenant_id: str, material_id: str, location_id: str) -> dict:
    item = await db.inventory_items.find_one(
        {"tenant_id": tenant_id, "material_id": material_id, "location_id": location_id}
    )
    if item:
        item.pop("_id", None)
        return item
    seed = InventoryItem(
        tenant_id=tenant_id, material_id=material_id, location_id=location_id,
        quantity_on_hand=0.0, quantity_reserved=0.0,
    ).model_dump()
    try:
        await db.inventory_items.insert_one(seed)
    except Exception:
        item = await db.inventory_items.find_one(
            {"tenant_id": tenant_id, "material_id": material_id, "location_id": location_id}
        )
        item.pop("_id", None)
        return item
    seed.pop("_id", None)
    return seed


async def _apply_delta(*, tenant_id: str, material_id: str, location_id: str,
                       delta: float, movement_type: str, direction: str,
                       actor_user_id: Optional[str] = None, reason: Optional[str] = None,
                       source_entity_type: Optional[str] = None,
                       source_entity_id: Optional[str] = None,
                       idempotency_key: Optional[str] = None,
                       observed_quantity: Optional[float] = None,
                       expected_quantity: Optional[float] = None,
                       unit_of_measure: str = "each",
                       allow_negative: bool = False) -> dict:
    """Race-safe balance mutation + immutable movement row."""
    # Idempotency: if movement with this key already applied, return it and skip
    if idempotency_key:
        existing = await db.inventory_movements.find_one(
            {"tenant_id": tenant_id, "idempotency_key": idempotency_key}
        )
        if existing:
            existing.pop("_id", None)
            return serialize_doc(existing)
    for _ in range(5):  # retry on race
        item = await _get_or_create_item(tenant_id=tenant_id, material_id=material_id, location_id=location_id)
        before = float(item.get("quantity_on_hand", 0.0))
        after = before + delta
        if after < 0 and not allow_negative:
            raise ValueError("negative_stock_rejected")
        # Optimistic update
        res = await db.inventory_items.update_one(
            {"id": item["id"], "quantity_on_hand": before},
            {"$set": {"quantity_on_hand": after,
                      "last_movement_at": utc_now().isoformat()}},
        )
        if res.modified_count == 0:
            continue  # race — retry
        mv_doc = InventoryMovement(
            tenant_id=tenant_id, material_id=material_id, location_id=location_id,
            quantity=abs(float(delta)), unit_of_measure=unit_of_measure,
            direction=direction,  # type: ignore[arg-type]
            movement_type=movement_type,  # type: ignore[arg-type]
            source_entity_type=source_entity_type, source_entity_id=source_entity_id,
            reason=reason, actor_user_id=actor_user_id,
            before_quantity=before, after_quantity=after,
            idempotency_key=idempotency_key,
            observed_quantity=observed_quantity, expected_quantity=expected_quantity,
        ).model_dump()
        # Omit idempotency_key from the DB row when unset so the sparse index
        # doesn't collide on repeated NULLs.
        if not idempotency_key:
            mv_doc.pop("idempotency_key", None)
        await db.inventory_movements.insert_one(mv_doc)
        await record_audit(
            tenant_id=tenant_id, actor_user_id=(actor_user_id or "system"),
            actor_email=(actor_user_id or "system@internal"),
            action=f"inventory.{movement_type}", entity_type="inventory_item",
            entity_id=item["id"],
            summary=f"{movement_type} {abs(delta)} @ location {location_id}",
            diff={"before": before, "after": after, "delta": delta, "reason": reason},
        )
        mv_doc.pop("_id", None)
        return serialize_doc(mv_doc)
    raise RuntimeError("inventory_race_exhausted")


async def receive(*, tenant_id, material_id, location_id, quantity, actor_user_id=None,
                  source_entity_type=None, source_entity_id=None, idempotency_key=None,
                  unit_of_measure="each", reason=None):
    return await _apply_delta(tenant_id=tenant_id, material_id=material_id, location_id=location_id,
                              delta=abs(float(quantity)), movement_type="receiving", direction="in",
                              actor_user_id=actor_user_id, source_entity_type=source_entity_type,
                              source_entity_id=source_entity_id, idempotency_key=idempotency_key,
                              unit_of_measure=unit_of_measure, reason=reason)


async def manual_increase(**kw):
    kw.setdefault("movement_type", "manual_increase")
    kw.setdefault("direction", "in")
    kw["delta"] = abs(float(kw.pop("quantity")))
    return await _apply_delta(**kw)


async def manual_decrease(**kw):
    kw.setdefault("movement_type", "manual_decrease")
    kw.setdefault("direction", "out")
    kw["delta"] = -abs(float(kw.pop("quantity")))
    return await _apply_delta(**kw)


async def physical_count(*, tenant_id, material_id, location_id, observed, actor_user_id=None,
                         reason=None, idempotency_key=None, unit_of_measure="each"):
    item = await _get_or_create_item(tenant_id=tenant_id, material_id=material_id, location_id=location_id)
    expected = float(item.get("quantity_on_hand", 0.0))
    delta = float(observed) - expected
    mv = await _apply_delta(
        tenant_id=tenant_id, material_id=material_id, location_id=location_id,
        delta=delta, movement_type="count_adjustment",
        direction="in" if delta >= 0 else "out",
        actor_user_id=actor_user_id, reason=reason or "physical count",
        idempotency_key=idempotency_key, unit_of_measure=unit_of_measure,
        observed_quantity=float(observed), expected_quantity=expected,
    )
    await db.inventory_items.update_one(
        {"tenant_id": tenant_id, "material_id": material_id, "location_id": location_id},
        {"$set": {"last_counted_at": utc_now().isoformat()}},
    )
    return mv


async def transfer(*, tenant_id, material_id, from_location_id, to_location_id, quantity,
                   actor_user_id=None, reason=None, idempotency_key=None, unit_of_measure="each"):
    if from_location_id == to_location_id:
        raise ValueError("transfer_same_location")
    q = abs(float(quantity))
    key_out = f"{idempotency_key}:out" if idempotency_key else None
    key_in = f"{idempotency_key}:in" if idempotency_key else None
    await _apply_delta(tenant_id=tenant_id, material_id=material_id, location_id=from_location_id,
                       delta=-q, movement_type="transfer_out", direction="out",
                       actor_user_id=actor_user_id, reason=reason, idempotency_key=key_out,
                       unit_of_measure=unit_of_measure)
    await _apply_delta(tenant_id=tenant_id, material_id=material_id, location_id=to_location_id,
                       delta=q, movement_type="transfer_in", direction="in",
                       actor_user_id=actor_user_id, reason=reason, idempotency_key=key_in,
                       unit_of_measure=unit_of_measure)
    return {"transferred": q}


async def reserve(*, tenant_id, material_id, location_id, quantity,
                  source_entity_type, source_entity_id, actor_user_id=None,
                  allow_over_available=False):
    q = abs(float(quantity))
    item = await _get_or_create_item(tenant_id=tenant_id, material_id=material_id, location_id=location_id)
    available = float(item.get("quantity_on_hand", 0.0)) - float(item.get("quantity_reserved", 0.0))
    if q > available and not allow_over_available:
        raise ValueError("reservation_exceeds_available")
    res = InventoryReservation(
        tenant_id=tenant_id, material_id=material_id, location_id=location_id,
        quantity=q, source_entity_type=source_entity_type, source_entity_id=source_entity_id,
        actor_user_id=actor_user_id, active=True,
    ).model_dump()
    await db.inventory_reservations.insert_one(res)
    await db.inventory_items.update_one(
        {"id": item["id"]},
        {"$inc": {"quantity_reserved": q}},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=(actor_user_id or "system"),
        actor_email=(actor_user_id or "system@internal"),
        action="inventory.reservation", entity_type="inventory_reservation",
        entity_id=res["id"], summary=f"Reserved {q} for {source_entity_type}:{source_entity_id}",
    )
    res.pop("_id", None)
    return serialize_doc(res)


async def release_reservation(*, tenant_id, reservation_id, actor_user_id=None, reason=None):
    res = await db.inventory_reservations.find_one(
        {"id": reservation_id, "tenant_id": tenant_id, "active": True}
    )
    if not res:
        raise ValueError("reservation_not_found")
    await db.inventory_items.update_one(
        {"tenant_id": tenant_id, "material_id": res["material_id"], "location_id": res["location_id"]},
        {"$inc": {"quantity_reserved": -float(res["quantity"])}},
    )
    await db.inventory_reservations.update_one(
        {"id": reservation_id},
        {"$set": {"active": False, "released_at": utc_now().isoformat(),
                  "released_reason": reason, "updated_at": utc_now().isoformat()}},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=(actor_user_id or "system"),
        actor_email=(actor_user_id or "system@internal"),
        action="inventory.reservation_release", entity_type="inventory_reservation",
        entity_id=reservation_id, summary=f"Released reservation {reservation_id}",
        diff={"reason": reason},
    )
    return {"released": True}


async def compute_available(item: dict) -> float:
    return float(item.get("quantity_on_hand", 0.0)) - float(item.get("quantity_reserved", 0.0))


async def low_stock_items(*, tenant_id: str) -> list[dict]:
    """List items where reorder_point is set and available <= reorder_point."""
    out: list[dict] = []
    async for item in db.inventory_items.find({"tenant_id": tenant_id}, {"_id": 0}):
        # Reorder point may live on the item or on the material
        rp = item.get("minimum_quantity")
        if rp is None:
            m = await db.materials.find_one({"id": item["material_id"], "tenant_id": tenant_id}, {"reorder_point": 1})
            rp = (m or {}).get("reorder_point")
        if rp is None:
            continue
        avail = float(item.get("quantity_on_hand", 0.0)) - float(item.get("quantity_reserved", 0.0))
        if avail <= float(rp):
            out.append({**serialize_doc(item), "quantity_available": avail, "reorder_point": float(rp)})
    return out
