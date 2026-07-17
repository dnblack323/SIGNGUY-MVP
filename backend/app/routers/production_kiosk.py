"""EC11 Phase 11F - shop-floor production kiosk routes."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from ..deps import get_current_user
from ..services import production_kiosk_service as svc

router = APIRouter(prefix="/production-kiosk", tags=["production_kiosk"])


class KioskConfigIn(BaseModel):
    kiosk_enabled: Optional[bool] = None
    device_session_ttl_minutes: Optional[int] = None
    employee_idle_timeout_minutes: Optional[int] = None
    pin_enabled: Optional[bool] = None
    shop_queue_visibility: Optional[str] = None
    customer_name_visible: Optional[bool] = None
    artwork_document_visible: Optional[bool] = None
    time_clock_panel_enabled: Optional[bool] = None
    supervisor_override_enabled: Optional[bool] = None
    allowed_basic_employee_actions: Optional[list[str]] = None
    device_labels: Optional[list[str]] = None


class ActivateDeviceIn(BaseModel):
    device_label: Optional[str] = None


class RevokeDeviceIn(BaseModel):
    reason: Optional[str] = None


class EmployeeCredentialIn(BaseModel):
    pin: str = Field(min_length=4)


class IdentifyEmployeeIn(BaseModel):
    employee_id: str
    pin: str


class StageActionIn(BaseModel):
    reason: Optional[str] = None
    completion_note: Optional[str] = None
    note: Optional[str] = None
    supervisor_override_token: Optional[str] = None


class SupervisorOverrideIn(BaseModel):
    employee_id: str
    stage_id: str
    action: str
    reason: str


class ClockInIn(BaseModel):
    work_order_id: Optional[str] = None
    notes: Optional[str] = None


def _raise(e: svc.ProductionKioskError) -> None:
    raise HTTPException(status_code=e.status_code, detail=str(e))


async def _employee_session(
    x_kiosk_device_token: Optional[str] = Header(default=None, alias=svc.DEVICE_SESSION_HEADER),
    x_kiosk_employee_token: Optional[str] = Header(default=None, alias=svc.EMPLOYEE_SESSION_HEADER),
) -> dict:
    try:
        return await svc.require_employee_session(x_kiosk_device_token, x_kiosk_employee_token)
    except svc.ProductionKioskError as e:
        _raise(e)


@router.get("/config")
async def get_config(user: dict = Depends(get_current_user)) -> dict:
    try:
        svc._assert_manager(user)
        return await svc.get_config(user["tenant_id"])
    except svc.ProductionKioskError as e:
        _raise(e)


@router.put("/config")
async def update_config(payload: KioskConfigIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.update_config(tenant_id=user["tenant_id"], values=payload.model_dump(exclude_none=True), user=user)
    except svc.ProductionKioskError as e:
        _raise(e)


@router.post("/employees/{employee_id}/credential")
async def set_employee_credential(employee_id: str, payload: EmployeeCredentialIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.set_employee_credential(tenant_id=user["tenant_id"], employee_id=employee_id, pin=payload.pin, user=user)
    except svc.ProductionKioskError as e:
        _raise(e)


@router.post("/sessions/activate")
async def activate_device(payload: ActivateDeviceIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.activate_device(tenant_id=user["tenant_id"], device_label=payload.device_label, user=user)
    except svc.ProductionKioskError as e:
        _raise(e)


@router.get("/sessions")
async def list_sessions(user: dict = Depends(get_current_user)) -> list[dict]:
    try:
        return await svc.list_sessions(tenant_id=user["tenant_id"], user=user)
    except svc.ProductionKioskError as e:
        _raise(e)


@router.post("/sessions/{session_id}/revoke")
async def revoke_session(session_id: str, payload: RevokeDeviceIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.revoke_session(tenant_id=user["tenant_id"], session_id=session_id, reason=payload.reason, user=user)
    except svc.ProductionKioskError as e:
        _raise(e)


@router.get("/session")
async def inspect_session(x_kiosk_device_token: Optional[str] = Header(default=None, alias=svc.DEVICE_SESSION_HEADER)) -> dict:
    try:
        return await svc.inspect_device_session(x_kiosk_device_token)
    except svc.ProductionKioskError as e:
        _raise(e)


@router.post("/identify")
async def identify_employee(
    payload: IdentifyEmployeeIn,
    x_kiosk_device_token: Optional[str] = Header(default=None, alias=svc.DEVICE_SESSION_HEADER),
) -> dict:
    try:
        return await svc.identify_employee(device_token=x_kiosk_device_token, employee_id=payload.employee_id, pin=payload.pin)
    except svc.ProductionKioskError as e:
        _raise(e)


@router.post("/employee/end")
async def end_employee_session(x_kiosk_device_token: Optional[str] = Header(default=None, alias=svc.DEVICE_SESSION_HEADER)) -> dict:
    try:
        return await svc.end_employee_session(device_token=x_kiosk_device_token)
    except svc.ProductionKioskError as e:
        _raise(e)


@router.get("/work")
async def work(search: Optional[str] = None, session: dict = Depends(_employee_session)) -> dict:
    try:
        return await svc.get_work_view(session=session, search=search)
    except svc.ProductionKioskError as e:
        _raise(e)


@router.post("/stages/{stage_id}/{action}")
async def stage_action(stage_id: str, action: str, payload: StageActionIn, session: dict = Depends(_employee_session)) -> dict:
    try:
        return await svc.perform_stage_action(session=session, stage_id=stage_id, action=action, payload=payload.model_dump(exclude_none=True))
    except svc.ProductionKioskError as e:
        _raise(e)


@router.post("/supervisor-overrides")
async def supervisor_override(
    payload: SupervisorOverrideIn,
    user: dict = Depends(get_current_user),
    x_kiosk_device_token: Optional[str] = Header(default=None, alias=svc.DEVICE_SESSION_HEADER),
) -> dict:
    try:
        return await svc.create_supervisor_override(
            tenant_id=user["tenant_id"], device_token=x_kiosk_device_token, employee_id=payload.employee_id,
            stage_id=payload.stage_id, action=payload.action, reason=payload.reason, user=user,
        )
    except svc.ProductionKioskError as e:
        _raise(e)


@router.get("/time-clock")
async def time_clock_status(session: dict = Depends(_employee_session)) -> dict:
    try:
        return await svc.get_time_clock_status(session)
    except svc.ProductionKioskError as e:
        _raise(e)


@router.post("/time-clock/clock-in")
async def clock_in(payload: ClockInIn, session: dict = Depends(_employee_session)) -> dict:
    try:
        return await svc.clock_in(session=session, work_order_id=payload.work_order_id, notes=payload.notes)
    except svc.ProductionKioskError as e:
        _raise(e)


@router.post("/time-clock/clock-out")
async def clock_out(session: dict = Depends(_employee_session)) -> dict:
    try:
        return await svc.clock_out(session)
    except svc.ProductionKioskError as e:
        _raise(e)
