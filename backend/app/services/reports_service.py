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
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Optional

from ..core.db import db
from ..core.time_utils import serialize_doc
from ..core.permissions import Perm
from ..models.webstore import WEBSTORE_TYPE_LABELS, WEBSTORE_TYPES
from . import finance_service, tax_service


APPROVED_WEBSTORE_TYPES = set(WEBSTORE_TYPES)
DEFAULT_LIMIT = 25000


def _now_date() -> date:
    return datetime.now(timezone.utc).date()


def _as_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value)[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _range_query(field: str, filters: dict[str, Any]) -> dict[str, Any]:
    rng: dict[str, Any] = {}
    if filters.get("date_from"):
        rng["$gte"] = filters["date_from"]
    if filters.get("date_to"):
        rng["$lte"] = filters["date_to"] + "T23:59:59.999999Z"
    return {field: rng} if rng else {}


def _month_key(value: Any) -> str:
    d = _as_date(value)
    return d.strftime("%Y-%m") if d else "unknown"


def _week_key(value: Any) -> str:
    d = _as_date(value)
    if not d:
        return "unknown"
    start = d - timedelta(days=d.weekday())
    return start.isoformat()


def _period_key(value: Any, period: str) -> str:
    d = _as_date(value)
    if not d:
        return "unknown"
    if period == "day":
        return d.isoformat()
    if period == "week":
        return _week_key(value)
    if period == "quarter":
        return f"{d.year}-Q{((d.month - 1) // 3) + 1}"
    if period == "year":
        return str(d.year)
    return _month_key(value)


def _money(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _pct(numerator: int | float, denominator: int | float) -> float:
    return round((float(numerator) / float(denominator)) * 100, 2) if denominator else 0.0


def _source_link(entity_type: str, entity_id: Any, route: str | None = None) -> dict[str, Any]:
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "route": route,
    }


def _validate_filter_values(filters: dict[str, Any] | None) -> None:
    for key, value in (filters or {}).items():
        if value in (None, ""):
            continue
        if isinstance(value, (dict, list, tuple, set)):
            raise ValueError(f"invalid_filter_value:{key}")


def _columns_with_drill_down(columns: list[dict[str, Any]], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not any(row.get("drill_down") for row in rows):
        return columns
    if any(col.get("key") == "drill_down" for col in columns):
        return columns
    return [*columns, {"key": "drill_down", "label": "Drill-down"}]


async def _customer_map(tenant_id: str) -> dict[str, dict[str, Any]]:
    return {
        c["id"]: c
        async for c in db.customers.find({"tenant_id": tenant_id}, {"_id": 0})
    }


async def _user_email_map(tenant_id: str) -> dict[str, str]:
    return {
        u["id"]: u.get("email") or u["id"]
        async for u in db.users.find({"tenant_id": tenant_id}, {"_id": 0, "id": 1, "email": 1})
    }


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


# -------- PDF-governed complete Report Builder reports --------
async def _overview_executive_summary(*, tenant_id: str, filters: dict) -> list[dict]:
    finance = await finance_service.dashboard_summary(
        tenant_id=tenant_id,
        date_from=filters.get("date_from"),
        date_to=filters.get("date_to"),
    )
    order_q = {"tenant_id": tenant_id, **_range_query("created_at", filters)}
    open_quote_q = {"tenant_id": tenant_id, "status": {"$in": ["draft", "sent", "viewed", "approved"]}}
    open_order_q = {"tenant_id": tenant_id, "status": {"$in": ["draft", "confirmed", "in_production", "ready"]}}
    sales_booked_cents = 0
    async for order in db.orders.find(order_q, {"_id": 0, "total_cents": 1}):
        sales_booked_cents += _money(order.get("total_cents"))
    open_quote_cents = 0
    async for quote in db.quotes.find(open_quote_q, {"_id": 0, "total_cents": 1}):
        open_quote_cents += _money(quote.get("total_cents"))
    open_order_cents = 0
    async for order in db.orders.find(open_order_q, {"_id": 0, "total_cents": 1}):
        open_order_cents += _money(order.get("total_cents"))
    estimated_profit_cents = 0
    async for item in db.order_items.find({"tenant_id": tenant_id}, {"_id": 0, "estimated_profit_cents": 1}):
        estimated_profit_cents += _money(item.get("estimated_profit_cents"))
    rows = [
        {"metric": "Revenue collected", "basis": "confirmed_payments", "value_cents": _money((finance.get("payments_received") or {}).get("value_cents")), "drill_down": [_source_link("payments", "confirmed")]},
        {"metric": "Sales booked", "basis": "orders_created", "value_cents": sales_booked_cents, "drill_down": [_source_link("orders", "date_range", "/orders")]},
        {"metric": "Open quote value", "basis": "open_quotes", "value_cents": open_quote_cents, "drill_down": [_source_link("quotes", "open", "/quotes")]},
        {"metric": "Open order value", "basis": "open_orders", "value_cents": open_order_cents, "drill_down": [_source_link("orders", "open", "/orders")]},
        {"metric": "Outstanding invoice balance", "basis": "invoice_balance_due", "value_cents": _money((finance.get("outstanding_receivables") or {}).get("value_cents")), "drill_down": [_source_link("invoices", "open")]},
        {"metric": "Estimated gross profit", "basis": "order_item_estimates", "value_cents": estimated_profit_cents, "drill_down": [_source_link("order_items", "estimated_profit")]},
        {"metric": "Low-stock alerts", "basis": "current_inventory", "count": len(await _inventory_low_stock(tenant_id=tenant_id, filters={})), "drill_down": [_source_link("inventory", "low_stock", "/inventory")]},
    ]
    return rows


async def _trend_summary(*, tenant_id: str, filters: dict) -> list[dict]:
    period = filters.get("period") or "month"
    buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {"period": "", "revenue_cents": 0, "order_count": 0, "order_value_cents": 0, "quote_count": 0, "converted_quote_count": 0, "labor_cost_cents": 0, "material_cost_cents": 0})
    async for p in db.payments.find({"tenant_id": tenant_id, "status": {"$in": ["confirmed", "partially_refunded", "refunded"]}, **_range_query("confirmed_at", filters)}, {"_id": 0}):
        key = _period_key(p.get("confirmed_at") or p.get("paid_on") or p.get("created_at"), period)
        buckets[key]["period"] = key
        buckets[key]["revenue_cents"] += _money(p.get("amount_cents"))
    async for o in db.orders.find({"tenant_id": tenant_id, **_range_query("created_at", filters)}, {"_id": 0}):
        key = _period_key(o.get("created_at"), period)
        buckets[key]["period"] = key
        buckets[key]["order_count"] += 1
        buckets[key]["order_value_cents"] += _money(o.get("total_cents"))
    async for q in db.quotes.find({"tenant_id": tenant_id, **_range_query("created_at", filters)}, {"_id": 0}):
        key = _period_key(q.get("created_at"), period)
        buckets[key]["period"] = key
        buckets[key]["quote_count"] += 1
        if q.get("status") == "converted" or q.get("converted_order_id"):
            buckets[key]["converted_quote_count"] += 1
    async for item in db.order_items.find({"tenant_id": tenant_id}, {"_id": 0, "created_at": 1, "pricing_snapshot": 1, "estimated_cost_cents": 1}):
        snap = item.get("pricing_snapshot") or {}
        details = snap.get("details") or snap.get("breakdown") or {}
        key = _period_key(item.get("created_at"), period)
        buckets[key]["period"] = key
        buckets[key]["labor_cost_cents"] += _money(details.get("labor_cost_cents") or snap.get("labor_cost_cents"))
        buckets[key]["material_cost_cents"] += _money(details.get("material_cost_cents") or snap.get("material_cost_cents") or item.get("estimated_cost_cents"))
    rows = []
    for key in sorted(buckets):
        row = buckets[key]
        row["average_order_value_cents"] = int(row["order_value_cents"] / row["order_count"]) if row["order_count"] else 0
        row["quote_conversion_percent"] = _pct(row["converted_quote_count"], row["quote_count"])
        rows.append(row)
    return rows


async def _orders_by_status(*, tenant_id: str, filters: dict) -> list[dict]:
    q = {"tenant_id": tenant_id, **_range_query("created_at", filters)}
    if filters.get("status"):
        q["status"] = filters["status"]
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"status": "", "order_count": 0, "value_cents": 0})
    async for o in db.orders.find(q, {"_id": 0}):
        status = o.get("status") or "unknown"
        grouped[status]["status"] = status
        grouped[status]["order_count"] += 1
        grouped[status]["value_cents"] += _money(o.get("total_cents"))
    return sorted(grouped.values(), key=lambda r: r["status"])


