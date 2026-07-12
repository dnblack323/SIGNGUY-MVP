"""EC8 phase 8d — PayrollTransaction (append-only ledger; the single source
of truth every calculation reads from — see `services/payroll_service.py`).

Never deleted, never mutated in place after creation (aside from the
`voided*` fields, which record a correction event without touching
`amount_cents`). Corrections always add a NEW row (`type="void"` reversal or
`type="correction"` delta) that references the original via
`source_record_type`/`source_record_id` — the ledger's running sum is always
correct without ever rewriting history.
"""
from __future__ import annotations

from typing import Literal, Optional

from .base import BaseDoc

PayrollTransactionType = Literal[
    "earning", "overtime_earning", "adjustment", "advance", "advance_repayment",
    "payment", "carryover_in", "carryover_out", "correction", "void",
]


class PayrollTransaction(BaseDoc):
    tenant_id: str
    employee_id: str
    pay_period_id: str
    type: PayrollTransactionType
    amount_cents: int              # signed; see payroll_service.py docstring for the sign convention per type
    effective_date: str            # "YYYY-MM-DD"
    reference: Optional[str] = None
    notes: Optional[str] = None
    source_record_type: Optional[str] = None   # e.g. "payroll_transaction", "timesheet"
    source_record_id: Optional[str] = None
    payment_method: Optional[str] = None        # only meaningful for type == "payment"
    payment_date: Optional[str] = None          # only meaningful for type == "payment"
    carryover_link_id: Optional[str] = None      # for carryover_in/out — id of the paired sibling transaction
    idempotency_key: Optional[str] = None
    audit_ref: Optional[str] = None
    voided: bool = False
    voided_by: Optional[str] = None
    voided_at: Optional[str] = None
    void_reason: Optional[str] = None
    created_by: str
