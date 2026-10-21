"""Setup file validation, storage, listing, preview, download, and removal."""
from __future__ import annotations

import hashlib

from ..models.file import FileRecord
from ..models.file_link import FileLink
from .webstore_setup_common import *
from .webstore_setup_portal_scope import _owner_store


SETUP_FILE_PARENT = "webstore"


def _extension(filename: str) -> str:
    return Path(filename or "").suffix.lower().lstrip(".")


def _looks_like(content: bytes, ext: str) -> bool:
    head = content[:256].lstrip()
    if ext in {"jpg", "jpeg"}:
        return content.startswith(b"\xff\xd8")
    if ext == "png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == "webp":
        return content.startswith(b"RIFF") and b"WEBP" in content[:16]
    if ext == "pdf":
        return content.startswith(b"%PDF")
    if ext == "svg":
        lower = head.lower()
        return lower.startswith(b"<svg") or (lower.startswith(b"<?xml") and b"<svg" in lower[:512])
    if ext in DOWNLOAD_ONLY_EXTENSIONS:
        return True
    return False


def _detect_content_type(filename: str, provided: Optional[str]) -> str:
    guessed = mimetypes.guess_type(filename)[0]
    return guessed or provided or "application/octet-stream"


def _safe_file_record(doc: dict, *, staff: bool = False) -> dict:
    allowed = {
        "id",
        "webstore_id",
        "category",
        "file_name",
        "extension",
        "content_type",
        "detected_content_type",
        "size_bytes",
        "uploaded_by_actor_type",
        "status",
        "version",
        "replaces_file_id",
        "replaced_by_file_id",
        "safe_preview_available",
        "inline_preview_allowed",
        "private_download_only",
        "svg_sanitized",
        "notes",
        "created_at",
        "updated_at",
    }
    if staff:
        allowed.add("uploaded_by_id")
    result = {k: v for k, v in doc.items() if k in allowed}
    if staff and doc.get("status") == "active" and doc.get("safe_preview_available") and doc.get("inline_preview_allowed"):
        result["preview_url"] = f"/api/webstores/{doc['webstore_id']}/setup-files/{doc['id']}/preview"
    return result


def _svg_is_safe(data: bytes) -> bool:
    lower = data[:200_000].lower()
    blocked = [b"<script", b"javascript:", b" onload=", b" onerror=", b"<foreignobject", b"http://", b"https://", b"xlink:href="]
    return not any(marker in lower for marker in blocked)


async def store_setup_file(
    *,
    tenant_id: str,
    webstore_id: str,
    actor_type: str,
    actor_id: Optional[str],
    filename: str,
    content_type: Optional[str],
    data: bytes,
    category: str,
    notes: Optional[str] = None,
    replaces_file_id: Optional[str] = None,
) -> dict:
    await _get_store(tenant_id, webstore_id)
    if not data:
        raise WebstoreSetupError("file_empty", "File is empty", 400)
    if len(data) > MAX_SETUP_FILE_BYTES:
        raise WebstoreSetupError("file_too_large", "Setup files must be 50 MB or smaller", 413)
    ext = _extension(filename)
    if ext in BLOCKED_EXTENSIONS or ext not in SAFE_EXTENSIONS:
        raise WebstoreSetupError("file_type_not_allowed", "That setup file type is not allowed", 400)
    if not _looks_like(data, ext):
        raise WebstoreSetupError("file_content_mismatch", "File content does not match the allowed file type", 400)
    detected = _detect_content_type(filename, content_type)
    if ext == "svg" and not _svg_is_safe(data):
        raise WebstoreSetupError("unsafe_svg_not_allowed", "SVG setup files cannot contain scripts, remote references, or unsafe inline markup", 400)
    svg_safe = ext == "svg"
    inline = ext in {"png", "jpg", "jpeg", "webp", "pdf"} or svg_safe
    version = 1
    if replaces_file_id:
        previous = await _find_setup_file(tenant_id, webstore_id, replaces_file_id)
        if not previous or previous.get("legacy"):
            raise WebstoreSetupError("setup_file_not_found", "Setup file to replace was not found", 404)
        version = int(previous.get("version") or 1) + 1
    # Canonical storage: one FileRecord in `files` + a FileLink to the Webstore (P2-9).
    key = storage.build_key(tenant_id, filename)
    storage.put_bytes(key, data, detected)
    record = FileRecord(
        tenant_id=tenant_id, storage_key=key, original_filename=filename, mime_type=detected,
        size_bytes=len(data), uploaded_by=actor_id or actor_type, visibility="customer_visible",
        sha256=hashlib.sha256(data).hexdigest(),
    ).model_dump()
    await db.files.insert_one(prepare_for_mongo(record))
    link = FileLink(
        tenant_id=tenant_id, file_id=record["id"], parent_type=SETUP_FILE_PARENT, parent_id=webstore_id,
        role=_clean_text(category, "category", limit=80), created_by=actor_id,
        metadata={
            "extension": ext, "content_type": content_type or detected, "uploaded_by_actor_type": actor_type,
            "status": "active", "version": version, "replaces_file_id": replaces_file_id,
            "safe_preview_available": inline, "inline_preview_allowed": inline, "private_download_only": not inline,
            "svg_sanitized": svg_safe, "notes": notes,
        },
    ).model_dump()
    await db.file_links.insert_one(prepare_for_mongo(link))
    if replaces_file_id:
        await db.file_links.update_one(
            {"tenant_id": tenant_id, "id": replaces_file_id},
            {"$set": {"archived": True, "metadata.status": "replaced", "metadata.replaced_by_file_id": link["id"], "updated_at": _now_iso()}},
        )
    await _audit(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action="webstore.setup_file_uploaded" if not replaces_file_id else "webstore.setup_file_replaced",
        entity_type="file_link",
        entity_id=link["id"],
        summary="Webstore setup file uploaded" if not replaces_file_id else "Webstore setup file replaced",
        metadata={"category": category, "extension": ext, "size_bytes": len(data), "version": version, "file_id": record["id"]},
    )
    return _safe_file_record(_link_view(link, record), staff=actor_type == "staff")


