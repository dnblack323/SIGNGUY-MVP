"""Stripe connected-account onboarding and readiness actions."""
from __future__ import annotations

from typing import Any

import stripe

from .webstore_payment_provider_types import ProviderResult

class StripeAccountMixin:
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
