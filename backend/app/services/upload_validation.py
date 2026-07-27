"""EC2 - Upload validation (MIME, extension, magic-byte, size, filename)."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import PurePath

from fastapi import HTTPException

MAX_UPLOAD_BYTES = 25 * 1024 * 1024

_UNSAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._\- ]+")

ALLOWED_MIME_EXTENSIONS: dict[str, set[str]] = {
    "image/png": {".png"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/gif": {".gif"},
    "image/webp": {".webp"},
    "application/pdf": {".pdf"},
    "application/msword": {".doc"},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {".docx"},
    "text/plain": {".txt"},
    "text/csv": {".csv"},
    "application/zip": {".zip"},
    "application/x-zip-compressed": {".zip"},
}

_MAGIC_BYTES: dict[str, list[bytes]] = {
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/gif": [b"GIF87a", b"GIF89a"],
    "application/pdf": [b"%PDF-"],
    "application/zip": [b"PK\x03\x04"],
    "application/x-zip-compressed": [b"PK\x03\x04"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [b"PK\x03\x04"],
}


@dataclass(frozen=True)
class ValidatedUpload:
    safe_filename: str
    mime_type: str
    size_bytes: int
    sha256: str


def sanitize_filename(name: str) -> str:
    name = PurePath((name or "").strip() or "unnamed").name
    name = name.replace("\\", "_").replace("/", "_")
    name = _UNSAFE_NAME_RE.sub("_", name)
    name = name.strip(" .") or "unnamed"
    if len(name) > 200:
        base, _, ext = name.rpartition(".")
        base = base[:180]
        name = f"{base}.{ext}" if ext else base
    return name or "unnamed"


def _extension_for(name: str) -> str:
    suffix = PurePath(name).suffix.lower()
    if not suffix:
        raise HTTPException(status_code=400, detail="File extension is required")
    return suffix


def _magic_matches(mime: str, data: bytes) -> bool:
    if mime == "image/webp":
        return len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    if mime.startswith("text/"):
        try:
            data[:4096].decode("utf-8")
            return b"\x00" not in data[:4096]
        except UnicodeDecodeError:
            return False
    prefixes = _MAGIC_BYTES.get(mime)
    if not prefixes:
        return True
    return any(data.startswith(p) for p in prefixes)


def validate_upload(
    *,
    filename: str,
    content_type: str | None,
    data: bytes,
    enforce_magic: bool = True,
) -> ValidatedUpload:
    if not filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    if data is None:
        raise HTTPException(status_code=400, detail="No file body provided")
    size = len(data)
    if size == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 25MB)")

    mime = (content_type or "").split(";", 1)[0].strip().lower()
    if mime not in ALLOWED_MIME_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {mime}")

    safe_name = sanitize_filename(filename)
    extension = _extension_for(safe_name)
    if extension not in ALLOWED_MIME_EXTENSIONS[mime]:
        raise HTTPException(status_code=400, detail="File extension does not match declared type")

    if enforce_magic and not _magic_matches(mime, data):
        raise HTTPException(status_code=400, detail="File contents do not match declared type")

    sha = hashlib.sha256(data).hexdigest()
    return ValidatedUpload(safe_filename=safe_name, mime_type=mime, size_bytes=size, sha256=sha)
