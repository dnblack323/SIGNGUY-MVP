"""EC2 — Activity envelope model.

Extends (does not replace) the MVP audit trail. Every activity event is
tenant-scoped and linked (optionally) to a business entity + the underlying
audit_event that recorded the low-level change. Activity events are the
human-visible feed surface; audit events are the immutable diff record.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field

from .base import BaseDoc

ActivitySeverity = Literal["info", "success", "warning", "error"]


class ActivityEvent(BaseDoc):
    tenant_id: str
    module: str                       # e.g. "orders", "invoices", "webhooks"
    action: str                       # e.g. "order.created", "invoice.sent"
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    actor_user_id: Optional[str] = None
    actor_email: Optional[str] = None
    audit_event_id: Optional[str] = None   # link back to underlying audit row
    summary: str
    severity: ActivitySeverity = "info"
    metadata: Optional[dict[str, Any]] = None  # small structured payload; NO secrets
