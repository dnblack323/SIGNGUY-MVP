"""Single provider boundary for the Webstores Stripe-ready foundation.

This module deliberately contains no Stripe SDK calls. Emergent will add the
provider adapter behind this interface after the deferred charge model is
approved. Until then every money-moving operation fails closed with a typed
result and no canonical commerce record is created.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional, Protocol

from ..core.config import Settings, get_settings
from ..core.security_guards import collect_webstore_stripe_violations

PAYMENT_PROVIDER_NOT_CONFIGURED = "PAYMENT_PROVIDER_NOT_CONFIGURED"
PAYMENT_PROVIDER_STATES = (
    "not_configured",
    "test_configuration_incomplete",
    "connected_verification_required",
    "restricted",
    "ready_for_test_checkout",
    "live_ready",
)


@dataclass(frozen=True)
class ProviderAuthority:
    """Typed authority issued by a verified provider adapter or test fixture."""

    provider: str
    mode: Literal["test", "live"]
    account_reference: Optional[str]
    charge_model: str
    webhook_verified: bool
    verified: bool
    restriction_status: Optional[str] = None
    charges_enabled: bool = True
    payouts_enabled: bool = True
    requirements_currently_due: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerifiedProviderPayment:
    provider: str
    provider_mode: Literal["test", "live"]
    provider_account_reference: Optional[str]
    provider_event_id: str
    provider_payment_id: str
    purchase_intent_id: str
    tenant_id: str
    amount_cents: int
    currency: str

    def as_internal_fields(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "provider_mode": self.provider_mode,
            "provider_account_reference": self.provider_account_reference,
            "provider_event_id": self.provider_event_id,
            "provider_payment_id": self.provider_payment_id,
            "purchase_intent_id": self.purchase_intent_id,
            "tenant_id": self.tenant_id,
            "amount_cents": self.amount_cents,
            "currency": self.currency,
        }


@dataclass(frozen=True)
class ProviderRefund:
    provider: str
    provider_mode: Literal["test", "live"]
    provider_account_reference: Optional[str]
    provider_payment_reference: str
    provider_refund_reference: str
    amount_cents: int
    currency: str
    status: str
    idempotency_key: str


@dataclass(frozen=True)
class ProviderFinancialEvent:
    event_type: Literal["payout", "transfer", "dispute"]
    provider: str
    provider_mode: Literal["test", "live"]
    provider_account_reference: Optional[str]
    provider_event_id: str
    provider_payment_reference: str
    amount_cents: int
    currency: str
    status: str
    sequence: Optional[int] = None


def _typed_result_data(result: ProviderResult) -> dict[str, Any]:
    if not result.ok or not isinstance(result.data, dict):
        raise ValueError("provider_result_not_successful")
    return result.data


def refund_from_provider_result(result: ProviderResult) -> ProviderRefund:
    data = _typed_result_data(result)
    provider_mode = str(data["provider_mode"])
    status = str(data["status"]).strip().lower()
    required_values = (
        data.get("provider"),
        data.get("provider_payment_reference"),
        data.get("provider_refund_reference"),
        data.get("currency"),
        data.get("idempotency_key"),
    )
    if (
        provider_mode not in {"test", "live"}
        or status not in {"pending", "succeeded", "confirmed"}
        or int(data["amount_cents"]) <= 0
        or any(not str(value).strip() for value in required_values)
    ):
        raise ValueError("provider_refund_fields_invalid")
    return ProviderRefund(
        provider=str(data["provider"]),
        provider_mode=provider_mode,  # type: ignore[arg-type]
        provider_account_reference=data.get("provider_account_reference"),
        provider_payment_reference=str(data["provider_payment_reference"]),
        provider_refund_reference=str(data["provider_refund_reference"]),
        amount_cents=int(data["amount_cents"]),
        currency=str(data["currency"]).lower(),
        status=status,
        idempotency_key=str(data["idempotency_key"]),
    )


def financial_event_from_provider_result(result: ProviderResult) -> ProviderFinancialEvent:
    data = _typed_result_data(result)
    event_type = str(data["event_type"])
    provider_mode = str(data["provider_mode"])
    required_values = (
        data.get("provider"),
        data.get("provider_event_id"),
        data.get("provider_payment_reference"),
        data.get("currency"),
        data.get("status"),
    )
    if (
        event_type not in {"payout", "transfer", "dispute"}
        or provider_mode not in {"test", "live"}
        or int(data["amount_cents"]) < 0
        or any(not str(value).strip() for value in required_values)
    ):
        raise ValueError("provider_event_type_invalid")
    return ProviderFinancialEvent(
        event_type=event_type,  # type: ignore[arg-type]
        provider=str(data["provider"]),
        provider_mode=provider_mode,  # type: ignore[arg-type]
        provider_account_reference=data.get("provider_account_reference"),
        provider_event_id=str(data["provider_event_id"]),
        provider_payment_reference=str(data["provider_payment_reference"]),
        amount_cents=int(data["amount_cents"]),
        currency=str(data["currency"]).lower(),
        status=str(data["status"]).strip().lower(),
        sequence=int(data["sequence"]) if data.get("sequence") is not None else None,
    )


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
    # The future Stripe adapter must be selected here after its charge model is
    # approved. Keeping the factory stable prevents commerce-service rewrites.
    return NotConfiguredWebstorePaymentProvider()


def payment_provider_not_configured(settings: Optional[Settings] = None) -> ProviderResult:
    status = provider_configuration_status(settings)
    return ProviderResult.failure(message=status["reason"])
