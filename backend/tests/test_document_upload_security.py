from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.deps import get_current_user
from server import app


def _override(user: dict):
    async def _get():
        return {**user}

    return _get


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear() -> None:
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_file_upload_uses_strict_mime_extension_and_magic_validation(seeded_users):
    user = seeded_users["user_a"]
    async with await _client_as(user) as client:
        valid = await client.post(
            "/api/files/upload",
            files={"file": ("proof.png", b"\x89PNG\r\n\x1a\n" + uuid.uuid4().bytes, "image/png")},
        )
        assert valid.status_code == 201, valid.text
        file_record = valid.json()["file"]
        assert file_record["original_filename"] == "proof.png"
        assert file_record["mime_type"] == "image/png"

        mismatch = await client.post(
            "/api/files/upload",
            files={"file": ("payload.exe", b"\x89PNG\r\n\x1a\n" + uuid.uuid4().bytes, "image/png")},
        )
        assert mismatch.status_code == 400

        generic = await client.post(
            "/api/files/upload",
            files={"file": ("payload.bin", b"opaque", "application/octet-stream")},
        )
        assert generic.status_code == 400

        forged = await client.post(
            "/api/files/upload",
            files={"file": ("payload.png", b"not a png", "image/png")},
        )
        assert forged.status_code == 400
    _clear()


@pytest.mark.asyncio
async def test_file_upload_sanitizes_filename_and_download_is_tenant_scoped(seeded_users):
    user_a = seeded_users["user_a"]
    user_b = seeded_users["user_b"]
    async with await _client_as(user_a) as client_a:
        uploaded = await client_a.post(
            "/api/files/upload",
            files={"file": ("../proof.pdf", b"%PDF-1.4\n1 0 obj\n%%EOF", "application/pdf")},
        )
        assert uploaded.status_code == 201, uploaded.text
        file_record = uploaded.json()["file"]
        assert file_record["original_filename"] == "proof.pdf"
        download = await client_a.get(f"/api/files/{file_record['id']}/download")
        assert download.status_code == 200
        assert "filename*=UTF-8''proof.pdf" in download.headers["content-disposition"]

    async with await _client_as(user_b) as client_b:
        hidden = await client_b.get(f"/api/files/{file_record['id']}/download")
        assert hidden.status_code == 404
    _clear()
