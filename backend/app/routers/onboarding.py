"""Guided onboarding routes.

Setup values are saved through the owning feature's own API (settings, pricing,
employees, production workflows, customers, orders). These routes only expose
progress: the dashboard, skip/defer/reviewed choices and the saved position.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

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


class PositionIn(BaseModel):
    task_key: Optional[str] = None
    dismiss_prompt: Optional[bool] = None


class SetupHandoffIn(BaseModel):
    purchase_id: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


@router.post("/platform/bootstrap", status_code=201)
async def bootstrap(user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.bootstrap_platform(user)
    except OnboardingError as ex:
        _raise(ex)


@router.get("/dashboard")
async def get_dashboard(user: dict = Depends(require_permission(Perm.ONBOARDING_READ))) -> dict:
    return await svc.dashboard(user)


@router.post("/tasks/{task_key}/status")
async def update_task(task_key: str, payload: TaskStatusIn, user: dict = Depends(require_permission(Perm.ONBOARDING_WRITE))) -> dict:
    try:
        return await svc.update_task_status(user, task_key, payload.status, reason=payload.reason, deferred_until=payload.deferred_until)
    except OnboardingError as ex:
        _raise(ex)


@router.post("/position")
async def save_position(payload: PositionIn, user: dict = Depends(require_permission(Perm.ONBOARDING_WRITE))) -> dict:
    try:
        return await svc.set_position(user, task_key=payload.task_key, dismiss_prompt=payload.dismiss_prompt)
    except OnboardingError as ex:
        _raise(ex)


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