def _link_view(link: dict, record: dict) -> dict:
    """A FileLink + FileRecord in the setup-file shape the UI already uses."""
    meta = link.get("metadata") or {}
    return {
        **meta,
        "id": link["id"],
        "file_id": link["file_id"],
        "webstore_id": link["parent_id"],
        "category": link.get("role"),
        "file_name": record.get("original_filename"),
        "detected_content_type": record.get("mime_type"),
        "size_bytes": record.get("size_bytes"),
        "storage_key": record.get("storage_key"),
        "uploaded_by_id": link.get("created_by"),
        "status": meta.get("status") or ("removed" if link.get("archived") else "active"),
        "created_at": link.get("created_at"),
        "updated_at": link.get("updated_at"),
    }


async def _setup_file_docs(tenant_id: str, webstore_id: str, *, include_inactive: bool) -> list[dict]:
    """Canonical setup files, then rows from the old Webstore file store (read-only, not migrated)."""
    q: dict[str, Any] = {"tenant_id": tenant_id, "parent_type": SETUP_FILE_PARENT, "parent_id": webstore_id}
    if not include_inactive:
        q["archived"] = {"$ne": True}
    links = [serialize_doc(d) async for d in db.file_links.find(q, {"_id": 0}).sort([("created_at", -1)])]
    file_ids = [link["file_id"] for link in links]
    records = {d["id"]: d async for d in db.files.find({"tenant_id": tenant_id, "id": {"$in": file_ids}}, {"_id": 0})}
    docs = [_link_view(link, records[link["file_id"]]) for link in links if link["file_id"] in records]
    legacy_q: dict[str, Any] = {"tenant_id": tenant_id, "webstore_id": webstore_id}
    if not include_inactive:
        legacy_q["status"] = "active"
    docs += [{**serialize_doc(d), "legacy": True} async for d in db.webstore_setup_files.find(legacy_q, {"_id": 0}).sort([("created_at", -1)])]
    return docs


async def _find_setup_file(tenant_id: str, webstore_id: str, file_id: str, *, include_replaced: bool = False) -> Optional[dict]:
    for doc in await _setup_file_docs(tenant_id, webstore_id, include_inactive=include_replaced):
        if doc["id"] == file_id and (doc.get("status") != "removed"):
            return doc
    return None


async def find_webstore_setup_file(tenant_id: str, webstore_id: str, file_id: str, *, include_replaced: bool = False) -> Optional[dict]:
    """The one lookup other Webstore modules use for a setup file (canonical or old-store row)."""
    return await _find_setup_file(tenant_id, webstore_id, file_id, include_replaced=include_replaced)


async def existing_setup_file_ids(tenant_id: str, webstore_id: str, file_ids: list[str]) -> set[str]:
    wanted = set(file_ids)
    return {d["id"] for d in await _setup_file_docs(tenant_id, webstore_id, include_inactive=False) if d["id"] in wanted}


