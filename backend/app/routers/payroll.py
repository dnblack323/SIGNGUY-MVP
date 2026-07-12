"""EC8 phase 8d — Payroll router (manager-facing).

Internal gross-pay ledger only — no ACH/direct-deposit, no tax withholding,
no statutory filings. See `services/payroll_service.py` for the full
architecture note.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import payroll_service
from ..services.payroll_service import PayrollError

router = APIRouter(prefix="/payroll", tags=["payroll"])


def _raise(e: PayrollError):
    raise HTTPException(status_code=e.status_code, detail=e.detail)


# ---- Settings ----

@router.get("/settings")
async def get_settings(user: dict = Depends(require_permission(Perm.PAYROLL_READ))) -> dict:
    return await payroll_service.get_payroll_settings(tenant_id=user["tenant_id"])


class SettingsUpdateIn(BaseModel):
    overtime_enabled: Optional[bool] = None
    weekly_threshold_minutes: Optional[int] = None
    overtime_multiplier: Optional[float] = None
    rounding_policy: Optional[str] = None
    default_payday: Optional[str] = None
    work_week_start: Optional[str] = None


@router.put("/settings")
async def update_settings(payload: SettingsUpdateIn, user: dict = Depends(require_permission(Perm.PAYROLL_MANAGE))) -> dict:
    updates = payload.model_dump(exclude_none=True)
    try:
        return await payroll_service.update_payroll_settings(tenant_id=user["tenant_id"], updates=updates, updated_by=user["id"])
    except PayrollError as e:
        _raise(e)


# ---- Pay Periods ----

@router.get("/periods")
async def list_periods(status: Optional[str] = None, user: dict = Depends(require_permission(Perm.PAYROLL_READ))) -> dict:
    return {"items": await payroll_service.list_pay_periods(tenant_id=user["tenant_id"], status=status)}


@router.get("/periods/current")
async def get_current_period(period_start: Optional[str] = None, user: dict = Depends(require_permission(Perm.PAYROLL_MANAGE))) -> dict:
    from datetime import date
    anchor = period_start or date.today().isoformat()
    period = await payroll_service.get_or_create_pay_period(tenant_id=user["tenant_id"], period_start=anchor, actor_user_id=user["id"])
    return await payroll_service.get_pay_period_detail(tenant_id=user["tenant_id"], period_id=period["id"])


@router.get("/periods/{period_id}")
async def get_period(period_id: str, user: dict = Depends(require_permission(Perm.PAYROLL_READ))) -> dict:
    try:
        return await payroll_service.get_pay_period_detail(tenant_id=user["tenant_id"], period_id=period_id)
    except PayrollError as e:
        _raise(e)


@router.post("/periods/{period_id}/recalculate")
async def recalculate(period_id: str, user: dict = Depends(require_permission(Perm.PAYROLL_MANAGE))) -> dict:
    try:
        return await payroll_service.recalc_period(tenant_id=user["tenant_id"], period_id=period_id, actor_user_id=user["id"], actor_email=user["email"])
    except PayrollError as e:
        _raise(e)


class OverrideIn(BaseModel):
    override_reason: Optional[str] = None


@router.post("/periods/{period_id}/approve")
async def approve(period_id: str, payload: OverrideIn, user: dict = Depends(require_permission(Perm.PAYROLL_MANAGE))) -> dict:
    try:
        return await payroll_service.approve_period(tenant_id=user["tenant_id"], period_id=period_id, actor_user_id=user["id"],
                                                      actor_email=user["email"], override_reason=payload.override_reason)
    except PayrollError as e:
        _raise(e)


class ReasonIn(BaseModel):
    reason: str


@router.post("/periods/{period_id}/reopen")
async def reopen(period_id: str, payload: ReasonIn, user: dict = Depends(require_permission(Perm.PAYROLL_MANAGE))) -> dict:
    try:
        return await payroll_service.reopen_period(tenant_id=user["tenant_id"], period_id=period_id, actor_user_id=user["id"],
                                                     actor_email=user["email"], reason=payload.reason)
    except PayrollError as e:
        _raise(e)


@router.post("/periods/{period_id}/close")
async def close(period_id: str, payload: OverrideIn, user: dict = Depends(require_permission(Perm.PAYROLL_MANAGE))) -> dict:
    try:
        return await payroll_service.close_period(tenant_id=user["tenant_id"], period_id=period_id, actor_user_id=user["id"],
                                                    actor_email=user["email"], override_reason=payload.override_reason)
    except PayrollError as e:
        _raise(e)


@router.post("/periods/{period_id}/void")
async def void(period_id: str, payload: ReasonIn, user: dict = Depends(require_permission(Perm.PAYROLL_MANAGE))) -> dict:
    try:
        return await payroll_service.void_period(tenant_id=user["tenant_id"], period_id=period_id, actor_user_id=user["id"],
                                                   actor_email=user["email"], reason=payload.reason)
    except PayrollError as e:
        _raise(e)


# ---- Ledger transactions ----

class TransactionIn(BaseModel):
    employee_id: str
    pay_period_id: str
    type: str
    amount_cents: int
    effective_date: str
    reference: Optional[str] = None
    notes: Optional[str] = None
    payment_method: Optional[str] = None
    payment_date: Optional[str] = None
    idempotency_key: Optional[str] = None


@router.post("/transactions")
async def create_transaction(payload: TransactionIn, user: dict = Depends(require_permission(Perm.PAYROLL_MANAGE))) -> dict:
    try:
        return await payroll_service.add_manual_transaction(
            tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"], **payload.model_dump(),
        )
    except PayrollError as e:
        _raise(e)


@router.post("/transactions/{transaction_id}/void")
async def void_transaction(transaction_id: str, payload: ReasonIn, user: dict = Depends(require_permission(Perm.PAYROLL_MANAGE))) -> dict:
    try:
        return await payroll_service.void_manual_transaction(tenant_id=user["tenant_id"], transaction_id=transaction_id,
                                                               actor_user_id=user["id"], actor_email=user["email"], reason=payload.reason)
    except PayrollError as e:
        _raise(e)


@router.get("/transactions")
async def list_transactions(employee_id: Optional[str] = None, pay_period_id: Optional[str] = None,
                             include_voided: bool = False, user: dict = Depends(require_permission(Perm.PAYROLL_READ))) -> dict:
    return {"items": await payroll_service.list_transactions(tenant_id=user["tenant_id"], employee_id=employee_id,
                                                               pay_period_id=pay_period_id, include_voided=include_voided)}


@router.get("/employees/{employee_id}/snapshots")
async def employee_snapshots(employee_id: str, user: dict = Depends(require_permission(Perm.PAYROLL_READ))) -> dict:
    return {"items": await payroll_service.list_employee_snapshots(tenant_id=user["tenant_id"], employee_id=employee_id)}
