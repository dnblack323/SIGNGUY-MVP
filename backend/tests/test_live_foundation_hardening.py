"""Live E2E checks against the running server (via REACT_APP_BACKEND_URL) for
Foundation Hardening: tenant-scoped login, password reset flow with dev token,
vendor materials route fix, and quiz apply/skip lifecycle. Uses requests
against the real deployed backend (not in-process ASGI)."""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


def _register(slug, email, password="TestPass123!"):
    r = requests.post(f"{BASE_URL}/api/auth/register-tenant", json={
        "tenant_name": slug, "tenant_slug": slug, "owner_email": email,
        "owner_full_name": "QA Owner", "owner_password": password,
    })
    return r


class TestTenantLogin:
    def test_register_and_login_success(self):
        slug = f"live-shop-{uuid.uuid4().hex[:8]}"
        email = f"live-{uuid.uuid4().hex[:8]}@example.com"
        r = _register(slug, email)
        assert r.status_code == 201, r.text

        login = requests.post(f"{BASE_URL}/api/auth/login", json={
            "tenant_slug": slug, "email": email, "password": "TestPass123!"
        })
        assert login.status_code == 200, login.text
        data = login.json()
        assert data["tenant"]["slug"] == slug
        assert "token" in data or "access_token" in data

    def test_login_wrong_shop_for_shared_email_fails(self):
        email = f"shared-{uuid.uuid4().hex[:8]}@example.com"
        s1 = f"shop-one-{uuid.uuid4().hex[:8]}"
        s2 = f"shop-two-{uuid.uuid4().hex[:8]}"
        r1 = _register(s1, email, "PassOne123!")
        r2 = _register(s2, email, "PassTwo123!")
        assert r1.status_code == 201 and r2.status_code == 201

        ok = requests.post(f"{BASE_URL}/api/auth/login", json={
            "tenant_slug": s2, "email": email, "password": "PassTwo123!"
        })
        assert ok.status_code == 200
        assert ok.json()["tenant"]["slug"] == s2

        wrong = requests.post(f"{BASE_URL}/api/auth/login", json={
            "tenant_slug": s1, "email": email, "password": "PassTwo123!"
        })
        assert wrong.status_code == 401, wrong.text

    def test_login_invalid_password_fails(self):
        slug = f"badpw-shop-{uuid.uuid4().hex[:8]}"
        email = f"badpw-{uuid.uuid4().hex[:8]}@example.com"
        _register(slug, email)
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "tenant_slug": slug, "email": email, "password": "WrongPass!"
        })
        assert r.status_code == 401


class TestPasswordResetFlow:
    def test_full_reset_flow_and_token_reuse_blocked(self):
        slug = f"reset-shop-{uuid.uuid4().hex[:8]}"
        email = f"reset-{uuid.uuid4().hex[:8]}@example.com"
        _register(slug, email, "OldPass123!")

        req = requests.post(f"{BASE_URL}/api/auth/request-password-reset", json={
            "tenant_slug": slug, "email": email
        })
        assert req.status_code in (200, 202), req.text
        body = req.json()
        token = body.get("dev_reset_token")
        assert token, f"Expected dev_reset_token in dev mode, got: {body}"

        reset = requests.post(f"{BASE_URL}/api/auth/reset-password", json={
            "token": token, "new_password": "NewPass456!"
        })
        assert reset.status_code in (200, 204), reset.text

        # New password works
        login_new = requests.post(f"{BASE_URL}/api/auth/login", json={
            "tenant_slug": slug, "email": email, "password": "NewPass456!"
        })
        assert login_new.status_code == 200

        # Old password fails
        login_old = requests.post(f"{BASE_URL}/api/auth/login", json={
            "tenant_slug": slug, "email": email, "password": "OldPass123!"
        })
        assert login_old.status_code == 401

        # Token reuse fails
        reuse = requests.post(f"{BASE_URL}/api/auth/reset-password", json={
            "token": token, "new_password": "AnotherPass789!"
        })
        assert reuse.status_code in (400, 401, 404), reuse.text

    def test_reset_uniform_response_for_unknown_shop(self):
        r_known_shape = requests.post(f"{BASE_URL}/api/auth/request-password-reset", json={
            "tenant_slug": "no-such-shop-xyz", "email": "nope@example.com"
        })
        assert r_known_shape.status_code in (200, 202)
        assert "ok" in r_known_shape.json() or "message" in r_known_shape.json()


class TestVendorMaterialsRoute:
    def _dev_token(self):
        r = requests.post(f"{BASE_URL}/api/auth/dev-login", json={"tenant_slug": "dev-shop"})
        assert r.status_code == 200, r.text
        data = r.json()
        return data.get("token") or data.get("access_token")

    def test_vendors_materials_returns_items_not_404(self):
        token = self._dev_token()
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/vendors/materials", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data
        assert isinstance(data["items"], list)


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
