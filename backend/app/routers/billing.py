"""EC13 tenant billing routes."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, StrictInt

from ..deps import get_current_user
from ..services import tenant_billing as svc
from ..services.tenant_billing import TenantBillingError

router = APIRouter(prefix="/billing", tags=["billing"])


def _raise(e: TenantBillingError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


class BillingAccountIn(BaseModel):
    tenant_id: Optional[str] = None
    billing_email: Optional[str] = None
    terms_version: Optional[str] = None


class CheckoutIn(BaseModel):
    session_type: str
    idempotency_key: str
    success_url: str
    cancel_url: str
    price_id: Optional[str] = None
    amount_cents: Optional[StrictInt] = Field(default=None, ge=0)
    setup_package_key: Optional[str] = None


class ExtendedTrialCheckoutIn(BaseModel):
    idempotency_key: str
    success_url: str
    cancel_url: str


class SetupCheckoutIn(BaseModel):
    package_key: str
    idempotency_key: str
    success_url: str
    cancel_url: str


class SetupWaiverIn(BaseModel):
    tenant_id: str
    package_key: str
    reason: str


class PortalIn(BaseModel):
    return_url: str


class CancelIn(BaseModel):
    reason: Optional[str] = None


class DowngradeIn(BaseModel):
    price_id: str


class GraceIn(BaseModel):
    grace_until: str
    reason: str


class SuspendIn(BaseModel):
    reason: str


class AssessFeeIn(BaseModel):
    payment_id: str
    transaction_type: str = "standard_customer_payment"


@router.get("/state")
async def get_state(tenant_id: Optional[str] = Query(default=None), user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.billing_state(user, tenant_id=tenant_id)
    except TenantBillingError as e:
        _raise(e)


@router.post("/account", status_code=201)
async def ensure_account(payload: BillingAccountIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.ensure_billing_account(
            user,
            tenant_id=payload.tenant_id,
            billing_email=payload.billing_email,
            terms_version=payload.terms_version,
        )
    except TenantBillingError as e:
        _raise(e)


@router.post("/trials/free", status_code=201)
async def start_free_trial(user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.start_free_trial(user)
    except TenantBillingError as e:
        _raise(e)


@router.post("/trials/extended-checkout", status_code=201)
async def start_extended_trial_checkout(payload: ExtendedTrialCheckoutIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.start_extended_trial_checkout(
            user,
            idempotency_key=payload.idempotency_key,
            success_url=payload.success_url,
            cancel_url=payload.cancel_url,
        )
    except TenantBillingError as e:
        _raise(e)


@router.post("/checkout-sessions", status_code=201)
async def create_checkout_session(payload: CheckoutIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_checkout_session(
            user,
            session_type=payload.session_type,
            idempotency_key=payload.idempotency_key,
            success_url=payload.success_url,
            cancel_url=payload.cancel_url,
            price_id=payload.price_id,
            amount_cents=payload.amount_cents,
            setup_package_key=payload.setup_package_key,
        )
    except TenantBillingError as e:
        _raise(e)


@router.post("/setup-packages/checkout", status_code=201)
async def create_setup_checkout(payload: SetupCheckoutIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_setup_package_checkout(
            user,
            package_key=payload.package_key,
            idempotency_key=payload.idempotency_key,
            success_url=payload.success_url,
            cancel_url=payload.cancel_url,
        )
    except TenantBillingError as e:
        _raise(e)


@router.post("/setup-packages/waivers", status_code=201)
async def waive_setup_package(payload: SetupWaiverIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.waive_setup_package(user, tenant_id=payload.tenant_id, package_key=payload.package_key, reason=payload.reason)
    except TenantBillingError as e:
        _raise(e)


@router.post("/portal-sessions", status_code=201)
async def create_portal_session(payload: PortalIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_billing_portal_session(user, return_url=payload.return_url)
    except (TenantBillingError, RuntimeError) as e:
        if isinstance(e, TenantBillingError):
            _raise(e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/subscriptions/{subscription_id}/cancel")
async def schedule_cancellation(subscription_id: str, payload: CancelIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.schedule_cancellation(user, subscription_id=subscription_id, reason=payload.reason)
    except TenantBillingError as e:
        _raise(e)


@router.post("/subscriptions/{subscription_id}/downgrade")
async def schedule_downgrade(subscription_id: str, payload: DowngradeIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.schedule_downgrade(user, subscription_id=subscription_id, price_id=payload.price_id)
    except TenantBillingError as e:
        _raise(e)


@router.post("/platform/subscriptions/{subscription_id}/grace")
async def apply_manual_grace(subscription_id: str, payload: GraceIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.apply_manual_grace(user, subscription_id=subscription_id, grace_until=payload.grace_until, reason=payload.reason)
    except TenantBillingError as e:
        _raise(e)


@router.post("/platform/subscriptions/{subscription_id}/suspend")
async def suspend_subscription(subscription_id: str, payload: SuspendIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.suspend_subscription(user, subscription_id=subscription_id, reason=payload.reason)
    except TenantBillingError as e:
        _raise(e)


@router.post("/platform/trials/expire")
async def expire_trials(user: dict = Depends(get_current_user)) -> dict:
    from ..services.commercial_catalog import require_platform_admin

    try:
        require_platform_admin(user)
        return await svc.expire_trials()
    except Exception as e:
        if isinstance(e, TenantBillingError):
            _raise(e)
        raise HTTPException(status_code=403, detail="Platform admin access is required")


@router.post("/platform/platform-fees/assess-payment", status_code=201)
async def assess_platform_fee(payload: AssessFeeIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.assess_platform_fee_for_payment(user, payment_id=payload.payment_id, transaction_type=payload.transaction_type)
    except TenantBillingError as e:
        _raise(e)
