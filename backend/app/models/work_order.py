from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field

from .base import BaseDoc

# EC5 permanent status enum. Legacy values (not_started/on_hold) still accepted
# on read via _effective_status(...).
ProductionStatus = Literal[
    "draft", "released", "queued", "in_progress", "blocked",
    "ready", "completed", "cancelled", "superseded",
    # legacy compat — mapped on read
    "not_started", "on_hold",
]
Priority = Literal["low", "normal", "high", "rush"]


def effective_status(raw: Optional[str]) -> str:
    m = {"not_started": "released", "on_hold": "blocked"}
    return m.get(raw or "", raw or "draft")


class WorkOrderItemSnapshot(BaseDoc):
    tenant_id: str
    order_item_id: str
    description: str
    quantity: int
    unit_price_cents: int


class WorkOrder(BaseDoc):
    tenant_id: str
    number: int
    order_id: str
    customer_id: str

    # EC5 lifecycle
    production_status: ProductionStatus = "draft"
    priority: Priority = "normal"
    due_date: Optional[str] = None
    requested_date: Optional[str] = None
    released_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    ready_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    block_reason: Optional[str] = None
    archived_at: Optional[datetime] = None

    # Assignment
    assigned_user_ids: list[str] = Field(default_factory=list)
    assigned_to: Optional[str] = None    # legacy single-assignee mirror
    department: Optional[str] = None

    # Versioning
    version: int = 1
    current_version: bool = True
    superseded_by: Optional[str] = None
    superseded_from: Optional[str] = None
    supersede_reason: Optional[str] = None
    snapshot_version: int = 1

    # Content
    production_instructions: Optional[str] = None
    internal_notes: Optional[str] = None
    items_snapshot: list[dict] = Field(default_factory=list)
    created_by: str
