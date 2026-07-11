"""EC6 — Portal-scoped JWT helpers. Distinct from staff `create_access_token`.

Portal tokens carry `sub_scope="portal"`. Staff dep must reject portal tokens;
portal dep must reject staff tokens. Two dependency graphs, zero crossover.
"""
from __future__ import annotations
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from .config import get_settings

_settings = get_settings()

PORTAL_TOKEN_TTL_MINUTES = 60 * 12  # 12 hours


def create_portal_token(*, portal_identity_id: str, tenant_id: str, customer_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": portal_identity_id,
        "sub_scope": "portal",
        "tenant_id": tenant_id,
        "customer_id": customer_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=PORTAL_TOKEN_TTL_MINUTES)).timestamp()),
        "typ": "portal_access",
    }
    return jwt.encode(payload, _settings.jwt_secret, algorithm=_settings.jwt_algorithm)


def decode_portal_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, _settings.jwt_secret, algorithms=[_settings.jwt_algorithm])


def generate_raw_token(nbytes: int = 32) -> str:
    """Generate a URL-safe raw token. Only the SHA-256 is persisted."""
    return secrets.token_urlsafe(nbytes)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
