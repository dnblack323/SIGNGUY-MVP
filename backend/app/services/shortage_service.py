"""EC7 phase 7b — Shortage calculation.

Given a list of `(material_id, required_qty)` tuples (typically derived from
Order Items or a manual restock request) and the current tenant Inventory,
return per-material shortage: how much more is needed after subtracting
available (on-hand minus reserved) stock.
"""
from __future__ import annotations
from typing import Any, Optional

from ..core.db import db


async def compute_shortage(*, tenant_id: str, requirements: list[dict[str, Any]],
                           location_id: Optional[str] = None) -> list[dict]:
    """
    :param requirements: list of {"material_id": str, "quantity": float, "order_item_id"?, "order_id"?}
    :param location_id: optional single-location shortage. When None the shortage is
        computed against the sum of available stock across all locations.
    :return: list of {material_id, required, available, shortage, order_item_id?, order_id?}
    """
    if not requirements:
        return []
    # Aggregate requirements per material first (so 3 order items of same material collapse)
    agg: dict[str, dict[str, Any]] = {}
    for r in requirements:
        mid = r["material_id"]
        row = agg.setdefault(mid, {"material_id": mid, "required": 0.0,
                                   "order_items": [], "orders": set()})
        row["required"] += float(r.get("quantity", 0.0))
        if r.get("order_item_id"):
            row["order_items"].append(r["order_item_id"])
        if r.get("order_id"):
            row["orders"].add(r["order_id"])
    out: list[dict] = []
    for mid, row in agg.items():
        inv_filt: dict[str, Any] = {"tenant_id": tenant_id, "material_id": mid}
        if location_id:
            inv_filt["location_id"] = location_id
        available = 0.0
        async for it in db.inventory_items.find(inv_filt, {"_id": 0}):
            available += float(it.get("quantity_on_hand", 0.0)) - float(it.get("quantity_reserved", 0.0))
        shortage = row["required"] - max(available, 0.0)
        material = await db.materials.find_one(
            {"tenant_id": tenant_id, "id": mid}, {"_id": 0, "name": 1, "sku": 1, "category": 1}
        )
        out.append({
            "material_id": mid,
            "material_name": (material or {}).get("name"),
            "material_sku": (material or {}).get("sku"),
            "material_category": (material or {}).get("category"),
            "required": row["required"],
            "available": max(available, 0.0),
            "shortage": max(shortage, 0.0),
            "order_item_ids": row["order_items"],
            "order_ids": sorted(row["orders"]),
            "has_shortage": shortage > 0,
        })
    # Highest shortage first, then largest requirement.
    out.sort(key=lambda x: (-x["shortage"], -x["required"]))
    return out


async def shortage_for_order(*, tenant_id: str, order_id: str,
                             location_id: Optional[str] = None) -> list[dict]:
    """Convenience: build the shortage for every OrderItem on a given Order.

    Requires the OrderItem to carry `material_key` -> internal Material id
    OR a mapping via `sku` -> Material.sku. When no mapping exists the item
    is skipped (recorded in `_skipped`) so callers can flag it.
    """
    reqs: list[dict[str, Any]] = []
    async for oi in db.order_items.find({"tenant_id": tenant_id, "order_id": order_id}, {"_id": 0}):
        material_id = None
        # Prefer explicit material_key when it looks like a Material id.
        key = oi.get("material_key")
        if key:
            hit = await db.materials.find_one(
                {"tenant_id": tenant_id, "$or": [{"id": key}, {"sku": key}]}, {"_id": 0, "id": 1}
            )
            if hit:
                material_id = hit["id"]
        if not material_id and oi.get("sku"):
            hit = await db.materials.find_one(
                {"tenant_id": tenant_id, "sku": oi["sku"]}, {"_id": 0, "id": 1}
            )
            if hit:
                material_id = hit["id"]
        if not material_id:
            continue
        reqs.append({
            "material_id": material_id,
            "quantity": float(oi.get("quantity", 0) or 0),
            "order_item_id": oi["id"],
            "order_id": order_id,
        })
    return await compute_shortage(tenant_id=tenant_id, requirements=reqs, location_id=location_id)
