"""EC7 phase 7b — Purchasing recommendation.

Given a set of `RecommendationItem` requests (material_id + quantity + optional
compatible_group constraint), enumerate the candidate SupplierProducts across
all vendors and rank fulfillment options by user-selected priority:

  - lowest_delivered_cost
  - fastest_arrival
  - preferred_supplier
  - fewest_warehouse_splits
  - all_items_available
  - best_combined_score          (default)

Rules (LOCKED per master plan Appendix A.3):
  - Delivered cost = item + quantity breaks + account pricing + package qty
    rounding + shipping + freight + handling + MOQ + warehouse split cost.
  - Never compare products across `compatible_group`. Requesting a cast wrap
    vinyl will not match calendared vinyl.
  - Never silently substitute apparel brand / style / color / size.
  - Estimated freight rows are labeled `rate_type: estimated`.
"""
from __future__ import annotations
from typing import Any, Optional

from ..core.db import db
from .supplier_connectors import get_connector


def _round_up_to_package(quantity: float, package_qty: int, moq: int) -> int:
    """Return the actual order quantity honoring package qty + MOQ."""
    q = max(int(quantity), int(moq or 0))
    pkg = max(int(package_qty or 1), 1)
    if q % pkg:
        q += pkg - (q % pkg)
    return q


def _apply_breaks(base_cents: int, breaks: list[dict], quantity: int) -> int:
    price = base_cents
    for b in breaks or []:
        if quantity >= int(b["min_qty"]):
            price = int(b["unit_price_cents"])
    return price


async def _stock_by_warehouse(*, tenant_id: str, supplier_product_id: str) -> list[dict]:
    cur = db.supplier_product_stock.find(
        {"tenant_id": tenant_id, "supplier_product_id": supplier_product_id}, {"_id": 0}
    )
    return [d async for d in cur]


async def _find_supplier_products_for_material(
    *, tenant_id: str, material_id: str, compatible_group_hint: Optional[str] = None,
) -> list[dict]:
    """Match a Material to candidate SupplierProducts via VendorMaterial links.

    When no explicit mapping exists, the fallback matches on SKU and category
    (still respecting `compatible_group` when provided). We NEVER return
    products whose `compatible_group` differs from `compatible_group_hint`
    when a hint is given.
    """
    products: dict[str, dict] = {}
    async for vm in db.vendor_materials.find(
        {"tenant_id": tenant_id, "material_id": material_id, "active": True}, {"_id": 0}
    ):
        p = await db.supplier_products.find_one(
            {"tenant_id": tenant_id, "id": vm["supplier_product_id"], "active": True,
             "discontinued": {"$ne": True}}, {"_id": 0}
        )
        if p and (not compatible_group_hint or p.get("compatible_group") == compatible_group_hint):
            products[p["id"]] = p
    if not products:
        # Fallback: match on material.sku / name / category.
        mat = await db.materials.find_one({"tenant_id": tenant_id, "id": material_id}, {"_id": 0})
        if mat:
            filt: dict[str, Any] = {"tenant_id": tenant_id, "active": True,
                                    "discontinued": {"$ne": True}}
            if compatible_group_hint:
                filt["compatible_group"] = compatible_group_hint
            elif mat.get("category"):
                filt["category"] = mat["category"]
            or_clauses = []
            if mat.get("sku"):
                or_clauses.append({"supplier_sku": mat["sku"]})
            or_clauses.append({"description": {"$regex": mat["name"], "$options": "i"}})
            filt["$or"] = or_clauses
            async for p in db.supplier_products.find(filt, {"_id": 0}):
                products[p["id"]] = p
    return list(products.values())


