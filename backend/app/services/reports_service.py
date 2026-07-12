"""EC7 phase 7d — Curated reports registry + Custom Report Builder foundation.

The reports service dispatches every report by a stable `report_key`. Each
report:
  - names its data source (collection + service)
  - names its date basis (issued_at, confirmed_at, expense_date, created_at)
  - names its calculation basis (issued_invoices / confirmed_payments / expenses / …)
  - lists known limitations
  - enforces the tenant, permission, and safe-empty-state contract

Report registry entries also define which fields are exportable — the CSV
exporter honors this whitelist so no hidden internal field ever leaks.

Custom Report Builder foundation is deliberately restricted:
  - allowed datasets only
  - allowed fields only
  - allowed filters only
  - allowed group_by / sort keys only
  - NO raw SQL, NO arbitrary Mongo queries, NO cross-tenant reads
  - permission enforced on every dataset
  - preview capped at 500 rows; export capped at 25 000 rows
"""
from __future__ import annotations
from typing import Any, Callable, Optional

from ..core.db import db
from ..core.time_utils import serialize_doc
from ..core.permissions import Perm
from . import finance_service, tax_service


# ---------------------------------------------------------------------------
# Report registry
#
# Each entry:
#   key              : stable id
#   title            : display
#   category         : "inventory" | "purchasing" | "expenses" | "finance" | "tax"
#   perm             : required Perm (backend authoritative)
#   data_source      : short descriptor for provenance
#   date_basis       : "issued_invoices" | "confirmed_payments" | "expense_date" |
#                       "purchase_order_created_at" | "movement_ts" | "n/a"
#   calc_basis       : short label — same set as finance metrics
#   limitations      : list of strings
#   columns          : ordered list of {"key": str, "label": str,
#                                        "money"?: bool, "date"?: bool}
#   run              : async fn (tenant_id, filters) -> list[dict[str, Any]]
# ---------------------------------------------------------------------------


def _money_col(k, label):
    return {"key": k, "label": label, "money": True}


def _date_col(k, label):
    return {"key": k, "label": label, "date": True}


# -------- inventory reports --------
async def _inventory_on_hand(*, tenant_id: str, filters: dict) -> list[dict]:
    cur = db.inventory_items.find({"tenant_id": tenant_id}, {"_id": 0})
    rows: list[dict] = []
    async for it in cur:
        mat = await db.materials.find_one({"tenant_id": tenant_id, "id": it["material_id"]}, {"_id": 0})
        loc = await db.inventory_locations.find_one({"tenant_id": tenant_id, "id": it["location_id"]}, {"_id": 0})
        on_hand = float(it.get("quantity_on_hand", 0) or 0)
        reserved = float(it.get("quantity_reserved", 0) or 0)
        available = max(on_hand - reserved, 0)
        rows.append({
            "material_id": it["material_id"],
            "material_name": (mat or {}).get("name"),
            "material_sku": (mat or {}).get("sku"),
            "category": (mat or {}).get("category"),
            "location_name": (loc or {}).get("name"),
            "quantity_on_hand": on_hand,
            "quantity_reserved": reserved,
            "quantity_available": available,
            "last_received_at": it.get("last_received_at"),
        })
    return rows


async def _inventory_low_stock(*, tenant_id: str, filters: dict) -> list[dict]:
    rows = await _inventory_on_hand(tenant_id=tenant_id, filters={})
    out: list[dict] = []
    for r in rows:
        mat = await db.materials.find_one(
            {"tenant_id": tenant_id, "id": r["material_id"]},
            {"_id": 0, "low_stock_threshold": 1},
        )
        low = float((mat or {}).get("low_stock_threshold") or 0)
        if low > 0 and r["quantity_available"] <= low:
            out.append({**r, "low_stock_threshold": low})
    return out


async def _inventory_movements(*, tenant_id: str, filters: dict) -> list[dict]:
    q: dict[str, Any] = {"tenant_id": tenant_id}
    if filters.get("material_id"): q["material_id"] = filters["material_id"]
    if filters.get("location_id"): q["location_id"] = filters["location_id"]
    rng: dict[str, Any] = {}
    if filters.get("date_from"): rng["$gte"] = filters["date_from"]
    if filters.get("date_to"): rng["$lte"] = filters["date_to"] + "T23:59:59.999999Z"
    if rng: q["created_at"] = rng
    cur = db.inventory_movements.find(q, {"_id": 0}).sort("created_at", -1).limit(25000)
    rows: list[dict] = []
    async for m in cur:
        mat = await db.materials.find_one({"tenant_id": tenant_id, "id": m["material_id"]}, {"_id": 0, "name": 1, "sku": 1})
        rows.append({
            "created_at": m.get("created_at"),
            "material_name": (mat or {}).get("name"),
            "material_sku": (mat or {}).get("sku"),
            "location_id": m.get("location_id"),
            "movement_type": m.get("movement_type"),
            "quantity": float(m.get("quantity", 0) or 0),
            "direction": m.get("direction"),
            "reason": m.get("reason"),
            "source_entity_type": m.get("source_entity_type"),
            "source_entity_id": m.get("source_entity_id"),
        })
    return rows