async def _orders_detail(*, tenant_id: str, filters: dict) -> list[dict]:
    q = {"tenant_id": tenant_id}
    q.update(_range_query("created_at", filters))
    if filters.get("status"):
        q["status"] = filters["status"]
    if filters.get("customer_id"):
        q["customer_id"] = filters["customer_id"]
    today = _now_date()
    mode = filters.get("mode")
    if mode == "open":
        q["status"] = {"$in": ["draft", "confirmed", "in_production", "ready"]}
    rows = []
    customers = await _customer_map(tenant_id)
    async for o in db.orders.find(q, {"_id": 0}).sort("created_at", -1).limit(DEFAULT_LIMIT):
        due = _as_date(o.get("due_date"))
        if mode == "late" and (not due or due >= today or o.get("status") in {"completed", "cancelled", "archived"}):
            continue
        if mode == "due_soon" and (not due or due > today + timedelta(days=7) or o.get("status") in {"completed", "cancelled", "archived"}):
            continue
        customer = customers.get(o.get("customer_id"), {})
        rows.append({
            "number": o.get("number"),
            "title": o.get("title") or o.get("job_name"),
            "customer_name": customer.get("name"),
            "status": o.get("status"),
            "due_date": o.get("due_date"),
            "total_cents": _money(o.get("total_cents")),
            "age_days": (today - (_as_date(o.get("created_at")) or today)).days,
            "drill_down": [_source_link("order", o.get("id"), f"/orders/{o.get('id')}")],
        })
    return rows


async def _order_item_profitability(*, tenant_id: str, filters: dict) -> list[dict]:
    group = filters.get("group_by") or "order"
    order_map = {o["id"]: o async for o in db.orders.find({"tenant_id": tenant_id}, {"_id": 0})}
    customer_map = await _customer_map(tenant_id)
    grouped: dict[str, dict[str, Any]] = {}
    async for item in db.order_items.find({"tenant_id": tenant_id}, {"_id": 0}).limit(DEFAULT_LIMIT):
        order = order_map.get(item.get("order_id"), {})
        customer = customer_map.get(order.get("customer_id"), {})
        if group == "category":
            key = item.get("category") or item.get("product_type") or "uncategorized"
            label = key
        elif group == "customer":
            key = order.get("customer_id") or "unknown"
            label = customer.get("name") or key
        else:
            key = item.get("order_id") or "unknown"
            label = order.get("title") or order.get("job_name") or key
        row = grouped.setdefault(key, {"group": label, "item_count": 0, "revenue_cents": 0, "estimated_cost_cents": 0, "estimated_profit_cents": 0})
        row["item_count"] += 1
        revenue = _money(item.get("line_total_cents") or item.get("unit_price_cents"))
        cost = _money(item.get("estimated_cost_cents"))
        profit = item.get("estimated_profit_cents")
        row["revenue_cents"] += revenue
        row["estimated_cost_cents"] += cost
        row["estimated_profit_cents"] += _money(profit if profit is not None else revenue - cost)
    for row in grouped.values():
        row["gross_margin_percent"] = _pct(row["estimated_profit_cents"], row["revenue_cents"])
    return sorted(grouped.values(), key=lambda r: r["estimated_profit_cents"], reverse=True)


async def _quotes_by_status(*, tenant_id: str, filters: dict) -> list[dict]:
    q = {"tenant_id": tenant_id, **_range_query("created_at", filters)}
    if filters.get("status"):
        q["status"] = filters["status"]
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"status": "", "quote_count": 0, "value_cents": 0, "converted_count": 0})
    async for quote in db.quotes.find(q, {"_id": 0}):
        status = quote.get("status") or "unknown"
        grouped[status]["status"] = status
        grouped[status]["quote_count"] += 1
        grouped[status]["value_cents"] += _money(quote.get("total_cents"))
        if status == "converted" or quote.get("converted_order_id"):
            grouped[status]["converted_count"] += 1
    for row in grouped.values():
        row["conversion_percent"] = _pct(row["converted_count"], row["quote_count"])
        row["average_quote_value_cents"] = int(row["value_cents"] / row["quote_count"]) if row["quote_count"] else 0
    return sorted(grouped.values(), key=lambda r: r["status"])


