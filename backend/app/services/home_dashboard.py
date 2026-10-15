"""F2 — Customizable Home dashboard.

The backend owns the widget registry, the per-widget permission check and
the widget data, so the browser never receives data the user may not see.

Each widget belongs to one data *family* (for example "unpaid_invoices").
A family may offer several presentations — compact KPI, standard summary,
list — but only one per family can be visible at a time, so Home never
shows the same metric twice in slightly different forms.

Data comes from existing records and services; nothing is estimated or
fabricated. A widget whose source fails reports `unavailable` instead of
breaking the page.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Optional

from ..core.db import db
from ..core.permissions import Perm, permissions_for_role
from ..core.time_utils import serialize_doc
from ..models.work_order import effective_status
from ..repositories.dashboard_preferences import dashboard_preferences
from . import calendar_service, employee_service, timesheet_service

logger = logging.getLogger(__name__)

LAYOUT_VERSION = 1
LIST_LIMIT = 25

# Shared definitions so Home agrees with the module screens.
ACTIVE_ORDER_STATUSES = ("confirmed", "in_production", "ready")  # same as Shop Operations analytics
AWAITING_QUOTE_STATUSES = ("sent", "viewed")
# Canonical EC4 dual status: issued documents whose financial status is open
# and whose actual balance due is positive. Rows written before EC4 carry no
# financial_status and fall back to the legacy single status.
OPEN_FINANCIAL_STATUSES = ("unpaid", "partial")
LEGACY_UNPAID_INVOICE_STATUSES = ("sent", "viewed", "partially_paid", "overdue")
ACTIVE_PRODUCTION_STATUSES = ("released", "queued", "in_progress", "blocked", "ready")
RAW_ACTIVE_PRODUCTION_STATUSES = (*ACTIVE_PRODUCTION_STATUSES, "not_started", "on_hold")  # legacy values mapped on read
CLOSED_EVENT_STATUSES = {"complete", "completed", "cancelled", "canceled"}

# Registry order is the default reading order.
WIDGETS: list[dict[str, Any]] = [
    {"key": "active_orders_kpi", "family": "active_orders", "kind": "kpi", "title": "Active orders", "perm": Perm.ORDER_READ, "to": "/orders", "default": True},
    {"key": "unpaid_invoices_kpi", "family": "unpaid_invoices", "kind": "kpi", "title": "Unpaid invoices", "perm": Perm.INVOICE_READ, "to": "/invoices", "default": True},
    {"key": "quotes_awaiting_kpi", "family": "quotes_awaiting", "kind": "kpi", "title": "Quotes awaiting decision", "perm": Perm.QUOTE_READ, "to": "/quotes", "default": False},
    {"key": "production_kpi", "family": "production", "kind": "kpi", "title": "Active work orders", "perm": Perm.WORK_ORDER_READ, "to": "/work-orders", "default": False},
    {"key": "timesheets_pending_kpi", "family": "timesheets_pending", "kind": "kpi", "title": "Timesheets to review", "perm": Perm.TIMESHEET_READ, "to": "/team/timesheets", "default": True},
    {"key": "active_team_kpi", "family": "active_team", "kind": "kpi", "title": "Active team members", "perm": Perm.EMPLOYEE_READ, "to": "/team/employees", "default": True},
    {"key": "production_status", "family": "production", "kind": "summary", "title": "Production status", "perm": Perm.WORK_ORDER_READ, "to": "/work-orders/board", "default": True},
    {"key": "orders_by_status", "family": "active_orders", "kind": "summary", "title": "Active orders by status", "perm": Perm.ORDER_READ, "to": "/orders", "default": False},
    {"key": "quote_pipeline", "family": "quotes_awaiting", "kind": "summary", "title": "Quotes awaiting decision", "perm": Perm.QUOTE_READ, "to": "/quotes", "default": False},
    {"key": "invoice_aging", "family": "unpaid_invoices", "kind": "summary", "title": "Invoice due dates", "perm": Perm.INVOICE_READ, "to": "/invoices", "default": False},
    {"key": "quotes_awaiting_list", "family": "quotes_awaiting", "kind": "list", "title": "Quotes awaiting decision", "perm": Perm.QUOTE_READ, "to": "/quotes", "default": True},
    {"key": "todays_schedule", "family": "todays_schedule", "kind": "list", "title": "Today's schedule", "perm": Perm.SCHEDULE_READ, "to": "/shop-schedule", "default": True},
    {"key": "active_orders_list", "family": "active_orders", "kind": "list", "title": "Active orders", "perm": Perm.ORDER_READ, "to": "/orders", "default": False},
    {"key": "production_list", "family": "production", "kind": "list", "title": "Active work orders", "perm": Perm.WORK_ORDER_READ, "to": "/work-orders", "default": False},
    {"key": "unpaid_invoices_list", "family": "unpaid_invoices", "kind": "list", "title": "Unpaid invoices", "perm": Perm.INVOICE_READ, "to": "/invoices", "default": False},
    {"key": "recent_customers", "family": "recent_customers", "kind": "list", "title": "Recent customers", "perm": Perm.CUSTOMER_READ, "to": "/customers", "default": True},
    {"key": "recent_activity", "family": "recent_activity", "kind": "list", "title": "Recent activity", "perm": Perm.AUDIT_READ, "to": None, "default": True},
    {"key": "recent_emails", "family": "recent_emails", "kind": "list", "title": "Recent emails", "perm": Perm.EMAIL_READ, "to": "/email-history", "default": False},
]
WIDGET_BY_KEY = {w["key"]: w for w in WIDGETS}


class HomeDashboardError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _allowed(user: dict, widget: dict) -> bool:
    return widget["perm"].value in set(permissions_for_role(user.get("role", "staff")))


def default_layout() -> dict[str, Any]:
    return {
        "version": LAYOUT_VERSION,
        "order": [w["key"] for w in WIDGETS],
        "hidden": [w["key"] for w in WIDGETS if not w["default"]],
        "collapsed": [],
    }


def sanitize_layout(value: Any) -> dict[str, Any]:
    """Drop unknown keys, append new widgets, and keep one visible widget per family.

    When two presentations of the same family are visible, the one earlier in
    the reading order wins and the other is hidden.
    """
    candidate = value if isinstance(value, dict) else {}
    defaults = default_layout()
    order: list[str] = []
    for key in candidate.get("order") or []:
        if isinstance(key, str) and key in WIDGET_BY_KEY and key not in order:
            order.append(key)
    for key in defaults["order"]:
        if key not in order:
            order.append(key)
    hidden_input = candidate.get("hidden")
    hidden = {k for k in (hidden_input if isinstance(hidden_input, list) else defaults["hidden"]) if k in WIDGET_BY_KEY}
    if isinstance(hidden_input, list):
        # Widgets introduced after the layout was saved start in their default state.
        known = set(candidate.get("order") or [])
        hidden |= {k for k in defaults["hidden"] if k not in known}
    families_shown: set[str] = set()
    for key in order:
        if key in hidden:
            continue
        family = WIDGET_BY_KEY[key]["family"]
        if family in families_shown:
            hidden.add(key)
        else:
            families_shown.add(family)
    collapsed = [k for k in dict.fromkeys(candidate.get("collapsed") or []) if k in WIDGET_BY_KEY and WIDGET_BY_KEY[k]["kind"] == "list"]
    return {"version": LAYOUT_VERSION, "order": order, "hidden": [k for k in order if k in hidden], "collapsed": collapsed}


async def get_layout(user: dict) -> dict[str, Any]:
    saved = await dashboard_preferences.get(tenant_id=user["tenant_id"], user_id=user["id"])
    return sanitize_layout(saved) if saved else default_layout()


async def save_layout(user: dict, layout: dict[str, Any]) -> dict[str, Any]:
    clean = sanitize_layout(layout)
    await dashboard_preferences.save(tenant_id=user["tenant_id"], user_id=user["id"], layout=clean)
    return clean


async def reset_layout(user: dict) -> dict[str, Any]:
    await dashboard_preferences.delete(tenant_id=user["tenant_id"], user_id=user["id"])
    return default_layout()


# ---- widget data -------------------------------------------------------------


async def _find(collection: str, filt: dict, *, sort: str, fields: dict, limit: int = LIST_LIMIT) -> list[dict]:
    cursor = db[collection].find(filt, {"_id": 0, **fields}).sort(sort, -1).limit(limit)
    return [serialize_doc(doc) async for doc in cursor]


def _not_archived(tenant_id: str) -> dict:
    return {"tenant_id": tenant_id, "archived_at": None}


async def _active_orders(tenant_id: str, kind: str, _ctx: dict) -> dict:
    filt = {**_not_archived(tenant_id), "status": {"$in": list(ACTIVE_ORDER_STATUSES)}}
    if kind == "kpi":
        return {"value": await db.orders.count_documents(filt)}
    if kind == "summary":
        rows = [{"label": s.replace("_", " ").capitalize(), "value": await db.orders.count_documents({**_not_archived(tenant_id), "status": s}), "to": f"/orders?status={s}"}
                for s in ACTIVE_ORDER_STATUSES]
        return {"rows": rows, "total": sum(r["value"] for r in rows)}
    items = await _find("orders", filt, sort="number", fields={"id": 1, "number": 1, "job_name": 1, "title": 1, "status": 1, "total_cents": 1})
    return {"total": await db.orders.count_documents(filt), "items": [
        {"id": o["id"], "ref": f"O-{o.get('number')}", "title": o.get("title") or o.get("job_name"), "status": o.get("status"),
         "status_kind": "order", "amount_cents": o.get("total_cents"), "to": f"/orders/{o['id']}"} for o in items]}


async def _quotes_awaiting(tenant_id: str, kind: str, _ctx: dict) -> dict:
    filt = {**_not_archived(tenant_id), "status": {"$in": list(AWAITING_QUOTE_STATUSES)}}
    if kind == "kpi":
        return {"value": await db.quotes.count_documents(filt)}
    if kind == "summary":
        rows = []
        for s in AWAITING_QUOTE_STATUSES:
            docs = [d async for d in db.quotes.find({**_not_archived(tenant_id), "status": s}, {"_id": 0, "total_cents": 1})]
            rows.append({"label": "Sent" if s == "sent" else "Viewed by customer", "value": len(docs),
                         "amount_cents": sum(int(d.get("total_cents") or 0) for d in docs), "to": f"/quotes?status={s}"})
        return {"rows": rows, "total": sum(r["value"] for r in rows), "amount_cents": sum(r["amount_cents"] for r in rows)}
    items = await _find("quotes", filt, sort="number", fields={"id": 1, "number": 1, "job_name": 1, "status": 1, "total_cents": 1, "created_at": 1})
    return {"total": await db.quotes.count_documents(filt), "items": [
        {"id": q["id"], "ref": f"Q-{q.get('number')}", "title": q.get("job_name"), "status": q.get("status"), "status_kind": "quote",
         "amount_cents": q.get("total_cents"), "when": q.get("created_at"), "to": f"/quotes/{q['id']}"} for q in items]}


def _unpaid_invoice_filter(tenant_id: str) -> dict:
    return {"tenant_id": tenant_id, "balance_due_cents": {"$gt": 0}, "$or": [
        {"document_status": "issued", "financial_status": {"$in": list(OPEN_FINANCIAL_STATUSES)}},
        {"financial_status": {"$exists": False}, "status": {"$in": list(LEGACY_UNPAID_INVOICE_STATUSES)}},
    ]}


async def _unpaid_invoices(tenant_id: str, kind: str, ctx: dict) -> dict:
    filt = _unpaid_invoice_filter(tenant_id)
    if kind == "kpi":
        docs = [d async for d in db.invoices.find(filt, {"_id": 0, "balance_due_cents": 1})]
        return {"value": len(docs), "amount_cents": sum(int(d.get("balance_due_cents") or 0) for d in docs)}
    if kind == "summary":
        now: datetime = ctx["now"]
        buckets = {"overdue": [0, 0], "due_7": [0, 0], "later": [0, 0]}
        async for d in db.invoices.find(filt, {"_id": 0, "due_date": 1, "balance_due_cents": 1, "status": 1}):
            due = _parse_dt(d.get("due_date"))
            bucket = "overdue" if d.get("status") == "overdue" or (due and due < now) else "due_7" if due and due <= now + timedelta(days=7) else "later"
            buckets[bucket][0] += 1
            buckets[bucket][1] += int(d.get("balance_due_cents") or 0)
        labels = {"overdue": "Overdue", "due_7": "Due in 7 days", "later": "Due later or no due date"}
        rows = [{"label": labels[k], "value": v[0], "amount_cents": v[1], "to": "/invoices"} for k, v in buckets.items()]
        return {"rows": rows, "total": sum(r["value"] for r in rows), "amount_cents": sum(r["amount_cents"] for r in rows)}
    items = await _find("invoices", filt, sort="number", fields={"id": 1, "number": 1, "title": 1, "status": 1, "due_date": 1, "balance_due_cents": 1})
    return {"total": await db.invoices.count_documents(filt), "items": [
        {"id": i["id"], "ref": f"I-{i.get('number')}", "title": i.get("title"), "status": i.get("status"), "status_kind": "invoice",
         "amount_cents": i.get("balance_due_cents"), "due_date": i.get("due_date"), "to": f"/invoices/{i['id']}"} for i in items]}


async def _production(tenant_id: str, kind: str, _ctx: dict) -> dict:
    filt = {**_not_archived(tenant_id), "production_status": {"$in": list(RAW_ACTIVE_PRODUCTION_STATUSES)}}
    if kind == "kpi":
        return {"value": await db.work_orders.count_documents(filt)}
    if kind == "summary":
        counts = dict.fromkeys(ACTIVE_PRODUCTION_STATUSES, 0)
        async for d in db.work_orders.find(filt, {"_id": 0, "production_status": 1}):
            status = effective_status(d.get("production_status"))
            if status in counts:
                counts[status] += 1
        rows = [{"label": s.replace("_", " ").capitalize(), "value": n, "status": s, "to": f"/work-orders?production_status={s}"} for s, n in counts.items()]
        return {"rows": rows, "total": sum(counts.values())}
    items = await _find("work_orders", filt, sort="number", fields={"id": 1, "number": 1, "title": 1, "production_status": 1, "due_at": 1})
    return {"total": await db.work_orders.count_documents(filt), "items": [
        {"id": w["id"], "ref": f"W-{w.get('number')}", "title": w.get("title") or "Work order", "status": effective_status(w.get("production_status")),
         "status_kind": "production", "to": f"/work-orders/{w['id']}"} for w in items]}


async def _timesheets_pending(tenant_id: str, _kind: str, _ctx: dict) -> dict:
    return {"value": len(await timesheet_service.list_pending_review(tenant_id=tenant_id))}


async def _active_team(tenant_id: str, _kind: str, _ctx: dict) -> dict:
    return {"value": (await employee_service.status_counts(tenant_id=tenant_id)).get("active", 0)}


async def _todays_schedule(tenant_id: str, _kind: str, ctx: dict) -> dict:
    feed = await calendar_service.list_events(tenant_id=tenant_id, start_at=ctx["day_start"], end_at=ctx["day_end"], limit=LIST_LIMIT,
                                              window_first=True, exclude_statuses=CLOSED_EVENT_STATUSES)
    items = []
    for ev in feed.get("items") or []:
        to = f"/work-orders/{ev['work_order_id']}" if ev.get("work_order_id") else f"/orders/{ev['order_id']}" if ev.get("order_id") else "/shop-schedule"
        items.append({"id": ev.get("id"), "title": ev.get("display_title") or ev.get("title") or "Scheduled item", "start_at": ev.get("start_at"),
                      "end_at": ev.get("end_at"), "event_type": ev.get("event_type"), "status": ev.get("status"), "to": to})
    return {"total": feed.get("total", len(items)), "items": items}


async def _recent_customers(tenant_id: str, _kind: str, _ctx: dict) -> dict:
    filt = {**_not_archived(tenant_id), "lifecycle_status": {"$nin": ["archived", "merged"]}}
    items = await _find("customers", filt, sort="created_at", fields={"id": 1, "number": 1, "name": 1, "company": 1, "created_at": 1}, limit=10)
    return {"total": len(items), "items": [
        {"id": c["id"], "title": c.get("name"), "subtitle": c.get("company"), "when": c.get("created_at"), "to": f"/customers/{c['id']}"} for c in items]}


async def _recent_activity(tenant_id: str, _kind: str, _ctx: dict) -> dict:
    items = await _find("audit_events", {"tenant_id": tenant_id}, sort="created_at", fields={}, limit=12)
    return {"total": len(items), "items": items}


async def _recent_emails(tenant_id: str, _kind: str, _ctx: dict) -> dict:
    items = await _find("email_logs", {"tenant_id": tenant_id}, sort="created_at", fields={"id": 1, "subject": 1, "to_email": 1, "status": 1, "created_at": 1}, limit=10)
    return {"total": len(items), "items": [
        {"id": e.get("id"), "title": e.get("subject"), "subtitle": f"to {e.get('to_email')}", "status": e.get("status"), "status_kind": "email",
         "when": e.get("created_at"), "to": "/email-history"} for e in items]}


SOURCES: dict[str, Callable[[str, str, dict], Awaitable[dict]]] = {
    "active_orders": _active_orders,
    "quotes_awaiting": _quotes_awaiting,
    "unpaid_invoices": _unpaid_invoices,
    "production": _production,
    "timesheets_pending": _timesheets_pending,
    "active_team": _active_team,
    "todays_schedule": _todays_schedule,
    "recent_customers": _recent_customers,
    "recent_activity": _recent_activity,
    "recent_emails": _recent_emails,
}


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        when = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _day_bounds(day_start: Optional[str], day_end: Optional[str], now: datetime) -> tuple[str, str]:
    start, end = _parse_dt(day_start), _parse_dt(day_end)
    if start and end and timedelta(0) < end - start <= timedelta(hours=26):
        return start.isoformat(), end.isoformat()
    utc_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return utc_start.isoformat(), (utc_start + timedelta(days=1)).isoformat()


def _public(widget: dict) -> dict:
    return {"key": widget["key"], "family": widget["family"], "kind": widget["kind"], "title": widget["title"], "to": widget["to"]}


async def home_dashboard(user: dict, *, day_start: Optional[str] = None, day_end: Optional[str] = None) -> dict[str, Any]:
    """Layout, the widgets this user may use, and data for the visible ones."""
    tenant_id = user["tenant_id"]
    now = datetime.now(timezone.utc)
    start, end = _day_bounds(day_start, day_end, now)
    ctx = {"now": now, "day_start": start, "day_end": end}
    layout = await get_layout(user)
    hidden = set(layout["hidden"])
    available, restricted, data = [], [], {}
    for key in layout["order"]:
        widget = WIDGET_BY_KEY[key]
        if not _allowed(user, widget):
            restricted.append({**_public(widget), "required_permission": widget["perm"].value})
            continue
        available.append(_public(widget))
        if key in hidden:
            continue
        try:
            data[key] = {"state": "ready", **await SOURCES[widget["family"]](tenant_id, widget["kind"], ctx)}
        except Exception:  # one failing source must not break Home
            logger.exception("Home widget %s failed", key)
            data[key] = {"state": "unavailable", "message": "This information is unavailable right now."}
    return {"layout": layout, "widgets": available, "restricted": restricted, "data": data}
