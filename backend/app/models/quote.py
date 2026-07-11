from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field

from .base import BaseDoc

QuoteStatus = Literal[
    "draft", "sent", "viewed", "approved", "declined", "expired", "converted", "void"
]


class Quote(BaseDoc):
    tenant_id: str
    number: int  # sequential per tenant
    customer_id: str
    job_name: str
    notes: Optional[str] = None                 # legacy MVP note — kept as internal note

    # EC3 — revision + expiration + approval-state foundation
    revision_number: int = 1
    expires_at: Optional[str] = None            # ISO date/time
    notes_internal: Optional[str] = None
    notes_customer: Optional[str] = None

    # EC3 — backend-derived commerce totals (integer cents)
    subtotal_cents: int = 0
    discount_cents: int = 0
    tax_cents: int = 0
    total_cents: int = 0                        # kept for backward compat with existing MVP UI

    status: QuoteStatus = "draft"
    sent_at: Optional[datetime] = None
    viewed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    approved_revision: Optional[int] = None
    approved_actor_user_id: Optional[str] = None
    approved_source: Optional[str] = None       # e.g. "staff", "portal", "public_token"
    declined_at: Optional[datetime] = None
    declined_reason: Optional[str] = None
    converted_order_id: Optional[str] = None
    converted_revision: Optional[int] = None
    converted_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    created_by: str                             # user id
