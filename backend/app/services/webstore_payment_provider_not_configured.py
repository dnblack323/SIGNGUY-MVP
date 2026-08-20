"""Fail-closed Webstore payment provider implementation."""
from __future__ import annotations

from typing import Any

from .webstore_payment_provider_types import ProviderResult

class NotConfiguredWebstorePaymentProvider:
    """Provider implementation used until the approved adapter exists."""

    def _failure(self) -> ProviderResult:
        return ProviderResult.failure(
            message="Webstore Stripe integration is deferred and not enabled; no provider operation was performed.",
        )

    async def create_connected_account_onboarding_link(self, **kwargs: Any) -> ProviderResult:
        return self._failure()

    async def retrieve_connected_account_status(self, **kwargs: Any) -> ProviderResult:
        return self._failure()

    async def synchronize_payment_readiness(self, **kwargs: Any) -> ProviderResult:
        return self._failure()

    async def create_checkout_session(self, **kwargs: Any) -> ProviderResult:
        return self._failure()

    async def retrieve_checkout_session(self, **kwargs: Any) -> ProviderResult:
        return self._failure()

    async def verify_payment(self, **kwargs: Any) -> ProviderResult:
        return self._failure()

    def verify_webhook_signature_and_parse(self, **kwargs: Any) -> ProviderResult:
        return self._failure()

    async def create_refund(self, **kwargs: Any) -> ProviderResult:
        return self._failure()

    async def retrieve_refund(self, **kwargs: Any) -> ProviderResult:
        return self._failure()

    async def retrieve_transfer_or_payout(self, **kwargs: Any) -> ProviderResult:
        return self._failure()

    async def retrieve_dispute(self, **kwargs: Any) -> ProviderResult:
        return self._failure()

    async def reconcile_provider_event(self, **kwargs: Any) -> ProviderResult:
        return self._failure()
