"""EC13 Phase 13A - commercial billing catalog and core contracts.

These are platform subscription/catalog contracts only. They do not execute
Stripe calls, Checkout Sessions, tenant subscription changes, EC2 entitlement
mutations, EC4 customer payments, or Webstore commerce.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field, StrictInt

from .base import BaseDoc

CatalogStatus = Literal["draft", "published", "retired"]
CommercialProductType = Literal[
    "core",
    "bundle",
    "addon",
    "standalone",
    "setup_package",
    "credit_pack",
    "trial_extension",
    "usage_category",
]
CommercialProductStatus = Literal["draft", "active", "inactive", "unavailable", "retired"]
BillingInterval = Literal["none", "monthly", "annual", "one_time", "usage"]
EntitlementScope = Literal["plan", "addon", "standalone", "trial", "setup", "usage"]
QuotaInterval = Literal["none", "monthly", "annual", "lifetime"]
FounderStatus = Literal["not_founder", "pending", "active", "grace", "lost", "revoked"]
FounderSource = Literal["manual_owner_decision", "migration_review", "subscription_activation"]
PlatformFeeAccountStatus = Literal["founder_intro", "founder_active", "ga", "custom"]
PlatformFeeTransactionType = Literal["standard_customer_payment", "webstore_sale"]
PlatformFeeTransactionStatus = Literal["assessed", "reversed", "partially_reversed", "adjusted"]
PlatformFeeSourceType = Literal["ec4_customer_payment", "webstore_sale", "manual_contract_test"]


class CommercialCatalogVersion(BaseDoc):
    version: str
    status: CatalogStatus = "draft"
    effective_at: Optional[str] = None
    retired_at: Optional[str] = None
    notes: Optional[str] = None
    created_by_user_id: str
    published_by_user_id: Optional[str] = None
    published_at: Optional[str] = None


class CommercialProduct(BaseDoc):
    catalog_version_id: str
    product_key: str
    name: str
    description: Optional[str] = None
    product_type: CommercialProductType
    status: CommercialProductStatus = "draft"
    owner_checkpoint: Optional[str] = None
    requires_owner_activation: bool = True
    publishable: bool = False
    stripe_sync_enabled: bool = False
    metadata: dict = Field(default_factory=dict)


class CommercialPrice(BaseDoc):
    catalog_version_id: str
    product_id: str
    price_key: str
    billing_interval: BillingInterval
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
    retired_at: Optional[str] = None
    replaces_price_id: Optional[str] = None


class CommercialEntitlementRule(BaseDoc):
    catalog_version_id: str
    product_id: str
    feature_key: str
    entitlement_scope: EntitlementScope
    enabled: bool = True
    quota: Optional[StrictInt] = Field(default=None, ge=0)
    quota_interval: QuotaInterval = "none"
    expires_with_subscription: bool = True
    source_priority: StrictInt = Field(default=100, ge=0)


class FounderTenantContract(BaseDoc):
    tenant_id: str
    founder_slot_number: Optional[StrictInt] = Field(default=None, ge=1, le=25)
    founder_status: FounderStatus
    source: FounderSource = "manual_owner_decision"
    ec12_founder_access_preserved: bool = True
    migration_verified_at: Optional[str] = None
    migration_notes: Optional[str] = None
    created_by_user_id: str


class PlatformFeeSchedule(BaseDoc):
    catalog_version_id: str
    fee_key: str
    account_status: PlatformFeeAccountStatus
    transaction_type: PlatformFeeTransactionType
    rate_basis_points: StrictInt = Field(ge=0, le=10000)
    is_active: bool = False
    effective_at: Optional[str] = None
    retired_at: Optional[str] = None


class PlatformFeeTransactionContract(BaseDoc):
    tenant_id: str
    source_transaction_type: PlatformFeeSourceType
    source_transaction_id: str
    fee_schedule_id: Optional[str] = None
    basis_amount_cents: StrictInt
    platform_fee_cents: StrictInt
    currency: str = "usd"
    snapshot_rate_basis_points: StrictInt = Field(ge=0, le=10000)
    status: PlatformFeeTransactionStatus = "assessed"
    reversal_of_fee_transaction_id: Optional[str] = None
    adjustment_reason: Optional[str] = None
    provider_fee_cents: Optional[StrictInt] = Field(default=None, ge=0)
    created_by_user_id: Optional[str] = None
