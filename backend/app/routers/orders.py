"""EC3 — Orders router.

Extended for the rich Order Item schema, backend-derived totals, pricing
snapshots, manual price overrides with reason, and the `production_required`
flag / override.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..deps import require_permission
from ..models.order import Order, OrderItem
from ..services.audit import record_audit
from ..services.commerce_totals import compute_document_totals, compute_line_totals, compute_pricing_summary
from ..services.order_item_rules import default_production_required
from ..services.order_pricing import build_item_pricing_fields, calculate_for_references
from ..services.pricing import get_or_init_pricing_settings
from ..services.pricing_snapshot_records import create_snapshot_record
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
    # EC9 Phase 9F — calculator-created / saved-item / canonical-material items.
    item_name: Optional[str] = None
    category_inputs: dict[str, Any] = Field(default_factory=dict)
    material_profile_id: Optional[str] = None
    pricing_component_ids: list[str] = Field(default_factory=list)
    saved_item_id: Optional[str] = None
    manual_price_cents: Optional[int] = Field(None, ge=0)
    selected_price_source: Optional[Literal["suggested", "manual"]] = None


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
    # EC9 Phase 9F
    item_name: Optional[str] = None
    category_inputs: Optional[dict[str, Any]] = None
    material_profile_id: Optional[str] = None
    pricing_component_ids: Optional[list[str]] = None
    saved_item_id: Optional[str] = None
    manual_price_cents: Optional[int] = Field(None, ge=0)
    selected_price_source: Optional[Literal["suggested", "manual"]] = None
    recalculate: bool = False


class RecalculatePreviewIn(BaseModel):
    category_inputs: Optional[dict[str, Any]] = None
    width_inches: Optional[float] = None
    height_inches: Optional[float] = None


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


async def _resolve_item_pricing(
    *, user: dict, category: Optional[str], quantity: int, category_inputs: Optional[dict],
    material_profile_id: Optional[str], pricing_component_ids: Optional[list], saved_item_id: Optional[str],
    manual_price_cents: Optional[int], selected_price_source: Optional[str], fallback_unit_price_cents: int,
    manual_override_reason: Optional[str], recalculated: bool = False,
    width_inches: Optional[float] = None, height_inches: Optional[float] = None,
) -> dict[str, Any]:
    """EC9 Phase 9F — the ONE place Order Item pricing is derived. Calls the
    canonical pricing service; never computes cost/price itself."""
    category_inputs = category_inputs or {}
    pricing_component_ids = pricing_component_ids or []
    use_calculator = bool(category) and (
        bool(category_inputs) or bool(material_profile_id) or bool(pricing_component_ids)
        or bool(saved_item_id) or selected_price_source == "suggested"
    )
    calc_result = None
    foundation_effective_at = None
    if use_calculator:
        settings = await get_or_init_pricing_settings(user["tenant_id"])
        foundation_effective_at = settings.get("updated_at")
        try:
            calc_result = await calculate_for_references(
                settings=settings, category=category, quantity=quantity, category_inputs=category_inputs,
                material_profile_id=material_profile_id, pricing_component_ids=pricing_component_ids,
                saved_item_id=saved_item_id, width_inches=width_inches, height_inches=height_inches,
            )
        except ValueError as e:
            detail = "Material pricing profile not found" if str(e) == "material_profile_not_found" else (
                "Saved item not found" if str(e) == "saved_item_not_found" else str(e))
            raise HTTPException(status_code=404, detail=detail)
    return build_item_pricing_fields(
        calc_result=calc_result, quantity=quantity, category=category, category_inputs=category_inputs,
        material_profile_id=material_profile_id, pricing_component_ids=pricing_component_ids,
        saved_item_id=saved_item_id, manual_price_cents=manual_price_cents, selected_price_source=selected_price_source,
        fallback_unit_price_cents=fallback_unit_price_cents, user_id=user["id"], actor_email=user["email"],
        foundation_effective_at=foundation_effective_at, manual_override_reason=manual_override_reason,
        recalculated=recalculated,
    )


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
    return {
        "order": serialize_doc(doc), "items": items, "totals": compute_document_totals(items),
        "pricing_summary": compute_pricing_summary(items),
    }


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
    doc = await db.orders.find_one({"id": order_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
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
    await db.orders.update_one({"id": order_id, "tenant_id": user["tenant_id"]}, {"$set": updates})
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action=f"order.status.{payload.status}", entity_type="order", entity_id=order_id,
        summary=f"Order O-{doc['number']} → {payload.status}",
        diff={"from": current, "to": payload.status, "reason": payload.reason},
    )
    doc = await db.orders.find_one({"id": order_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
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
    pricing_fields = await _resolve_item_pricing(
        user=user, category=payload.category, quantity=payload.quantity, category_inputs=payload.category_inputs,
        material_profile_id=payload.material_profile_id, pricing_component_ids=payload.pricing_component_ids,
        saved_item_id=payload.saved_item_id, manual_price_cents=payload.manual_price_cents,
        selected_price_source=payload.selected_price_source, fallback_unit_price_cents=payload.unit_price_cents,
        manual_override_reason=payload.manual_override_reason,
        width_inches=payload.width_inches, height_inches=payload.height_inches,
    )
    final_unit_price_cents = pricing_fields.pop("unit_price_cents")
    line = compute_line_totals(
        quantity=payload.quantity,
        unit_price_cents=final_unit_price_cents,
        discount_cents=payload.discount_cents,
        tax_cents=payload.tax_cents,
    )
    item = OrderItem(
        tenant_id=user["tenant_id"],
        order_id=order_id,
        position=position,
        item_name=payload.item_name,
        product_type=payload.product_type,
        description=payload.description,
        sku=payload.sku,
        quantity=payload.quantity,
        unit_of_measure=payload.unit_of_measure,
        width_inches=payload.width_inches,
        height_inches=payload.height_inches,
        depth_inches=payload.depth_inches,
        material_key=payload.material_key,
        unit_price_cents=final_unit_price_cents,
        discount_cents=line["discount_cents"],
        tax_cents=line["tax_cents"],
        line_subtotal_cents=line["line_subtotal_cents"],
        line_total_cents=line["line_total_cents"],
        manual_override_reason=payload.manual_override_reason,
        production_required=bool(prod_req),
        notes=payload.notes,
        **pricing_fields,
    )
    await db.order_items.insert_one(prepare_for_mongo(item.model_dump()))
    await _recompute_order_totals(user["tenant_id"], order_id)

    # EC9 Phase 9G — every priced order item gets an immutable historical
    # snapshot record (append-only; never mutated afterward).
    await create_snapshot_record(
        tenant_id=user["tenant_id"], source_type="order_item", source_id=item.id,
        order_id=order_id, item_doc=item.model_dump(), calculated_by_user_id=user["id"],
    )

    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="order.item_added", entity_type="order", entity_id=order_id,
        summary=f"Item added to O-{order['number']}: {payload.description}",
        diff={"item_id": item.id, "unit_price_cents": final_unit_price_cents,
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
    updates = payload.model_dump(exclude_none=True, exclude={"recalculate"})
    recalc_requested = payload.recalculate
    if not updates and not recalc_requested:
        raise HTTPException(status_code=400, detail="No updates")

    now = utc_now().isoformat()

    pricing_trigger_fields = {"category_inputs", "material_profile_id", "pricing_component_ids", "saved_item_id",
                               "manual_price_cents", "selected_price_source", "category", "quantity",
                               "width_inches", "height_inches"}
    needs_pricing_resolution = recalc_requested or any(f in updates for f in pricing_trigger_fields)
    if needs_pricing_resolution:
        pricing_fields = await _resolve_item_pricing(
            user=user,
            category=updates.get("category", line.get("category")),
            quantity=int(updates.get("quantity", line.get("quantity") or 1)),
            category_inputs=updates.get("category_inputs", line.get("category_inputs") or {}),
            material_profile_id=updates.get("material_profile_id", line.get("material_profile_id")),
            pricing_component_ids=updates.get("pricing_component_ids", line.get("pricing_component_ids") or []),
            saved_item_id=updates.get("saved_item_id", line.get("saved_item_id")),
            manual_price_cents=updates.get("manual_price_cents", line.get("manual_price_cents")),
            selected_price_source=updates.get("selected_price_source", line.get("selected_price_source")),
            fallback_unit_price_cents=int(updates.get("unit_price_cents", line.get("unit_price_cents") or 0)),
            manual_override_reason=updates.get("manual_override_reason", line.get("manual_override_reason")),
            recalculated=recalc_requested,
            width_inches=updates.get("width_inches", line.get("width_inches")),
            height_inches=updates.get("height_inches", line.get("height_inches")),
        )
        if recalc_requested and line.get("pricing_snapshot"):
            updates["previous_pricing_snapshot"] = line.get("pricing_snapshot")
        updates.update(pricing_fields)

    # Manual override reason required only when the SELECTED final price
    # changes AND the resulting source is "manual". Backend-authoritative
    # "suggested" acceptances never require one.
    price_changed = "unit_price_cents" in updates and int(updates["unit_price_cents"]) != int(line.get("unit_price_cents") or 0)
    if price_changed:
        final_source = updates.get("selected_price_source", line.get("selected_price_source") or "manual")
        if final_source == "manual":
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
    await db.order_items.update_one(
        {"id": item_id, "order_id": order_id, "tenant_id": user["tenant_id"]},
        {"$set": updates},
    )
    await _recompute_order_totals(user["tenant_id"], order_id)

    # EC9 Phase 9G — a repriced item gets a NEW immutable snapshot record; the
    # previous "active" record is relabeled "superseded" (never mutated).
    if needs_pricing_resolution or price_changed:
        await create_snapshot_record(
            tenant_id=user["tenant_id"], source_type="order_item", source_id=item_id,
            order_id=order_id, item_doc={**line, **updates}, calculated_by_user_id=user["id"],
        )

    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="order.item_updated", entity_type="order", entity_id=order_id,
        summary="Order item updated", diff={"item_id": item_id, "changes": updates},
    )
    doc = await db.order_items.find_one(
        {"id": item_id, "order_id": order_id, "tenant_id": user["tenant_id"]},
        {"_id": 0},
    )
    return serialize_doc(doc)


@router.post("/{order_id}/items/{item_id}/recalculate-preview")
async def recalculate_item_preview(
    order_id: str,
    item_id: str,
    payload: RecalculatePreviewIn = Body(default_factory=RecalculatePreviewIn),
    user: dict = Depends(require_permission(Perm.ORDER_WRITE)),
) -> dict:
    """EC9 Phase 9F — pure preview, no persistence. Old item/snapshot stays
    untouched until the caller PATCHes with `recalculate: true` to accept."""
    order = await db.orders.find_one({"id": order_id, "tenant_id": user["tenant_id"]})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.get("status") != "draft":
        raise HTTPException(status_code=400, detail="Recalculation preview is only available for draft orders")
    line = await db.order_items.find_one({"id": item_id, "order_id": order_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not line:
        raise HTTPException(status_code=404, detail="Order item not found")
    if not line.get("category"):
        raise HTTPException(status_code=400, detail="This item has no category/calculator to recalculate")

    category_inputs = payload.category_inputs if payload.category_inputs is not None else (line.get("category_inputs") or {})
    width_inches = payload.width_inches if payload.width_inches is not None else line.get("width_inches")
    height_inches = payload.height_inches if payload.height_inches is not None else line.get("height_inches")
    pricing_fields = await _resolve_item_pricing(
        user=user, category=line.get("category"), quantity=int(line.get("quantity") or 1),
        category_inputs=category_inputs, material_profile_id=line.get("material_profile_id"),
        pricing_component_ids=line.get("pricing_component_ids") or [], saved_item_id=line.get("saved_item_id"),
        manual_price_cents=line.get("manual_price_cents"), selected_price_source=line.get("selected_price_source") or "suggested",
        fallback_unit_price_cents=int(line.get("unit_price_cents") or 0),
        manual_override_reason=line.get("manual_override_reason"), recalculated=True,
        width_inches=width_inches, height_inches=height_inches,
    )
    return {"old": {k: line.get(k) for k in (
        "unit_price_cents", "suggested_price_cents", "manual_price_cents", "selected_price_source",
        "estimated_cost_cents", "estimated_profit_cents", "estimated_margin_percent", "pricing_snapshot",
    )}, "new": pricing_fields}


@router.delete("/{order_id}/items/{item_id}", status_code=204, response_class=Response)
async def delete_item(order_id: str, item_id: str, user: dict = Depends(require_permission(Perm.ORDER_WRITE))) -> Response:
    line = await db.order_items.find_one({"id": item_id, "order_id": order_id, "tenant_id": user["tenant_id"]})
    if not line:
        raise HTTPException(status_code=404, detail="Order item not found")
    await db.order_items.delete_one({"id": item_id, "order_id": order_id, "tenant_id": user["tenant_id"]})
    await _recompute_order_totals(user["tenant_id"], order_id)
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="order.item_archived", entity_type="order", entity_id=order_id,
        summary="Order item removed",
        diff={"item_id": item_id, "description": line.get("description")},
    )
    return Response(status_code=204)
