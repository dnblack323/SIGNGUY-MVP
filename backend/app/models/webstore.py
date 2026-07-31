"""EC14 - Webstores canonical data contracts."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field, StrictInt

from .base import BaseDoc

WEBSTORE_TYPES = ("b2b", "fundraiser", "event", "promotional", "employee", "general")
WEBSTORE_TYPE_LABELS = {
    "b2b": "B2B",
    "fundraiser": "Fundraiser",
    "event": "Event",
    "promotional": "Promotional",
    "employee": "Employee",
    "general": "General",
}

WEBSTORE_LIFECYCLE_STATES = (
    "draft",
    "questionnaire_sent",
    "waiting_on_store_owner",
    "questionnaire_submitted",
    "ai_setup_ready",
    "ai_product_suggestions_ready",
    "artwork_needs_review",
    "mockups_generated",
    "mockups_approved",
    "products_selected",
    "store_packet_generated",
    "sent_for_approval",
    "changes_requested",
    "approved",
    "launch_ready",
    "scheduled",
    "paused",
    "live",
    "closing_soon",
    "closed",
    "in_production",
    "completed",
    "relaunch_ready",
    "archived",
)

WebstoreStatus = Literal[
    "draft",
    "questionnaire_sent",
    "waiting_on_store_owner",
    "questionnaire_submitted",
    "ai_setup_ready",
    "ai_product_suggestions_ready",
    "artwork_needs_review",
    "mockups_generated",
    "mockups_approved",
    "products_selected",
    "store_packet_generated",
    "sent_for_approval",
    "changes_requested",
    "approved",
    "launch_ready",
    "scheduled",
    "paused",
    "live",
    "closing_soon",
    "closed",
    "in_production",
    "completed",
    "relaunch_ready",
    "archived",
]
WebstoreOwnerStatus = Literal["active", "disabled", "archived"]
WebstoreType = Literal["b2b", "fundraiser", "event", "promotional", "employee", "general"]
WebstoreProductStatus = Literal["draft", "planned", "incomplete", "ready", "active", "inactive", "archived"]
WebstoreTemplateScope = Literal["tenant", "platform"]
WebstoreTemplateStatus = Literal["draft", "active", "archived"]
WebstoreCategoryStatus = Literal["active", "archived"]
QuestionnaireStatus = Literal["draft", "submitted", "returned_for_changes", "reviewed", "superseded", "pending"]
WebstoreSetupState = Literal[
    "not_started",
    "invitation_pending",
    "questionnaire_in_progress",
    "questionnaire_submitted",
    "staff_review",
    "changes_requested",
    "setup_in_progress",
    "blocked",
    "setup_complete",
]
WebstoreAssignmentRole = Literal["owner", "manager"]
WebstoreAssignmentStatus = Literal["invited", "active", "revoked", "expired", "replaced"]
WebstoreInvitationStatus = Literal["pending", "sent", "send_failed", "accepted", "revoked", "expired", "superseded"]
WebstoreQuestionnaireTemplateStatus = Literal["active", "inactive", "retired"]
WebstoreSetupFileStatus = Literal["active", "replaced", "removed"]
WebstoreAnswerApplicationStatus = Literal["applied", "reversed"]
WebstoreBrandingStatus = Literal[
    "draft",
    "waiting_owner_approval",
    "changes_requested",
    "owner_approved",
    "published",
]
ArtworkStatus = Literal[
    "uploaded",
    "cleanup_pending",
    "cleaned",
    "approved_for_mockups",
    "approved_for_production",
    "rejected",
]
MockupStatus = Literal["draft", "generated", "shop_approved", "owner_approved", "changes_requested"]
LaunchPacketStatus = Literal["draft", "generated", "sent_for_approval", "delivered", "changes_requested", "owner_approved", "superseded", "invalidated"]
WebstoreChangeRequestStatus = Literal["open", "answered", "resolved", "declined", "superseded"]
BuyerOrderStatus = Literal[
    "new",
    "paid",
    "in_review",
    "ready_for_production",
    "in_production",
    "ready_for_pickup",
    "shipped",
    "delivered",
    "completed",
    "refunded",
    "canceled",
]
PurchaseIntentStatus = Literal[
    "pending_payment",
    "payment_processing",
    "paid_order_created",
    "payment_failed",
    "partially_refunded",
    "refunded",
    "disputed",
    "expired",
    "canceled",
]
PaymentEventStatus = Literal["processing", "processed", "failed", "duplicate"]
LedgerEntryType = Literal[
    "buyer_payment",
    "product_subtotal",
    "donation",
    "shipping",
    "sales_tax",
    "payment_processing_fee",
    "platform_usage_fee",
    "platform_usage_fee_reversal",
    "store_owner_share",
    "fundraiser_share",
    "production_cost_estimate",
    "shop_gross_estimate",
    "refund",
    "payout",
    "dispute_hold",
    "dispute_release",
]
LedgerEntryStatus = Literal["posted", "reversed", "adjusted"]
StripeBoundaryStatus = Literal["local_only", "pending_provider", "provider_ready", "failed"]
AIUsageStatus = Literal["drafted", "reviewed", "approved", "rejected"]


class WebstoreOwner(BaseDoc):
    tenant_id: str
    name: str
    email: str
    phone: Optional[str] = None
    organization: Optional[str] = None
    customer_id: Optional[str] = None
    portal_identity_id: Optional[str] = None
    stripe_account_id: Optional[str] = None
    stripe_onboarding_status: str = "not_required"
    status: WebstoreOwnerStatus = "active"


class Webstore(BaseDoc):
    tenant_id: str
    owner_id: str
    name: str
    slug: str
    public_slug: str
    store_type: WebstoreType = "general"
    status: WebstoreStatus = "draft"
    description: Optional[str] = None
    branding: dict[str, Any] = Field(default_factory=dict)
    checkout_enabled: bool = False
    entitlement_feature_key: str = "webstores"
    terms_fee_acknowledged: bool = False
    owner_approved_at: Optional[str] = None
    owner_approved_by_portal_identity_id: Optional[str] = None
    owner_approved_packet_id: Optional[str] = None
    owner_approved_packet_version: Optional[StrictInt] = Field(default=None, ge=1)
    owner_approval_invalidated_at: Optional[str] = None
    owner_approval_invalidated_reason: Optional[str] = None
    launch_packet_id: Optional[str] = None
    launch_packet_version: StrictInt = Field(default=0, ge=0)
    required_terms_version: str = "webstore_terms_2026_07"
    terms_acceptance_id: Optional[str] = None
    terms_accepted_version: Optional[str] = None
    terms_accepted_at: Optional[str] = None
    terms_accepted_by_portal_identity_id: Optional[str] = None
    direct_owner_payout_required: bool = False
    stripe_onboarding_required: bool = False
    stripe_payment_ready: bool = False
    payment_readiness_status: str = "not_configured"
    public_url: Optional[str] = None
    deadline_at: Optional[str] = None
    intended_launch_at: Optional[str] = None
    intended_close_at: Optional[str] = None
    launch_timezone: Optional[str] = None
    launched_at: Optional[str] = None
    closed_at: Optional[str] = None
    archived_at: Optional[str] = None
    setup_state: WebstoreSetupState = "not_started"
    setup_profile: dict[str, Any] = Field(default_factory=dict)
    setup_requirements: dict[str, Any] = Field(default_factory=dict)
    target_launch_at: Optional[str] = None
    event_start_at: Optional[str] = None
    event_location: Optional[str] = None
    primary_owner_assignment_id: Optional[str] = None
    creation_idempotency_key: Optional[str] = None


class WebstoreProductTemplate(BaseDoc):
    tenant_id: str
    template_name: str
    product_category: str
    product_type: str
    scope: WebstoreTemplateScope = "tenant"
    status: WebstoreTemplateStatus = "active"
    default_title: Optional[str] = None
    default_short_description: Optional[str] = None
    default_description: Optional[str] = None
    suggested_category_name: Optional[str] = None
    production_method: Optional[str] = None
    supplier_source_info: Optional[str] = None
    default_production_notes: Optional[str] = None
    default_customer_images: dict[str, Any] = Field(default_factory=dict)
    default_artwork_associations: list[dict[str, Any]] = Field(default_factory=list)
    default_mockup_associations: list[dict[str, Any]] = Field(default_factory=list)
    best_store_types: list[str] = Field(default_factory=list)
    default_variants: list[dict[str, Any]] = Field(default_factory=list)
    mockup_supported: bool = True
    suggested_production_cost_cents: StrictInt = Field(default=0, ge=0)
    suggested_selling_price_cents: StrictInt = Field(default=0, ge=0)
    suggested_store_owner_share_cents: StrictInt = Field(default=0, ge=0)
    platform_fee_basis_points: StrictInt = Field(default=150, ge=0, le=10000)
    internal_notes: Optional[str] = None
    editable_by_shop: bool = True
    active: bool = True
    revision: StrictInt = Field(default=1, ge=1)
    created_by_user_id: Optional[str] = None
    updated_by_user_id: Optional[str] = None


class WebstoreProduct(BaseDoc):
    tenant_id: str
    webstore_id: str
    source_template_id: Optional[str] = None
    source_template_revision: Optional[StrictInt] = Field(default=None, ge=1)
    name: str
    short_description: Optional[str] = None
    full_description: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    category: Optional[str] = None
    product_type: Optional[str] = None
    production_method: Optional[str] = None
    supplier_source_info: Optional[str] = None
    fulfillment_notes: Optional[str] = None
    sku: Optional[str] = None
    production_cost_cents: StrictInt = Field(default=0, ge=0)
    selling_price_cents: StrictInt = Field(ge=0)
    store_owner_share_cents: StrictInt = Field(default=0, ge=0)
    fundraiser_share_cents: StrictInt = Field(default=0, ge=0)
    platform_fee_basis_points: StrictInt = Field(default=150, ge=0, le=10000)
    variants: list[dict[str, Any]] = Field(default_factory=list)
    personalization_enabled: bool = False
    personalization_fields: list[dict[str, Any]] = Field(default_factory=list)
    bundle_items: list[dict[str, Any]] = Field(default_factory=list)
    inventory_policy: str = "not_tracked"
    inventory_quantity: Optional[StrictInt] = Field(default=None, ge=0)
    launch_packet_eligible: bool = False
    launch_packet_include: bool = False
    readiness_notes: list[str] = Field(default_factory=list)
    image_file_ids: list[str] = Field(default_factory=list)
    customer_images: dict[str, Any] = Field(default_factory=dict)
    artwork_associations: list[dict[str, Any]] = Field(default_factory=list)
    mockup_associations: list[dict[str, Any]] = Field(default_factory=list)
    mockup_ids: list[str] = Field(default_factory=list)
    production_notes: Optional[str] = None
    public: bool = False
    featured: bool = False
    status: WebstoreProductStatus = "draft"
    revision: StrictInt = Field(default=1, ge=1)
    created_by_user_id: Optional[str] = None
    updated_by_user_id: Optional[str] = None


class WebstoreProductCategory(BaseDoc):
    tenant_id: str
    webstore_id: str
    name: str
    normalized_name: str
    description: Optional[str] = None
    status: WebstoreCategoryStatus = "active"
    revision: StrictInt = Field(default=1, ge=1)
    created_by_user_id: Optional[str] = None
    updated_by_user_id: Optional[str] = None


class WebstoreQuestionnaireSubmission(BaseDoc):
    tenant_id: str
    webstore_id: str
    owner_id: str
    portal_identity_id: Optional[str] = None
    template_ids: list[str] = Field(default_factory=list)
    template_version_ids: list[str] = Field(default_factory=list)
    template_snapshot: dict[str, Any] = Field(default_factory=dict)
    answers: dict[str, Any] = Field(default_factory=dict)
    known_products: list[dict[str, Any]] = Field(default_factory=list)
    open_to_suggestions: bool = True
    missing_info_flags: list[str] = Field(default_factory=list)
    status: QuestionnaireStatus = "pending"
    submitted_snapshot: dict[str, Any] = Field(default_factory=dict)
    inactive_answer_paths: list[str] = Field(default_factory=list)
    returned_reason: Optional[str] = None
    submitted_at: Optional[str] = None
    reviewed_at: Optional[str] = None


class WebstoreAccessAssignment(BaseDoc):
    tenant_id: str
    webstore_id: str
    owner_id: str
    role: WebstoreAssignmentRole
    email: str
    name: Optional[str] = None
    portal_identity_id: Optional[str] = None
    is_primary_owner: bool = False
    status: WebstoreAssignmentStatus = "invited"
    invitation_id: Optional[str] = None
    invited_at: Optional[str] = None
    accepted_at: Optional[str] = None
    revoked_at: Optional[str] = None
    expired_at: Optional[str] = None
    replaced_at: Optional[str] = None
    replaced_by_assignment_id: Optional[str] = None


class WebstoreInvitation(BaseDoc):
    tenant_id: str
    webstore_id: str
    assignment_id: str
    role: WebstoreAssignmentRole
    email: str
    name: Optional[str] = None
    token_hash: str
    status: WebstoreInvitationStatus = "pending"
    expires_at: str
    sent_at: Optional[str] = None
    accepted_at: Optional[str] = None
    revoked_at: Optional[str] = None
    superseded_at: Optional[str] = None
    delivery_message_id: Optional[str] = None
    delivery_error: Optional[str] = None
    created_by_user_id: Optional[str] = None


class WebstoreQuestionnaireTemplate(BaseDoc):
    tenant_id: str
    scope: str = "tenant"
    store_type: str = "general"
    version: StrictInt = Field(default=1, ge=1)
    title: str
    sections: list[dict[str, Any]] = Field(default_factory=list)
    status: WebstoreQuestionnaireTemplateStatus = "active"
    source_template_id: Optional[str] = None


class WebstoreSetupFile(BaseDoc):
    tenant_id: str
    webstore_id: str
    category: str
    file_name: str
    extension: str
    content_type: str
    detected_content_type: str
    size_bytes: StrictInt = Field(ge=0)
    storage_key: str
    uploaded_by_actor_type: str
    uploaded_by_id: Optional[str] = None
    status: WebstoreSetupFileStatus = "active"
    version: StrictInt = Field(default=1, ge=1)
    replaces_file_id: Optional[str] = None
    replaced_by_file_id: Optional[str] = None
    safe_preview_available: bool = False
    inline_preview_allowed: bool = False
    private_download_only: bool = True
    svg_sanitized: bool = False
    notes: Optional[str] = None


class WebstoreAnswerApplication(BaseDoc):
    tenant_id: str
    webstore_id: str
    submission_id: str
    idempotency_key: str
    status: WebstoreAnswerApplicationStatus = "applied"
    actor_user_id: Optional[str] = None
    actor_email: Optional[str] = None
    reason: str
    proposed_changes: list[dict[str, Any]] = Field(default_factory=list)
    applied_changes: list[dict[str, Any]] = Field(default_factory=list)
    rejected_changes: list[dict[str, Any]] = Field(default_factory=list)
    reversal_of_application_id: Optional[str] = None
    reversed_at: Optional[str] = None


class WebstoreBrandingRecord(BaseDoc):
    tenant_id: str
    webstore_id: str
    status: WebstoreBrandingStatus = "draft"
    draft: dict[str, Any] = Field(default_factory=dict)
    draft_hash: Optional[str] = None
    submitted_snapshot: Optional[dict[str, Any]] = None
    submitted_hash: Optional[str] = None
    submitted_at: Optional[str] = None
    submitted_by_actor_type: Optional[str] = None
    submitted_by_id: Optional[str] = None
    submitted_by_email: Optional[str] = None
    owner_decision: dict[str, Any] = Field(default_factory=dict)
    feedback_note: Optional[str] = None
    published_branding: Optional[dict[str, Any]] = None
    published_hash: Optional[str] = None
    published_version_id: Optional[str] = None
    published_at: Optional[str] = None


class WebstoreBrandingPublishedVersion(BaseDoc):
    tenant_id: str
    webstore_id: str
    version: StrictInt = Field(ge=1)
    branding: dict[str, Any] = Field(default_factory=dict)
    content_hash: str
    published_by_user_id: str
    published_by_email: Optional[str] = None
    submitted_at: Optional[str] = None
    owner_approved_at: Optional[str] = None


class WebstoreArtworkFile(BaseDoc):
    tenant_id: str
    webstore_id: str
    product_id: Optional[str] = None
    uploaded_by_actor_type: str = "staff"
    uploaded_by_id: Optional[str] = None
    file_id: Optional[str] = None
    original_file_id: Optional[str] = None
    original_url: Optional[str] = None
    cleaned_file_id: Optional[str] = None
    cleaned_url: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    purpose: Optional[str] = None
    artwork_status: ArtworkStatus = "uploaded"
    background_removed: bool = False
    transparent_png_created: bool = False
    quality_score: Optional[int] = None
    quality_warnings: list[str] = Field(default_factory=list)
    shop_approved_for_mockups: bool = False
    shop_approved_for_production: bool = False
    notes: Optional[str] = None


class WebstoreMockup(BaseDoc):
    tenant_id: str
    webstore_id: str
    product_id: Optional[str] = None
    artwork_id: Optional[str] = None
    mockup_file_id: Optional[str] = None
    generation_source: str = "manual"
    purpose: Optional[str] = None
    alt_text: Optional[str] = None
    staff_note: Optional[str] = None
    status: MockupStatus = "draft"
    shop_approved: bool = False
    owner_visible: bool = False
    owner_approved: bool = False
    notes: Optional[str] = None


class WebstoreLaunchPacket(BaseDoc):
    tenant_id: str
    webstore_id: str
    version: StrictInt = Field(default=1, ge=1)
    status: LaunchPacketStatus = "draft"
    snapshot: dict[str, Any] = Field(default_factory=dict)
    snapshot_hash: Optional[str] = None
    pricing_summary: dict[str, Any] = Field(default_factory=dict)
    promotion_copy: Optional[str] = None
    qr_code_url: Optional[str] = None
    share_url: Optional[str] = None
    generated_by_user_id: Optional[str] = None
    delivered_by_user_id: Optional[str] = None
    delivery_recipient_email: Optional[str] = None
    delivery_status: Optional[str] = None
    delivery_error: Optional[str] = None
    delivery_idempotency_key: Optional[str] = None
    delivery_portal_path: Optional[str] = None
    sent_at: Optional[str] = None
    delivered_at: Optional[str] = None
    owner_decision_at: Optional[str] = None
    owner_decision_by_portal_identity_id: Optional[str] = None
    change_request_reason: Optional[str] = None
    superseded_at: Optional[str] = None
    invalidated_at: Optional[str] = None
    invalidated_reason: Optional[str] = None


class WebstorePacketApproval(BaseDoc):
    tenant_id: str
    webstore_id: str
    packet_id: str
    packet_version: StrictInt = Field(ge=1)
    portal_identity_id: str
    approver_name: Optional[str] = None
    approver_email: Optional[str] = None
    accepted_snapshot_hash: str
    approved_at: str
    status: str = "current"
    invalidated_at: Optional[str] = None
    invalidated_reason: Optional[str] = None
    audit_evidence: dict[str, Any] = Field(default_factory=dict)


class WebstoreTermsAcceptance(BaseDoc):
    tenant_id: str
    webstore_id: str
    terms_version: str
    portal_identity_id: str
    acceptor_name: Optional[str] = None
    acceptor_email: Optional[str] = None
    accepted_at: str
    packet_id: Optional[str] = None
    packet_version: Optional[StrictInt] = Field(default=None, ge=1)
    terms_snapshot: dict[str, Any] = Field(default_factory=dict)
    fee_summary_snapshot: dict[str, Any] = Field(default_factory=dict)
    audit_evidence: dict[str, Any] = Field(default_factory=dict)
    status: str = "current"


class WebstoreChangeRequest(BaseDoc):
    tenant_id: str
    webstore_id: str
    packet_id: str
    packet_version: StrictInt = Field(ge=1)
    category: str
    affected_item_ref: Optional[str] = None
    owner_comment: str
    status: WebstoreChangeRequestStatus = "open"
    portal_identity_id: str
    owner_visible_history: list[dict[str, Any]] = Field(default_factory=list)
    staff_only_history: list[dict[str, Any]] = Field(default_factory=list)
    resolved_at: Optional[str] = None


class WebstoreBuyerOrder(BaseDoc):
    tenant_id: str
    number: Optional[int] = None
    webstore_id: str
    buyer_name: str
    buyer_email: str
    buyer_phone: Optional[str] = None
    line_items: list[dict[str, Any]] = Field(default_factory=list)
    product_subtotal_cents: StrictInt = Field(default=0, ge=0)
    donation_cents: StrictInt = Field(default=0, ge=0)
    shipping_cents: StrictInt = Field(default=0, ge=0)
    tax_cents: StrictInt = Field(default=0, ge=0)
    total_cents: StrictInt = Field(default=0, ge=0)
    currency: str = "usd"
    status: BuyerOrderStatus = "new"
    payment_status: str = "pending"
    fulfillment_status: str = "not_started"
    stripe_connect_checkout_id: Optional[str] = None
    checkout_url: Optional[str] = None
    idempotency_key: Optional[str] = None
    bridged_order_id: Optional[str] = None
    bridge_status: str = "not_started"


class WebstorePurchaseIntent(BaseDoc):
    tenant_id: str
    webstore_id: str
    public_slug: str
    buyer_name: str
    buyer_email: str
    buyer_phone: Optional[str] = None
    line_items: list[dict[str, Any]] = Field(default_factory=list)
    product_subtotal_cents: StrictInt = Field(default=0, ge=0)
    donation_cents: StrictInt = Field(default=0, ge=0)
    shipping_cents: StrictInt = Field(default=0, ge=0)
    tax_cents: StrictInt = Field(default=0, ge=0)
    discount_cents: StrictInt = Field(default=0, ge=0)
    fee_cents: StrictInt = Field(default=0, ge=0)
    total_cents: StrictInt = Field(default=0, ge=0)
    currency: str = "usd"
    status: PurchaseIntentStatus = "pending_payment"
    idempotency_key: Optional[str] = None
    canonical_customer_id: Optional[str] = None
    canonical_order_id: Optional[str] = None
    canonical_payment_id: Optional[str] = None
    provider: Optional[str] = None
    provider_payment_id: Optional[str] = None
    provider_checkout_id: Optional[str] = None
    checkout_status: str = "created"
    confirmation_token: Optional[str] = None
    verified_payment_event_id: Optional[str] = None
    production_bridge_status: str = "not_started"
    work_order_id: Optional[str] = None
    fulfillment_status: str = "not_started"
    refund_status: str = "not_refunded"
    dispute_status: str = "none"
    payout_status: str = "pending"
    immutable_snapshot: dict[str, Any] = Field(default_factory=dict)


class WebstorePaymentEvent(BaseDoc):
    tenant_id: str
    webstore_id: str
    purchase_intent_id: str
    provider: str
    provider_event_id: str
    provider_payment_id: str
    amount_cents: StrictInt = Field(ge=0)
    currency: str = "usd"
    status: PaymentEventStatus = "processing"
    canonical_customer_id: Optional[str] = None
    canonical_order_id: Optional[str] = None
    canonical_payment_id: Optional[str] = None
    failure_code: Optional[str] = None
    failure_reason: Optional[str] = None
    processed_at: Optional[str] = None
    raw_event_snapshot: dict[str, Any] = Field(default_factory=dict)


class WebstoreLedgerEntry(BaseDoc):
    tenant_id: str
    webstore_id: str
    buyer_order_id: Optional[str] = None
    entry_type: LedgerEntryType
    amount_cents: StrictInt
    currency: str = "usd"
    basis_amount_cents: Optional[StrictInt] = None
    snapshot_basis_points: Optional[StrictInt] = Field(default=None, ge=0, le=10000)
    source_type: str
    source_id: str
    status: LedgerEntryStatus = "posted"
    reversal_of_ledger_entry_id: Optional[str] = None
    notes: Optional[str] = None


class WebstoreActivity(BaseDoc):
    tenant_id: str
    webstore_id: str
    actor_type: str
    actor_id: Optional[str] = None
    actor_email: Optional[str] = None
    action: str
    entity_type: str
    entity_id: str
    summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class WebstoreAIUsageEvent(BaseDoc):
    tenant_id: str
    webstore_id: str
    action: str
    status: AIUsageStatus = "drafted"
    prompt_source: Optional[str] = None
    output_snapshot: dict[str, Any] = Field(default_factory=dict)
    reviewed_by_user_id: Optional[str] = None
    reviewed_at: Optional[str] = None


class WebstoreStripeConnectRecord(BaseDoc):
    tenant_id: str
    webstore_id: str
    owner_id: Optional[str] = None
    record_type: str
    status: StripeBoundaryStatus = "local_only"
    stripe_account_id: Optional[str] = None
    stripe_checkout_session_id: Optional[str] = None
    checkout_url: Optional[str] = None
    amount_cents: Optional[StrictInt] = Field(default=None, ge=0)
    currency: str = "usd"
    idempotency_key: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
