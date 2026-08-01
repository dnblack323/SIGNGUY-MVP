"""Stripe-ready Webstores foundation contracts.

These tests deliberately prove that the placeholder foundation cannot create
provider, Payment, Order, or checkout state.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.core.security_guards import collect_webstore_stripe_violations
from app.services.webstore_payment_provider import (
    PAYMENT_PROVIDER_NOT_CONFIGURED,
    NotConfiguredWebstorePaymentProvider,
    get_webstore_payment_provider,
    provider_configuration_status,
)
from app.services.webstores import WebstoreError, _payment_readiness, create_purchase_intent
from server import app


def _settings(monkeypatch: pytest.MonkeyPatch, **values: str) -> Settings:
    defaults = {
        "STRIPE_ENABLED": "true",
        "STRIPE_MODE": "test",
        "STRIPE_SECRET_KEY": "sk_test_foundation_only",
        "STRIPE_PUBLISHABLE_KEY": "pk_test_foundation_only",
        "STRIPE_CONNECT_CLIENT_ID": "ca_foundation_only",
        "STRIPE_CONNECT_RETURN_URL": "https://example.test/stripe/return",
        "STRIPE_CONNECT_REFRESH_URL": "https://example.test/stripe/refresh",
        "STRIPE_CHECKOUT_SUCCESS_URL": "https://example.test/checkout/success",
        "STRIPE_CHECKOUT_CANCEL_URL": "https://example.test/checkout/cancel",
        "STRIPE_CONNECT_CHARGE_MODEL": "deferred",
        "STRIPE_WEBHOOK_SECRET": "webhook-foundation-only",
    }
    defaults.update(values)
    for key, value in defaults.items():
        monkeypatch.setenv(key, value)
    return Settings()


def test_stripe_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch):
    settings = _settings(monkeypatch, STRIPE_ENABLED="false")
    status = provider_configuration_status(settings)
    assert status["state"] == "not_configured"
    assert status["provider_authority"] is False
    assert status["violations"] == []


def test_placeholder_values_and_deferred_model_fail_closed(monkeypatch: pytest.MonkeyPatch):
    settings = _settings(
        monkeypatch,
        STRIPE_SECRET_KEY="",
        STRIPE_PUBLISHABLE_KEY="",
        STRIPE_CONNECT_CHARGE_MODEL="deferred",
    )
    codes = {item.code for item in collect_webstore_stripe_violations(settings)}
    assert "webstore_stripe_credentials_missing" in codes
    assert "webstore_stripe_charge_model_deferred" in codes
    assert provider_configuration_status(settings)["provider_authority"] is False


def test_mode_mismatch_and_invalid_callbacks_fail_closed(monkeypatch: pytest.MonkeyPatch):
    settings = _settings(
        monkeypatch,
        STRIPE_MODE="live",
        STRIPE_SECRET_KEY="sk_test_foundation_only",
        STRIPE_PUBLISHABLE_KEY="pk_test_foundation_only",
        STRIPE_CONNECT_RETURN_URL="not-a-url",
    )
    codes = {item.code for item in collect_webstore_stripe_violations(settings)}
    assert "webstore_stripe_mode_mismatch" in codes
    assert "webstore_stripe_callback_url_invalid" in codes


@pytest.mark.asyncio
async def test_stored_readiness_flags_do_not_make_webstore_payment_ready(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STRIPE_ENABLED", "false")
    readiness = await _payment_readiness({"stripe_payment_ready": True, "payment_readiness_status": "ready"})
    assert readiness["ready"] is False
    assert readiness["provider_authority"] is False
    assert readiness["stored_flags_ignored"] is True


@pytest.mark.asyncio
async def test_disabled_provider_has_typed_failures_and_no_fake_checkout():
    provider = get_webstore_payment_provider()
    assert isinstance(provider, NotConfiguredWebstorePaymentProvider)
    result = await provider.create_checkout_session(amount_cents=1000, currency="usd")
    assert result.ok is False
    assert result.code == PAYMENT_PROVIDER_NOT_CONFIGURED


@pytest.mark.asyncio
async def test_public_checkout_fails_before_store_or_intent_lookup(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STRIPE_ENABLED", "false")
    with pytest.raises(WebstoreError) as error:
        await create_purchase_intent("missing-public-slug", {"buyer_name": "Buyer", "buyer_email": "buyer@example.com", "line_items": []})
    assert error.value.code == "payment_provider_not_configured"


@pytest.mark.asyncio
async def test_development_webhook_harness_is_unavailable_without_dev_bypass(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(get_settings(), "auth_dev_bypass", False, raising=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/webhooks/webstores/test-provider", content=b"{}")
    assert response.status_code == 404


def test_provider_status_never_serializes_secrets(monkeypatch: pytest.MonkeyPatch):
    settings = _settings(monkeypatch, STRIPE_ENABLED="true", STRIPE_CONNECT_CHARGE_MODEL="destination")
    status = provider_configuration_status(settings)
    rendered = repr(status)
    assert settings.stripe_secret_key not in rendered
    assert settings.stripe_publishable_key not in rendered
    assert settings.stripe_webhook_secret not in rendered
