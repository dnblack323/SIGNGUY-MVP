"""EC2 — Integration Status service.

Reports which integrations are configured and enabled WITHOUT revealing any
secret values. This is the single read-only surface for the frontend
`/settings/integrations` page.
"""
from __future__ import annotations

from typing import Any

from ..core.config import get_settings


def integration_status() -> dict[str, Any]:
    s = get_settings()

    def _report(name: str, enabled: bool, configured: bool, missing: list[str]) -> dict[str, Any]:
        return {
            "name": name,
            "enabled": enabled,
            "configured": configured,
            "missing_secrets": missing,
            "ok": (not enabled) or (configured and not missing),
        }

    return {
        "env": s.env,
        "integrations": [
            _report(
                "sendgrid_outbound",
                enabled=bool(s.sendgrid_api_key and s.sendgrid_from_email),
                configured=bool(s.sendgrid_api_key and s.sendgrid_from_email),
                missing=[
                    k for k, v in (
                        ("SENDGRID_API_KEY", s.sendgrid_api_key),
                        ("SENDGRID_FROM_EMAIL", s.sendgrid_from_email),
                    ) if not v
                ],
            ),
            _report(
                "sendgrid_webhook",
                enabled=s.sendgrid_webhook_enabled,
                configured=bool(s.sendgrid_webhook_secret),
                missing=(["SENDGRID_WEBHOOK_SECRET"] if (s.sendgrid_webhook_enabled and not s.sendgrid_webhook_secret) else []),
            ),
            _report(
                "stripe_writes",
                enabled=s.stripe_writes_enabled,
                configured=bool(s.stripe_api_key),
                missing=(["STRIPE_API_KEY"] if (s.stripe_writes_enabled and not s.stripe_api_key) else []),
            ),
            _report(
                "stripe_webhook",
                enabled=s.stripe_webhook_enabled,
                configured=bool(s.stripe_webhook_secret),
                missing=(["STRIPE_WEBHOOK_SECRET"] if (s.stripe_webhook_enabled and not s.stripe_webhook_secret) else []),
            ),
            _report(
                "ai_provider",
                enabled=s.ai_enabled,
                configured=bool(s.emergent_llm_key),
                missing=(["EMERGENT_LLM_KEY"] if (s.ai_enabled and not s.emergent_llm_key) else []),
            ),
            _report(
                "sms_provider",
                enabled=s.sms_enabled,
                configured=bool(s.sms_provider_key and s.sms_provider_secret),
                missing=[
                    k for k, v in (
                        ("SMS_PROVIDER_KEY", s.sms_provider_key),
                        ("SMS_PROVIDER_SECRET", s.sms_provider_secret),
                    ) if s.sms_enabled and not v
                ],
            ),
            _report(
                "object_storage",
                enabled=True,
                configured=bool(s.emergent_llm_key),
                missing=(["EMERGENT_LLM_KEY"] if not s.emergent_llm_key else []),
            ),
        ],
    }
