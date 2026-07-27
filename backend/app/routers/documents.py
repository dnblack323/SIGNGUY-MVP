"""Shared documents/files system.

- One upload endpoint.
- One list/get endpoint.
- One download endpoint (all downloads authenticated + tenant-scoped).
- Attachments (polymorphic) link a file to multiple entities.

Both /api/files/{file_id}/download and /api/files/{file_id}/view require auth.
Storage keys are prefixed with tenant path; enforced server-side.
"""
from __future__ import annotations

import logging
from typing import Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..deps import require_permission
from ..models.file import Attachment, FileRecord
from ..services import storage
from ..services.audit import record_audit
from ..services.upload_validation import validate_upload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["documents"])

AttachmentParentType = Literal["customer", "quote", "order", "order_item", "work_order", "invoice", "email", "generic"]


class AttachmentIn(BaseModel):
    file_id: str
    parent_type: AttachmentParentType
    parent_id: str
    note: Optional[str] = None


class FileVisibilityIn(BaseModel):
    visibility: Literal["internal", "customer_visible"]


@router.post("/upload", status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    visibility: Literal["internal", "customer_visible"] = Form("internal"),
    parent_type: Optional[AttachmentParentType] = Form(None),
    parent_id: Optional[str] = Form(None),
    user: dict = Depends(require_permission(Perm.DOCUMENT_WRITE)),
) -> dict:
    data = await file.read()
    validated = validate_upload(filename=file.filename or "", content_type=file.content_type, data=data)

    # De-duplicate by (tenant_id, sha256) — if the exact bytes already exist, reuse the record.
    existing = await db.files.find_one({"tenant_id": user["tenant_id"], "sha256": validated.sha256, "archived": {"$ne": True}})
    if existing:
        file_record = FileRecord(**{**existing, **{"id": existing["id"]}})
    else:
        storage_key = storage.build_key(user["tenant_id"], validated.safe_filename)
        try:
            storage.put_bytes(storage_key, data, validated.mime_type)
        except Exception as e:
            logger.exception("Storage upload failed")
            raise HTTPException(status_code=502, detail=f"Storage upload failed: {e}")
        file_record = FileRecord(
            tenant_id=user["tenant_id"], storage_key=storage_key,
            original_filename=validated.safe_filename, mime_type=validated.mime_type, size_bytes=validated.size_bytes,
            uploaded_by=user["id"], visibility=visibility, sha256=validated.sha256,
        )
        await db.files.insert_one(prepare_for_mongo(file_record.model_dump()))
        await record_audit(
            tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
            action="file.upload", entity_type="file", entity_id=file_record.id,
            summary=f"Uploaded '{validated.safe_filename}' ({validated.size_bytes} bytes)",
            diff={"visibility": visibility, "mime": validated.mime_type},
        )

    attachment = None
    if parent_type and parent_id:
        # Verify parent belongs to tenant
        parent_coll = {
            "customer": "customers", "quote": "quotes", "order": "orders",
            "order_item": "order_items", "work_order": "work_orders",
            "invoice": "invoices", "email": "email_logs", "generic": None,
        }.get(parent_type)
        if parent_coll:
            parent_doc = await db[parent_coll].find_one({"id": parent_id, "tenant_id": user["tenant_id"]})
            if not parent_doc:
                raise HTTPException(status_code=404, detail="Parent record not found")
        att = Attachment(
            tenant_id=user["tenant_id"], file_id=file_record.id,
            parent_type=parent_type, parent_id=parent_id, attached_by=user["id"],
        )
        await db.attachments.insert_one(prepare_for_mongo(att.model_dump()))
        await record_audit(
            tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
            action="attachment.create", entity_type=parent_type, entity_id=parent_id,
            summary=f"Attached '{file_record.original_filename}' to {parent_type} {parent_id}",
            diff={"file_id": file_record.id, "attachment_id": att.id},
        )
        attachment = serialize_doc(att.model_dump())

    return {"file": serialize_doc(file_record.model_dump()), "attachment": attachment}


@router.get("")
async def list_files(
    parent_type: Optional[str] = Query(None),
    parent_id: Optional[str] = Query(None),
    visibility: Optional[str] = Query(None),
    limit: int = Query(100, le=500), skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.DOCUMENT_READ)),
) -> dict:
    tid = user["tenant_id"]
    if parent_type and parent_id:
        att_ids: list[str] = []
        async for a in db.attachments.find({"tenant_id": tid, "parent_type": parent_type, "parent_id": parent_id}, {"_id": 0}):
            att_ids.append(a["file_id"])
        q: dict = {"tenant_id": tid, "archived": {"$ne": True}, "id": {"$in": att_ids}}
    else:
        q = {"tenant_id": tid, "archived": {"$ne": True}}
        if visibility:
            q["visibility"] = visibility
    total = await db.files.count_documents(q)
    cursor = db.files.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    return {"items": [serialize_doc(d) async for d in cursor], "total": total, "limit": limit, "skip": skip}


