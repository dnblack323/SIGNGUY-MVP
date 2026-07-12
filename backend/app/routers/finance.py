"""EC7 phase 7c — Finance Dashboard router.

Every response preserves the explicit `basis` label from the finance service.
Callers MUST NOT display or export these values without the label.
"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import finance_service

router = APIRouter(prefix="/finance", tags=["finance"])


def _tz(v: Optional[str]) -> str:
    return v or "UTC"


@router.get("/summary")
async def get_summary(date_from: Optional[str] = None, date_to: Optional[str] = None,
                       timezone: Optional[str] = None,
                       user: dict = Depends(require_permission(Perm.FINANCE_READ))) -> dict:
    return await finance_service.dashboard_summary(
        tenant_id=user["tenant_id"], date_from=date_from, date_to=date_to,
        timezone_name=_tz(timezone),
    )


@router.get("/revenue")
async def get_revenue(date_from: Optional[str] = None, date_to: Optional[str] = None,
                      timezone: Optional[str] = None,
                      user: dict = Depends(require_permission(Perm.FINANCE_READ))) -> dict:
    return await finance_service.invoice_revenue(
        tenant_id=user["tenant_id"], date_from=date_from, date_to=date_to,
        timezone_name=_tz(timezone),
    )


@router.get("/revenue-trend")
async def get_revenue_trend(date_from: str = Query(...), date_to: str = Query(...),
                             timezone: Optional[str] = None,
                             user: dict = Depends(require_permission(Perm.FINANCE_READ))) -> dict:
    return await finance_service.revenue_trend(
        tenant_id=user["tenant_id"], date_from=date_from, date_to=date_to,
        timezone_name=_tz(timezone),
    )


@router.get("/payments-received")
async def get_payments(date_from: Optional[str] = None, date_to: Optional[str] = None,
                       timezone: Optional[str] = None,
                       user: dict = Depends(require_permission(Perm.FINANCE_READ))) -> dict:
    return await finance_service.payments_received(
        tenant_id=user["tenant_id"], date_from=date_from, date_to=date_to,
        timezone_name=_tz(timezone),
    )


@router.get("/payments-received-trend")
async def get_payments_trend(date_from: str = Query(...), date_to: str = Query(...),
                              timezone: Optional[str] = None,
                              user: dict = Depends(require_permission(Perm.FINANCE_READ))) -> dict:
    return await finance_service.payments_received_trend(
        tenant_id=user["tenant_id"], date_from=date_from, date_to=date_to,
        timezone_name=_tz(timezone),
    )


@router.get("/refunds")
async def get_refunds(date_from: Optional[str] = None, date_to: Optional[str] = None,
                      timezone: Optional[str] = None,
                      user: dict = Depends(require_permission(Perm.FINANCE_READ))) -> dict:
    return await finance_service.refunds(
        tenant_id=user["tenant_id"], date_from=date_from, date_to=date_to,
        timezone_name=_tz(timezone),
    )


@router.get("/outstanding")
async def get_outstanding(timezone: Optional[str] = None,
                           user: dict = Depends(require_permission(Perm.FINANCE_READ))) -> dict:
    return await finance_service.outstanding_receivables(
        tenant_id=user["tenant_id"], timezone_name=_tz(timezone),
    )


@router.get("/expenses")
async def get_expenses(date_from: Optional[str] = None, date_to: Optional[str] = None,
                       category_key: Optional[str] = None,
                       timezone: Optional[str] = None,
                       user: dict = Depends(require_permission(Perm.FINANCE_READ))) -> dict:
    return await finance_service.expenses_total(
        tenant_id=user["tenant_id"], date_from=date_from, date_to=date_to,
        category_key=category_key, timezone_name=_tz(timezone),
    )


@router.get("/expenses-by-category")
async def get_expenses_by_cat(date_from: Optional[str] = None, date_to: Optional[str] = None,
                                timezone: Optional[str] = None,
                                user: dict = Depends(require_permission(Perm.FINANCE_READ))) -> dict:
    return await finance_service.expenses_by_category(
        tenant_id=user["tenant_id"], date_from=date_from, date_to=date_to,
        timezone_name=_tz(timezone),
    )


@router.get("/expense-trend")
async def get_expense_trend(date_from: str = Query(...), date_to: str = Query(...),
                             timezone: Optional[str] = None,
                             user: dict = Depends(require_permission(Perm.FINANCE_READ))) -> dict:
    return await finance_service.expense_trend(
        tenant_id=user["tenant_id"], date_from=date_from, date_to=date_to,
        timezone_name=_tz(timezone),
    )


@router.get("/tax-collected")
async def get_tax_collected(date_from: Optional[str] = None, date_to: Optional[str] = None,
                             timezone: Optional[str] = None,
                             user: dict = Depends(require_permission(Perm.FINANCE_READ))) -> dict:
    return await finance_service.tax_collected(
        tenant_id=user["tenant_id"], date_from=date_from, date_to=date_to,
        timezone_name=_tz(timezone),
    )


@router.get("/average-order-value")
async def get_aov(date_from: Optional[str] = None, date_to: Optional[str] = None,
                   timezone: Optional[str] = None,
                   user: dict = Depends(require_permission(Perm.FINANCE_READ))) -> dict:
    return await finance_service.average_order_value(
        tenant_id=user["tenant_id"], date_from=date_from, date_to=date_to,
        timezone_name=_tz(timezone),
    )


@router.get("/average-invoice-value")
async def get_aiv(date_from: Optional[str] = None, date_to: Optional[str] = None,
                   timezone: Optional[str] = None,
                   user: dict = Depends(require_permission(Perm.FINANCE_READ))) -> dict:
    return await finance_service.average_invoice_value(
        tenant_id=user["tenant_id"], date_from=date_from, date_to=date_to,
        timezone_name=_tz(timezone),
    )


@router.get("/top-customers")
async def get_top_customers(date_from: Optional[str] = None, date_to: Optional[str] = None,
                             limit: int = Query(10, le=100),
                             timezone: Optional[str] = None,
                             user: dict = Depends(require_permission(Perm.FINANCE_READ))) -> dict:
    return await finance_service.top_customers_by_revenue(
        tenant_id=user["tenant_id"], date_from=date_from, date_to=date_to,
        limit=limit, timezone_name=_tz(timezone),
    )


@router.get("/payment-method-breakdown")
async def get_pm_breakdown(date_from: Optional[str] = None, date_to: Optional[str] = None,
                             timezone: Optional[str] = None,
                             user: dict = Depends(require_permission(Perm.FINANCE_READ))) -> dict:
    return await finance_service.payment_method_breakdown(
        tenant_id=user["tenant_id"], date_from=date_from, date_to=date_to,
        timezone_name=_tz(timezone),
    )


@router.get("/estimated-gross-profit")
async def get_egp(date_from: Optional[str] = None, date_to: Optional[str] = None,
                   timezone: Optional[str] = None,
                   user: dict = Depends(require_permission(Perm.FINANCE_READ))) -> dict:
    return await finance_service.estimated_gross_profit(
        tenant_id=user["tenant_id"], date_from=date_from, date_to=date_to,
        timezone_name=_tz(timezone),
    )


@router.get("/estimated-net-operating")
async def get_eno(date_from: Optional[str] = None, date_to: Optional[str] = None,
                   timezone: Optional[str] = None,
                   user: dict = Depends(require_permission(Perm.FINANCE_READ))) -> dict:
    return await finance_service.estimated_net_operating(
        tenant_id=user["tenant_id"], date_from=date_from, date_to=date_to,
        timezone_name=_tz(timezone),
    )
