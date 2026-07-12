"""EC8 phase 8c — Shift (single authoritative shift-assignment record).

Deliberately does NOT carry Time Clock state (`open`/`completed`/etc. belong
to `TimeEntry`, owned by Phase 8b — see `models/time_entry.py`). A Shift is a
planned assignment; a TimeEntry is what actually happened. The two may be
compared later (e.g. "scheduled but not clocked in") but never merged into
one state machine.
"""
from __future__ import annotations

from typing import Literal, Optional

from .base import BaseDoc

ShiftStatus = Literal["scheduled", "cancelled", "completed"]


class Shift(BaseDoc):
    tenant_id: str
    schedule_id: str
    employee_id: str
    shift_date: str                        # tenant-local business date, "YYYY-MM-DD"
    start_at: str                          # ISO datetime
    end_at: str                            # ISO datetime
    break_minutes_expected: int = 0
    location: Optional[str] = None
    title: Optional[str] = None            # shift type / role for this shift
    notes: Optional[str] = None
    work_order_id: Optional[str] = None    # opaque link only — never resolved to full WO for the portal
    order_id: Optional[str] = None         # opaque link only — never resolved to full Order for the portal
    status: ShiftStatus = "scheduled"
    conflict_override_reason: Optional[str] = None  # set only when created/edited over an availability warning
    created_by: str
    updated_by: str
