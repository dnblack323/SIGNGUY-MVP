from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, EmailStr, Field

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..deps import require_permission
from ..models.customer import Customer, CustomerAddress, CustomerContact, CustomerLifecycleStatus, CustomerType
from ..services.customer_service import (
    duplicate_candidates,
    merge_customers,
    mongo_customer_payload,
    related_records,
    serialize_customer,
)
from ..services.audit import record_audit
from ..services.sequence import next_record_number

router = APIRouter(prefix="/customers", tags=["customers"])


class CustomerIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    company: Optional[str] = None
    customer_type: CustomerType = "business"
    lifecycle_status: CustomerLifecycleStatus = "active"
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    contacts: list[CustomerContact] = Field(default_factory=list)
    addresses: list[CustomerAddress] = Field(default_factory=list)
    notes: Optional[str] = None


class CustomerUpdateIn(CustomerIn):
    name: Optional[str] = None  # type: ignore[assignment]
    customer_type: Optional[CustomerType] = None  # type: ignore[assignment]
    lifecycle_status: Optional[CustomerLifecycleStatus] = None  # type: ignore[assignment]
    contacts: Optional[list[CustomerContact]] = None  # type: ignore[assignment]
    addresses: Optional[list[CustomerAddress]] = None  # type: ignore[assignment]


class CustomerArchiveIn(BaseModel):
    reason: Optional[str] = None


class CustomerMergeIn(BaseModel):
    source_customer_id: str
    surviving_customer_id: str
    confirmation: str


@router.get("")
async def list_customers(
    search: Optional[str] = Query(None),
    status: Literal["active", "archived", "all"] = Query("active"),
    limit: int = Query(50, le=200),
    skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.CUSTOMER_READ)),
) -> dict:
    q: dict = {"tenant_id": user["tenant_id"]}
    clauses: list[dict] = []
    if status == "active":
        q["archived"] = {"$ne": True}
        q["merged_into"] = {"$exists": False}
    elif status == "archived":
        clauses.append({"$or": [{"archived": True}, {"merged_into": {"$exists": True}}]})
    if search:
        clauses.append({"$or": [
            {"name": {"$regex": search, "$options": "i"}},
            {"company": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}},
            {"contacts.name": {"$regex": search, "$options": "i"}},
            {"contacts.email": {"$regex": search, "$options": "i"}},
            {"contacts.phone": {"$regex": search, "$options": "i"}},
            {"addresses.line1": {"$regex": search, "$options": "i"}},
            {"addresses.city": {"$regex": search, "$options": "i"}},
        ]})
    if clauses:
        q["$and"] = clauses
    total = await db.customers.count_documents(q)
    cursor = db.customers.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    items = [serialize_customer(doc) async for doc in cursor]
    return {"items": items, "total": total, "limit": limit, "skip": skip}


@router.post("", status_code=201)
async def create_customer(payload: CustomerIn, user: dict = Depends(require_permission(Perm.CUSTOMER_WRITE))) -> dict:
    raw = payload.model_dump(exclude_none=True)
    normalized = mongo_customer_payload({"tenant_id": user["tenant_id"], **raw})
    c = Customer(**normalized)
    allocation = await next_record_number(
        tenant_id=user["tenant_id"],
        record_type="customer",
        issued_to_entity_type="customer",
        issued_to_entity_id=c.id,
        actor_user_id=user["id"],
        actor_email=user["email"],
        reason="customer.create",
    )
    c.number = allocation.number
    await db.customers.insert_one(prepare_for_mongo(c.model_dump()))
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="customer.create", entity_type="customer", entity_id=c.id,
        summary=f"Customer '{c.name}' created",
        diff={"customer_type": c.customer_type, "lifecycle_status": c.lifecycle_status},
    )
    return serialize_customer(c.model_dump())


