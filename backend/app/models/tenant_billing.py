"""EC13 - tenant commercial billing, trials, setup purchases, and sessions."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field, StrictInt

from .base import BaseDoc

BillingAccountStatus = Literal["pending", "trialing", "active", "past_due", "restricted", "suspended", "canceled", "closed"]
SubscriptionStatus = Literal[
    "pending_checkout",
    "trialing",
    "active",
    "past_due",
    "cancellation_scheduled",
    "canceled",
    "incomplete",
    "unpaid",
]
DunningState = Literal[
    "current",
    "day_1_7_warning",
    "day_8_14_soft_restriction",
    "eligible_for_suspension",
    "suspended",
    "manually_extended",
    "resolved",
]
TrialStatus = Literal[
    "free_active",
    "free_expired",
    "extended_pending_payment",
    "extended_active",
    "extended_expired",
    "converted",
    "forfeited",
]
TrialKind = Literal["free", "extended"]
CheckoutSessionType = Literal["subscription", "setup_package", "extended_trial", "credit_pack"]
CheckoutSessionStatus = Literal["created", "completed", "expired", "canceled", "superseded"]
SetupPackageStatus = Literal["pending_payment", "paid", "waived", "refunded", "partially_refunded", "fulfilled", "canceled"]
BillingPortalSessionStatus = Literal["created", "expired"]


class TenantBillingAccount(BaseDoc):
    tenant_id: str
    billing_owner_user_id: Optional[str] = None
    billing_email: Optional[str] = None
    status: BillingAccountStatus = "pending"
    stripe_customer_id: Optional[str] = None
    terms_version: Optional[str] = None
    current_subscription_id: Optional[str] = None
    trial_record_id: Optional[str] = None
    suspended_at: Optional[str] = None
    suspension_reason: Optional[str] = None
    closed_at: Optional[str] = None


class TenantSubscription(BaseDoc):
    tenant_id: str
    billing_account_id: str
    catalog_version_id: str
    plan_product_id: str
    price_id: str
    billing_interval: str
    status: SubscriptionStatus = "pending_checkout"
    dunning_state: DunningState = "current"
    add_on_product_ids: list[str] = Field(default_factory=list)
    add_on_price_ids: list[str] = Field(default_factory=list)
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    founder_contract_id: Optional[str] = None
    current_period_start: Optional[str] = None
    current_period_end: Optional[str] = None
    first_payment_failed_at: Optional[str] = None
    last_payment_succeeded_at: Optional[str] = None
    cancel_at_period_end: bool = False
    canceled_at: Optional[str] = None
    cancellation_reason: Optional[str] = None
    scheduled_downgrade_price_id: Optional[str] = None
    scheduled_downgrade_product_id: Optional[str] = None
    scheduled_change_at: Optional[str] = None
    manual_grace_until: Optional[str] = None
    manual_grace_reason: Optional[str] = None


class TrialRecord(BaseDoc):
    tenant_id: str
    billing_account_id: str
    trial_kind: TrialKind
    status: TrialStatus
    starts_at: str
    ends_at: str
    credit_allotment: StrictInt = Field(ge=0)
    conversion_credit_cents: StrictInt = Field(default=0, ge=0)
    conversion_credit_expires_at: Optional[str] = None
    checkout_session_id: Optional[str] = None
    converted_subscription_id: Optional[str] = None
    created_by_user_id: str


class CheckoutSessionRecord(BaseDoc):
    tenant_id: str
    billing_account_id: str
    session_type: CheckoutSessionType
    status: CheckoutSessionStatus = "created"
    product_id: Optional[str] = None
    price_id: Optional[str] = None
    setup_package_key: Optional[str] = None
    amount_cents: Optional[StrictInt] = Field(default=None, ge=0)
    currency: str = "usd"
    idempotency_key: str
    stripe_checkout_session_id: Optional[str] = None
    checkout_url: Optional[str] = None
    completed_at: Optional[str] = None
    expires_at: Optional[str] = None
    superseded_at: Optional[str] = None
    created_by_user_id: str


class BillingPortalSessionRecord(BaseDoc):
    tenant_id: str
    billing_account_id: str
    status: BillingPortalSessionStatus = "created"
    stripe_billing_portal_session_id: Optional[str] = None
    portal_url: Optional[str] = None
    return_url: Optional[str] = None
    expires_at: Optional[str] = None
    created_by_user_id: str


class SetupPackagePurchase(BaseDoc):
    tenant_id: str
    billing_account_id: str
    package_key: str
    checkout_session_id: Optional[str] = None
    status: SetupPackageStatus = "pending_payment"
    amount_cents: StrictInt = Field(ge=0)
    currency: str = "usd"
    waived_by_user_id: Optional[str] = None
    waiver_reason: Optional[str] = None
    paid_at: Optional[str] = None
    refunded_at: Optional[str] = None
    fulfilled_at: Optional[str] = None
    ec19_handoff_status: str = "not_started"
