"""EC2 — Email Activity (SendGrid delivery / open / bounce / drop events).

Backs the outbound-email observability layer. One row per provider event.
Uniqueness enforced via (provider, provider_event_id) — SendGrid emits unique
event IDs so duplicates are safely no-ops.

DO NOT store the entire SendGrid payload verbatim. Persist only the fields
needed for support triage + delivery analytics.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import EmailStr, Field

from .base import BaseDoc

EmailActivityEvent = Literal[
    "processed",
    "delivered",
    "open",
    "click",
    "bounce",
    "dropped",
    "spamreport",
    "unsubscribe",
    "deferred",
    "group_unsubscribe",
    "group_resubscribe",
]


class EmailActivity(BaseDoc):
    tenant_id: str
    provider: str = "sendgrid"
    provider_event_id: str            # unique per provider event
    email_log_id: Optional[str] = None  # link to internal EmailLog when resolvable
    sendgrid_message_id: Optional[str] = None
    to_email: EmailStr
    event: EmailActivityEvent
    event_timestamp: datetime
    reason: Optional[str] = None       # bounce/drop reason (short string)
    smtp_id: Optional[str] = None
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[str] = None
    # Small trimmed payload snapshot for support triage; MUST NOT contain
    # secrets, full HTML, or attachment bytes. Kept to safe scalar fields.
    payload_snapshot: Optional[dict[str, Any]] = None