@router.get("/duplicates")
async def list_duplicate_candidates(
    customer_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    user: dict = Depends(require_permission(Perm.CUSTOMER_READ)),
) -> dict:
    items = await duplicate_candidates(tenant_id=user["tenant_id"], customer_id=customer_id, search=search)
    return {"items": items, "total": len(items)}


@router.post("/merge")
async def merge_customer_records(payload: CustomerMergeIn, user: dict = Depends(require_permission(Perm.CUSTOMER_WRITE))) -> dict:
    return await merge_customers(
        tenant_id=user["tenant_id"],
        actor_user_id=user["id"],
        actor_email=user["email"],
        source_customer_id=payload.source_customer_id,
        surviving_customer_id=payload.surviving_customer_id,
        confirmation=payload.confirmation,
    )


@router.get("/{customer_id}")
async def get_customer(customer_id: str, user: dict = Depends(require_permission(Perm.CUSTOMER_READ))) -> dict:
    doc = await db.customers.find_one({"id": customer_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Customer not found")
    return serialize_customer(doc)


@router.patch("/{customer_id}")
async def update_customer(customer_id: str, payload: CustomerUpdateIn, user: dict = Depends(require_permission(Perm.CUSTOMER_WRITE))) -> dict:
    existing = await db.customers.find_one({"id": customer_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Customer not found")
    updates = {k: v for k, v in payload.model_dump(exclude_unset=True, exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    updates = mongo_customer_payload(updates, existing)
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
    return serialize_customer(doc)


@router.delete("/{customer_id}", status_code=204, response_class=Response)
async def archive_customer(customer_id: str, user: dict = Depends(require_permission(Perm.CUSTOMER_WRITE))) -> Response:
    await _archive_customer(customer_id, CustomerArchiveIn(), user)
    return Response(status_code=204)


@router.post("/{customer_id}/archive")
async def archive_customer_post(customer_id: str, payload: CustomerArchiveIn, user: dict = Depends(require_permission(Perm.CUSTOMER_WRITE))) -> dict:
    return await _archive_customer(customer_id, payload, user)


async def _archive_customer(customer_id: str, payload: CustomerArchiveIn, user: dict) -> dict:
    existing = await db.customers.find_one({"id": customer_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Customer not found")
    if existing.get("merged_into"):
        raise HTTPException(status_code=400, detail="Merged customer records are already archived")
    now = utc_now().isoformat()
    res = await db.customers.update_one(
        {"id": customer_id, "tenant_id": user["tenant_id"]},
        {"$set": {"archived": True, "archived_at": now, "archived_reason": payload.reason, "lifecycle_status": "archived", "updated_at": now}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Customer not found")
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="customer.archive", entity_type="customer", entity_id=customer_id,
        summary=f"Archived customer {customer_id}",
        diff={"reason": payload.reason},
    )
    doc = await db.customers.find_one({"id": customer_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    return serialize_customer(doc)


@router.post("/{customer_id}/restore")
async def restore_customer(customer_id: str, user: dict = Depends(require_permission(Perm.CUSTOMER_WRITE))) -> dict:
    existing = await db.customers.find_one({"id": customer_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Customer not found")
    if existing.get("merged_into"):
        raise HTTPException(status_code=400, detail="Merged customer records cannot be restored; open the surviving customer instead")
    now = utc_now().isoformat()
    await db.customers.update_one(
        {"id": customer_id, "tenant_id": user["tenant_id"]},
        {"$set": {"archived": False, "archived_at": None, "archived_reason": None, "lifecycle_status": "active", "updated_at": now}},
    )
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="customer.restore", entity_type="customer", entity_id=customer_id,
        summary=f"Restored customer {customer_id}",
    )
    doc = await db.customers.find_one({"id": customer_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    return serialize_customer(doc)


@router.get("/{customer_id}/related")
async def customer_related(customer_id: str, user: dict = Depends(require_permission(Perm.CUSTOMER_READ))) -> dict:
    """Return authoritative records linked to this customer without copying them."""
    return await related_records(tenant_id=user["tenant_id"], customer_id=customer_id)
