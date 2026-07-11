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


def _is_dev_placeholder_key(key: str) -> bool:
    """Detect placeholder / non-live test keys used only for local regression.

    Real Stripe test keys start with `sk_test_` and are 100+ chars long. The
    Emergent-provisioned placeholder value `sk_test_emergent` (or empty) is
    used to indicate 'no outbound Stripe traffic allowed in this env'.
    """
    if not key:
        return True
    return key in {"sk_test_emergent", "sk_test_placeholder"} or len(key) < 24


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

    In production (real key configured) → calls Stripe. Placeholder keys in
    dev/preview environments short-circuit with a synthesized intent so the UI
    regression path is exercisable without outbound Stripe traffic. AUTH_DEV_BYPASS
    gates the placeholder-mode behaviour so a production deploy with a bad key
    still fails hard.
    """
    from ..core.config import get_settings
    settings = get_settings()
    if _is_dev_placeholder_key(settings.stripe_api_key or "") and settings.auth_dev_bypass:
        # Synthesize a deterministic-yet-unique intent id + client secret.
        import uuid
        pi_id = f"pi_dev_{uuid.uuid4().hex[:20]}"
        cs = f"{pi_id}_secret_{uuid.uuid4().hex[:16]}"
        return {"id": pi_id, "client_secret": cs, "status": "requires_payment_method",
                "amount": int(amount_cents), "currency": currency}
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