async def _material_cost_history(*, tenant_id: str, filters: dict) -> list[dict]:
    q: dict[str, Any] = {"tenant_id": tenant_id}
    if filters.get("material_id"): q["material_id"] = filters["material_id"]
    cur = db.material_cost_history.find(q, {"_id": 0}).sort("effective_at", -1).limit(25000)
    rows: list[dict] = []
    async for r in cur:
        mat = await db.materials.find_one({"tenant_id": tenant_id, "id": r["material_id"]}, {"_id": 0, "name": 1, "sku": 1})
        rows.append({
            "effective_at": r.get("effective_at"),
            "material_name": (mat or {}).get("name"),
            "material_sku": (mat or {}).get("sku"),
            "cost_cents": int(r.get("cost_cents", 0)),
            "cost_unit": r.get("cost_unit"),
            "source": r.get("source"),
            "source_ref": r.get("source_ref"),
        })
    return rows


# -------- purchasing reports --------
async def _po_by_status(*, tenant_id: str, filters: dict) -> list[dict]:
    q: dict[str, Any] = {"tenant_id": tenant_id}
    if filters.get("status"): q["status"] = filters["status"]
    if filters.get("vendor_id"): q["vendor_id"] = filters["vendor_id"]
    cur = db.purchase_orders.find(q, {"_id": 0}).sort("number", -1).limit(25000)
    rows: list[dict] = []
    async for po in cur:
        rows.append({
            "number": po.get("number"),
            "vendor_name": (po.get("vendor_snapshot") or {}).get("name"),
            "status": po.get("status"),
            "subtotal_cents": int(po.get("subtotal_cents", 0)),
            "shipping_cents": int(po.get("shipping_cents", 0)),
            "handling_cents": int(po.get("handling_cents", 0)),
            "total_cents": int(po.get("total_cents", 0)),
            "created_at": po.get("created_at"),
            "submitted_at": po.get("submitted_at"),
            "tracking_status": po.get("tracking_status"),
        })
    return rows


async def _vendor_spend(*, tenant_id: str, filters: dict) -> list[dict]:
    q: dict[str, Any] = {"tenant_id": tenant_id,
                        "status": {"$in": ["submitted", "acknowledged",
                                            "partially_received", "received"]}}
    rng: dict[str, Any] = {}
    if filters.get("date_from"): rng["$gte"] = filters["date_from"]
    if filters.get("date_to"): rng["$lte"] = filters["date_to"] + "T23:59:59.999999Z"
    if rng: q["created_at"] = rng
    pipeline = [{"$match": q},
                {"$group": {"_id": "$vendor_id",
                             "spend_cents": {"$sum": "$total_cents"},
                             "po_count": {"$sum": 1}}},
                {"$sort": {"spend_cents": -1}}]
    result = await db.purchase_orders.aggregate(pipeline).to_list(length=25000)
    rows: list[dict] = []
    for r in result:
        vendor = await db.vendors.find_one({"id": r["_id"]}, {"_id": 0, "name": 1})
        rows.append({
            "vendor_name": (vendor or {}).get("name"),
            "spend_cents": int(r["spend_cents"] or 0),
            "po_count": int(r["po_count"] or 0),
        })
    return rows


# -------- expense reports --------
async def _expenses_by_category(*, tenant_id: str, filters: dict) -> list[dict]:
    res = await finance_service.expenses_by_category(
        tenant_id=tenant_id, date_from=filters.get("date_from"),
        date_to=filters.get("date_to"),
    )
    return res.get("items", [])


async def _expenses_by_vendor(*, tenant_id: str, filters: dict) -> list[dict]:
    q: dict[str, Any] = {"tenant_id": tenant_id, "state": "active"}
    rng: dict[str, Any] = {}
    if filters.get("date_from"): rng["$gte"] = filters["date_from"]
    if filters.get("date_to"): rng["$lte"] = filters["date_to"]
    if rng: q["expense_date"] = rng
    pipeline = [{"$match": q},
                {"$group": {"_id": "$vendor_id",
                             "total_cents": {"$sum": "$total_cents"},
                             "count": {"$sum": 1}}},
                {"$sort": {"total_cents": -1}}]
    result = await db.expenses.aggregate(pipeline).to_list(length=25000)
    rows: list[dict] = []
    for r in result:
        vendor = None
        if r["_id"]:
            vendor = await db.vendors.find_one({"id": r["_id"]}, {"_id": 0, "name": 1})
        rows.append({
            "vendor_name": (vendor or {}).get("name") or "(no vendor)",
            "total_cents": int(r["total_cents"] or 0),
            "count": int(r["count"] or 0),
        })
    return rows


async def _expenses_all(*, tenant_id: str, filters: dict) -> list[dict]:
    q: dict[str, Any] = {"tenant_id": tenant_id}
    if filters.get("state"): q["state"] = filters["state"]
    if filters.get("category_key"): q["category_key"] = filters["category_key"]
    rng: dict[str, Any] = {}
    if filters.get("date_from"): rng["$gte"] = filters["date_from"]
    if filters.get("date_to"): rng["$lte"] = filters["date_to"]
    if rng: q["expense_date"] = rng
    cur = db.expenses.find(q, {"_id": 0}).sort([("expense_date", -1), ("number", -1)]).limit(25000)
    rows: list[dict] = []
    async for e in cur:
        rows.append({
            "number": e.get("number"),
            "expense_date": e.get("expense_date"),
            "category_key": e.get("category_key"),
            "category_label": e.get("category_label_snapshot"),
            "vendor_name": e.get("vendor_name_snapshot"),
            "description": e.get("description"),
            "amount_cents": int(e.get("amount_cents", 0)),
            "tax_cents": int(e.get("tax_cents", 0)),
            "total_cents": int(e.get("total_cents", 0)),
            "payment_method": e.get("payment_method"),
            "deductible_class": e.get("deductible_class"),
            "state": e.get("state"),
        })
    return rows


