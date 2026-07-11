"""SendGrid email service.

- Env-var config only.
- Fails gracefully when keys are missing: EmailLog is written with status='skipped' or 'failed'.
- Never crashes the calling request.
- EC2: on successful outbound, writes a `processed` row into `email_activity`
  so the observability feed shows the send before any provider webhook lands.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from ..core.config import get_settings
from ..core.db import db
from ..core.time_utils import prepare_for_mongo, utc_now
from ..models.email_activity import EmailActivity

logger = logging.getLogger(__name__)
_settings = get_settings()


def is_configured() -> bool:
    return bool(_settings.sendgrid_api_key and _settings.sendgrid_from_email)


def send_email(
    *,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    reply_to: Optional[str] = None,
) -> tuple[bool, str | None, str | None]:
    """Return (ok, message_id, error_message).

    If not configured, returns (False, None, 'sendgrid_not_configured').
    """
    if not is_configured():
        return False, None, "sendgrid_not_configured"
    try:
        from sendgrid import SendGridAPIClient  # type: ignore
        from sendgrid.helpers.mail import Mail, ReplyTo  # type: ignore

        message = Mail(
            from_email=(_settings.sendgrid_from_email, _settings.sendgrid_from_name),
            to_emails=to_email,
            subject=subject,
            plain_text_content=body_text,
            html_content=body_html or f"<pre>{body_text}</pre>",
        )
        if reply_to:
            message.reply_to = ReplyTo(reply_to)
        sg = SendGridAPIClient(_settings.sendgrid_api_key)
        response = sg.send(message)
        msg_id = response.headers.get("X-Message-Id") if hasattr(response, "headers") else None
        if 200 <= response.status_code < 300:
            return True, msg_id, None
        return False, msg_id, f"sendgrid_http_{response.status_code}"
    except Exception as e:  # noqa: BLE001
        logger.exception("SendGrid send failed")
        return False, None, f"exception:{type(e).__name__}:{e}"


async def record_processed_activity(
    *,
    tenant_id: str,
    email_log_id: str,
    to_email: str,
    sendgrid_message_id: Optional[str],
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[str] = None,
    ok: bool = True,
    error: Optional[str] = None,
) -> None:
    """EC2 — write an internal 'processed' or 'dropped' row into email_activity
    so the send is visible in the observability feed even before/without the
    provider webhook. Uses `email_log_id`-based provider_event_id so external
    SendGrid events don't collide.
    """
    provider_event_id = f"internal:{email_log_id}"
    try:
        activity = EmailActivity(
            tenant_id=tenant_id,
            provider="internal",
            provider_event_id=provider_event_id,
            email_log_id=email_log_id,
            sendgrid_message_id=sendgrid_message_id,
            to_email=to_email,  # type: ignore[arg-type]
            event="processed" if ok else "dropped",
            event_timestamp=utc_now(),
            reason=error,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )
        await db.email_activity.insert_one(prepare_for_mongo(activity.model_dump()))
    except Exception:
        logger.exception("record_processed_activity failed for email_log_id=%s", email_log_id)
