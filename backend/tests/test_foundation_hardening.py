"""Foundation Hardening — targeted regression tests for the external code
review fixes: tenant-scoped login/password-reset, reset-token hashing +
uniform response + rate limiting, Google-link ambiguity guard, vendor
materials route shadowing, and grouped-quiz validation/lifecycle locking.

Uses direct HTTP calls through the real app (not the `get_current_user`
override) for the auth endpoints since these are public/unauthenticated
routes by design.
"""
from __future__ import annotations
import uuid
from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient
from server import app
from app.core.db import db
from app.core.security import hash_reset_token
from app.deps import get_current_user


async def _anon_client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _override(u):
    async def _get(): return {**u}
    return _get


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


async def _register_tenant(c, slug, email, password="TestPass123!"):
    r = await c.post("/api/auth/register-tenant", json={
        "tenant_name": slug, "tenant_slug": slug, "owner_email": email,
        "owner_full_name": "QA Owner", "owner_password": password,
    })
    assert r.status_code == 201, r.text
    return r.json()


# ---------- Tenant-scoped login ----------

@pytest.mark.asyncio
async def test_login_requires_correct_shop_slug_for_ambiguous_email():
    shared_email = f"dup-{uuid.uuid4().hex[:6]}@example.com"
    async with await _anon_client() as c:
        s1 = f"shop-a-{uuid.uuid4().hex[:6]}"
        s2 = f"shop-b-{uuid.uuid4().hex[:6]}"
        await _register_tenant(c, s1, shared_email, "PasswordOne1!")
        await _register_tenant(c, s2, shared_email, "PasswordTwo2!")

        ok1 = await c.post("/api/auth/login", json={"tenant_slug": s1, "email": shared_email, "password": "PasswordOne1!"})
        assert ok1.status_code == 200
        assert ok1.json()["tenant"]["slug"] == s1

        ok2 = await c.post("/api/auth/login", json={"tenant_slug": s2, "email": shared_email, "password": "PasswordTwo2!"})
        assert ok2.status_code == 200
        assert ok2.json()["tenant"]["slug"] == s2

        # Wrong shop for a given password must fail, not silently pick a tenant
        wrong = await c.post("/api/auth/login", json={"tenant_slug": s1, "email": shared_email, "password": "PasswordTwo2!"})
        assert wrong.status_code == 401

        unknown_shop = await c.post("/api/auth/login", json={"tenant_slug": "does-not-exist-xyz", "email": shared_email, "password": "PasswordOne1!"})
        assert unknown_shop.status_code == 401


# ---------- Password reset: uniform response + hashed storage + rate limit ----------

@pytest.mark.asyncio
async def test_password_reset_response_uniform_in_production_mode():
    from app.routers import auth as auth_module
    email = f"reset-{uuid.uuid4().hex[:6]}@example.com"
    async with await _anon_client() as c:
        slug = f"reset-shop-{uuid.uuid4().hex[:6]}"
        await _register_tenant(c, slug, email)
        with patch.object(auth_module._settings, "env", "production"):
            known = await c.post("/api/auth/request-password-reset", json={"tenant_slug": slug, "email": email})
            unknown = await c.post("/api/auth/request-password-reset", json={"tenant_slug": "no-such-shop", "email": "nope@example.com"})
        assert known.status_code == unknown.status_code == 202
        assert known.json() == unknown.json() == {"ok": True}  # identical shape — no enumeration


@pytest.mark.asyncio
async def test_password_reset_token_stored_hashed_not_plaintext_and_rate_limited():
    from app.routers import auth as auth_module
    email = f"hash-{uuid.uuid4().hex[:6]}@example.com"
    async with await _anon_client() as c:
        slug = f"hash-shop-{uuid.uuid4().hex[:6]}"
        await _register_tenant(c, slug, email)
        raw_tokens = []
        with patch.object(auth_module._settings, "env", "development"):
            for _ in range(7):
                r = await c.post("/api/auth/request-password-reset", json={"tenant_slug": slug, "email": email})
                assert r.status_code == 202
                raw_tokens.append(r.json().get("dev_reset_token"))

        # Rate limit: only the first 5 requests within the window create a token
        assert all(raw_tokens[:5]), "first 5 requests should each mint a token"
        assert raw_tokens[5] is None and raw_tokens[6] is None, "6th+ request should be silently rate-limited"

        user = await db.users.find_one({"email": email})
        docs = [d async for d in db.password_reset_tokens.find({"user_id": user["id"]})]
        assert len(docs) == 5
        # Confirm no document stores the raw token value anywhere, only its hash
        for raw, d in zip(raw_tokens[:5], docs):
            assert "token" not in d
            assert d["token_hash"] != raw
            assert d["token_hash"] == hash_reset_token(raw)


# ---------- Google account-link ambiguity guard ----------

class _FakeResp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_google_link_rejects_ambiguous_email_across_tenants():
    shared_email = f"gdup-{uuid.uuid4().hex[:6]}@example.com"
    async with await _anon_client() as c:
        s1 = f"g-shop-a-{uuid.uuid4().hex[:6]}"
        s2 = f"g-shop-b-{uuid.uuid4().hex[:6]}"
        await _register_tenant(c, s1, shared_email)
        await _register_tenant(c, s2, shared_email)

        fake_profile = {"id": f"google-{uuid.uuid4().hex[:8]}", "email": shared_email, "name": "Dup"}
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_FakeResp(200, fake_profile))):
            r = await c.post("/api/auth/google/session", json={"session_id": "fake-session-id"})
        assert r.status_code == 409


