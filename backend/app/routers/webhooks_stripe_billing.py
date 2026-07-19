"""EC13 Stripe Billing webhook handler.

Separate from EC4 `/api/webhooks/stripe`, which remains customer-invoice
PaymentIntent/refund only.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from ..core.config import get_settings
from ..services import stripe_billing, tenant_billing
from ..services.webhooks import mark_failed, mark_processed, mark_verified, record_received

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/stripe-billing", status_code=200)
async def stripe_billing_webhook(request: Request) -> dict:
    settings = get_settings()
    if not settings.stripe_webhook_enabled or not settings.stripe_webhook_secret:
        raise HTTPException(status_code=404, detail="Not found")

    raw = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe_billing.verify_webhook(payload=raw, signature=signature, secret=settings.stripe_webhook_secret)
    except Exception as ex:  # noqa: BLE001
        logger.warning("Stripe billing webhook signature verification failed: %s", ex)
        raise HTTPException(status_code=401, detail="Invalid signature")

    provider_event_id = event.get("id") if isinstance(event, dict) else event["id"]
    event_type = event.get("type") if isinstance(event, dict) else event["type"]
    obj = ((event.get("data") or {}).get("object") if isinstance(event, dict) else event["data"]["object"]) or {}
    tenant_id = ((obj.get("metadata") or {}).get("tenant_id")) if isinstance(obj, dict) else None

    _, is_dup = await record_received(
        provider="stripe_billing",
        provider_event_id=provider_event_id,
        event_type=event_type,
        metadata={"livemode": bool(event.get("livemode")) if isinstance(event, dict) else bool(event["livemode"])},
    )
    await mark_verified(provider="stripe_billing", provider_event_id=provider_event_id, tenant_id=tenant_id)
    if is_dup:
        return {"ok": True, "deduplicated": True}

    try:
        result = await tenant_billing.process_stripe_billing_event(event)
    except Exception as ex:  # noqa: BLE001
        await mark_failed(
            provider="stripe_billing",
            provider_event_id=provider_event_id,
            error_code="handler_error",
            error_message=str(ex),
        )
        logger.exception("Stripe billing webhook handler failed")
        raise HTTPException(status_code=500, detail="Handler error")

    await mark_processed(provider="stripe_billing", provider_event_id=provider_event_id)
    return {"ok": True, **result}
