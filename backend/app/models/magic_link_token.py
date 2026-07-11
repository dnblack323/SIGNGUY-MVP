"""EC6 — Magic-link token (portal login).

Only the SHA-256 hash of the raw token is stored. The raw token is emailed
once and then discarded. Tokens are single-use, expiring, and audience-scoped
to a specific portal_identity.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import Field
from .base import BaseDoc


class MagicLinkToken(BaseDoc):
    tenant_id: str
    portal_identity_id: str
    token_hash: str            # sha256(raw)
    expires_at: datetime
    single_use: bool = True
    consumed_at: Optional[datetime] = None
    ip_issued: Optional[str] = None
    email_sent_to: Optional[str] = None  # informational; not the raw token
