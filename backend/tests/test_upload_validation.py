"""EC2 — Upload validation tests."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services.upload_validation import (
    MAX_UPLOAD_BYTES,
    sanitize_filename,
    validate_upload,
)

PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF_HEADER = b"%PDF-1.4\n" + b"\x00" * 64
JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def test_sanitize_filename_strips_path_and_specials():
    # Path separators are collapsed to underscores; there is no way to
    # traverse a directory after sanitization.
    result = sanitize_filename("../etc/passwd")
    assert "/" not in result
    assert "\\" not in result
    assert result == ".._etc_passwd"
    assert sanitize_filename("").endswith("unnamed")
    long_name = "a" * 500 + ".pdf"
    assert len(sanitize_filename(long_name)) <= 200 + 4


def test_reject_empty_file():
    with pytest.raises(HTTPException) as exc:
        validate_upload(filename="a.png", content_type="image/png", data=b"")
    assert exc.value.status_code == 400


def test_reject_too_large_file():
    big = b"a" * (MAX_UPLOAD_BYTES + 1)
    with pytest.raises(HTTPException) as exc:
        validate_upload(filename="a.png", content_type="image/png", data=big)
    assert exc.value.status_code == 413


def test_reject_disallowed_mime():
    with pytest.raises(HTTPException) as exc:
        validate_upload(filename="a.exe", content_type="application/x-msdownload", data=b"MZ...")
    assert exc.value.status_code == 400


def test_accept_valid_png():
    v = validate_upload(filename="logo.png", content_type="image/png", data=PNG_HEADER)
    assert v.mime_type == "image/png"
    assert v.size_bytes == len(PNG_HEADER)
    assert len(v.sha256) == 64


def test_accept_valid_pdf():
    v = validate_upload(filename="doc.pdf", content_type="application/pdf", data=PDF_HEADER)
    assert v.mime_type == "application/pdf"


def test_reject_png_with_wrong_magic_bytes():
    fake = b"NOT-A-PNG" + b"\x00" * 100
    with pytest.raises(HTTPException) as exc:
        validate_upload(filename="a.png", content_type="image/png", data=fake)
    assert exc.value.status_code == 400


def test_can_disable_magic_enforcement():
    fake = b"nope"
    v = validate_upload(filename="a.png", content_type="image/png", data=fake, enforce_magic=False)
    assert v.mime_type == "image/png"
