"""EC14 - Webstore owner portal routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps_portal import get_current_portal_identity
from ..services import webstores as svc
from ..services.webstores import WebstoreError

router = APIRouter(prefix="/portal/webstores", tags=["portal-webstores"])


def _raise(e: WebstoreError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


async def _webstore_identity(identity: dict = Depends(get_current_portal_identity)) -> dict:
    perms = set(identity.get("permissions") or [])
    if identity.get("portal_type") not in {"webstore_owner", "webstore_manager"}:
        raise HTTPException(status_code=403, detail="Webstore portal access required")
    if not ({"portal:webstore_owner_admin", "portal:webstore_manager_ops"} & perms):
        raise HTTPException(status_code=403, detail="Missing portal permission: portal:webstore_owner_admin")
    return identity


class QuestionnaireIn(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    known_products: list[dict[str, Any]] = Field(default_factory=list)
    open_to_suggestions: bool = True
    missing_info_flags: list[str] = Field(default_factory=list)


@router.get("")
async def list_owned(identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await svc.owner_portal_list(identity)
    except WebstoreError as e:
        _raise(e)


@router.get("/{webstore_id}")
async def detail(webstore_id: str, identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await svc.owner_portal_detail(identity, webstore_id)
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/questionnaire")
async def questionnaire(webstore_id: str, payload: QuestionnaireIn, identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await svc.submit_questionnaire(identity, webstore_id, payload.model_dump())
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/launch-packets/{packet_id}/approve")
async def approve_launch(webstore_id: str, packet_id: str, identity: dict = Depends(_webstore_identity)) -> dict:
    try:
        return await svc.owner_approve_launch_packet(identity, webstore_id, packet_id)
    except WebstoreError as e:
        _raise(e)
