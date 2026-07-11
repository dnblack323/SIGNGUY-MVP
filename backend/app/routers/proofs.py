"""EC6 — Staff Proofs router."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import serialize_doc
from ..deps import require_permission
from ..services.proofs_service import (
    create_proof, add_proof_version, transition_proof, ALLOWED_TRANSITIONS,
)

router = APIRouter(prefix="/proofs", tags=["proofs"])


class ProofCreateIn(BaseModel):
    parent_type: str
    parent_id: str
    title: str
    description: Optional[str] = None
    file_id: Optional[str] = None
    document_id: Optional[str] = None
    customer_id: Optional[str] = None


class ProofVersionIn(BaseModel):
    file_id: str
    document_id: Optional[str] = None
    notes: Optional[str] = None


class ProofTransitionIn(BaseModel):
    target: str
    reason: Optional[str] = None


@router.get("")
async def list_proofs(
    parent_type: Optional[str] = Query(None),
    parent_id: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, le=500), skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.DOCUMENT_READ)),
) -> dict:
    q: dict = {"tenant_id": user["tenant_id"]}
    if parent_type: q["parent_type"] = parent_type
    if parent_id: q["parent_id"] = parent_id
    if customer_id: q["customer_id"] = customer_id
    if status: q["status"] = status
    total = await db.proofs.count_documents(q)
    cur = db.proofs.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    return {"items": [serialize_doc(d) async for d in cur], "total": total, "limit": limit, "skip": skip}


@router.post("", status_code=201)
async def create(payload: ProofCreateIn, user: dict = Depends(require_permission(Perm.DOCUMENT_WRITE))) -> dict:
    return await create_proof(
        tenant_id=user["tenant_id"], parent_type=payload.parent_type,
        parent_id=payload.parent_id, title=payload.title,
        description=payload.description, file_id=payload.file_id,
        document_id=payload.document_id, customer_id=payload.customer_id,
        created_by=user["id"], actor_email=user["email"],
    )


@router.get("/{pid}")
async def get_proof(pid: str, user: dict = Depends(require_permission(Perm.DOCUMENT_READ))) -> dict:
    d = await db.proofs.find_one({"id": pid, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Proof not found")
    versions = [serialize_doc(v) async for v in db.proof_versions.find(
        {"tenant_id": user["tenant_id"], "proof_id": pid}, {"_id": 0}
    ).sort("version", -1)]
    return {"proof": serialize_doc(d), "versions": versions}


@router.post("/{pid}/versions", status_code=201)
async def add_version(pid: str, payload: ProofVersionIn, user: dict = Depends(require_permission(Perm.DOCUMENT_WRITE))) -> dict:
    try:
        return await add_proof_version(
            tenant_id=user["tenant_id"], proof_id=pid, file_id=payload.file_id,
            document_id=payload.document_id, notes=payload.notes,
            created_by=user["id"], actor_email=user["email"],
        )
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@router.post("/{pid}/transition")
async def transition(pid: str, payload: ProofTransitionIn, user: dict = Depends(require_permission(Perm.DOCUMENT_WRITE))) -> dict:
    try:
        return await transition_proof(
            tenant_id=user["tenant_id"], proof_id=pid, target=payload.target,
            reason=payload.reason, actor_user_id=user["id"], actor_email=user["email"],
        )
    except ValueError as ex:
        msg = str(ex)
        if msg.startswith("invalid_transition:"):
            raise HTTPException(status_code=400, detail=f"Invalid transition ({msg.split(':',1)[1]})")
        if msg == "reason_required":
            raise HTTPException(status_code=400, detail="Reason required")
        raise HTTPException(status_code=404, detail=msg)
