"""EC14 - Webstores canonical data contracts."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field, StrictInt

from .base import BaseDoc

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
WebstoreProductStatus = Literal["draft", "active", "inactive", "archived"]
QuestionnaireStatus = Literal["pending", "submitted", "reviewed"]
ArtworkStatus = Literal[
    "uploaded",
    "cleanup_pending",
    "cleaned",
    "approved_for_mockups",
    "approved_for_production",
    "rejected",
]
MockupStatus = Literal["draft", "generated", "shop_approved", "owner_approved", "changes_requested"]
LaunchPacketStatus = Literal["draft", "generated", "sent_for_approval", "changes_requested", "owner_approved"]
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
    store_type: WebstoreType = "general"
    status: WebstoreStatus = "draft"
    description: Optional[str] = None
    branding: dict[str, Any] = Field(default_factory=dict)
    checkout_enabled: bool = False
    entitlement_feature_key: str = "webstores"
    terms_fee_acknowledged: bool = False
    owner_approved_at: Optional[str] = None
    owner_approved_by_portal_identity_id: Optional[str] = None
    launch_packet_id: Optional[str] = None
    direct_owner_payout_required: bool = False
    stripe_onboarding_required: bool = False
    stripe_payment_ready: bool = False
    public_url: Optional[str] = None
    deadline_at: Optional[str] = None
    launched_at: Optional[str] = None
    closed_at: Optional[str] = None
    archived_at: Optional[str] = None


class WebstoreProductTemplate(BaseDoc):
    tenant_id: str
    template_name: str
    product_category: str
    product_type: str
    default_description: Optional[str] = None
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


class WebstoreProduct(BaseDoc):
    tenant_id: str
    webstore_id: str
    source_template_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    product_type: Optional[str] = None
    sku: Optional[str] = None
    production_cost_cents: StrictInt = Field(default=0, ge=0)
    selling_price_cents: StrictInt = Field(ge=0)
    store_owner_share_cents: StrictInt = Field(default=0, ge=0)
    platform_fee_basis_points: StrictInt = Field(default=150, ge=0, le=10000)
    variants: list[dict[str, Any]] = Field(default_factory=list)
    personalization_enabled: bool = False
    image_file_ids: list[str] = Field(default_factory=list)
    mockup_ids: list[str] = Field(default_factory=list)
    production_notes: Optional[str] = None
    public: bool = False
    featured: bool = False
    status: WebstoreProductStatus = "draft"


class WebstoreQuestionnaireSubmission(BaseDoc):
    tenant_id: str
    webstore_id: str
    owner_id: str
    answers: dict[str, Any] = Field(default_factory=dict)
    known_products: list[dict[str, Any]] = Field(default_factory=list)
    open_to_suggestions: bool = True
    missing_info_flags: list[str] = Field(default_factory=list)
    status: QuestionnaireStatus = "pending"
    submitted_at: Optional[str] = None


class WebstoreArtworkFile(BaseDoc):
    tenant_id: str
    webstore_id: str
    uploaded_by_actor_type: str = "staff"
    uploaded_by_id: Optional[str] = None
    original_file_id: Optional[str] = None
    original_url: Optional[str] = None
    cleaned_file_id: Optional[str] = None
    cleaned_url: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
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
    status: MockupStatus = "draft"
    shop_approved: bool = False
    owner_visible: bool = False
    owner_approved: bool = False
    notes: Optional[str] = None


class WebstoreLaunchPacket(BaseDoc):
    tenant_id: str
    webstore_id: str
    status: LaunchPacketStatus = "draft"
    snapshot: dict[str, Any] = Field(default_factory=dict)
    pricing_summary: dict[str, Any] = Field(default_factory=dict)
    promotion_copy: Optional[str] = None
    qr_code_url: Optional[str] = None
    share_url: Optional[str] = None
    sent_at: Optional[str] = None
    owner_decision_at: Optional[str] = None
    change_request_reason: Optional[str] = None


class WebstoreBuyerOrder(BaseDoc):
    tenant_id: str
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
