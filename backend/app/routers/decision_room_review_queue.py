"""EC10 Phase 10E-4 - internal Decision Room review queue.

This router is deliberately thin. The normalized queue, side metadata, and
internal-note storage were scaffolded in ``decision_room_service``; endpoints
here expose that existing service without creating duplicate queue records or
any commercial apply path.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import decision_room_service as svc
from ..services.decision_room_service import DecisionRoomError

router = APIRouter(prefix="/decision-room-review-queue", tags=["decision-room-review-queue"])

_ERROR_STATUS = {
    "review_record_not_found": 404,
    "assigned_user_not_found": 404,
    "invalid_action_type": 400,
    "acknowledge_not_supported": 400,
    "question_message_required": 400,
}


def _raise(ex: DecisionRoomError) -> None:
    raise HTTPException(status_code=_ERROR_STATUS.get(ex.code, 400), detail=str(ex))


class ReviewAssignmentIn(BaseModel):
    assigned_user_id: Optional[str] = None


class InternalNoteIn(BaseModel):
    note: str = Field(..., min_length=1, max_length=2000)


@router.get("")
async def list_queue(
    activity_type: Optional[str] = None,
    status: Optional[str] = None,
    decision_room_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    assigned_user_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    unresolved_only: bool = False,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.DECISION_ROOM_READ)),
) -> dict:
    return await svc.list_review_queue(
        tenant_id=user["tenant_id"],
        activity_type=activity_type,
        status=status,
        decision_room_id=decision_room_id,
        customer_id=customer_id,
        assigned_user_id=assigned_user_id,
        date_from=date_from,
        date_to=date_to,
        unresolved_only=unresolved_only,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.post("/{record_type}/{record_id}/acknowledge")
async def acknowledge_item(
    record_type: str,
    record_id: str,
    user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE)),
) -> dict:
    try:
        return await svc.acknowledge_review_item(
            tenant_id=user["tenant_id"],
            record_type=record_type,
            record_id=record_id,
            actor_user_id=user["id"],
            actor_email=user["email"],
        )
    except DecisionRoomError as ex:
        _raise(ex)


@router.post("/{record_type}/{record_id}/assign")
async def assign_item(
    record_type: str,
    record_id: str,
    payload: ReviewAssignmentIn,
    user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE)),
) -> dict:
    try:
        return await svc.assign_review_item(
            tenant_id=user["tenant_id"],
            record_type=record_type,
            record_id=record_id,
            assigned_user_id=payload.assigned_user_id,
            actor_user_id=user["id"],
            actor_email=user["email"],
        )
    except DecisionRoomError as ex:
        _raise(ex)


@router.get("/{record_type}/{record_id}/notes")
async def list_notes(
    record_type: str,
    record_id: str,
    user: dict = Depends(require_permission(Perm.DECISION_ROOM_READ)),
) -> dict:
    try:
        return {"items": await svc.list_internal_notes(tenant_id=user["tenant_id"], record_type=record_type, record_id=record_id)}
    except DecisionRoomError as ex:
        _raise(ex)


@router.post("/{record_type}/{record_id}/notes", status_code=201)
async def add_note(
    record_type: str,
    record_id: str,
    payload: InternalNoteIn,
    user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE)),
) -> dict:
    try:
        return await svc.add_internal_note(
            tenant_id=user["tenant_id"],
            record_type=record_type,
            record_id=record_id,
            note=payload.note,
            actor_user_id=user["id"],
            actor_email=user["email"],
        )
    except DecisionRoomError as ex:
        _raise(ex)
