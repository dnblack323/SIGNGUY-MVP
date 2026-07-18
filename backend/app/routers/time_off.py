"""EC12 Phase 12C - staff time-off review routes."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import time_off_service
from ..services.time_off_service import TimeOffError

router = APIRouter(prefix="/time-off", tags=["time_off"])


def _raise(e: TimeOffError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


class ManagerNoteIn(BaseModel):
    note: Optional[str] = None


@router.get("")
async def list_requests(
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.SCHEDULE_READ)),
) -> dict:
    return await time_off_service.list_requests(
        tenant_id=user["tenant_id"], employee_id=employee_id, status=status, include_private=True, limit=limit, skip=skip,
    )


@router.get("/{request_id}")
async def get_request(request_id: str, user: dict = Depends(require_permission(Perm.SCHEDULE_READ))) -> dict:
    try:
        return await time_off_service.get_request(tenant_id=user["tenant_id"], request_id=request_id, include_private=True)
    except TimeOffError as e:
        _raise(e)


@router.get("/conflicts/check")
async def check_conflicts(employee_id: str, start_at: str, end_at: str,
                          user: dict = Depends(require_permission(Perm.SCHEDULE_READ))) -> dict:
    try:
        return await time_off_service.list_conflicts(
            tenant_id=user["tenant_id"], employee_id=employee_id, start_at=start_at, end_at=end_at,
        )
    except TimeOffError as e:
        _raise(e)


@router.post("/{request_id}/approve")
async def approve(request_id: str, payload: ManagerNoteIn,
                  user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await time_off_service.approve_request(
            tenant_id=user["tenant_id"], request_id=request_id, actor_user_id=user["id"],
            actor_email=user["email"], note=payload.note,
        )
    except TimeOffError as e:
        _raise(e)


@router.post("/{request_id}/deny")
async def deny(request_id: str, payload: ManagerNoteIn,
               user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await time_off_service.deny_request(
            tenant_id=user["tenant_id"], request_id=request_id, actor_user_id=user["id"],
            actor_email=user["email"], note=payload.note,
        )
    except TimeOffError as e:
        _raise(e)


@router.post("/{request_id}/clarification")
async def clarify(request_id: str, payload: ManagerNoteIn,
                  user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await time_off_service.request_clarification(
            tenant_id=user["tenant_id"], request_id=request_id, actor_user_id=user["id"],
            actor_email=user["email"], note=payload.note,
        )
    except TimeOffError as e:
        _raise(e)

