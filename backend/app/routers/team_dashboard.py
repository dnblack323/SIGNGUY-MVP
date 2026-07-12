"""EC8 phase 8a — Team Dashboard foundation. EC8 phase 8c — added a compact
scheduling snapshot only (no full calendar widget — Team Schedule page owns
the detailed grid).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import announcement_service, employee_service, schedule_service

router = APIRouter(prefix="/team", tags=["team-dashboard"])


@router.get("/dashboard")
async def team_dashboard(user: dict = Depends(require_permission(Perm.EMPLOYEE_READ))) -> dict:
    counts = await employee_service.status_counts(tenant_id=user["tenant_id"])
    announcements = await announcement_service.active_announcements(tenant_id=user["tenant_id"], limit=5)
    scheduling = await schedule_service.today_snapshot(tenant_id=user["tenant_id"])
    return {
        "employee_status_counts": counts,
        "active_employees": counts.get("active", 0),
        "announcements": announcements,
        "scheduling": scheduling,
    }
