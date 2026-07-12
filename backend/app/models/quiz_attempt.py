"""EC8 phase 8e — Quiz Attempt (append-only attempt history).

Every attempt is retained — never overwritten. Scoring happens entirely in
`services/training_service.py`; the raw `answers` are stored for audit but
the training definition's answer key is never returned to a caller.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from .base import BaseDoc


class QuizAttempt(BaseDoc):
    tenant_id: str
    employee_id: str
    training_assignment_id: str
    attempt_number: int
    answers: list[dict] = Field(default_factory=list)  # [{question_id, selected_index}]
    score: int              # percentage 0-100
    passed: bool
    started_at: datetime
    completed_at: datetime
    duration_seconds: Optional[int] = None
    reviewed_by: Optional[str] = None
