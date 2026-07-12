"""EC7 phase 7c — Tax reporting router."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import tax_service

router = APIRouter(prefix="/tax", tags=["tax"])


def _tz(v: Optional[str]) -> str:
    return v or "UTC"


# ---------- Exemption CRUD ----------
class ExemptionIn(BaseModel):
    customer_id: str
    jurisdiction: str
    reference: str
    effective_from: str
    effective_to: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None


@router.get("/exemptions")
async def list_exemptions(customer_id: Optional[str] = None,
                          jurisdiction: Optional[str] = None,
                          include_archived: bool = False,
                          user: dict = Depends(require_permission(Perm.TAX_REPORT_READ))) -> dict:
    items = await tax_service.list_exemptions(
        tenant_id=user["tenant_id"], customer_id=customer_id,
        jurisdiction=jurisdiction, include_archived=include_archived,
    )
    return {"items": items}


@router.post("/exemptions", status_code=201)
async def upsert_exemption(payload: ExemptionIn,
                            user: dict = Depends(require_permission(Perm.SETTINGS_WRITE))) -> dict:
    try:
        return await tax_service.upsert_exemption(
            tenant_id=user["tenant_id"], customer_id=payload.customer_id,
            jurisdiction=payload.jurisdiction, reference=payload.reference,
            effective_from=payload.effective_from, effective_to=payload.effective_to,
            reason=payload.reason, notes=payload.notes,
            actor_user_id=user["id"],
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@router.post("/exemptions/{exemption_id}/archive")
async def archive_exemption(exemption_id: str,
                             user: dict = Depends(require_permission(Perm.SETTINGS_WRITE))) -> dict:
    try:
        return await tax_service.archive_exemption(
            tenant_id=user["tenant_id"], exemption_id=exemption_id,
        )
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@router.get("/exemptions/check")
async def check_exemption(customer_id: str,
                           jurisdiction: Optional[str] = None,
                           at_date: Optional[str] = None,
                           user: dict = Depends(require_permission(Perm.TAX_REPORT_READ))) -> dict:
    return await tax_service.is_customer_exempt(
        tenant_id=user["tenant_id"], customer_id=customer_id,
        jurisdiction=jurisdiction, at_date=at_date,
    )


# ---------- Reports ----------
@router.get("/collected")
async def report_collected(date_from: Optional[str] = None,
                            date_to: Optional[str] = None,
                            timezone: Optional[str] = None,
                            user: dict = Depends(require_permission(Perm.TAX_REPORT_READ))) -> dict:
    return await tax_service.tax_collected_by_range(
        tenant_id=user["tenant_id"], date_from=date_from,
        date_to=date_to, timezone_name=_tz(timezone),
    )


@router.get("/collected-by-jurisdiction")
async def report_by_jurisdiction(date_from: Optional[str] = None,
                                  date_to: Optional[str] = None,
                                  timezone: Optional[str] = None,
                                  user: dict = Depends(require_permission(Perm.TAX_REPORT_READ))) -> dict:
    return await tax_service.tax_collected_by_jurisdiction(
        tenant_id=user["tenant_id"], date_from=date_from,
        date_to=date_to, timezone_name=_tz(timezone),
    )


@router.get("/manual-overrides")
async def report_manual_overrides(date_from: Optional[str] = None,
                                   date_to: Optional[str] = None,
                                   timezone: Optional[str] = None,
                                   user: dict = Depends(require_permission(Perm.TAX_REPORT_READ))) -> dict:
    return await tax_service.manual_tax_override_report(
        tenant_id=user["tenant_id"], date_from=date_from,
        date_to=date_to, timezone_name=_tz(timezone),
    )


@router.get("/exempt-customers")
async def report_exempt_customers(jurisdiction: Optional[str] = None,
                                    date_from: Optional[str] = None,
                                    date_to: Optional[str] = None,
                                    timezone: Optional[str] = None,
                                    user: dict = Depends(require_permission(Perm.TAX_REPORT_READ))) -> dict:
    return await tax_service.exempt_customer_report(
        tenant_id=user["tenant_id"], jurisdiction=jurisdiction,
        date_from=date_from, date_to=date_to, timezone_name=_tz(timezone),
    )
