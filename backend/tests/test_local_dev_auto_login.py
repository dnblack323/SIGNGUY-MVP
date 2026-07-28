"""Local development auto-login guard tests."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from server import app
from app.core.permissions import PLATFORM_CREATOR_ROLE, PlatformPerm
from app.routers import auth as auth_router


@pytest.mark.asyncio
async def test_dev_login_uses_configured_local_owner_and_platform_creator(clean_db):
    email = f"thesigntistslab-{uuid.uuid4().hex[:8]}@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with (
            patch.object(auth_router._settings, "env", "development"),
            patch.object(auth_router._settings, "auth_dev_bypass", True),
            patch.object(auth_router._settings, "dev_login_email", email),
            patch.object(auth_router._settings, "dev_login_full_name", "The Signtists Lab"),
            patch.object(auth_router._settings, "dev_login_platform_creator", True),
        ):
            response = await client.post("/api/auth/dev-login")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["email"] == email
    assert body["user"]["role"] == "owner"
    assert body["user"]["platform_role"] == PLATFORM_CREATOR_ROLE
    assert body["user"]["platform_admin"] is True
    assert PlatformPerm.PLATFORM_CREATOR.value in body["user"]["permissions"]
    assert PlatformPerm.PLATFORM_ADMIN.value in body["user"]["permissions"]


@pytest.mark.asyncio
async def test_dev_login_refuses_production_even_when_bypass_flag_is_true():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with (
            patch.object(auth_router._settings, "env", "production"),
            patch.object(auth_router._settings, "auth_dev_bypass", True),
            patch.object(auth_router._settings, "dev_login_platform_creator", True),
        ):
            response = await client.post("/api/auth/dev-login")

    assert response.status_code == 404