async def _quotes_needing_followup(*, tenant_id: str, filters: dict) -> list[dict]:
    cutoff = (_now_date() - timedelta(days=int(filters.get("age_days") or 7))).isoformat()
    q = {"tenant_id": tenant_id, "status": {"$in": ["sent", "viewed"]}, "created_at": {"$lte": cutoff + "T23:59:59.999999Z"}}
    customers = await _customer_map(tenant_id)
    rows = []
    async for quote in db.quotes.find(q, {"_id": 0}).sort("created_at", 1).limit(DEFAULT_LIMIT):
        customer = customers.get(quote.get("customer_id"), {})
        rows.append({
            "number": quote.get("number"),
            "job_name": quote.get("job_name"),
            "customer_name": customer.get("name"),
            "status": quote.get("status"),
            "total_cents": _money(quote.get("total_cents")),
            "created_at": quote.get("created_at"),
            "drill_down": [_source_link("quote", quote.get("id"), f"/quotes/{quote.get('id')}")],
        })
    return rows


async def _customer_performance(*, tenant_id: str, filters: dict) -> list[dict]:
    customers = await _customer_map(tenant_id)
    grouped: dict[str, dict[str, Any]] = {
        cid: {
            "customer_id": cid,
            "customer_name": c.get("name"),
            "company": c.get("company"),
            "order_count": 0,
            "lifetime_value_cents": 0,
            "estimated_profit_cents": 0,
            "first_purchase_at": None,
            "last_purchase_at": None,
        }
        for cid, c in customers.items()
    }
    async for order in db.orders.find({"tenant_id": tenant_id}, {"_id": 0}):
        row = grouped.setdefault(order.get("customer_id"), {"customer_id": order.get("customer_id"), "customer_name": order.get("customer_id"), "company": None, "order_count": 0, "lifetime_value_cents": 0, "estimated_profit_cents": 0, "first_purchase_at": None, "last_purchase_at": None})
        row["order_count"] += 1
        row["lifetime_value_cents"] += _money(order.get("total_cents"))
        created = order.get("created_at")
        if not row["first_purchase_at"] or str(created) < str(row["first_purchase_at"]):
            row["first_purchase_at"] = created
        if not row["last_purchase_at"] or str(created) > str(row["last_purchase_at"]):
            row["last_purchase_at"] = created
    profits = await _order_item_profitability(tenant_id=tenant_id, filters={"group_by": "customer"})
    profit_by_name = {p["group"]: p["estimated_profit_cents"] for p in profits}
    for row in grouped.values():
        row["estimated_profit_cents"] = profit_by_name.get(row.get("customer_name"), 0)
        row["purchase_frequency"] = row["order_count"]
        row["inactive"] = not row["last_purchase_at"] or (_now_date() - (_as_date(row["last_purchase_at"]) or _now_date())).days >= int(filters.get("inactive_days") or 180)
        row["drill_down"] = [_source_link("customer", row["customer_id"], f"/customers/{row['customer_id']}")]
    return sorted(grouped.values(), key=lambda r: r["lifetime_value_cents"], reverse=True)


async def _payments_collected(*, tenant_id: str, filters: dict) -> list[dict]:
    q = {"tenant_id": tenant_id, **_range_query("confirmed_at", filters)}
    if filters.get("status"):
        q["status"] = filters["status"]
    else:
        q["status"] = {"$in": ["confirmed", "partially_refunded", "refunded", "failed"]}
    if filters.get("method"):
        q["method"] = filters["method"]
    rows = []
    async for p in db.payments.find(q, {"_id": 0}).sort("confirmed_at", -1).limit(DEFAULT_LIMIT):
        rows.append({
            "payment_number": p.get("number"),
            "status": p.get("status"),
            "method": p.get("method") or p.get("source"),
            "amount_cents": _money(p.get("amount_cents")),
            "confirmed_at": p.get("confirmed_at") or p.get("paid_on"),
            "invoice_id": p.get("invoice_id"),
            "customer_id": p.get("customer_id"),
            "drill_down": [_source_link("payment", p.get("id"))],
        })
    return rows


async def _payment_method_mix(*, tenant_id: str, filters: dict) -> list[dict]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"method": "", "payment_count": 0, "amount_cents": 0})
    for p in await _payments_collected(tenant_id=tenant_id, filters=filters):
        method = p.get("method") or "unknown"
        grouped[method]["method"] = method
        grouped[method]["payment_count"] += 1
        grouped[method]["amount_cents"] += _money(p.get("amount_cents"))
    return sorted(grouped.values(), key=lambda r: r["amount_cents"], reverse=True)


async def _invoice_aging(*, tenant_id: str, filters: dict) -> list[dict]:
    buckets = {
        "current": {"bucket": "current", "invoice_count": 0, "balance_due_cents": 0},
        "1-30": {"bucket": "1-30", "invoice_count": 0, "balance_due_cents": 0},
        "31-60": {"bucket": "31-60", "invoice_count": 0, "balance_due_cents": 0},
        "61-90": {"bucket": "61-90", "invoice_count": 0, "balance_due_cents": 0},
        "90+": {"bucket": "90+", "invoice_count": 0, "balance_due_cents": 0},
    }
    today = _now_date()
    async for inv in db.invoices.find({"tenant_id": tenant_id, "document_status": {"$ne": "void"}, "financial_status": {"$in": ["unpaid", "partial"]}}, {"_id": 0}):
        due = _as_date(inv.get("due_date"))
        age = (today - due).days if due else 0
        key = "current" if age <= 0 else "1-30" if age <= 30 else "31-60" if age <= 60 else "61-90" if age <= 90 else "90+"
        buckets[key]["invoice_count"] += 1
        buckets[key]["balance_due_cents"] += _money(inv.get("balance_due_cents"))
    return list(buckets.values())


async def _webstore_sales_by_store(*, tenant_id: str, filters: dict) -> list[dict]:
    stores = {s["id"]: s async for s in db.webstores.find({"tenant_id": tenant_id}, {"_id": 0})}
    grouped: dict[str, dict[str, Any]] = {}
    async for order in db.webstore_buyer_orders.find({"tenant_id": tenant_id, **_range_query("created_at", filters)}, {"_id": 0}):
        store = stores.get(order.get("webstore_id"), {})
        store_type = store.get("store_type") or "general"
        official_type = store_type if store_type in APPROVED_WEBSTORE_TYPES else "other_or_legacy"
        row = grouped.setdefault(order.get("webstore_id"), {"webstore_id": order.get("webstore_id"), "store_name": store.get("name"), "store_type": official_type, "order_count": 0, "sales_cents": 0, "donation_cents": 0, "tax_cents": 0, "shipping_cents": 0})
        row["order_count"] += 1
        row["sales_cents"] += _money(order.get("total_cents"))
        row["donation_cents"] += _money(order.get("donation_cents"))
        row["tax_cents"] += _money(order.get("tax_cents"))
        row["shipping_cents"] += _money(order.get("shipping_cents"))
    for row in grouped.values():
        row["average_order_value_cents"] = int(row["sales_cents"] / row["order_count"]) if row["order_count"] else 0
        row["drill_down"] = [_source_link("webstore", row["webstore_id"], f"/webstores/{row['webstore_id']}")]
    return sorted(grouped.values(), key=lambda r: r["sales_cents"], reverse=True)


