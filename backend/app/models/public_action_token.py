"""EC6 — Public action token (single-purpose, scoped, expiring).

Bound to a single action + a single parent record. Raw token is emailed once
and hashed at rest. Consuming a single-use token marks it consumed. Multi-use
tokens (quote_view, invoice_view) may permit GETs before expiry but never
authorize writes beyond the bound action.
"""
from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional
from pydantic import Field
from .base import BaseDoc

PublicAction = Literal[
    "proof_approve",
    "proof_request_changes",
    "sign",
    "quote_view",
    "invoice_view",
    "invoice_pay",
    "customer_intake",
]


class PublicActionToken(BaseDoc):
    tenant_id: str
    token_hash: str                       # sha256(raw)
    action: PublicAction
    parent_type: str                      # "proof" | "invoice" | "quote" | "signature_request" | "customer_intake" | ...
    parent_id: str
    parent_version: Optional[int] = None  # locked at issue time when applicable
    audience_email: Optional[str] = None  # optional binding for extra safety
    expires_at: datetime
    single_use: bool = True
    consumed_at: Optional[datetime] = None
    revoked: bool = False
    issued_by: Optional[str] = None       # staff user_id
    ip_issued: Optional[str] = None
