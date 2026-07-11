"""EC6 — Staff signatures + approvals router."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import serialize_doc
from ..deps import require_permission
from ..services.approvals_signatures_service import (
    create_signature_request, record_signature, record_approval, ALLOWED_APPROVAL_PARENTS,
)

router = APIRouter(prefix="/signatures", tags=["signatures"])
approvals_router = APIRouter(prefix="/approvals", tags=["approvals"])


class SignatureRequestIn(BaseModel):
    parent_type: str
    parent_id: str
    title: str
    required_signers: list[dict]     # [{name, email, role?}]
    parent_version: Optional[int] = None
    description: Optional[str] = None


class ApprovalIn(BaseModel):
    parent_type: str
    parent_id: str
    action: str    # approve | request_changes | decline
    parent_version: Optional[int] = None
    reason: Optional[str] = None


@router.get("/requests")
async def list_requests(
    parent_type: Optional[str] = Query(None), parent_id: Optional[str] = Query(None),
    limit: int = Query(100, le=500), skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.DOCUMENT_READ)),
) -> dict:
    q: dict = {"tenant_id": user["tenant_id"]}
    if parent_type: q["parent_type"] = parent_type
    if parent_id: q["parent_id"] = parent_id
    total = await db.signature_requests.count_documents(q)
    cur = db.signature_requests.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    return {"items": [serialize_doc(d) async for d in cur], "total": total}


@router.post("/requests", status_code=201)
async def create_request(payload: SignatureRequestIn, user: dict = Depends(require_permission(Perm.DOCUMENT_WRITE))) -> dict:
    try:
        return await create_signature_request(
            tenant_id=user["tenant_id"], parent_type=payload.parent_type,
            parent_id=payload.parent_id, title=payload.title,
            required_signers=payload.required_signers,
            parent_version=payload.parent_version,
            description=payload.description, created_by=user["id"], actor_email=user["email"],
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@router.get("/requests/{rid}")
async def get_request(rid: str, user: dict = Depends(require_permission(Perm.DOCUMENT_READ))) -> dict:
    d = await db.signature_requests.find_one({"id": rid, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Signature request not found")
    sigs = [serialize_doc(s) async for s in db.signatures.find(
        {"tenant_id": user["tenant_id"], "request_id": rid}, {"_id": 0}
    ).sort("created_at", 1)]
    return {"request": serialize_doc(d), "signatures": sigs}


# ---- Approvals ----

@approvals_router.get("")
async def list_approvals(
    parent_type: Optional[str] = Query(None), parent_id: Optional[str] = Query(None),
    limit: int = Query(100, le=500), skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.DOCUMENT_READ)),
) -> dict:
    q: dict = {"tenant_id": user["tenant_id"]}
    if parent_type: q["parent_type"] = parent_type
    if parent_id: q["parent_id"] = parent_id
    total = await db.approvals.count_documents(q)
    cur = db.approvals.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    return {"items": [serialize_doc(d) async for d in cur], "total": total}


@approvals_router.post("", status_code=201)
async def create_approval(payload: ApprovalIn, user: dict = Depends(require_permission(Perm.DOCUMENT_WRITE))) -> dict:
    try:
        return await record_approval(
            tenant_id=user["tenant_id"], parent_type=payload.parent_type,
            parent_id=payload.parent_id, action=payload.action,
            actor_type="staff", actor_ref=user["id"], actor_display=user["email"],
            parent_version=payload.parent_version, reason=payload.reason,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
