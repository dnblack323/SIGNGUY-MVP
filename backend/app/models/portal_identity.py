"""EC6 — Portal Identity. Extended additively in EC8 phase 8c for Employee Portal.

Separate collection from `users`. A portal identity belongs to exactly one
tenant AND (depending on `portal_type`) exactly one Customer OR exactly one
Employee — never both. Multiple *customer* portal identities may map to the
same customer (owner, billing, purchasing, project, approver, etc.); an
*employee* portal identity is strictly 1:1 with its Employee (see the unique
partial index in `core/db.py`). Portal JWTs carry `sub_scope="portal"` and
are never accepted on staff routes. An employee-typed token can never
satisfy a customer-scoped route and vice versa (see `deps_portal.py`).
"""
from __future__ import annotations
from typing import Literal, Optional
from datetime import datetime
from pydantic import Field
from .base import BaseDoc

PortalIdentityStatus = Literal["active", "disabled"]
PortalType = Literal["customer", "employee"]
PortalPresetBundle = Literal["owner_full", "billing_only", "approver_only", "viewer_only", "custom"]

# Portal permission strings (portal:* scope). Backend-enforced.
PORTAL_PERMS = [
    "portal:view_quotes",
    "portal:approve_quotes",
    "portal:view_orders",
    "portal:view_proofs",
    "portal:approve_proofs",
    "portal:view_invoices",
    "portal:pay_invoices",
    "portal:view_documents",
    "portal:sign_documents",
    "portal:view_messages",
    "portal:send_messages",
    "portal:manage_profile",
]

# EC8 phase 8c — Employee Portal permission strings. Disjoint namespace from
# PORTAL_PERMS above (customer). Matches the reserved `PortalPerm` enum values
# in `core/permissions.py` (PORTAL_EMPLOYEE_VIEW/TIME_CLOCK/TIMESHEET_VIEW/
# SCHEDULE_VIEW) — this is the checkpoint that wires their enforcement.
# Every active Employee Portal identity is granted the full set; there is no
# per-identity preset for employees (unlike customer role_label presets) since
# scope is always "self" and never configurable per-identity.
EMPLOYEE_PORTAL_PERMS = [
    "portal:employee_view",
    "portal:employee_time_clock",
    "portal:employee_timesheet_view",
    "portal:employee_schedule_view",
    "portal:employee_pay_view",
]

PRESET_BUNDLES: dict[str, list[str]] = {
    "owner_full": PORTAL_PERMS[:],
    "billing_only": [
        "portal:view_quotes", "portal:view_orders", "portal:view_invoices",
        "portal:pay_invoices", "portal:view_documents", "portal:view_messages",
        "portal:manage_profile",
    ],
    "approver_only": [
        "portal:view_quotes", "portal:approve_quotes",
        "portal:view_proofs", "portal:approve_proofs",
        "portal:view_orders", "portal:view_documents",
        "portal:sign_documents", "portal:view_messages", "portal:manage_profile",
    ],
    "viewer_only": [
        "portal:view_quotes", "portal:view_orders", "portal:view_invoices",
        "portal:view_documents", "portal:view_messages", "portal:manage_profile",
    ],
    "custom": [],  # explicit list required
}


class PortalIdentity(BaseDoc):
    tenant_id: str
    portal_type: PortalType = "customer"
    customer_id: Optional[str] = None  # required when portal_type == "customer"
    employee_id: Optional[str] = None  # required when portal_type == "employee"
    email: str  # lowercased at write
    password_hash: Optional[str] = None  # None → magic-link-only
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role_label: Optional[str] = None  # e.g. "Billing", "Approver", "Owner"
    permissions_preset: PortalPresetBundle = "viewer_only"
    permissions: list[str] = Field(default_factory=list)  # backend-authoritative list
    status: PortalIdentityStatus = "active"
    magic_link_only: bool = True   # if True, password is not accepted for login
    last_login_at: Optional[datetime] = None
    failed_login_count: int = 0
    locked_until: Optional[datetime] = None
