"""Stripe refund and webhook-only reconciliation operations."""
from __future__ import annotations

from typing import Any

import stripe

from .webstore_payment_provider_types import ProviderResult

class StripeRefundMixin:
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
