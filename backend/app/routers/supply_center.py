"""EC7 phase 7b — Supply Center router.

Staff surface for supplier catalog operations:
  - catalog search (GET /supply/catalog?q=&category=&vendor_id=)
  - product details (GET /supply/catalog/{sp_id})
  - account price (POST /supply/catalog/{sp_id}/price)
  - inventory + shipping (GET /supply/catalog/{sp_id}/inventory)
  - shortage calc (POST /supply/shortage — accepts explicit reqs OR order_id)
  - purchasing recommendation (POST /supply/recommend)
  - cart -> draft PO (POST /supply/cart/checkout)
"""
from __future__ import annotations
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import serialize_doc
from ..deps import require_permission
from ..services import shortage_service, purchasing_recommendation, purchasing_service
from ..services.supplier_connectors import get_connector, ConnectorCapability

router = APIRouter(prefix="/supply", tags=["supply"])


# ----- Catalog + product endpoints -----
@router.get("/catalog")
async def search_catalog(q: Optional[str] = None,
                         category: Optional[str] = None,
                         vendor_id: Optional[str] = None,
                         limit: int = Query(50, le=200),
                         user: dict = Depends(require_permission(Perm.PURCHASING_READ))) -> dict:
    filt: dict[str, Any] = {"tenant_id": user["tenant_id"], "active": True}
    if category: filt["category"] = category
    if vendor_id: filt["vendor_id"] = vendor_id
    if q:
        filt["$or"] = [
            {"description": {"$regex": q, "$options": "i"}},
            {"supplier_sku": {"$regex": q, "$options": "i"}},
            {"brand": {"$regex": q, "$options": "i"}},
            {"series": {"$regex": q, "$options": "i"}},
            {"family": {"$regex": q, "$options": "i"}},
        ]
    cur = db.supplier_products.find(filt, {"_id": 0}).limit(limit)
    items = [serialize_doc(d) async for d in cur]
    total = await db.supplier_products.count_documents(filt)
    return {"items": items, "total": total}


@router.get("/catalog/{sp_id}")
async def get_catalog_product(sp_id: str,
                              user: dict = Depends(require_permission(Perm.PURCHASING_READ))) -> dict:
    prod = await db.supplier_products.find_one(
        {"tenant_id": user["tenant_id"], "id": sp_id}, {"_id": 0}
    )
    if not prod:
        raise HTTPException(status_code=404, detail="Supplier product not found")
    vendor = await db.vendors.find_one({"id": prod["vendor_id"]}, {"_id": 0})
    stocks = [serialize_doc(d) async for d in db.supplier_product_stock.find(
        {"tenant_id": user["tenant_id"], "supplier_product_id": sp_id}, {"_id": 0}
    )]
    for s in stocks:
        wh = await db.supplier_warehouses.find_one({"id": s["warehouse_id"]}, {"_id": 0})
        s["warehouse"] = serialize_doc(wh) if wh else None
    variants = []
    if prod.get("family"):
        async for v in db.supplier_products.find(
            {"tenant_id": user["tenant_id"], "family": prod["family"], "active": True},
            {"_id": 0, "id": 1, "supplier_sku": 1, "variant": 1, "description": 1}
        ):
            variants.append(serialize_doc(v))
    return {"product": serialize_doc(prod), "vendor": serialize_doc(vendor) if vendor else None,
            "stock_by_warehouse": stocks, "variants": variants}


class AccountPriceIn(BaseModel):
    quantity: int


@router.post("/catalog/{sp_id}/price")
async def account_price(sp_id: str, payload: AccountPriceIn,
                        user: dict = Depends(require_permission(Perm.PURCHASING_READ))) -> dict:
    prod = await db.supplier_products.find_one(
        {"tenant_id": user["tenant_id"], "id": sp_id}, {"_id": 0}
    )
    if not prod:
        raise HTTPException(status_code=404, detail="Supplier product not found")
    vendor = await db.vendors.find_one({"id": prod["vendor_id"]}, {"_id": 0})
    connector = get_connector(vendor["connector_key"])
    if not connector.supports(ConnectorCapability.ACCOUNT_PRICE):
        return {"unit_price_cents": int(prod.get("account_price_cents", 0)),
                "note": "connector does not support live pricing — returning last-known account price"}
    return await connector.get_account_price(
        tenant_id=user["tenant_id"], vendor_id=prod["vendor_id"],
        supplier_product_id=sp_id, quantity=int(payload.quantity),
    )


# ----- Shortage -----
class ShortageReq(BaseModel):
    material_id: str
    quantity: float
    compatible_group: Optional[str] = None
    order_id: Optional[str] = None
    order_item_id: Optional[str] = None


class ShortageIn(BaseModel):
    order_id: Optional[str] = None
    requirements: list[ShortageReq] = Field(default_factory=list)
    location_id: Optional[str] = None


