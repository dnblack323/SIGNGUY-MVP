"""Stripe provider base helpers for Webstore payment operations."""
from __future__ import annotations

import asyncio
from typing import Any, Optional

import stripe

from ..core.config import Settings
from ..core.security_guards import collect_webstore_stripe_violations
from .webstore_payment_provider_types import ProviderResult

class StripeProviderBase:
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
