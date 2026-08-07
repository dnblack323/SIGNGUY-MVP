from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.permissions import PlatformPerm
from app.core.security import create_access_token, hash_password
from server import app


def _token(user: dict) -> str:
    return create_access_token(subject=user["id"], tenant_id=user["tenant_id"])


def _impersonation_token(target: dict, admin: dict, log_id: str) -> str:
    return create_access_token(
        subject=target["id"],
        tenant_id=target["tenant_id"],
        extra={
            "impersonating": True,
            "impersonation_log_id": log_id,
            "platform_admin_id": admin["id"],
            "platform_admin_email": admin["email"],
        },
    )


def _headers(user: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(user)}"}


@pytest.fixture
async def ec20_ctx(clean_db):
    suffix = uuid.uuid4().hex[:8]
    tenant = {
        "id": f"ec20-tenant-{suffix}",
        "slug": f"ec20-tenant-{suffix}",
        "name": "EC20 Tenant",
        "plan": "pro",
        "is_active": True,
    }
    platform_tenant = {
        "id": f"ec20-platform-{suffix}",
        "slug": f"ec20-platform-{suffix}",
        "name": "EC20 Platform",
        "is_active": True,
    }
    owner = {
        "id": f"ec20-owner-{suffix}",
        "tenant_id": tenant["id"],
        "email": f"owner-{suffix}@example.com",
        "full_name": "Owner User",
        "role": "owner",
        "is_active": True,
        "password_hash": hash_password("Password123!"),
    }
    platform_admin = {
        "id": f"ec20-admin-{suffix}",
        "tenant_id": platform_tenant["id"],
        "email": f"platform-{suffix}@example.com",
        "full_name": "Platform Admin",
        "role": "staff",
        "is_active": True,
        "platform_admin": True,
        "permissions": [PlatformPerm.PLATFORM_ADMIN.value],
        "password_hash": hash_password("Password123!"),
    }
    await db.tenants.insert_many([tenant, platform_tenant])
    await db.users.insert_many([owner, platform_admin])
    await db.platform_settings.update_one(
        {"id": "global"},
        {"$set": {"announcement": None, "maintenance": {"enabled": False}}},
        upsert=True,
    )
    return {"tenant": tenant, "platform_tenant": platform_tenant, "owner": owner, "platform_admin": platform_admin}


@pytest.mark.asyncio
async def test_platform_admin_tenant_access_is_platform_only(ec20_ctx):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        denied = await client.get("/api/platform-admin/tenants", headers=_headers(ec20_ctx["owner"]))
        allowed = await client.get(
            "/api/platform-admin/tenants",
            params={"search": ec20_ctx["tenant"]["slug"]},
            headers=_headers(ec20_ctx["platform_admin"]),
        )

    assert denied.status_code == 403
    assert allowed.status_code == 200, allowed.text
    assert any(row["id"] == ec20_ctx["tenant"]["id"] for row in allowed.json()["items"])


@pytest.mark.asyncio
async def test_platform_admin_sample_data_seed_populates_dashboard_sections(ec20_ctx):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        seeded = await client.post("/api/platform-admin/sample-data/seed", headers=_headers(ec20_ctx["platform_admin"]))
        tenants = await client.get("/api/platform-admin/tenants", params={"search": "sample"}, headers=_headers(ec20_ctx["platform_admin"]))
        analytics = await client.get("/api/platform-admin/analytics", headers=_headers(ec20_ctx["platform_admin"]))
        email_logs = await client.get("/api/platform-admin/email-logs", params={"tenant_id": "demo-platform-admin-alpha"}, headers=_headers(ec20_ctx["platform_admin"]))

    assert seeded.status_code == 200, seeded.text
    body = seeded.json()
    assert "demo-platform-admin-alpha" in body["tenant_ids"]
    assert tenants.status_code == 200, tenants.text
    assert len(tenants.json()["items"]) >= 3
    assert analytics.status_code == 200, analytics.text
    assert analytics.json()["overview"]["analytics_events"] >= 3
    assert email_logs.status_code == 200, email_logs.text
    assert email_logs.json()["total"] >= 1


