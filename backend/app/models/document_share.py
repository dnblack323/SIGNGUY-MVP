"""EC2 — Document Share.

Records that a document has been shared externally (email, portal link, etc.).
Enforces revocation and per-recipient tracking. Actual short-lived share
tokens will be minted in EC4 (portal checkpoint) — this model just holds the
share record shape.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field

from .base import BaseDoc

ShareChannel = Literal["email", "portal_link", "internal"]


class DocumentShare(BaseDoc):
    tenant_id: str
    document_id: str
    channel: ShareChannel
    recipient_key: str          # email address or portal user id
    shared_by: Optional[str] = None
    revoked: bool = False
    revoked_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None
