"""EC7 phase 7b — Purchase Order + Receiving router."""
from __future__ import annotations
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import serialize_doc
from ..deps import require_permission
from ..services import purchasing_service, receiving_service

router = APIRouter(prefix="/purchase-orders", tags=["purchase_orders"])


class POLineIn(BaseModel):
    material_id: Optional[str] = None
    supplier_product_id: Optional[str] = None
    supplier_warehouse_id: Optional[str] = None
    order_id: Optional[str] = None
    order_item_id: Optional[str] = None
    supplier_sku: Optional[str] = None
    description: str
    manufacturer: Optional[str] = None
    brand: Optional[str] = None
    variant: dict[str, Any] = Field(default_factory=dict)
    quantity_ordered: float
    unit_of_measure: str = "each"
    package_qty: int = 1
    unit_price_cents: int = 0
    position: int = 0


class PODraftIn(BaseModel):
    vendor_id: str
    ship_to_location_id: Optional[str] = None
    notes: Optional[str] = None
    lines: list[POLineIn] = Field(default_factory=list)


class POFreightIn(BaseModel):
    shipping_cents: int = 0
    handling_cents: int = 0
    tax_cents: int = 0
    warehouse_splits: list[dict[str, Any]] = Field(default_factory=list)


class POSubmitIn(BaseModel):
    confirm: bool = True


class POCancelIn(BaseModel):
    reason: str


class ReceiveLineIn(BaseModel):
    po_line_id: str
    quantity: float
    location_id: Optional[str] = None


class ReceiveIn(BaseModel):
    lines: list[ReceiveLineIn]
    default_location_id: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
async def list_pos(status: Optional[str] = None, vendor_id: Optional[str] = None,
                   limit: int = Query(100, le=500),
                   user: dict = Depends(require_permission(Perm.PURCHASING_READ))) -> dict:
    filt: dict = {"tenant_id": user["tenant_id"]}
    if status: filt["status"] = status
    if vendor_id: filt["vendor_id"] = vendor_id
    total = await db.purchase_orders.count_documents(filt)
    cur = db.purchase_orders.find(filt, {"_id": 0}).sort("number", -1).limit(limit)
    return {"items": [serialize_doc(d) async for d in cur], "total": total}


@router.post("", status_code=201)
async def create_po(payload: PODraftIn,
                    user: dict = Depends(require_permission(Perm.PURCHASING_WRITE))) -> dict:
    try:
        po = await purchasing_service.create_draft(
            tenant_id=user["tenant_id"], vendor_id=payload.vendor_id,
            actor_user_id=user["id"], actor_email=user["email"],
            ship_to_location_id=payload.ship_to_location_id, notes=payload.notes,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    for pos, line in enumerate(payload.lines):
        try:
            await purchasing_service.add_line(
                tenant_id=user["tenant_id"], purchase_order_id=po["id"],
                actor_user_id=user["id"], actor_email=user["email"],
                payload={**line.model_dump(), "position": pos},
            )
        except ValueError as ex:
            raise HTTPException(status_code=400, detail=str(ex))
    refreshed = await db.purchase_orders.find_one(
        {"tenant_id": user["tenant_id"], "id": po["id"]}, {"_id": 0}
    )
    return serialize_doc(refreshed)


@router.get("/{po_id}")
async def get_po(po_id: str,
                 user: dict = Depends(require_permission(Perm.PURCHASING_READ))) -> dict:
    po = await db.purchase_orders.find_one({"id": po_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    lines = [serialize_doc(d) async for d in db.purchase_order_lines.find(
        {"tenant_id": user["tenant_id"], "purchase_order_id": po_id}, {"_id": 0}
    ).sort("position", 1)]
    receiving = [serialize_doc(d) async for d in db.receiving_records.find(
        {"tenant_id": user["tenant_id"], "purchase_order_id": po_id}, {"_id": 0}
    ).sort("received_at", -1)]
    return {"purchase_order": serialize_doc(po), "lines": lines, "receiving_records": receiving}


@router.post("/{po_id}/lines", status_code=201)
async def add_po_line(po_id: str, payload: POLineIn,
                      user: dict = Depends(require_permission(Perm.PURCHASING_WRITE))) -> dict:
    try:
        return await purchasing_service.add_line(
            tenant_id=user["tenant_id"], purchase_order_id=po_id,
            actor_user_id=user["id"], actor_email=user["email"],
            payload=payload.model_dump(),
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@router.post("/{po_id}/freight")
async def set_po_freight(po_id: str, payload: POFreightIn,
                          user: dict = Depends(require_permission(Perm.PURCHASING_WRITE))) -> dict:
    return await purchasing_service.set_freight(
        tenant_id=user["tenant_id"], purchase_order_id=po_id,
        shipping_cents=payload.shipping_cents, handling_cents=payload.handling_cents,
        tax_cents=payload.tax_cents, warehouse_splits=payload.warehouse_splits,
    )


@router.post("/{po_id}/submit")
async def submit_po(po_id: str, payload: POSubmitIn, request: Request,
                    user: dict = Depends(require_permission(Perm.PURCHASING_WRITE))) -> dict:
    idem = request.headers.get("Idempotency-Key")
    try:
        return await purchasing_service.submit(
            tenant_id=user["tenant_id"], purchase_order_id=po_id,
            actor_user_id=user["id"], actor_email=user["email"],
            idempotency_key=idem or "", confirm=payload.confirm,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@router.post("/{po_id}/cancel")
async def cancel_po(po_id: str, payload: POCancelIn,
                    user: dict = Depends(require_permission(Perm.PURCHASING_WRITE))) -> dict:
    try:
        return await purchasing_service.cancel(
            tenant_id=user["tenant_id"], purchase_order_id=po_id,
            actor_user_id=user["id"], actor_email=user["email"], reason=payload.reason,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@router.post("/{po_id}/tracking/refresh")
async def refresh_tracking(po_id: str,
                            user: dict = Depends(require_permission(Perm.PURCHASING_READ))) -> dict:
    return await purchasing_service.poll_tracking(
        tenant_id=user["tenant_id"], purchase_order_id=po_id,
    )


@router.post("/{po_id}/receive", status_code=201)
async def receive_po(po_id: str, payload: ReceiveIn, request: Request,
                     user: dict = Depends(require_permission(Perm.PURCHASING_WRITE))) -> dict:
    idem = request.headers.get("Idempotency-Key")
    if not idem:
        raise HTTPException(status_code=400, detail="Idempotency-Key header required")
    try:
        return await receiving_service.receive(
            tenant_id=user["tenant_id"], purchase_order_id=po_id,
            actor_user_id=user["id"], actor_email=user["email"],
            idempotency_key=idem, lines=[l.model_dump() for l in payload.lines],
            default_location_id=payload.default_location_id, notes=payload.notes,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
