"""EC8 phase 8b — Time Entry (single authoritative Time Clock record).

Durations are stored as integer MINUTES throughout (never float hours) per
the owner's directive. `work_date` is the tenant-timezone business date the
shift started on (see `services/time_period_utils.py`) — never a
browser-local date.

Corrections are append-only (`corrections` list) — original values are never
overwritten in place. An "approved" entry cannot be corrected in Phase 8b;
the containing weekly Timesheet must be reopened first.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from .base import BaseDoc

TimeEntryStatus = Literal["open", "completed", "corrected", "approved", "voided"]
TimeEntrySource = Literal["self", "admin"]


class TimeEntry(BaseDoc):
    tenant_id: str
    employee_id: str
    linked_user_id: Optional[str] = None  # snapshot of Employee.linked_user_id at clock-in time
    work_date: str                        # tenant-local business date, "YYYY-MM-DD"
    clock_in_at: str
    clock_out_at: Optional[str] = None
    breaks: list[dict] = Field(default_factory=list)  # [{start_at, end_at}]
    total_break_minutes: int = 0
    worked_minutes: int = 0               # clock_in->clock_out span minus total_break_minutes
    regular_minutes: int = 0              # foundation: == worked_minutes until OT policy exists
    overtime_minutes: int = 0             # foundation: always 0 until OT policy exists
    status: TimeEntryStatus = "open"
    source: TimeEntrySource = "self"
    work_order_id: Optional[str] = None
    task_id: Optional[str] = None         # placeholder only — no Tasks system exists yet
    notes: Optional[str] = None
    created_by: str
    updated_by: str
    corrections: list[dict] = Field(default_factory=list)  # append-only correction history
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    void_reason: Optional[str] = None
