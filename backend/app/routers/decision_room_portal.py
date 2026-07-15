"""EC10 Phase 10E-1 — Customer Portal Decision Room access (read-only).

Portal-authenticated (JWT, `sub_scope="portal"`, `portal_type="customer"`)
retrieval of Decision Rooms belonging to the caller's own Customer record.
Returns ONLY the frozen published-version content — see
`services/decision_room_service.get_customer_view()` for the shared
customer-safe rendering logic (also used by the Public Token route in
`public_actions.py`). No selection/rejection/comment/question/change-request
capture exists here — that is Phase 10E-2/10E-3 (not built).

Also serves customer-safe DERIVATIVE media (images/PDFs/proof previews/
rendered markup previews) referenced by that same frozen version — see
`services/decision_room_service.resolve_customer_safe_media()`. This never
becomes a general file browser: only ids actually referenced in the frozen
published version (and, for plain attachments, explicitly `visibility ==
"customer_visible"`) are ever servable.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Response

from ..deps_portal import require_portal_permission
from ..services import decision_room_service as svc
from ..services import storage
from ..services.decision_room_service import DecisionRoomError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portal/decision-rooms", tags=["portal_decision_rooms"])


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