# -------- finance & tax reports (thin wrappers) --------
async def _finance_summary_flat(*, tenant_id: str, filters: dict) -> list[dict]:
    s = await finance_service.dashboard_summary(
        tenant_id=tenant_id, date_from=filters.get("date_from"),
        date_to=filters.get("date_to"),
    )
    return [{"metric": k, "basis": v.get("basis"),
             "value_cents": v.get("value_cents", 0)}
            for k, v in s.items()
            if isinstance(v, dict) and "basis" in v]


async def _top_customers_flat(*, tenant_id: str, filters: dict) -> list[dict]:
    s = await finance_service.top_customers_by_revenue(
        tenant_id=tenant_id, date_from=filters.get("date_from"),
        date_to=filters.get("date_to"), limit=int(filters.get("limit", 25)),
    )
    return s.get("items", [])


async def _tax_by_jurisdiction_flat(*, tenant_id: str, filters: dict) -> list[dict]:
    r = await tax_service.tax_collected_by_jurisdiction(
        tenant_id=tenant_id, date_from=filters.get("date_from"),
        date_to=filters.get("date_to"),
    )
    return r.get("items", [])


async def _tax_overrides_flat(*, tenant_id: str, filters: dict) -> list[dict]:
    r = await tax_service.manual_tax_override_report(
        tenant_id=tenant_id, date_from=filters.get("date_from"),
        date_to=filters.get("date_to"),
    )
    return r.get("items", [])


async def _exempt_customers_flat(*, tenant_id: str, filters: dict) -> list[dict]:
    r = await tax_service.exempt_customer_report(
        tenant_id=tenant_id, date_from=filters.get("date_from"),
        date_to=filters.get("date_to"), jurisdiction=filters.get("jurisdiction"),
    )
    return r.get("items", [])


# -------- payroll reports (EC8 phase 8d) --------
# Both reports read the `payroll_snapshots` read-model (itself derived live
# from the `payroll_transactions` ledger — see `services/payroll_service.py`)
# joined against `pay_periods` for the date/status filter. The registry is
# intentionally left open for later payroll report keys (advances, payments,
# carryover, unpaid balances, regular-vs-overtime, trends) — no second
# report/CSV system is introduced here.
async def _payroll_period_ids_in_range(*, tenant_id: str, filters: dict) -> list[str]:
    q: dict[str, Any] = {"tenant_id": tenant_id}
    if filters.get("period_status"): q["status"] = filters["period_status"]
    rng: dict[str, Any] = {}
    if filters.get("date_from"): rng["$gte"] = filters["date_from"]
    if filters.get("date_to"): rng["$lte"] = filters["date_to"]
    if rng: q["start_date"] = rng
    return [p["id"] async for p in db.pay_periods.find(q, {"_id": 0, "id": 1})]


async def _payroll_by_period(*, tenant_id: str, filters: dict) -> list[dict]:
    period_ids = await _payroll_period_ids_in_range(tenant_id=tenant_id, filters=filters)
    periods = {p["id"]: p async for p in db.pay_periods.find({"tenant_id": tenant_id, "id": {"$in": period_ids}}, {"_id": 0})}
    q: dict[str, Any] = {"tenant_id": tenant_id, "pay_period_id": {"$in": period_ids}}
    if filters.get("employee_id"): q["employee_id"] = filters["employee_id"]
    cur = db.payroll_snapshots.find(q, {"_id": 0}).limit(25000)
    rows: list[dict] = []
    async for s in cur:
        p = periods.get(s["pay_period_id"], {})
        rows.append({
            "period_start": p.get("start_date"), "period_end": p.get("end_date"), "payday": p.get("payday"),
            "period_status": p.get("status"), "employee_name": s.get("employee_name"),
            "regular_minutes": s.get("regular_minutes", 0), "overtime_minutes": s.get("overtime_minutes", 0),
            "gross_regular_cents": int(s.get("gross_regular_cents", 0)), "gross_overtime_cents": int(s.get("gross_overtime_cents", 0)),
            "adjustment_total_cents": int(s.get("adjustment_total_cents", 0)), "advance_total_cents": int(s.get("advance_total_cents", 0)),
            "repayment_total_cents": int(s.get("repayment_total_cents", 0)), "payment_total_cents": int(s.get("payment_total_cents", 0)),
            "carryover_in_cents": int(s.get("carryover_in_cents", 0)), "carryover_out_cents": int(s.get("carryover_out_cents", 0)),
            "total_earned_cents": int(s.get("total_earned_cents", 0)), "total_paid_cents": int(s.get("total_paid_cents", 0)),
            "remaining_balance_cents": int(s.get("remaining_balance_cents", 0)),
        })
    rows.sort(key=lambda r: (r["period_start"] or "", r["employee_name"] or ""), reverse=True)
    return rows


