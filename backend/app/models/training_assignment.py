"""EC8 phase 8e — Training Assignment (one Employee's instance of a
Training Definition)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import Field

from .base import BaseDoc

TrainingAssignmentStatus = Literal[
    "not_started", "in_progress", "pending_signoff", "completed", "failed", "expired", "cancelled",
]
PracticalSignoffStatus = Literal["not_required", "pending", "passed", "failed"]


class TrainingAssignment(BaseDoc):
    tenant_id: str
    employee_id: str
    training_definition_id: str
    equipment_id: Optional[str] = None   # denormalized from the definition at assignment time
    assigned_by: str
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    due_date: Optional[str] = None
    status: TrainingAssignmentStatus = "not_started"
    progress_percent: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    required_score: Optional[int] = None   # snapshot of definition.passing_score
    latest_score: Optional[int] = None
    practical_signoff_required: bool = False  # snapshot of definition.practical_signoff_required
    practical_signoff_status: PracticalSignoffStatus = "not_required"
    acknowledged_at: Optional[datetime] = None
    manager_notes: Optional[str] = None            # never shown to the Employee Portal
    employee_visible_notes: Optional[str] = None
    renewal_of: Optional[str] = None               # prior TrainingAssignment.id, for retraining cycles
    created_by: str
    updated_by: str