@pytest.mark.asyncio
async def test_google_link_succeeds_for_unambiguous_email():
    email = f"gok-{uuid.uuid4().hex[:6]}@example.com"
    async with await _anon_client() as c:
        slug = f"g-ok-shop-{uuid.uuid4().hex[:6]}"
        await _register_tenant(c, slug, email)
        fake_profile = {"id": f"google-{uuid.uuid4().hex[:8]}", "email": email, "name": "OK"}
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_FakeResp(200, fake_profile))):
            r = await c.post("/api/auth/google/session", json={"session_id": "fake-session-id"})
        assert r.status_code == 200
        assert r.json()["tenant"]["slug"] == slug


# ---------- Vendor materials route shadowing fix ----------

@pytest.mark.asyncio
async def test_vendor_materials_route_not_shadowed_by_vid():
    ta = f"t-vend-{uuid.uuid4().hex[:6]}"
    ua = {"id": f"u-{uuid.uuid4().hex[:6]}", "tenant_id": ta, "email": "v@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_one({"id": ta, "slug": ta, "name": "TV"})
    app.dependency_overrides[get_current_user] = _override(ua)
    try:
        async with await _anon_client() as c:
            r = await c.get("/api/vendors/materials")
            assert r.status_code == 200
            assert "items" in r.json()
            assert r.json().get("detail") != "Vendor not found"
    finally:
        _clear()


# ---------- Grouped pricing quiz: validation + lifecycle ----------

async def _quiz_ctx():
    ta = f"t-quiz-{uuid.uuid4().hex[:6]}"
    ua = {"id": f"u-{uuid.uuid4().hex[:6]}", "tenant_id": ta, "email": "q@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_one({"id": ta, "slug": ta, "name": "TQ"})
    return ua


@pytest.mark.asyncio
async def test_quiz_apply_rejects_unknown_field_and_out_of_range_values():
    ua = await _quiz_ctx()
    app.dependency_overrides[get_current_user] = _override(ua)
    try:
        async with await _anon_client() as c:
            sub = await c.post("/api/pricing/quiz/submit", json={
                "category": "banners", "job_duration_hours": 2, "crew_size": 1,
                "customer_charge": 100, "price_floor": 50,
            })
            sid = sub.json()["id"]

            # Field the quiz never suggested (e.g. default_waste_percent) must be rejected
            bad_field = await c.post(f"/api/pricing/quiz/submissions/{sid}/apply", json={
                "accepted_shop_defaults": {"production_hourly_rate": 40, "default_waste_percent": 5},
            })
            assert bad_field.status_code == 400

            # Negative rate must fail Pydantic validation on ShopDefaultsIn (422)
            negative = await c.post(f"/api/pricing/quiz/submissions/{sid}/apply", json={
                "accepted_shop_defaults": {"production_hourly_rate": -10},
            })
            assert negative.status_code == 422

            # Margin > 100% must fail Pydantic validation
            bad_margin = await c.post(f"/api/pricing/quiz/submissions/{sid}/apply", json={
                "accepted_shop_defaults": {"target_profit_margin_percent": 250},
            })
            assert bad_margin.status_code == 422
    finally:
        _clear()


@pytest.mark.asyncio
async def test_quiz_status_lifecycle_locked():
    ua = await _quiz_ctx()
    app.dependency_overrides[get_current_user] = _override(ua)
    try:
        async with await _anon_client() as c:
            sub = await c.post("/api/pricing/quiz/submit", json={
                "category": "banners", "job_duration_hours": 2, "crew_size": 1,
                "customer_charge": 100, "price_floor": 50,
            })
            sid = sub.json()["id"]

            ok = await c.post(f"/api/pricing/quiz/submissions/{sid}/apply", json={"accepted_shop_defaults": {"production_hourly_rate": 40}})
            assert ok.status_code == 200
            assert ok.json()["status"] == "applied"

            # Re-apply must be rejected
            reapply = await c.post(f"/api/pricing/quiz/submissions/{sid}/apply", json={"accepted_shop_defaults": {"production_hourly_rate": 45}})
            assert reapply.status_code == 400

            # Cannot skip an already-applied submission
            skip_after_apply = await c.post(f"/api/pricing/quiz/submissions/{sid}/skip")
            assert skip_after_apply.status_code == 400

            # A skipped submission can never be applied
            sub2 = await c.post("/api/pricing/quiz/submit", json={
                "category": "banners", "job_duration_hours": 2, "crew_size": 1,
                "customer_charge": 100, "price_floor": 50,
            })
            sid2 = sub2.json()["id"]
            skipped = await c.post(f"/api/pricing/quiz/submissions/{sid2}/skip")
            assert skipped.status_code == 200
            assert skipped.json()["status"] == "skipped"
            apply_skipped = await c.post(f"/api/pricing/quiz/submissions/{sid2}/apply", json={"accepted_shop_defaults": {"production_hourly_rate": 40}})
            assert apply_skipped.status_code == 400
    finally:
        _clear()
