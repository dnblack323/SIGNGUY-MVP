"""EC16 shared AI gateway, metering, cost, credit, and governance routes."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, StrictInt

from ..core.permissions import Perm
from ..deps import get_current_user, require_permission
from ..services import ai_gateway as svc
from ..services.ai_gateway import AIGatewayError

router = APIRouter(prefix="/ai", tags=["ai-gateway"])


def _raise(e: AIGatewayError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


class ProviderIn(BaseModel):
    provider_key: str
    display_name: str
    status: str = "draft"
    credential_mode: str = "platform_managed"
    supported_modalities: list[str] = Field(default_factory=list)
    byok_supported: bool = False
    credential_reference: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderUpdateIn(BaseModel):
    display_name: Optional[str] = None
    status: Optional[str] = None
    credential_mode: Optional[str] = None
    supported_modalities: Optional[list[str]] = None
    byok_supported: Optional[bool] = None
    credential_reference: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class ModelProfileIn(BaseModel):
    provider_config_id: str
    model_key: str
    display_name: str
    task_category: str
    intensity: str = "standard"
    status: str = "draft"
    input_unit_label: str = "input_token"
    output_unit_label: str = "output_token"
    estimated_input_cost_micros_per_unit: StrictInt = Field(default=0, ge=0)
    estimated_output_cost_micros_per_unit: StrictInt = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CapabilityIn(BaseModel):
    capability_key: str
    display_name: str
    feature_key: str
    action_key: str
    entitlement_feature_key: Optional[str] = None
    status: str = "draft"
    billable: bool = True
    default_credit_charge: StrictInt = Field(default=1, ge=0)
    allowed_model_profile_ids: list[str] = Field(default_factory=list)
    context_requirements: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptVersionIn(BaseModel):
    capability_key: str
    prompt_key: str
    version: str
    status: str = "draft"
    template: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    checksum: Optional[str] = None


class PromptUpdateIn(BaseModel):
    capability_key: Optional[str] = None
    prompt_key: Optional[str] = None
    version: Optional[str] = None
    template: Optional[str] = None
    input_schema: Optional[dict[str, Any]] = None
    output_schema: Optional[dict[str, Any]] = None
    checksum: Optional[str] = None
    status: Optional[str] = None
    retired_at: Optional[str] = None


class CreditGrantIn(BaseModel):
    included_credits: StrictInt = Field(default=0, ge=0)
    purchased_credits: StrictInt = Field(default=0, ge=0)
    reason: str
    idempotency_key: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None


class CreditAdjustmentIn(BaseModel):
    included_credits_delta: StrictInt = 0
    purchased_credits_delta: StrictInt = 0
    reason: str
    idempotency_key: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None


class GovernancePolicyIn(BaseModel):
    scope_type: str = "global"
    scope_key: Optional[str] = None
    tenant_id: Optional[str] = None
    capability_key: Optional[str] = None
    model_profile_id: Optional[str] = None
    status: str = "draft"
    zero_credit_behavior: str = "block"
    disabled_capability_keys: list[str] = Field(default_factory=list)
    max_requests_per_day: Optional[StrictInt] = Field(default=None, ge=0)
    max_credits_per_day: Optional[StrictInt] = Field(default=None, ge=0)
    max_cost_micros_per_day: Optional[StrictInt] = Field(default=None, ge=0)
    low_credit_threshold_credits: Optional[StrictInt] = Field(default=None, ge=0)
    effective_at: Optional[str] = None
    retired_at: Optional[str] = None


class GatewayRequestIn(BaseModel):
    capability_key: str
    model_profile_id: Optional[str] = None
    prompt_version_id: Optional[str] = None
    context_packet_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    session_id: Optional[str] = None
    background: bool = False
    input_units: StrictInt = Field(default=0, ge=0)
    output_units: StrictInt = Field(default=0, ge=0)
    estimated_cost_micros: Optional[StrictInt] = Field(default=None, ge=0)
    actual_cost_cents: Optional[StrictInt] = Field(default=None, ge=0)
    credit_charge_credits: Optional[StrictInt] = Field(default=None, ge=0)
    duration_ms: StrictInt = Field(default=0, ge=0)
    source_links: list[dict[str, Any]] = Field(default_factory=list)
    provider_event_id: Optional[str] = None
    simulate_result: str = "success"


class AlertUpdateIn(BaseModel):
    status: str


class ProviderHealthIn(BaseModel):
    provider_key: str
    model_key: Optional[str] = None
    status: str
    reason: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.get("/platform/providers")
async def list_providers(user: dict = Depends(get_current_user)) -> dict:
    try:
        svc.require_platform_ai_admin(user)
        return await svc.list_provider_configs()
    except AIGatewayError as e:
        _raise(e)


@router.post("/platform/providers", status_code=201)
async def create_provider(payload: ProviderIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_provider_config(user, payload.model_dump(exclude_none=True))
    except AIGatewayError as e:
        _raise(e)


@router.patch("/platform/providers/{provider_id}")
async def update_provider(provider_id: str, payload: ProviderUpdateIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.update_provider_config(user, provider_id, payload.model_dump(exclude_unset=True))
    except AIGatewayError as e:
        _raise(e)


@router.get("/platform/models")
async def list_models(user: dict = Depends(get_current_user)) -> dict:
    try:
        svc.require_platform_ai_admin(user)
        return await svc.list_model_profiles()
    except AIGatewayError as e:
        _raise(e)


@router.post("/platform/models", status_code=201)
async def create_model(payload: ModelProfileIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_model_profile(user, payload.model_dump(exclude_none=True))
    except AIGatewayError as e:
        _raise(e)


@router.get("/platform/capabilities")
async def list_capabilities(status: Optional[str] = Query(None), user: dict = Depends(get_current_user)) -> dict:
    try:
        svc.require_platform_ai_admin(user)
        return await svc.list_capabilities(status=status)
    except AIGatewayError as e:
        _raise(e)


@router.post("/platform/capabilities", status_code=201)
async def create_capability(payload: CapabilityIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_capability(user, payload.model_dump(exclude_none=True))
    except AIGatewayError as e:
        _raise(e)


@router.post("/platform/prompts", status_code=201)
async def create_prompt(payload: PromptVersionIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_prompt_version(user, payload.model_dump(exclude_none=True))
    except AIGatewayError as e:
        _raise(e)


@router.patch("/platform/prompts/{prompt_id}")
async def update_prompt(prompt_id: str, payload: PromptUpdateIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.update_prompt_version(user, prompt_id, payload.model_dump(exclude_unset=True))
    except AIGatewayError as e:
        _raise(e)


@router.post("/platform/prompts/{prompt_id}/publish")
async def publish_prompt(prompt_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.publish_prompt_version(user, prompt_id)
    except AIGatewayError as e:
        _raise(e)


@router.post("/platform/credit-accounts/{tenant_id}/grants", status_code=201)
async def grant_credits(tenant_id: str, payload: CreditGrantIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.grant_credits(user, tenant_id, payload.model_dump(exclude_none=True))
    except AIGatewayError as e:
        _raise(e)


@router.post("/platform/credit-accounts/{tenant_id}/adjustments", status_code=201)
async def adjust_credits(tenant_id: str, payload: CreditAdjustmentIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.adjust_credits(user, tenant_id, payload.model_dump(exclude_none=True))
    except AIGatewayError as e:
        _raise(e)


@router.post("/platform/governance-policies", status_code=201)
async def create_policy(payload: GovernancePolicyIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_governance_policy(user, payload.model_dump(exclude_none=True))
    except AIGatewayError as e:
        _raise(e)


@router.get("/platform/governance-policies")
async def list_policies(user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.list_governance_policies(user)
    except AIGatewayError as e:
        _raise(e)


@router.get("/platform/dashboard")
async def platform_dashboard(user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.platform_dashboard(user)
    except AIGatewayError as e:
        _raise(e)


@router.post("/platform/provider-health", status_code=201)
async def record_provider_health(payload: ProviderHealthIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.record_provider_health(user, payload.model_dump(exclude_none=True))
    except AIGatewayError as e:
        _raise(e)


@router.get("/credits/account")
async def get_credit_account(user: dict = Depends(require_permission(Perm.AI_CREDIT_READ))) -> dict:
    return await svc.get_credit_account(user["tenant_id"])


@router.get("/credits/ledger")
async def get_credit_ledger(limit: int = Query(100, ge=1, le=250), user: dict = Depends(require_permission(Perm.AI_CREDIT_READ))) -> dict:
    return await svc.list_credit_ledger(user["tenant_id"], limit=limit)


@router.get("/history")
async def get_history(limit: int = Query(100, ge=1, le=250), user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.list_action_history(user, limit=limit)
    except AIGatewayError as e:
        _raise(e)


@router.get("/alerts")
async def list_alerts(status: Optional[str] = Query(None), user: dict = Depends(require_permission(Perm.AI_CREDIT_READ))) -> dict:
    return await svc.list_budget_alerts(user, status=status)


@router.post("/alerts/{alert_id}/status")
async def update_alert(alert_id: str, payload: AlertUpdateIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.update_budget_alert(user, alert_id, payload.status)
    except AIGatewayError as e:
        _raise(e)


@router.post("/gateway/requests", status_code=201)
async def create_gateway_request(payload: GatewayRequestIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_gateway_request(user, payload.model_dump(exclude_none=True))
    except AIGatewayError as e:
        _raise(e)
