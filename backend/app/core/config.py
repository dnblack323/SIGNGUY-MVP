"""Env-backed application settings."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT_DIR / ".env")


class Settings:
    def __init__(self) -> None:
        self.mongo_url: str = os.environ["MONGO_URL"]
        self.db_name: str = os.environ["DB_NAME"]
        self.cors_origins: list[str] = os.environ.get("CORS_ORIGINS", "*").split(",")

        self.jwt_secret: str = os.environ.get("JWT_SECRET", "dev-secret-do-not-use-in-prod")
        self.jwt_algorithm: str = "HS256"
        self.jwt_access_ttl_minutes: int = int(os.environ.get("JWT_ACCESS_TTL_MINUTES", 60 * 24))  # 24h dev
        self.password_reset_ttl_minutes: int = 60

        self.app_name: str = os.environ.get("APP_NAME", "signguy-ai")
        self.emergent_llm_key: str | None = os.environ.get("EMERGENT_LLM_KEY") or None
        self.storage_url: str = "https://integrations.emergentagent.com/objstore/api/v1/storage"

        self.sendgrid_api_key: str | None = os.environ.get("SENDGRID_API_KEY") or None
        self.sendgrid_from_email: str | None = os.environ.get("SENDGRID_FROM_EMAIL") or None
        self.sendgrid_from_name: str = os.environ.get("SENDGRID_FROM_NAME", "SignGuy AI")

        # Dev-only auth bypass: when true, /api/auth/dev-login is enabled.
        # Frontend uses it to auto-provision a Dev Shop so the user doesn't have to log in.
        # MUST be set to false before production/deploy.
        self.auth_dev_bypass: bool = os.environ.get("AUTH_DEV_BYPASS", "false").lower() == "true"

        # EC1 — Environment + Integration-Enabled flags.
        # ENV values: "development" (default), "test", "production".
        # Startup guards (app.core.security_guards) enforce required secrets only
        # when the corresponding integration is enabled in production.
        self.env: str = os.environ.get("ENV", "development").strip().lower()

        # SendGrid webhook (inbound delivery events). Requires webhook secret when enabled.
        self.sendgrid_webhook_enabled: bool = (
            os.environ.get("SENDGRID_WEBHOOK_ENABLED", "false").lower() == "true"
        )
        self.sendgrid_webhook_secret: str | None = (
            os.environ.get("SENDGRID_WEBHOOK_SECRET") or None
        )

        # Stripe (Core payments). Distinguish "writes enabled" from "webhook enabled".
        self.stripe_writes_enabled: bool = (
            os.environ.get("STRIPE_WRITES_ENABLED", "false").lower() == "true"
        )
        self.stripe_webhook_enabled: bool = (
            os.environ.get("STRIPE_WEBHOOK_ENABLED", "false").lower() == "true"
        )
        self.stripe_api_key: str | None = os.environ.get("STRIPE_API_KEY") or None
        self.stripe_webhook_secret: str | None = (
            os.environ.get("STRIPE_WEBHOOK_SECRET") or None
        )

        # AI provider (Emergent LLM key). Only required when AI generation is enabled.
        self.ai_enabled: bool = os.environ.get("AI_ENABLED", "false").lower() == "true"

        # SMS/MMS. Only required when SMS is enabled.
        self.sms_enabled: bool = os.environ.get("SMS_ENABLED", "false").lower() == "true"
        self.sms_provider_key: str | None = os.environ.get("SMS_PROVIDER_KEY") or None
        self.sms_provider_secret: str | None = (
            os.environ.get("SMS_PROVIDER_SECRET") or None
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