@pytest.mark.asyncio
async def test_suspend_blocks_tenant_login_but_not_platform_admin_login(ec20_ctx):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        suspended = await client.post(
            f"/api/platform-admin/tenants/{ec20_ctx['tenant']['id']}/suspend",
            json={"reason": "Dunning threshold reached"},
            headers=_headers(ec20_ctx["platform_admin"]),
        )
        owner_login = await client.post(
            "/api/auth/login",
            json={
                "tenant_slug": ec20_ctx["tenant"]["slug"],
                "email": ec20_ctx["owner"]["email"],
                "password": "Password123!",
            },
        )
        platform_login = await client.post(
            "/api/auth/login",
            json={
                "tenant_slug": ec20_ctx["platform_tenant"]["slug"],
                "email": ec20_ctx["platform_admin"]["email"],
                "password": "Password123!",
            },
        )

    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["tenant"]["is_active"] is False
    assert owner_login.status_code == 403
    assert owner_login.json()["detail"]["code"] == "tenant_suspended"
    assert owner_login.json()["detail"]["support_email"]
    assert platform_login.status_code == 200, platform_login.text


@pytest.mark.asyncio
async def test_announcement_settings_publish_public_banner(ec20_ctx):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        publish = await client.put(
            "/api/platform-admin/announcement",
            json={"message": "Scheduled update tonight", "severity": "warning", "dismissable": False},
            headers=_headers(ec20_ctx["platform_admin"]),
        )
        public = await client.get("/api/platform/announcement")

    assert publish.status_code == 200, publish.text
    assert public.status_code == 200
    assert public.json()["active"] is True
    assert public.json()["message"] == "Scheduled update tonight"
    assert public.json()["severity"] == "warning"
    assert public.json()["dismissable"] is False


@pytest.mark.asyncio
async def test_impersonation_returns_target_token_and_end_log(ec20_ctx):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        started = await client.post(
            "/api/platform-admin/impersonate",
            json={"target_user_id": ec20_ctx["owner"]["id"]},
            headers=_headers(ec20_ctx["platform_admin"]),
        )
        body = started.json()
        me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
        ended = await client.post(
            f"/api/platform-admin/impersonation-logs/{body['impersonation_log']['id']}/end",
            headers=_headers(ec20_ctx["platform_admin"]),
        )

    assert started.status_code == 200, started.text
    assert body["target_user"]["id"] == ec20_ctx["owner"]["id"]
    assert me.status_code == 200, me.text
    assert me.json()["user"]["impersonation"]["is_impersonating"] is True
    assert ended.status_code == 200, ended.text
    assert ended.json()["ended_at"]


@pytest.mark.asyncio
async def test_exit_impersonation_without_query_uses_current_impersonation_token(ec20_ctx):
    log = {
        "id": f"imp-log-{uuid.uuid4().hex[:8]}",
        "platform_admin_user_id": ec20_ctx["platform_admin"]["id"],
        "platform_admin_email": ec20_ctx["platform_admin"]["email"],
        "target_user_id": ec20_ctx["owner"]["id"],
        "target_user_email": ec20_ctx["owner"]["email"],
        "tenant_id": ec20_ctx["tenant"]["id"],
        "started_at": "2026-08-06T12:00:00+00:00",
        "ended_at": None,
    }
    await db.impersonation_logs.insert_one(log)
    token = _impersonation_token(ec20_ctx["owner"], ec20_ctx["platform_admin"], log["id"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/platform-admin/exit-impersonation", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200, response.text
    assert response.json()["ended_at"]


@pytest.mark.asyncio
async def test_maintenance_mode_blocks_user_writes_but_allows_platform_admin(ec20_ctx):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        enabled = await client.put(
            "/api/platform-admin/maintenance",
            json={"enabled": True, "message": "Maintenance window"},
            headers=_headers(ec20_ctx["platform_admin"]),
        )
        user_write = await client.post("/api/customers", json={"name": "Blocked Customer"}, headers=_headers(ec20_ctx["owner"]))
        admin_write = await client.put(
            "/api/platform-admin/maintenance",
            json={"enabled": False, "message": ""},
            headers=_headers(ec20_ctx["platform_admin"]),
        )

    assert enabled.status_code == 200, enabled.text
    assert user_write.status_code == 503
    assert user_write.json()["detail"]["code"] == "maintenance_mode"
    assert admin_write.status_code == 200, admin_write.text
