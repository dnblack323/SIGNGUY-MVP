"""EC9 Phase 9C — Grouped Pricing Setup Quiz submission.

An ADDITIVE setup path alongside the existing detailed `CategorySetupWizard`
(never a replacement). One grouped, practical-scenario Q&A produces a set of
PROVISIONAL suggestions the owner must explicitly review before any value is
applied to `pricing_settings.shop_defaults`. The original answers and derived
suggestions are stored immutably for audit; `applied_fields`/`applied_at`
record only what the owner actually chose to apply (which may differ from
the raw suggestions if they edited or rejected individual values).
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field

from .base import BaseDoc

QuizStatus = Literal["draft", "applied", "skipped"]


class PricingQuizSubmission(BaseDoc):
    tenant_id: str
    category: str
    answers: dict[str, Any]
    derived_suggestions: dict[str, Any]
    math_shown: list[str] = Field(default_factory=list)
    status: QuizStatus = "draft"
    applied_fields: dict[str, float] = Field(default_factory=dict)
    applied_at: Optional[str] = None
    applied_by_user_id: Optional[str] = None
