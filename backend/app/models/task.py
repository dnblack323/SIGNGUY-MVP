"""EC12 Phase 12A - shared tenant-scoped task foundation."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field

from .base import BaseDoc

TaskStatus = Literal["not_started", "in_progress", "waiting", "blocked", "completed", "canceled"]
TaskPriority = Literal["low", "normal", "high", "rush"]
TaskVisibility = Literal["internal", "staff", "employee"]
TaskCommentVisibility = Literal["internal", "employee"]


class Task(BaseDoc):
    tenant_id: str
    title: str
    description: Optional[str] = None
    status: TaskStatus = "not_started"
    priority: TaskPriority = "normal"
    task_type: str = "general"

    source_type: Optional[str] = None
    source_id: Optional[str] = None
    customer_id: Optional[str] = None
    quote_id: Optional[str] = None
    order_id: Optional[str] = None
    order_item_id: Optional[str] = None
    work_order_id: Optional[str] = None
    invoice_id: Optional[str] = None
    production_stage_id: Optional[str] = None

    assigned_user_id: Optional[str] = None
    assigned_employee_id: Optional[str] = None
    created_by_user_id: Optional[str] = None
    created_by_employee_id: Optional[str] = None

    due_at: Optional[str] = None
    start_at: Optional[str] = None
    completed_at: Optional[str] = None
    completed_by_user_id: Optional[str] = None
    completed_by_employee_id: Optional[str] = None
    archived_at: Optional[str] = None

    recurrence_rule: Optional[dict[str, Any]] = None
    reminder_policy: dict[str, Any] = Field(default_factory=dict)
    visibility: TaskVisibility = "staff"
    employee_visible: bool = False
    internal_only: bool = True

    waiting_reason: Optional[str] = None
    block_reason: Optional[str] = None
    cancel_reason: Optional[str] = None
    reopen_reason: Optional[str] = None
    idempotency_key: Optional[str] = None
    version: int = 1
    status_history: list[dict[str, Any]] = Field(default_factory=list)
    assignment_history: list[dict[str, Any]] = Field(default_factory=list)
    completion_history: list[dict[str, Any]] = Field(default_factory=list)


class TaskComment(BaseDoc):
    tenant_id: str
    task_id: str
    author_user_id: Optional[str] = None
    author_employee_id: Optional[str] = None
    body: str
    visibility: TaskCommentVisibility = "internal"
    edited_at: Optional[str] = None
    archived_at: Optional[str] = None


class TaskReminderRecord(BaseDoc):
    tenant_id: str
    task_id: str
    reminder_kind: Literal["due", "overdue"]
    policy_key: Optional[str] = None
    sent_at: Optional[str] = None
    notification_error: Optional[str] = None
