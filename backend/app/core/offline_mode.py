"""One definition of "no live integrations" for the test bootstrap and the demo seeder.

Standard library only, so it can run before ``app.core.config`` reads the environment.
Blanks every provider credential and switches every outbound integration off, even if the
caller's shell or ``backend/.env`` provides live values (the process environment wins over
``.env``, which ``load_dotenv`` never overrides).
"""
from __future__ import annotations

from typing import MutableMapping

BLANKED_VARS = (
    "SENDGRID_API_KEY", "SENDGRID_FROM_EMAIL", "SENDGRID_WEBHOOK_PUBLIC_KEY", "OPENAI_API_KEY",
    "AI_PROVIDER_API_KEY", "STRIPE_API_KEY", "STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY",
    "STRIPE_WEBHOOK_SECRET", "STRIPE_CONNECT_CLIENT_ID", "STRIPE_CONNECT_WEBHOOK_SECRET",
    "SMS_PROVIDER_KEY", "SMS_PROVIDER_SECRET", "GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET",
    "OBJECT_STORAGE_BASE_URL", "PUBLIC_APP_URL",
)
DISABLED_FLAGS = (
    "AI_ENABLED", "SMS_ENABLED", "STRIPE_ENABLED", "STRIPE_WRITES_ENABLED", "STRIPE_WEBHOOK_ENABLED",
    "GOOGLE_AUTH_ENABLED", "OPENAI_REALTIME_ENABLED", "SENDGRID_WEBHOOK_ENABLED", "ASSISTANT_TEXT_ENABLED",
)


def apply_offline_environment(env: MutableMapping[str, str]) -> None:
    for name in BLANKED_VARS:
        env[name] = ""
    for name in DISABLED_FLAGS:
        env[name] = "false"
