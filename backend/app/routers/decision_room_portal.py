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
from pydantic import BaseModel

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
