"""EC10 Phase 10A — Intake Submission (canonical data contract).

An `IntakeSubmission` captures a request for work (from staff, a customer,
a public link, a questionnaire, or another source) BEFORE it becomes an
authoritative Quote or Order. It never copies live Customer/Quote/Order
records — only references them by id (mirrors the `CustomerIntake`
staged-diff precedent from EC6: nothing here silently overwrites anything).

No pricing is calculated or invented here. Pricing remains exclusively owned
by the EC9 `calculate_pricing()` service; `IntakeItem.category_inputs` is
just carried forward, unpriced, for later use by that service.

Phase 10A intentionally leaves `VisualMarkup`/`DecisionRoom` unimplemented —
`visual_markup_id`/`rendered_preview_file_id` (item-level) and
`decision_room_id` (submission-level) are reserved, unenforced reference
fields only, per the EC10 preflight (Phase 10C/10D contracts).
"""
from __future__ import annotations

import uuid
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from .base import BaseDoc

IntakeSourceType = Literal[
    "internal_user", "customer_portal", "public_intake_link", "questionnaire",
    "email_import", "quote", "order", "saved_template", "api", "other",
]

IntakeStatus = Literal[
    "draft", "submitted", "under_review", "needs_information",
    "accepted", "converted_to_quote", "converted_to_order",
    "rejected", "cancelled",
]

IntakePriority = Literal["low", "normal", "high", "urgent"]

IntakeItemConversionStatus = Literal[
    "pending", "converted_to_quote_line_item", "converted_to_order_item",
]


class IntakeItem(BaseModel):
    """One requested line within an IntakeSubmission (multi-item intake)."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    category: Optional[str] = None
    item_name: Optional[str] = None
    description: Optional[str] = None
    quantity: int = 1
    measurements: dict[str, Any] = Field(default_factory=dict)   # e.g. {"width_inches": 24, "unit": "in", "source": "customer_provided"}
    category_inputs: dict[str, Any] = Field(default_factory=dict)  # unpriced — consumed later by EC9 calculate_pricing()

    # Canonical EC7/EC9 references (never copied — reference only)
    saved_item_id: Optional[str] = None
    material_profile_id: Optional[str] = None
    pricing_component_ids: list[str] = Field(default_factory=list)

    # Assets (reference existing FileRecord ids only — no inline storage)
    file_ids: list[str] = Field(default_factory=list)

    customer_notes: Optional[str] = None
    internal_notes: Optional[str] = None

    proof_required: bool = False
    approval_required: bool = False
    requested_due_date: Optional[str] = None
    installation_required: bool = False

    conversion_status: IntakeItemConversionStatus = "pending"
    quote_line_item_id: Optional[str] = None
    order_item_id: Optional[str] = None

    # Phase 10C contract (not implemented yet — reference only)
    visual_markup_id: Optional[str] = None
    rendered_preview_file_id: Optional[str] = None


class IntakeSubmission(BaseDoc):
    tenant_id: str
    intake_number: int

    source_type: IntakeSourceType = "internal_user"
    source_reference: Optional[str] = None  # e.g. "template:<id>" | "quote:<id>" — opaque, unvalidated in 10A

    submitted_by_user_id: Optional[str] = None
    submitted_by_customer_id: Optional[str] = None

    customer_id: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None

    project_name: Optional[str] = None
    project_description: Optional[str] = None
    intake_type: Optional[str] = None

    status: IntakeStatus = "draft"
    priority: IntakePriority = "normal"

    requested_due_date: Optional[str] = None
    installation_required: bool = False
    installation_location: Optional[str] = None
    installation_notes: Optional[str] = None

    assigned_user_id: Optional[str] = None
    assigned_team_id: Optional[str] = None  # reserved — no Team/Task grouping exists yet

    quote_id: Optional[str] = None
    order_id: Optional[str] = None

    questionnaire_submission_ids: list[str] = Field(default_factory=list)  # references `customer_intakes` rows
    file_ids: list[str] = Field(default_factory=list)  # submission-level assets (not tied to one item)
    items: list[IntakeItem] = Field(default_factory=list)

    proof_required: bool = False
    approval_required: bool = False

    internal_notes: Optional[str] = None
    customer_notes: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    idempotency_key: Optional[str] = None

    submitted_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    converted_at: Optional[str] = None
    rejected_at: Optional[str] = None
    rejected_reason: Optional[str] = None
    cancelled_at: Optional[str] = None
    cancelled_reason: Optional[str] = None

    created_by_user_id: Optional[str] = None
    updated_by_user_id: Optional[str] = None

    # Phase 10C/10D contracts (not implemented yet — reference only)
    visual_markup_ids: list[str] = Field(default_factory=list)
    decision_room_id: Optional[str] = None
