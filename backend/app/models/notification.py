"""EC2 — In-App Notifications (staff-only, tenant-scoped).

This is distinct from external portal notifications (customer/employee/webstore
portals). Portal delivery flows will land in their own checkpoints and MUST NOT
reuse this collection.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import Field

from .base import BaseDoc

NotificationStatus = Literal["unread", "read", "dismissed"]
NotificationSeverity = Literal["info", "success", "warning", "error"]


class Notification(BaseDoc):
    tenant_id: str
    recipient_user_id: str            # staff user
    module: str                       # e.g. "invoices"
    kind: str                         # short slug e.g. "invoice.overdue"
    title: str
    body: Optional[str] = None
    severity: NotificationSeverity = "info"
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    link: Optional[str] = None        # front-end deep-link path
    status: NotificationStatus = "unread"
    read_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None
    metadata: Optional[dict[str, Any]] = None  # small structured payload; NO secrets
