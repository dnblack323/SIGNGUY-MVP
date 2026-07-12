"""EC8 phase 8a — Announcements router (Team & Workflow)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import announcement_service
from ..services.announcement_service import AnnouncementError

router = APIRouter(prefix="/announcements", tags=["announcements"])


class AnnouncementIn(BaseModel):
    title: str
    body: str
    audience: str = "all"
    employee_ids: list[str] = Field(default_factory=list)
    acknowledgement_required: bool = False
    expires_at: Optional[str] = None


@router.get("")
async def list_announcements(status: Optional[str] = None,
                              user: dict = Depends(require_permission(Perm.EMPLOYEE_READ))) -> dict:
    items = await announcement_service.list_announcements(tenant_id=user["tenant_id"], status=status)
    return {"items": items}


@router.post("", status_code=201)
async def create_announcement(payload: AnnouncementIn,
                               user: dict = Depends(require_permission(Perm.EMPLOYEE_MANAGE))) -> dict:
    return await announcement_service.create_announcement(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        payload=payload.model_dump(),
    )


@router.post("/{announcement_id}/publish")
async def publish_announcement(announcement_id: str,
                                user: dict = Depends(require_permission(Perm.EMPLOYEE_MANAGE))) -> dict:
    try:
        return await announcement_service.publish_announcement(
            tenant_id=user["tenant_id"], announcement_id=announcement_id,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except AnnouncementError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
