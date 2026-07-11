"""EC6 — Portal Identity.

Separate collection from `users`. A portal identity belongs to exactly one
tenant AND one customer. Multiple portal identities may map to the same
customer (owner, billing, purchasing, project, approver, etc.). Portal JWTs
carry `sub_scope="portal"` and are never accepted on staff routes.
"""
from __future__ import annotations
from typing import Literal, Optional
from datetime import datetime
from pydantic import Field
from .base import BaseDoc

PortalIdentityStatus = Literal["active", "disabled"]
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
    customer_id: str
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
