"""EC1 — Production Startup Guard Tests.

Verifies that:
  1. Development environments do not raise (guards are permissive).
  2. Production start fails with dev bypass enabled.
  3. Production start fails with a placeholder JWT secret.
  4. Enabled integrations require their verification secrets in production.
  5. Disabled integrations do not require unused credentials in production.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.core.security_guards import (
    JWT_PLACEHOLDER_SECRETS,
    StartupGuardError,
    collect_violations,
    enforce_startup_guards,
)


@dataclass
class FakeSettings:
    env: str = "development"
    auth_dev_bypass: bool = False
    jwt_secret: str = "a-strong-non-placeholder-secret-1234567890"
    sendgrid_webhook_enabled: bool = False
    sendgrid_webhook_secret: str | None = None
    stripe_writes_enabled: bool = False
    stripe_webhook_enabled: bool = False
    stripe_api_key: str | None = None
    stripe_webhook_secret: str | None = None
    ai_enabled: bool = False
    emergent_llm_key: str | None = None
    sms_enabled: bool = False
    sms_provider_key: str | None = None
    sms_provider_secret: str | None = None


def _prod(**overrides) -> FakeSettings:
    s = FakeSettings(env="production")
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def test_development_passes_even_with_dev_bypass():
    s = FakeSettings(env="development", auth_dev_bypass=True, jwt_secret="dev-secret-do-not-use-in-prod")
    assert collect_violations(s) == []
    enforce_startup_guards(s)  # must not raise


def test_production_fails_with_dev_bypass():
    s = _prod(auth_dev_bypass=True)
    vs = collect_violations(s)
    assert any(v.code == "dev_bypass_enabled_in_production" for v in vs)
    with pytest.raises(StartupGuardError):
        enforce_startup_guards(s)


def test_production_fails_with_placeholder_jwt():
    for placeholder in list(JWT_PLACEHOLDER_SECRETS):
        s = _prod(jwt_secret=placeholder)
        vs = collect_violations(s)
        assert any(v.code == "jwt_secret_placeholder_in_production" for v in vs), placeholder


def test_production_fails_with_empty_jwt():
    s = _prod(jwt_secret="")
    vs = collect_violations(s)
    assert any(v.code == "jwt_secret_placeholder_in_production" for v in vs)


def test_production_passes_with_strong_secrets_all_disabled():
    s = _prod()
    assert collect_violations(s) == []
    enforce_startup_guards(s)


def test_production_stripe_requires_key_when_writes_enabled():
    s = _prod(stripe_writes_enabled=True, stripe_api_key=None)
    vs = collect_violations(s)
    assert any(v.code == "stripe_api_key_missing" for v in vs)


def test_production_stripe_webhook_requires_secret_when_enabled():
    s = _prod(stripe_webhook_enabled=True, stripe_webhook_secret=None)
    vs = collect_violations(s)
    assert any(v.code == "stripe_webhook_secret_missing" for v in vs)


def test_production_sendgrid_webhook_requires_secret_when_enabled():
    s = _prod(sendgrid_webhook_enabled=True, sendgrid_webhook_secret=None)
    vs = collect_violations(s)
    assert any(v.code == "sendgrid_webhook_secret_missing" for v in vs)


def test_production_ai_requires_key_when_enabled():
    s = _prod(ai_enabled=True, emergent_llm_key=None)
    vs = collect_violations(s)
    assert any(v.code == "ai_provider_key_missing" for v in vs)


def test_production_sms_requires_credentials_when_enabled():
    s = _prod(sms_enabled=True, sms_provider_key=None, sms_provider_secret=None)
    vs = collect_violations(s)
    assert any(v.code == "sms_provider_credentials_missing" for v in vs)


def test_disabled_integrations_dont_require_credentials():
    s = _prod(
        stripe_writes_enabled=False,
        stripe_webhook_enabled=False,
        sendgrid_webhook_enabled=False,
        ai_enabled=False,
        sms_enabled=False,
    )
    vs = collect_violations(s)
    assert all(
        v.code not in {
            "stripe_api_key_missing",
            "stripe_webhook_secret_missing",
            "sendgrid_webhook_secret_missing",
            "ai_provider_key_missing",
            "sms_provider_credentials_missing",
        }
        for v in vs
    )
