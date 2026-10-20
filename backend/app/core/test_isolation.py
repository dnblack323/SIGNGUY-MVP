"""Fail-closed validation of the database/server target used by automated tests.

Standard library only, so it can run before any application module (and before
``app.core.config``) reads MongoDB settings. This is the single authority on what
counts as a valid test target; ``tests/_test_env.py`` creates targets, ``config.py``
re-validates them at import time, and standalone scripts call
``require_isolated_script_target``.

A valid target is proven by *ownership*, not by a name prefix:
  * a run id and owner token created by the test bootstrap for this run,
  * a database name that embeds that exact run id,
  * a loopback MongoDB endpoint that is not the developer's default port, unless CI.
"""
from __future__ import annotations

import re
import sys
from typing import Mapping
from urllib.parse import urlparse

RUN_ID_VAR = "SIGNGUY_TEST_RUN_ID"
OWNER_TOKEN_VAR = "SIGNGUY_TEST_OWNER_TOKEN"
TEST_API_URL_VAR = "SIGNGUY_TEST_API_BASE_URL"

TEST_DB_PREFIX = "signguy_test_"
OWNER_COLLECTION = "_signguy_test_owner"
FORBIDDEN_DB_NAMES = frozenset({
    "signguy_local", "signguy_mvp", "signguy", "signguy_prod", "signguy_production",
    "test_database", "admin", "config", "local",
})
DEV_MONGO_PORT = 27017
DEV_BACKEND_PORTS = frozenset({"8001", "8000"})
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

_RUN_ID_RE = re.compile(r"^[0-9a-f]{12}$")
_WORKER_RE = re.compile(r"^(main|gw\d{1,3})$")


class UnsafeTestTargetError(RuntimeError):
    """The test target is not provably disposable; refuse before any write."""


def test_db_name(run_id: str, worker: str) -> str:
    return f"{TEST_DB_PREFIX}{run_id}_{worker}"


def validate_mongo_url(url: str, env: Mapping[str, str]) -> None:
    if not url or "mongodb+srv" in url or "mongodb.net" in url:
        raise UnsafeTestTargetError("MongoDB URL is empty or points at a hosted cluster")
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "mongodb" or host not in LOOPBACK_HOSTS:
        raise UnsafeTestTargetError(f"Test MongoDB must be a loopback mongodb:// endpoint, got host {host!r}")
    if (parsed.port or DEV_MONGO_PORT) == DEV_MONGO_PORT and env.get("CI", "").lower() != "true":
        raise UnsafeTestTargetError(
            "Port 27017 is the developer MongoDB; tests may only use it inside CI. "
            "Let the test bootstrap start its private mongod instead."
        )


def parse_run_db_name(db_name: str, run_id: str) -> str:
    """Return the worker label of ``db_name`` or raise if it is not this run's database."""
    if not _RUN_ID_RE.match(run_id or ""):
        raise UnsafeTestTargetError(f"{RUN_ID_VAR} is missing or malformed")
    if db_name in FORBIDDEN_DB_NAMES:
        raise UnsafeTestTargetError(f"Database {db_name!r} is a protected database")
    prefix = f"{TEST_DB_PREFIX}{run_id}_"
    worker = db_name[len(prefix):] if db_name.startswith(prefix) else ""
    if not _WORKER_RE.match(worker):
        raise UnsafeTestTargetError(f"Database {db_name!r} does not belong to test run {run_id}")
    return worker


def validate_test_target(env: Mapping[str, str]) -> str:
    """Validate the MongoDB target in ``env``; return the database name."""
    run_id = env.get(RUN_ID_VAR, "")
    if not env.get(OWNER_TOKEN_VAR):
        raise UnsafeTestTargetError(f"{OWNER_TOKEN_VAR} is missing; the test bootstrap did not run")
    db_name = env.get("DB_NAME", "")
    parse_run_db_name(db_name, run_id)
    validate_mongo_url(env.get("MONGO_URL", ""), env)
    if env.get("ENV", "").strip().lower() == "production":
        raise UnsafeTestTargetError("ENV=production is not allowed in a test run")
    return db_name


def validate_test_api_url(url: str) -> None:
    """A test may only send requests to a loopback server that is not the dev backend."""
    parsed = urlparse(url or "")
    if (parsed.hostname or "").lower() not in LOOPBACK_HOSTS or not parsed.port:
        raise UnsafeTestTargetError(f"Test API URL must be an explicit loopback host:port, got {url!r}")
    if str(parsed.port) in DEV_BACKEND_PORTS:
        raise UnsafeTestTargetError(f"Port {parsed.port} is the development backend; refusing to send test requests")


def under_test(env: Mapping[str, str]) -> bool:
    return RUN_ID_VAR in env or "pytest" in sys.modules


def require_isolated_script_target(env: Mapping[str, str], api_url: str | None = None) -> None:
    """Entry guard for standalone test scripts; exits with code 2 instead of touching dev data."""
    try:
        validate_test_target(env)
        if api_url is not None:
            validate_test_api_url(api_url)
    except UnsafeTestTargetError as exc:
        sys.stderr.write(
            f"REFUSING TO RUN: {exc}\n"
            "Run this script inside an isolated environment:\n"
            "    python -m tests._test_env run -- python <script>\n"
        )
        raise SystemExit(2)
