"""EC7 phase 7b — Vendors + VendorMaterials + supplier catalog seed router."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.config import get_settings
from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import serialize_doc, utc_now
from ..deps import require_permission
from ..models.vendor import Vendor, VendorMaterial
from ..services.supplier_connectors import TestSupplierAdapter, list_connectors

router = APIRouter(prefix="/vendors", tags=["vendors"])


class VendorIn(BaseModel):
    name: str
    display_name: Optional[str] = None
    connector_key: str = "manual"
    connector_tier: str = "manual"
    account_number: Optional[str] = None
    website: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    categories: list[str] = Field(default_factory=list)
    preferred: bool = False
    notes: Optional[str] = None


class VendorMaterialIn(BaseModel):
    vendor_id: str
    material_id: str
    supplier_product_id: str
    supplier_sku: Optional[str] = None
    preferred: bool = False


@router.get("")
async def list_vendors(active: Optional[bool] = True, q: Optional[str] = None,
                       user: dict = Depends(require_permission(Perm.VENDOR_READ))) -> dict:
    filt: dict = {"tenant_id": user["tenant_id"]}
    if active is not None:
        filt["active"] = active
    if q:
        filt["$or"] = [{"name": {"$regex": q, "$options": "i"}},
                       {"display_name": {"$regex": q, "$options": "i"}}]
    cur = db.vendors.find(filt, {"_id": 0}).sort("name", 1)
    return {"items": [serialize_doc(d) async for d in cur],
            "connectors": list_connectors()}


@router.post("", status_code=201)
async def create_vendor(payload: VendorIn,
                        user: dict = Depends(require_permission(Perm.VENDOR_WRITE))) -> dict:
    doc = Vendor(tenant_id=user["tenant_id"], **payload.model_dump()).model_dump()  # type: ignore[arg-type]
    await db.vendors.insert_one(doc)
    doc.pop("_id", None)
    return serialize_doc(doc)


# ----- Vendor <-> Material mapping -----
# NOTE: these fixed-path routes (`/materials`, `/seed/test-adapter`) MUST be
# registered before the dynamic `/{vid}` routes below — FastAPI matches
# routes in registration order, so `/{vid}` would otherwise shadow them
# (e.g. GET /vendors/materials would be interpreted as GET /vendors/{vid}
# with vid="materials").
@router.post("/materials", status_code=201, tags=["vendors"])
async def link_vendor_material(payload: VendorMaterialIn,
                                user: dict = Depends(require_permission(Perm.VENDOR_WRITE))) -> dict:
    doc = VendorMaterial(tenant_id=user["tenant_id"], **payload.model_dump()).model_dump()  # type: ignore[arg-type]
    await db.vendor_materials.update_one(
        {"tenant_id": user["tenant_id"], "vendor_id": payload.vendor_id,
         "material_id": payload.material_id,
         "supplier_product_id": payload.supplier_product_id},
        {"$set": doc}, upsert=True,
    )
    return serialize_doc(doc)


@router.get("/materials")
async def list_vendor_materials(material_id: Optional[str] = None,
                                 vendor_id: Optional[str] = None,
                                 user: dict = Depends(require_permission(Perm.VENDOR_READ))) -> dict:
    filt: dict = {"tenant_id": user["tenant_id"], "active": True}
    if material_id: filt["material_id"] = material_id
    if vendor_id: filt["vendor_id"] = vendor_id
    cur = db.vendor_materials.find(filt, {"_id": 0})
    return {"items": [serialize_doc(d) async for d in cur]}


# ----- Deterministic seed of the synthetic supplier catalog (dev/test only) -----
@router.post("/seed/test-adapter", status_code=201)
async def seed_test_adapter(reset: bool = Query(False),
                            user: dict = Depends(require_permission(Perm.VENDOR_WRITE))) -> dict:
    """Seed the deterministic synthetic supplier catalog for this tenant.

    LOCKED per master plan §12 — disabled in production.
    """
    settings = get_settings()
    if settings.env == "production":
        raise HTTPException(status_code=403, detail="Seeding is disabled in production")
    stats = await TestSupplierAdapter().seed_tenant(tenant_id=user["tenant_id"], reset=reset)
    return {"seeded": True, "reset": reset, **stats,
            "note": "SYNTHETIC DEMO DATA — NOT REAL SUPPLIER PRICING"}


@router.get("/{vid}")
async def get_vendor(vid: str,
                     user: dict = Depends(require_permission(Perm.VENDOR_READ))) -> dict:
    doc = await db.vendors.find_one({"id": vid, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Vendor not found")
    warehouses = [serialize_doc(w) async for w in db.supplier_warehouses.find(
        {"tenant_id": user["tenant_id"], "vendor_id": vid}, {"_id": 0}
    )]
    return {"vendor": serialize_doc(doc), "warehouses": warehouses}


@router.patch("/{vid}")
async def update_vendor(vid: str, payload: VendorIn,
                        user: dict = Depends(require_permission(Perm.VENDOR_WRITE))) -> dict:
    upd = {k: v for k, v in payload.model_dump().items() if v is not None}
    upd["updated_at"] = utc_now().isoformat()
    res = await db.vendors.update_one({"id": vid, "tenant_id": user["tenant_id"]}, {"$set": upd})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Vendor not found")
    doc = await db.vendors.find_one({"id": vid}, {"_id": 0})
    return serialize_doc(doc or {})


@router.post("/{vid}/archive")
async def archive_vendor(vid: str,
                         user: dict = Depends(require_permission(Perm.VENDOR_WRITE))) -> dict:
    res = await db.vendors.update_one({"id": vid, "tenant_id": user["tenant_id"]},
                                       {"$set": {"active": False, "updated_at": utc_now().isoformat()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return {"archived": True}
