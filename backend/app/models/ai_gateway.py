"""EC16 - shared AI gateway, metering, cost, credit, and governance contracts."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field, StrictInt

from .base import BaseDoc

ProviderStatus = Literal["draft", "active", "disabled", "retired"]
ModelStatus = Literal["draft", "active", "disabled", "retired"]
CapabilityStatus = Literal["draft", "active", "disabled", "retired"]
PromptStatus = Literal["draft", "published", "retired"]
ContextStatus = Literal["created", "redacted", "used", "expired", "discarded"]
ActionStatus = Literal["received", "blocked", "reserved", "executing", "succeeded", "failed", "refunded", "canceled"]
UsageStatus = Literal["estimated", "final", "reversed"]
ProviderCostStatus = Literal["estimated", "actual", "adjusted", "reconciled"]
CreditAccountStatus = Literal["active", "restricted", "suspended", "closed"]
CreditLedgerEntryType = Literal["grant", "reserve", "commit", "release", "refund", "adjustment", "expiration"]
GovernanceStatus = Literal["draft", "active", "inactive", "retired"]
GovernanceScopeType = Literal["global", "tenant", "capability", "model"]
ZeroCreditBehavior = Literal["block", "allow_non_billable"]
BudgetAlertStatus = Literal["open", "acknowledged", "resolved"]
BudgetAlertType = Literal["low_credit", "zero_credit", "rate_limit", "spend_cap", "provider_cost"]
HealthStatus = Literal["healthy", "degraded", "disabled", "failed"]


class AIProviderConfig(BaseDoc):
    provider_key: str
    display_name: str
    status: ProviderStatus = "draft"
    credential_mode: str = "platform_managed"
    supported_modalities: list[str] = Field(default_factory=list)
    byok_supported: bool = False
    credential_reference: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AIModelProfile(BaseDoc):
    provider_config_id: str
    provider_key: str
    model_key: str
    display_name: str
    task_category: str
    intensity: str = "standard"
    status: ModelStatus = "draft"
    input_unit_label: str = "input_token"
    output_unit_label: str = "output_token"
    estimated_input_cost_micros_per_unit: StrictInt = Field(default=0, ge=0)
    estimated_output_cost_micros_per_unit: StrictInt = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AICapability(BaseDoc):
    capability_key: str
    display_name: str
    feature_key: str
    action_key: str
    entitlement_feature_key: Optional[str] = None
    status: CapabilityStatus = "draft"
    billable: bool = True
    default_credit_charge: StrictInt = Field(default=1, ge=0)
    allowed_model_profile_ids: list[str] = Field(default_factory=list)
    context_requirements: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AIPromptVersion(BaseDoc):
    capability_key: str
    prompt_key: str
    version: str
    status: PromptStatus = "draft"
    template: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    checksum: Optional[str] = None
    published_by_user_id: Optional[str] = None
    published_at: Optional[str] = None
    retired_at: Optional[str] = None


class AIContextPacket(BaseDoc):
    tenant_id: str
    user_id: str
    status: ContextStatus = "created"
    source_entity_type: Optional[str] = None
    source_entity_id: Optional[str] = None
    source_links: list[dict[str, Any]] = Field(default_factory=list)
    consent_flags: dict[str, bool] = Field(default_factory=dict)
    redaction_metadata: dict[str, Any] = Field(default_factory=dict)
    expires_at: Optional[str] = None
    payload_summary: dict[str, Any] = Field(default_factory=dict)


class AIActionRequest(BaseDoc):
    tenant_id: str
    user_id: str
    capability_key: str
    feature_key: str
    action_key: str
    provider_key: Optional[str] = None
    model_key: Optional[str] = None
    model_profile_id: Optional[str] = None
    prompt_version_id: Optional[str] = None
    context_packet_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    session_id: Optional[str] = None
    background: bool = False
    status: ActionStatus = "received"
    credit_charge_credits: StrictInt = Field(default=0, ge=0)
    reserved_credit_ledger_entry_id: Optional[str] = None
    committed_credit_ledger_entry_id: Optional[str] = None
    usage_ledger_entry_id: Optional[str] = None
    provider_cost_ledger_entry_id: Optional[str] = None
    duration_ms: StrictInt = Field(default=0, ge=0)
    result_status: Optional[str] = None
    result_summary: Optional[str] = None
    failure_reason: Optional[str] = None
    source_links: list[dict[str, Any]] = Field(default_factory=list)


class AIUsageLedgerEntry(BaseDoc):
    tenant_id: str
    user_id: str
    action_request_id: str
    capability_key: str
    feature_key: str
    action_key: str
    provider_key: Optional[str] = None
    model_key: Optional[str] = None
    input_units: StrictInt = Field(default=0, ge=0)
    output_units: StrictInt = Field(default=0, ge=0)
    duration_ms: StrictInt = Field(default=0, ge=0)
    credits_charged: StrictInt = Field(default=0, ge=0)
    status: UsageStatus = "final"
    result_status: str = "succeeded"
    session_id: Optional[str] = None
    background: bool = False
    source_links: list[dict[str, Any]] = Field(default_factory=list)
    idempotency_key: Optional[str] = None


class AIProviderCostLedgerEntry(BaseDoc):
    tenant_id: str
    action_request_id: str
    usage_ledger_entry_id: Optional[str] = None
    provider_key: str
    model_key: str
    estimated_cost_micros: StrictInt = Field(default=0, ge=0)
    actual_cost_micros: StrictInt = Field(default=0, ge=0)
    actual_cost_cents: Optional[StrictInt] = Field(default=None, ge=0)
    currency: str = "usd"
    input_units: StrictInt = Field(default=0, ge=0)
    output_units: StrictInt = Field(default=0, ge=0)
    status: ProviderCostStatus = "actual"
    provider_event_id: Optional[str] = None
    reconciliation_status: str = "unreconciled"
    idempotency_key: Optional[str] = None


class AICreditAccount(BaseDoc):
    tenant_id: str
    included_balance_credits: StrictInt = Field(default=0, ge=0)
    purchased_balance_credits: StrictInt = Field(default=0, ge=0)
    reserved_credits: StrictInt = Field(default=0, ge=0)
    billing_cycle_starts_at: Optional[str] = None
    billing_cycle_ends_at: Optional[str] = None
    low_credit_threshold_credits: StrictInt = Field(default=0, ge=0)
    status: CreditAccountStatus = "active"


class AICreditLedgerEntry(BaseDoc):
    tenant_id: str
    credit_account_id: str
    entry_type: CreditLedgerEntryType
    amount_credits: StrictInt
    included_credits_delta: StrictInt = 0
    purchased_credits_delta: StrictInt = 0
    reserved_credits_delta: StrictInt = 0
    balance_after_included_credits: StrictInt = Field(ge=0)
    balance_after_purchased_credits: StrictInt = Field(ge=0)
    reserved_after_credits: StrictInt = Field(ge=0)
    action_request_id: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    reason: Optional[str] = None
    created_by_user_id: Optional[str] = None


class AIGovernancePolicy(BaseDoc):
    scope_type: GovernanceScopeType = "global"
    scope_key: Optional[str] = None
    tenant_id: Optional[str] = None
    capability_key: Optional[str] = None
    model_profile_id: Optional[str] = None
    status: GovernanceStatus = "draft"
    zero_credit_behavior: ZeroCreditBehavior = "block"
    disabled_capability_keys: list[str] = Field(default_factory=list)
    max_requests_per_day: Optional[StrictInt] = Field(default=None, ge=0)
    max_credits_per_day: Optional[StrictInt] = Field(default=None, ge=0)
    max_cost_micros_per_day: Optional[StrictInt] = Field(default=None, ge=0)
    low_credit_threshold_credits: Optional[StrictInt] = Field(default=None, ge=0)
    effective_at: Optional[str] = None
    retired_at: Optional[str] = None
    created_by_user_id: str


class AIBudgetAlert(BaseDoc):
    tenant_id: str
    alert_type: BudgetAlertType
    status: BudgetAlertStatus = "open"
    capability_key: Optional[str] = None
    action_request_id: Optional[str] = None
    threshold_value: Optional[StrictInt] = None
    observed_value: Optional[StrictInt] = None
    summary: str
    acknowledged_by_user_id: Optional[str] = None
    acknowledged_at: Optional[str] = None
    resolved_by_user_id: Optional[str] = None
    resolved_at: Optional[str] = None


class AIProviderHealthEvent(BaseDoc):
    provider_key: str
    model_key: Optional[str] = None
    status: HealthStatus
    reason: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by_user_id: str
