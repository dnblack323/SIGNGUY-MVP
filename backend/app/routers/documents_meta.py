"""EC6 — Documents metadata + share-token routes (staff)."""
from __future__ import annotations
from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import serialize_doc, utc_now
from ..deps import require_permission
from ..services.documents_service import create_document, add_document_version
from ..services.portal_tokens import mint_public_action_token, revoke_public_action_token
from ..services.audit import record_audit

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentCreateIn(BaseModel):
    title: str
    file_id: Optional[str] = None
    category: str = "general"
    source_type: str = "upload"
    requires_review: bool = False
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    visibility: str = "internal"
    customer_id: Optional[str] = None


class DocumentPatchIn(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    visibility: Optional[str] = None
    tags: Optional[list[str]] = None
    archived: Optional[bool] = None


class DocumentVersionIn(BaseModel):
    file_id: str
    notes: Optional[str] = None


class ShareMintIn(BaseModel):
    action: str = Field(pattern=r"^(quote_view|invoice_view|invoice_pay|proof_approve|sign|customer_intake)$")
    parent_type: str
    parent_id: str
    parent_version: Optional[int] = None
    audience_email: Optional[str] = None
    ttl_hours: int = 72
    single_use: Optional[bool] = None  # inferred by action if omitted


@router.post("", status_code=201)
async def create_doc(payload: DocumentCreateIn, user: dict = Depends(require_permission(Perm.DOCUMENT_WRITE))) -> dict:
    return await create_document(
        tenant_id=user["tenant_id"], title=payload.title, file_id=payload.file_id,
        category=payload.category, source_type=payload.source_type,
        requires_review=payload.requires_review, description=payload.description,
        tags=payload.tags, visibility=payload.visibility,
        customer_id=payload.customer_id, created_by=user["id"],
    )


@router.get("")
async def list_docs(
    category: Optional[str] = Query(None), customer_id: Optional[str] = Query(None),
    visibility: Optional[str] = Query(None),
    limit: int = Query(100, le=500), skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.DOCUMENT_READ)),
) -> dict:
    q: dict = {"tenant_id": user["tenant_id"], "archived": False}
    if category: q["category"] = category
    if customer_id: q["customer_id"] = customer_id
    if visibility: q["visibility"] = visibility
    total = await db.documents.count_documents(q)
    cur = db.documents.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    return {"items": [serialize_doc(d) async for d in cur], "total": total, "limit": limit, "skip": skip}


@router.get("/{doc_id}")
async def get_doc(doc_id: str, user: dict = Depends(require_permission(Perm.DOCUMENT_READ))) -> dict:
    d = await db.documents.find_one({"id": doc_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    versions = [serialize_doc(v) async for v in db.document_versions.find(
        {"tenant_id": user["tenant_id"], "document_id": doc_id}, {"_id": 0}
    ).sort("version", -1)]
    return {"document": serialize_doc(d), "versions": versions}


@router.patch("/{doc_id}")
async def patch_doc(doc_id: str, payload: DocumentPatchIn, user: dict = Depends(require_permission(Perm.DOCUMENT_WRITE))) -> dict:
    upd = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if not upd:
        raise HTTPException(status_code=400, detail="No updates")
    upd["updated_at"] = utc_now().isoformat()
    res = await db.documents.update_one({"id": doc_id, "tenant_id": user["tenant_id"]}, {"$set": upd})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    d = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    return serialize_doc(d or {})


@router.post("/{doc_id}/versions", status_code=201)
async def add_version(doc_id: str, payload: DocumentVersionIn, user: dict = Depends(require_permission(Perm.DOCUMENT_WRITE))) -> dict:
    try:
        return await add_document_version(
            tenant_id=user["tenant_id"], document_id=doc_id,
            file_id=payload.file_id, notes=payload.notes, created_by=user["id"],
        )
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@router.post("/{doc_id}/share", status_code=201)
async def mint_share(
    doc_id: str, payload: ShareMintIn, request: Request,
    user: dict = Depends(require_permission(Perm.DOCUMENT_SHARE)),
) -> dict:
    # Ensure the document exists in-tenant
    d = await db.documents.find_one({"id": doc_id, "tenant_id": user["tenant_id"]})
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    # Multi-view actions allow multi-use tokens; write actions are single-use
    single = True if payload.single_use is None else bool(payload.single_use)
    if payload.action in {"quote_view", "invoice_view"} and payload.single_use is None:
        single = False
    raw, token_doc = await mint_public_action_token(
        tenant_id=user["tenant_id"], action=payload.action,
        parent_type=payload.parent_type, parent_id=payload.parent_id,
        parent_version=payload.parent_version,
        audience_email=payload.audience_email,
        ttl_hours=payload.ttl_hours, single_use=single, issued_by=user["id"],
        ip_issued=(request.client.host if request.client else None),
    )
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="document.share_token_mint", entity_type="document", entity_id=doc_id,
        summary=f"Share token minted ({payload.action})",
        diff={"action": payload.action, "audience_email": payload.audience_email},
    )
    token_doc.pop("token_hash", None)  # never echo hash either
    return {"token": raw, "record": serialize_doc(token_doc)}


@router.delete("/share-tokens/{token_id}", status_code=204)
async def revoke_share(token_id: str, user: dict = Depends(require_permission(Perm.DOCUMENT_SHARE))):
    await revoke_public_action_token(token_id, user["tenant_id"])
    from fastapi import Response
    return Response(status_code=204)
