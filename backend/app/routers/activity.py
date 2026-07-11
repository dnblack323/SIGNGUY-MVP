"""EC2 — Activity feed router (tenant-scoped read)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..core.permissions import Perm
from ..deps import require_permission
from ..services.activity import list_activity

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("")
async def list_(
    module: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.AUDIT_READ)),
) -> dict:
    return await list_activity(
        tenant_id=user["tenant_id"],
        module=module,
        entity_type=entity_type,
        entity_id=entity_id,
        severity=severity,
        limit=limit,
        skip=skip,
    )
