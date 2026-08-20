"""Stripe Checkout session actions for Webstore purchases."""
from __future__ import annotations

from typing import Any, Optional

import stripe

from .webstore_payment_provider_types import ProviderResult

class StripeCheckoutMixin:
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