async def _webstore_product_performance(*, tenant_id: str, filters: dict) -> list[dict]:
    products = {p["id"]: p async for p in db.webstore_products.find({"tenant_id": tenant_id}, {"_id": 0})}
    grouped: dict[str, dict[str, Any]] = {}
    async for order in db.webstore_buyer_orders.find({"tenant_id": tenant_id, **_range_query("created_at", filters)}, {"_id": 0}):
        for line in order.get("line_items") or []:
            pid = line.get("product_id")
            product = products.get(pid, {})
            row = grouped.setdefault(pid, {"product_id": pid, "product_name": line.get("name") or product.get("name"), "quantity": 0, "revenue_cents": 0, "production_cost_cents": 0})
            qty = int(line.get("quantity") or 0)
            row["quantity"] += qty
            row["revenue_cents"] += _money(line.get("line_total_cents"))
            row["production_cost_cents"] += _money(product.get("production_cost_cents")) * qty
    for row in grouped.values():
        row["estimated_margin_cents"] = row["revenue_cents"] - row["production_cost_cents"]
        row["gross_margin_percent"] = _pct(row["estimated_margin_cents"], row["revenue_cents"])
    return sorted(grouped.values(), key=lambda r: r["quantity"], reverse=True)


async def _webstore_ledger_summary(*, tenant_id: str, filters: dict) -> list[dict]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"entry_type": "", "entry_count": 0, "amount_cents": 0})
    async for entry in db.webstore_ledger_entries.find({"tenant_id": tenant_id, **_range_query("created_at", filters)}, {"_id": 0}):
        typ = entry.get("entry_type") or "unknown"
        grouped[typ]["entry_type"] = typ
        grouped[typ]["entry_count"] += 1
        grouped[typ]["amount_cents"] += _money(entry.get("amount_cents"))
    return sorted(grouped.values(), key=lambda r: r["amount_cents"], reverse=True)


async def _inventory_value(*, tenant_id: str, filters: dict) -> list[dict]:
    materials = {m["id"]: m async for m in db.materials.find({"tenant_id": tenant_id}, {"_id": 0})}
    rows = []
    async for item in db.inventory_items.find({"tenant_id": tenant_id}, {"_id": 0}):
        material = materials.get(item.get("material_id"), {})
        quantity = float(item.get("quantity_on_hand") or 0)
        cost = _money(material.get("current_cost_cents"))
        rows.append({
            "material_name": material.get("name"),
            "sku": material.get("sku"),
            "quantity_on_hand": quantity,
            "cost_cents": cost,
            "inventory_value_cents": int(quantity * cost),
            "drill_down": [_source_link("material", item.get("material_id"), f"/materials/{item.get('material_id')}")],
        })
    return sorted(rows, key=lambda r: r["inventory_value_cents"], reverse=True)


async def _time_hours_by_employee(*, tenant_id: str, filters: dict) -> list[dict]:
    employees = {e["id"]: e async for e in db.employees.find({"tenant_id": tenant_id}, {"_id": 0})}
    grouped: dict[str, dict[str, Any]] = {}
    async for entry in db.time_entries.find({"tenant_id": tenant_id, **_range_query("work_date", filters)}, {"_id": 0}):
        emp = employees.get(entry.get("employee_id"), {})
        row = grouped.setdefault(entry.get("employee_id"), {"employee_id": entry.get("employee_id"), "employee_name": emp.get("name"), "entry_count": 0, "worked_minutes": 0, "regular_minutes": 0, "overtime_minutes": 0, "missed_clock_count": 0})
        row["entry_count"] += 1
        row["worked_minutes"] += int(entry.get("worked_minutes") or 0)
        row["regular_minutes"] += int(entry.get("regular_minutes") or 0)
        row["overtime_minutes"] += int(entry.get("overtime_minutes") or 0)
        if entry.get("status") == "open" or not entry.get("clock_out_at"):
            row["missed_clock_count"] += 1
    for row in grouped.values():
        row["worked_hours"] = round(row["worked_minutes"] / 60, 2)
    return sorted(grouped.values(), key=lambda r: r["worked_minutes"], reverse=True)


async def _time_off_summary(*, tenant_id: str, filters: dict) -> list[dict]:
    employees = {e["id"]: e.get("name") async for e in db.employees.find({"tenant_id": tenant_id}, {"_id": 0, "id": 1, "name": 1})}
    rows = []
    async for req in db.time_off_requests.find({"tenant_id": tenant_id, **_range_query("start_at", filters)}, {"_id": 0}).sort("start_at", 1).limit(DEFAULT_LIMIT):
        rows.append({
            "employee_name": employees.get(req.get("employee_id"), req.get("employee_id")),
            "request_type": req.get("request_type"),
            "status": req.get("status"),
            "start_at": req.get("start_at"),
            "end_at": req.get("end_at"),
            "all_day": req.get("all_day"),
        })
    return rows


async def _wrap_project_performance(*, tenant_id: str, filters: dict) -> list[dict]:
    vehicles = {v["id"]: v async for v in db.wrap_vehicles.find({"tenant_id": tenant_id}, {"_id": 0})}
    grouped: dict[str, dict[str, Any]] = {}
    async for p in db.wrap_projects.find({"tenant_id": tenant_id, **_range_query("created_at", filters)}, {"_id": 0}):
        vehicle = vehicles.get(p.get("vehicle_id"), {})
        key = vehicle.get("vehicle_type") or p.get("project_type") or "unknown"
        row = grouped.setdefault(key, {"vehicle_or_project_type": key, "project_count": 0, "estimate_total_cents": 0, "deposit_required_cents": 0, "material_estimate_cents": 0, "labor_estimate_cents": 0, "completed_count": 0})
        row["project_count"] += 1
        row["estimate_total_cents"] += _money(p.get("estimate_total_cents"))
        row["deposit_required_cents"] += _money(p.get("deposit_required_cents"))
        row["material_estimate_cents"] += _money(p.get("material_estimate_cents"))
        row["labor_estimate_cents"] += _money(p.get("labor_estimate_cents"))
        if p.get("status") in {"completed", "warranty_active"}:
            row["completed_count"] += 1
    for row in grouped.values():
        row["estimated_profit_cents"] = row["estimate_total_cents"] - row["material_estimate_cents"] - row["labor_estimate_cents"]
        row["completion_rate_percent"] = _pct(row["completed_count"], row["project_count"])
    return sorted(grouped.values(), key=lambda r: r["estimate_total_cents"], reverse=True)