async def _payroll_by_employee(*, tenant_id: str, filters: dict) -> list[dict]:
    period_ids = await _payroll_period_ids_in_range(tenant_id=tenant_id, filters=filters)
    pipeline = [
        {"$match": {"tenant_id": tenant_id, "pay_period_id": {"$in": period_ids}}},
        {"$group": {
            "_id": "$employee_id", "employee_name": {"$first": "$employee_name"},
            "period_count": {"$sum": 1},
            "total_regular_cents": {"$sum": "$gross_regular_cents"}, "total_overtime_cents": {"$sum": "$gross_overtime_cents"},
            "total_adjustments_cents": {"$sum": "$adjustment_total_cents"}, "total_advances_cents": {"$sum": "$advance_total_cents"},
            "total_repayments_cents": {"$sum": "$repayment_total_cents"}, "total_payments_cents": {"$sum": "$payment_total_cents"},
            "total_carryover_in_cents": {"$sum": "$carryover_in_cents"}, "total_carryover_out_cents": {"$sum": "$carryover_out_cents"},
            "total_earned_cents": {"$sum": "$total_earned_cents"}, "total_remaining_cents": {"$sum": "$remaining_balance_cents"},
        }},
        {"$sort": {"total_earned_cents": -1}},
    ]
    result = await db.payroll_snapshots.aggregate(pipeline).to_list(length=25000)
    return [{**{k: v for k, v in r.items() if k != "_id"}} for r in result]


# -------- Equipment / Training / Certification reports (EC8 phase 8e) --------
# All 5 reuse `certification_service`/`training_service`/`equipment_service`
# read logic rather than re-querying raw collections directly — same
# single-source-of-truth principle as the payroll reports above.

async def _certification_matrix_flat(*, tenant_id: str, filters: dict) -> list[dict]:
    from . import certification_service as cs
    from ..core.db import db as _db
    employees = [serialize_doc(d) async for d in _db.employees.find({"tenant_id": tenant_id, "status": {"$ne": "archived"}}, {"_id": 0})]
    equipment_map = {e["id"]: e async for e in _db.equipment.find({"tenant_id": tenant_id}, {"_id": 0})}
    certs = await cs.list_certifications(tenant_id=tenant_id, employee_id=filters.get("employee_id"), equipment_id=filters.get("equipment_id"))
    emp_names = {e["id"]: e["name"] for e in employees}
    rows = []
    for c in certs:
        eq = equipment_map.get(c.get("equipment_id"), {})
        rows.append({
            "employee_name": emp_names.get(c["employee_id"], c["employee_id"]),
            "equipment_name": eq.get("name") or c.get("certification_type") or "—",
            "status": cs.effective_status(c), "issued_date": c.get("issued_date"),
            "expiration_date": c.get("expiration_date"), "expires_soon": c.get("expires_soon", False),
            "restrictions": c.get("restrictions"),
        })
    return rows


async def _expiring_certifications(*, tenant_id: str, filters: dict) -> list[dict]:
    rows = await _certification_matrix_flat(tenant_id=tenant_id, filters=filters)
    return [r for r in rows if r["expires_soon"] or r["status"] == "expired"]


async def _incomplete_training(*, tenant_id: str, filters: dict) -> list[dict]:
    from ..core.db import db as _db
    q: dict[str, Any] = {"tenant_id": tenant_id, "status": {"$in": ["not_started", "in_progress", "pending_signoff"]}}
    if filters.get("employee_id"): q["employee_id"] = filters["employee_id"]
    employees = {e["id"]: e["name"] async for e in _db.employees.find({"tenant_id": tenant_id}, {"_id": 0, "id": 1, "name": 1})}
    defs = {d["id"]: d["title"] async for d in _db.training_definitions.find({"tenant_id": tenant_id}, {"_id": 0, "id": 1, "title": 1})}
    rows = []
    async for a in _db.training_assignments.find(q, {"_id": 0}):
        a = serialize_doc(a)
        rows.append({
            "employee_name": employees.get(a["employee_id"], a["employee_id"]),
            "training_title": defs.get(a["training_definition_id"], a["training_definition_id"]),
            "status": a["status"], "progress_percent": a.get("progress_percent", 0),
            "due_date": a.get("due_date"), "assigned_at": a.get("assigned_at"),
        })
    return rows


async def _overdue_training(*, tenant_id: str, filters: dict) -> list[dict]:
    from . import training_service
    items = await training_service.list_assignments(tenant_id=tenant_id, employee_id=filters.get("employee_id"))
    from ..core.db import db as _db
    employees = {e["id"]: e["name"] async for e in _db.employees.find({"tenant_id": tenant_id}, {"_id": 0, "id": 1, "name": 1})}
    defs = {d["id"]: d["title"] async for d in _db.training_definitions.find({"tenant_id": tenant_id}, {"_id": 0, "id": 1, "title": 1})}
    return [{
        "employee_name": employees.get(a["employee_id"], a["employee_id"]),
        "training_title": defs.get(a["training_definition_id"], a["training_definition_id"]),
        "status": a["status"], "due_date": a.get("due_date"),
    } for a in items if a.get("overdue")]


async def _equipment_access_report(*, tenant_id: str, filters: dict) -> list[dict]:
    from . import equipment_service
    return await equipment_service.access_report(tenant_id=tenant_id)


