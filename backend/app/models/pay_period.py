"""EC8 phase 8d — Pay Period (single authoritative tenant-scoped weekly payroll period).

One PayPeriod per tenant per Saturday-Friday work week (payday == the Friday
`end_date`). This is an internal gross-pay ledger container — NOT a
payroll-processing, tax-filing, or banking record. `PayrollSnapshot` (one
per Employee per period) and `PayrollTransaction` (append-only ledger) are
the two other authoritative collections this phase owns; nothing else
calculates payroll.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from .base import BaseDoc

PayPeriodStatus = Literal["open", "review", "approved", "partially_paid", "paid", "closed", "voided"]
PayPeriodLockState = Literal["unlocked", "restricted", "locked"]


class PayPeriod(BaseDoc):
    tenant_id: str
    start_date: str                # Saturday, "YYYY-MM-DD"
    end_date: str                  # Friday, "YYYY-MM-DD"
    payday: str                    # Friday, "YYYY-MM-DD" — always equals end_date in v1
    status: PayPeriodStatus = "open"
    period_label: Optional[str] = None
    lock_state: PayPeriodLockState = "unlocked"
    version: int = 1
    reviewed_at: Optional[str] = None
    reviewed_by: Optional[str] = None
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    finalized_at: Optional[str] = None
    finalized_by: Optional[str] = None
    closed_at: Optional[str] = None
    closed_by: Optional[str] = None
    voided_at: Optional[str] = None
    voided_by: Optional[str] = None
    void_reason: Optional[str] = None
    notes: Optional[str] = None
    status_history: list[dict] = Field(default_factory=list)  # [{from, to, reason, actor_user_id, at}]
    created_by: str
    updated_by: str
