"""EC1 — Production Startup Security Guards.

The application refuses to start in a production environment when:
- AUTH_DEV_BYPASS=true
- The JWT secret is missing or matches a known placeholder
- An integration is explicitly enabled in production without its required verification secret

Development and test environments may run with documented test settings; dev bypass
remains visibly identified via GET /api/auth/dev-config and the dev banner in the app shell.

This module is imported by server.py at startup and by tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .config import Settings

# Known development/placeholder JWT secrets that must never appear in production.
JWT_PLACEHOLDER_SECRETS = frozenset(
    {
        "dev-secret-do-not-use-in-prod",
        "change-me",
        "changeme",
        "secret",
        "please-change-me",
        "placeholder",
        "test",
        "development",
    }
)


class StartupGuardError(RuntimeError):
    """Raised when a permanent production guard rejects the current configuration."""


@dataclass(frozen=True)
class GuardViolation:
    code: str
    message: str


def _is_production(settings: Settings) -> bool:
    return settings.env == "production"


def _placeholder_jwt_secret(secret: str | None) -> bool:
    if not secret:
        return True
    return secret.strip().lower() in JWT_PLACEHOLDER_SECRETS


def collect_violations(settings: Settings) -> list[GuardViolation]:
    """Return the list of guard violations for the given settings, empty if safe.

    Development environments always return an empty list. Production checks:
      1. Dev bypass must be disabled.
      2. JWT secret must be present and not a known placeholder.
      3. Enabled integrations must have their required secrets.
      4. Disabled integrations impose no requirement.
    """
    violations: list[GuardViolation] = []

    if not _is_production(settings):
        return violations

    # 1. Dev bypass off in production.
    if settings.auth_dev_bypass:
        violations.append(
            GuardViolation(
                code="dev_bypass_enabled_in_production",
                message="AUTH_DEV_BYPASS must be false in production.",
            )
        )

    # 2. JWT secret must be set and not a placeholder.
    if _placeholder_jwt_secret(settings.jwt_secret):
        violations.append(
            GuardViolation(
                code="jwt_secret_placeholder_in_production",
                message="JWT_SECRET must be a strong non-placeholder value in production.",
            )
        )

    # 3. Integration-enabled checks.
    if settings.sendgrid_webhook_enabled and not settings.sendgrid_webhook_secret:
        violations.append(
            GuardViolation(
                code="sendgrid_webhook_secret_missing",
                message="SENDGRID_WEBHOOK_SECRET is required when SENDGRID_WEBHOOK_ENABLED=true.",
            )
        )
    if settings.stripe_writes_enabled and not settings.stripe_api_key:
        violations.append(
            GuardViolation(
                code="stripe_api_key_missing",
                message="STRIPE_API_KEY is required when STRIPE_WRITES_ENABLED=true.",
            )
        )
    if settings.stripe_webhook_enabled and not settings.stripe_webhook_secret:
        violations.append(
            GuardViolation(
                code="stripe_webhook_secret_missing",
                message="STRIPE_WEBHOOK_SECRET is required when STRIPE_WEBHOOK_ENABLED=true.",
            )
        )
    if settings.ai_enabled and not settings.emergent_llm_key:
        violations.append(
            GuardViolation(
                code="ai_provider_key_missing",
                message="EMERGENT_LLM_KEY is required when AI_ENABLED=true.",
            )
        )
    if settings.sms_enabled and not (settings.sms_provider_key and settings.sms_provider_secret):
        violations.append(
            GuardViolation(
                code="sms_provider_credentials_missing",
                message="SMS provider credentials are required when SMS_ENABLED=true.",
            )
        )

    return violations


def enforce_startup_guards(settings: Settings) -> None:
    """Raise StartupGuardError if any production guard rejects the current settings.

    Called from server.py startup hook. Development environments pass through.
    """
    violations = collect_violations(settings)
    if not violations:
        return
    joined = "; ".join(f"[{v.code}] {v.message}" for v in violations)
    raise StartupGuardError(f"Refusing to start: {joined}")


def format_violations(violations: Iterable[GuardViolation]) -> str:
    return "; ".join(f"[{v.code}] {v.message}" for v in violations)
