"""EC19 onboarding, help center, and contextual documentation contracts."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field

from .base import BaseDoc

OnboardingProgramStatus = Literal["draft", "active", "retired"]
OnboardingTaskStatus = Literal["not_started", "in_progress", "completed", "skipped", "deferred", "blocked"]
OnboardingTaskLevel = Literal["required", "recommended", "optional"]
OnboardingImportStatus = Literal["uploaded", "pending_provider", "unavailable", "reviewed", "discarded"]
TemplateExerciseStatus = Literal["draft", "previewed", "saved", "discarded"]
HelpArticleStatus = Literal["draft", "published", "archived"]
HelpAudience = Literal["owner", "admin", "staff", "platform"]
SupportEscalationStatus = Literal["open", "triaged", "resolved", "closed"]


class OnboardingProgramDefinition(BaseDoc):
    program_key: str
    version: int = Field(ge=1)
    status: OnboardingProgramStatus = "draft"
    title: str
    description: Optional[str] = None
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    effective_at: Optional[str] = None
    retired_at: Optional[str] = None
    platform_managed: bool = True


class TenantOnboardingInstance(BaseDoc):
    tenant_id: str
    program_key: str
    program_version: int
    status: OnboardingTaskStatus = "not_started"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_by_user_id: Optional[str] = None
    updated_by_user_id: Optional[str] = None


class OnboardingTaskState(BaseDoc):
    tenant_id: str
    program_key: str
    program_version: int
    task_key: str
    status: OnboardingTaskStatus = "not_started"
    level: OnboardingTaskLevel = "recommended"
    skipped_reason: Optional[str] = None
    deferred_until: Optional[str] = None
    blocked_reason: Optional[str] = None
    completed_at: Optional[str] = None
    updated_by_user_id: Optional[str] = None


class OnboardingStepResponse(BaseDoc):
    tenant_id: str
    task_key: str
    response_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None
    applied: bool = False
    applied_record_ids: list[str] = Field(default_factory=list)
    created_by_user_id: str


class OnboardingImportRecord(BaseDoc):
    tenant_id: str
    import_type: str
    file_name: str
    file_type: Optional[str] = None
    file_size_bytes: Optional[int] = Field(default=None, ge=0)
    status: OnboardingImportStatus = "uploaded"
    analysis_status: str = "not_requested"
    analysis_boundary: str = "ec17_ec16_provider_deferred"
    warnings: list[str] = Field(default_factory=list)
    created_by_user_id: str


class OnboardingTemplateExercise(BaseDoc):
    tenant_id: str
    template_id: Optional[str] = None
    template_type: str
    name: str
    body: dict[str, Any] = Field(default_factory=dict)
    preview: dict[str, Any] = Field(default_factory=dict)
    missing_placeholders: list[str] = Field(default_factory=list)
    status: TemplateExerciseStatus = "draft"
    created_by_user_id: str


class HelpArticle(BaseDoc):
    slug: str
    title: str
    category: str
    body: str
    status: HelpArticleStatus = "draft"
    audience: list[HelpAudience] = Field(default_factory=lambda: ["owner", "admin", "staff"])
    module: Optional[str] = None
    search_keywords: list[str] = Field(default_factory=list)
    published_at: Optional[str] = None
    archived_at: Optional[str] = None
    version: int = 1
    platform_managed: bool = True
    created_by_user_id: Optional[str] = None
    updated_by_user_id: Optional[str] = None


class ContextualHelpDefinition(BaseDoc):
    surface_key: str
    help_key: str
    module: str
    title: str
    body: str
    status: HelpArticleStatus = "published"
    article_slug: Optional[str] = None
    role_hints: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class HelpFeedback(BaseDoc):
    tenant_id: str
    article_id: Optional[str] = None
    article_slug: Optional[str] = None
    helpful: Optional[bool] = None
    comment: Optional[str] = None
    idempotency_key: Optional[str] = None
    created_by_user_id: str


class SupportEscalation(BaseDoc):
    tenant_id: str
    subject: str
    message: str
    source_surface: Optional[str] = None
    status: SupportEscalationStatus = "open"
    idempotency_key: Optional[str] = None
    created_by_user_id: str