async def _wrap_material_use(*, tenant_id: str, filters: dict) -> list[dict]:
    projects = {p["id"]: p async for p in db.wrap_projects.find({"tenant_id": tenant_id}, {"_id": 0})}
    rows = []
    async for plan in db.wrap_panel_plans.find({"tenant_id": tenant_id}, {"_id": 0}).sort("created_at", -1).limit(DEFAULT_LIMIT):
        project = projects.get(plan.get("project_id"), {})
        rows.append({
            "project_name": project.get("project_name"),
            "status": plan.get("status"),
            "revision": plan.get("revision"),
            "material_usage_square_feet": plan.get("material_usage_square_feet", 0),
            "material_cost_cents": _money(plan.get("material_cost_cents")),
            "labor_cost_cents": _money(plan.get("labor_cost_cents")),
            "drill_down": [_source_link("wrap_project", plan.get("project_id"), f"/wrap-lab?project_id={plan.get('project_id')}")],
        })
    return rows


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


_METRIC_COLUMNS = [
    {"key": "metric", "label": "Metric"},
    {"key": "basis", "label": "Basis"},
    _money_col("value_cents", "Value"),
    {"key": "count", "label": "Count"},
]

_PERIOD_COLUMNS = [
    {"key": "period", "label": "Period"},
    _money_col("revenue_cents", "Revenue"),
    {"key": "order_count", "label": "Orders"},
    _money_col("order_value_cents", "Order value"),
    _money_col("average_order_value_cents", "Average order value"),
    {"key": "quote_count", "label": "Quotes"},
    {"key": "quote_conversion_percent", "label": "Quote conversion %"},
    _money_col("labor_cost_cents", "Labor cost"),
    _money_col("material_cost_cents", "Material cost"),
]