REPORTS: dict[str, dict[str, Any]] = {
    # -- Inventory --
    "inventory.on_hand": {
        "title": "Inventory on hand", "category": "inventory",
        "perm": Perm.INVENTORY_READ,
        "data_source": "inventory_items", "date_basis": "n/a",
        "calc_basis": "current_inventory",
        "limitations": ["reserved qty subtracted from available",
                        "no valuation of finished goods"],
        "columns": [
            {"key": "material_sku", "label": "SKU"},
            {"key": "material_name", "label": "Material"},
            {"key": "category", "label": "Category"},
            {"key": "location_name", "label": "Location"},
            {"key": "quantity_on_hand", "label": "On hand"},
            {"key": "quantity_reserved", "label": "Reserved"},
            {"key": "quantity_available", "label": "Available"},
            _date_col("last_received_at", "Last received"),
        ], "run": _inventory_on_hand,
    },
    "inventory.low_stock": {
        "title": "Low stock", "category": "inventory",
        "perm": Perm.INVENTORY_READ,
        "data_source": "inventory_items", "date_basis": "n/a",
        "calc_basis": "current_inventory",
        "limitations": ["only materials with low_stock_threshold > 0"],
        "columns": [
            {"key": "material_sku", "label": "SKU"},
            {"key": "material_name", "label": "Material"},
            {"key": "location_name", "label": "Location"},
            {"key": "quantity_available", "label": "Available"},
            {"key": "low_stock_threshold", "label": "Threshold"},
        ], "run": _inventory_low_stock,
    },
    "inventory.movements": {
        "title": "Inventory movements", "category": "inventory",
        "perm": Perm.INVENTORY_READ,
        "data_source": "inventory_movements", "date_basis": "movement_ts",
        "calc_basis": "immutable_ledger",
        "limitations": ["capped at 25 000 rows"],
        "columns": [
            _date_col("created_at", "Timestamp"),
            {"key": "material_name", "label": "Material"},
            {"key": "material_sku", "label": "SKU"},
            {"key": "movement_type", "label": "Type"},
            {"key": "direction", "label": "Direction"},
            {"key": "quantity", "label": "Quantity"},
            {"key": "reason", "label": "Reason"},
            {"key": "source_entity_type", "label": "Linked type"},
            {"key": "source_entity_id", "label": "Linked id"},
        ], "run": _inventory_movements,
    },
    "inventory.material_cost_history": {
        "title": "Material cost history", "category": "inventory",
        "perm": Perm.INVENTORY_READ,
        "data_source": "material_cost_history", "date_basis": "effective_at",
        "calc_basis": "historical_snapshots",
        "limitations": ["capped at 25 000 rows"],
        "columns": [
            _date_col("effective_at", "Effective"),
            {"key": "material_name", "label": "Material"},
            {"key": "material_sku", "label": "SKU"},
            _money_col("cost_cents", "Cost"),
            {"key": "cost_unit", "label": "Unit"},
            {"key": "source", "label": "Source"},
            {"key": "source_ref", "label": "Source ref"},
        ], "run": _material_cost_history,
    },
    # -- Purchasing --
    "purchasing.pos_by_status": {
        "title": "Purchase Orders by status", "category": "purchasing",
        "perm": Perm.PURCHASING_READ,
        "data_source": "purchase_orders", "date_basis": "purchase_order_created_at",
        "calc_basis": "purchase_orders",
        "limitations": ["snapshot values at time of PO creation"],
        "columns": [
            {"key": "number", "label": "PO #"},
            {"key": "vendor_name", "label": "Vendor"},
            {"key": "status", "label": "Status"},
            _money_col("subtotal_cents", "Subtotal"),
            _money_col("shipping_cents", "Shipping"),
            _money_col("total_cents", "Total"),
            _date_col("created_at", "Created"),
            {"key": "tracking_status", "label": "Tracking"},
        ], "run": _po_by_status,
    },
    "purchasing.vendor_spend": {
        "title": "Vendor spend", "category": "purchasing",
        "perm": Perm.PURCHASING_READ,
        "data_source": "purchase_orders", "date_basis": "purchase_order_created_at",
        "calc_basis": "purchase_orders",
        "limitations": ["excludes draft and cancelled POs"],
        "columns": [
            {"key": "vendor_name", "label": "Vendor"},
            _money_col("spend_cents", "Spend"),
            {"key": "po_count", "label": "POs"},
        ], "run": _vendor_spend,
    },
    # -- Expenses --
    "expenses.by_category": {
        "title": "Expenses by category", "category": "expenses",
        "perm": Perm.EXPENSE_READ,
        "data_source": "expenses", "date_basis": "expense_date",
        "calc_basis": "expenses",
        "limitations": ["voided + archived excluded"],
        "columns": [
            {"key": "category_key", "label": "Category"},
            _money_col("value_cents", "Total"),
            {"key": "count", "label": "Count"},
        ], "run": _expenses_by_category,
    },
    "expenses.by_vendor": {
        "title": "Expenses by vendor", "category": "expenses",
        "perm": Perm.EXPENSE_READ,
        "data_source": "expenses", "date_basis": "expense_date",
        "calc_basis": "expenses",
        "limitations": ["voided + archived excluded; unlinked expenses grouped as '(no vendor)'"],
        "columns": [
            {"key": "vendor_name", "label": "Vendor"},
            _money_col("total_cents", "Total"),
            {"key": "count", "label": "Count"},
        ], "run": _expenses_by_vendor,
    },
    "expenses.all": {
        "title": "All expenses", "category": "expenses",
        "perm": Perm.EXPENSE_READ,
        "data_source": "expenses", "date_basis": "expense_date",
        "calc_basis": "expenses",
        "limitations": ["capped at 25 000 rows"],
        "columns": [
            {"key": "number", "label": "#"},
            _date_col("expense_date", "Date"),
            {"key": "category_label", "label": "Category"},
            {"key": "vendor_name", "label": "Vendor"},
            {"key": "description", "label": "Description"},
            _money_col("amount_cents", "Amount"),
            _money_col("tax_cents", "Tax"),
            _money_col("total_cents", "Total"),
            {"key": "payment_method", "label": "Payment"},
            {"key": "deductible_class", "label": "Deductible"},
            {"key": "state", "label": "State"},
        ], "run": _expenses_all,
    },
    # -- Finance --
    "finance.summary": {
        "title": "Finance summary metrics", "category": "finance",
        "perm": Perm.FINANCE_READ,
        "data_source": "invoices+payments+expenses", "date_basis": "mixed",
        "calc_basis": "labeled_metrics",
        "limitations": ["each row carries its own basis label — do not sum across rows"],
        "columns": [
            {"key": "metric", "label": "Metric"},
            {"key": "basis", "label": "Basis"},
            _money_col("value_cents", "Value"),
        ], "run": _finance_summary_flat,
    },
    "finance.top_customers": {
        "title": "Top customers by revenue", "category": "finance",
        "perm": Perm.FINANCE_READ,
        "data_source": "invoices", "date_basis": "issued_at",
        "calc_basis": "issued_invoices",
        "limitations": ["issued invoices only"],
        "columns": [
            {"key": "customer_name", "label": "Customer"},
            {"key": "customer_company", "label": "Company"},
            _money_col("revenue_cents", "Revenue"),
            {"key": "invoice_count", "label": "Invoices"},
        ], "run": _top_customers_flat,
    },
    # -- Tax --
    "tax.by_jurisdiction": {
        "title": "Tax collected by jurisdiction", "category": "tax",
        "perm": Perm.TAX_REPORT_READ,
        "data_source": "invoices", "date_basis": "issued_at",
        "calc_basis": "tax_collected",
        "limitations": ["invoice tax snapshots only — historical rates preserved",
                        "jurisdiction resolved via Invoice.tax_jurisdiction_snapshot when set, else Customer.state"],
        "columns": [
            {"key": "jurisdiction", "label": "Jurisdiction"},
            _money_col("subtotal_cents", "Subtotal"),
            _money_col("tax_cents", "Tax collected"),
            {"key": "invoice_count", "label": "Invoices"},
        ], "run": _tax_by_jurisdiction_flat,
    },
    "tax.manual_overrides": {
        "title": "Manual tax overrides", "category": "tax",
        "perm": Perm.TAX_REPORT_READ,
        "data_source": "invoices", "date_basis": "issued_at",
        "calc_basis": "tax_collected",
        "limitations": ["snapshotted values"],
        "columns": [
            {"key": "number", "label": "Invoice #"},
            _date_col("issued_at", "Issued"),
            _money_col("tax_cents", "Tax"),
            {"key": "override_reason", "label": "Reason"},
        ], "run": _tax_overrides_flat,
    },
    "tax.exempt_customers": {
        "title": "Exempt customers", "category": "tax",
        "perm": Perm.TAX_REPORT_READ,
        "data_source": "invoices+tax_exemptions", "date_basis": "issued_at",
        "calc_basis": "tax_collected",
        "limitations": ["shows tax charged even when customer has an active exemption — surfaces discrepancies"],
        "columns": [
            {"key": "customer_name", "label": "Customer"},
            {"key": "customer_company", "label": "Company"},
            {"key": "invoice_count", "label": "Invoices"},
            _money_col("subtotal_cents", "Subtotal"),
            _money_col("tax_cents", "Tax charged"),
        ], "run": _exempt_customers_flat,
    },
    # -- Payroll (EC8 phase 8d) --
    "payroll.by_period": {
        "title": "Payroll by Pay Period", "category": "payroll",
        "perm": Perm.PAYROLL_READ,
        "data_source": "payroll_snapshots+pay_periods", "date_basis": "period_start",
        "calc_basis": "payroll_ledger_derived",
        "limitations": ["gross-pay ledger only — no tax withholding or statutory deductions",
                        "figures reflect the ledger at report time; a still-open period may change"],
        "columns": [
            _date_col("period_start", "Week start"), _date_col("period_end", "Week end"),
            _date_col("payday", "Payday"), {"key": "period_status", "label": "Status"},
            {"key": "employee_name", "label": "Employee"},
            {"key": "regular_minutes", "label": "Regular min"}, {"key": "overtime_minutes", "label": "OT min"},
            _money_col("gross_regular_cents", "Regular pay"), _money_col("gross_overtime_cents", "OT pay"),
            _money_col("adjustment_total_cents", "Adjustments"), _money_col("advance_total_cents", "Advances"),
            _money_col("repayment_total_cents", "Repayments"), _money_col("payment_total_cents", "Payments"),
            _money_col("carryover_in_cents", "Carryover in"), _money_col("carryover_out_cents", "Carryover out"),
            _money_col("total_earned_cents", "Total earned"), _money_col("total_paid_cents", "Total paid"),
            _money_col("remaining_balance_cents", "Balance remaining"),
        ], "run": _payroll_by_period,
    },
    "payroll.by_employee": {
        "title": "Payroll by Employee", "category": "payroll",
        "perm": Perm.PAYROLL_READ,
        "data_source": "payroll_snapshots+pay_periods", "date_basis": "period_start",
        "calc_basis": "payroll_ledger_derived",
        "limitations": ["gross-pay ledger only — no tax withholding or statutory deductions",
                        "totals span every Pay Period matching the date filter"],
        "columns": [
            {"key": "employee_name", "label": "Employee"}, {"key": "period_count", "label": "Periods"},
            _money_col("total_regular_cents", "Regular pay"), _money_col("total_overtime_cents", "OT pay"),
            _money_col("total_adjustments_cents", "Adjustments"), _money_col("total_advances_cents", "Advances"),
            _money_col("total_repayments_cents", "Repayments"), _money_col("total_payments_cents", "Payments"),
            _money_col("total_carryover_in_cents", "Carryover in"), _money_col("total_carryover_out_cents", "Carryover out"),
            _money_col("total_earned_cents", "Total earned"), _money_col("total_remaining_cents", "Balance remaining"),
        ], "run": _payroll_by_employee,
    },
    # -- Equipment / Training / Certification (EC8 phase 8e) --
    "certification.matrix": {
        "title": "Certification Matrix", "category": "certification",
        "perm": Perm.CERTIFICATION_READ,
        "data_source": "certifications+employees+equipment", "date_basis": "issued_date",
        "calc_basis": "certification_ledger",
        "limitations": ["shows the most recent Certification per Employee+Equipment only"],
        "columns": [
            {"key": "employee_name", "label": "Employee"}, {"key": "equipment_name", "label": "Equipment / Type"},
            {"key": "status", "label": "Status"}, _date_col("issued_date", "Issued"), _date_col("expiration_date", "Expires"),
            {"key": "restrictions", "label": "Restrictions"},
        ], "run": _certification_matrix_flat,
    },
    "certification.expiring": {
        "title": "Expiring Certifications", "category": "certification",
        "perm": Perm.CERTIFICATION_READ,
        "data_source": "certifications", "date_basis": "expiration_date",
        "calc_basis": "certification_ledger",
        "limitations": ["'expiring soon' window is tenant-configurable (Settings > certification namespace)"],
        "columns": [
            {"key": "employee_name", "label": "Employee"}, {"key": "equipment_name", "label": "Equipment / Type"},
            {"key": "status", "label": "Status"}, _date_col("expiration_date", "Expires"),
        ], "run": _expiring_certifications,
    },
    "training.incomplete": {
        "title": "Incomplete Training", "category": "training",
        "perm": Perm.TRAINING_MANAGE,
        "data_source": "training_assignments", "date_basis": "assigned_at",
        "calc_basis": "assignment_status",
        "limitations": ["snapshot at report time — status changes as employees progress"],
        "columns": [
            {"key": "employee_name", "label": "Employee"}, {"key": "training_title", "label": "Training"},
            {"key": "status", "label": "Status"}, {"key": "progress_percent", "label": "Progress %"},
            _date_col("due_date", "Due"),
        ], "run": _incomplete_training,
    },
    "training.overdue": {
        "title": "Overdue Training", "category": "training",
        "perm": Perm.TRAINING_MANAGE,
        "data_source": "training_assignments", "date_basis": "due_date",
        "calc_basis": "due_date_past_and_incomplete",
        "limitations": ["overdue = due_date in the past and not completed/cancelled/failed"],
        "columns": [
            {"key": "employee_name", "label": "Employee"}, {"key": "training_title", "label": "Training"},
            {"key": "status", "label": "Status"}, _date_col("due_date", "Due"),
        ], "run": _overdue_training,
    },
    "equipment.access": {
        "title": "Equipment Access Report", "category": "equipment",
        "perm": Perm.EQUIPMENT_READ,
        "data_source": "equipment+certifications", "date_basis": "n/a",
        "calc_basis": "current_certification_counts",
        "limitations": ["counts reflect Certification status at report time"],
        "columns": [
            {"key": "equipment_name", "label": "Equipment"}, {"key": "category", "label": "Category"},
            {"key": "status", "label": "Status"}, {"key": "access_policy", "label": "Access policy"},
            {"key": "safety_sensitive", "label": "Safety sensitive"},
            {"key": "certified_employee_count", "label": "Certified"}, {"key": "expiring_soon_count", "label": "Expiring soon"},
            {"key": "expired_count", "label": "Expired"}, {"key": "revoked_count", "label": "Revoked"},
        ], "run": _equipment_access_report,
    },
}


