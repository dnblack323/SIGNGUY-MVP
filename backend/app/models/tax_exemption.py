"""EC7 phase 7c — Tax exemption records + reporting model.

Tenant-scoped Customer tax-exemption records. Additive to the Customer model
so no existing MVP customer row is rewritten. Each row captures:
  - exemption reference (state resale cert #, nonprofit ID, etc.)
  - jurisdiction (US state / country / freeform)
  - effective_from + optional effective_to
  - archived flag

Reports join on `tax_exemptions` when filtering exempt vs taxable sales, so
Customer.exempt_status can be added later without contradicting history.
"""
from __future__ import annotations
from typing import Optional
from .base import BaseDoc


class TaxExemption(BaseDoc):
    tenant_id: str
    customer_id: str
    jurisdiction: str                     # e.g. "US-CA", "US-NY", "US-NJ", "NON_US"
    reference: str                        # certificate id / resale #
    reason: Optional[str] = None
    effective_from: str                   # ISO date
    effective_to: Optional[str] = None    # ISO date; None = still active
    notes: Optional[str] = None
    archived: bool = False
    created_by: str
