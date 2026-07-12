"""EC7 phase 7c — Canonical Finance service.

**Every metric returned by this service is explicitly labeled with a
`basis`.** Callers (dashboard, reports, exports) MUST NOT mix cash-received
totals with issued-invoice totals without preserving the label.

Basis values:
  - "issued_invoices"             : sum of Invoice.total_cents for issued (non-void) invoices
  - "confirmed_payments_received" : sum of Payment.amount_cents where status == "confirmed"
                                    (refunds subtracted separately, not silently netted)
  - "refunds"                     : sum of refund Payment records
  - "outstanding_receivables"     : sum of Invoice.balance_due_cents where unpaid/partial
  - "expenses"                    : sum of active Expense.total_cents (voided excluded)
  - "tax_collected"               : sum of Invoice.tax_cents (issued invoices, snapshot values)
  - "estimated_cost"              : available-evidence cost only; NEVER invented
  - "estimated_gross_profit"      : issued_invoice_revenue − estimated_cost (partial coverage warned)
  - "estimated_net_operating"     : issued_invoice_revenue − expenses − refunds

Guardrails:
  - Every query is tenant-scoped.
  - Date ranges are stored as ISO date strings; caller supplies timezone
    boundaries. If caller passes tz-aware ISO datetimes we retain them.
  - Aggregation uses MongoDB pipelines with `$match` first for index use.
  - Bounded top-N queries never scan without a limit.
  - Empty ranges return zeros with `empty: true` — never a crash.
  - Warnings + limitations lists explain any incomplete data.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from ..core.db import db


# ---------------------------------------------------------------------------
# Range helpers — every metric respects `date_from` + `date_to` as inclusive
# ISO date bounds. We match Invoice.issued_at, Payment.confirmed_at,
# Expense.expense_date depending on the metric's field.
# ---------------------------------------------------------------------------
def _range_iso(date_from: Optional[str], date_to: Optional[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if date_from: out["$gte"] = date_from
    if date_to: out["$lte"] = date_to + "T23:59:59.999999Z" if "T" not in date_to else date_to
    return out


def _date_range_dict(date_from: Optional[str], date_to: Optional[str]) -> dict[str, Any]:
    return {"from": date_from, "to": date_to}


def _empty_metric(basis: str, date_from: Optional[str], date_to: Optional[str],
                  timezone_name: str = "UTC", extra: Optional[dict] = None) -> dict:
    base = {
        "basis": basis, "value_cents": 0, "empty": True,
        "date_range": _date_range_dict(date_from, date_to),
        "timezone": timezone_name, "warnings": [], "limitations": [],
    }
    if extra: base.update(extra)
    return base


# ---------------------------------------------------------------------------
# Invoice-based metrics
# ---------------------------------------------------------------------------
async def invoice_revenue(*, tenant_id: str, date_from: Optional[str] = None,
                          date_to: Optional[str] = None,
                          timezone_name: str = "UTC") -> dict:
    match: dict[str, Any] = {"tenant_id": tenant_id, "document_status": "issued"}
    rng = _range_iso(date_from, date_to)
    if rng: match["issued_at"] = rng
    pipeline = [{"$match": match},
                {"$group": {"_id": None, "total": {"$sum": "$total_cents"},
                             "count": {"$sum": 1}}}]
    result = await db.invoices.aggregate(pipeline).to_list(length=1)
    if not result:
        return _empty_metric("issued_invoices", date_from, date_to, timezone_name,
                             extra={"count": 0})
    return {
        "basis": "issued_invoices",
        "value_cents": int(result[0]["total"] or 0),
        "count": int(result[0]["count"] or 0),
        "date_range": _date_range_dict(date_from, date_to),
        "timezone": timezone_name,
        "empty": False, "warnings": [], "limitations": [],
    }


async def outstanding_receivables(*, tenant_id: str,
                                  timezone_name: str = "UTC") -> dict:
    """Sum of Invoice.balance_due_cents where issued + unpaid/partial. Aging
    breakdown too."""
    match = {"tenant_id": tenant_id, "document_status": "issued",
             "financial_status": {"$in": ["unpaid", "partial"]}}
    pipeline = [{"$match": match},
                {"$group": {"_id": "$financial_status",
                             "total": {"$sum": "$balance_due_cents"},
                             "count": {"$sum": 1}}}]
    result = await db.invoices.aggregate(pipeline).to_list(length=10)
    by_status = {r["_id"]: {"count": r["count"], "total_cents": int(r["total"] or 0)}
                 for r in result}
    unpaid = by_status.get("unpaid", {"count": 0, "total_cents": 0})
    partial = by_status.get("partial", {"count": 0, "total_cents": 0})
    total_cents = unpaid["total_cents"] + partial["total_cents"]
    # Aging: use due_date when set; else fall back to issued_at
    now = datetime.now(timezone.utc)
    aging = {"current_0_30": 0, "days_31_60": 0, "days_61_90": 0, "days_91_plus": 0}
    overdue_count = 0
    async for inv in db.invoices.find(match, {"_id": 0}):
        balance = int(inv.get("balance_due_cents", 0))
        if balance <= 0:
            continue
        ref = inv.get("due_date") or inv.get("issued_at")
        if not ref:
            aging["current_0_30"] += balance
            continue
        try:
            if isinstance(ref, str):
                ref_dt = datetime.fromisoformat(ref.replace("Z", "+00:00"))
            else:
                ref_dt = ref  # datetime already
        except Exception:
            ref_dt = now
        if ref_dt.tzinfo is None:
            ref_dt = ref_dt.replace(tzinfo=timezone.utc)
        days = (now - ref_dt).days
        if days > 0:
            overdue_count += 1
        if days <= 30:
            aging["current_0_30"] += balance
        elif days <= 60:
            aging["days_31_60"] += balance
        elif days <= 90:
            aging["days_61_90"] += balance
        else:
            aging["days_91_plus"] += balance
    return {
        "basis": "outstanding_receivables",
        "value_cents": total_cents,
        "unpaid_count": unpaid["count"], "unpaid_cents": unpaid["total_cents"],
        "partial_count": partial["count"], "partial_cents": partial["total_cents"],
        "overdue_count": overdue_count,
        "aging_cents": aging,
        "timezone": timezone_name,
        "empty": total_cents == 0,
        "warnings": [], "limitations": ["aging uses due_date when set, else issued_at"],
    }


async def tax_collected(*, tenant_id: str, date_from: Optional[str] = None,
                        date_to: Optional[str] = None,
                        timezone_name: str = "UTC") -> dict:
    """Tax collected = sum of Invoice.tax_cents from issued invoices in range.
    LOCKED: uses invoice tax snapshots (never recomputes from current tax settings)."""
    match: dict[str, Any] = {"tenant_id": tenant_id, "document_status": "issued"}
    rng = _range_iso(date_from, date_to)
    if rng: match["issued_at"] = rng
    pipeline = [{"$match": match},
                {"$group": {"_id": None, "total": {"$sum": "$tax_cents"},
                             "count": {"$sum": 1}}}]
    result = await db.invoices.aggregate(pipeline).to_list(length=1)
    if not result:
        return _empty_metric("tax_collected", date_from, date_to, timezone_name,
                             extra={"count": 0, "note": "invoice tax snapshots only"})
    return {
        "basis": "tax_collected",
        "value_cents": int(result[0]["total"] or 0),
        "count": int(result[0]["count"] or 0),
        "date_range": _date_range_dict(date_from, date_to),
        "timezone": timezone_name,
        "empty": False, "warnings": [],
        "limitations": ["values come from Invoice.tax_cents snapshots — historical tax rates preserved"],
    }


# ---------------------------------------------------------------------------
# Payment-based metrics (CASH basis)
# ---------------------------------------------------------------------------
async def payments_received(*, tenant_id: str, date_from: Optional[str] = None,
                            date_to: Optional[str] = None,
                            timezone_name: str = "UTC") -> dict:
    """Sum of confirmed Payment.amount_cents in range. Excludes refund records."""
    match: dict[str, Any] = {"tenant_id": tenant_id, "status": "confirmed",
                             "refund_of_payment_id": None}
    rng = _range_iso(date_from, date_to)
    if rng: match["confirmed_at"] = rng
    pipeline = [{"$match": match},
                {"$group": {"_id": None, "total": {"$sum": "$amount_cents"},
                             "count": {"$sum": 1}}}]
    result = await db.payments.aggregate(pipeline).to_list(length=1)
    value = int(result[0]["total"]) if result else 0
    count = int(result[0]["count"]) if result else 0
    return {
        "basis": "confirmed_payments_received",
        "value_cents": value, "count": count,
        "date_range": _date_range_dict(date_from, date_to),
        "timezone": timezone_name,
        "empty": value == 0 and count == 0,
        "warnings": [], "limitations": [],
    }


async def refunds(*, tenant_id: str, date_from: Optional[str] = None,
                  date_to: Optional[str] = None,
                  timezone_name: str = "UTC") -> dict:
    match: dict[str, Any] = {"tenant_id": tenant_id,
                             "refund_of_payment_id": {"$ne": None}}
    rng = _range_iso(date_from, date_to)
    if rng: match["refunded_at"] = rng
    pipeline = [{"$match": match},
                {"$group": {"_id": None, "total": {"$sum": "$amount_cents"},
                             "count": {"$sum": 1}}}]
    result = await db.payments.aggregate(pipeline).to_list(length=1)
    value = int(result[0]["total"]) if result else 0
    count = int(result[0]["count"]) if result else 0
    return {
        "basis": "refunds", "value_cents": value, "count": count,
        "date_range": _date_range_dict(date_from, date_to),
        "timezone": timezone_name, "empty": value == 0,
        "warnings": [], "limitations": [],
    }


async def payment_method_breakdown(*, tenant_id: str,
                                   date_from: Optional[str] = None,
                                   date_to: Optional[str] = None,
                                   timezone_name: str = "UTC") -> dict:
    match: dict[str, Any] = {"tenant_id": tenant_id, "status": "confirmed",
                             "refund_of_payment_id": None}
    rng = _range_iso(date_from, date_to)
    if rng: match["confirmed_at"] = rng
    pipeline = [{"$match": match},
                {"$group": {"_id": {"source": "$source", "method": "$method"},
                             "total": {"$sum": "$amount_cents"},
                             "count": {"$sum": 1}}}]
    result = await db.payments.aggregate(pipeline).to_list(length=64)
    items = [
        {"source": r["_id"].get("source"), "method": r["_id"].get("method"),
         "value_cents": int(r["total"] or 0), "count": int(r["count"] or 0)}
        for r in result
    ]
    return {"basis": "confirmed_payments_received", "items": items,
            "timezone": timezone_name,
            "date_range": _date_range_dict(date_from, date_to),
            "warnings": [], "limitations": []}


async def top_customers_by_revenue(*, tenant_id: str, limit: int = 10,
                                   date_from: Optional[str] = None,
                                   date_to: Optional[str] = None,
                                   timezone_name: str = "UTC") -> dict:
    match: dict[str, Any] = {"tenant_id": tenant_id, "document_status": "issued"}
    rng = _range_iso(date_from, date_to)
    if rng: match["issued_at"] = rng
    pipeline = [
        {"$match": match},
        {"$group": {"_id": "$customer_id",
                     "revenue_cents": {"$sum": "$total_cents"},
                     "invoice_count": {"$sum": 1}}},
        {"$sort": {"revenue_cents": -1}},
        {"$limit": max(int(limit), 1)},
    ]
    result = await db.invoices.aggregate(pipeline).to_list(length=limit)
    items: list[dict[str, Any]] = []
    for r in result:
        cid = r["_id"]
        cust = await db.customers.find_one({"tenant_id": tenant_id, "id": cid},
                                            {"_id": 0, "name": 1, "company": 1})
        items.append({
            "customer_id": cid,
            "customer_name": (cust or {}).get("name"),
            "customer_company": (cust or {}).get("company"),
            "revenue_cents": int(r["revenue_cents"] or 0),
            "invoice_count": int(r["invoice_count"] or 0),
        })
    return {"basis": "issued_invoices", "items": items,
            "timezone": timezone_name,
            "date_range": _date_range_dict(date_from, date_to)}


# ---------------------------------------------------------------------------
# Expense-based metrics
# ---------------------------------------------------------------------------
async def expenses_total(*, tenant_id: str, date_from: Optional[str] = None,
                         date_to: Optional[str] = None,
                         timezone_name: str = "UTC",
                         category_key: Optional[str] = None) -> dict:
    match: dict[str, Any] = {"tenant_id": tenant_id, "state": "active"}
    date_filter: dict[str, Any] = {}
    if date_from: date_filter["$gte"] = date_from
    if date_to: date_filter["$lte"] = date_to
    if date_filter: match["expense_date"] = date_filter
    if category_key: match["category_key"] = category_key
    pipeline = [{"$match": match},
                {"$group": {"_id": None, "total": {"$sum": "$total_cents"},
                             "count": {"$sum": 1}}}]
    result = await db.expenses.aggregate(pipeline).to_list(length=1)
    value = int(result[0]["total"]) if result else 0
    count = int(result[0]["count"]) if result else 0
    return {
        "basis": "expenses", "value_cents": value, "count": count,
        "date_range": _date_range_dict(date_from, date_to),
        "timezone": timezone_name, "empty": value == 0,
        "category_key": category_key,
        "warnings": [], "limitations": ["voided + archived Expenses excluded"],
    }


async def expenses_by_category(*, tenant_id: str, date_from: Optional[str] = None,
                               date_to: Optional[str] = None,
                               timezone_name: str = "UTC") -> dict:
    match: dict[str, Any] = {"tenant_id": tenant_id, "state": "active"}
    date_filter: dict[str, Any] = {}
    if date_from: date_filter["$gte"] = date_from
    if date_to: date_filter["$lte"] = date_to
    if date_filter: match["expense_date"] = date_filter
    pipeline = [{"$match": match},
                {"$group": {"_id": "$category_key",
                             "total": {"$sum": "$total_cents"},
                             "count": {"$sum": 1}}},
                {"$sort": {"total": -1}}]
    result = await db.expenses.aggregate(pipeline).to_list(length=64)
    items = [{"category_key": r["_id"],
              "value_cents": int(r["total"] or 0),
              "count": int(r["count"] or 0)} for r in result]
    return {"basis": "expenses", "items": items,
            "date_range": _date_range_dict(date_from, date_to),
            "timezone": timezone_name}


# ---------------------------------------------------------------------------
# Trends — monthly buckets for a supplied date range (max 24 months per call)
# ---------------------------------------------------------------------------
def _month_buckets(date_from: str, date_to: str) -> list[str]:
    df = datetime.fromisoformat(date_from[:10])
    dt = datetime.fromisoformat(date_to[:10])
    out: list[str] = []
    cur = df.replace(day=1)
    limit_end = dt.replace(day=1)
    for _ in range(24):
        out.append(cur.strftime("%Y-%m"))
        if cur >= limit_end:
            break
        # advance one month
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)
    return out


async def _monthly_trend(*, tenant_id: str, collection: str, date_field: str,
                         amount_field: str, extra_match: dict, date_from: str,
                         date_to: str, timezone_name: str, basis: str) -> dict:
    buckets = _month_buckets(date_from, date_to)
    empty_map = {b: {"value_cents": 0, "count": 0} for b in buckets}
    match: dict[str, Any] = {"tenant_id": tenant_id, **extra_match}
    rng = _range_iso(date_from, date_to)
    if rng: match[date_field] = rng
    pipeline = [
        {"$match": match},
        {"$addFields": {"__yearmonth": {"$substr": [f"${date_field}", 0, 7]}}},
        {"$group": {"_id": "$__yearmonth",
                     "total": {"$sum": f"${amount_field}"},
                     "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    result = await db[collection].aggregate(pipeline).to_list(length=24)
    for r in result:
        if r["_id"] in empty_map:
            empty_map[r["_id"]] = {"value_cents": int(r["total"] or 0),
                                    "count": int(r["count"] or 0)}
    series = [{"period": p, **empty_map[p]} for p in buckets]
    return {"basis": basis, "series": series, "granularity": "month",
            "date_range": _date_range_dict(date_from, date_to),
            "timezone": timezone_name, "warnings": [], "limitations": []}


async def revenue_trend(*, tenant_id: str, date_from: str, date_to: str,
                        timezone_name: str = "UTC") -> dict:
    return await _monthly_trend(
        tenant_id=tenant_id, collection="invoices",
        date_field="issued_at", amount_field="total_cents",
        extra_match={"document_status": "issued"},
        date_from=date_from, date_to=date_to,
        timezone_name=timezone_name, basis="issued_invoices",
    )


async def payments_received_trend(*, tenant_id: str, date_from: str, date_to: str,
                                  timezone_name: str = "UTC") -> dict:
    return await _monthly_trend(
        tenant_id=tenant_id, collection="payments",
        date_field="confirmed_at", amount_field="amount_cents",
        extra_match={"status": "confirmed", "refund_of_payment_id": None},
        date_from=date_from, date_to=date_to,
        timezone_name=timezone_name, basis="confirmed_payments_received",
    )


async def expense_trend(*, tenant_id: str, date_from: str, date_to: str,
                        timezone_name: str = "UTC") -> dict:
    return await _monthly_trend(
        tenant_id=tenant_id, collection="expenses",
        date_field="expense_date", amount_field="total_cents",
        extra_match={"state": "active"},
        date_from=date_from, date_to=date_to,
        timezone_name=timezone_name, basis="expenses",
    )


# ---------------------------------------------------------------------------
# Averages
# ---------------------------------------------------------------------------
async def average_order_value(*, tenant_id: str, date_from: Optional[str] = None,
                              date_to: Optional[str] = None,
                              timezone_name: str = "UTC") -> dict:
    match: dict[str, Any] = {"tenant_id": tenant_id}
    # Orders use created_at as their reference date (Orders don't have issued_at).
    rng = _range_iso(date_from, date_to)
    if rng: match["created_at"] = rng
    pipeline = [{"$match": match},
                {"$group": {"_id": None, "total": {"$sum": "$total_cents"},
                             "count": {"$sum": 1}}}]
    result = await db.orders.aggregate(pipeline).to_list(length=1)
    if not result or not result[0]["count"]:
        return _empty_metric("issued_invoices", date_from, date_to, timezone_name,
                             extra={"average_cents": 0, "count": 0,
                                    "note": "no orders in range"})
    total = int(result[0]["total"] or 0)
    count = int(result[0]["count"] or 0)
    return {"basis": "issued_invoices", "average_cents": int(total / count),
            "total_cents": total, "count": count,
            "date_range": _date_range_dict(date_from, date_to),
            "timezone": timezone_name, "warnings": [], "limitations": []}


async def average_invoice_value(*, tenant_id: str, date_from: Optional[str] = None,
                                date_to: Optional[str] = None,
                                timezone_name: str = "UTC") -> dict:
    match: dict[str, Any] = {"tenant_id": tenant_id, "document_status": "issued"}
    rng = _range_iso(date_from, date_to)
    if rng: match["issued_at"] = rng
    pipeline = [{"$match": match},
                {"$group": {"_id": None, "total": {"$sum": "$total_cents"},
                             "count": {"$sum": 1}}}]
    result = await db.invoices.aggregate(pipeline).to_list(length=1)
    if not result or not result[0]["count"]:
        return _empty_metric("issued_invoices", date_from, date_to, timezone_name,
                             extra={"average_cents": 0, "count": 0})
    total = int(result[0]["total"] or 0)
    count = int(result[0]["count"] or 0)
    return {"basis": "issued_invoices", "average_cents": int(total / count),
            "total_cents": total, "count": count,
            "date_range": _date_range_dict(date_from, date_to),
            "timezone": timezone_name, "warnings": [], "limitations": []}


# ---------------------------------------------------------------------------
# Estimated profit — best-effort, NEVER invents missing cost.
# ---------------------------------------------------------------------------
async def estimated_gross_profit(*, tenant_id: str, date_from: Optional[str] = None,
                                 date_to: Optional[str] = None,
                                 timezone_name: str = "UTC") -> dict:
    """Revenue (issued invoices) − sum of available cost inputs.

    LOCKED per master plan §12E / Appendix A.3:
      - We only use cost inputs that ACTUALLY EXIST on the record.
      - Missing costs are counted and surfaced as `coverage` + `warnings`.
      - We never invent a fallback cost; the returned profit is explicitly
        labeled "partial_coverage" when any orders/items lack cost data.
      - Historical Quote/Order/Invoice prices are NEVER recomputed here.
    """
    # 1) Revenue from issued invoices in range
    rev = await invoice_revenue(tenant_id=tenant_id, date_from=date_from,
                                 date_to=date_to, timezone_name=timezone_name)
    # 2) Cost estimate — from Order.total_cost_snapshot_cents (if set) plus
    #    receiving-cost of Materials, plus linked Expenses on those Orders.
    match_inv: dict[str, Any] = {"tenant_id": tenant_id, "document_status": "issued"}
    rng = _range_iso(date_from, date_to)
    if rng: match_inv["issued_at"] = rng
    order_ids: list[str] = []
    async for inv in db.invoices.find(match_inv, {"_id": 0, "order_id": 1}):
        if inv.get("order_id"):
            order_ids.append(inv["order_id"])
    if not order_ids:
        cost_cents = 0
        coverage = {"orders_with_cost": 0, "orders_missing_cost": 0}
    else:
        cost_cents = 0
        with_cost = 0
        missing = 0
        found_ids: set[str] = set()
        async for o in db.orders.find(
            {"tenant_id": tenant_id, "id": {"$in": order_ids}},
            {"_id": 0, "id": 1, "cost_snapshot_cents": 1, "material_cost_snapshot_cents": 1},
        ):
            found_ids.add(o["id"])
            c = o.get("cost_snapshot_cents") or o.get("material_cost_snapshot_cents")
            if c is not None:
                cost_cents += int(c or 0)
                with_cost += 1
            else:
                missing += 1
        # Orders referenced by invoices but not present in the orders collection
        # (or missing entirely) count as missing cost too.
        missing += sum(1 for oid in order_ids if oid not in found_ids)
        # Linked Expenses attached to these Orders (state=active)
        exp_pipeline = [
            {"$match": {"tenant_id": tenant_id, "state": "active",
                        "order_id": {"$in": order_ids}}},
            {"$group": {"_id": None, "total": {"$sum": "$total_cents"}}},
        ]
        exp_res = await db.expenses.aggregate(exp_pipeline).to_list(length=1)
        cost_cents += int((exp_res[0]["total"] if exp_res else 0) or 0)
        coverage = {"orders_with_cost": with_cost, "orders_missing_cost": missing,
                    "linked_expenses_included": True}
    revenue_cents = rev["value_cents"]
    profit_cents = revenue_cents - cost_cents
    warnings: list[str] = []
    limitations = [
        "cost inputs use available evidence only (Order cost snapshot + linked active Expenses)",
        "orders missing cost snapshot are counted but not silently zeroed",
        "historical Quote/Order/Invoice pricing is never recomputed",
        "not audited accounting output — see EC3.1 for full pricing verification",
    ]
    if coverage.get("orders_missing_cost", 0) > 0:
        warnings.append("partial_cost_coverage: some orders lack cost snapshot; profit is a lower-bound estimate")
        coverage_label = "partial_coverage"
    else:
        coverage_label = "full_available_evidence"
    return {
        "basis": "estimated_gross_profit",
        "value_cents": profit_cents,
        "revenue_cents": revenue_cents,
        "cost_cents": cost_cents,
        "coverage": coverage, "coverage_label": coverage_label,
        "date_range": _date_range_dict(date_from, date_to),
        "timezone": timezone_name,
        "warnings": warnings, "limitations": limitations,
    }


async def estimated_net_operating(*, tenant_id: str, date_from: Optional[str] = None,
                                  date_to: Optional[str] = None,
                                  timezone_name: str = "UTC") -> dict:
    """Rough operating result = issued_invoice_revenue − active_expenses − refunds.
    Labels remain explicit; no accrual/cash mixing."""
    rev = await invoice_revenue(tenant_id=tenant_id, date_from=date_from,
                                 date_to=date_to, timezone_name=timezone_name)
    exp = await expenses_total(tenant_id=tenant_id, date_from=date_from,
                                date_to=date_to, timezone_name=timezone_name)
    rf = await refunds(tenant_id=tenant_id, date_from=date_from,
                        date_to=date_to, timezone_name=timezone_name)
    net = rev["value_cents"] - exp["value_cents"] - rf["value_cents"]
    return {
        "basis": "estimated_net_operating",
        "value_cents": net,
        "revenue_cents": rev["value_cents"],
        "expenses_cents": exp["value_cents"],
        "refunds_cents": rf["value_cents"],
        "date_range": _date_range_dict(date_from, date_to),
        "timezone": timezone_name,
        "warnings": [],
        "limitations": [
            "combines Invoice-basis revenue with Expense-basis costs (labels preserved per-line)",
            "not audited accounting output",
        ],
    }


# ---------------------------------------------------------------------------
# Composite summary
# ---------------------------------------------------------------------------
async def dashboard_summary(*, tenant_id: str, date_from: Optional[str] = None,
                            date_to: Optional[str] = None,
                            timezone_name: str = "UTC") -> dict:
    revenue = await invoice_revenue(tenant_id=tenant_id, date_from=date_from,
                                    date_to=date_to, timezone_name=timezone_name)
    payments = await payments_received(tenant_id=tenant_id, date_from=date_from,
                                        date_to=date_to, timezone_name=timezone_name)
    rfd = await refunds(tenant_id=tenant_id, date_from=date_from,
                        date_to=date_to, timezone_name=timezone_name)
    outstanding = await outstanding_receivables(tenant_id=tenant_id,
                                                 timezone_name=timezone_name)
    expenses = await expenses_total(tenant_id=tenant_id, date_from=date_from,
                                     date_to=date_to, timezone_name=timezone_name)
    tax = await tax_collected(tenant_id=tenant_id, date_from=date_from,
                              date_to=date_to, timezone_name=timezone_name)
    aov = await average_order_value(tenant_id=tenant_id, date_from=date_from,
                                     date_to=date_to, timezone_name=timezone_name)
    aiv = await average_invoice_value(tenant_id=tenant_id, date_from=date_from,
                                       date_to=date_to, timezone_name=timezone_name)
    top = await top_customers_by_revenue(tenant_id=tenant_id, limit=5,
                                          date_from=date_from, date_to=date_to,
                                          timezone_name=timezone_name)
    breakdown = await payment_method_breakdown(tenant_id=tenant_id,
                                                date_from=date_from, date_to=date_to,
                                                timezone_name=timezone_name)
    gp = await estimated_gross_profit(tenant_id=tenant_id, date_from=date_from,
                                       date_to=date_to, timezone_name=timezone_name)
    net = await estimated_net_operating(tenant_id=tenant_id, date_from=date_from,
                                         date_to=date_to, timezone_name=timezone_name)
    return {
        "date_range": _date_range_dict(date_from, date_to),
        "timezone": timezone_name,
        "revenue_issued_invoices": revenue,
        "payments_received": payments,
        "refunds": rfd,
        "outstanding_receivables": outstanding,
        "expenses": expenses,
        "tax_collected": tax,
        "average_order_value": aov,
        "average_invoice_value": aiv,
        "top_customers": top,
        "payment_method_breakdown": breakdown,
        "estimated_gross_profit": gp,
        "estimated_net_operating": net,
        "warnings": [w for src in (revenue, payments, rfd, outstanding, expenses, tax, gp, net)
                     for w in src.get("warnings", [])],
        "limitations": [
            "Invoice-basis and Payment-basis metrics are shown side by side — labels are authoritative",
            "estimated profit uses only available cost evidence",
            "not audited accounting output — see EC3.1 for full pricing verification",
        ],
    }
