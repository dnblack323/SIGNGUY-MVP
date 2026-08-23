"""Stripe Connect provider composition for Webstores."""
from __future__ import annotations

from .webstore_payment_provider_stripe_accounts import StripeAccountMixin
from .webstore_payment_provider_stripe_base import StripeProviderBase
from .webstore_payment_provider_stripe_checkout import StripeCheckoutMixin
from .webstore_payment_provider_stripe_events import StripeWebhookMixin
from .webstore_payment_provider_stripe_refunds import StripeRefundMixin


class StripeWebstorePaymentProvider(
    StripeRefundMixin,
    StripeWebhookMixin,
    StripeCheckoutMixin,
    StripeAccountMixin,
    StripeProviderBase,
):
    """Stripe Connect adapter for Webstore onboarding and buyer checkout."""

    provider_name = "stripe"
