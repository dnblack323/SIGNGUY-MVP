"""EC4 — Stripe webhook handler.

Verifies signature, records the event through EC2 shared webhook infrastructure,
then routes the event to the appropriate `payment_service` helper. Replay-safe
via the unique (provider, provider_event_id) index in `webhook_events`.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from ..core.config import get_settings
from ..services import stripe_core
from ..services.payment_service import (
    confirm_refund_from_webhook,
    confirm_stripe_from_webhook,
    fail_stripe_from_webhook,
)
from ..services.webhooks import mark_failed, mark_processed, mark_verified, record_received

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/stripe", status_code=200)
async def stripe_webhook(request: Request) -> dict:
    settings = get_settings()
    if not settings.stripe_webhook_enabled or not settings.stripe_webhook_secret:
        # Fail closed — do not leak enablement state.
        raise HTTPException(status_code=404, detail="Not found")

    raw = await request.body()
    signature = request.headers.get("stripe-signature", "")

    try:
        event = stripe_core.verify_webhook(
            payload=raw, signature=signature, secret=settings.stripe_webhook_secret
        )
    except Exception as ex:  # noqa: BLE001
        logger.warning("Stripe webhook signature verification failed: %s", ex)
        raise HTTPException(status_code=401, detail="Invalid signature")

    provider_event_id = event.get("id") if isinstance(event, dict) else event["id"]
    event_type = event.get("type") if isinstance(event, dict) else event["type"]
    obj = event["data"]["object"]

    # Record + dedupe via EC2 infra
    _, is_dup = await record_received(
        provider="stripe",
        provider_event_id=provider_event_id,
        event_type=event_type,
        metadata={"livemode": bool(event.get("livemode"))},
    )
    await mark_verified(provider="stripe", provider_event_id=provider_event_id)
    if is_dup:
        return {"ok": True, "deduplicated": True}

    try:
        if event_type == "payment_intent.succeeded":
            charges = obj.get("charges", {}).get("data") if obj.get("charges") else []
            charge_id = charges[0]["id"] if charges else None
            await confirm_stripe_from_webhook(
                payment_intent_id=obj["id"],
                provider_event_id=provider_event_id,
                charge_id=charge_id,
            )
        elif event_type == "payment_intent.payment_failed":
            reason = ((obj.get("last_payment_error") or {}).get("message"))
            await fail_stripe_from_webhook(
                payment_intent_id=obj["id"],
                provider_event_id=provider_event_id,
                reason=reason,
                canceled=False,
            )
        elif event_type == "payment_intent.canceled":
            await fail_stripe_from_webhook(
                payment_intent_id=obj["id"],
                provider_event_id=provider_event_id,
                reason="canceled",
                canceled=True,
            )
        elif event_type == "charge.refunded":
            # Refunds on the charge live under obj["refunds"]["data"]
            refunds = (obj.get("refunds") or {}).get("data") or []
            for r in refunds:
                await confirm_refund_from_webhook(
                    stripe_refund_id=r["id"], provider_event_id=provider_event_id
                )
        elif event_type == "refund.updated":
            r = obj
            if r.get("status") == "succeeded":
                await confirm_refund_from_webhook(
                    stripe_refund_id=r["id"], provider_event_id=provider_event_id
                )
        else:
            # Ignore unrelated events but still mark processed for observability.
            pass
    except Exception as ex:  # noqa: BLE001
        await mark_failed(
            provider="stripe", provider_event_id=provider_event_id,
            error_code="handler_error", error_message=str(ex),
        )
        logger.exception("Stripe webhook handler failed")
        raise HTTPException(status_code=500, detail="Handler error")

    await mark_processed(provider="stripe", provider_event_id=provider_event_id)
    return {"ok": True}
