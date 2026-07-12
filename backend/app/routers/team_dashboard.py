"""EC8 phase 8a — Team Dashboard foundation.

Deliberately compact for Phase 8a: employee status summary + active
announcements only. Time Clock / Timesheet / Payroll / Certification widgets
land in their owning phases (8b/8d/8e) — no placeholder empty sections here,
per the owner's "keep layout compact, no giant empty sections" instruction.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import announcement_service, employee_service

router = APIRouter(prefix="/team", tags=["team-dashboard"])


@router.get("/dashboard")
async def team_dashboard(user: dict = Depends(require_permission(Perm.EMPLOYEE_READ))) -> dict:
    counts = await employee_service.status_counts(tenant_id=user["tenant_id"])
    announcements = await announcement_service.active_announcements(tenant_id=user["tenant_id"], limit=5)
    return {
        "employee_status_counts": counts,
        "active_employees": counts.get("active", 0),
        "announcements": announcements,
    }
