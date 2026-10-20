"""Fail-closed safety checks for browser tests (extends the Webstores browser harness guard).

Two layers, both refuse to continue on any doubt:

1. ``assert_backend_test_env(env)`` — the environment a browser-test backend may
   start with: explicit harness flag, not production, dev bypass off, an isolated
   ``webstores_browser_harness_*`` database that is never ``signguy_local`` or the
   developer database, random JWT material, and no live email or payment keys.
2. ``preflight(...)`` — run after the harness backend and the frontend dev server
   are up, before any browser step. It proves, without adding any route, that:
     * the backend answering on the harness port accepts the harness's random
       staff credentials (they exist only in the isolated database);
     * the frontend's ``/api`` proxy reaches that same backend (same login succeeds
       through the proxy);
     * the dev auto-login is refused through the proxy, so the browser cannot
       reach or modify the development shop.

Usage:  python -m tests.browser_target_guard --fixture <harness fixture json> --frontend http://127.0.0.1:3102
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Mapping

ISOLATED_DB_PREFIX = "webstores_browser_harness_"
FORBIDDEN_DB_NAMES = {"signguy_local", "signguy", "test_database"}
DEV_BACKEND_PORTS = {"8001"}
LIVE_SECRET_VARS = ("SENDGRID_API_KEY", "STRIPE_SECRET_KEY", "STRIPE_API_KEY", "STRIPE_WEBHOOK_SECRET", "STRIPE_CONNECT_WEBHOOK_SECRET")


class BrowserTargetError(RuntimeError):
    """The browser-test target is not provably isolated; refuse to continue."""


def _developer_db_name() -> str | None:
    """DB_NAME from the developer's backend/.env, if one exists next to this checkout."""
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.exists():
        return None
    for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip().startswith("DB_NAME="):
            return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None


def assert_backend_test_env(env: Mapping[str, str]) -> None:
    if env.get("WEBSTORES_BROWSER_HARNESS") != "1":
        raise BrowserTargetError("WEBSTORES_BROWSER_HARNESS=1 is required")
    if env.get("ENV", "development").strip().lower() == "production":
        raise BrowserTargetError("The browser harness cannot run in production")
    if env.get("AUTH_DEV_BYPASS", "false").strip().lower() == "true":
        raise BrowserTargetError("The browser harness requires AUTH_DEV_BYPASS=false")
    db_name = env.get("DB_NAME", "")
    if not db_name.startswith(ISOLATED_DB_PREFIX):
        raise BrowserTargetError("The browser harness requires an isolated webstores_browser_harness_* DB_NAME")
    if db_name in FORBIDDEN_DB_NAMES or db_name == _developer_db_name():
        raise BrowserTargetError(f"The browser harness refuses the development database {db_name!r}")
    jwt_secret = env.get("JWT_SECRET", "")
    if not jwt_secret or jwt_secret == "dev-secret-do-not-use-in-prod":
        raise BrowserTargetError("The browser harness requires random JWT_SECRET material")
    live = [name for name in LIVE_SECRET_VARS if (env.get(name) or "").strip()]
    if live:
        raise BrowserTargetError(f"The browser harness refuses live provider credentials: {', '.join(live)}")


def _post_json(url: str, payload: dict) -> tuple[int, dict]:
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except (urllib.error.URLError, OSError) as exc:
        raise BrowserTargetError(f"Cannot reach {url}: {exc}") from exc


def preflight(*, fixture: dict, frontend_url: str) -> list[str]:
    """Return the checks that passed; raise BrowserTargetError on the first failure."""
    passed: list[str] = []
    api_base = str(fixture.get("api_base") or "").rstrip("/")
    db_name = str(fixture.get("db_name") or "")
    if not db_name.startswith(ISOLATED_DB_PREFIX) or db_name in FORBIDDEN_DB_NAMES or db_name == _developer_db_name():
        raise BrowserTargetError(f"Fixture database {db_name!r} is not an isolated harness database")
    passed.append(f"isolated database {db_name}")
    for port in DEV_BACKEND_PORTS:
        if f":{port}/" in f"{api_base}/" or f":{port}/" in f"{frontend_url.rstrip('/')}/":
            raise BrowserTargetError(f"Port {port} belongs to the development backend")
    staff = fixture.get("staff_a") or {}
    login = {"tenant_slug": (fixture.get("tenant_a") or {}).get("slug"), "email": staff.get("email"), "password": staff.get("password")}
    status, body = _post_json(f"{api_base}/auth/login", login)
    if status != 200 or not body.get("access_token"):
        raise BrowserTargetError(f"Harness backend {api_base} did not accept the harness credentials (HTTP {status})")
    passed.append(f"backend {api_base} holds the harness tenant")
    proxied = f"{frontend_url.rstrip('/')}/api"
    status, body = _post_json(f"{proxied}/auth/login", login)
    if status != 200 or not body.get("access_token"):
        raise BrowserTargetError(f"Frontend proxy {proxied} does not reach the harness backend (HTTP {status})")
    passed.append(f"frontend proxy {proxied} reaches the harness backend")
    status, _ = _post_json(f"{proxied}/auth/dev-login", {})
    if status == 200:
        raise BrowserTargetError("Dev auto-login answered through the frontend proxy; the dev shop is reachable")
    passed.append(f"dev auto-login refused through the proxy (HTTP {status})")
    return passed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--frontend", required=True)
    args = parser.parse_args(argv)
    try:
        fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        for line in preflight(fixture=fixture, frontend_url=args.frontend):
            print(f"OK  {line}")
    except (BrowserTargetError, OSError, ValueError) as exc:
        print(f"REFUSED  {exc}", file=sys.stderr)
        return 2
    print("Browser target verified: isolated harness only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
