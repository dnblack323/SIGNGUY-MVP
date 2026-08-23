"""EC14 - staff Webstores manager routes."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from ..core.permissions import Perm
from ..deps import get_current_user, require_permission
from ..services import webstore_payments
from ..services import webstore_orders as webstore_orders_svc
from ..services import webstore_production
from ..services import webstore_reports
from ..services import webstore_setup as setup_svc
from ..services import webstore_branding as branding_svc
from ..services import webstores as svc
from ..services.webstore_branding import WebstoreBrandingError
from ..services.webstore_setup import WebstoreSetupError
from ..services.webstores import WebstoreError



def _raise(e: WebstoreError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


def _raise_setup(e: WebstoreSetupError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


def _raise_branding(e: WebstoreBrandingError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


class OwnerIn(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    organization: Optional[str] = None
    customer_id: Optional[str] = None
    create_portal_identity: bool = True


class WebstoreIn(BaseModel):
    owner_id: str
    name: str
    slug: Optional[str] = None
    store_type: str = "general"
    description: Optional[str] = None
    branding: dict[str, Any] = Field(default_factory=dict)
    direct_owner_payout_required: bool = False
    stripe_onboarding_required: bool = False
    deadline_at: Optional[str] = None
    target_launch_at: Optional[str] = None
    event_start_at: Optional[str] = None
    event_location: Optional[str] = None
    setup_profile: dict[str, Any] = Field(default_factory=dict)
    setup_requirements: dict[str, Any] = Field(default_factory=dict)
    store_settings: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None
    send_owner_invitation: bool = True
    additional_owner_emails: list[str] = Field(default_factory=list)
    manager_emails: list[str] = Field(default_factory=list)


class WebstorePatchIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    branding: Optional[dict[str, Any]] = None
    store_type: Optional[str] = None
    terms_fee_acknowledged: Optional[bool] = None
    required_terms_version: Optional[str] = None
    direct_owner_payout_required: Optional[bool] = None
    stripe_onboarding_required: Optional[bool] = None
    payment_readiness_status: Optional[str] = None
    store_settings: Optional[dict[str, Any]] = None
    deadline_at: Optional[str] = None
    target_launch_at: Optional[str] = None
    event_start_at: Optional[str] = None
    event_location: Optional[str] = None
    intended_launch_at: Optional[str] = None
    intended_close_at: Optional[str] = None
    launch_timezone: Optional[str] = None
    confirm_type_change: Optional[bool] = None
    type_change_reason: Optional[str] = None
    impact_review_acknowledged: Optional[bool] = None


class StatusIn(BaseModel):
    status: str
    reason: Optional[str] = None


class LifecycleTransitionIn(BaseModel):
    state: str
    reason: Optional[str] = None


class RelaunchIn(BaseModel):
    reason: Optional[str] = None


class QuestionnaireSendIn(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None


class LifecycleRevisionIn(BaseModel):
    expected_revision: StrictInt = Field(ge=1)


class VerifiedPaymentHandoffIn(BaseModel):
    purchase_intent_id: str = Field(min_length=1, max_length=120)


class TemplateIn(BaseModel):
    template_name: str
    product_category: str
    product_type: str
    scope: str = "tenant"
    status: str = "active"
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
    platform_fee_basis_points: StrictInt = Field(default=0, ge=0, le=10000)
    internal_notes: Optional[str] = None
    active: bool = True
    webstore_id: Optional[str] = None


class TemplatePatchIn(BaseModel):
    expected_revision: StrictInt = Field(ge=1)
    template_name: Optional[str] = None
    product_category: Optional[str] = None
    product_type: Optional[str] = None
    status: Optional[str] = None
    default_title: Optional[str] = None
    default_short_description: Optional[str] = None
    default_description: Optional[str] = None
    suggested_category_name: Optional[str] = None
    production_method: Optional[str] = None
    supplier_source_info: Optional[str] = None
    default_production_notes: Optional[str] = None
    default_customer_images: Optional[dict[str, Any]] = None
    default_artwork_associations: Optional[list[dict[str, Any]]] = None
    default_mockup_associations: Optional[list[dict[str, Any]]] = None
    best_store_types: Optional[list[str]] = None
    default_variants: Optional[list[dict[str, Any]]] = None
    mockup_supported: Optional[bool] = None
    suggested_production_cost_cents: Optional[StrictInt] = Field(default=None, ge=0)
    suggested_selling_price_cents: Optional[StrictInt] = Field(default=None, ge=0)
    suggested_store_owner_share_cents: Optional[StrictInt] = Field(default=None, ge=0)
    platform_fee_basis_points: Optional[StrictInt] = Field(default=None, ge=0, le=10000)
    internal_notes: Optional[str] = None
    webstore_id: Optional[str] = None


class ProductIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_template_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    name: Optional[str] = None
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
    production_cost_cents: Optional[StrictInt] = Field(default=None, ge=0)
    selling_price_cents: Optional[StrictInt] = Field(default=None, ge=0)
    store_owner_share_cents: Optional[StrictInt] = Field(default=None, ge=0)
    fundraiser_share_cents: Optional[StrictInt] = Field(default=None, ge=0)
    platform_fee_basis_points: Optional[StrictInt] = Field(default=None, ge=0, le=10000)
    fulfillment_methods: Optional[list[str]] = None
    default_fulfillment_method: Optional[str] = None
    pickup_instructions: Optional[str] = None
    shipping_cost_cents: Optional[StrictInt] = Field(default=None, ge=0)
    variants: Optional[list[dict[str, Any]]] = None
    personalization_enabled: bool = False
    personalization_fields: list[dict[str, Any]] = Field(default_factory=list)
    bundle_items: list[dict[str, Any]] = Field(default_factory=list)
    inventory_policy: str = "not_tracked"
    inventory_quantity: Optional[StrictInt] = Field(default=None, ge=0)
    display_order: Optional[StrictInt] = Field(default=None, ge=0)
    launch_packet_eligible: bool = False
    launch_packet_include: bool = False
    image_file_ids: list[str] = Field(default_factory=list)
    customer_images: dict[str, Any] = Field(default_factory=dict)
    artwork_associations: list[dict[str, Any]] = Field(default_factory=list)
    mockup_associations: list[dict[str, Any]] = Field(default_factory=list)
    production_notes: Optional[str] = None
    public: bool = False
    featured: bool = False
    status: str = "draft"


class ProductPatchIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    expected_revision: StrictInt = Field(ge=1)
    name: Optional[str] = None
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
    production_cost_cents: Optional[StrictInt] = Field(default=None, ge=0)
    selling_price_cents: Optional[StrictInt] = Field(default=None, ge=0)
    store_owner_share_cents: Optional[StrictInt] = Field(default=None, ge=0)
    fundraiser_share_cents: Optional[StrictInt] = Field(default=None, ge=0)
    platform_fee_basis_points: Optional[StrictInt] = Field(default=None, ge=0, le=10000)
    fulfillment_methods: Optional[list[str]] = None
    default_fulfillment_method: Optional[str] = None
    pickup_instructions: Optional[str] = None
    shipping_cost_cents: Optional[StrictInt] = Field(default=None, ge=0)
    variants: Optional[list[dict[str, Any]]] = None
    personalization_enabled: Optional[bool] = None
    personalization_fields: Optional[list[dict[str, Any]]] = None
    bundle_items: Optional[list[dict[str, Any]]] = None
    inventory_policy: Optional[str] = None
    inventory_quantity: Optional[StrictInt] = Field(default=None, ge=0)
    display_order: Optional[StrictInt] = Field(default=None, ge=0)
    launch_packet_eligible: Optional[bool] = None
    launch_packet_include: Optional[bool] = None
    customer_images: Optional[dict[str, Any]] = None
    artwork_associations: Optional[list[dict[str, Any]]] = None
    mockup_associations: Optional[list[dict[str, Any]]] = None
    production_notes: Optional[str] = None
    public: Optional[bool] = None
    featured: Optional[bool] = None
    status: Optional[str] = None


class CategoryIn(BaseModel):
    name: str
    description: Optional[str] = None


class CategoryPatchIn(BaseModel):
    expected_revision: StrictInt = Field(ge=1)
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class ArtworkIn(BaseModel):
    product_id: Optional[str] = None
    file_id: Optional[str] = None
    original_file_id: Optional[str] = None
    original_url: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    purpose: Optional[str] = None
    notes: Optional[str] = None


class MockupIn(BaseModel):
    product_id: Optional[str] = None
    artwork_id: Optional[str] = None
    mockup_file_id: Optional[str] = None
    generation_source: str = "manual"
    purpose: Optional[str] = None
    alt_text: Optional[str] = None
    staff_note: Optional[str] = None
    status: str = "generated"
    shop_approved: bool = False
    owner_visible: bool = False
    notes: Optional[str] = None


class ProductDuplicateIn(BaseModel):
    expected_revision: StrictInt = Field(ge=1)
    name: Optional[str] = None


class ProductReorderIn(BaseModel):
    product_ids: list[str] = Field(default_factory=list)


class ProductApprovalSubmitIn(BaseModel):
    expected_revision: StrictInt = Field(ge=1)
    comment: Optional[str] = None


class MockupApprovalSubmitIn(BaseModel):
    comment: Optional[str] = None


class AIContractIn(BaseModel):
    action: str
    status: str = "drafted"
    prompt_source: Optional[str] = None
    output_snapshot: dict[str, Any] = Field(default_factory=dict)
    reviewed_by_user_id: Optional[str] = None
    reviewed_at: Optional[str] = None


class ProductAIActionPreviewIn(BaseModel):
    action: str


class ProductAIActionRunIn(BaseModel):
    action: str
    confirmed_credit_charge_credits: StrictInt = Field(ge=0)
    prompt: Optional[str] = None
    context_notes: Optional[str] = None
    idempotency_key: Optional[str] = None


class LaunchPacketIn(BaseModel):
    promotion_copy: Optional[str] = None
    qr_code_url: Optional[str] = None
    share_url: Optional[str] = None


class ChangeRequestUpdateIn(BaseModel):
    status: str
    response: Optional[str] = None
    internal_note: Optional[str] = None


class PlatformFeeReversalIn(BaseModel):
    refund_basis_amount_cents: StrictInt = Field(gt=0)


class WebstoreRefundIn(BaseModel):
    amount_cents: Optional[StrictInt] = Field(default=None, gt=0)
    reason: str
    idempotency_key: Optional[str] = None


class AssignmentIn(BaseModel):
    role: str = "owner"
    email: str
    name: Optional[str] = None
    owner_id: Optional[str] = None
    is_primary_owner: bool = False
    send_invitation: bool = True


class RevokeAssignmentIn(BaseModel):
    reason: Optional[str] = None


class PrimaryOwnerIn(BaseModel):
    assignment_id: str
    confirm: bool
    reason: str


class BrandingDraftIn(BaseModel):
    content: dict[str, Any] = Field(default_factory=dict)


class BrandingReviewIn(BaseModel):
    note: Optional[str] = None


class QuestionnaireTemplateIn(BaseModel):
    store_type: str = "general"
    title: Optional[str] = None
    version: int = 1
    sections: list[dict[str, Any]] = Field(default_factory=list)
    status: str = "active"


class QuestionnaireReturnIn(BaseModel):
    reason: str


class AnswerApplicationIn(BaseModel):
    submission_id: str
    selected_answer_keys: list[str] = Field(default_factory=list)
    proposed_values: dict[str, Any] = Field(default_factory=dict)
    reason: Optional[str] = None
    idempotency_key: Optional[str] = None


class ReverseApplicationIn(BaseModel):
    reason: str
    idempotency_key: Optional[str] = None


class RemoveFileIn(BaseModel):
    reason: Optional[str] = None


async def _read_upload_limited(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total = 0
    max_bytes = setup_svc.MAX_SETUP_FILE_BYTES
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise WebstoreSetupError("file_too_large", "Setup files must be 50 MB or smaller", 413)
        chunks.append(chunk)
    return b"".join(chunks)



__all__ = [name for name in globals() if not name.startswith("__")]
