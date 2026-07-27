"""Application-owned object storage adapter.

The default implementation stores bytes under a configured filesystem root and
keeps all access backend-proxied. Storage keys remain tenant-scoped and are not
public URLs.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Tuple

from ..core.config import ROOT_DIR, get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()
_TEST_OBJECTS: dict[str, tuple[bytes, str]] = {}


def _use_test_storage() -> bool:
    return _settings.env == "test"


def _storage_root() -> Path:
    configured = _settings.object_storage_path
    if configured:
        return Path(configured).expanduser().resolve()
    if _settings.env == "production":
        raise RuntimeError("OBJECT_STORAGE_PATH missing; object storage unavailable")
    return (ROOT_DIR / ".data" / "object_storage").resolve()


def _safe_storage_path(storage_key: str) -> Path:
    root = _storage_root()
    path = (root / storage_key).resolve()
    if root != path and root not in path.parents:
        raise ValueError("Storage key escapes object storage root")
    return path


def initialize() -> None:
    if _use_test_storage():
        logger.info("Object storage initialized in test mode")
        return
    if _settings.storage_backend != "filesystem":
        raise RuntimeError("Unsupported STORAGE_BACKEND; expected 'filesystem'")
    root = _storage_root()
    root.mkdir(parents=True, exist_ok=True)
    logger.info("Object storage initialized at %s", root)


def build_key(tenant_id: str, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    ext = "".join(ch for ch in ext if ch.isalnum())[:8] or "bin"
    return f"{_settings.app_name}/tenants/{tenant_id}/files/{uuid.uuid4()}.{ext}"


def put_bytes(storage_key: str, data: bytes, content_type: str) -> dict:
    if _use_test_storage():
        _TEST_OBJECTS[storage_key] = (data, content_type)
        return {"storage_key": storage_key, "test_storage": True}
    initialize()
    path = _safe_storage_path(storage_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"storage_key": storage_key, "backend": "filesystem"}


def get_bytes(storage_key: str) -> Tuple[bytes, str]:
    if _use_test_storage():
        if storage_key not in _TEST_OBJECTS:
            raise FileNotFoundError(storage_key)
        return _TEST_OBJECTS[storage_key]
    path = _safe_storage_path(storage_key)
    return path.read_bytes(), "application/octet-stream"
