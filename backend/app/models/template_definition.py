"""Reusable templates shared by EC10 and EC12 systems."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field

from .base import BaseDoc

TemplateType = Literal[
    "intake", "questionnaire", "decision_options",
    "task", "task_checklist", "appointment", "appointment_confirmation", "appointment_reminder",
    "message", "announcement", "note", "daily_digest", "email", "sms",
    "support_response", "bug_response", "feature_request_response", "time_off_response",
]
TemplateOwnerScope = Literal["tenant", "platform"]
TemplateSourceStatus = Literal["active", "deprecated", "replaced"]
TemplatePackType = Literal["starter", "future_paid", "custom"]


class TemplateDefinition(BaseDoc):
    """A reusable template whose body is copied/rendered on apply.

    Live records never keep a mutable reference to this body, so later
    template edits cannot alter already-created intake submissions,
    customer intake prompt configs, Decision Room options, or EC12 records.
    """

    tenant_id: Optional[str] = None
    owner_scope: TemplateOwnerScope = "tenant"
    name: str
    template_type: TemplateType
    description: Optional[str] = None
    body: dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    active: bool = True
    archived_at: Optional[str] = None
    source_status: TemplateSourceStatus = "active"
    source_template_id: Optional[str] = None
    source_template_version: Optional[int] = None
    source_template_name: Optional[str] = None
    installed_at: Optional[str] = None
    tenant_modified: bool = False
    source_update_available: bool = False
    starter_template: bool = False
    pack_id: Optional[str] = None
    pack_type: Optional[TemplatePackType] = None
    platform_managed: bool = False
    premium_reserved: bool = False
    channels: list[str] = Field(default_factory=list)
    placeholders: list[str] = Field(default_factory=list)
    created_by_user_id: Optional[str] = None
    updated_by_user_id: Optional[str] = None


class TemplatePack(BaseDoc):
    id: str
    name: str
    description: Optional[str] = None
    pack_type: TemplatePackType = "starter"
    version: int = 1
    included_template_ids: list[str] = Field(default_factory=list)
    active: bool = True
    platform_managed: bool = True
    starter_pack: bool = False
    premium_reserved: bool = False
