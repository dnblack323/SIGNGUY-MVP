"""Payment provider configuration and selection for Webstores."""
from __future__ import annotations

from typing import Any, Optional

from ..core.config import Settings, get_settings
from ..core.security_guards import collect_webstore_stripe_violations
from .webstore_payment_provider_not_configured import NotConfiguredWebstorePaymentProvider
from .webstore_payment_provider_stripe import StripeWebstorePaymentProvider
from .webstore_payment_provider_types import ProviderAuthority, ProviderResult, WebstorePaymentProvider

def provider_configuration_status(
    settings: Optional[Settings] = None,
    authoritative_status: Optional[ProviderAuthority] = None,
) -> dict[str, Any]:
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
    if authoritative_status is not None:
        if authoritative_status.mode != settings.stripe_mode:
            return {
                "state": "connected_verification_required",
                "label": "Connected - verification required",
                "configured": True,
                "provider_authority": False,
                "reason": "The connected Stripe account mode does not match the configured application mode.",
                "violations": ["webstore_stripe_mode_mismatch"],
            }
        if authoritative_status.restriction_status or not authoritative_status.charges_enabled or not authoritative_status.payouts_enabled:
            return {
                "state": "restricted",
                "label": "Restricted",
                "configured": True,
                "provider_authority": False,
                "reason": authoritative_status.restriction_status or "Provider capabilities are restricted.",
                "violations": [],
            }
        if not authoritative_status.verified or not authoritative_status.webhook_verified or authoritative_status.requirements_currently_due:
            return {
                "state": "connected_verification_required",
                "label": "Connected — verification required",
                "configured": True,
                "provider_authority": False,
                "reason": "Provider verification requirements are not complete.",
                "violations": [],
            }
        if authoritative_status.charge_model == "deferred":
            return {
                "state": "connected_verification_required",
                "label": "Connected — verification required",
                "configured": True,
                "provider_authority": False,
                "reason": "The final Stripe Connect charge model remains deferred.",
                "violations": ["webstore_stripe_charge_model_deferred"],
            }
        if not authoritative_status.account_reference:
            return {
                "state": "connected_verification_required",
                "label": "Connected — verification required",
                "configured": True,
                "provider_authority": False,
                "reason": "Provider account reference is missing.",
                "violations": [],
            }
        if authoritative_status.mode == "test":
            return {
                "state": "ready_for_test_checkout",
                "label": "Ready for test checkout",
                "configured": True,
                "provider_authority": True,
                "reason": "Provider-authoritative test checkout readiness is verified.",
                "violations": [],
            }
        if authoritative_status.mode == "live":
            return {
                "state": "live_ready",
                "label": "Live ready",
                "configured": True,
                "provider_authority": True,
                "reason": "Provider-authoritative live readiness is verified.",
                "violations": [],
            }
    return {
        "state": "connected_verification_required",
        "label": "Connected — verification required",
        "configured": True,
        "provider_authority": False,
        "reason": "A provider adapter and provider-authoritative account verification are required before checkout can be enabled.",
        "violations": [],
    }


def get_webstore_payment_provider(settings: Optional[Settings] = None) -> WebstorePaymentProvider:
    settings = settings or get_settings()
    if not settings.stripe_enabled or collect_webstore_stripe_violations(settings):
        return NotConfiguredWebstorePaymentProvider()
    return StripeWebstorePaymentProvider(settings)


def payment_provider_not_configured(settings: Optional[Settings] = None) -> ProviderResult:
    status = provider_configuration_status(settings)
    return ProviderResult.failure(message=status["reason"])
