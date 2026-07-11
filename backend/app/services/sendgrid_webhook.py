"""EC2 — SendGrid Event Webhook verification + processing.

Signature scheme
----------------
SendGrid signs the raw request body with an HMAC-SHA256 keyed by the shared
webhook secret. The digest is base64-encoded and delivered in the
`X-Twilio-Email-Event-Webhook-Signature` header. A UNIX timestamp is delivered
in the `X-Twilio-Email-Event-Webhook-Timestamp` header. The signed string is
`timestamp + raw_body_bytes`.

Reference: SendGrid Event Webhook Security docs (HMAC-SHA256 shared-secret
mode). ECDSA signature mode is NOT used in EC2 — HMAC only.

Runtime behavior
----------------
- Signature-verify FIRST. Failure returns 401 without touching the event log.
- If the (provider, provider_event_id) is already recorded, return 200 as a
  duplicate no-op.
- On success we persist one `email_activity` row per SendGrid event object,
  updating `webhook_events` status accordingly.
- No raw payload is stored beyond a small trimmed metadata block.

The route level gates real production traffic behind
`settings.sendgrid_webhook_enabled=True` AND a real secret being present.
The EC1 startup guard already enforces this in production.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from typing import Any, Optional

from ..core.config import get_settings
from ..core.db import db
from ..core.time_utils import prepare_for_mongo, utc_now
from ..models.email_activity import EmailActivity
from . import webhooks as webhook_svc

logger = logging.getLogger(__name__)


def verify_signature(
    *,
    secret: str,
    signature_header: str,
    timestamp_header: str,
    raw_body: bytes,
) -> bool:
    """Return True iff the HMAC-SHA256 signature matches.

    The signed value is `timestamp_header + raw_body`. Signature header value
    is base64-encoded HMAC-SHA256 digest.
    """
    if not secret or not signature_header or not timestamp_header:
        return False
    try:
        signed = timestamp_header.encode("utf-8") + raw_body
        mac = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).digest()
        expected = base64.b64encode(mac).decode("utf-8")
        return hmac.compare_digest(expected, signature_header)
    except Exception:
        return False


def _trim_payload(evt: dict[str, Any]) -> dict[str, Any]:
    """Keep only safe scalar fields for observability. No raw HTML, no headers."""
    keep = {
        "event",
        "sg_event_id",
        "sg_message_id",
        "smtp-id",
        "email",
        "timestamp",
        "reason",
        "response",
        "status",
        "type",
        "category",
    }
    return {k: v for k, v in evt.items() if k in keep and isinstance(v, (str, int, float, bool, list))}


async def _resolve_email_log(sg_message_id: Optional[str], to_email: Optional[str]) -> Optional[dict[str, Any]]:
    if not sg_message_id and not to_email:
        return None
    q: dict[str, Any] = {}
    if sg_message_id:
        q["sendgrid_message_id"] = {"$regex": f"^{sg_message_id.split('.')[0]}"}
    if to_email and not q:
        q["to_email"] = to_email
    if not q:
        return None
    return await db.email_logs.find_one(q, {"_id": 0})


async def process_events(events: list[dict[str, Any]]) -> dict[str, int]:
    """Persist EmailActivity rows for a list of SendGrid event payloads.

    Duplicate `sg_event_id` values are safely skipped (unique index enforces).
    Returns counts per event type.
    """
    counts: dict[str, int] = {"received": 0, "duplicate": 0, "unresolved_tenant": 0}
    for evt in events:
        counts["received"] += 1
        sg_event_id = evt.get("sg_event_id")
        if not sg_event_id:
            continue
        # Dedupe via webhook_events framework for observability.
        wh, is_dup = await webhook_svc.record_received(
            provider="sendgrid",
            provider_event_id=str(sg_event_id),
            event_type=str(evt.get("event") or "unknown"),
            metadata=_trim_payload(evt),
        )
        if is_dup:
            counts["duplicate"] += 1
            continue

        sg_message_id = evt.get("sg_message_id") or evt.get("smtp-id")
        to_email = evt.get("email")
        related = await _resolve_email_log(sg_message_id, to_email)
        tenant_id = related.get("tenant_id") if related else None
        email_log_id = related.get("id") if related else None

        if not tenant_id:
            counts["unresolved_tenant"] += 1
            await webhook_svc.mark_failed(
                provider="sendgrid",
                provider_event_id=str(sg_event_id),
                error_code="tenant_unresolved",
                error_message="No matching email_log to derive tenant_id",
            )
            continue

        # Coerce sendgrid timestamp (unix seconds) to ISO.
        ts = evt.get("timestamp")
        try:
            from datetime import datetime, timezone
            when = datetime.fromtimestamp(int(ts), tz=timezone.utc) if ts else utc_now()
        except Exception:
            when = utc_now()

        activity = EmailActivity(
            tenant_id=tenant_id,
            provider="sendgrid",
            provider_event_id=str(sg_event_id),
            email_log_id=email_log_id,
            sendgrid_message_id=str(sg_message_id) if sg_message_id else None,
            to_email=to_email or (related.get("to_email") if related else "unknown@invalid"),
            event=str(evt.get("event") or "processed"),  # type: ignore[arg-type]
            event_timestamp=when,
            reason=str(evt.get("reason") or evt.get("response") or "") or None,
            smtp_id=str(evt.get("smtp-id")) if evt.get("smtp-id") else None,
            related_entity_type=(related.get("related_type") if related else None),
            related_entity_id=(related.get("related_id") if related else None),
            payload_snapshot=_trim_payload(evt),
        )
        try:
            await db.email_activity.insert_one(prepare_for_mongo(activity.model_dump()))
        except Exception:
            logger.exception("email_activity insert failed for sg_event_id=%s", sg_event_id)

        await webhook_svc.mark_verified(
            provider="sendgrid", provider_event_id=str(sg_event_id), tenant_id=tenant_id
        )
        await webhook_svc.mark_processed(provider="sendgrid", provider_event_id=str(sg_event_id))
    return counts
