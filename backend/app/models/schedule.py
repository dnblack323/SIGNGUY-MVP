"""EC8 phase 8c — Schedule (single authoritative tenant-scoped weekly schedule).

One Schedule document per tenant per Saturday-Friday week (matches the
Phase 8b week boundary from `services/time_period_utils.py` so Team Schedule,
Employee Portal My Schedule, and Team Dashboard summaries all read the same
week grid). `Shift` documents (see `models/shift.py`) point back at this via
`schedule_id` — no redundant per-employee or per-day schedule collections.
"""
from __future__ import annotations

from typing import Literal, Optional

from .base import BaseDoc

ScheduleStatus = Literal["draft", "published", "archived"]


class Schedule(BaseDoc):
    tenant_id: str
    period_start: str            # Saturday, "YYYY-MM-DD"
    period_end: str              # Friday, "YYYY-MM-DD"
    status: ScheduleStatus = "draft"
    version: int = 1
    published_at: Optional[str] = None
    published_by: Optional[str] = None
    last_notified_at: Optional[str] = None  # watermark — only shifts changed after this get re-notified
    created_by: str
    updated_by: str
