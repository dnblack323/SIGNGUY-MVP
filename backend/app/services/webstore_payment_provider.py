"""Single provider boundary for Webstores Stripe commerce.

The Stripe adapter lives behind this module so the rest of the application only
receives typed, provider-authoritative results. Configuration and connected
account verification remain fail-closed; no provider result creates an Order
or Production record by itself.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Literal, Optional, Protocol

import stripe

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
    webstore_id: str
    amount_cents: int
    currency: str
    raw_event_snapshot: Optional[dict[str, Any]] = None

    def as_internal_fields(self) -> dict[str, Any]:
        fields = {
            "provider": self.provider,
            "provider_mode": self.provider_mode,
            "provider_account_reference": self.provider_account_reference,
            "provider_event_id": self.provider_event_id,
            "provider_payment_id": self.provider_payment_id,
            "purchase_intent_id": self.purchase_intent_id,
            "tenant_id": self.tenant_id,
            "webstore_id": self.webstore_id,
            "amount_cents": self.amount_cents,
            "currency": self.currency,
        }
        if self.raw_event_snapshot:
            fields["raw_event_snapshot"] = self.raw_event_snapshot
        return fields


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
    raw_event_snapshot: Optional[dict[str, Any]] = None


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
        raw_event_snapshot=data.get("raw_event_snapshot") if isinstance(data.get("raw_event_snapshot"), dict) else None,
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


class StripeWebstorePaymentProvider:
    """Stripe Connect adapter for Webstore onboarding and buyer checkout.

    Stripe's Python client is synchronous. Calls are moved to a worker thread
    so request handlers remain async, while all application records continue to
    be written by the Webstores services after typed results are returned.
    """

    provider_name = "stripe"

    def __init__(self, settings: Settings):
        self.settings = settings

    def _failure(self, code: str, message: str) -> ProviderResult:
        return ProviderResult.failure(code=code, message=message)

    def _configure(self) -> Optional[ProviderResult]:
        violations = collect_webstore_stripe_violations(self.settings)
        if violations:
            return self._failure("PAYMENT_PROVIDER_NOT_CONFIGURED", violations[0].message)
        if not self.settings.stripe_secret_key:
            return self._failure("PAYMENT_PROVIDER_NOT_CONFIGURED", "Stripe secret key is not configured.")
        stripe.api_key = self.settings.stripe_secret_key
        return None

    async def _call(self, method: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(method, **kwargs)

    @staticmethod
    def _account_id(kwargs: dict[str, Any]) -> Optional[str]:
        return str(kwargs.get("connected_account_reference") or kwargs.get("account_reference") or "").strip() or None

    def _account_request_options(self, account_reference: Optional[str]) -> dict[str, Any]:
        return {"stripe_account": account_reference} if account_reference else {}

    async def create_connected_account_onboarding_link(self, **kwargs: Any) -> ProviderResult:
        failure = self._configure()
        if failure:
            return failure
        account_reference = self._account_id(kwargs)
        try:
            if not account_reference:
                account = await self._call(
                    stripe.Account.create,
                    type="express",
                    capabilities={
                        "card_payments": {"requested": True},
                        "transfers": {"requested": True},
                    },
                    metadata={
                        "tenant_id": str(kwargs.get("tenant_id") or ""),
                        "webstore_id": str(kwargs.get("webstore_id") or ""),
                        "app": "signguy-webstore",
                    },
                    idempotency_key=str(kwargs.get("idempotency_key") or f"webstore-connect-{kwargs.get('webstore_id')}"),
                )
                account_reference = str(account.id)
            link = await self._call(
                stripe.AccountLink.create,
                account=account_reference,
                refresh_url=self.settings.stripe_connect_refresh_url,
                return_url=self.settings.stripe_connect_return_url,
                type="account_onboarding",
            )
            return ProviderResult.success(
                {
                    "provider": self.provider_name,
                    "provider_mode": self.settings.stripe_mode,
                    "account_reference": account_reference,
                    "onboarding_url": str(link.url),
                    "onboarding_state": "pending",
                }
            )
        except Exception as exc:
            return self._failure("PAYMENT_PROVIDER_ERROR", f"Stripe onboarding could not be started: {exc}")

    async def retrieve_connected_account_status(self, **kwargs: Any) -> ProviderResult:
        failure = self._configure()
        if failure:
            return failure
        account_reference = self._account_id(kwargs)
        if not account_reference:
            return self._failure("CONNECTED_ACCOUNT_REQUIRED", "Connect the Webstore owner before checking Stripe status.")
        try:
            account = await self._call(
                stripe.Account.retrieve,
                account_reference,
                **self._account_request_options(account_reference),
            )
            requirements = account.get("requirements") or {}
            current = [str(value) for value in requirements.get("currently_due") or []]
            past_due = [str(value) for value in requirements.get("past_due") or []]
            charges_enabled = bool(account.get("charges_enabled"))
            payouts_enabled = bool(account.get("payouts_enabled"))
            details_submitted = bool(account.get("details_submitted"))
            restriction = requirements.get("disabled_reason")
            onboarding_state = "complete" if details_submitted and charges_enabled and payouts_enabled and not current else "verification_required"
            return ProviderResult.success(
                {
                    "provider": self.provider_name,
                    "provider_mode": self.settings.stripe_mode,
                    "account_reference": account_reference,
                    "onboarding_state": onboarding_state,
                    "charges_enabled": charges_enabled,
                    "payouts_enabled": payouts_enabled,
                    "requirements_currently_due": current,
                    "requirements_past_due": past_due,
                    "restriction_status": str(restriction) if restriction else None,
                    "details_submitted": details_submitted,
                }
            )
        except Exception as exc:
            return self._failure("PAYMENT_PROVIDER_ERROR", f"Stripe account status could not be retrieved: {exc}")

    async def synchronize_payment_readiness(self, **kwargs: Any) -> ProviderResult:
        return await self.retrieve_connected_account_status(**kwargs)

    @staticmethod
    def _checkout_line_item(item: dict[str, Any], currency: str) -> Optional[dict[str, Any]]:
        quantity = int(item.get("quantity") or 0)
        unit_amount = int(item.get("unit_amount_cents") or 0)
        name = str(item.get("name") or "Webstore item").strip()
        if quantity <= 0 or unit_amount <= 0 or not name:
            return None
        return {
            "price_data": {
                "currency": currency,
                "product_data": {"name": name},
                "unit_amount": unit_amount,
            },
            "quantity": quantity,
        }

    async def create_checkout_session(self, **kwargs: Any) -> ProviderResult:
        failure = self._configure()
        if failure:
            return failure
        account_reference = self._account_id(kwargs)
        currency = str(kwargs.get("currency") or "usd").lower()
        line_items = [self._checkout_line_item(item, currency) for item in kwargs.get("line_items") or []]
        if not account_reference or not line_items or any(item is None for item in line_items):
            return self._failure("CHECKOUT_INPUT_INVALID", "A connected account and valid server-priced line items are required.")
        if not str(kwargs.get("idempotency_key") or "").strip():
            return self._failure("IDEMPOTENCY_KEY_REQUIRED", "Checkout-session creation requires an idempotency key.")
        if self.settings.stripe_charge_model not in {"destination", "direct"}:
            return self._failure("CHARGE_MODEL_UNSUPPORTED", "Stripe Connect charge model is not approved for Webstore checkout.")
        metadata = {
            "tenant_id": str(kwargs.get("tenant_id") or ""),
            "webstore_id": str(kwargs.get("webstore_id") or ""),
            "purchase_intent_id": str(kwargs.get("purchase_intent_id") or ""),
            "app": "signguy-webstore",
        }
        params: dict[str, Any] = {
            "mode": "payment",
            "line_items": [item for item in line_items if item is not None],
            "success_url": self.settings.stripe_checkout_success_url,
            "cancel_url": self.settings.stripe_checkout_cancel_url,
            "client_reference_id": str(kwargs.get("purchase_intent_id") or ""),
            "customer_email": kwargs.get("buyer_email"),
            "metadata": metadata,
            "payment_intent_data": {"metadata": metadata},
            "idempotency_key": str(kwargs.get("idempotency_key") or kwargs.get("purchase_intent_id") or ""),
        }
        if self.settings.stripe_charge_model == "destination":
            params["payment_intent_data"]["transfer_data"] = {"destination": account_reference}
        else:
            params.update(self._account_request_options(account_reference))
        try:
            session = await self._call(stripe.checkout.Session.create, **params)
            return ProviderResult.success(
                {
                    "provider": self.provider_name,
                    "provider_mode": self.settings.stripe_mode,
                    "account_reference": account_reference,
                    "checkout_session_id": str(session.id),
                    "checkout_url": str(session.url),
                    "checkout_status": str(session.status or "open"),
                    "payment_status": str(session.payment_status or "unpaid"),
                }
            )
        except Exception as exc:
            return self._failure("PAYMENT_PROVIDER_ERROR", f"Stripe checkout could not be created: {exc}")

    async def retrieve_checkout_session(self, **kwargs: Any) -> ProviderResult:
        failure = self._configure()
        if failure:
            return failure
        session_id = str(kwargs.get("checkout_session_id") or "").strip()
        if not session_id:
            return self._failure("CHECKOUT_SESSION_REQUIRED", "A Stripe Checkout Session is required.")
        try:
            session = await self._call(
                stripe.checkout.Session.retrieve,
                session_id,
                **self._account_request_options(self._account_id(kwargs)),
            )
            payment_intent = session.get("payment_intent")
            if not isinstance(payment_intent, str) and payment_intent:
                payment_intent = payment_intent.get("id")
            return ProviderResult.success(
                {
                    "provider": self.provider_name,
                    "provider_mode": self.settings.stripe_mode,
                    "account_reference": self._account_id(kwargs),
                    "checkout_session_id": session_id,
                    "checkout_status": str(session.get("status") or "open"),
                    "payment_status": str(session.get("payment_status") or "unpaid"),
                    "payment_intent_id": str(payment_intent or "") or None,
                }
            )
        except Exception as exc:
            return self._failure("PAYMENT_PROVIDER_ERROR", f"Stripe checkout could not be retrieved: {exc}")

    async def verify_payment(self, **kwargs: Any) -> ProviderResult:
        result = await self.retrieve_checkout_session(**kwargs)
        if not result.ok:
            return result
        data = dict(result.data or {})
        if data.get("payment_status") != "paid":
            return self._failure("PAYMENT_NOT_VERIFIED", "Stripe has not marked this Checkout Session as paid.")
        data["provider_payment_id"] = data.get("payment_intent_id") or data.get("checkout_session_id")
        return ProviderResult.success(data)

    def verify_webhook_signature_and_parse(self, **kwargs: Any) -> ProviderResult:
        failure = self._configure()
        if failure:
            return failure
        payload = kwargs.get("payload")
        signature = str(kwargs.get("signature") or "")
        secret = self.settings.stripe_webhook_secret
        if not isinstance(payload, (bytes, bytearray)) or not signature or not secret:
            return self._failure("WEBHOOK_INPUT_INVALID", "A Stripe payload, signature, and webhook secret are required.")
        try:
            event = stripe.Webhook.construct_event(bytes(payload), signature, secret)
            event_type = str(event.get("type") or "")
            if event_type not in {
                "checkout.session.completed",
                "checkout.session.async_payment_succeeded",
                "checkout.session.async_payment_failed",
                "checkout.session.expired",
                "payment_intent.succeeded",
                "payment_intent.payment_failed",
                "payment_intent.canceled",
                "payout.paid",
                "payout.failed",
                "payout.canceled",
                "transfer.created",
                "transfer.paid",
                "transfer.failed",
                "transfer.reversed",
                "charge.dispute.created",
                "charge.dispute.closed",
                "refund.created",
                "refund.updated",
                "charge.refunded",
            }:
                return ProviderResult.success({"ignored": True, "provider_event_id": str(event.get("id") or ""), "event_type": event_type})
            data_object = ((event.get("data") or {}).get("object") or {})
            metadata = data_object.get("metadata") or {}
            payment_intent = data_object.get("payment_intent") or data_object.get("id")
            if isinstance(payment_intent, dict):
                payment_intent = payment_intent.get("id")
            amount = data_object.get("amount_total") or data_object.get("amount_received") or data_object.get("amount")
            currency = str(data_object.get("currency") or "usd").lower()
            if event_type in {"refund.created", "refund.updated", "charge.refunded"}:
                refund_object = data_object
                if event_type == "charge.refunded":
                    refunds = ((data_object.get("refunds") or {}).get("data") or [])
                    refund_object = refunds[0] if refunds else {}
                refund_metadata = refund_object.get("metadata") or metadata
                refund_reference = refund_object.get("id")
                payment_reference = refund_object.get("payment_intent") or data_object.get("payment_intent")
                if isinstance(payment_reference, dict):
                    payment_reference = payment_reference.get("id")
                refund_amount = refund_object.get("amount") or data_object.get("amount_refunded") or amount
                refund_currency = str(refund_object.get("currency") or currency).lower()
                if not refund_reference or not payment_reference or refund_amount is None or not refund_metadata.get("tenant_id") or not refund_metadata.get("webstore_id"):
                    return self._failure("WEBHOOK_EVENT_INCOMPLETE", "Stripe refund event is missing Webstore metadata, payment, or amount.")
                return ProviderResult.success(
                    {
                        "event_kind": "refund",
                        "provider": self.provider_name,
                        "provider_mode": self.settings.stripe_mode,
                        "provider_event_id": str(event["id"]),
                        "provider_refund_reference": str(refund_reference),
                        "provider_payment_reference": str(payment_reference),
                        "provider_account_reference": event.get("account"),
                        "tenant_id": str(refund_metadata["tenant_id"]),
                        "webstore_id": str(refund_metadata["webstore_id"]),
                        "purchase_intent_id": str(refund_metadata.get("purchase_intent_id") or "") or None,
                        "amount_cents": int(refund_amount),
                        "currency": refund_currency,
                        "status": str(refund_object.get("status") or "succeeded").lower(),
                        "idempotency_key": str(refund_metadata.get("idempotency_key") or f"webstore-refund-webhook:{refund_reference}"),
                        "raw_event_snapshot": {
                            "provider_event_id": str(event["id"]),
                            "event_type": event_type,
                            "refund_reference": str(refund_reference),
                            "payment_reference": str(payment_reference),
                            "amount_cents": int(refund_amount),
                            "currency": refund_currency,
                            "metadata": {
                                "tenant_id": str(refund_metadata["tenant_id"]),
                                "webstore_id": str(refund_metadata["webstore_id"]),
                                "purchase_intent_id": str(refund_metadata.get("purchase_intent_id") or "") or None,
                            },
                        },
                    }
                )
            financial_event_types = {
                "payout.paid": "payout",
                "payout.failed": "payout",
                "payout.canceled": "payout",
                "transfer.created": "transfer",
                "transfer.paid": "transfer",
                "transfer.failed": "transfer",
                "transfer.reversed": "transfer",
                "charge.dispute.created": "dispute",
                "charge.dispute.closed": "dispute",
            }
            normalized_financial_type = financial_event_types.get(event_type)
            if normalized_financial_type:
                financial_reference = (
                    data_object.get("payment_intent")
                    or metadata.get("provider_payment_reference")
                    or metadata.get("payment_intent_id")
                )
                if isinstance(financial_reference, dict):
                    financial_reference = financial_reference.get("id")
                if not financial_reference or amount is None or not metadata.get("tenant_id") or not metadata.get("webstore_id"):
                    return self._failure("WEBHOOK_EVENT_INCOMPLETE", "Stripe financial event is missing Webstore payment metadata or amount.")
                status = str(data_object.get("status") or "pending").lower()
                if normalized_financial_type == "dispute" and event_type.endswith("closed"):
                    status = status or "closed"
                return ProviderResult.success(
                    {
                        "event_kind": "financial",
                        "event_type": normalized_financial_type,
                        "provider": self.provider_name,
                        "provider_mode": self.settings.stripe_mode,
                        "provider_event_id": str(event["id"]),
                        "provider_payment_reference": str(financial_reference),
                        "provider_account_reference": event.get("account"),
                        "tenant_id": str(metadata.get("tenant_id") or ""),
                        "webstore_id": str(metadata.get("webstore_id") or ""),
                        "amount_cents": int(amount),
                        "currency": currency,
                        "status": status,
                        "sequence": int(metadata["sequence"]) if metadata.get("sequence") is not None else None,
                        "raw_event_snapshot": {
                            "provider_event_id": str(event["id"]),
                            "event_type": event_type,
                            "account": event.get("account"),
                            "amount_cents": int(amount),
                            "currency": currency,
                            "status": status,
                            "sequence": int(metadata["sequence"]) if metadata.get("sequence") is not None else None,
                            "metadata": {
                                "tenant_id": str(metadata["tenant_id"]),
                                "webstore_id": str(metadata["webstore_id"]),
                                "provider_payment_reference": str(financial_reference),
                            },
                        },
                    }
                )
            provider_payment_reference = payment_intent
            if event_type == "checkout.session.completed" and str(data_object.get("payment_status") or "").lower() != "paid":
                event_kind = "payment_pending"
                status = "pending"
                failure_code = None
                failure_reason = "Stripe Checkout has not confirmed payment yet."
            elif event_type in {"checkout.session.async_payment_failed", "payment_intent.payment_failed"}:
                event_kind = "payment_failure"
                status = "payment_failed"
                last_error = data_object.get("last_payment_error") or {}
                failure_code = str(last_error.get("code") or data_object.get("failure_code") or "payment_failed")
                failure_reason = str(
                    last_error.get("message")
                    or data_object.get("failure_message")
                    or data_object.get("status")
                    or event_type
                )
            elif event_type in {"checkout.session.expired", "payment_intent.canceled"}:
                event_kind = "payment_failure"
                status = "expired" if event_type == "checkout.session.expired" else "canceled"
                failure_code = status
                failure_reason = str(data_object.get("cancellation_reason") or data_object.get("status") or event_type)
            else:
                event_kind = "payment_success"
                status = "succeeded"
                failure_code = None
                failure_reason = None
            required = (
                event.get("id"),
                metadata.get("tenant_id"),
                metadata.get("webstore_id"),
                metadata.get("purchase_intent_id"),
                provider_payment_reference,
                amount,
            )
            if any(value in (None, "") for value in required):
                return self._failure("WEBHOOK_EVENT_INCOMPLETE", "Stripe payment event is missing Webstore metadata or amount.")
            if event_kind != "payment_success":
                return ProviderResult.success(
                    {
                        "event_kind": event_kind,
                        "provider": self.provider_name,
                        "provider_mode": self.settings.stripe_mode,
                        "provider_event_id": str(event["id"]),
                        "provider_payment_id": str(provider_payment_reference),
                        "purchase_intent_id": str(metadata["purchase_intent_id"]),
                        "webstore_id": str(metadata["webstore_id"]),
                        "tenant_id": str(metadata["tenant_id"]),
                        "amount_cents": int(amount),
                        "currency": currency,
                        "status": status,
                        "failure_code": failure_code,
                        "failure_reason": failure_reason,
                        "provider_account_reference": event.get("account"),
                        "raw_event_snapshot": {
                            "provider_event_id": str(event["id"]),
                            "event_type": event_type,
                            "account": event.get("account"),
                            "amount_cents": int(amount),
                            "currency": currency,
                            "payment_status": data_object.get("payment_status"),
                            "status": status,
                            "failure_code": failure_code,
                            "failure_reason": failure_reason,
                            "metadata": {
                                "tenant_id": str(metadata["tenant_id"]),
                                "webstore_id": str(metadata["webstore_id"]),
                                "purchase_intent_id": str(metadata["purchase_intent_id"]),
                            },
                        },
                    }
                )
            required = (
                event.get("id"),
                metadata.get("tenant_id"),
                metadata.get("webstore_id"),
                metadata.get("purchase_intent_id"),
                payment_intent,
                amount,
            )
            if any(value in (None, "") for value in required):
                return self._failure("WEBHOOK_EVENT_INCOMPLETE", "Stripe payment event is missing Webstore metadata or amount.")
            return ProviderResult.success(
                {
                    "ignored": False,
                    "provider": self.provider_name,
                    "provider_mode": self.settings.stripe_mode,
                    "provider_event_id": str(event["id"]),
                    "provider_payment_id": str(payment_intent),
                    "purchase_intent_id": str(metadata["purchase_intent_id"]),
                    "webstore_id": str(metadata["webstore_id"]),
                    "tenant_id": str(metadata["tenant_id"]),
                    "amount_cents": int(amount),
                    "currency": currency,
                    "provider_account_reference": event.get("account"),
                    "event_type": event_type,
                    "raw_event_snapshot": {
                        "provider_event_id": str(event["id"]),
                        "event_type": event_type,
                        "account": event.get("account"),
                        "amount_cents": int(amount),
                        "currency": currency,
                        "metadata": {
                            "tenant_id": str(metadata["tenant_id"]),
                            "webstore_id": str(metadata["webstore_id"]),
                            "purchase_intent_id": str(metadata["purchase_intent_id"]),
                        },
                    },
                }
            )
        except Exception as exc:
            return self._failure("WEBHOOK_SIGNATURE_INVALID", f"Stripe webhook verification failed: {exc}")

    async def create_refund(self, **kwargs: Any) -> ProviderResult:
        failure = self._configure()
        if failure:
            return failure
        payment_reference = str(kwargs.get("provider_payment_reference") or kwargs.get("payment_intent_id") or "").strip()
        if not payment_reference:
            return self._failure("PAYMENT_REFERENCE_REQUIRED", "A Stripe payment reference is required for refunds.")
        params: dict[str, Any] = {
            "payment_intent": payment_reference,
            "amount": int(kwargs.get("amount_cents") or 0),
            "idempotency_key": str(kwargs.get("idempotency_key") or ""),
        }
        params["metadata"] = {
            "reason": str(kwargs.get("reason") or "Webstore refund"),
            "tenant_id": str(kwargs.get("tenant_id") or ""),
            "webstore_id": str(kwargs.get("webstore_id") or ""),
            "purchase_intent_id": str(kwargs.get("purchase_intent_id") or ""),
        }
        account_reference = self._account_id(kwargs)
        params.update(self._account_request_options(account_reference))
        try:
            refund = await self._call(stripe.Refund.create, **params)
            return ProviderResult.success(
                {
                    "provider": self.provider_name,
                    "provider_mode": self.settings.stripe_mode,
                    "provider_account_reference": account_reference,
                    "provider_payment_reference": payment_reference,
                    "provider_refund_reference": str(refund.id),
                    "amount_cents": int(refund.amount),
                    "currency": str(refund.currency or "usd").lower(),
                    "status": str(refund.status or "pending"),
                    "idempotency_key": str(kwargs.get("idempotency_key") or ""),
                }
            )
        except Exception as exc:
            return self._failure("PAYMENT_PROVIDER_ERROR", f"Stripe refund could not be created: {exc}")

    async def retrieve_refund(self, **kwargs: Any) -> ProviderResult:
        return self._failure("PROVIDER_OPERATION_UNAVAILABLE", "Stripe refund retrieval is reconciled from provider webhooks.")

    async def retrieve_transfer_or_payout(self, **kwargs: Any) -> ProviderResult:
        return self._failure("PROVIDER_OPERATION_UNAVAILABLE", "Stripe payout reconciliation is handled by provider webhooks.")

    async def retrieve_dispute(self, **kwargs: Any) -> ProviderResult:
        return self._failure("PROVIDER_OPERATION_UNAVAILABLE", "Stripe dispute reconciliation is handled by provider webhooks.")

    async def reconcile_provider_event(self, **kwargs: Any) -> ProviderResult:
        return self._failure("PROVIDER_OPERATION_UNAVAILABLE", "Stripe financial events are reconciled from signed provider webhooks.")


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
