"""EC2 — Shared Webhook Event log.

Every inbound webhook (SendGrid today; Stripe + others in later ECs) is
recorded here BEFORE processing. This gives:
  - Replay-safety via unique (provider, provider_event_id).
  - Auditable processing status + failure reason.
  - A single place to observe webhook health.

Raw payloads are stored only when explicitly opted in (SENDGRID_STORE_RAW_PAYLOAD
etc.). Otherwise a trimmed metadata snapshot is written.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import Field

from .base import BaseDoc

WebhookProcessingStatus = Literal["received", "verified", "processed", "failed", "duplicate"]


class WebhookEvent(BaseDoc):
    provider: str                       # "sendgrid" | "stripe" | ...
    provider_event_id: str              # required — dedupe key
    received_at: datetime
    processing_status: WebhookProcessingStatus = "received"
    signature_verified: bool = False
    tenant_id: Optional[str] = None     # resolved after verification when possible
    event_type: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None  # trimmed, non-sensitive snapshot
