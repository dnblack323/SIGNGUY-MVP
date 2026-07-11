"""EC2 — Integration status (read-only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..core.permissions import Perm
from ..deps import require_permission
from ..services.integration_status import integration_status

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/status")
async def status(user: dict = Depends(require_permission(Perm.INTEGRATION_READ))) -> dict:
    return integration_status()