REPORTS.update({
    "overview.executive_summary": {
        "title": "Executive Summary",
        "category": "overview",
        "perm": Perm.REPORT_READ,
        "data_source": "finance+orders+quotes+inventory",
        "date_basis": "mixed",
        "calc_basis": "stored_source_values",
        "limitations": ["Each row declares its basis; do not sum mixed-basis metrics."],
        "columns": _METRIC_COLUMNS,
        "run": _overview_executive_summary,
    },
    "overview.trends": {
        "title": "Business Trends",
        "category": "overview",
        "perm": Perm.REPORT_READ,
        "data_source": "payments+orders+quotes+order_items",
        "date_basis": "mixed",
        "calc_basis": "stored_source_values",
        "limitations": ["Trend buckets use stored source dates and do not recalculate pricing."],
        "columns": _PERIOD_COLUMNS,
        "run": _trend_summary,
    },
    "orders.by_status": {
        "title": "Orders by Status",
        "category": "operations",
        "perm": Perm.ORDER_READ,
        "data_source": "orders",
        "date_basis": "created_at",
        "calc_basis": "stored_order_totals",
        "limitations": ["Uses stored order totals and statuses."],
        "columns": [{"key": "status", "label": "Status"}, {"key": "order_count", "label": "Orders"}, _money_col("value_cents", "Value")],
        "run": _orders_by_status,
    },
    "orders.detail": {
        "title": "Order Detail",
        "category": "operations",
        "perm": Perm.ORDER_READ,
        "data_source": "orders+customers",
        "date_basis": "created_at",
        "calc_basis": "stored_order_totals",
        "limitations": ["Mode filter may select open, due soon, or late orders."],
        "columns": [
            {"key": "number", "label": "Order #"},
            {"key": "title", "label": "Job"},
            {"key": "customer_name", "label": "Customer"},
            {"key": "status", "label": "Status"},
            _date_col("due_date", "Due"),
            _money_col("total_cents", "Total"),
            {"key": "age_days", "label": "Age days"},
        ],
        "run": _orders_detail,
    },
    "orders.profitability": {
        "title": "Order Profitability",
        "category": "financial",
        "perm": Perm.ORDER_READ,
        "data_source": "order_items",
        "date_basis": "created_at",
        "calc_basis": "stored_line_item_estimates",
        "limitations": ["Profit values use stored line-item estimates only; no recalculation occurs."],
        "columns": [
            {"key": "group", "label": "Group"},
            {"key": "item_count", "label": "Items"},
            _money_col("revenue_cents", "Revenue"),
            _money_col("estimated_cost_cents", "Estimated cost"),
            _money_col("estimated_profit_cents", "Estimated profit"),
            {"key": "gross_margin_percent", "label": "Gross margin %"},
        ],
        "run": _order_item_profitability,
    },
    "quotes.by_status": {
        "title": "Quotes by Status",
        "category": "customers_sales",
        "perm": Perm.QUOTE_READ,
        "data_source": "quotes",
        "date_basis": "created_at",
        "calc_basis": "stored_quote_totals",
        "limitations": ["Uses stored quote totals and conversion markers."],
        "columns": [
            {"key": "status", "label": "Status"},
            {"key": "quote_count", "label": "Quotes"},
            _money_col("value_cents", "Value"),
            {"key": "converted_count", "label": "Converted"},
            {"key": "conversion_percent", "label": "Conversion %"},
            _money_col("average_quote_value_cents", "Average quote value"),
        ],
        "run": _quotes_by_status,
    },
    "quotes.followup": {
        "title": "Quotes Needing Follow-Up",
        "category": "customers_sales",
        "perm": Perm.QUOTE_READ,
        "data_source": "quotes+customers",
        "date_basis": "created_at",
        "calc_basis": "stored_quote_status",
        "limitations": ["Default follow-up age is seven days unless filtered."],
        "columns": [
            {"key": "number", "label": "Quote #"},
            {"key": "job_name", "label": "Job"},
            {"key": "customer_name", "label": "Customer"},
            {"key": "status", "label": "Status"},
            _money_col("total_cents", "Total"),
            _date_col("created_at", "Created"),
        ],
        "run": _quotes_needing_followup,
    },
    "customers.performance": {
        "title": "Customer Performance",
        "category": "customers_sales",
        "perm": Perm.CUSTOMER_READ,
        "data_source": "customers+orders+order_items",
        "date_basis": "created_at",
        "calc_basis": "stored_order_totals",
        "limitations": ["Customer profitability uses stored line-item estimates only."],
        "columns": [
            {"key": "customer_name", "label": "Customer"},
            {"key": "company", "label": "Company"},
            {"key": "order_count", "label": "Orders"},
            _money_col("lifetime_value_cents", "Lifetime value"),
            _money_col("estimated_profit_cents", "Estimated profit"),
            _date_col("first_purchase_at", "First purchase"),
            _date_col("last_purchase_at", "Last purchase"),
            {"key": "inactive", "label": "Inactive"},
        ],
        "run": _customer_performance,
    },
    "finance.invoice_aging": {
        "title": "Invoice Aging",
        "category": "financial",
        "perm": Perm.FINANCE_READ,
        "data_source": "invoices",
        "date_basis": "due_date",
        "calc_basis": "stored_invoice_balance",
        "limitations": ["Aging uses stored invoice balance due."],
        "columns": [{"key": "bucket", "label": "Bucket"}, {"key": "invoice_count", "label": "Invoices"}, _money_col("balance_due_cents", "Balance due")],
        "run": _invoice_aging,
    },
    "finance.payments_collected": {
        "title": "Payments Collected",
        "category": "financial",
        "perm": Perm.FINANCE_READ,
        "data_source": "payments",
        "date_basis": "confirmed_at",
        "calc_basis": "confirmed_payments",
        "limitations": ["Uses payment records and refund status snapshots."],
        "columns": [
            {"key": "payment_number", "label": "Payment #"},
            {"key": "status", "label": "Status"},
            {"key": "method", "label": "Method"},
            _money_col("amount_cents", "Amount"),
            _date_col("confirmed_at", "Confirmed"),
            {"key": "invoice_id", "label": "Invoice"},
        ],
        "run": _payments_collected,
    },
    "finance.payment_method_mix": {
        "title": "Payment Method Mix",
        "category": "financial",
        "perm": Perm.FINANCE_READ,
        "data_source": "payments",
        "date_basis": "confirmed_at",
        "calc_basis": "confirmed_payments",
        "limitations": ["Uses stored confirmed payment method values."],
        "columns": [{"key": "method", "label": "Method"}, {"key": "payment_count", "label": "Payments"}, _money_col("amount_cents", "Amount")],
        "run": _payment_method_mix,
    },
    "webstores.sales_by_store": {
        "title": "Webstore Sales by Store",
        "category": "webstores",
        "perm": Perm.WEBSTORE_READ,
        "data_source": "webstores+webstore_buyer_orders",
        "date_basis": "created_at",
        "calc_basis": "stored_webstore_order_totals",
        "limitations": [
            f"Official Webstore types are {', '.join(WEBSTORE_TYPE_LABELS[store_type] for store_type in WEBSTORE_TYPES)}; persisted legacy or unknown values are grouped as other_or_legacy."
        ],
        "columns": [
            {"key": "store_name", "label": "Store"},
            {"key": "store_type", "label": "Type"},
            {"key": "order_count", "label": "Orders"},
            _money_col("sales_cents", "Sales"),
            _money_col("donation_cents", "Donations"),
            _money_col("tax_cents", "Tax"),
            _money_col("shipping_cents", "Shipping"),
            _money_col("average_order_value_cents", "Average order value"),
        ],
        "run": _webstore_sales_by_store,
    },
    "webstores.product_performance": {
        "title": "Webstore Product Performance",
        "category": "webstores",
        "perm": Perm.WEBSTORE_READ,
        "data_source": "webstore_buyer_orders+webstore_products",
        "date_basis": "created_at",
        "calc_basis": "stored_webstore_line_items",
        "limitations": ["Uses stored buyer order line items and existing product cost snapshots where present."],
        "columns": [
            {"key": "product_name", "label": "Product"},
            {"key": "quantity", "label": "Quantity"},
            _money_col("revenue_cents", "Revenue"),
            _money_col("production_cost_cents", "Production cost"),
            _money_col("estimated_margin_cents", "Estimated margin"),
            {"key": "gross_margin_percent", "label": "Gross margin %"},
        ],
        "run": _webstore_product_performance,
    },
    "webstores.ledger_summary": {
        "title": "Webstore Ledger Summary",
        "category": "webstores",
        "perm": Perm.WEBSTORE_READ,
        "data_source": "webstore_ledger_entries",
        "date_basis": "created_at",
        "calc_basis": "stored_webstore_ledger",
        "limitations": ["Reads ledger entries only; payout workflows are unchanged."],
        "columns": [{"key": "entry_type", "label": "Entry type"}, {"key": "entry_count", "label": "Entries"}, _money_col("amount_cents", "Amount")],
        "run": _webstore_ledger_summary,
    },
    "inventory.value": {
        "title": "Inventory Value",
        "category": "materials_purchasing",
        "perm": Perm.INVENTORY_READ,
        "data_source": "inventory_items+materials",
        "date_basis": "n/a",
        "calc_basis": "current_material_cost_snapshot",
        "limitations": ["Uses current stored material cost; does not value finished goods."],
        "columns": [
            {"key": "sku", "label": "SKU"},
            {"key": "material_name", "label": "Material"},
            {"key": "quantity_on_hand", "label": "On hand"},
            _money_col("cost_cents", "Cost"),
            _money_col("inventory_value_cents", "Value"),
        ],
        "run": _inventory_value,
    },
    "time.hours_by_employee": {
        "title": "Hours by Employee",
        "category": "team_labor",
        "perm": Perm.TIMECLOCK_MANAGE,
        "data_source": "time_entries+employees",
        "date_basis": "work_date",
        "calc_basis": "stored_time_entries",
        "limitations": ["Reads time entries only; payroll posting is unchanged."],
        "columns": [
            {"key": "employee_name", "label": "Employee"},
            {"key": "entry_count", "label": "Entries"},
            {"key": "worked_hours", "label": "Worked hours"},
            {"key": "regular_minutes", "label": "Regular minutes"},
            {"key": "overtime_minutes", "label": "Overtime minutes"},
            {"key": "missed_clock_count", "label": "Missed clocks"},
        ],
        "run": _time_hours_by_employee,
    },
    "time.time_off": {
        "title": "Time Off Summary",
        "category": "team_labor",
        "perm": Perm.EMPLOYEE_READ,
        "data_source": "time_off_requests+employees",
        "date_basis": "start_at",
        "calc_basis": "stored_time_off_requests",
        "limitations": ["Employee schedule publishing remains in Team scheduling."],
        "columns": [
            {"key": "employee_name", "label": "Employee"},
            {"key": "request_type", "label": "Type"},
            {"key": "status", "label": "Status"},
            _date_col("start_at", "Start"),
            _date_col("end_at", "End"),
            {"key": "all_day", "label": "All day"},
        ],
        "run": _time_off_summary,
    },
    "wraplab.project_performance": {
        "title": "Wrap Lab Project Performance",
        "category": "wrap_lab",
        "perm": Perm.WRAP_LAB_READ,
        "data_source": "wrap_projects+wrap_vehicles",
        "date_basis": "created_at",
        "calc_basis": "stored_wrap_project_estimates",
        "limitations": ["Reads stored Wrap Lab project values only; workflow and pricing remain unchanged."],
        "columns": [
            {"key": "vehicle_or_project_type", "label": "Vehicle/project type"},
            {"key": "project_count", "label": "Projects"},
            _money_col("estimate_total_cents", "Estimate total"),
            _money_col("material_estimate_cents", "Material estimate"),
            _money_col("labor_estimate_cents", "Labor estimate"),
            _money_col("estimated_profit_cents", "Estimated profit"),
            {"key": "completion_rate_percent", "label": "Completion rate %"},
        ],
        "run": _wrap_project_performance,
    },
    "wraplab.material_use": {
        "title": "Wrap Lab Material Use",
        "category": "wrap_lab",
        "perm": Perm.WRAP_LAB_READ,
        "data_source": "wrap_panel_plans+wrap_projects",
        "date_basis": "created_at",
        "calc_basis": "stored_wrap_panel_plans",
        "limitations": ["Reads stored panel plan values only."],
        "columns": [
            {"key": "project_name", "label": "Project"},
            {"key": "status", "label": "Status"},
            {"key": "revision", "label": "Revision"},
            {"key": "material_usage_square_feet", "label": "Sq ft"},
            _money_col("material_cost_cents", "Material cost"),
            _money_col("labor_cost_cents", "Labor cost"),
        ],
        "run": _wrap_material_use,
    },
})


