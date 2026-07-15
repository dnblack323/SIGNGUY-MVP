"""EC10 Phase 10E-1 — Customer Portal Decision Room access (read-only).

Portal-authenticated (JWT, `sub_scope="portal"`, `portal_type="customer"`)
retrieval of Decision Rooms belonging to the caller's own Customer record.
Returns ONLY the frozen published-version content — see
`services/decision_room_service.get_customer_view()` for the shared
customer-safe rendering logic (also used by the Public Token route in
`public_actions.py`). No selection/rejection/comment/question/change-request
capture exists here — that is Phase 10E-2/10E-3 (not built).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..deps_portal import require_portal_permission
from ..services import decision_room_service as svc
from ..services.decision_room_service import DecisionRoomError

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
