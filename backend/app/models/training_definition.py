"""EC8 phase 8e — Training Definition (bounded training content, not a
generic workflow engine).

Quiz questions (when `training_type="quiz"` or a quiz step is embedded) are
stored directly on the definition with the `correct_index` field. This is
NEVER serialized to an Employee Portal response (see
`routers/portal_employee.py` `_public_training_view`) — scoring always
happens backend-side in `services/training_service.py`.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from .base import BaseDoc

TrainingType = Literal[
    "reading", "video", "sop_review", "quiz", "practical_demonstration",
    "manager_signoff", "retraining",
]


class TrainingDefinition(BaseDoc):
    tenant_id: str
    title: str
    description: Optional[str] = None
    equipment_id: Optional[str] = None
    training_type: TrainingType = "reading"
    required_role: Optional[str] = None   # free-text audience label (matches Employee.role_label)
    # Ordered checklist of bounded steps: [{id, label, type: reading|video|sop_review|quiz|practical_demonstration|manager_signoff}]
    required_steps: list[dict] = Field(default_factory=list)
    # [{id, prompt, choices: [str, ...], correct_index}] — correct_index is backend-only, stripped before any portal response.
    quiz_questions: list[dict] = Field(default_factory=list)
    passing_score: Optional[int] = None   # percentage 0-100; relevant only when quiz_questions is non-empty
    practical_signoff_required: bool = False
    expiration_interval_days: Optional[int] = None  # None = never expires / one-time
    version: int = 1
    active: bool = True
    created_by: str
    updated_by: str