BLOCKED_REPORT_REQUIREMENTS: list[dict[str, Any]] = [
    {
        "id": "RB-DASHBOARD-WIDGET-PUBLISH",
        "name": "Publish report widgets to dashboards",
        "status": "blocked",
        "reason": "Dashboard Customizer contract is not implemented yet; reporting exposes dashboard_widget metadata only.",
    },
    {
        "id": "RB-WEBSTORE-PAYOUT-DETAIL",
        "name": "Detailed webstore payout reports",
        "status": "blocked",
        "reason": "Webstore payout rebuild is deferred; current reports read stored sales and ledger values without changing payout behavior.",
    },
    {
        "id": "RB-WRAP-WORKFLOW-DEEP-DIVE",
        "name": "Wrap Lab workflow deep-dive reports",
        "status": "blocked",
        "reason": "Wrap Lab workflow rebuild is deferred; current reports read stored projects and panel plans only.",
    },
    {
        "id": "RB-PAYROLL-TAX-FILING",
        "name": "Payroll tax filing exports",
        "status": "blocked",
        "reason": "Payroll withholding and statutory deduction contracts are not implemented; payroll exports are restricted to stored gross-pay ledger data.",
    },
]


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
    _validate_filter_values(filters)
    rows = await r["run"](tenant_id=tenant_id, filters=filters or {})
    total = len(rows)
    limited = rows[:max(int(preview_limit), 0)]
    columns = _columns_with_drill_down(r["columns"], limited)
    return {
        "key": key, "title": r["title"], "category": r["category"],
        "data_source": r["data_source"], "date_basis": r["date_basis"],
        "calc_basis": r["calc_basis"], "limitations": r["limitations"],
        "columns": columns, "rows": limited, "row_count": total,
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


CUSTOM_DATASETS.update({
    "customers": {
        "perm": Perm.CUSTOMER_READ,
        "collection": "customers",
        "date_field": "created_at",
        "fields": ["number", "name", "company", "email", "phone", "status", "customer_type", "created_at"],
        "filters": ["status", "customer_type", "date_from", "date_to"],
        "group_by": ["status", "customer_type"],
        "sort": ["created_at", "name", "number"],
    },
    "quotes": {
        "perm": Perm.QUOTE_READ,
        "collection": "quotes",
        "date_field": "created_at",
        "fields": ["number", "customer_id", "job_name", "status", "subtotal_cents", "tax_cents", "total_cents", "created_at", "expires_at"],
        "filters": ["status", "customer_id", "date_from", "date_to"],
        "group_by": ["status", "customer_id"],
        "sort": ["created_at", "total_cents", "number"],
    },
    "orders": {
        "perm": Perm.ORDER_READ,
        "collection": "orders",
        "date_field": "created_at",
        "fields": ["number", "customer_id", "title", "job_name", "status", "subtotal_cents", "tax_cents", "total_cents", "due_date", "created_at"],
        "filters": ["status", "customer_id", "date_from", "date_to"],
        "group_by": ["status", "customer_id"],
        "sort": ["created_at", "due_date", "total_cents", "number"],
    },
    "order_items": {
        "perm": Perm.ORDER_READ,
        "collection": "order_items",
        "date_field": "created_at",
        "fields": ["order_id", "name", "description", "category", "quantity", "unit_price_cents", "line_total_cents", "estimated_cost_cents", "estimated_profit_cents", "created_at"],
        "filters": ["order_id", "category", "date_from", "date_to"],
        "group_by": ["order_id", "category"],
        "sort": ["created_at", "line_total_cents", "name"],
    },
    "payments": {
        "perm": Perm.FINANCE_READ,
        "collection": "payments",
        "date_field": "confirmed_at",
        "fields": ["number", "status", "method", "source", "amount_cents", "invoice_id", "customer_id", "confirmed_at", "created_at"],
        "filters": ["status", "method", "source", "customer_id", "date_from", "date_to"],
        "group_by": ["status", "method", "source", "customer_id"],
        "sort": ["confirmed_at", "amount_cents", "number"],
    },
    "work_orders": {
        "perm": Perm.WORK_ORDER_READ,
        "collection": "work_orders",
        "date_field": "created_at",
        "fields": ["number", "order_id", "customer_id", "status", "priority", "due_date", "created_at"],
        "filters": ["status", "priority", "customer_id", "date_from", "date_to"],
        "group_by": ["status", "priority", "customer_id"],
        "sort": ["created_at", "due_date", "number"],
    },
    "webstores": {
        "perm": Perm.WEBSTORE_READ,
        "collection": "webstores",
        "date_field": "created_at",
        "fields": ["name", "slug", "store_type", "status", "visibility", "created_at"],
        "filters": ["store_type", "status", "visibility", "date_from", "date_to"],
        "group_by": ["store_type", "status", "visibility"],
        "sort": ["created_at", "name"],
    },
    "webstore_buyer_orders": {
        "perm": Perm.WEBSTORE_READ,
        "collection": "webstore_buyer_orders",
        "date_field": "created_at",
        "fields": ["webstore_id", "buyer_email", "status", "subtotal_cents", "tax_cents", "shipping_cents", "donation_cents", "total_cents", "created_at"],
        "filters": ["webstore_id", "status", "date_from", "date_to"],
        "group_by": ["webstore_id", "status"],
        "sort": ["created_at", "total_cents"],
    },
    "webstore_products": {
        "perm": Perm.WEBSTORE_READ,
        "collection": "webstore_products",
        "date_field": "created_at",
        "fields": ["webstore_id", "name", "sku", "status", "price_cents", "production_cost_cents", "created_at"],
        "filters": ["webstore_id", "status", "date_from", "date_to"],
        "group_by": ["webstore_id", "status"],
        "sort": ["created_at", "name", "price_cents"],
    },
    "webstore_ledger_entries": {
        "perm": Perm.WEBSTORE_READ,
        "collection": "webstore_ledger_entries",
        "date_field": "created_at",
        "fields": ["webstore_id", "entry_type", "amount_cents", "status", "created_at"],
        "filters": ["webstore_id", "entry_type", "status", "date_from", "date_to"],
        "group_by": ["webstore_id", "entry_type", "status"],
        "sort": ["created_at", "amount_cents"],
    },
    "inventory_items": {
        "perm": Perm.INVENTORY_READ,
        "collection": "inventory_items",
        "date_field": "created_at",
        "fields": ["material_id", "location_id", "quantity_on_hand", "quantity_reserved", "last_received_at", "created_at"],
        "filters": ["material_id", "location_id", "date_from", "date_to"],
        "group_by": ["material_id", "location_id"],
        "sort": ["created_at", "quantity_on_hand"],
    },
    "materials": {
        "perm": Perm.INVENTORY_READ,
        "collection": "materials",
        "date_field": "created_at",
        "fields": ["sku", "name", "category", "status", "current_cost_cents", "cost_unit", "created_at"],
        "filters": ["category", "status", "date_from", "date_to"],
        "group_by": ["category", "status"],
        "sort": ["created_at", "name", "sku"],
    },
    "purchase_order_lines": {
        "perm": Perm.PURCHASING_READ,
        "collection": "purchase_order_lines",
        "date_field": "created_at",
        "fields": ["purchase_order_id", "material_id", "description", "quantity", "unit_cost_cents", "line_total_cents", "created_at"],
        "filters": ["purchase_order_id", "material_id", "date_from", "date_to"],
        "group_by": ["purchase_order_id", "material_id"],
        "sort": ["created_at", "line_total_cents"],
    },
    "employees": {
        "perm": Perm.EMPLOYEE_READ,
        "collection": "employees",
        "date_field": "created_at",
        "fields": ["employee_number", "name", "email", "employment_status", "department", "role", "created_at"],
        "filters": ["employment_status", "department", "role", "date_from", "date_to"],
        "group_by": ["employment_status", "department", "role"],
        "sort": ["created_at", "name", "employee_number"],
    },
    "time_entries": {
        "perm": Perm.TIMECLOCK_MANAGE,
        "collection": "time_entries",
        "date_field": "work_date",
        "fields": ["employee_id", "work_date", "status", "worked_minutes", "regular_minutes", "overtime_minutes", "created_at"],
        "filters": ["employee_id", "status", "date_from", "date_to"],
        "group_by": ["employee_id", "status"],
        "sort": ["work_date", "worked_minutes"],
    },
    "timesheets": {
        "perm": Perm.TIMESHEET_READ,
        "collection": "timesheets",
        "date_field": "period_start",
        "fields": ["employee_id", "period_start", "period_end", "status", "regular_minutes", "overtime_minutes", "created_at"],
        "filters": ["employee_id", "status", "date_from", "date_to"],
        "group_by": ["employee_id", "status"],
        "sort": ["period_start", "employee_id"],
    },
    "payroll_snapshots": {
        "perm": Perm.PAYROLL_READ,
        "collection": "payroll_snapshots",
        "date_field": "period_start",
        "fields": ["employee_id", "period_start", "period_end", "status", "gross_regular_cents", "gross_overtime_cents", "total_earned_cents", "remaining_balance_cents"],
        "filters": ["employee_id", "status", "date_from", "date_to"],
        "group_by": ["employee_id", "status"],
        "sort": ["period_start", "total_earned_cents"],
    },
    "wrap_projects": {
        "perm": Perm.WRAP_LAB_READ,
        "collection": "wrap_projects",
        "date_field": "created_at",
        "fields": ["project_name", "customer_id", "vehicle_id", "status", "project_type", "estimate_total_cents", "material_estimate_cents", "labor_estimate_cents", "created_at"],
        "filters": ["status", "project_type", "customer_id", "date_from", "date_to"],
        "group_by": ["status", "project_type", "customer_id"],
        "sort": ["created_at", "estimate_total_cents", "project_name"],
    },
    "wrap_panel_plans": {
        "perm": Perm.WRAP_LAB_READ,
        "collection": "wrap_panel_plans",
        "date_field": "created_at",
        "fields": ["project_id", "status", "revision", "material_usage_square_feet", "material_cost_cents", "labor_cost_cents", "created_at"],
        "filters": ["project_id", "status", "date_from", "date_to"],
        "group_by": ["project_id", "status"],
        "sort": ["created_at", "revision", "material_cost_cents"],
    },
})


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
    _validate_filter_values(filters)
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
    if group_by:
        grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
        money_fields = [f for f in fields if f.endswith("_cents")]
        for row in rows:
            key = tuple(row.get(g) for g in group_by)
            target = grouped.setdefault(
                key,
                {
                    **{g: row.get(g) for g in group_by},
                    "row_count": 0,
                    **{f: 0 for f in money_fields},
                },
            )
            target["row_count"] += 1
            for f in money_fields:
                target[f] += _money(row.get(f))
        rows = list(grouped.values())
    return {
        "dataset": dataset_key, "fields": fields, "filters": filters or {},
        "group_by": group_by or [], "sort": sort or [],
        "row_count": len(rows), "rows": rows,
        "limitations": ["approved datasets + fields only",
                        "cross-tenant reads disabled",
                        "max 25 000 rows"],
    }
