"""EC9 Phase 9G — Immutable Pricing Snapshot endpoints (§3–§7).

Tenant-scoped read + deterministic explain/compare only. Snapshot creation
happens exclusively as a side-effect of Quote/Order/Order Item pricing writes
(`routers/quotes.py`, `routers/orders.py`, `services/quote_conversion.py`) —
there is intentionally no create/delete/update endpoint here.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..core.permissions import Perm
from ..deps import require_permission
from ..services.pricing_snapshot_records import (
    compare_snapshots,
    explain_snapshot,
    get_snapshot_record,
    list_snapshot_records,
)

router = APIRouter(prefix="/pricing/snapshots", tags=["pricing"])


class CompareIn(BaseModel):
    base_snapshot_id: str
    candidate_snapshot_id: str


@router.get("")
async def list_snapshots(
    source_type: Optional[str] = Query(None),
    source_id: Optional[str] = Query(None),
    user: dict = Depends(require_permission(Perm.PRICING_READ)),
) -> dict:
    items = await list_snapshot_records(user["tenant_id"], source_type=source_type, source_id=source_id)
    return {"items": items}


@router.get("/{snapshot_id}")
async def get_snapshot(snapshot_id: str, user: dict = Depends(require_permission(Perm.PRICING_READ))) -> dict:
    doc = await get_snapshot_record(user["tenant_id"], snapshot_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Pricing snapshot not found")
    return doc


@router.get("/{snapshot_id}/explain")
async def explain(snapshot_id: str, user: dict = Depends(require_permission(Perm.PRICING_READ))) -> dict:
    doc = await get_snapshot_record(user["tenant_id"], snapshot_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Pricing snapshot not found")
    previous = None
    if doc.get("previous_snapshot_id"):
        previous = await get_snapshot_record(user["tenant_id"], doc["previous_snapshot_id"])
    return explain_snapshot(doc, previous)


@router.post("/compare")
async def compare(payload: CompareIn, user: dict = Depends(require_permission(Perm.PRICING_READ))) -> dict:
    base = await get_snapshot_record(user["tenant_id"], payload.base_snapshot_id)
    candidate = await get_snapshot_record(user["tenant_id"], payload.candidate_snapshot_id)
    if not base or not candidate:
        raise HTTPException(status_code=404, detail="One or both snapshots not found")
    return {
        "base_snapshot_id": base["id"],
        "candidate_snapshot_id": candidate["id"],
        "diff": compare_snapshots(base, candidate),
    }