def list_reports_for_user(user_perms: set[str]) -> list[dict]:
    """Return the report definitions the caller is allowed to see."""
    out: list[dict] = []
    for key, r in REPORTS.items():
        if r["perm"].value not in user_perms:
            continue
        out.append({
            "key": key, "title": r["title"], "category": r["category"],
            "data_source": r["data_source"], "date_basis": r["date_basis"],
            "calc_basis": r["calc_basis"], "limitations": r["limitations"],
            "columns": r["columns"],
        })
    return out


async def run_report(*, key: str, tenant_id: str, filters: dict,
                     user_perms: set[str], preview_limit: int = 500) -> dict:
    r = REPORTS.get(key)
    if not r:
        raise ValueError("unknown_report")
    if r["perm"].value not in user_perms:
        raise PermissionError("permission_denied")
    rows = await r["run"](tenant_id=tenant_id, filters=filters or {})
    total = len(rows)
    limited = rows[:max(int(preview_limit), 0)]
    return {
        "key": key, "title": r["title"], "category": r["category"],
        "data_source": r["data_source"], "date_basis": r["date_basis"],
        "calc_basis": r["calc_basis"], "limitations": r["limitations"],
        "columns": r["columns"], "rows": limited, "row_count": total,
        "preview_limit": preview_limit, "truncated": total > preview_limit,
        "filters": filters or {},
    }


