"""EC13 Phase 13A - commercial billing catalog routes."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from ..core.permissions import Perm, permissions_for_role
from ..deps import get_current_user
from ..services import commercial_catalog as svc
from ..services.commercial_catalog import CommercialCatalogError

router = APIRouter(prefix="/commercial", tags=["commercial"])


def _raise(e: CommercialCatalogError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


async def commercial_read_user(user: dict = Depends(get_current_user)) -> dict:
    role_permissions = set(permissions_for_role(user.get("role", "staff")))
    if Perm.SUBSCRIPTION_READ.value in role_permissions:
        return user
    try:
        svc.require_platform_admin(user)
        return user
    except CommercialCatalogError:
        raise HTTPException(status_code=403, detail="Missing permission: subscription:read")


class CatalogVersionIn(BaseModel):
    version: str
    effective_at: Optional[str] = None
    notes: Optional[str] = None


class CatalogVersionUpdateIn(BaseModel):
    effective_at: Optional[str] = None
    notes: Optional[str] = None


class ProductIn(BaseModel):
    catalog_version_id: str
    product_key: str
    name: str
    description: Optional[str] = None
    product_type: str
    status: str = "draft"
    owner_checkpoint: Optional[str] = None
    requires_owner_activation: bool = True
    publishable: bool = False
    stripe_sync_enabled: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductUpdateIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    owner_checkpoint: Optional[str] = None
    requires_owner_activation: Optional[bool] = None
    publishable: Optional[bool] = None
    stripe_sync_enabled: Optional[bool] = None
    metadata: Optional[dict[str, Any]] = None


class PriceIn(BaseModel):
    catalog_version_id: str
    product_id: str
    price_key: str
    billing_interval: str
    currency: str = "usd"
    amount_cents: StrictInt = Field(ge=0)
    is_active: bool = False
    is_public: bool = False
    is_stripe_syncable: bool = False
    stripe_product_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    approved_by_owner: bool = False
    approved_at: Optional[str] = None
    effective_at: Optional[str] = None


class PriceUpdateIn(BaseModel):
    price_key: Optional[str] = None
    billing_interval: Optional[str] = None
    currency: Optional[str] = None
    amount_cents: Optional[StrictInt] = Field(default=None, ge=0)
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None
    is_stripe_syncable: Optional[bool] = None
    stripe_product_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    approved_by_owner: Optional[bool] = None
    approved_at: Optional[str] = None
    effective_at: Optional[str] = None
    retired_at: Optional[str] = None


class PriceRevisionIn(BaseModel):
    price_key: str
    billing_interval: Optional[str] = None
    currency: Optional[str] = None
    amount_cents: StrictInt = Field(ge=0)
    is_active: bool = False
    is_public: bool = False
    is_stripe_syncable: bool = False
    approved_by_owner: bool = False
    approved_at: Optional[str] = None
    effective_at: Optional[str] = None


class EntitlementRuleIn(BaseModel):
    catalog_version_id: str
    product_id: str
    feature_key: str
    entitlement_scope: str
    enabled: bool = True
    quota: Optional[StrictInt] = Field(default=None, ge=0)
    quota_interval: str = "none"
    expires_with_subscription: bool = True
    source_priority: StrictInt = Field(default=100, ge=0)


class FounderContractIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    tenant_id: str
    founder_slot_number: Optional[StrictInt] = Field(default=None, ge=1, le=25)
    founder_status: str
    source: str = "manual_owner_decision"
    migration_verified_at: Optional[str] = None
    migration_notes: Optional[str] = None


class PlatformFeeScheduleIn(BaseModel):
    catalog_version_id: str
    fee_key: str
    account_status: str
    transaction_type: str
    rate_basis_points: StrictInt = Field(ge=0, le=10000)
    is_active: bool = False
    effective_at: Optional[str] = None
    retired_at: Optional[str] = None


class PlatformFeeTransactionIn(BaseModel):
    tenant_id: str
    source_transaction_type: str
    source_transaction_id: str
    fee_schedule_id: Optional[str] = None
    basis_amount_cents: StrictInt = Field(gt=0)
    platform_fee_cents: StrictInt = Field(gt=0)
    currency: str = "usd"
    snapshot_rate_basis_points: StrictInt = Field(ge=0, le=10000)
    provider_fee_cents: Optional[StrictInt] = Field(default=None, ge=0)


class PlatformFeeReversalIn(BaseModel):
    refund_basis_amount_cents: StrictInt = Field(gt=0)


class PlatformFeeAdjustmentIn(BaseModel):
    platform_fee_cents: StrictInt
    basis_amount_cents: StrictInt = 0
    adjustment_reason: str


@router.get("/catalog/versions")
async def list_catalog_versions(user: dict = Depends(commercial_read_user)) -> dict:
    return await svc.list_catalog_versions()


@router.post("/catalog/versions", status_code=201)
async def create_catalog_version(payload: CatalogVersionIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_catalog_version(user, payload.model_dump(exclude_none=True))
    except CommercialCatalogError as e:
        _raise(e)


@router.patch("/catalog/versions/{catalog_version_id}")
async def update_catalog_version(catalog_version_id: str, payload: CatalogVersionUpdateIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.update_catalog_version(user, catalog_version_id, payload.model_dump(exclude_unset=True))
    except CommercialCatalogError as e:
        _raise(e)


@router.post("/catalog/versions/{catalog_version_id}/publish")
async def publish_catalog_version(catalog_version_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.publish_catalog_version(user, catalog_version_id)
    except CommercialCatalogError as e:
        _raise(e)


@router.get("/catalog/products")
async def list_products(
    status: Optional[str] = None,
    product_type: Optional[str] = None,
    user: dict = Depends(commercial_read_user),
) -> dict:
    return await svc.list_products(status=status, product_type=product_type)


@router.post("/catalog/products", status_code=201)
async def create_product(payload: ProductIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_product(user, payload.model_dump(exclude_none=True))
    except CommercialCatalogError as e:
        _raise(e)


@router.patch("/catalog/products/{product_id}")
async def update_product(product_id: str, payload: ProductUpdateIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.update_product(user, product_id, payload.model_dump(exclude_unset=True))
    except CommercialCatalogError as e:
        _raise(e)


@router.get("/catalog/products/{product_id}/purchase-eligibility")
async def product_purchase_eligibility(product_id: str, user: dict = Depends(commercial_read_user)) -> dict:
    try:
        return await svc.purchase_eligibility(product_id)
    except CommercialCatalogError as e:
        _raise(e)


@router.get("/catalog/prices")
async def list_prices(product_id: Optional[str] = None, user: dict = Depends(commercial_read_user)) -> dict:
    return await svc.list_prices(product_id=product_id)


@router.post("/catalog/prices", status_code=201)
async def create_price(payload: PriceIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_price(user, payload.model_dump(exclude_none=True))
    except CommercialCatalogError as e:
        _raise(e)


@router.patch("/catalog/prices/{price_id}")
async def update_price(price_id: str, payload: PriceUpdateIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.update_price(user, price_id, payload.model_dump(exclude_unset=True))
    except CommercialCatalogError as e:
        _raise(e)


@router.post("/catalog/prices/{price_id}/revisions", status_code=201)
async def revise_price(price_id: str, payload: PriceRevisionIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.revise_price(user, price_id, payload.model_dump(exclude_none=True))
    except CommercialCatalogError as e:
        _raise(e)


@router.get("/catalog/entitlement-rules")
async def list_entitlement_rules(product_id: Optional[str] = None, user: dict = Depends(commercial_read_user)) -> dict:
    return await svc.list_entitlement_rules(product_id=product_id)


@router.post("/catalog/entitlement-rules", status_code=201)
async def create_entitlement_rule(payload: EntitlementRuleIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_entitlement_rule(user, payload.model_dump(exclude_none=True))
    except CommercialCatalogError as e:
        _raise(e)


@router.get("/founder-contracts")
async def list_founder_contracts(
    tenant_id: Optional[str] = Query(default=None),
    user: dict = Depends(commercial_read_user),
) -> dict:
    try:
        return await svc.list_founder_contracts(user, tenant_id=tenant_id)
    except CommercialCatalogError as e:
        _raise(e)


@router.post("/founder-contracts", status_code=201)
async def create_founder_contract(payload: FounderContractIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_founder_contract(user, payload.model_dump(exclude_none=True))
    except CommercialCatalogError as e:
        _raise(e)


@router.get("/platform-fee-schedules")
async def list_platform_fee_schedules(user: dict = Depends(commercial_read_user)) -> dict:
    return await svc.list_platform_fee_schedules()


@router.post("/platform-fee-schedules", status_code=201)
async def create_platform_fee_schedule(payload: PlatformFeeScheduleIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_platform_fee_schedule(user, payload.model_dump(exclude_none=True))
    except CommercialCatalogError as e:
        _raise(e)


@router.post("/platform-fee-transactions", status_code=201)
async def create_platform_fee_transaction(payload: PlatformFeeTransactionIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_platform_fee_transaction(user, payload.model_dump(exclude_none=True))
    except CommercialCatalogError as e:
        _raise(e)


@router.post("/platform-fee-transactions/{transaction_id}/reversals", status_code=201)
async def create_platform_fee_reversal(transaction_id: str, payload: PlatformFeeReversalIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_platform_fee_reversal(user, transaction_id, payload.refund_basis_amount_cents)
    except CommercialCatalogError as e:
        _raise(e)


@router.post("/platform-fee-transactions/{transaction_id}/adjustments", status_code=201)
async def create_platform_fee_adjustment(transaction_id: str, payload: PlatformFeeAdjustmentIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_platform_fee_adjustment(user, transaction_id, payload.model_dump())
    except CommercialCatalogError as e:
        _raise(e)
