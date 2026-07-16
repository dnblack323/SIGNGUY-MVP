"""EC10 Phase 10G - tenant-scoped reusable templates."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field

from .base import BaseDoc

TemplateType = Literal["intake", "questionnaire", "decision_options"]


class TemplateDefinition(BaseDoc):
    """A reusable tenant-owned template whose body is copied on apply.

    Live records never keep a mutable reference to this body, so later
    template edits cannot alter already-created intake submissions,
    customer intake prompt configs, or Decision Room options.
    """

    tenant_id: str
    name: str
    template_type: TemplateType
    description: Optional[str] = None
    body: dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    active: bool = True
    archived_at: Optional[str] = None
    created_by_user_id: Optional[str] = None
    updated_by_user_id: Optional[str] = None