# ---------------------------------------------------------------------------
# Custom Report Builder foundation
# ---------------------------------------------------------------------------
CUSTOM_DATASETS: dict[str, dict[str, Any]] = {
    "expenses": {
        "perm": Perm.EXPENSE_READ,
        "collection": "expenses",
        "date_field": "expense_date",
        "fields": ["number", "expense_date", "category_key", "category_label_snapshot",
                    "vendor_name_snapshot", "description", "amount_cents", "tax_cents",
                    "total_cents", "payment_method", "deductible_class", "state",
                    "recurring", "created_at"],
        "filters": ["state", "category_key", "vendor_id", "payment_method",
                    "deductible_class", "date_from", "date_to"],
        "group_by": ["category_key", "vendor_name_snapshot", "payment_method", "deductible_class"],
        "sort": ["expense_date", "total_cents", "number"],
    },
    "purchase_orders": {
        "perm": Perm.PURCHASING_READ,
        "collection": "purchase_orders",
        "date_field": "created_at",
        "fields": ["number", "status", "vendor_id", "vendor_snapshot",
                    "subtotal_cents", "shipping_cents", "handling_cents",
                    "total_cents", "created_at", "submitted_at", "tracking_status"],
        "filters": ["status", "vendor_id", "date_from", "date_to"],
        "group_by": ["status", "vendor_id"],
        "sort": ["created_at", "total_cents", "number"],
    },
    "invoices": {
        "perm": Perm.FINANCE_READ,
        "collection": "invoices",
        "date_field": "issued_at",
        "fields": ["number", "customer_id", "document_status", "financial_status",
                    "subtotal_cents", "tax_cents", "total_cents",
                    "amount_paid_cents", "balance_due_cents",
                    "issued_at", "due_date"],
        "filters": ["document_status", "financial_status", "customer_id",
                    "date_from", "date_to"],
        "group_by": ["document_status", "financial_status", "customer_id"],
        "sort": ["issued_at", "total_cents", "number"],
    },
}


