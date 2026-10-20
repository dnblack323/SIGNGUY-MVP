"""EC2 — SendGrid Signed Event Webhook verification + processing.

Signature scheme
----------------
SendGrid signs each Event Webhook request with ECDSA (P-256). The base64
signature arrives in `X-Twilio-Email-Event-Webhook-Signature` and a UNIX
timestamp in `X-Twilio-Email-Event-Webhook-Timestamp`; the signed content is
`timestamp + raw_body`. We verify with the account's verification public key
using the verifier bundled in the official `sendgrid` library.

Runtime behavior
----------------
- Signature-verify FIRST over the raw body. Any failure returns 401 without
  touching the event log (fail closed).
- If the (provider, provider_event_id) is already recorded, return 200 as a
  duplicate no-op.
- Each event is attributed to a tenant ONLY through the SendGrid message id
  stored on our own `email_logs` row. Events without a matching message id are
  recorded as `tenant_unresolved` and ignored — never matched by recipient.
- No raw payload is stored beyond a small trimmed metadata block.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, utc_now
from ..models.email_activity import EmailActivity
from . import webhooks as webhook_svc

logger = logging.getLogger(__name__)


def verify_signature(
    *,
    public_key: str,
    signature_header: str,
    timestamp_header: str,
    raw_body: bytes,
) -> bool:
    """Return True iff SendGrid's ECDSA signature over `timestamp + raw_body` is valid."""
    if not public_key or not signature_header or not timestamp_header:
        return False
    try:
        from sendgrid.helpers.eventwebhook import EventWebhook  # type: ignore

        return bool(
            EventWebhook(public_key).verify_signature(raw_body.decode("utf-8"), signature_header, timestamp_header)
        )
    except Exception:
        return False


def sendgrid_message_id_prefix(sg_message_id: Optional[str]) -> Optional[str]:
    """SendGrid event `sg_message_id` is `<X-Message-Id>.<filter suffix>`; the prefix is what we stored."""
    value = str(sg_message_id or "").strip()
    return value.split(".", 1)[0] or None


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


async def _resolve_email_log(sg_message_id: Optional[str]) -> Optional[dict[str, Any]]:
    prefix = sendgrid_message_id_prefix(sg_message_id)
    if not prefix:
        return None
    return await db.email_logs.find_one({"sendgrid_message_id": prefix}, {"_id": 0})


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

        sg_message_id = evt.get("sg_message_id")
        to_email = evt.get("email")
        related = await _resolve_email_log(sg_message_id)
        tenant_id = related.get("tenant_id") if related else None
        email_log_id = related.get("id") if related else None

        if not tenant_id:
            counts["unresolved_tenant"] += 1
            await webhook_svc.mark_failed(
                provider="sendgrid",
                provider_event_id=str(sg_event_id),
                error_code="tenant_unresolved",
                error_message="No email_log with this SendGrid message id",
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
