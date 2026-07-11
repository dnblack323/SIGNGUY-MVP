"""EC6 — Proofs and Proof Versions.

Immutable version history. A proof lives against an Order, an OrderItem, or a
Work Order. Each version snapshots a file (rendered proof) and captures
send/view/approve/revision events.
"""
from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional
from pydantic import Field
from .base import BaseDoc

ProofParentType = Literal["order", "order_item", "work_order"]
ProofStatus = Literal[
    "draft", "sent", "viewed", "approved", "changes_requested",
    "cancelled", "superseded",
]


class Proof(BaseDoc):
    tenant_id: str
    number: int
    parent_type: ProofParentType
    parent_id: str
    customer_id: Optional[str] = None    # convenience for portal scoping
    title: str
    description: Optional[str] = None
    current_version: int = 1
    current_file_id: Optional[str] = None
    current_document_id: Optional[str] = None
    status: ProofStatus = "draft"
    due_at: Optional[datetime] = None
    last_sent_at: Optional[datetime] = None
    last_viewed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    changes_requested_at: Optional[datetime] = None
    changes_requested_reason: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    cancelled_reason: Optional[str] = None
    created_by: Optional[str] = None


class ProofVersion(BaseDoc):
    tenant_id: str
    proof_id: str
    version: int
    file_id: str
    document_id: Optional[str] = None
    notes: Optional[str] = None
    sent_at: Optional[datetime] = None
    viewed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    changes_requested_at: Optional[datetime] = None
    changes_requested_reason: Optional[str] = None
    created_by: Optional[str] = None
