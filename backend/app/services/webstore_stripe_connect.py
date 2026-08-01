"""Compatibility exports for the single Webstores payment-provider boundary.

The old EC14 local-record helpers are retained as safe compatibility names,
but they no longer create checkout or onboarding records. Provider behavior is
implemented only through :mod:`webstore_payment_provider`.
"""
from __future__ import annotations

from typing import Any, Optional

from .webstore_payment_provider import (
    PAYMENT_PROVIDER_NOT_CONFIGURED,
    NotConfiguredWebstorePaymentProvider,
    ProviderResult,
    WebstorePaymentProvider,
    get_webstore_payment_provider,
    payment_provider_not_configured,
    provider_configuration_status,
)


async def create_local_checkout_record(*, tenant_id: str, webstore_id: str, buyer_order_id: str, amount_cents: int, currency: str = "usd", idempotency_key: Optional[str] = None, metadata: Optional[dict[str, Any]] = None) -> ProviderResult:
    """Reject the retired local checkout contract without writing fake state."""
    return ProviderResult.failure(
        PAYMENT_PROVIDER_NOT_CONFIGURED,
        "Local Webstore checkout records are retired; configure the provider adapter before checkout.",
    )


async def create_local_onboarding_record(*, tenant_id: str, webstore_id: str, owner_id: str, idempotency_key: Optional[str] = None) -> ProviderResult:
    """Reject the retired local onboarding contract without writing fake state."""
    return ProviderResult.failure(
        PAYMENT_PROVIDER_NOT_CONFIGURED,
        "Local Webstore onboarding records are retired; configure the provider adapter before onboarding.",
    )


__all__ = [
    "PAYMENT_PROVIDER_NOT_CONFIGURED",
    "NotConfiguredWebstorePaymentProvider",
    "ProviderResult",
    "WebstorePaymentProvider",
    "create_local_checkout_record",
    "create_local_onboarding_record",
    "get_webstore_payment_provider",
    "payment_provider_not_configured",
    "provider_configuration_status",
]
