from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import approval_center_service as svc
from ..services.decision_room_service import DecisionRoomError

router = APIRouter(prefix="/approval-center", tags=["approval-center"])

_ERROR_STATUS = {
    "customer_not_found": 404,
    "quote_not_found": 404,
    "quote_line_item_not_found": 404,
    "order_not_found": 404,
    "order_item_not_found": 404,
    "work_order_not_found": 404,
    "title_required": 400,
    "order_item_order_mismatch": 400,
}


class ApprovalWorkCreateIn(BaseModel):
    target_type: str = Field(pattern="^(customer|quote|quote_line_item|order|order_item)$")
    target_id: str = Field(min_length=1)
    title: Optional[str] = None
    customer_safe_intro: Optional[str] = None
    allow_customer_comments: bool = True
    allow_customer_questions: bool = True
    allow_change_requests: bool = True
    allow_reject_all: bool = False


def _raise_decision_room_error(ex: DecisionRoomError) -> None:
    raise HTTPException(status_code=_ERROR_STATUS.get(ex.code, 400), detail=str(ex))


@router.get("/queue")
async def authority_queue(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    kind: Optional[str] = Query(None),
    unresolved_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.DECISION_ROOM_READ)),
) -> dict:
    return await svc.list_authority_queue(
        tenant_id=user["tenant_id"],
        search=search,
        status=status,
        kind=kind,
        unresolved_only=unresolved_only,
        limit=limit,
        offset=offset,
    )


@router.get("/targets")
async def targets(
    target_type: str = Query(pattern="^(customer|quote|quote_line_item|order|order_item)$"),
    search: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    user: dict = Depends(require_permission(Perm.DECISION_ROOM_READ)),
) -> dict:
    try:
        return await svc.search_targets(
            tenant_id=user["tenant_id"],
            target_type=target_type,
            search=search,
            limit=limit,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@router.get("/history")
async def approval_history(
    source_type: str = Query(pattern="^(quote|order|order_item|work_order_summary|proof_version|contract)$"),
    source_id: str = Query(min_length=1),
    user: dict = Depends(require_permission(Perm.DECISION_ROOM_READ)),
) -> dict:
    try:
        return await svc.list_approval_history(
            tenant_id=user["tenant_id"],
            source_type=source_type,
            source_id=source_id,
        )
    except DecisionRoomError as ex:
        _raise_decision_room_error(ex)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@router.post("/work", status_code=201)
async def create_approval_work(
    payload: ApprovalWorkCreateIn,
    user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE)),
) -> dict:
    try:
        return await svc.create_approval_work(
            tenant_id=user["tenant_id"],
            target_type=payload.target_type,
            target_id=payload.target_id,
            title=payload.title,
            customer_safe_intro=payload.customer_safe_intro,
            allow_customer_comments=payload.allow_customer_comments,
            allow_customer_questions=payload.allow_customer_questions,
            allow_change_requests=payload.allow_change_requests,
            allow_reject_all=payload.allow_reject_all,
            actor_user_id=user["id"],
            actor_email=user["email"],
        )
    except DecisionRoomError as ex:
        _raise_decision_room_error(ex)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