def list_datasets_for_user(user_perms: set[str]) -> list[dict]:
    out: list[dict] = []
    for k, d in CUSTOM_DATASETS.items():
        if d["perm"].value not in user_perms:
            continue
        out.append({
            "key": k,
            "fields": d["fields"], "filters": d["filters"],
            "group_by": d["group_by"], "sort": d["sort"],
            "date_field": d["date_field"],
        })
    return out


async def run_custom_report(*, dataset_key: str, tenant_id: str, user_perms: set[str],
                            fields: list[str], filters: dict,
                            group_by: Optional[list[str]] = None,
                            sort: Optional[list[dict]] = None,
                            limit: int = 500) -> dict:
    ds = CUSTOM_DATASETS.get(dataset_key)
    if not ds:
        raise ValueError("unknown_dataset")
    if ds["perm"].value not in user_perms:
        raise PermissionError("permission_denied")
    allowed_fields = set(ds["fields"])
    if not fields or not all(f in allowed_fields for f in fields):
        raise ValueError("invalid_field_selection")
    allowed_filters = set(ds["filters"])
    for f in (filters or {}).keys():
        if f not in allowed_filters:
            raise ValueError(f"invalid_filter:{f}")
    if group_by:
        allowed_group = set(ds["group_by"])
        if not all(g in allowed_group for g in group_by):
            raise ValueError("invalid_group_by")
    q: dict[str, Any] = {"tenant_id": tenant_id}
    for k, v in (filters or {}).items():
        if v in (None, "", []):
            continue
        if k == "date_from":
            q.setdefault(ds["date_field"], {})["$gte"] = v
        elif k == "date_to":
            q.setdefault(ds["date_field"], {})["$lte"] = v + "T23:59:59.999999Z"
        else:
            q[k] = v
    projection = {"_id": 0, **{f: 1 for f in fields}}
    limit = max(1, min(int(limit), 25000))
    sort_spec: list[tuple[str, int]] = []
    for s in (sort or []):
        key = s.get("field")
        if key not in set(ds["sort"]):
            continue
        direction = -1 if s.get("dir") == "desc" else 1
        sort_spec.append((key, direction))
    cur = db[ds["collection"]].find(q, projection)
    if sort_spec:
        cur = cur.sort(sort_spec)
    cur = cur.limit(limit)
    rows: list[dict[str, Any]] = []
    async for r in cur:
        rows.append(serialize_doc(r))
    return {
        "dataset": dataset_key, "fields": fields, "filters": filters or {},
        "group_by": group_by or [], "sort": sort or [],
        "row_count": len(rows), "rows": rows,
        "limitations": ["approved datasets + fields only",
                        "cross-tenant reads disabled",
                        "max 25 000 rows"],
    }
