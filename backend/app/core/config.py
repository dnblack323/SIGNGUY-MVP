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
        default_cors = "http://localhost:3000,http://127.0.0.1:3000"
        self.cors_origins: list[str] = [origin.strip() for origin in os.environ.get("CORS_ORIGINS", default_cors).split(",") if origin.strip()]

        self.jwt_secret: str = os.environ.get("JWT_SECRET", "dev-secret-do-not-use-in-prod")
        self.jwt_algorithm: str = "HS256"
        self.jwt_access_ttl_minutes: int = int(os.environ.get("JWT_ACCESS_TTL_MINUTES", 60 * 24))  # 24h dev
        self.password_reset_ttl_minutes: int = 60

        self.app_name: str = os.environ.get("APP_NAME", "signguy-ai")
        self.ai_provider_api_key: str | None = os.environ.get("AI_PROVIDER_API_KEY") or None
        self.storage_backend: str = os.environ.get("STORAGE_BACKEND", "filesystem").strip().lower()
        self.object_storage_path: str | None = os.environ.get("OBJECT_STORAGE_PATH") or None
        self.object_storage_base_url: str | None = os.environ.get("OBJECT_STORAGE_BASE_URL") or None

        self.sendgrid_api_key: str | None = os.environ.get("SENDGRID_API_KEY") or None
        self.sendgrid_from_email: str | None = os.environ.get("SENDGRID_FROM_EMAIL") or None
        self.sendgrid_from_name: str = os.environ.get("SENDGRID_FROM_NAME", "SignGuy AI")

        # Dev-only auth bypass: when true, /api/auth/dev-login is enabled.
        # Frontend uses it to auto-provision a Dev Shop so the user doesn't have to log in.
        # MUST be set to false before production/deploy.
        self.auth_dev_bypass: bool = os.environ.get("AUTH_DEV_BYPASS", "false").lower() == "true"
        self.dev_login_email: str = os.environ.get("DEV_LOGIN_EMAIL", "dev@signguy-dev.example.com").strip().lower()
        self.dev_login_full_name: str = os.environ.get("DEV_LOGIN_FULL_NAME", "Dev Owner").strip() or "Dev Owner"
        self.dev_login_platform_creator: bool = (
            os.environ.get("DEV_LOGIN_PLATFORM_CREATOR", "false").lower() == "true"
        )

        # EC1 — Environment + Integration-Enabled flags.
        # ENV values: "development" (default), "test", "production".
        # Startup guards (app.core.security_guards) enforce required secrets only
        # when the corresponding integration is enabled in production.
        self.env: str = os.environ.get("ENV", "development").strip().lower()
        self.deployment_context: str = os.environ.get("DEPLOYMENT_CONTEXT", "local").strip().lower()

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

        # Webstores Stripe-ready foundation. These values describe a future
        # provider adapter; no Webstore provider calls are made by this build.
        self.stripe_enabled: bool = os.environ.get("STRIPE_ENABLED", "false").lower() == "true"
        self.stripe_mode: str = os.environ.get("STRIPE_MODE", "test").strip().lower()
        self.stripe_secret_key: str | None = os.environ.get("STRIPE_SECRET_KEY") or None
        self.stripe_publishable_key: str | None = os.environ.get("STRIPE_PUBLISHABLE_KEY") or None
        self.stripe_connect_client_id: str | None = os.environ.get("STRIPE_CONNECT_CLIENT_ID") or None
        self.stripe_connect_return_url: str | None = os.environ.get("STRIPE_CONNECT_RETURN_URL") or None
        self.stripe_connect_refresh_url: str | None = os.environ.get("STRIPE_CONNECT_REFRESH_URL") or None
        self.stripe_checkout_success_url: str | None = os.environ.get("STRIPE_CHECKOUT_SUCCESS_URL") or None
        self.stripe_checkout_cancel_url: str | None = os.environ.get("STRIPE_CHECKOUT_CANCEL_URL") or None
        self.stripe_charge_model: str = os.environ.get("STRIPE_CONNECT_CHARGE_MODEL", "deferred").strip().lower()

        # AI provider. Only required when AI generation is enabled.
        self.ai_enabled: bool = os.environ.get("AI_ENABLED", "false").lower() == "true"
        self.google_auth_enabled: bool = os.environ.get("GOOGLE_AUTH_ENABLED", "false").lower() == "true"
        self.google_oauth_client_id: str | None = os.environ.get("GOOGLE_OAUTH_CLIENT_ID") or None
        self.google_oauth_client_secret: str | None = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET") or None
        self.google_oauth_auth_url: str = os.environ.get(
            "GOOGLE_OAUTH_AUTH_URL",
            "https://accounts.google.com/o/oauth2/v2/auth",
        )
        self.google_oauth_token_url: str = os.environ.get(
            "GOOGLE_OAUTH_TOKEN_URL",
            "https://oauth2.googleapis.com/token",
        )
        self.google_oauth_userinfo_url: str = os.environ.get(
            "GOOGLE_OAUTH_USERINFO_URL",
            "https://openidconnect.googleapis.com/v1/userinfo",
        )
        self.google_oauth_state_ttl_seconds: int = int(os.environ.get("GOOGLE_OAUTH_STATE_TTL_SECONDS", "600"))

        # EC18 - OpenAI Realtime voice for the paid Business Assistant.
        # The permanent API key is backend-only. Browser clients receive only
        # short-lived Realtime credentials minted by the backend when enabled.
        self.openai_api_key: str | None = os.environ.get("OPENAI_API_KEY") or None
        self.openai_realtime_enabled: bool = (
            os.environ.get("OPENAI_REALTIME_ENABLED", "false").lower() == "true"
        )
        self.openai_realtime_model: str = os.environ.get("OPENAI_REALTIME_MODEL", "gpt-realtime-2.1")
        self.openai_realtime_voice: str = os.environ.get("OPENAI_REALTIME_VOICE", "alloy")
        self.openai_realtime_timeout_seconds: float = float(os.environ.get("OPENAI_REALTIME_TIMEOUT_SECONDS", "10"))
        self.openai_realtime_turn_detection: str = os.environ.get("OPENAI_REALTIME_TURN_DETECTION", "server_vad")
        self.openai_realtime_push_to_talk_default: bool = (
            os.environ.get("OPENAI_REALTIME_PUSH_TO_TALK_DEFAULT", "true").lower() == "true"
        )
        self.openai_realtime_rate_limit_sessions: int = int(os.environ.get("OPENAI_REALTIME_RATE_LIMIT_SESSIONS", "10"))
        self.openai_realtime_rate_limit_window_seconds: int = int(os.environ.get("OPENAI_REALTIME_RATE_LIMIT_WINDOW_SECONDS", "60"))
        self.assistant_transcript_retention: str = os.environ.get("ASSISTANT_TRANSCRIPT_RETENTION", "conversation_policy")

        # SMS/MMS. Only required when SMS is enabled.
        self.sms_enabled: bool = os.environ.get("SMS_ENABLED", "false").lower() == "true"
        self.sms_provider_key: str | None = os.environ.get("SMS_PROVIDER_KEY") or None
        self.sms_provider_secret: str | None = (
            os.environ.get("SMS_PROVIDER_SECRET") or None
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
