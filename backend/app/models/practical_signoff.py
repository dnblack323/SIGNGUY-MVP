"""EC8 phase 8e — Practical Signoff.

An Employee may never self-certify: `evaluator_user_id` must be a
manager/trainer distinct from the Employee's own linked User account,
enforced in `services/training_service.py`.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from .base import BaseDoc

SignoffResult = Literal["passed", "failed"]


class PracticalSignoff(BaseDoc):
    tenant_id: str
    employee_id: str
    training_assignment_id: str
    equipment_id: Optional[str] = None
    evaluator_user_id: str
    evaluation_date: str  # ISO date "YYYY-MM-DD"
    result: SignoffResult
    notes: Optional[str] = None
    restrictions: Optional[str] = None
    evidence_document_ids: list[str] = Field(default_factory=list)
    created_by: str