@router.post("/shortage")
async def compute_shortage(payload: ShortageIn,
                           user: dict = Depends(require_permission(Perm.PURCHASING_READ))) -> dict:
    if payload.order_id:
        rows = await shortage_service.shortage_for_order(
            tenant_id=user["tenant_id"], order_id=payload.order_id,
            location_id=payload.location_id
        )
    else:
        rows = await shortage_service.compute_shortage(
            tenant_id=user["tenant_id"],
            requirements=[r.model_dump() for r in payload.requirements],
            location_id=payload.location_id,
        )
    return {"items": rows}


# ----- Recommendation -----
class RecommendReq(BaseModel):
    material_id: str
    quantity: float
    compatible_group: Optional[str] = None


class RecommendIn(BaseModel):
    requirements: list[RecommendReq]
    priority: str = "best_combined_score"


@router.post("/recommend")
async def recommend(payload: RecommendIn,
                    user: dict = Depends(require_permission(Perm.PURCHASING_READ))) -> dict:
    return await purchasing_recommendation.recommend(
        tenant_id=user["tenant_id"],
        requirements=[r.model_dump() for r in payload.requirements],
        priority=payload.priority,
    )


# ----- Cart -> draft PO(s) -----
class CartItem(BaseModel):
    vendor_id: str
    supplier_product_id: str
    supplier_warehouse_id: Optional[str] = None
    material_id: Optional[str] = None
    order_id: Optional[str] = None
    order_item_id: Optional[str] = None
    description: str
    manufacturer: Optional[str] = None
    brand: Optional[str] = None
    supplier_sku: Optional[str] = None
    variant: dict[str, Any] = Field(default_factory=dict)
    quantity_ordered: float
    unit_price_cents: int
    package_qty: int = 1
    unit_of_measure: str = "each"


class CartCheckoutIn(BaseModel):
    items: list[CartItem]
    ship_to_location_id: Optional[str] = None
    source_recommendation_key: Optional[str] = None
    source_priority: Optional[str] = None
    notes: Optional[str] = None
    shipping_cents_by_vendor: dict[str, int] = Field(default_factory=dict)
    handling_cents_by_vendor: dict[str, int] = Field(default_factory=dict)


@router.post("/cart/checkout", status_code=201)
async def cart_checkout(payload: CartCheckoutIn,
                        user: dict = Depends(require_permission(Perm.PURCHASING_WRITE))) -> dict:
    """Turn a purchasing cart into one draft PO per vendor.

    The cart items are grouped by vendor. One PurchaseOrder is created per
    vendor with the full set of lines. Shipping+handling estimates can be
    injected per vendor via `shipping_cents_by_vendor` / `handling_cents_by_vendor`
    (typically supplied by the recommendation totals).
    """
    if not payload.items:
        raise HTTPException(status_code=400, detail="Cart is empty")
    by_vendor: dict[str, list[CartItem]] = {}
    for item in payload.items:
        by_vendor.setdefault(item.vendor_id, []).append(item)
    created: list[dict] = []
    for vendor_id, items in by_vendor.items():
        po = await purchasing_service.create_draft(
            tenant_id=user["tenant_id"], vendor_id=vendor_id,
            actor_user_id=user["id"], actor_email=user["email"],
            ship_to_location_id=payload.ship_to_location_id,
            source_recommendation_key=payload.source_recommendation_key,
            source_priority=payload.source_priority, notes=payload.notes,
        )
        for pos, it in enumerate(items):
            await purchasing_service.add_line(
                tenant_id=user["tenant_id"], purchase_order_id=po["id"],
                actor_user_id=user["id"], actor_email=user["email"],
                payload={**it.model_dump(), "position": pos},
            )
        await purchasing_service.set_freight(
            tenant_id=user["tenant_id"], purchase_order_id=po["id"],
            shipping_cents=int(payload.shipping_cents_by_vendor.get(vendor_id, 0)),
            handling_cents=int(payload.handling_cents_by_vendor.get(vendor_id, 0)),
        )
        refreshed = await db.purchase_orders.find_one(
            {"tenant_id": user["tenant_id"], "id": po["id"]}, {"_id": 0}
        )
        created.append(serialize_doc(refreshed))
    return {"created": created}


# ----- Supplier order log listing -----
@router.get("/supplier-orders")
async def list_supplier_orders(purchase_order_id: Optional[str] = None,
                               vendor_id: Optional[str] = None,
                               limit: int = 100,
                               user: dict = Depends(require_permission(Perm.PURCHASING_READ))) -> dict:
    filt: dict = {"tenant_id": user["tenant_id"]}
    if purchase_order_id: filt["purchase_order_id"] = purchase_order_id
    if vendor_id: filt["vendor_id"] = vendor_id
    cur = db.supplier_order_log.find(filt, {"_id": 0}).sort("submitted_at", -1).limit(limit)
    return {"items": [serialize_doc(d) async for d in cur]}