async def count_active_setup_files(tenant_id: str, webstore_id: str) -> int:
    return len(await _setup_file_docs(tenant_id, webstore_id, include_inactive=False))


async def upload_setup_file(user: dict, webstore_id: str, *, filename: str, content_type: str, data: bytes, category: str, notes: Optional[str] = None, replaces_file_id: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    file_doc = await store_setup_file(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        filename=filename,
        content_type=content_type,
        data=data,
        category=category,
        notes=notes,
        replaces_file_id=replaces_file_id,
    )
    return {"file": file_doc}


async def portal_upload_setup_file(identity: dict, webstore_id: str, *, filename: str, content_type: str, data: bytes, category: str, notes: Optional[str] = None, replaces_file_id: Optional[str] = None) -> dict:
    await _owner_store(identity, webstore_id)
    file_doc = await store_setup_file(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal",
        actor_id=identity.get("id"),
        filename=filename,
        content_type=content_type,
        data=data,
        category=category,
        notes=notes,
        replaces_file_id=replaces_file_id,
    )
    return {"file": file_doc}


async def list_setup_files(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    await _get_store(user["tenant_id"], webstore_id)
    docs = await _setup_file_docs(user["tenant_id"], webstore_id, include_inactive=True)
    return {"items": [_safe_file_record(d, staff=True) for d in docs]}


async def portal_list_setup_files(identity: dict, webstore_id: str) -> dict:
    await _owner_store(identity, webstore_id)
    docs = await _setup_file_docs(identity["tenant_id"], webstore_id, include_inactive=False)
    return {"items": [_safe_file_record(d, staff=False) for d in docs]}


async def download_setup_file(tenant_id: str, webstore_id: str, file_id: str) -> tuple[dict, bytes, str]:
    doc = await _find_setup_file(tenant_id, webstore_id, file_id)
    if not doc:
        raise WebstoreSetupError("setup_file_not_found", "Setup file not found", 404)
    data, content_type = storage.get_bytes(doc["storage_key"])
    return doc, data, doc.get("detected_content_type") or content_type


async def preview_setup_file(user: dict, webstore_id: str, file_id: str) -> tuple[dict, bytes, str]:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    await _get_store(user["tenant_id"], webstore_id)
    doc = await _find_setup_file(user["tenant_id"], webstore_id, file_id)
    if not doc:
        raise WebstoreSetupError("setup_file_not_found", "Setup file not found", 404)
    if not doc.get("safe_preview_available") or not doc.get("inline_preview_allowed") or doc.get("private_download_only"):
        raise WebstoreSetupError("setup_file_preview_unavailable", "This setup file is not safe for inline preview", 400)
    ext = str(doc.get("extension") or "").lower()
    if ext in DOWNLOAD_ONLY_EXTENSIONS or ext not in SAFE_EXTENSIONS:
        raise WebstoreSetupError("setup_file_preview_unavailable", "This setup file is not safe for inline preview", 400)
    try:
        data, content_type = storage.get_bytes(doc["storage_key"])
    except FileNotFoundError:
        raise WebstoreSetupError("setup_file_not_found", "Setup file not found", 404)
    return doc, data, doc.get("detected_content_type") or content_type


async def remove_setup_file(user: dict, webstore_id: str, file_id: str, reason: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    doc = await _find_setup_file(user["tenant_id"], webstore_id, file_id)
    if not doc:
        raise WebstoreSetupError("setup_file_not_found", "Setup file not found", 404)
    if doc.get("legacy"):
        raise WebstoreSetupError("legacy_setup_file_read_only", "Files uploaded before the shared file store are read-only until migration is authorised", 409)
    await db.file_links.update_one(
        {"tenant_id": user["tenant_id"], "id": file_id},
        {"$set": {"archived": True, "metadata.status": "removed", "metadata.notes": reason, "updated_at": _now_iso()}},
    )
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.setup_file_removed",
        entity_type="file_link",
        entity_id=file_id,
        summary="Webstore setup file removed",
        metadata={"reason": reason},
    )
    return {"file_id": file_id, "status": "removed"}

__all__ = ['SETUP_FILE_PARENT', '_extension', '_looks_like', '_detect_content_type', '_safe_file_record', '_svg_is_safe', 'store_setup_file', 'count_active_setup_files', 'find_webstore_setup_file', 'existing_setup_file_ids', 'upload_setup_file', 'portal_upload_setup_file', 'list_setup_files', 'portal_list_setup_files', 'download_setup_file', 'preview_setup_file', 'remove_setup_file']
