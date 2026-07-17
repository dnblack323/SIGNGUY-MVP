"""Emergent Object Storage adapter. Private-by-default.

Proxies downloads through this backend so every retrieval is auth+tenant scoped.
Storage paths are tenant-scoped: {app_name}/tenants/{tenant_id}/files/{uuid}
"""
from __future__ import annotations

import logging
import uuid
from typing import Tuple

import requests

from ..core.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()

_STORAGE_KEY: str | None = None
_TEST_OBJECTS: dict[str, tuple[bytes, str]] = {}


def _use_test_storage() -> bool:
    return _settings.env == "test" and not _settings.emergent_llm_key


def _init_storage_key() -> str:
    global _STORAGE_KEY
    if _STORAGE_KEY:
        return _STORAGE_KEY
    if _use_test_storage():
        _STORAGE_KEY = "test-storage"
        return _STORAGE_KEY
    if not _settings.emergent_llm_key:
        raise RuntimeError("EMERGENT_LLM_KEY missing; object storage unavailable")
    resp = requests.post(
        f"{_settings.storage_url}/init",
        json={"emergent_key": _settings.emergent_llm_key},
        timeout=30,
    )
    resp.raise_for_status()
    _STORAGE_KEY = resp.json()["storage_key"]
    return _STORAGE_KEY


def initialize() -> None:
    try:
        _init_storage_key()
        logger.info("Object storage initialized")
    except Exception as e:
        logger.error("Object storage init failed: %s", e)


def build_key(tenant_id: str, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    ext = "".join(ch for ch in ext if ch.isalnum())[:8] or "bin"
    return f"{_settings.app_name}/tenants/{tenant_id}/files/{uuid.uuid4()}.{ext}"


def put_bytes(storage_key: str, data: bytes, content_type: str) -> dict:
    if _use_test_storage():
        _TEST_OBJECTS[storage_key] = (data, content_type)
        return {"storage_key": storage_key, "test_storage": True}
    key = _init_storage_key()
    resp = requests.put(
        f"{_settings.storage_url}/objects/{storage_key}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def get_bytes(storage_key: str) -> Tuple[bytes, str]:
    if _use_test_storage():
        if storage_key not in _TEST_OBJECTS:
            raise FileNotFoundError(storage_key)
        return _TEST_OBJECTS[storage_key]
    key = _init_storage_key()
    resp = requests.get(
        f"{_settings.storage_url}/objects/{storage_key}",
        headers={"X-Storage-Key": key},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")
