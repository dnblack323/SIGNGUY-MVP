"""EC10 Phase 10C — Visual Markup router.

Staff-only. No customer-facing/public markup route exists here.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import markup_service
from ..services.markup_service import MarkupError

router = APIRouter(prefix="/markup", tags=["visual-markup"])

_ERROR_STATUS = {
    "source_file_not_found": 404, "intake_not_found": 404, "intake_item_not_found": 404,
    "preview_file_not_found": 404, "markup_not_found": 404, "version_not_found": 404,
    "unsupported_source_file_type": 400, "invalid_pdf_page": 400, "markup_archived": 400,
    "malformed_markup": 400, "unsupported_object_type": 400, "payload_too_large": 400,
    "too_many_objects": 400, "embedded_binary_forbidden": 400,
}


def _raise(ex: MarkupError) -> None:
    raise HTTPException(status_code=_ERROR_STATUS.get(ex.code, 400), detail=str(ex))


class CreateMarkupIn(BaseModel):
    source_file_id: str
    source_page_number: Optional[int] = None
    intake_id: Optional[str] = None
    intake_item_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None


class SaveVersionIn(BaseModel):
    structured_markup_json: dict[str, Any] = Field(default_factory=dict)
    canvas_width: int
    canvas_height: int
    source_display_width: int
    source_display_height: int
    rendered_preview_file_id: Optional[str] = None
    change_summary: Optional[str] = None


class AttachIn(BaseModel):
    intake_id: str
    intake_item_id: Optional[str] = None


@router.post("", status_code=201)
async def create_markup(payload: CreateMarkupIn, user: dict = Depends(require_permission(Perm.MARKUP_WRITE))) -> dict:
    try:
        return await markup_service.create_markup(
            tenant_id=user["tenant_id"], source_file_id=payload.source_file_id,
            source_page_number=payload.source_page_number, intake_id=payload.intake_id,
            intake_item_id=payload.intake_item_id, title=payload.title, description=payload.description,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except MarkupError as ex:
        _raise(ex)


@router.get("")
async def list_markup(
    intake_id: Optional[str] = Query(None), intake_item_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None), user: dict = Depends(require_permission(Perm.MARKUP_READ)),
) -> dict:
    items = await markup_service.list_markup(
        tenant_id=user["tenant_id"], intake_id=intake_id, intake_item_id=intake_item_id, status=status,
    )
    return {"items": items}


@router.get("/{markup_id}")
async def get_markup(markup_id: str, user: dict = Depends(require_permission(Perm.MARKUP_READ))) -> dict:
    try:
        return await markup_service.get_markup(tenant_id=user["tenant_id"], markup_id=markup_id)
    except MarkupError as ex:
        _raise(ex)


@router.post("/{markup_id}/versions", status_code=201)
async def save_version(
    markup_id: str, payload: SaveVersionIn, user: dict = Depends(require_permission(Perm.MARKUP_WRITE)),
) -> dict:
    try:
        return await markup_service.save_version(
            tenant_id=user["tenant_id"], markup_id=markup_id,
            structured_markup_json=payload.structured_markup_json,
            canvas_width=payload.canvas_width, canvas_height=payload.canvas_height,
            source_display_width=payload.source_display_width, source_display_height=payload.source_display_height,
            rendered_preview_file_id=payload.rendered_preview_file_id, change_summary=payload.change_summary,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except MarkupError as ex:
        _raise(ex)


@router.get("/{markup_id}/versions")
async def list_versions(markup_id: str, user: dict = Depends(require_permission(Perm.MARKUP_READ))) -> dict:
    try:
        return {"items": await markup_service.list_versions(tenant_id=user["tenant_id"], markup_id=markup_id)}
    except MarkupError as ex:
        _raise(ex)


@router.get("/{markup_id}/versions/{version_id}")
async def get_version(
    markup_id: str, version_id: str, user: dict = Depends(require_permission(Perm.MARKUP_READ)),
) -> dict:
    try:
        return await markup_service.get_version(tenant_id=user["tenant_id"], markup_id=markup_id, version_id=version_id)
    except MarkupError as ex:
        _raise(ex)


@router.get("/{markup_id}/preview")
async def get_preview(markup_id: str, user: dict = Depends(require_permission(Perm.MARKUP_READ))) -> dict:
    try:
        return await markup_service.get_preview_reference(tenant_id=user["tenant_id"], markup_id=markup_id)
    except MarkupError as ex:
        _raise(ex)


@router.post("/{markup_id}/archive")
async def archive(markup_id: str, user: dict = Depends(require_permission(Perm.MARKUP_WRITE))) -> dict:
    try:
        return await markup_service.archive_markup(tenant_id=user["tenant_id"], markup_id=markup_id, actor_user_id=user["id"], actor_email=user["email"])
    except MarkupError as ex:
        _raise(ex)


@router.post("/{markup_id}/restore")
async def restore(markup_id: str, user: dict = Depends(require_permission(Perm.MARKUP_WRITE))) -> dict:
    try:
        return await markup_service.restore_markup(tenant_id=user["tenant_id"], markup_id=markup_id, actor_user_id=user["id"], actor_email=user["email"])
    except MarkupError as ex:
        _raise(ex)


@router.post("/{markup_id}/attach")
async def attach(markup_id: str, payload: AttachIn, user: dict = Depends(require_permission(Perm.MARKUP_WRITE))) -> dict:
    try:
        if payload.intake_item_id:
            return await markup_service.attach_to_intake_item(
                tenant_id=user["tenant_id"], markup_id=markup_id, intake_id=payload.intake_id,
                intake_item_id=payload.intake_item_id, actor_user_id=user["id"], actor_email=user["email"],
            )
        return await markup_service.attach_to_intake(
            tenant_id=user["tenant_id"], markup_id=markup_id, intake_id=payload.intake_id,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except MarkupError as ex:
        _raise(ex)
