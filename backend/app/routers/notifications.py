"""EC2 — Notification routes (staff-only, tenant-scoped, per-user).

Every route is scoped to the calling user's user_id. A user CANNOT read or
mutate notifications belonging to any other user, even inside the same tenant.
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..deps import get_current_user
from ..services import notifications as svc

router = APIRouter(prefix="/notifications", tags=["notifications"])


class MarkManyIn(BaseModel):
    ids: list[str]


@router.get("")
async def list_(
    status: Optional[Literal["unread", "read", "dismissed"]] = Query(None),
    limit: int = Query(50, le=200),
    skip: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
) -> dict:
    return await svc.list_for_user(
        tenant_id=user["tenant_id"],
        user_id=user["id"],
        status=status,
        limit=limit,
        skip=skip,
    )


@router.get("/unread-count")
async def unread_count(user: dict = Depends(get_current_user)) -> dict:
    return {"unread": await svc.unread_count(tenant_id=user["tenant_id"], user_id=user["id"])}


@router.post("/{notification_id}/read")
async def mark_read(notification_id: str, user: dict = Depends(get_current_user)) -> dict:
    ok = await svc.mark_read(tenant_id=user["tenant_id"], user_id=user["id"], notification_id=notification_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"ok": True}


@router.post("/read-many")
async def mark_many(payload: MarkManyIn, user: dict = Depends(get_current_user)) -> dict:
    modified = await svc.mark_many_read(
        tenant_id=user["tenant_id"], user_id=user["id"], ids=payload.ids
    )
    return {"modified": modified}


@router.post("/{notification_id}/dismiss")
async def dismiss(notification_id: str, user: dict = Depends(get_current_user)) -> dict:
    ok = await svc.dismiss(tenant_id=user["tenant_id"], user_id=user["id"], notification_id=notification_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"ok": True}
