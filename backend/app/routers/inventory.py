"""EC7 phase 7a — Materials + Inventory (locations, items, movements, adjustments, reservations) staff router."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import serialize_doc, utc_now
from ..deps import require_permission
from ..models.material import Material, MaterialCostHistory
from ..models.inventory import InventoryLocation
from ..services import inventory_service

materials_router = APIRouter(prefix="/materials", tags=["materials"])
inventory_router = APIRouter(prefix="/inventory", tags=["inventory"])


# ---- Materials ----
class MaterialIn(BaseModel):
    name: str
    sku: Optional[str] = None
    category: str = "other"
    manufacturer: Optional[str] = None
    brand: Optional[str] = None
    series: Optional[str] = None
    description: Optional[str] = None
    purchase_unit: str = "each"
    unit_of_measure: str = "each"
    current_cost_cents: int = 0
    cost_unit: str = "each"
    reorder_point: Optional[float] = None
    reorder_quantity: Optional[float] = None
    default_location_id: Optional[str] = None
    stock_tracked: bool = True
    package_size: Optional[float] = None
    roll_width_inches: Optional[float] = None
    roll_length_feet: Optional[float] = None
    sheet_width_inches: Optional[float] = None
    sheet_height_inches: Optional[float] = None
    quantity_per_package: Optional[float] = None
    vendor_item_number: Optional[str] = None
    pricing_material_id: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


@materials_router.get("")
async def list_materials(
    category: Optional[str] = None, active: Optional[bool] = True,
    q: Optional[str] = None, limit: int = Query(200, le=500), skip: int = 0,
    user: dict = Depends(require_permission(Perm.INVENTORY_READ)),
) -> dict:
    filt: dict = {"tenant_id": user["tenant_id"]}
    if category: filt["category"] = category
    if active is not None: filt["active"] = active
    if q:
        filt["$or"] = [{"name": {"$regex": q, "$options": "i"}}, {"sku": {"$regex": q, "$options": "i"}}]
    total = await db.materials.count_documents(filt)
    cur = db.materials.find(filt, {"_id": 0}).sort("name", 1).skip(skip).limit(limit)
    return {"items": [serialize_doc(d) async for d in cur], "total": total}


@materials_router.post("", status_code=201)
async def create_material(payload: MaterialIn, user: dict = Depends(require_permission(Perm.INVENTORY_WRITE))) -> dict:
    doc = Material(tenant_id=user["tenant_id"], **payload.model_dump()).model_dump()  # type: ignore[arg-type]
    await db.materials.insert_one(doc)
    if doc["current_cost_cents"]:
        await db.material_cost_history.insert_one(MaterialCostHistory(
            tenant_id=user["tenant_id"], material_id=doc["id"],
            cost_cents=doc["current_cost_cents"], cost_unit=doc["cost_unit"],
            effective_at=utc_now().isoformat(), source="manual",
            actor_user_id=user["id"],
        ).model_dump())
    doc.pop("_id", None)
    return serialize_doc(doc)


@materials_router.get("/{mid}")
async def get_material(mid: str, user: dict = Depends(require_permission(Perm.INVENTORY_READ))) -> dict:
    doc = await db.materials.find_one({"id": mid, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Material not found")
    balances = [serialize_doc(b) async for b in db.inventory_items.find(
        {"tenant_id": user["tenant_id"], "material_id": mid}, {"_id": 0}
    )]
    cost_history = [serialize_doc(h) async for h in db.material_cost_history.find(
        {"tenant_id": user["tenant_id"], "material_id": mid}, {"_id": 0}
    ).sort("effective_at", -1).limit(50)]
    return {"material": serialize_doc(doc), "balances": balances, "cost_history": cost_history}


@materials_router.patch("/{mid}")
async def update_material(mid: str, payload: MaterialIn, user: dict = Depends(require_permission(Perm.INVENTORY_WRITE))) -> dict:
    upd = {k: v for k, v in payload.model_dump().items() if v is not None}
    upd["updated_at"] = utc_now().isoformat()
    res = await db.materials.update_one({"id": mid, "tenant_id": user["tenant_id"]}, {"$set": upd})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Material not found")
    doc = await db.materials.find_one({"id": mid}, {"_id": 0})
    return serialize_doc(doc or {})


@materials_router.post("/{mid}/archive", status_code=200)
async def archive_material(mid: str, user: dict = Depends(require_permission(Perm.INVENTORY_WRITE))) -> dict:
    res = await db.materials.update_one({"id": mid, "tenant_id": user["tenant_id"]}, {"$set": {"active": False}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Material not found")
    return {"archived": True}


@materials_router.post("/{mid}/restore", status_code=200)
async def restore_material(mid: str, user: dict = Depends(require_permission(Perm.INVENTORY_WRITE))) -> dict:
    """Reactivate an archived material — required so it can be intentionally
    re-selected for pricing (EC9 Phase 9A invariant 5)."""
    res = await db.materials.update_one({"id": mid, "tenant_id": user["tenant_id"]}, {"$set": {"active": True}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Material not found")
    return {"restored": True}


# ---- Locations ----
class LocationIn(BaseModel):
    name: str
    kind: str = "shop"
    address: Optional[str] = None
    notes: Optional[str] = None


@inventory_router.get("/locations")
async def list_locations(user: dict = Depends(require_permission(Perm.INVENTORY_READ))) -> dict:
    cur = db.inventory_locations.find({"tenant_id": user["tenant_id"]}, {"_id": 0}).sort("name", 1)
    return {"items": [serialize_doc(d) async for d in cur]}


@inventory_router.post("/locations", status_code=201)
async def create_location(payload: LocationIn, user: dict = Depends(require_permission(Perm.INVENTORY_WRITE))) -> dict:
    doc = InventoryLocation(tenant_id=user["tenant_id"], **payload.model_dump()).model_dump()  # type: ignore[arg-type]
    await db.inventory_locations.insert_one(doc)
    doc.pop("_id", None)
    return serialize_doc(doc)


# ---- Balances ----
@inventory_router.get("/items")
async def list_items(
    material_id: Optional[str] = None, location_id: Optional[str] = None,
    low_stock: bool = False, limit: int = 500,
    user: dict = Depends(require_permission(Perm.INVENTORY_READ)),
) -> dict:
    if low_stock:
        return {"items": await inventory_service.low_stock_items(tenant_id=user["tenant_id"])}
    q: dict = {"tenant_id": user["tenant_id"]}
    if material_id: q["material_id"] = material_id
    if location_id: q["location_id"] = location_id
    cur = db.inventory_items.find(q, {"_id": 0}).limit(limit)
    items = []
    async for it in cur:
        avail = float(it.get("quantity_on_hand", 0.0)) - float(it.get("quantity_reserved", 0.0))
        items.append({**serialize_doc(it), "quantity_available": avail})
    return {"items": items}


@inventory_router.get("/movements")
async def list_movements(
    material_id: Optional[str] = None, location_id: Optional[str] = None,
    source_entity_id: Optional[str] = None, limit: int = 200,
    user: dict = Depends(require_permission(Perm.INVENTORY_READ)),
) -> dict:
    q: dict = {"tenant_id": user["tenant_id"]}
    if material_id: q["material_id"] = material_id
    if location_id: q["location_id"] = location_id
    if source_entity_id: q["source_entity_id"] = source_entity_id
    cur = db.inventory_movements.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    return {"items": [serialize_doc(d) async for d in cur]}


# ---- Adjustments ----
class AdjustIn(BaseModel):
    material_id: str
    location_id: str
    quantity: float
    reason: Optional[str] = None
    unit_of_measure: str = "each"


class CountIn(BaseModel):
    material_id: str
    location_id: str
    observed_quantity: float
    reason: Optional[str] = None
    unit_of_measure: str = "each"


class TransferIn(BaseModel):
    material_id: str
    from_location_id: str
    to_location_id: str
    quantity: float
    reason: Optional[str] = None
    unit_of_measure: str = "each"


class ReserveIn(BaseModel):
    material_id: str
    location_id: str
    quantity: float
    source_entity_type: str
    source_entity_id: str
    allow_over_available: bool = False


@inventory_router.post("/adjustments/increase", status_code=201)
async def adj_increase(payload: AdjustIn, request: Request, user: dict = Depends(require_permission(Perm.INVENTORY_WRITE))) -> dict:
    return await inventory_service.manual_increase(
        tenant_id=user["tenant_id"], material_id=payload.material_id, location_id=payload.location_id,
        quantity=payload.quantity, actor_user_id=user["id"], reason=payload.reason,
        unit_of_measure=payload.unit_of_measure,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )


@inventory_router.post("/adjustments/decrease", status_code=201)
async def adj_decrease(payload: AdjustIn, request: Request, user: dict = Depends(require_permission(Perm.INVENTORY_WRITE))) -> dict:
    try:
        return await inventory_service.manual_decrease(
            tenant_id=user["tenant_id"], material_id=payload.material_id, location_id=payload.location_id,
            quantity=payload.quantity, actor_user_id=user["id"], reason=payload.reason,
            unit_of_measure=payload.unit_of_measure,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@inventory_router.post("/adjustments/count", status_code=201)
async def adj_count(payload: CountIn, request: Request, user: dict = Depends(require_permission(Perm.INVENTORY_WRITE))) -> dict:
    return await inventory_service.physical_count(
        tenant_id=user["tenant_id"], material_id=payload.material_id, location_id=payload.location_id,
        observed=payload.observed_quantity, actor_user_id=user["id"], reason=payload.reason,
        unit_of_measure=payload.unit_of_measure,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )


@inventory_router.post("/transfers", status_code=201)
async def do_transfer(payload: TransferIn, request: Request, user: dict = Depends(require_permission(Perm.INVENTORY_WRITE))) -> dict:
    try:
        return await inventory_service.transfer(
            tenant_id=user["tenant_id"], material_id=payload.material_id,
            from_location_id=payload.from_location_id, to_location_id=payload.to_location_id,
            quantity=payload.quantity, actor_user_id=user["id"], reason=payload.reason,
            unit_of_measure=payload.unit_of_measure,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@inventory_router.post("/reservations", status_code=201)
async def do_reserve(payload: ReserveIn, user: dict = Depends(require_permission(Perm.INVENTORY_WRITE))) -> dict:
    try:
        return await inventory_service.reserve(
            tenant_id=user["tenant_id"], material_id=payload.material_id, location_id=payload.location_id,
            quantity=payload.quantity, source_entity_type=payload.source_entity_type,
            source_entity_id=payload.source_entity_id, actor_user_id=user["id"],
            allow_over_available=payload.allow_over_available,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@inventory_router.delete("/reservations/{rid}")
async def do_release(rid: str, user: dict = Depends(require_permission(Perm.INVENTORY_WRITE))) -> dict:
    try:
        return await inventory_service.release_reservation(
            tenant_id=user["tenant_id"], reservation_id=rid, actor_user_id=user["id"],
        )
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))
