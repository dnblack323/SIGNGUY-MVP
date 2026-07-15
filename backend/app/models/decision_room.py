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
    # EC10 Phase 10E-2 — "reject all options" is a distinct, room-level
    # customer action from rejecting a single option; per owner instruction
    # it must NOT be assumed enabled — off by default, explicit opt-in.
    allow_reject_all: bool = False
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
    allow_reject_all: bool = False
    require_internal_acceptance: bool = True
    expiration_at: Optional[str] = None

    published_by_user_id: Optional[str] = None


CustomerDecisionActionType = Literal["option_selected", "option_rejected", "all_options_rejected", "change_requested"]
CustomerDecisionAccessMode = Literal["portal", "public_token"]
CustomerDecisionInternalReviewStatus = Literal["pending_review", "acknowledged"]


class CustomerDecision(BaseDoc):
    """EC10 Phase 10E-2 — append-only, customer-originated decision event
    against the FROZEN `published_version_id` a customer actually viewed.

    NEVER mutated to reflect a later choice — superseding a prior selection
    is expressed by inserting a NEW row whose `supersedes_decision_id`
    points at the old row; the old row is never edited or deleted (mirrors
    the `Approval`/append-only precedent). `internal_review_status` starts
    and stays `pending_review` from the customer's own action; only staff
    (via a dedicated endpoint) can ever move it to `acknowledged` — no
    customer-submitted field can set or influence it. Nothing in this model
    or the service that writes it ever mutates a Quote/Order/Order Item
    (that stays Phase 10F, an explicit, separate, staff-controlled step)."""

    tenant_id: str
    decision_room_id: str
    published_version_id: str
    published_version_number: Optional[int] = None  # display-only convenience, never authoritative

    action_type: CustomerDecisionActionType
    option_id: Optional[str] = None  # required for option_selected/option_rejected; must be None for all_options_rejected
    comment: Optional[str] = None    # required (non-empty) for change_requested

    source_access_mode: CustomerDecisionAccessMode
    customer_id: Optional[str] = None       # set when source_access_mode == "portal"
    public_token_id: Optional[str] = None   # set when source_access_mode == "public_token"
    actor_display: Optional[str] = None

    supersedes_decision_id: Optional[str] = None
    internal_review_status: CustomerDecisionInternalReviewStatus = "pending_review"

    idempotency_key: Optional[str] = None
    submitted_at: Optional[str] = None
    ip: Optional[str] = None
    user_agent: Optional[str] = None



# ---- EC10 Phase 10E-3 — Customer Questions, Anchored Comments/Pins, and
# Save for Later. All three reuse `CustomerDecisionAccessMode` (portal vs
# public_token) but are DELIBERATELY separate collections from
# `CustomerDecision` — none of these represent a select/reject decision,
# and folding them in would distort that model's supersede/history
# semantics for no benefit.

DecisionRoomQuestionStatus = Literal["open", "answered", "resolved"]


class DecisionRoomQuestion(BaseDoc):
    """A customer question tied to the exact frozen `published_version_id`
    they were shown, optionally scoped to one option and/or one piece of
    customer-safe media. `staff_response`/`responded_*` are populated ONLY
    by the staff respond endpoint — never customer-submitted."""

    tenant_id: str
    decision_room_id: str
    published_version_id: str
    option_id: Optional[str] = None
    source_file_id: Optional[str] = None
    visual_markup_id: Optional[str] = None
    markup_version_id: Optional[str] = None

    source_access_mode: CustomerDecisionAccessMode
    customer_id: Optional[str] = None
    public_token_id: Optional[str] = None
    actor_display: Optional[str] = None

    customer_message: str
    status: DecisionRoomQuestionStatus = "open"

    staff_response: Optional[str] = None
    responded_by_user_id: Optional[str] = None
    responded_at: Optional[str] = None

    idempotency_key: Optional[str] = None
    submitted_at: Optional[str] = None


DecisionRoomOverlayType = Literal["comment", "pin"]
DecisionRoomOverlayStatus = Literal["active", "withdrawn"]


class DecisionRoomOverlay(BaseDoc):
    """A customer-authored anchored comment/pin over a customer-safe media
    reference — stored ENTIRELY separately from staff-authored Fabric.js
    `MarkupVersion.structured_markup_json`. Coordinates are normalized
    (0.0-1.0) relative to the referenced media's display box, independent
    of the staff editor's `canvas_pixels_v1` contract, so a customer overlay
    renders correctly at any viewer size without needing canvas dimensions."""

    tenant_id: str
    decision_room_id: str
    published_version_id: str
    source_file_id: Optional[str] = None
    visual_markup_id: Optional[str] = None
    markup_version_id: Optional[str] = None
    page_number: Optional[int] = None

    overlay_type: DecisionRoomOverlayType = "comment"
    normalized_x: float
    normalized_y: float
    marker_number: Optional[int] = None  # assigned server-side for overlay_type == "pin" only

    customer_message: str
    status: DecisionRoomOverlayStatus = "active"

    source_access_mode: CustomerDecisionAccessMode
    customer_id: Optional[str] = None
    public_token_id: Optional[str] = None

    idempotency_key: Optional[str] = None


class SavedForLater(BaseDoc):
    """A lightweight "come back later" marker — deliberately NOT a
    `CustomerDecision` (it never selects/rejects/requests anything, extends
    no expiration, and touches no pricing). Append-only; a returning
    customer simply keeps viewing the same frozen `published_version_id`."""

    tenant_id: str
    decision_room_id: str
    published_version_id: str
    source_access_mode: CustomerDecisionAccessMode
    customer_id: Optional[str] = None
    public_token_id: Optional[str] = None
    note: Optional[str] = None
    idempotency_key: Optional[str] = None
    saved_at: Optional[str] = None
