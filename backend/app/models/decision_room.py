"""EC10 Phase 10D — Customer Decision Room (internal authoring only).

A `DecisionRoom` presents 1..N `DecisionOption` cards for a Customer to
compare, select, or ask about (Phase 10E — NOT built here). Phase 10D is
STAFF-ONLY: no customer access, no public-token resolution, no selection/
rejection/comment capture exists anywhere in this file or its service.

`DecisionOption` is embedded on the room (mirrors the
`IntakeSubmission.items` / `IntakeItem` precedent from Phase 10A/10B) —
options are always authored, reordered, and duplicated as a unit with their
parent room and never need independent tenant-level querying.

`DecisionRoomVersion` is a SEPARATE, append-only collection (mirrors
`VisualMarkup`/`MarkupVersion` from Phase 10C) that freezes the customer-
facing content at the moment of publication. A published version must stay
byte-identical forever, even as the live `DecisionRoom` (and any Quote/
Order/File/Proof/pricing snapshot it references) continues to change.
"""
from __future__ import annotations

import uuid
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from .base import BaseDoc

DecisionRoomStatus = Literal["draft", "ready", "published", "expired", "closed", "archived"]
DecisionBadgeType = Literal["recommended", "best_value", "premium", "budget", "fastest", "custom", "none"]
PriceDisplayMode = Literal["show_price", "hide_price", "contact_for_price"]
SelectedPriceSource = Literal["snapshot", "manual"]


class DecisionOption(BaseModel):
    """One customer-facing comparison card within a DecisionRoom. Embedded —
    never queried independently of its parent room. All money is integer
    cents. Phase 10D never calculates pricing here — `suggested_price_cents`
    is only ever copied (immutably, at attach time) from an existing EC9
    `PricingSnapshotRecord`; `manual_price_cents` is only ever set when a
    human explicitly types a value."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    display_order: int = 0
    internal_name: Optional[str] = None
    customer_label: Optional[str] = None
    badge_type: DecisionBadgeType = "none"
    custom_badge_text: Optional[str] = None
    headline: Optional[str] = None
    customer_safe_description: Optional[str] = None
    included_features: list[str] = Field(default_factory=list)
    excluded_features: list[str] = Field(default_factory=list)
    expected_timing: Optional[str] = None

    price_display_mode: PriceDisplayMode = "show_price"
    pricing_snapshot_id: Optional[str] = None
    suggested_price_cents: Optional[int] = None
    manual_price_cents: Optional[int] = None
    selected_price_source: SelectedPriceSource = "manual"
    selected_display_price_cents: Optional[int] = None  # backend-derived — never client-set directly

    quote_line_item_id: Optional[str] = None
    order_item_id: Optional[str] = None
    proof_id: Optional[str] = None
    file_ids: list[str] = Field(default_factory=list)
    visual_markup_id: Optional[str] = None
    rendered_preview_file_id: Optional[str] = None
    thumbnail_file_id: Optional[str] = None

    internal_notes: Optional[str] = None
    customer_safe_notes: Optional[str] = None

    active: bool = True
    created_by_user_id: Optional[str] = None
    updated_by_user_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DecisionRoom(BaseDoc):
    tenant_id: str
    title: str
    internal_name: Optional[str] = None
    customer_safe_intro: Optional[str] = None
    status: DecisionRoomStatus = "draft"

    customer_id: Optional[str] = None
    intake_id: Optional[str] = None
    quote_id: Optional[str] = None
    order_id: Optional[str] = None
    order_item_id: Optional[str] = None

    # Reserved — Phase 10E/public-access stub only. No public-token issuance
    # or resolution happens anywhere in Phase 10D.
    public_token_id: Optional[str] = None

    # `current_version` tracks the draft's version position; it is bumped
    # (without creating a `DecisionRoomVersion` row) whenever the room is
    # edited AFTER it has been published, so `current_version != published_
    # version` is a cheap signal that unpublished changes exist.
    current_version: int = 0
    published_version: int = 0

    expiration_at: Optional[str] = None
    allow_save_for_later: bool = False
    allow_customer_comments: bool = False
    allow_customer_questions: bool = False
    allow_change_requests: bool = False
    require_internal_acceptance: bool = True  # matches EC10 owner decision #1's recommended default

    options: list[DecisionOption] = Field(default_factory=list)

    created_by_user_id: Optional[str] = None
    updated_by_user_id: Optional[str] = None
    published_by_user_id: Optional[str] = None
    published_at: Optional[str] = None
    archived_at: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionRoomVersion(BaseDoc):
    """Append-only frozen snapshot created ONLY by `publish_room()`. Never
    mutated after insert."""

    tenant_id: str
    decision_room_id: str
    version_number: int

    title: str
    customer_safe_intro: Optional[str] = None
    options_snapshot: list[dict[str, Any]] = Field(default_factory=list)  # frozen DecisionOption dicts
    allow_save_for_later: bool = False
    allow_customer_comments: bool = False
    allow_customer_questions: bool = False
    allow_change_requests: bool = False
    require_internal_acceptance: bool = True
    expiration_at: Optional[str] = None

    published_by_user_id: Optional[str] = None
