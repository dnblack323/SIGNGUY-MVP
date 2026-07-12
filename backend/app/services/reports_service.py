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
