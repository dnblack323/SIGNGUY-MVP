"""EC6 — Documents / Asset Library service."""
from __future__ import annotations
from typing import Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.document import Document, DocumentVersion
from ..models.document_link import DocumentLink


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


# ---- Generic cross-entity document linking (EC2 `DocumentLink`, first wired
# up in EC8 phase 8e for Equipment/Training — reused as-is, no new
# file-storage or document-library system). ----

async def link_document(
    *, tenant_id: str, document_id: str, entity_type: str, entity_id: str,
    portal_visible: bool = False, created_by: Optional[str] = None,
) -> dict:
    doc = await db.documents.find_one({"id": document_id, "tenant_id": tenant_id}, {"_id": 0, "id": 1})
    if not doc:
        raise ValueError("document_not_found")
    existing = await db.document_links.find_one(
        {"tenant_id": tenant_id, "document_id": document_id, "entity_type": entity_type, "entity_id": entity_id},
        {"_id": 0},
    )
    if existing:
        return serialize_doc(existing)
    link = DocumentLink(
        tenant_id=tenant_id, document_id=document_id, entity_type=entity_type,
        entity_id=entity_id, portal_visible=portal_visible, created_by=created_by,
    ).model_dump()
    await db.document_links.insert_one(prepare_for_mongo(dict(link)))
    return serialize_doc(link)


async def unlink_document(*, tenant_id: str, link_id: str) -> bool:
    res = await db.document_links.delete_one({"id": link_id, "tenant_id": tenant_id})
    return res.deleted_count > 0


async def list_linked_documents(
    *, tenant_id: str, entity_type: str, entity_id: str, portal_visible_only: bool = False,
) -> list[dict]:
    q: dict = {"tenant_id": tenant_id, "entity_type": entity_type, "entity_id": entity_id}
    if portal_visible_only:
        q["portal_visible"] = True
    links = [serialize_doc(l) async for l in db.document_links.find(q, {"_id": 0})]
    if not links:
        return []
    doc_ids = [l["document_id"] for l in links]
    docs = {d["id"]: serialize_doc(d) async for d in db.documents.find({"tenant_id": tenant_id, "id": {"$in": doc_ids}}, {"_id": 0})}
    out = []
    for l in links:
        d = docs.get(l["document_id"])
        if d:
            out.append({**d, "link_id": l["id"], "portal_visible": l.get("portal_visible", False)})
    return out
