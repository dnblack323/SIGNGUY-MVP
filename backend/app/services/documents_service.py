"""EC6 — Documents / Asset Library service."""
from __future__ import annotations
from typing import Optional

from ..core.db import db
from ..core.time_utils import serialize_doc, utc_now
from ..models.document import Document, DocumentVersion


async def create_document(
    *, tenant_id: str, title: str, file_id: Optional[str],
    category: str = "general", source_type: str = "upload",
    requires_review: bool = False, description: Optional[str] = None,
    tags: Optional[list[str]] = None, visibility: str = "internal",
    customer_id: Optional[str] = None, created_by: Optional[str] = None,
) -> dict:
    doc = Document(
        tenant_id=tenant_id, title=title,
        category=category,  # type: ignore[arg-type]
        source_type=source_type,  # type: ignore[arg-type]
        requires_review=requires_review, current_file_id=file_id, version=1,
        description=description, tags=tags or [],
        visibility=visibility,  # type: ignore[arg-type]
        customer_id=customer_id, created_by=created_by,
    ).model_dump()
    await db.documents.insert_one(doc)
    if file_id:
        ver = DocumentVersion(
            tenant_id=tenant_id, document_id=doc["id"], version=1, file_id=file_id,
            created_by=created_by,
        ).model_dump()
        await db.document_versions.insert_one(ver)
    doc.pop("_id", None)
    return serialize_doc(doc)


async def add_document_version(
    *, tenant_id: str, document_id: str, file_id: str,
    notes: Optional[str] = None, created_by: Optional[str] = None,
) -> dict:
    doc = await db.documents.find_one({"id": document_id, "tenant_id": tenant_id})
    if not doc:
        raise ValueError("document_not_found")
    new_version = int(doc.get("version", 1)) + 1
    ver = DocumentVersion(
        tenant_id=tenant_id, document_id=document_id, version=new_version,
        file_id=file_id, notes=notes, created_by=created_by,
    ).model_dump()
    await db.document_versions.insert_one(ver)
    await db.documents.update_one(
        {"id": document_id, "tenant_id": tenant_id},
        {"$set": {"version": new_version, "current_file_id": file_id,
                  "updated_at": utc_now().isoformat()}},
    )
    doc = await db.documents.find_one({"id": document_id}, {"_id": 0})
    return serialize_doc(doc or {})
