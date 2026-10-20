"""Fail-closed browser-test target checks (tests/browser_target_guard.py)."""
from __future__ import annotations

import pytest

from tests import browser_target_guard as guard

SAFE_ENV = {
    "WEBSTORES_BROWSER_HARNESS": "1",
    "ENV": "test",
    "AUTH_DEV_BYPASS": "false",
    "DB_NAME": "webstores_browser_harness_unit",
    "JWT_SECRET": "random-unit-secret",
}
FIXTURE = {
    "db_name": "webstores_browser_harness_unit",
    "api_base": "http://127.0.0.1:8102/api",
    "tenant_a": {"slug": "harness-a"},
    "staff_a": {"email": "staff-a@example.com", "password": "random-password"},
}


def test_backend_env_accepts_only_an_isolated_harness_setup():
    guard.assert_backend_test_env(SAFE_ENV)


@pytest.mark.parametrize("override, message", [
    ({"WEBSTORES_BROWSER_HARNESS": ""}, "WEBSTORES_BROWSER_HARNESS=1 is required"),
    ({"ENV": "production"}, "cannot run in production"),
    ({"AUTH_DEV_BYPASS": "true"}, "requires AUTH_DEV_BYPASS=false"),
    ({"DB_NAME": "signguy_local"}, "isolated webstores_browser_harness_* DB_NAME"),
    ({"DB_NAME": "signguy_phase2b_browser"}, "isolated webstores_browser_harness_* DB_NAME"),
    ({"JWT_SECRET": "dev-secret-do-not-use-in-prod"}, "random JWT_SECRET"),
    ({"SENDGRID_API_KEY": "SG.real"}, "refuses live provider credentials: SENDGRID_API_KEY"),
    ({"STRIPE_SECRET_KEY": "sk_live_x"}, "refuses live provider credentials: STRIPE_SECRET_KEY"),
])
def test_backend_env_refuses_anything_else(override, message):
    with pytest.raises(guard.BrowserTargetError, match=message.replace("*", r"\*")):
        guard.assert_backend_test_env({**SAFE_ENV, **override})


def test_backend_env_refuses_the_developer_database(monkeypatch):
    monkeypatch.setattr(guard, "_developer_db_name", lambda: "webstores_browser_harness_unit")
    with pytest.raises(guard.BrowserTargetError, match="development database"):
        guard.assert_backend_test_env(SAFE_ENV)


def _fake_http(responses: dict[str, int]):
    calls: list[str] = []

    def post(url: str, payload: dict):
        calls.append(url)
        for suffix, status in responses.items():
            if url.endswith(suffix):
                return status, ({"access_token": "t"} if status == 200 else {})
        raise AssertionError(f"unexpected call {url}")

    return post, calls


def test_preflight_passes_only_when_proxy_reaches_the_harness(monkeypatch):
    post, calls = _fake_http({"8102/api/auth/login": 200, "3102/api/auth/login": 200, "/auth/dev-login": 404})
    monkeypatch.setattr(guard, "_post_json", post)
    passed = guard.preflight(fixture=FIXTURE, frontend_url="http://127.0.0.1:3102")
    assert len(passed) == 4 and calls[1] == "http://127.0.0.1:3102/api/auth/login"


@pytest.mark.parametrize("responses, frontend, message", [
    # Proxy points somewhere else (e.g. the dev backend): harness credentials are unknown there.
    ({"8102/api/auth/login": 200, "3102/api/auth/login": 401}, "http://127.0.0.1:3102", "does not reach the harness backend"),
    # Dev auto-login reachable through the proxy: the dev shop could be modified.
    ({"8102/api/auth/login": 200, "3102/api/auth/login": 200, "/auth/dev-login": 200}, "http://127.0.0.1:3102", "dev shop is reachable"),
    # The backend on the harness port is not the harness.
    ({"8102/api/auth/login": 401}, "http://127.0.0.1:3102", "did not accept the harness credentials"),
])
def test_preflight_refuses_unsafe_targets(monkeypatch, responses, frontend, message):
    post, _ = _fake_http(responses)
    monkeypatch.setattr(guard, "_post_json", post)
    with pytest.raises(guard.BrowserTargetError, match=message):
        guard.preflight(fixture=FIXTURE, frontend_url=frontend)


def test_preflight_refuses_dev_ports_and_dev_databases(monkeypatch):
    monkeypatch.setattr(guard, "_post_json", lambda *a: (_ for _ in ()).throw(AssertionError("must not call")))
    with pytest.raises(guard.BrowserTargetError, match="development backend"):
        guard.preflight(fixture={**FIXTURE, "api_base": "http://localhost:8001/api"}, frontend_url="http://127.0.0.1:3102")
    with pytest.raises(guard.BrowserTargetError, match="not an isolated harness database"):
        guard.preflight(fixture={**FIXTURE, "db_name": "signguy_local"}, frontend_url="http://127.0.0.1:3102")
