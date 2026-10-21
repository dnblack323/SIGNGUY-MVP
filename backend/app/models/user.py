from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .base import BaseDoc


Role = Literal["owner", "admin", "staff"]


class Tenant(BaseDoc):
    name: str
    slug: str


class AssistantPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    personality_key: Literal["ops_partner", "wise_mentor", "cheerful_helper", "no_bs_direct", "sarcastic_funny"] = "ops_partner"
    display_name: str = Field(default="SignGuy AI", min_length=1, max_length=60)
    response_length: Literal["concise", "detailed"] = "concise"
    voice: Optional[str] = Field(default=None, max_length=60)
    spoken_replies: bool = False
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Use a valid IANA timezone")
        return value


class User(BaseDoc):
    tenant_id: str
    email: EmailStr
    full_name: str
    role: Role = "staff"
    password_hash: str
    is_active: bool = True
    last_login_at: Optional[datetime] = None
    google_id: Optional[str] = None
    assistant_preferences: AssistantPreferences = Field(default_factory=AssistantPreferences)


class PasswordResetToken(BaseDoc):
    user_id: str
    tenant_id: str
    token_hash: str
    expires_at: datetime
    used_at: Optional[datetime] = None
