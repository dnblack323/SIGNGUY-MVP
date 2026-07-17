"""EC11 Phase 11B - staff production timeline endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.db import db
from ..core.permissions import Perm
from ..deps import require_permission
from ..services import production_timeline_service as svc

router = APIRouter(tags=["production-timeline"])


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: {value}")


async def _timeline(
    *,
    tenant_id: str,
    scope: str,
    source_id: str,
    event_category: Optional[str],
    event_type: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    actor: Optional[str],
    visibility: Optional[str],
    sort: Literal["asc", "desc"],
    limit: int,
    offset: int,
) -> dict:
    try:
        return await svc.list_timeline(
            tenant_id=tenant_id,
            scope=scope,
            source_id=source_id,
            event_category=event_category,
            event_type=event_type,
            date_from=_parse_date(date_from),
            date_to=_parse_date(date_to),
            actor=actor,
            visibility=visibility,
            sort=sort,
            limit=limit,
            offset=offset,
        )
    except ValueError as ex:
        status = 404 if str(ex).endswith("_not_found") else 400
        raise HTTPException(status_code=status, detail=str(ex))


@router.get("/orders/{order_id}/timeline")
async def order_timeline(
    order_id: str,
    event_category: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    actor: Optional[str] = Query(None),
    visibility: Optional[str] = Query(None),
    sort: Literal["asc", "desc"] = Query("desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.ORDER_READ)),
) -> dict:
    return await _timeline(
        tenant_id=user["tenant_id"], scope="order", source_id=order_id,
        event_category=event_category, event_type=event_type,
        date_from=date_from, date_to=date_to, actor=actor, visibility=visibility,
        sort=sort, limit=limit, offset=offset,
    )


@router.get("/orders/{order_id}/items/{item_id}/timeline")
async def order_item_timeline(
    order_id: str,
    item_id: str,
    event_category: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    actor: Optional[str] = Query(None),
    visibility: Optional[str] = Query(None),
    sort: Literal["asc", "desc"] = Query("desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.ORDER_READ)),
) -> dict:
    item = await db.order_items.find_one({"tenant_id": user["tenant_id"], "id": item_id, "order_id": order_id}, {"_id": 0, "id": 1})
    if not item:
        raise HTTPException(status_code=404, detail="order_item_not_found")
    result = await _timeline(
        tenant_id=user["tenant_id"], scope="order_item", source_id=item_id,
        event_category=event_category, event_type=event_type,
        date_from=date_from, date_to=date_to, actor=actor, visibility=visibility,
        sort=sort, limit=limit, offset=offset,
    )
    return result


@router.get("/work-orders/{work_order_id}/timeline")
async def work_order_timeline(
    work_order_id: str,
    event_category: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    actor: Optional[str] = Query(None),
    visibility: Optional[str] = Query(None),
    sort: Literal["asc", "desc"] = Query("desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.WORK_ORDER_READ)),
) -> dict:
    return await _timeline(
        tenant_id=user["tenant_id"], scope="work_order", source_id=work_order_id,
        event_category=event_category, event_type=event_type,
        date_from=date_from, date_to=date_to, actor=actor, visibility=visibility,
        sort=sort, limit=limit, offset=offset,
    )
