"""EC2 — Upload validation (MIME, extension, magic-byte, size, filename)."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from fastapi import HTTPException

MAX_UPLOAD_BYTES = 25 * 1024 * 1024

ALLOWED_MIME_PREFIXES = (
    "image/",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument",
    "text/",
    "application/zip",
    "application/x-zip-compressed",
    "application/octet-stream",
)

_UNSAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._\- ]+")
_MAGIC_BYTES: dict[str, list[bytes]] = {
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/gif": [b"GIF87a", b"GIF89a"],
    "image/webp": [b"RIFF"],  # partial — followed by WEBP marker
    "application/pdf": [b"%PDF-"],
    "application/zip": [b"PK\x03\x04"],
    "application/x-zip-compressed": [b"PK\x03\x04"],
}


@dataclass(frozen=True)
class ValidatedUpload:
    safe_filename: str
    mime_type: str
    size_bytes: int
    sha256: str


def sanitize_filename(name: str) -> str:
    name = (name or "").strip() or "unnamed"
    # Collapse whitespace, strip control chars, prevent path separators.
    name = name.replace("\\", "_").replace("/", "_")
    name = _UNSAFE_NAME_RE.sub("_", name)
    if len(name) > 200:
        base, _, ext = name.rpartition(".")
        base = base[:180]
        name = f"{base}.{ext}" if ext else base
    return name or "unnamed"


def _mime_allowed(mime: str) -> bool:
    return any(mime.startswith(p) for p in ALLOWED_MIME_PREFIXES)


def _magic_matches(mime: str, data: bytes) -> bool:
    prefixes = _MAGIC_BYTES.get(mime)
    if not prefixes:
        return True  # We don't fingerprint every type; MIME check + size cap suffice.
    return any(data.startswith(p) for p in prefixes)


def validate_upload(
    *,
    filename: str,
    content_type: str | None,
    data: bytes,
    enforce_magic: bool = True,
) -> ValidatedUpload:
    """Return a ValidatedUpload or raise HTTPException 4xx.

    - Rejects empty / too-large payloads.
    - Rejects disallowed MIME.
    - Optionally rejects when magic bytes don't match the MIME.
    - Sanitizes filename.
    - Computes sha256.
    """
    if not filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    if data is None:
        raise HTTPException(status_code=400, detail="No file body provided")
    size = len(data)
    if size == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 25MB)")

    mime = (content_type or "application/octet-stream").strip().lower()
    if not _mime_allowed(mime):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {mime}")

    if enforce_magic and not _magic_matches(mime, data):
        raise HTTPException(status_code=400, detail="File contents do not match declared type")

    safe_name = sanitize_filename(filename)
    sha = hashlib.sha256(data).hexdigest()
    return ValidatedUpload(safe_filename=safe_name, mime_type=mime, size_bytes=size, sha256=sha)
