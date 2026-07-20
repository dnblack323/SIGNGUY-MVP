"""EC19 onboarding routes."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..deps import get_current_user, require_permission
from ..services import onboarding as svc
from ..services.onboarding import OnboardingError

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _raise(ex: OnboardingError) -> None:
    raise HTTPException(status_code=ex.status_code, detail=ex.detail)


class TaskStatusIn(BaseModel):
    status: str
    reason: Optional[str] = None
    deferred_until: Optional[str] = None


class StepResponseIn(BaseModel):
    task_key: str
    response_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None


class CompanyProfileIn(BaseModel):
    company_profile: dict[str, Any] = Field(default_factory=dict)
    branding: dict[str, Any] = Field(default_factory=dict)


class PricingScenarioIn(BaseModel):
    category: str
    job_duration_hours: float = Field(..., gt=0)
    crew_size: int = Field(..., ge=1)
    material_cost_estimate: Optional[float] = Field(None, ge=0)
    customer_charge: float = Field(..., gt=0)
    price_floor: float = Field(..., ge=0)
    includes_design: bool = False
    includes_install: bool = False
    includes_setup: bool = False
    includes_finishing: bool = False
    difficulty: str = "typical"


class PricingApplyIn(BaseModel):
    accepted_shop_defaults: dict[str, Any] = Field(default_factory=dict)


class HistoricalImportIn(BaseModel):
    file_name: str
    file_type: Optional[str] = None
    file_size_bytes: Optional[int] = Field(default=None, ge=0)
    request_analysis: bool = False


class PlaceholderPreviewIn(BaseModel):
    content: str
    context: dict[str, Any] = Field(default_factory=dict)


class TemplateExerciseIn(BaseModel):
    name: str = "Onboarding sample template"
    template_type: str = "email"
    body: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    save_as_template: bool = False


class SetupHandoffIn(BaseModel):
    purchase_id: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class TestPortalIn(BaseModel):
    result: dict[str, Any] = Field(default_factory=dict)


@router.post("/platform/bootstrap", status_code=201)
async def bootstrap(user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.bootstrap_platform(user)
    except OnboardingError as ex:
        _raise(ex)


@router.get("/dashboard")
async def get_dashboard(user: dict = Depends(require_permission(Perm.ONBOARDING_READ))) -> dict:
    try:
        return await svc.dashboard(user)
    except OnboardingError as ex:
        _raise(ex)


@router.post("/tasks/{task_key}/status")
async def update_task(task_key: str, payload: TaskStatusIn, user: dict = Depends(require_permission(Perm.ONBOARDING_WRITE))) -> dict:
    try:
        return await svc.update_task_status(user, task_key, payload.status, reason=payload.reason, deferred_until=payload.deferred_until)
    except OnboardingError as ex:
        _raise(ex)


@router.post("/responses", status_code=201)
async def save_response(payload: StepResponseIn, user: dict = Depends(require_permission(Perm.ONBOARDING_WRITE))) -> dict:
    try:
        return await svc.save_response(
            user,
            task_key=payload.task_key,
            response_type=payload.response_type,
            payload=payload.payload,
            idempotency_key=payload.idempotency_key,
        )
    except OnboardingError as ex:
        _raise(ex)


@router.post("/company-profile/apply")
async def apply_company_profile(payload: CompanyProfileIn, user: dict = Depends(require_permission(Perm.ONBOARDING_WRITE))) -> dict:
    try:
        return await svc.apply_company_profile(user, payload.model_dump())
    except OnboardingError as ex:
        _raise(ex)


@router.post("/pricing/scenario", status_code=201)
async def pricing_scenario(payload: PricingScenarioIn, user: dict = Depends(require_permission(Perm.ONBOARDING_WRITE))) -> dict:
    try:
        return await svc.pricing_scenario(user, payload.model_dump())
    except (OnboardingError, ValueError) as ex:
        raise HTTPException(status_code=getattr(ex, "status_code", 400), detail=getattr(ex, "detail", str(ex)))


@router.post("/pricing/scenario/{submission_id}/apply")
async def apply_pricing_scenario(submission_id: str, payload: PricingApplyIn, user: dict = Depends(require_permission(Perm.ONBOARDING_WRITE))) -> dict:
    try:
        return await svc.apply_pricing_scenario(user, submission_id, payload.accepted_shop_defaults)
    except (OnboardingError, ValueError) as ex:
        raise HTTPException(status_code=getattr(ex, "status_code", 400), detail=getattr(ex, "detail", str(ex)))


@router.post("/historical-invoices", status_code=201)
async def historical_import(payload: HistoricalImportIn, user: dict = Depends(require_permission(Perm.ONBOARDING_WRITE))) -> dict:
    try:
        return await svc.create_historical_import(user, payload.model_dump())
    except OnboardingError as ex:
        _raise(ex)


@router.get("/placeholders")
async def placeholders(user: dict = Depends(require_permission(Perm.ONBOARDING_READ))) -> dict:
    return svc.placeholder_registry()


@router.post("/placeholders/preview")
async def placeholder_preview(payload: PlaceholderPreviewIn, user: dict = Depends(require_permission(Perm.ONBOARDING_READ))) -> dict:
    try:
        return svc.preview_placeholders(payload.content, payload.context)
    except OnboardingError as ex:
        _raise(ex)


@router.post("/template-exercises", status_code=201)
async def template_exercise(payload: TemplateExerciseIn, user: dict = Depends(require_permission(Perm.ONBOARDING_WRITE))) -> dict:
    try:
        return await svc.template_exercise(user, payload.model_dump())
    except (OnboardingError, ValueError) as ex:
        raise HTTPException(status_code=getattr(ex, "status_code", 400), detail=getattr(ex, "detail", str(ex)))


@router.get("/setup-package-handoff")
async def get_setup_package_handoff(user: dict = Depends(require_permission(Perm.ONBOARDING_READ))) -> dict:
    try:
        return await svc.setup_package_handoff(user)
    except OnboardingError as ex:
        _raise(ex)


@router.post("/setup-package-handoff")
async def update_setup_package_handoff(payload: SetupHandoffIn, user: dict = Depends(require_permission(Perm.ONBOARDING_WRITE))) -> dict:
    try:
        return await svc.setup_package_handoff(user, purchase_id=payload.purchase_id, status=payload.status, notes=payload.notes)
    except OnboardingError as ex:
        _raise(ex)


@router.post("/test-portal", status_code=201)
async def record_test_portal(payload: TestPortalIn, user: dict = Depends(require_permission(Perm.ONBOARDING_WRITE))) -> dict:
    try:
        return await svc.record_test_portal(user, payload.result)
    except OnboardingError as ex:
        _raise(ex)
