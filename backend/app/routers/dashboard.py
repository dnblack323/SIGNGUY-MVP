from __future__ import annotations

from fastapi import APIRouter, Depends

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import serialize_doc
from ..deps import require_permission
from ..services import order_completion_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def dashboard_summary(user: dict = Depends(require_permission(Perm.DASHBOARD_READ))) -> dict:
    tid = user["tenant_id"]

    active_order_statuses = ["confirmed", "in_production"]
    active_orders_count = await db.orders.count_documents({"tenant_id": tid, "status": {"$in": active_order_statuses}})
    quotes_follow_up_count = await db.quotes.count_documents({"tenant_id": tid, "status": "sent"})
    wo_attention_count = await db.work_orders.count_documents({
        "tenant_id": tid, "production_status": {"$in": ["in_progress", "on_hold"]}
    })
    unpaid_invoices_count = await db.invoices.count_documents({
        "tenant_id": tid, "status": {"$in": ["sent", "viewed", "partially_paid", "overdue"]}
    })

    async def _list(coll, q, sort_field="created_at", limit=8):
        out = []
        async for d in db[coll].find(q, {"_id": 0}).sort(sort_field, -1).limit(limit):
            out.append(serialize_doc(d))
        return out

    active_orders = await _list("orders", {"tenant_id": tid, "status": {"$in": active_order_statuses}}, "number")
    quotes_follow_up = await _list("quotes", {"tenant_id": tid, "status": "sent"}, "number")
    work_orders_attention = await _list("work_orders", {"tenant_id": tid, "production_status": {"$in": ["in_progress", "on_hold"]}}, "number")
    unpaid_invoices = await _list("invoices", {"tenant_id": tid, "status": {"$in": ["sent", "viewed", "partially_paid", "overdue"]}}, "number")
    recent_emails = await _list("email_logs", {"tenant_id": tid}, "created_at", 8)
    recent_activity = await _list("audit_events", {"tenant_id": tid}, "created_at", 12)

    return {
        "counts": {
            "active_orders": active_orders_count,
            "quotes_follow_up": quotes_follow_up_count,
            "work_orders_attention": wo_attention_count,
            "unpaid_invoices": unpaid_invoices_count,
        },
        "active_orders": active_orders,
        "quotes_follow_up": quotes_follow_up,
        "work_orders_attention": work_orders_attention,
        "unpaid_invoices": unpaid_invoices,
        "recent_emails": recent_emails,
        "recent_activity": recent_activity,
    }


@router.get("/shop-operations/analytics")
async def shop_operations_analytics(user: dict = Depends(require_permission(Perm.DASHBOARD_READ))) -> dict:
    return await order_completion_service.shop_operations_analytics(user["tenant_id"])
