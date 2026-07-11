"""EC6 — Approvals (dual-parent).

Immutable approval records. Approval NEVER silently changes pricing / invoice
status / payment status / production completion / unrelated Order Items.
Any resulting operational transition is executed by the owning module's
service and audited separately.
"""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import Field
from .base import BaseDoc

ApprovalParentType = Literal[
    "quote_revision", "proof_version", "contract",
    "order_item", "work_order_summary",
]
ApprovalAction = Literal["approve", "request_changes", "decline"]
ApprovalActorType = Literal["portal_customer", "public_token", "staff"]


class Approval(BaseDoc):
    tenant_id: str
    parent_type: ApprovalParentType
    parent_id: str
    parent_version: Optional[int] = None
    action: ApprovalAction
    reason: Optional[str] = None
    actor_type: ApprovalActorType
    actor_ref: str                       # portal_identity.id | "token:<id>" | user.id
    actor_display: Optional[str] = None  # e.g. signer name for audit clarity
    ip: Optional[str] = None
    user_agent: Optional[str] = None