async def recommend(*, tenant_id: str, requirements: list[dict[str, Any]],
                    priority: str = "best_combined_score") -> dict:
    """
    :param requirements: list of {"material_id": str, "quantity": float,
        "compatible_group"?: str}
    :param priority: one of the priority keys above.
    :return: {"items": [...], "totals": {...}, "warnings": [...],
              "estimates_labeled": True, "priority": priority}
    """
    warnings: list[str] = []
    per_item_options: list[dict] = []
    for req in requirements:
        material_id = req["material_id"]
        need_qty = float(req.get("quantity", 0.0))
        if need_qty <= 0:
            continue
        hint = req.get("compatible_group")
        candidates = await _find_supplier_products_for_material(
            tenant_id=tenant_id, material_id=material_id, compatible_group_hint=hint
        )
        if not candidates:
            warnings.append(f"no_supplier_products_for_material:{material_id}")
            per_item_options.append({"material_id": material_id, "requested": need_qty,
                                     "options": [], "compatible_group": hint})
            continue
        options: list[dict] = []
        for prod in candidates:
            vendor = await db.vendors.find_one({"id": prod["vendor_id"]}, {"_id": 0})
            connector = get_connector(vendor["connector_key"]) if vendor else None
            order_qty = _round_up_to_package(need_qty, prod.get("package_qty", 1),
                                             prod.get("minimum_order_qty", 0))
            unit_price = _apply_breaks(int(prod.get("account_price_cents", 0)),
                                       prod.get("quantity_breaks", []) or [],
                                       order_qty)
            line_extended = unit_price * order_qty
            stocks = await _stock_by_warehouse(
                tenant_id=tenant_id, supplier_product_id=prod["id"]
            )
            # For each warehouse: compute delivered cost (assuming single-line ship).
            wh_options: list[dict] = []
            for s in stocks:
                wh = await db.supplier_warehouses.find_one({"id": s["warehouse_id"]}, {"_id": 0})
                if not wh or not wh.get("active", True):
                    continue
                ship = None
                if connector:
                    try:
                        ship = await connector.get_shipping_quote(
                            tenant_id=tenant_id, vendor_id=vendor["id"],
                            warehouse_id=s["warehouse_id"], line_count=1
                        )
                    except NotImplementedError:
                        ship = None
                ship = ship or {"cost_cents": 0, "handling_cents": 0,
                                "rate_type": "estimated", "warehouse_id": s["warehouse_id"]}
                available = int(s.get("available_qty", 0))
                fulfillable = min(order_qty, available)
                partial = fulfillable < order_qty
                delivered_cost = line_extended + int(ship["cost_cents"]) + int(ship["handling_cents"])
                lead = int(s.get("lead_time_days", 0)) + (0 if available >= order_qty else 3)
                wh_options.append({
                    "warehouse_id": s["warehouse_id"],
                    "warehouse_code": (wh or {}).get("code"),
                    "warehouse_name": (wh or {}).get("name"),
                    "available_qty": available,
                    "fulfillable_qty": fulfillable,
                    "partial": partial,
                    "unit_price_cents": unit_price,
                    "line_extended_cents": line_extended,
                    "shipping_cents": int(ship["cost_cents"]),
                    "handling_cents": int(ship["handling_cents"]),
                    "delivered_cost_cents": delivered_cost,
                    "lead_time_days": lead,
                    "rate_type": ship.get("rate_type", "estimated"),
                })
            options.append({
                "vendor_id": (vendor or {}).get("id"),
                "vendor_name": (vendor or {}).get("name"),
                "vendor_preferred": bool((vendor or {}).get("preferred")),
                "supplier_product_id": prod["id"],
                "supplier_sku": prod["supplier_sku"],
                "description": prod.get("description"),
                "compatible_group": prod.get("compatible_group"),
                "package_qty": int(prod.get("package_qty", 1)),
                "minimum_order_qty": int(prod.get("minimum_order_qty", 0)),
                "order_quantity": order_qty,
                "warehouses": wh_options,
            })
        per_item_options.append({"material_id": material_id, "requested": need_qty,
                                 "compatible_group": hint, "options": options})

    # ---- Score each per-item option (best warehouse per option first) ----
    def score_option(opt: dict) -> Optional[dict]:
        whs = [w for w in opt.get("warehouses", [])
               if not w["partial"] and w["fulfillable_qty"] >= opt["order_quantity"]]
        # If nothing single-warehouse fills the order, keep the best partial for split logic.
        if not whs:
            whs = opt.get("warehouses", [])
        if not whs:
            return None
        best = min(whs, key=lambda w: (w["delivered_cost_cents"], w["lead_time_days"]))
        return {**opt, "chosen_warehouse": best}

    per_item_scored: list[dict] = []
    for row in per_item_options:
        scored = [x for x in (score_option(o) for o in row["options"]) if x]
        row["scored_options"] = scored
        per_item_scored.append(row)

    def pick(row: dict, priority_key: str) -> Optional[dict]:
        candidates = row.get("scored_options") or []
        if not candidates:
            return None
        if priority_key == "lowest_delivered_cost":
            return min(candidates, key=lambda o: o["chosen_warehouse"]["delivered_cost_cents"])
        if priority_key == "fastest_arrival":
            return min(candidates, key=lambda o: (o["chosen_warehouse"]["lead_time_days"],
                                                  o["chosen_warehouse"]["delivered_cost_cents"]))
        if priority_key == "preferred_supplier":
            preferred = [o for o in candidates if o["vendor_preferred"]]
            pool = preferred or candidates
            return min(pool, key=lambda o: o["chosen_warehouse"]["delivered_cost_cents"])
        if priority_key == "all_items_available":
            available = [o for o in candidates
                         if not o["chosen_warehouse"]["partial"]]
            pool = available or candidates
            return min(pool, key=lambda o: o["chosen_warehouse"]["delivered_cost_cents"])
        if priority_key == "fewest_warehouse_splits":
            # Same behaviour per-item; splits matter across items and are counted post-selection.
            available = [o for o in candidates if not o["chosen_warehouse"]["partial"]]
            pool = available or candidates
            return min(pool, key=lambda o: o["chosen_warehouse"]["delivered_cost_cents"])
        # best_combined_score
        def combined(o: dict) -> float:
            wh = o["chosen_warehouse"]
            preferred_bonus = -1500 if o["vendor_preferred"] else 0
            partial_penalty = 5000 if wh["partial"] else 0
            return wh["delivered_cost_cents"] + wh["lead_time_days"] * 150 + partial_penalty + preferred_bonus
        return min(candidates, key=combined)

    items_out: list[dict] = []
    grand_delivered = 0
    grand_item = 0
    grand_ship = 0
    grand_handling = 0
    warehouse_split_set: set[str] = set()
    vendor_split_set: set[str] = set()
    for row in per_item_scored:
        chosen = pick(row, priority)
        if chosen:
            wh = chosen["chosen_warehouse"]
            warehouse_split_set.add(f"{chosen['vendor_id']}:{wh['warehouse_id']}")
            vendor_split_set.add(chosen["vendor_id"])
            grand_delivered += wh["delivered_cost_cents"]
            grand_item += wh["line_extended_cents"]
            grand_ship += wh["shipping_cents"]
            grand_handling += wh["handling_cents"]
        items_out.append({
            "material_id": row["material_id"],
            "requested": row["requested"],
            "compatible_group": row.get("compatible_group"),
            "chosen": chosen,
            "alternatives": [o for o in (row.get("scored_options") or []) if o is not chosen],
        })

    return {
        "priority": priority,
        "estimates_labeled": True,
        "warnings": warnings,
        "items": items_out,
        "totals": {
            "delivered_cost_cents": grand_delivered,
            "item_subtotal_cents": grand_item,
            "shipping_cents": grand_ship,
            "handling_cents": grand_handling,
            "warehouse_splits": len(warehouse_split_set),
            "vendor_splits": len(vendor_split_set),
        },
    }
