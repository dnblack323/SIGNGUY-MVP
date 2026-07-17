"""EC10 Phase 10F - staff-controlled Decision Room commercial apply."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import decision_room_service as svc
from ..services.decision_room_service import DecisionRoomError

router = APIRouter(prefix="/decision-rooms", tags=["decision-rooms"])

_ERROR_STATUS = {
    "room_not_found": 404,
    "decision_not_found": 404,
    "version_not_found": 404,
    "option_not_found": 404,
    "pricing_snapshot_not_found": 404,
    "quote_not_found": 404,
    "quote_line_item_not_found": 404,
    "order_not_found": 404,
    "order_item_not_found": 404,
    "quote_converted": 400,
    "decision_not_applicable": 400,
    "decision_apply_target_required": 400,
    "decision_superseded": 409,
}


def _raise(ex: DecisionRoomError) -> None:
    detail: Any = {"message": str(ex), "errors": ex.details} if ex.details else str(ex)
    raise HTTPException(status_code=_ERROR_STATUS.get(ex.code, 400), detail=detail)


class DecisionApplyIn(BaseModel):
    note: Optional[str] = None


@router.post("/{room_id}/decisions/{decision_id}/apply")
async def apply_decision(
    room_id: str,
    decision_id: str,
    payload: DecisionApplyIn = DecisionApplyIn(),
    user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE)),
) -> dict:
    try:
        return await svc.apply_customer_decision(
            tenant_id=user["tenant_id"],
            room_id=room_id,
            decision_id=decision_id,
            actor_user_id=user["id"],
            actor_email=user["email"],
            note=payload.note,
        )
    except DecisionRoomError as ex:
        _raise(ex)
