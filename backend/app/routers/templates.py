"""EC10 Phase 10G - reusable templates."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import template_service
from ..services.decision_room_service import DecisionRoomError
from ..services.template_service import TemplateError

router = APIRouter(prefix="/templates", tags=["templates"])

_ERROR_STATUS = {
    "template_not_found": 404,
    "customer_intake_not_found": 404,
    "name_required": 400,
    "invalid_template_type": 400,
    "invalid_template_body": 400,
    "invalid_template_target": 400,
    "invalid_channel": 400,
    "unknown_placeholder": 400,
    "platform_template_immutable": 403,
    "platform_admin_required": 403,
    "invalid_source_status": 400,
    "source_template_missing": 400,
    "source_update_not_available": 400,
    "template_archived": 400,
    "room_not_found": 404,
    "option_not_found": 404,
    "room_locked": 400,
    "invalid_badge_type": 400,
    "invalid_price_display_mode": 400,
}


def _raise(ex: TemplateError) -> None:
    detail: Any = str(ex)
    raise HTTPException(status_code=_ERROR_STATUS.get(ex.code, 400), detail=detail)


class TemplateCreateIn(BaseModel):
    name: str
    template_type: str
    description: Optional[str] = None
    body: dict[str, Any] = Field(default_factory=dict)


class TemplateUpdateIn(BaseModel):
    name: Optional[str] = None
    template_type: Optional[str] = None
    description: Optional[str] = None
    body: Optional[dict[str, Any]] = None


class TemplateApplyIn(BaseModel):
    target_type: str
    target_id: Optional[str] = None
    context: dict[str, Any] = Field(default_factory=dict)


class TemplateValidateIn(BaseModel):
    template_type: str
    body: dict[str, Any] = Field(default_factory=dict)


class PlatformTemplateCreateIn(TemplateCreateIn):
    source_status: Optional[str] = None
    starter_template: bool = False
    pack_id: Optional[str] = None
    pack_type: Optional[str] = None
    premium_reserved: bool = False


class PlatformTemplateUpdateIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    body: Optional[dict[str, Any]] = None
    source_status: Optional[str] = None
    active: Optional[bool] = None


@router.post("", status_code=201)
async def create_template(payload: TemplateCreateIn, user: dict = Depends(require_permission(Perm.TEMPLATE_WRITE))) -> dict:
    try:
        return await template_service.create_template(
            tenant_id=user["tenant_id"], payload=payload.model_dump(),
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except TemplateError as ex:
        _raise(ex)
    except DecisionRoomError as ex:
        raise HTTPException(status_code=_ERROR_STATUS.get(ex.code, 400), detail=str(ex))


@router.get("")
async def list_templates(
    template_type: Optional[str] = Query(None), active: Optional[bool] = Query(None),
    channel: Optional[str] = Query(None), include_platform: bool = Query(True), include_archived: bool = Query(False),
    user: dict = Depends(require_permission(Perm.TEMPLATE_READ)),
) -> dict:
    try:
        return {"items": await template_service.list_templates(
            tenant_id=user["tenant_id"], template_type=template_type, active=active,
            channel=channel, include_platform=include_platform, include_archived=include_archived,
        )}
    except TemplateError as ex:
        _raise(ex)


@router.get("/{template_id}")
async def get_template(template_id: str, user: dict = Depends(require_permission(Perm.TEMPLATE_READ))) -> dict:
    try:
        return await template_service.get_template(tenant_id=user["tenant_id"], template_id=template_id, user=user)
    except TemplateError as ex:
        _raise(ex)
    except DecisionRoomError as ex:
        raise HTTPException(status_code=_ERROR_STATUS.get(ex.code, 400), detail=str(ex))


@router.patch("/{template_id}")
async def update_template(template_id: str, payload: TemplateUpdateIn, user: dict = Depends(require_permission(Perm.TEMPLATE_WRITE))) -> dict:
    try:
        return await template_service.update_template(
            tenant_id=user["tenant_id"], template_id=template_id, changes=payload.model_dump(exclude_unset=True),
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except TemplateError as ex:
        _raise(ex)


@router.post("/{template_id}/archive")
async def archive_template(template_id: str, user: dict = Depends(require_permission(Perm.TEMPLATE_WRITE))) -> dict:
    try:
        return await template_service.archive_template(
            tenant_id=user["tenant_id"], template_id=template_id,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except TemplateError as ex:
        _raise(ex)


@router.post("/{template_id}/restore")
async def restore_template(template_id: str, user: dict = Depends(require_permission(Perm.TEMPLATE_WRITE))) -> dict:
    try:
        return await template_service.restore_template(
            tenant_id=user["tenant_id"], template_id=template_id,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except TemplateError as ex:
        _raise(ex)


@router.post("/{template_id}/apply")
async def apply_template(template_id: str, payload: TemplateApplyIn, user: dict = Depends(require_permission(Perm.TEMPLATE_WRITE))) -> dict:
    try:
        return await template_service.apply_template(
            tenant_id=user["tenant_id"], template_id=template_id,
            target_type=payload.target_type, target_id=payload.target_id,
            actor_user_id=user["id"], actor_email=user["email"], context=payload.context,
        )
    except TemplateError as ex:
        _raise(ex)
    except DecisionRoomError as ex:
        raise HTTPException(status_code=_ERROR_STATUS.get(ex.code, 400), detail=str(ex))


@router.post("/validate")
async def validate_template(payload: TemplateValidateIn, user: dict = Depends(require_permission(Perm.TEMPLATE_READ))) -> dict:
    try:
        return await template_service.validate_template_payload(template_type=payload.template_type, body=payload.body)
    except TemplateError as ex:
        _raise(ex)


@router.post("/{template_id}/duplicate", status_code=201)
async def duplicate_template(template_id: str, user: dict = Depends(require_permission(Perm.TEMPLATE_WRITE))) -> dict:
    try:
        return await template_service.duplicate_template(
            tenant_id=user["tenant_id"], template_id=template_id,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except TemplateError as ex:
        _raise(ex)


@router.post("/{template_id}/preview")
async def preview_template(template_id: str, payload: dict[str, Any] | None = None, user: dict = Depends(require_permission(Perm.TEMPLATE_READ))) -> dict:
    try:
        return await template_service.preview_template(tenant_id=user["tenant_id"], template_id=template_id, context=(payload or {}).get("context"))
    except TemplateError as ex:
        _raise(ex)


@router.get("/{template_id}/source-comparison")
async def source_comparison(template_id: str, user: dict = Depends(require_permission(Perm.TEMPLATE_READ))) -> dict:
    try:
        return await template_service.compare_source_version(tenant_id=user["tenant_id"], template_id=template_id)
    except TemplateError as ex:
        _raise(ex)


@router.post("/{template_id}/install-newer-source-copy", status_code=201)
async def install_newer_source_copy(template_id: str, user: dict = Depends(require_permission(Perm.TEMPLATE_WRITE))) -> dict:
    try:
        return await template_service.install_newer_source_copy(
            tenant_id=user["tenant_id"], template_id=template_id,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except TemplateError as ex:
        _raise(ex)


@router.get("/packs/list")
async def list_packs(user: dict = Depends(require_permission(Perm.TEMPLATE_READ))) -> dict:
    return {"items": await template_service.list_template_packs()}


@router.post("/packs/starter/install")
async def install_starter_pack(user: dict = Depends(require_permission(Perm.TEMPLATE_WRITE))) -> dict:
    try:
        return await template_service.install_starter_pack(
            tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        )
    except TemplateError as ex:
        _raise(ex)


@router.post("/starter/{source_template_id}/install", status_code=201)
async def install_starter_template(source_template_id: str, user: dict = Depends(require_permission(Perm.TEMPLATE_WRITE))) -> dict:
    try:
        return await template_service.install_template_copy(
            tenant_id=user["tenant_id"], source_template_id=source_template_id,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except TemplateError as ex:
        _raise(ex)


@router.post("/platform-masters", status_code=201)
async def create_platform_master(payload: PlatformTemplateCreateIn, user: dict = Depends(require_permission(Perm.TEMPLATE_WRITE))) -> dict:
    try:
        return await template_service.create_platform_master(payload=payload.model_dump(exclude_none=True), actor=user)
    except TemplateError as ex:
        _raise(ex)


@router.patch("/platform-masters/{template_id}")
async def update_platform_master(template_id: str, payload: PlatformTemplateUpdateIn, user: dict = Depends(require_permission(Perm.TEMPLATE_WRITE))) -> dict:
    try:
        return await template_service.update_platform_master(template_id=template_id, changes=payload.model_dump(exclude_unset=True), actor=user)
    except TemplateError as ex:
        _raise(ex)
