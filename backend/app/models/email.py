from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import EmailStr, Field

from .base import BaseDoc

EmailStatus = Literal["queued", "sent", "delivered", "failed", "skipped"]
EmailTemplate = Literal[
    "quote_sent", "invoice_sent", "invoice_reminder", "document_sent", "general",
    "webstore_invitation", "webstore_information_packet", "webstore_questionnaire", "webstore_launch_packet",
]
EmailRelatedType = Literal["quote", "order", "work_order", "invoice", "document", "customer", "general", "webstore"]


class EmailLog(BaseDoc):
    tenant_id: str
    customer_id: Optional[str] = None
    related_type: EmailRelatedType = "general"
    related_id: Optional[str] = None
    template: EmailTemplate = "general"
    to_email: EmailStr
    from_email: str
    reply_to: Optional[str] = None
    subject: str
    body: str  # plain text body sent
    status: EmailStatus = "queued"
    error_message: Optional[str] = None
    sent_by: str  # user_id
    attachment_file_ids: list[str] = Field(default_factory=list)
    idempotency_key: Optional[str] = None
    sendgrid_message_id: Optional[str] = None
