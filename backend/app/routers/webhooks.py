"""EC2 — Inbound webhook routes.

Currently only SendGrid Event Webhook is wired. Additional providers will be
added in later ECs (Stripe in EC3, etc.).

The route reads the RAW request body (necessary for HMAC), verifies signature,
short-circuits on missing config, and then hands events to the processor.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request, status

from ..core.config import get_settings
from ..services.sendgrid_webhook import process_events, verify_signature

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/sendgrid", status_code=200)
async def sendgrid_webhook(request: Request) -> dict:
    settings = get_settings()

    # Route is fail-closed: if not enabled or secret missing, reject.
    if not settings.sendgrid_webhook_enabled or not settings.sendgrid_webhook_secret:
        # 404 to hide the surface when disabled — no leakage of enablement state.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    raw = await request.body()
    signature = request.headers.get("X-Twilio-Email-Event-Webhook-Signature", "")
    timestamp = request.headers.get("X-Twilio-Email-Event-Webhook-Timestamp", "")

    if not verify_signature(
        secret=settings.sendgrid_webhook_secret,
        signature_header=signature,
        timestamp_header=timestamp,
        raw_body=raw,
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        events = json.loads(raw.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")

    if not isinstance(events, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payload must be a list of events")

    counts = await process_events(events)
    return {"ok": True, "counts": counts}
