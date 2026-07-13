"""EC3 — Orders router.

Extended for the rich Order Item schema, backend-derived totals, pricing
snapshots, manual price overrides with reason, and the `production_required`
flag / override.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..deps import require_permission
from ..models.order import Order, OrderItem
from ..services.audit import record_audit
from ..services.commerce_totals import compute_document_totals, compute_line_totals
from ..services.order_item_rules import default_production_required
from ..services.pricing_snapshot import build_manual_snapshot
from ..services.sequence import next_number

router = APIRouter(prefix="/orders", tags=["orders"])

# ---- Payloads ----


class OrderCreateIn(BaseModel):
    customer_id: str
    job_name: str = Field(min_length=1, max_length=200)
    title: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    notes_internal: Optional[str] = None
    notes_customer: Optional[str] = None
    due_date: Optional[str] = None


class OrderUpdateIn(BaseModel):
    job_name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    notes_internal: Optional[str] = None
    notes_customer: Optional[str] = None
    due_date: Optional[str] = None


class OrderStatusIn(BaseModel):
    status: Literal["draft", "confirmed", "in_production", "ready", "completed", "cancelled", "archived"]
    reason: Optional[str] = None


# EC3 §13 — Reject financial-status impersonation
FORBIDDEN_STATUSES = {"paid", "partially_paid", "invoiced", "refunded", "overpaid", "unpaid"}


class OrderItemIn(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: int = Field(1, ge=1)
    unit_price_cents: int = Field(0, ge=0)
    discount_cents: int = Field(0, ge=0)
    tax_cents: int = Field(0, ge=0)
    category: Optional[str] = None
    product_type: Optional[str] = None
    sku: Optional[str] = None
    unit_of_measure: str = "each"
    width_inches: Optional[float] = None
    height_inches: Optional[float] = None
    depth_inches: Optional[float] = None
    material_key: Optional[str] = None
    notes: Optional[str] = None
    production_required: Optional[bool] = None
    manual_override_reason: Optional[str] = None


class OrderItemPatchIn(BaseModel):
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    quantity: Optional[int] = Field(None, ge=1)
    unit_price_cents: Optional[int] = Field(None, ge=0)
    discount_cents: Optional[int] = Field(None, ge=0)
    tax_cents: Optional[int] = Field(None, ge=0)
    category: Optional[str] = None
    product_type: Optional[str] = None
    sku: Optional[str] = None
    unit_of_measure: Optional[str] = None
    width_inches: Optional[float] = None
    height_inches: Optional[float] = None
    depth_inches: Optional[float] = None
    material_key: Optional[str] = None
    notes: Optional[str] = None
    position: Optional[int] = None
    manual_override_reason: Optional[str] = None
    production_required: Optional[bool] = None
    production_required_override_reason: Optional[str] = None


# ---- Helpers ----


async def _list_items(tenant_id: str, order_id: str) -> list[dict[str, Any]]:
    cursor = db.order_items.find(
        {"tenant_id": tenant_id, "order_id": order_id}, {"_id": 0}
    ).sort("position", 1)
    return [serialize_doc(d) async for d in cursor]


async def _recompute_order_totals(tenant_id: str, order_id: str) -> dict[str, int]:
    items = await _list_items(tenant_id, order_id)
    totals = compute_document_totals(items)
    updates = {
        "subtotal_cents": totals["subtotal_cents"],
        "discount_cents": totals["discount_cents"],
        "tax_cents": totals["tax_cents"],
        "total_cents": totals["total_cents"],
        "balance_cents": totals["total_cents"],
        "updated_at": utc_now().isoformat(),
    }
    await db.orders.update_one({"id": order_id, "tenant_id": tenant_id}, {"$set": updates})
    return totals


# ---- Order CRUD ----


@router.get("")
async def list_orders(
    status: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.ORDER_READ)),
) -> dict:
    q: dict = {"tenant_id": user["tenant_id"]}
    if status:
        q["status"] = status
    if customer_id:
        q["customer_id"] = customer_id
    total = await db.orders.count_documents(q)
    cursor = db.orders.find(q, {"_id": 0}).sort("number", -1).skip(skip).limit(limit)
    items = [serialize_doc(d) async for d in cursor]
    return {"items": items, "total": total, "limit": limit, "skip": skip}


@router.post("", status_code=201)
async def create_order(payload: OrderCreateIn, user: dict = Depends(require_permission(Perm.ORDER_WRITE))) -> dict:
    cust = await db.customers.find_one({"id": payload.customer_id, "tenant_id": user["tenant_id"]})
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    number = await next_number(tenant_id=user["tenant_id"], name="order")
    order = Order(
        tenant_id=user["tenant_id"],
        number=number,
        customer_id=payload.customer_id,
        job_name=payload.job_name,
        title=payload.title or payload.job_name,
        description=payload.description,
        notes=payload.notes,
        notes_internal=payload.notes_internal,
        notes_customer=payload.notes_customer,
        due_date=payload.due_date,
        created_by=user["id"],
    )
    await db.orders.insert_one(prepare_for_mongo(order.model_dump()))
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="order.created", entity_type="order", entity_id=order.id,
        summary=f"Order O-{number} created for {cust['name']}",
    )
    return serialize_doc(order.model_dump())


@router.get("/{order_id}")
async def get_order(order_id: str, user: dict = Depends(require_permission(Perm.ORDER_READ))) -> dict:
    doc = await db.orders.find_one({"id": order_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Order not found")
    items = await _list_items(user["tenant_id"], order_id)
    return {"order": serialize_doc(doc), "items": items, "totals": compute_document_totals(items)}


@router.patch("/{order_id}")
async def update_order(order_id: str, payload: OrderUpdateIn, user: dict = Depends(require_permission(Perm.ORDER_WRITE))) -> dict:
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates")
    updates["updated_at"] = utc_now().isoformat()
    res = await db.orders.update_one({"id": order_id, "tenant_id": user["tenant_id"]}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="order.updated", entity_type="order", entity_id=order_id,
        summary="Order updated", diff={"changes": updates},
    )
    doc = await db.orders.find_one({"id": order_id}, {"_id": 0})
    return serialize_doc(doc)


@router.post("/{order_id}/status")
async def set_order_status(order_id: str, payload: OrderStatusIn, user: dict = Depends(require_permission(Perm.ORDER_WRITE))) -> dict:
    if payload.status in FORBIDDEN_STATUSES:
        raise HTTPException(status_code=400, detail=f"'{payload.status}' is not a valid order status")
    doc = await db.orders.find_one({"id": order_id, "tenant_id": user["tenant_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Order not found")
    current = doc.get("status") or "draft"
    if payload.status == current:
        return serialize_doc(doc)

    allowed = {
        "draft": {"confirmed", "cancelled"},
        "confirmed": {"in_production", "cancelled"},
        "in_production": {"ready", "on_hold" if False else "in_production", "cancelled"},
        "ready": {"completed", "cancelled"},
        "completed": {"archived"},
        "cancelled": {"archived"},
        "archived": set(),
    }
    if payload.status not in allowed.get(current, set()):
        raise HTTPException(status_code=400, detail=f"Invalid transition {current} → {payload.status}")

    updates: dict[str, Any] = {"status": payload.status, "updated_at": utc_now().isoformat()}
    if payload.status == "archived":
        updates["archived_at"] = utc_now().isoformat()
    await db.orders.update_one({"id": order_id}, {"$set": updates})
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action=f"order.status.{payload.status}", entity_type="order", entity_id=order_id,
        summary=f"Order O-{doc['number']} → {payload.status}",
        diff={"from": current, "to": payload.status, "reason": payload.reason},
    )
    doc = await db.orders.find_one({"id": order_id}, {"_id": 0})
    return serialize_doc(doc)


@router.post("/{order_id}/recalculate")
async def recalculate(order_id: str, user: dict = Depends(require_permission(Perm.ORDER_WRITE))) -> dict:
    order = await db.orders.find_one({"id": order_id, "tenant_id": user["tenant_id"]})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    totals = await _recompute_order_totals(user["tenant_id"], order_id)
    return {"totals": totals}


# ---- Order Items ----


@router.post("/{order_id}/items", status_code=201)
async def add_item(order_id: str, payload: OrderItemIn, user: dict = Depends(require_permission(Perm.ORDER_WRITE))) -> dict:
    order = await db.orders.find_one({"id": order_id, "tenant_id": user["tenant_id"]})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    position = await db.order_items.count_documents({"tenant_id": user["tenant_id"], "order_id": order_id})
    prod_req = payload.production_required
    if prod_req is None:
        prod_req = default_production_required(payload.category)
    line = compute_line_totals(
        quantity=payload.quantity,
        unit_price_cents=payload.unit_price_cents,
        discount_cents=payload.discount_cents,
        tax_cents=payload.tax_cents,
    )
    snapshot = build_manual_snapshot(
        unit_price_cents=payload.unit_price_cents,
        quantity=payload.quantity,
        reason=payload.manual_override_reason,
        actor_user_id=user["id"],
        actor_email=user["email"],
        source="user_entered",
    )
    item = OrderItem(
        tenant_id=user["tenant_id"],
        order_id=order_id,
        position=position,
        category=payload.category,
        product_type=payload.product_type,
        description=payload.description,
        sku=payload.sku,
        quantity=payload.quantity,
        unit_of_measure=payload.unit_of_measure,
        width_inches=payload.width_inches,
        height_inches=payload.height_inches,
        depth_inches=payload.depth_inches,
        material_key=payload.material_key,
        unit_price_cents=payload.unit_price_cents,
        discount_cents=line["discount_cents"],
        tax_cents=line["tax_cents"],
        line_subtotal_cents=line["line_subtotal_cents"],
        line_total_cents=line["line_total_cents"],
        pricing_snapshot=snapshot,
        manual_override_reason=payload.manual_override_reason,
        production_required=bool(prod_req),
        notes=payload.notes,
    )
    await db.order_items.insert_one(prepare_for_mongo(item.model_dump()))
    await _recompute_order_totals(user["tenant_id"], order_id)
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="order.item_added", entity_type="order", entity_id=order_id,
        summary=f"Item added to O-{order['number']}: {payload.description}",
        diff={"item_id": item.id, "unit_price_cents": payload.unit_price_cents,
              "quantity": payload.quantity, "production_required": bool(prod_req)},
    )
    return serialize_doc(item.model_dump())


@router.patch("/{order_id}/items/{item_id}")
async def update_item(order_id: str, item_id: str, payload: OrderItemPatchIn,
                      user: dict = Depends(require_permission(Perm.ORDER_WRITE))) -> dict:
    order = await db.orders.find_one({"id": order_id, "tenant_id": user["tenant_id"]})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    line = await db.order_items.find_one({"id": item_id, "order_id": order_id, "tenant_id": user["tenant_id"]})
    if not line:
        raise HTTPException(status_code=404, detail="Order item not found")
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates")

    now = utc_now().isoformat()
    # Manual override reason required for unit price change
    if "unit_price_cents" in updates and int(updates["unit_price_cents"]) != int(line.get("unit_price_cents") or 0):
        if not updates.get("manual_override_reason") and not line.get("manual_override_reason"):
            raise HTTPException(status_code=400, detail="Override reason required for manual price change")
        updates["manual_override_actor_user_id"] = user["id"]
        updates["manual_override_actor_email"] = user["email"]
        updates["manual_override_at"] = now

    # production_required override needs a reason
    if "production_required" in updates and bool(updates["production_required"]) != bool(line.get("production_required")):
        if not updates.get("production_required_override_reason"):
            raise HTTPException(status_code=400, detail="production_required override requires a reason")
        updates["production_required_override_actor_user_id"] = user["id"]
        updates["production_required_override_at"] = now

    merged = {**line, **updates}
    line_totals = compute_line_totals(
        quantity=int(merged.get("quantity") or 1),
        unit_price_cents=int(merged.get("unit_price_cents") or 0),
        discount_cents=int(merged.get("discount_cents") or 0),
        tax_cents=int(merged.get("tax_cents") or 0),
    )
    updates.update(line_totals)
    updates["updated_at"] = now
    await db.order_items.update_one({"id": item_id}, {"$set": updates})
    await _recompute_order_totals(user["tenant_id"], order_id)
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="order.item_updated", entity_type="order", entity_id=order_id,
        summary="Order item updated", diff={"item_id": item_id, "changes": updates},
    )
    doc = await db.order_items.find_one({"id": item_id}, {"_id": 0})
    return serialize_doc(doc)


@router.delete("/{order_id}/items/{item_id}", status_code=204, response_class=Response)
async def delete_item(order_id: str, item_id: str, user: dict = Depends(require_permission(Perm.ORDER_WRITE))) -> Response:
    line = await db.order_items.find_one({"id": item_id, "order_id": order_id, "tenant_id": user["tenant_id"]})
    if not line:
        raise HTTPException(status_code=404, detail="Order item not found")
    await db.order_items.delete_one({"id": item_id})
    await _recompute_order_totals(user["tenant_id"], order_id)
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="order.item_archived", entity_type="order", entity_id=order_id,
        summary="Order item removed",
        diff={"item_id": item_id, "description": line.get("description")},
    )
    return Response(status_code=204)
