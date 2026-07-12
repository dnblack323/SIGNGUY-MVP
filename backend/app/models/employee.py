"""EC8 phase 8a — Employee (workforce/HR record).

An Employee is DISTINCT from a `User` (system login account, role
owner/admin/staff). Some employees have no login at all; some optionally
link to an existing `User` via `linked_user_id` (one-directional pointer —
the reverse lookup never happens on `User`). Employee.id is authoritative
for every EC8 collection (TimeEntry, Timesheet, PayPeriod snapshots,
PayrollTransaction, Certification, etc.) — never `User.id`.

Employees are never hard-deleted. Status transitions
(active -> suspended/inactive/terminated -> archived -> reactivated) are
audit events recorded by the caller via `services/audit.py`.

EC8 v1 explicitly excludes sensitive payroll identifiers (SSN, bank/routing
numbers, direct-deposit credentials) per the owner-approved EC8 preflight
gate — this is an internal workforce/time/gross-pay ledger, not a
payroll-processing or tax-filing service.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from .base import BaseDoc

EmployeeStatus = Literal["active", "suspended", "inactive", "terminated", "archived"]


class Employee(BaseDoc):
    tenant_id: str
    linked_user_id: Optional[str] = None   # optional pointer to an existing User (same tenant)
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role_label: Optional[str] = None       # free-text job title, e.g. "Install Tech"
    status: EmployeeStatus = "active"
    hire_date: Optional[str] = None        # ISO date string "YYYY-MM-DD" (BSON has no date-only type)
    termination_date: Optional[str] = None
    hourly_rate_cents: int = 1500          # locked default baseline: $15.00/hr, configurable per employee
    overtime_policy: Optional[str] = None  # foundation field only — no calculation logic in v1
    availability: Optional[str] = None     # free-text notes; superseded by availability_blocks below (8c)
    # EC8 phase 8c — structured availability for the Team Schedule builder's
    # conflict warnings. Each block: {id, kind: "unavailable"|"preferred",
    # day_of_week: 0-6 (Mon=0) | None, date_from, date_to, start_time,
    # end_time, note, created_at, created_by}. Deliberately NOT a PTO/accrual
    # ledger — just enough structure to warn a manager before double-booking.
    availability_blocks: list[dict] = Field(default_factory=list)
    portal_access: bool = False            # entitlement flag for Phase 8c Employee Portal — no behavior yet
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    notes: Optional[str] = None
    status_history: list[dict] = Field(default_factory=list)  # [{from,to,reason,actor_user_id,at}]
