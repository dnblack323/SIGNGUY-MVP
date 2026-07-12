"""EC8 phase 8a — Employees router."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import employee_service
from ..services.employee_service import EmployeeError

router = APIRouter(prefix="/employees", tags=["employees"])


class EmployeeIn(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role_label: Optional[str] = None
    linked_user_id: Optional[str] = None
    hire_date: Optional[str] = None
    hourly_rate_cents: Optional[int] = None
    overtime_policy: Optional[str] = None
    availability: Optional[str] = None
    portal_access: Optional[bool] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    notes: Optional[str] = None


class EmployeeUpdateIn(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role_label: Optional[str] = None
    linked_user_id: Optional[str] = None
    hire_date: Optional[str] = None
    hourly_rate_cents: Optional[int] = None
    overtime_policy: Optional[str] = None
    availability: Optional[str] = None
    portal_access: Optional[bool] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    notes: Optional[str] = None


class StatusChangeIn(BaseModel):
    status: str
    reason: str


def _raise(e: EmployeeError):
    raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("")
async def list_employees(status: Optional[str] = None, q: Optional[str] = None,
                          user: dict = Depends(require_permission(Perm.EMPLOYEE_READ))) -> dict:
    items = await employee_service.list_employees(tenant_id=user["tenant_id"], status=status, q=q)
    return {"items": items}


@router.get("/status-counts")
async def status_counts(user: dict = Depends(require_permission(Perm.EMPLOYEE_READ))) -> dict:
    return await employee_service.status_counts(tenant_id=user["tenant_id"])


@router.post("", status_code=201)
async def create_employee(payload: EmployeeIn, user: dict = Depends(require_permission(Perm.EMPLOYEE_MANAGE))) -> dict:
    try:
        data = {k: v for k, v in payload.model_dump().items() if v is not None}
        return await employee_service.create_employee(
            tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"], payload=data,
        )
    except EmployeeError as e:
        _raise(e)


@router.get("/{employee_id}")
async def get_employee(employee_id: str, user: dict = Depends(require_permission(Perm.EMPLOYEE_READ))) -> dict:
    try:
        return await employee_service.get_employee(tenant_id=user["tenant_id"], employee_id=employee_id)
    except EmployeeError as e:
        _raise(e)


@router.patch("/{employee_id}")
async def update_employee(employee_id: str, payload: EmployeeUpdateIn,
                           user: dict = Depends(require_permission(Perm.EMPLOYEE_MANAGE))) -> dict:
    try:
        return await employee_service.update_employee(
            tenant_id=user["tenant_id"], employee_id=employee_id,
            actor_user_id=user["id"], actor_email=user["email"], payload=payload.model_dump(),
        )
    except EmployeeError as e:
        _raise(e)


@router.post("/{employee_id}/status")
async def change_status(employee_id: str, payload: StatusChangeIn,
                         user: dict = Depends(require_permission(Perm.EMPLOYEE_MANAGE))) -> dict:
    try:
        return await employee_service.change_status(
            tenant_id=user["tenant_id"], employee_id=employee_id,
            actor_user_id=user["id"], actor_email=user["email"],
            new_status=payload.status, reason=payload.reason,
        )
    except EmployeeError as e:
        _raise(e)
