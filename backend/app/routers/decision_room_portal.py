"""EC10 Phase 10E-1/10E-2 — Customer Portal Decision Room access.

Portal-authenticated (JWT, `sub_scope="portal"`, `portal_type="customer"`)
retrieval of Decision Rooms belonging to the caller's own Customer record.
Returns ONLY the frozen published-version content — see
`services/decision_room_service.get_customer_view()` for the shared
customer-safe rendering logic (also used by the Public Token route in
`public_actions.py`).

Phase 10E-2 adds the customer's own decision submission (select/reject/
reject-all/request-change) — gated behind the distinct
`portal:respond_decision_rooms` permission (view alone must never allow a
decision to be submitted on someone else's behalf). Comments/questions/
save-for-later remain Phase 10E-3, not built here.

Also serves customer-safe DERIVATIVE media (images/PDFs/proof previews/
rendered markup previews) referenced by that same frozen version — see
`services/decision_room_service.resolve_customer_safe_media()`. This never
becomes a general file browser: only ids actually referenced in the frozen
published version (and, for plain attachments, explicitly `visibility ==
"customer_visible"`) are ever servable.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict

from ..deps_portal import require_portal_permission
from ..services import decision_room_service as svc
from ..services import storage
from ..services.decision_room_service import DecisionRoomError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portal/decision-rooms", tags=["portal_decision_rooms"])

_ERROR_STATUS = {
    "room_not_found": 404, "option_not_found": 404,
    "room_not_open_for_decisions": 400, "invalid_action_type": 400,
    "option_id_required": 400, "option_id_not_allowed": 400,
    "reject_all_not_allowed": 400, "change_requests_not_allowed": 400, "comment_required": 400,
    # EC10 Phase 10E-3
    "questions_not_allowed": 400, "question_message_required": 400,
    "comments_not_allowed": 400, "invalid_coordinates": 400, "anchor_required": 400,
    "visual_markup_not_in_version": 404, "markup_version_not_found": 404, "invalid_pdf_page": 400,
    "overlay_not_found": 404, "overlay_locked": 400, "save_for_later_not_allowed": 400,
    "media_not_found": 404, "media_unavailable": 404,
}


def _raise(ex: DecisionRoomError) -> None:
    raise HTTPException(status_code=_ERROR_STATUS.get(ex.code, 400), detail=str(ex))


@router.get("")
async def list_rooms(identity: dict = Depends(require_portal_permission("portal:view_decision_rooms"))) -> dict:
    items = await svc.list_customer_rooms(tenant_id=identity["tenant_id"], customer_id=identity["customer_id"])
    return {"items": items}


@router.get("/{room_id}")
async def get_room(room_id: str, identity: dict = Depends(require_portal_permission("portal:view_decision_rooms"))) -> dict:
    try:
        return await svc.get_customer_view(
            tenant_id=identity["tenant_id"], room_id=room_id, customer_id=identity["customer_id"],
        )
    except DecisionRoomError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@router.get("/{room_id}/media/{file_id}")
async def get_media(
    room_id: str, file_id: str, identity: dict = Depends(require_portal_permission("portal:view_decision_rooms")),
):
    try:
        file_doc = await svc.resolve_customer_safe_media(
            tenant_id=identity["tenant_id"], room_id=room_id, file_id=file_id, customer_id=identity["customer_id"],
        )
    except DecisionRoomError as ex:
        raise HTTPException(status_code=404, detail="Media not available")
    try:
        data, ct = storage.get_bytes(file_doc["storage_key"])
    except Exception:
        logger.exception("Decision Room customer media storage fetch failed")
        raise HTTPException(status_code=404, detail="Media not available")
    return Response(content=data, media_type=file_doc.get("mime_type") or ct)


# ---- EC10 Phase 10E-2 — customer decision submission ----------------------

class PortalDecisionSubmitIn(BaseModel):
    action_type: str
    option_id: Optional[str] = None
    comment: Optional[str] = None
    idempotency_key: Optional[str] = None


@router.post("/{room_id}/decisions", status_code=201)
async def submit_decision(
    room_id: str, payload: PortalDecisionSubmitIn, request: Request,
    identity: dict = Depends(require_portal_permission("portal:respond_decision_rooms")),
) -> dict:
    try:
        return await svc.submit_customer_decision(
            tenant_id=identity["tenant_id"], room_id=room_id,
            action_type=payload.action_type, option_id=payload.option_id, comment=payload.comment,
            source_access_mode="portal", customer_id=identity["customer_id"],
            actor_display=identity.get("full_name") or identity.get("email"),
            idempotency_key=payload.idempotency_key,
            ip=(request.client.host if request.client else None), user_agent=request.headers.get("user-agent"),
        )
    except DecisionRoomError as ex:
        _raise(ex)


@router.get("/{room_id}/decisions")
async def list_my_decisions(
    room_id: str, identity: dict = Depends(require_portal_permission("portal:view_decision_rooms")),
) -> dict:
    try:
        items = await svc.list_my_customer_decisions(
            tenant_id=identity["tenant_id"], room_id=room_id, customer_id=identity["customer_id"],
        )
        return {"items": items}
    except DecisionRoomError as ex:
        _raise(ex)



# ---- EC10 Phase 10E-3 — Questions, anchored comments/pins, save for later.
# Reuses the SAME `portal:respond_decision_rooms`/`portal:view_decision_rooms`
# permission split as Phase 10E-2 — a viewer-only identity can read this
# room's history but never submit a new question/overlay/save.

class PortalQuestionSubmitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_message: str
    option_id: Optional[str] = None
    source_file_id: Optional[str] = None
    visual_markup_id: Optional[str] = None
    markup_version_id: Optional[str] = None
    page_number: Optional[int] = None
    idempotency_key: Optional[str] = None


@router.post("/{room_id}/questions", status_code=201)
async def submit_question(
    room_id: str, payload: PortalQuestionSubmitIn,
    identity: dict = Depends(require_portal_permission("portal:respond_decision_rooms")),
) -> dict:
    try:
        return await svc.submit_customer_question(
            tenant_id=identity["tenant_id"], room_id=room_id, customer_message=payload.customer_message,
            option_id=payload.option_id, source_file_id=payload.source_file_id,
            visual_markup_id=payload.visual_markup_id, markup_version_id=payload.markup_version_id,
            page_number=payload.page_number, source_access_mode="portal", customer_id=identity["customer_id"],
            actor_display=identity.get("full_name") or identity.get("email"), idempotency_key=payload.idempotency_key,
        )
    except DecisionRoomError as ex:
        _raise(ex)


@router.get("/{room_id}/questions")
async def list_my_questions(
    room_id: str, identity: dict = Depends(require_portal_permission("portal:view_decision_rooms")),
) -> dict:
    try:
        return {"items": await svc.list_my_questions(tenant_id=identity["tenant_id"], room_id=room_id, customer_id=identity["customer_id"])}
    except DecisionRoomError as ex:
        _raise(ex)


class PortalOverlaySubmitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    overlay_type: str = "comment"
    customer_message: str
    normalized_x: float
    normalized_y: float
    source_file_id: Optional[str] = None
    visual_markup_id: Optional[str] = None
    markup_version_id: Optional[str] = None
    page_number: Optional[int] = None
    idempotency_key: Optional[str] = None


class PortalOverlayEditIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_message: str


@router.post("/{room_id}/overlays", status_code=201)
async def submit_overlay(
    room_id: str, payload: PortalOverlaySubmitIn,
    identity: dict = Depends(require_portal_permission("portal:respond_decision_rooms")),
) -> dict:
    try:
        return await svc.submit_customer_overlay(
            tenant_id=identity["tenant_id"], room_id=room_id, overlay_type=payload.overlay_type,
            customer_message=payload.customer_message, normalized_x=payload.normalized_x, normalized_y=payload.normalized_y,
            source_file_id=payload.source_file_id, visual_markup_id=payload.visual_markup_id,
            markup_version_id=payload.markup_version_id, page_number=payload.page_number,
            source_access_mode="portal", customer_id=identity["customer_id"], idempotency_key=payload.idempotency_key,
        )
    except DecisionRoomError as ex:
        _raise(ex)


@router.get("/{room_id}/overlays")
async def list_my_overlays(
    room_id: str, identity: dict = Depends(require_portal_permission("portal:view_decision_rooms")),
) -> dict:
    try:
        return {"items": await svc.list_my_overlays(tenant_id=identity["tenant_id"], room_id=room_id, customer_id=identity["customer_id"])}
    except DecisionRoomError as ex:
        _raise(ex)


@router.patch("/{room_id}/overlays/{overlay_id}")
async def edit_overlay(
    room_id: str, overlay_id: str, payload: PortalOverlayEditIn,
    identity: dict = Depends(require_portal_permission("portal:respond_decision_rooms")),
) -> dict:
    try:
        return await svc.edit_customer_overlay(
            tenant_id=identity["tenant_id"], room_id=room_id, overlay_id=overlay_id,
            customer_message=payload.customer_message, customer_id=identity["customer_id"],
        )
    except DecisionRoomError as ex:
        _raise(ex)


@router.post("/{room_id}/overlays/{overlay_id}/withdraw")
async def withdraw_overlay(
    room_id: str, overlay_id: str,
    identity: dict = Depends(require_portal_permission("portal:respond_decision_rooms")),
) -> dict:
    try:
        return await svc.withdraw_customer_overlay(
            tenant_id=identity["tenant_id"], room_id=room_id, overlay_id=overlay_id, customer_id=identity["customer_id"],
        )
    except DecisionRoomError as ex:
        _raise(ex)


class PortalSaveForLaterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: Optional[str] = None
    idempotency_key: Optional[str] = None


@router.post("/{room_id}/save-for-later", status_code=201)
async def save_for_later(
    room_id: str, payload: PortalSaveForLaterIn,
    identity: dict = Depends(require_portal_permission("portal:respond_decision_rooms")),
) -> dict:
    try:
        return await svc.submit_save_for_later(
            tenant_id=identity["tenant_id"], room_id=room_id, note=payload.note,
            source_access_mode="portal", customer_id=identity["customer_id"], idempotency_key=payload.idempotency_key,
        )
    except DecisionRoomError as ex:
        _raise(ex)


@router.get("/{room_id}/save-for-later")
async def list_my_saved_for_later(
    room_id: str, identity: dict = Depends(require_portal_permission("portal:view_decision_rooms")),
) -> dict:
    try:
        return {"items": await svc.list_my_saved_for_later(tenant_id=identity["tenant_id"], room_id=room_id, customer_id=identity["customer_id"])}
    except DecisionRoomError as ex:
        _raise(ex)