@router.get("/{file_id}")
async def get_file(file_id: str, user: dict = Depends(require_permission(Perm.DOCUMENT_READ))) -> dict:
    doc = await db.files.find_one({"id": file_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="File not found")
    atts = [serialize_doc(a) async for a in db.attachments.find(
        {"tenant_id": user["tenant_id"], "file_id": file_id}, {"_id": 0}
    )]
    return {"file": serialize_doc(doc), "attachments": atts}


@router.patch("/{file_id}/visibility")
async def set_visibility(file_id: str, payload: FileVisibilityIn, user: dict = Depends(require_permission(Perm.DOCUMENT_WRITE))) -> dict:
    res = await db.files.update_one(
        {"id": file_id, "tenant_id": user["tenant_id"]},
        {"$set": {"visibility": payload.visibility, "updated_at": utc_now().isoformat()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="File not found")
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="file.visibility_change", entity_type="file", entity_id=file_id,
        summary=f"File visibility set to {payload.visibility}",
        diff={"visibility": payload.visibility},
    )
    doc = await db.files.find_one({"id": file_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    return serialize_doc(doc)


@router.delete("/{file_id}", status_code=204, response_class=Response)
async def archive_file(file_id: str, user: dict = Depends(require_permission(Perm.DOCUMENT_WRITE))) -> Response:
    res = await db.files.update_one(
        {"id": file_id, "tenant_id": user["tenant_id"]},
        {"$set": {"archived": True, "updated_at": utc_now().isoformat()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="File not found")
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="file.archive", entity_type="file", entity_id=file_id,
        summary="File archived",
    )
    return Response(status_code=204)


@router.get("/{file_id}/download")
async def download_file(file_id: str, user: dict = Depends(require_permission(Perm.DOCUMENT_READ))):
    doc = await db.files.find_one({"id": file_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not doc or doc.get("archived"):
        raise HTTPException(status_code=404, detail="File not found")
    # Extra defence-in-depth: enforce the storage key is under this tenant's path.
    if f"/tenants/{user['tenant_id']}/" not in doc["storage_key"]:
        raise HTTPException(status_code=403, detail="Storage path/tenant mismatch")
    try:
        data, ct = storage.get_bytes(doc["storage_key"])
    except Exception as e:
        logger.exception("Storage download failed")
        raise HTTPException(status_code=502, detail=f"Storage download failed: {e}")
    return Response(
        content=data,
        media_type=doc.get("mime_type") or ct,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(doc['original_filename'])}"},
    )


@router.get("/{file_id}/view")
async def view_file(file_id: str, user: dict = Depends(require_permission(Perm.DOCUMENT_READ))):
    doc = await db.files.find_one({"id": file_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not doc or doc.get("archived"):
        raise HTTPException(status_code=404, detail="File not found")
    if f"/tenants/{user['tenant_id']}/" not in doc["storage_key"]:
        raise HTTPException(status_code=403, detail="Storage path/tenant mismatch")
    try:
        data, ct = storage.get_bytes(doc["storage_key"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Storage download failed: {e}")
    return Response(content=data, media_type=doc.get("mime_type") or ct)


@router.post("/attach", status_code=201)
async def attach_existing(payload: AttachmentIn, user: dict = Depends(require_permission(Perm.DOCUMENT_WRITE))) -> dict:
    f = await db.files.find_one({"id": payload.file_id, "tenant_id": user["tenant_id"]})
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    parent_coll = {
        "customer": "customers", "quote": "quotes", "order": "orders",
        "order_item": "order_items", "work_order": "work_orders",
        "invoice": "invoices", "email": "email_logs", "generic": None,
    }.get(payload.parent_type)
    if parent_coll:
        parent_doc = await db[parent_coll].find_one({"id": payload.parent_id, "tenant_id": user["tenant_id"]})
        if not parent_doc:
            raise HTTPException(status_code=404, detail="Parent record not found")
    dup = await db.attachments.find_one({
        "tenant_id": user["tenant_id"], "file_id": payload.file_id,
        "parent_type": payload.parent_type, "parent_id": payload.parent_id,
    })
    if dup:
        return serialize_doc(dup)
    att = Attachment(
        tenant_id=user["tenant_id"], file_id=payload.file_id,
        parent_type=payload.parent_type, parent_id=payload.parent_id,
        attached_by=user["id"], note=payload.note,
    )
    await db.attachments.insert_one(prepare_for_mongo(att.model_dump()))
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="attachment.create", entity_type=payload.parent_type, entity_id=payload.parent_id,
        summary=f"Attached file to {payload.parent_type} {payload.parent_id}",
        diff={"file_id": payload.file_id, "attachment_id": att.id},
    )
    return serialize_doc(att.model_dump())


@router.delete("/attachments/{attachment_id}", status_code=204, response_class=Response)
async def detach(attachment_id: str, user: dict = Depends(require_permission(Perm.DOCUMENT_WRITE))) -> Response:
    att = await db.attachments.find_one({"id": attachment_id, "tenant_id": user["tenant_id"]})
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")
    await db.attachments.delete_one({"id": attachment_id})
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="attachment.delete", entity_type=att["parent_type"], entity_id=att["parent_id"],
        summary="Attachment removed", diff={"attachment_id": attachment_id, "file_id": att["file_id"]},
    )
    return Response(status_code=204)
