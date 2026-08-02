"""Shared form maker contracts for questionnaires, client forms, and quizzes."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field

from .base import BaseDoc

FORM_CONTEXT_TYPES = ("webstore", "customer", "intake", "training_assignment", "general")
FORM_TEMPLATE_STATUSES = ("draft", "published", "archived")
FORM_REQUEST_STATUSES = ("pending", "sent", "opened", "submitted", "expired", "revoked")
FORM_RESPONSE_STATUSES = ("submitted", "reviewed", "superseded")
FORM_FIELD_TYPES = (
    "text",
    "textarea",
    "number",
    "email",
    "phone",
    "select",
    "multi_select",
    "radio",
    "checkbox",
    "date",
    "file_upload",
    "signature",
    "heading",
    "paragraph",
)

FormContextType = Literal["webstore", "customer", "intake", "training_assignment", "general"]
FormTemplateStatus = Literal["draft", "published", "archived"]
FormRequestStatus = Literal["pending", "sent", "opened", "submitted", "expired", "revoked"]
FormResponseStatus = Literal["submitted", "reviewed", "superseded"]


class FormTemplate(BaseDoc):
    tenant_id: str
    name: str
    module: str = "general"
    context_type: FormContextType = "general"
    description: Optional[str] = None
    status: FormTemplateStatus = "draft"
    version: int = Field(default=1, ge=1)
    sections: list[dict[str, Any]] = Field(default_factory=list)
    mapping_config: dict[str, Any] = Field(default_factory=dict)
    private_config: dict[str, Any] = Field(default_factory=dict)
    source_template_id: Optional[str] = None
    created_by_user_id: Optional[str] = None
    updated_by_user_id: Optional[str] = None


class FormRequest(BaseDoc):
    tenant_id: str
    template_id: str
    template_version: int = Field(default=1, ge=1)
    template_snapshot: dict[str, Any] = Field(default_factory=dict)
    context_type: FormContextType = "general"
    context_id: Optional[str] = None
    recipient_email: Optional[str] = None
    recipient_name: Optional[str] = None
    token_hash: str
    status: FormRequestStatus = "pending"
    expires_at: Optional[str] = None
    opened_at: Optional[str] = None
    submitted_at: Optional[str] = None
    consent_metadata: dict[str, Any] = Field(default_factory=dict)
    created_by_user_id: Optional[str] = None


class FormResponse(BaseDoc):
    tenant_id: str
    request_id: Optional[str] = None
    template_id: str
    template_version: int = Field(default=1, ge=1)
    context_type: FormContextType = "general"
    context_id: Optional[str] = None
    respondent_email: Optional[str] = None
    respondent_name: Optional[str] = None
    answers: dict[str, Any] = Field(default_factory=dict)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    submitted_snapshot: dict[str, Any] = Field(default_factory=dict)
    status: FormResponseStatus = "submitted"
    reviewed_at: Optional[str] = None
    reviewed_by_user_id: Optional[str] = None
    mapping_results: list[dict[str, Any]] = Field(default_factory=list)
