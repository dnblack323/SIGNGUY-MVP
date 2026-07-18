"""EC12 Phase 12C - employee time-off and absence requests.

This is deliberately separate from EC8 shifts and EC8 payroll. Approved
requests project onto the shared calendar as absences; they do not create,
delete, or edit shifts or payroll records.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field

from .base import BaseDoc

TimeOffStatus = Literal["pending", "clarification_requested", "approved", "denied", "canceled"]
TimeOffType = Literal["vacation", "sick", "personal", "bereavement", "jury_duty", "unpaid", "other"]


class TimeOffRequest(BaseDoc):
    tenant_id: str
    employee_id: str
    requested_by_employee_id: str
    reviewed_by_user_id: Optional[str] = None
    request_type: TimeOffType = "other"
    start_at: str
    end_at: str
    all_day: bool = False
    reason: Optional[str] = None
    private_reason: Optional[str] = None
    manager_note: Optional[str] = None
    status: TimeOffStatus = "pending"
    clarification_requested_at: Optional[str] = None
    approved_at: Optional[str] = None
    denied_at: Optional[str] = None
    canceled_at: Optional[str] = None
    version: int = 1
    history: list[dict[str, Any]] = Field(default_factory=list)

