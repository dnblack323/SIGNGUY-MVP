from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, EmailStr, Field

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..deps import require_permission
from ..models.customer import Customer
from ..services.audit import record_audit

router = APIRouter(prefix="/customers", tags=["customers"])


class CustomerIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    company: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    notes: Optional[str] = None


class CustomerUpdateIn(CustomerIn):
    name: Optional[str] = None  # type: ignore[assignment]


@router.get("")
async def list_customers(
    search: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.CUSTOMER_READ)),
) -> dict:
    q: dict = {"tenant_id": user["tenant_id"], "archived": {"$ne": True}}
    if search:
        q["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"company": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
        ]
    total = await db.customers.count_documents(q)
    cursor = db.customers.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    items = [serialize_doc(doc) async for doc in cursor]
    return {"items": items, "total": total, "limit": limit, "skip": skip}


@router.post("", status_code=201)
async def create_customer(payload: CustomerIn, user: dict = Depends(require_permission(Perm.CUSTOMER_WRITE))) -> dict:
    c = Customer(tenant_id=user["tenant_id"], **payload.model_dump(exclude_none=True))
    await db.customers.insert_one(prepare_for_mongo(c.model_dump()))
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="customer.create", entity_type="customer", entity_id=c.id,
        summary=f"Customer '{c.name}' created",
    )
    return serialize_doc(c.model_dump())


@router.get("/{customer_id}")
async def get_customer(customer_id: str, user: dict = Depends(require_permission(Perm.CUSTOMER_READ))) -> dict:
    doc = await db.customers.find_one({"id": customer_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Customer not found")
    return serialize_doc(doc)


@router.patch("/{customer_id}")
async def update_customer(customer_id: str, payload: CustomerUpdateIn, user: dict = Depends(require_permission(Perm.CUSTOMER_WRITE))) -> dict:
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    updates["updated_at"] = utc_now().isoformat()
    res = await db.customers.update_one({"id": customer_id, "tenant_id": user["tenant_id"]}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Customer not found")
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="customer.update", entity_type="customer", entity_id=customer_id,
        summary=f"Updated customer {customer_id}", diff={"changes": updates},
    )
    doc = await db.customers.find_one({"id": customer_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    return serialize_doc(doc)


@router.delete("/{customer_id}", status_code=204, response_class=Response)
async def archive_customer(customer_id: str, user: dict = Depends(require_permission(Perm.CUSTOMER_WRITE))) -> Response:
    res = await db.customers.update_one(
        {"id": customer_id, "tenant_id": user["tenant_id"]}, {"$set": {"archived": True, "updated_at": utc_now().isoformat()}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Customer not found")
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="customer.archive", entity_type="customer", entity_id=customer_id,
        summary=f"Archived customer {customer_id}",
    )
    return Response(status_code=204)


@router.get("/{customer_id}/related")
async def customer_related(customer_id: str, user: dict = Depends(require_permission(Perm.CUSTOMER_READ))) -> dict:
    """Return quotes/orders/work-orders/invoices/documents/emails linked to this customer."""
    doc = await db.customers.find_one({"id": customer_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Customer not found")
    tid = user["tenant_id"]
    async def _all(coll, q):
        return [serialize_doc(d) async for d in db[coll].find(q, {"_id": 0}).sort("created_at", -1).limit(200)]
    return {
        "quotes": await _all("quotes", {"tenant_id": tid, "customer_id": customer_id}),
        "orders": await _all("orders", {"tenant_id": tid, "customer_id": customer_id}),
        "work_orders": await _all("work_orders", {"tenant_id": tid, "customer_id": customer_id}),
        "invoices": await _all("invoices", {"tenant_id": tid, "customer_id": customer_id}),
        "emails": await _all("email_logs", {"tenant_id": tid, "customer_id": customer_id}),
    }
