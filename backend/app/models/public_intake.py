"""EC6 — Public Quote Request + Public Customer Intake responses.

Minimal, secure public workflows. Public submissions never touch authoritative
Quote / Customer records directly. Quote requests create a draft, tenant-scoped
`quote_request` for staff review + optional customer/lead match. Customer
intake responses are stored raw and mapped-to-changes are staged for staff
review — no silent overwrite of authoritative Customer data.
"""
from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import Field
from .base import BaseDoc

QuoteRequestStatus = Literal[
    "new", "matched", "converted", "spam", "rejected",
]


class QuoteRequest(BaseDoc):
    tenant_id: str
    number: int
    status: QuoteRequestStatus = "new"
    # public-supplied (contact + project)
    contact_name: str
    contact_email: str
    contact_phone: Optional[str] = None
    company: Optional[str] = None
    project_title: Optional[str] = None
    project_description: Optional[str] = None
    desired_due_date: Optional[str] = None
    file_ids: list[str] = Field(default_factory=list)  # sanitized uploads
    # server-populated (never trust client)
    source: str = "public_web"
    consent_marketing: bool = False
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    matched_customer_id: Optional[str] = None
    matched_lead_id: Optional[str] = None
    converted_quote_id: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    notes_internal: Optional[str] = None  # staff-only


CustomerIntakeStatus = Literal["issued", "submitted", "applied", "rejected"]


class CustomerIntake(BaseDoc):
    """A staff-issued intake sent to a known Customer via a scoped token.

    A `CustomerIntake` row is created when staff mints an intake link; when the
    customer submits, the response is stored on the row (raw) and staged
    changes are computed. No silent overwrite of the authoritative Customer.
    """
    tenant_id: str
    customer_id: str                      # the intake target
    number: int
    status: CustomerIntakeStatus = "issued"
    token_id: Optional[str] = None        # public_action_tokens.id
    prompt_config: dict[str, Any] = Field(default_factory=dict)   # what fields to request
    response: dict[str, Any] = Field(default_factory=dict)        # raw submitted values
    submitted_at: Optional[str] = None
    submitted_ip: Optional[str] = None
    submitted_user_agent: Optional[str] = None
    staged_changes: dict[str, Any] = Field(default_factory=dict)  # server-computed diff for staff review
    applied_at: Optional[str] = None
    applied_by: Optional[str] = None
    applied_fields: list[str] = Field(default_factory=list)       # explicit staff-approved fields
    file_ids: list[str] = Field(default_factory=list)
    created_by: Optional[str] = None
