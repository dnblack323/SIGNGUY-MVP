"""EC13 Stripe Billing boundary for platform subscriptions.

This module is intentionally separate from EC4 `stripe_core.py`, which owns
customer invoice PaymentIntents/refunds. EC13 never writes EC4 `payments`.
"""
from __future__ import annotations

from typing import Any, Optional
import uuid

import stripe

from ..core.config import get_settings


def _configured() -> bool:
    key = get_settings().stripe_api_key
    if not key:
        return False
    stripe.api_key = key
    return True


def _is_dev_placeholder_key(key: str) -> bool:
    return not key or key in {"sk_test_emergent", "sk_test_placeholder"} or len(key) < 24


def create_checkout_session(
    *,
    tenant_id: str,
    internal_checkout_session_id: str,
    session_type: str,
    mode: str,
    price_id: Optional[str],
    amount_cents: Optional[int],
    currency: str,
    success_url: str,
    cancel_url: str,
    idempotency_key: str,
    billing_interval: Optional[str] = None,
    customer_email: Optional[str] = None,
    stripe_customer_id: Optional[str] = None,
) -> dict[str, Any]:
    settings = get_settings()
    if _is_dev_placeholder_key(settings.stripe_api_key or "") and settings.auth_dev_bypass:
        session_id = f"cs_dev_{uuid.uuid4().hex[:24]}"
        return {
            "id": session_id,
            "url": f"https://checkout.stripe.test/session/{session_id}",
            "expires_at": None,
        }
    if not settings.stripe_writes_enabled or not _configured():
        raise RuntimeError("stripe_not_configured")

    line_price: dict[str, Any]
    if price_id:
        line_price = {"price": price_id, "quantity": 1}
    elif amount_cents is not None:
        price_data: dict[str, Any] = {
            "currency": currency,
            "unit_amount": int(amount_cents),
            "product_data": {"name": f"SignGuy {session_type.replace('_', ' ').title()}"},
        }
        if mode == "subscription" and billing_interval in {"monthly", "annual"}:
            price_data["recurring"] = {"interval": "month" if billing_interval == "monthly" else "year"}
        line_price = {
            "price_data": {
                **price_data,
            },
            "quantity": 1,
        }
    else:
        raise RuntimeError("stripe_price_required")

    kwargs: dict[str, Any] = {
        "mode": mode,
        "line_items": [line_price],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {
            "app": "signguy-ai",
            "tenant_id": tenant_id,
            "internal_checkout_session_id": internal_checkout_session_id,
            "session_type": session_type,
        },
        "idempotency_key": idempotency_key,
    }
    if stripe_customer_id:
        kwargs["customer"] = stripe_customer_id
    elif customer_email:
        kwargs["customer_email"] = customer_email

    session = stripe.checkout.Session.create(**kwargs)
    return {"id": session.id, "url": session.url, "expires_at": getattr(session, "expires_at", None)}


def create_billing_portal_session(
    *,
    tenant_id: str,
    billing_account_id: str,
    stripe_customer_id: Optional[str],
    return_url: str,
) -> dict[str, Any]:
    settings = get_settings()
    if _is_dev_placeholder_key(settings.stripe_api_key or "") and settings.auth_dev_bypass:
        session_id = f"bps_dev_{uuid.uuid4().hex[:24]}"
        return {
            "id": session_id,
            "url": f"https://billing.stripe.test/session/{session_id}",
        }
    if not settings.stripe_writes_enabled or not _configured() or not stripe_customer_id:
        raise RuntimeError("stripe_not_configured")
    session = stripe.billing_portal.Session.create(
        customer=stripe_customer_id,
        return_url=return_url,
        metadata={"app": "signguy-ai", "tenant_id": tenant_id, "billing_account_id": billing_account_id},
    )
    return {"id": session.id, "url": session.url}


def verify_webhook(*, payload: bytes, signature: str, secret: str) -> Any:
    return stripe.Webhook.construct_event(payload, signature, secret)
