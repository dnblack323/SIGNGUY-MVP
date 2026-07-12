"""EC8 phase 8b — Timesheet (weekly approvable unit, Saturday-Friday).

Daily and monthly views are computed on the fly from `TimeEntry` documents
(no persisted document needed). The WEEKLY Timesheet is the one persisted,
approvable unit — this is deliberately compatible with (but not yet equal
to) the Phase 8d Pay Period, per the EC8 preflight's proposed architecture.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from .base import BaseDoc

TimesheetStatus = Literal["pending", "approved", "rejected"]


class Timesheet(BaseDoc):
    tenant_id: str
    employee_id: str
    week_start: str   # Saturday, "YYYY-MM-DD"
    week_end: str     # Friday, "YYYY-MM-DD"
    status: TimesheetStatus = "pending"
    worked_minutes: int = 0
    break_minutes: int = 0
    regular_minutes: int = 0
    overtime_minutes: int = 0
    estimated_gross_cents: int = 0
    incomplete_entry_count: int = 0
    missed_clock_count: int = 0
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    rejected_by: Optional[str] = None
    rejected_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    review_history: list[dict] = Field(default_factory=list)  # [{action, by, at, reason?}]
