"""EC8 phase 8c — Employee Portal admin (staff-side invite/suspend/list).

Gated by `employee:manage` (invite/suspend) and `employee:read` (list/status)
— reuses the exact same Employee permission namespace as the Employees API,
per the owner's directive that Employee Portal access is an Employee-record
concern, not a new permission module.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import employee_portal_service
from ..services.employee_portal_service import EmployeePortalError

router = APIRouter(prefix="/employee-portal", tags=["employee-portal-admin"])


def _raise(e: EmployeePortalError):
    raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("")
async def list_identities(user: dict = Depends(require_permission(Perm.EMPLOYEE_READ))) -> dict:
    items = await employee_portal_service.list_employee_portal_identities(tenant_id=user["tenant_id"])
    return {"items": items}


@router.get("/{employee_id}")
async def get_status(employee_id: str, user: dict = Depends(require_permission(Perm.EMPLOYEE_READ))) -> dict:
    return await employee_portal_service.get_portal_status(tenant_id=user["tenant_id"], employee_id=employee_id)


@router.post("/{employee_id}/invite", status_code=201)
async def invite(employee_id: str, request: Request,
                  user: dict = Depends(require_permission(Perm.EMPLOYEE_MANAGE))) -> dict:
    try:
        return await employee_portal_service.invite_employee(
            tenant_id=user["tenant_id"], employee_id=employee_id,
            request_ip=(request.client.host if request.client else None),
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except EmployeePortalError as e:
        _raise(e)


@router.post("/{employee_id}/suspend")
async def suspend(employee_id: str, user: dict = Depends(require_permission(Perm.EMPLOYEE_MANAGE))) -> dict:
    try:
        return await employee_portal_service.suspend_employee_portal(
            tenant_id=user["tenant_id"], employee_id=employee_id, actor_user_id=user["id"], actor_email=user["email"],
        )
    except EmployeePortalError as e:
        _raise(e)
