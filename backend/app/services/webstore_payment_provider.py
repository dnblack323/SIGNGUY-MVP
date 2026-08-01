"""Single provider boundary for the Webstores Stripe-ready foundation.

This module deliberately contains no Stripe SDK calls. Emergent will add the
provider adapter behind this interface after the deferred charge model is
approved. Until then every money-moving operation fails closed with a typed
result and no canonical commerce record is created.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol

from ..core.config import Settings, get_settings
from ..core.security_guards import collect_webstore_stripe_violations

PAYMENT_PROVIDER_NOT_CONFIGURED = "PAYMENT_PROVIDER_NOT_CONFIGURED"


@dataclass(frozen=True)
class ProviderResult:
    ok: bool
    code: str
    message: str
    data: Optional[dict[str, Any]] = None

    @classmethod
    def failure(cls, code: str = PAYMENT_PROVIDER_NOT_CONFIGURED, message: str = "Webstore payment provider is not configured.") -> "ProviderResult":
        return cls(ok=False, code=code, message=message)

    @classmethod
    def success(cls, data: Optional[dict[str, Any]] = None) -> "ProviderResult":
        return cls(ok=True, code="OK", message="Provider operation completed.", data=data or {})


class WebstorePaymentProvider(Protocol):
    async def create_connected_account_onboarding_link(self, **kwargs: Any) -> ProviderResult: ...
    async def retrieve_connected_account_status(self, **kwargs: Any) -> ProviderResult: ...
    async def synchronize_payment_readiness(self, **kwargs: Any) -> ProviderResult: ...
    async def create_checkout_session(self, **kwargs: Any) -> ProviderResult: ...
    async def retrieve_checkout_session(self, **kwargs: Any) -> ProviderResult: ...
    async def verify_payment(self, **kwargs: Any) -> ProviderResult: ...
    def verify_webhook_signature_and_parse(self, **kwargs: Any) -> ProviderResult: ...
    async def create_refund(self, **kwargs: Any) -> ProviderResult: ...
    async def retrieve_refund(self, **kwargs: Any) -> ProviderResult: ...
    async def retrieve_transfer_or_payout(self, **kwargs: Any) -> ProviderResult: ...
    async def retrieve_dispute(self, **kwargs: Any) -> ProviderResult: ...
    async def reconcile_provider_event(self, **kwargs: Any) -> ProviderResult: ...


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


def provider_configuration_status(settings: Optional[Settings] = None) -> dict[str, Any]:
    settings = settings or get_settings()
    if not settings.stripe_enabled:
        return {
            "state": "not_configured",
            "label": "Not configured",
            "configured": False,
            "provider_authority": False,
            "reason": "Stripe integration is disabled for this foundation build.",
            "violations": [],
        }
    violations = collect_webstore_stripe_violations(settings)
    if violations:
        return {
            "state": "test_configuration_incomplete",
            "label": "Test configuration incomplete",
            "configured": False,
            "provider_authority": False,
            "reason": violations[0].message,
            "violations": [violation.code for violation in violations],
        }
    return {
        "state": "connected_verification_required",
        "label": "Connected - verification required",
        "configured": True,
        "provider_authority": False,
        "reason": "A provider adapter and provider-authoritative account verification are required before checkout can be enabled.",
        "violations": [],
    }


def get_webstore_payment_provider(settings: Optional[Settings] = None) -> WebstorePaymentProvider:
    # The future Stripe adapter must be selected here after its charge model is
    # approved. Keeping the factory stable prevents commerce-service rewrites.
    return NotConfiguredWebstorePaymentProvider()


def payment_provider_not_configured(settings: Optional[Settings] = None) -> ProviderResult:
    status = provider_configuration_status(settings)
    return ProviderResult.failure(message=status["reason"])
