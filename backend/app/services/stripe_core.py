"""EC4 — Stripe Core wrapper.

Thin wrapper around the raw `stripe` SDK that enforces:
- Amount is server-derived from the Invoice balance.
- Server-controlled `idempotency_key` on PaymentIntent creation + refunds.
- No secret exposure to callers.
- All state changes flow back through the webhook (`services/payment_service`).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import stripe

from ..core.config import get_settings

logger = logging.getLogger(__name__)


def _configured() -> bool:
    key = get_settings().stripe_api_key
    if not key:
        return False
    stripe.api_key = key
    return True


def is_enabled() -> bool:
    return get_settings().stripe_writes_enabled and _configured()


def create_payment_intent(
    *,
    amount_cents: int,
    currency: str = "usd",
    tenant_id: str,
    invoice_id: str,
    internal_payment_id: str,
    idempotency_key: str,
    customer_email: Optional[str] = None,
) -> dict[str, Any]:
    """Create a PaymentIntent for an Invoice.

    Returns a dict with `id`, `client_secret`, `status`, `amount`. Raises
    `stripe.error.StripeError` on provider errors — caller handles.
    """
    if not _configured():
        raise RuntimeError("stripe_not_configured")
    intent = stripe.PaymentIntent.create(
        amount=int(amount_cents),
        currency=currency,
        metadata={
            "tenant_id": tenant_id,
            "invoice_id": invoice_id,
            "internal_payment_id": internal_payment_id,
            "app": "signguy-ai",
        },
        receipt_email=customer_email,
        automatic_payment_methods={"enabled": True},
        idempotency_key=idempotency_key,
    )
    return {
        "id": intent.id,
        "client_secret": intent.client_secret,
        "status": intent.status,
        "amount": intent.amount,
        "currency": intent.currency,
    }


def create_refund(
    *,
    payment_intent_id: str,
    amount_cents: Optional[int] = None,
    reason: Optional[str] = None,
    idempotency_key: str,
) -> dict[str, Any]:
    if not _configured():
        raise RuntimeError("stripe_not_configured")
    kwargs: dict[str, Any] = {
        "payment_intent": payment_intent_id,
        "idempotency_key": idempotency_key,
        "metadata": {"app": "signguy-ai"},
    }
    if amount_cents is not None:
        kwargs["amount"] = int(amount_cents)
    if reason:
        kwargs["metadata"]["reason"] = reason
    refund = stripe.Refund.create(**kwargs)
    return {"id": refund.id, "status": refund.status, "amount": refund.amount}


def verify_webhook(*, payload: bytes, signature: str, secret: str) -> Any:
    return stripe.Webhook.construct_event(payload, signature, secret)


def publishable_key() -> Optional[str]:
    """Return the publishable key stored under STRIPE_PUBLISHABLE_KEY (if set)."""
    import os
    return os.environ.get("STRIPE_PUBLISHABLE_KEY") or None
