"""Setup file validation, storage, listing, preview, download, and removal."""
from __future__ import annotations

from .webstore_setup_common import *
from .webstore_setup_portal_scope import _owner_store
from .webstore_setup_progress import _refresh_setup_state


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
    key = storage.build_key(tenant_id, filename)
    storage.put_bytes(key, data, detected)
    version = 1
    if replaces_file_id:
        previous = await db.webstore_setup_files.find_one({"tenant_id": tenant_id, "webstore_id": webstore_id, "id": replaces_file_id}, {"_id": 0})
        if not previous:
            raise WebstoreSetupError("setup_file_not_found", "Setup file to replace was not found", 404)
        version = int(previous.get("version") or 1) + 1
    doc = WebstoreSetupFile(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        category=_clean_text(category, "category", limit=80),
        file_name=filename,
        extension=ext,
        content_type=content_type or detected,
        detected_content_type=detected,
        size_bytes=len(data),
        storage_key=key,
        uploaded_by_actor_type=actor_type,
        uploaded_by_id=actor_id,
        version=version,
        replaces_file_id=replaces_file_id,
        safe_preview_available=inline,
        inline_preview_allowed=inline,
        private_download_only=not inline,
        svg_sanitized=svg_safe,
        notes=notes,
    ).model_dump()
    await db.webstore_setup_files.insert_one(prepare_for_mongo(doc))
    if replaces_file_id:
        await db.webstore_setup_files.update_one(
            {"tenant_id": tenant_id, "id": replaces_file_id},
            {"$set": {"status": "replaced", "replaced_by_file_id": doc["id"], "updated_at": _now_iso()}},
        )
    await _refresh_setup_state(tenant_id, webstore_id)
    await _audit(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action="webstore.setup_file_uploaded" if not replaces_file_id else "webstore.setup_file_replaced",
        entity_type="webstore_setup_file",
        entity_id=doc["id"],
        summary="Webstore setup file uploaded" if not replaces_file_id else "Webstore setup file replaced",
        metadata={"category": category, "extension": ext, "size_bytes": len(data), "version": version},
    )
    return _safe_file_record(serialize_doc(doc), staff=actor_type == "staff")


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
    items = [_safe_file_record(serialize_doc(d), staff=True) async for d in db.webstore_setup_files.find({"tenant_id": user["tenant_id"], "webstore_id": webstore_id}, {"_id": 0, "storage_key": 0}).sort([("created_at", -1)])]
    return {"items": items}


async def portal_list_setup_files(identity: dict, webstore_id: str) -> dict:
    await _owner_store(identity, webstore_id)
    items = [_safe_file_record(serialize_doc(d), staff=False) async for d in db.webstore_setup_files.find({"tenant_id": identity["tenant_id"], "webstore_id": webstore_id, "status": {"$ne": "removed"}}, {"_id": 0, "storage_key": 0}).sort([("created_at", -1)])]
    return {"items": items}


async def download_setup_file(tenant_id: str, webstore_id: str, file_id: str) -> tuple[dict, bytes, str]:
    doc = await db.webstore_setup_files.find_one({"tenant_id": tenant_id, "webstore_id": webstore_id, "id": file_id, "status": {"$ne": "removed"}}, {"_id": 0})
    if not doc:
        raise WebstoreSetupError("setup_file_not_found", "Setup file not found", 404)
    data, content_type = storage.get_bytes(doc["storage_key"])
    return serialize_doc(doc), data, doc.get("detected_content_type") or content_type


async def preview_setup_file(user: dict, webstore_id: str, file_id: str) -> tuple[dict, bytes, str]:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    await _get_store(user["tenant_id"], webstore_id)
    doc = await db.webstore_setup_files.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": file_id, "status": "active"},
        {"_id": 0},
    )
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
    return serialize_doc(doc), data, doc.get("detected_content_type") or content_type


async def remove_setup_file(user: dict, webstore_id: str, file_id: str, reason: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    result = await db.webstore_setup_files.update_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": file_id, "status": {"$ne": "removed"}},
        {"$set": {"status": "removed", "notes": reason, "updated_at": _now_iso()}},
    )
    if result.matched_count != 1:
        raise WebstoreSetupError("setup_file_not_found", "Setup file not found", 404)
    await _refresh_setup_state(user["tenant_id"], webstore_id)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.setup_file_removed",
        entity_type="webstore_setup_file",
        entity_id=file_id,
        summary="Webstore setup file removed",
        metadata={"reason": reason},
    )
    return {"file_id": file_id, "status": "removed"}

__all__ = ['_extension', '_looks_like', '_detect_content_type', '_safe_file_record', '_svg_is_safe', 'store_setup_file', 'upload_setup_file', 'portal_upload_setup_file', 'list_setup_files', 'portal_list_setup_files', 'download_setup_file', 'preview_setup_file', 'remove_setup_file']
