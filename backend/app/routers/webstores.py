"""EC14 - staff Webstores manager routes."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, StrictInt

from ..deps import get_current_user
from ..services import webstores as svc
from ..services.webstores import WebstoreError

router = APIRouter(prefix="/webstores", tags=["webstores"])


def _raise(e: WebstoreError) -> None:
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
    stripe_payment_ready: bool = False
    deadline_at: Optional[str] = None


class WebstorePatchIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    branding: Optional[dict[str, Any]] = None
    checkout_enabled: Optional[bool] = None
    terms_fee_acknowledged: Optional[bool] = None
    direct_owner_payout_required: Optional[bool] = None
    stripe_onboarding_required: Optional[bool] = None
    stripe_payment_ready: Optional[bool] = None
    deadline_at: Optional[str] = None


class StatusIn(BaseModel):
    status: str
    reason: Optional[str] = None


class TemplateIn(BaseModel):
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
    active: bool = True


class ProductIn(BaseModel):
    source_template_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    product_type: Optional[str] = None
    sku: Optional[str] = None
    production_cost_cents: Optional[StrictInt] = Field(default=None, ge=0)
    selling_price_cents: Optional[StrictInt] = Field(default=None, ge=0)
    store_owner_share_cents: Optional[StrictInt] = Field(default=None, ge=0)
    platform_fee_basis_points: Optional[StrictInt] = Field(default=None, ge=0, le=10000)
    variants: Optional[list[dict[str, Any]]] = None
    personalization_enabled: bool = False
    image_file_ids: list[str] = Field(default_factory=list)
    production_notes: Optional[str] = None
    public: bool = False
    featured: bool = False
    status: str = "draft"


class ArtworkIn(BaseModel):
    original_file_id: Optional[str] = None
    original_url: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    notes: Optional[str] = None


class MockupIn(BaseModel):
    product_id: Optional[str] = None
    artwork_id: Optional[str] = None
    mockup_file_id: Optional[str] = None
    generation_source: str = "manual"
    status: str = "generated"
    shop_approved: bool = False
    owner_visible: bool = False
    notes: Optional[str] = None


class AIContractIn(BaseModel):
    action: str
    status: str = "drafted"
    prompt_source: Optional[str] = None
    output_snapshot: dict[str, Any] = Field(default_factory=dict)
    reviewed_by_user_id: Optional[str] = None
    reviewed_at: Optional[str] = None


class LaunchPacketIn(BaseModel):
    promotion_copy: Optional[str] = None
    qr_code_url: Optional[str] = None
    share_url: Optional[str] = None


class PlatformFeeReversalIn(BaseModel):
    refund_basis_amount_cents: StrictInt = Field(gt=0)


@router.get("")
async def list_webstores(status: Optional[str] = Query(None), user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.list_webstores(user, status=status)
    except WebstoreError as e:
        _raise(e)


@router.post("", status_code=201)
async def create_webstore(payload: WebstoreIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_webstore(user, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.get("/{webstore_id}")
async def get_webstore(webstore_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.get_webstore(user, webstore_id)
    except WebstoreError as e:
        _raise(e)


@router.patch("/{webstore_id}")
async def update_webstore(webstore_id: str, payload: WebstorePatchIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.update_webstore(user, webstore_id, payload.model_dump(exclude_unset=True))
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/status")
async def set_status(webstore_id: str, payload: StatusIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.set_webstore_status(user, webstore_id, payload.status, reason=payload.reason)
    except WebstoreError as e:
        _raise(e)


@router.get("/{webstore_id}/launch-readiness")
async def launch_readiness(webstore_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.launch_readiness(user, webstore_id)
    except WebstoreError as e:
        _raise(e)


@router.get("/{webstore_id}/reports")
async def reports(webstore_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.reports(user, webstore_id)
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/products", status_code=201)
async def create_product(webstore_id: str, payload: ProductIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_product(user, webstore_id, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.get("/{webstore_id}/products")
async def list_products(webstore_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.list_products(user, webstore_id=webstore_id)
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/artwork", status_code=201)
async def create_artwork(webstore_id: str, payload: ArtworkIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_artwork(user, webstore_id, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/mockups", status_code=201)
async def create_mockup(webstore_id: str, payload: MockupIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_mockup(user, webstore_id, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/ai-contracts", status_code=201)
async def create_ai_contract(webstore_id: str, payload: AIContractIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_ai_usage_event(user, webstore_id, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/launch-packets", status_code=201)
async def generate_launch_packet(webstore_id: str, payload: LaunchPacketIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.generate_launch_packet(user, webstore_id, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/launch-packets/{packet_id}/send")
async def send_launch_packet(webstore_id: str, packet_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.send_launch_packet(user, webstore_id, packet_id)
    except WebstoreError as e:
        _raise(e)


@router.post("/buyer-orders/{buyer_order_id}/bridge")
async def bridge_buyer_order(buyer_order_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.bridge_buyer_order_to_order(user, buyer_order_id)
    except WebstoreError as e:
        _raise(e)


@router.post("/ledger/{ledger_entry_id}/platform-fee-reversals", status_code=201)
async def reverse_platform_fee(ledger_entry_id: str, payload: PlatformFeeReversalIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.reverse_platform_fee(user, ledger_entry_id, payload.refund_basis_amount_cents)
    except WebstoreError as e:
        _raise(e)


@router.get("/owners/list")
async def list_owners(user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.list_owners(user)
    except WebstoreError as e:
        _raise(e)


@router.post("/owners", status_code=201)
async def create_owner(payload: OwnerIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_owner(user, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.get("/product-templates/list")
async def list_templates(active: Optional[bool] = Query(None), user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.list_templates(user, active=active)
    except WebstoreError as e:
        _raise(e)


@router.post("/product-templates", status_code=201)
async def create_template(payload: TemplateIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_template(user, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)
