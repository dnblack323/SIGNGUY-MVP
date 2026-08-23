"""Compatibility surface for Webstore payment providers.

The provider implementation lives in responsibility-focused sibling modules.
This module preserves the original public import surface and Stripe monkeypatch
path used by focused tests.
"""
from __future__ import annotations

import stripe

from .webstore_payment_provider_config import (
    get_webstore_payment_provider,
    payment_provider_not_configured,
    provider_configuration_status,
)
from .webstore_payment_provider_not_configured import NotConfiguredWebstorePaymentProvider
from .webstore_payment_provider_stripe import StripeWebstorePaymentProvider
from .webstore_payment_provider_types import (
    PAYMENT_PROVIDER_NOT_CONFIGURED,
    PAYMENT_PROVIDER_STATES,
    ProviderAuthority,
    ProviderFinancialEvent,
    ProviderRefund,
    ProviderResult,
    VerifiedProviderPayment,
    WebstorePaymentProvider,
    _typed_result_data,
    financial_event_from_provider_result,
    refund_from_provider_result,
)
