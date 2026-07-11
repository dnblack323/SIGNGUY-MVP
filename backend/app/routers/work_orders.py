from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..deps import require_permission
from ..models.work_order import WorkOrder
from ..services.audit import record_audit
from ..services.sequence import next_number

router = APIRouter(prefix="/work-orders", tags=["work_orders"])


class WorkOrderCreateIn(BaseModel):
    order_id: str
    production_instructions: Optional[str] = None
    internal_notes: Optional[str] = None
    assigned_to: Optional[str] = None


class WorkOrderUpdateIn(BaseModel):
    production_instructions: Optional[str] = None
    internal_notes: Optional[str] = None
    assigned_to: Optional[str] = None


class ProductionStatusIn(BaseModel):
    production_status: Literal["not_started", "in_progress", "on_hold", "completed"]


@router.get("")
async def list_work_orders(
    production_status: Optional[str] = Query(None),
    order_id: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200), skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.WORK_ORDER_READ)),
) -> dict:
    q: dict = {"tenant_id": user["tenant_id"]}
    if production_status:
        q["production_status"] = production_status
    if order_id:
        q["order_id"] = order_id
    if customer_id:
        q["customer_id"] = customer_id
    total = await db.work_orders.count_documents(q)
    cursor = db.work_orders.find(q, {"_id": 0}).sort("number", -1).skip(skip).limit(limit)
    return {"items": [serialize_doc(d) async for d in cursor], "total": total, "limit": limit, "skip": skip}


@router.post("", status_code=201)
async def create_work_order(payload: WorkOrderCreateIn, user: dict = Depends(require_permission(Perm.WORK_ORDER_WRITE))) -> dict:
    order = await db.orders.find_one({"id": payload.order_id, "tenant_id": user["tenant_id"]})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if payload.assigned_to:
        assignee = await db.users.find_one({"id": payload.assigned_to, "tenant_id": user["tenant_id"]})
        if not assignee:
            raise HTTPException(status_code=400, detail="Assigned user not found")
    # Snapshot only order items requiring production (EC3 §15)
    items_snapshot = []
    async for it in db.order_items.find({"tenant_id": user["tenant_id"], "order_id": order["id"]}, {"_id": 0}).sort("position", 1):
        if not it.get("production_required", True):
            continue
        items_snapshot.append({
            "order_item_id": it["id"],
            "description": it["description"],
            "quantity": int(it.get("quantity", 1)),
            "unit_price_cents": int(it.get("unit_price_cents", 0)),
            "category": it.get("category"),
            "production_required": True,
        })
    number = await next_number(tenant_id=user["tenant_id"], name="work_order")
    wo = WorkOrder(
        tenant_id=user["tenant_id"], number=number,
        order_id=order["id"], customer_id=order["customer_id"],
        production_instructions=payload.production_instructions,
        internal_notes=payload.internal_notes,
        assigned_to=payload.assigned_to,
        items_snapshot=items_snapshot,
        created_by=user["id"],
    )
    await db.work_orders.insert_one(prepare_for_mongo(wo.model_dump()))
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="work_order.create", entity_type="work_order", entity_id=wo.id,
        summary=f"Work Order W-{number} created from Order O-{order['number']}",
        diff={"order_id": order["id"], "items_count": len(items_snapshot)},
    )
    return serialize_doc(wo.model_dump())


@router.get("/{wo_id}")
async def get_work_order(wo_id: str, user: dict = Depends(require_permission(Perm.WORK_ORDER_READ))) -> dict:
    doc = await db.work_orders.find_one({"id": wo_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Work order not found")
    return serialize_doc(doc)


@router.patch("/{wo_id}")
async def update_work_order(wo_id: str, payload: WorkOrderUpdateIn, user: dict = Depends(require_permission(Perm.WORK_ORDER_WRITE))) -> dict:
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="No updates")
    updates["updated_at"] = utc_now().isoformat()
    if "assigned_to" in updates and updates["assigned_to"]:
        assignee = await db.users.find_one({"id": updates["assigned_to"], "tenant_id": user["tenant_id"]})
        if not assignee:
            raise HTTPException(status_code=400, detail="Assigned user not found")
    res = await db.work_orders.update_one({"id": wo_id, "tenant_id": user["tenant_id"]}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Work order not found")
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="work_order.update", entity_type="work_order", entity_id=wo_id,
        summary="Work order updated", diff={"changes": updates},
    )
    doc = await db.work_orders.find_one({"id": wo_id}, {"_id": 0})
    return serialize_doc(doc)


@router.post("/{wo_id}/production-status")
async def set_production_status(wo_id: str, payload: ProductionStatusIn, user: dict = Depends(require_permission(Perm.WORK_ORDER_WRITE))) -> dict:
    doc = await db.work_orders.find_one({"id": wo_id, "tenant_id": user["tenant_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Work order not found")
    if payload.production_status == doc["production_status"]:
        return serialize_doc(doc)
    await db.work_orders.update_one(
        {"id": wo_id}, {"$set": {"production_status": payload.production_status, "updated_at": utc_now().isoformat()}}
    )
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="work_order.status_change", entity_type="work_order", entity_id=wo_id,
        summary=f"W-{doc['number']} production status → {payload.production_status}",
        diff={"from": doc["production_status"], "to": payload.production_status},
    )
    doc = await db.work_orders.find_one({"id": wo_id}, {"_id": 0})
    return serialize_doc(doc)
