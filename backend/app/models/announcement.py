"""EC8 phase 8a — Announcement (Team & Workflow).

Reuses `services/notifications.py` (in-app) and `services/email.py` (outbound
email) for delivery — this model stores only the announcement content and
audience; it is NOT a second messaging system.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from .base import BaseDoc

AnnouncementAudience = Literal["all", "selected"]
AnnouncementStatus = Literal["draft", "published", "expired"]


class Announcement(BaseDoc):
    tenant_id: str
    title: str
    body: str
    audience: AnnouncementAudience = "all"
    employee_ids: list[str] = Field(default_factory=list)  # used only when audience == "selected"
    acknowledgement_required: bool = False
    status: AnnouncementStatus = "draft"
    published_at: Optional[str] = None
    expires_at: Optional[str] = None
    created_by: str
    acknowledged_by: list[str] = Field(default_factory=list)  # employee_ids who acknowledged
