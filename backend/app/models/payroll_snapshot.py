"""EC8 phase 8d — PayrollSnapshot (frozen per-Employee, per-PayPeriod calculation result).

Recalculated freely while the parent PayPeriod is `status == "open"`
(each recalculation supersedes the prior snapshot's row in place, but the
underlying `earning`/`overtime_earning` PayrollTransaction rows it generated
are voided-and-replaced, never deleted — see `services/payroll_service.py`).
Once the PayPeriod is approved+, this document is `locked=True` and must
never be silently rewritten — a later Employee.hourly_rate_cents change can
never retroactively alter `hourly_rate_cents` on an existing snapshot.
"""
from __future__ import annotations

from typing import Optional

from pydantic import Field

from .base import BaseDoc


class PayrollSnapshot(BaseDoc):
    tenant_id: str
    pay_period_id: str
    employee_id: str
    employee_name: str
    employee_status: str
    linked_user_id: Optional[str] = None
    hourly_rate_cents: int
    overtime_policy_snapshot: dict = Field(default_factory=dict)  # {enabled, weekly_threshold_minutes, multiplier, source}
    regular_minutes: int = 0
    overtime_minutes: int = 0
    gross_regular_cents: int = 0
    gross_overtime_cents: int = 0
    adjustment_total_cents: int = 0
    advance_total_cents: int = 0
    repayment_total_cents: int = 0
    payment_total_cents: int = 0
    carryover_in_cents: int = 0
    carryover_out_cents: int = 0
    total_earned_cents: int = 0        # gross + adjustments + carryover_in - repayments
    total_paid_cents: int = 0          # advances + payments
    remaining_balance_cents: int = 0   # total_earned - total_paid
    calculated_at: Optional[str] = None
    calculation_version: int = 0
    source_time_entry_ids: list[str] = Field(default_factory=list)
    source_timesheet_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    locked: bool = False
    created_by: str
    updated_by: str
