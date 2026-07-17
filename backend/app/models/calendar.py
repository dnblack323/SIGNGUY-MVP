"""EC12 Phase 12D - stored appointment records for the shared calendar feed."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field

from .base import BaseDoc

CalendarEventStatus = Literal["scheduled", "rescheduled", "canceled", "completed"]
CalendarVisibility = Literal["internal", "staff", "employee"]
CalendarEventType = Literal[
    "consultation",
    "site_survey",
    "vehicle_dropoff",
    "vehicle_pickup",
    "installation",
    "customer_meeting",
    "internal_meeting",
    "production_milestone",
    "custom",
]


class CalendarEvent(BaseDoc):
    tenant_id: str
    event_type: CalendarEventType = "custom"
    title: str
    description: Optional[str] = None
    start_at: str
    end_at: str
    all_day: bool = False
    timezone: Optional[str] = None
    location: Optional[str] = None
    status: CalendarEventStatus = "scheduled"
    customer_id: Optional[str] = None
    order_id: Optional[str] = None
    order_item_id: Optional[str] = None
    work_order_id: Optional[str] = None
    production_stage_id: Optional[str] = None
    employee_id: Optional[str] = None
    assigned_user_id: Optional[str] = None
    created_by_user_id: Optional[str] = None
    created_by_employee_id: Optional[str] = None
    visibility: CalendarVisibility = "staff"
    reminder_policy: dict[str, Any] = Field(default_factory=dict)
    recurrence_rule: Optional[dict[str, Any]] = None
    source_type: str = "appointment"
    source_id: Optional[str] = None
    archived_at: Optional[str] = None
    version: int = 1
    history: list[dict[str, Any]] = Field(default_factory=list)
    conflict_overrides: list[dict[str, Any]] = Field(default_factory=list)

