"""EC12 Phase 12E - shared messages, notes, preferences, and digest contracts."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from .base import BaseDoc

ThreadType = Literal[
    "direct",
    "group",
    "team",
    "task_discussion",
    "order_discussion",
    "work_order_discussion",
    "production_discussion",
    "appointment_discussion",
    "announcement_discussion",
]
Visibility = Literal["internal", "employee_visible"]
MessageType = Literal["message", "system"]
NoteVisibility = Literal["internal", "employee_visible", "private_to_author", "manager_only"]
IdentityType = Literal["user", "employee"]


class MessageThread(BaseDoc):
    tenant_id: str
    thread_type: ThreadType
    title: str
    created_by_user_id: Optional[str] = None
    created_by_employee_id: Optional[str] = None
    participant_user_ids: list[str] = Field(default_factory=list)
    participant_employee_ids: list[str] = Field(default_factory=list)
    team_or_group_id: Optional[str] = None
    customer_id: Optional[str] = None
    order_id: Optional[str] = None
    order_item_id: Optional[str] = None
    work_order_id: Optional[str] = None
    production_stage_id: Optional[str] = None
    task_id: Optional[str] = None
    calendar_event_id: Optional[str] = None
    announcement_id: Optional[str] = None
    visibility: Visibility = "internal"
    archived_at: Optional[str] = None
    last_message_at: Optional[str] = None


class ThreadMessage(BaseDoc):
    tenant_id: str
    thread_id: str
    sender_user_id: Optional[str] = None
    sender_employee_id: Optional[str] = None
    body: str
    message_type: MessageType = "message"
    visibility: Visibility = "internal"
    edited_at: Optional[str] = None
    archived_at: Optional[str] = None
    idempotency_key: Optional[str] = None


class MessageReadState(BaseDoc):
    tenant_id: str
    thread_id: str
    identity_type: IdentityType
    identity_id: str
    last_read_at: Optional[str] = None
    last_read_message_id: Optional[str] = None
    archived_at: Optional[str] = None


class InternalNote(BaseDoc):
    tenant_id: str
    title: Optional[str] = None
    body: str
    author_user_id: Optional[str] = None
    author_employee_id: Optional[str] = None
    visibility: NoteVisibility = "internal"
    pinned: bool = False
    customer_id: Optional[str] = None
    order_id: Optional[str] = None
    order_item_id: Optional[str] = None
    work_order_id: Optional[str] = None
    production_stage_id: Optional[str] = None
    task_id: Optional[str] = None
    calendar_event_id: Optional[str] = None
    employee_id: Optional[str] = None
    edited_at: Optional[str] = None
    archived_at: Optional[str] = None


class CommunicationPreference(BaseDoc):
    tenant_id: str
    identity_type: IdentityType
    identity_id: str
    in_app_messages: bool = True
    task_notifications: bool = True
    schedule_changes: bool = True
    time_off_decisions: bool = True
    appointment_reminders: bool = True
    announcements: bool = True
    daily_digest: bool = True
    email_delivery: bool = False
    digest_time: str = "08:00"
    digest_frequency: str = "daily"
    quiet_hours: dict = Field(default_factory=lambda: {
        "enabled": False,
        "start_time": "18:00",
        "end_time": "07:00",
        "timezone": "UTC",
        "allow_critical": True,
        "weekends": True,
    })


class DailyDigest(BaseDoc):
    tenant_id: str
    recipient_type: IdentityType
    recipient_id: str
    digest_date: str
    status: str = "preview"
    sections: dict = Field(default_factory=dict)
    delivered_at: Optional[str] = None
    delivery_channel: str = "in_app"
    delivery_error: Optional[str] = None
