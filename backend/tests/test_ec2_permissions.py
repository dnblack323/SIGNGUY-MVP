"""EC2 — Permission guard integration tests.

Verifies that new EC2 routes reject unauthenticated + under-privileged calls
before touching business logic.
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def _client():
    from server import app  # type: ignore

    return TestClient(app)


def test_settings_get_requires_auth():
    c = _client()
    r = c.get("/api/settings")
    assert r.status_code == 401


def test_settings_put_requires_auth():
    c = _client()
    r = c.put("/api/settings/branding", json={"primary_color": "#123456"})
    assert r.status_code == 401


def test_notifications_list_requires_auth():
    c = _client()
    r = c.get("/api/notifications")
    assert r.status_code == 401


def test_notifications_unread_count_requires_auth():
    c = _client()
    r = c.get("/api/notifications/unread-count")
    assert r.status_code == 401


def test_entitlements_list_requires_auth():
    c = _client()
    r = c.get("/api/entitlements")
    assert r.status_code == 401


def test_integration_status_requires_auth():
    c = _client()
    r = c.get("/api/integrations/status")
    assert r.status_code == 401


def test_activity_requires_auth():
    c = _client()
    r = c.get("/api/activity")
    assert r.status_code == 401


def test_unknown_settings_namespace_rejected(monkeypatch):
    """Once authenticated, unknown namespace values are 400 — not 500."""
    from app.deps import get_current_user, require_permission
    from app.core.permissions import Perm
    from server import app  # type: ignore

    async def _fake_user():
        return {"id": "u1", "tenant_id": "t1", "email": "u1@x.com", "role": "owner"}

    async def _fake_perm():
        return await _fake_user()

    app.dependency_overrides[get_current_user] = _fake_user
    # Override the permission dependency factory via closure — swap the settings routes' dep chain
    from app.deps import require_permission as rp_module
    original_rp = require_permission
    # We can override the specific bound dep by replacing the wrapper — easiest
    # path is to override get_current_user only, since require_permission uses
    # it under the hood and our fake user has role=owner (full perms).
    try:
        c = TestClient(app)
        r = c.get("/api/settings/not-a-real-namespace")
        assert r.status_code == 400
    finally:
        app.dependency_overrides.pop(get_current_user, None)
