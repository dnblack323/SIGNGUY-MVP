"""Password hashing (bcrypt) and JWT token helpers."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from .config import get_settings

_settings = get_settings()


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(*, subject: str, tenant_id: str, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "tenant_id": tenant_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=_settings.jwt_access_ttl_minutes)).timestamp()),
        "typ": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _settings.jwt_secret, algorithm=_settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, _settings.jwt_secret, algorithms=[_settings.jwt_algorithm])


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


def hash_reset_token(raw_token: str) -> str:
    """One-way SHA-256 digest of a password-reset token. Only the raw token
    is ever emailed to the user; the database stores the hash so read access
    to the DB alone can never be used to redeem an unused reset token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
