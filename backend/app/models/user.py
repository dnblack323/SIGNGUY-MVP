from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import EmailStr, Field

from .base import BaseDoc, _now


Role = Literal["owner", "admin", "staff"]


class Tenant(BaseDoc):
    name: str
    slug: str


class User(BaseDoc):
    tenant_id: str
    email: EmailStr
    full_name: str
    role: Role = "staff"
    password_hash: str
    is_active: bool = True
    last_login_at: Optional[datetime] = None
    google_id: Optional[str] = None


class PasswordResetToken(BaseDoc):
    user_id: str
    tenant_id: str
    token_hash: str
    expires_at: datetime
    used_at: Optional[datetime] = None
