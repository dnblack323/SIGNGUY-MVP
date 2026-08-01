"""Isolation contracts for the disposable Webstores browser harness."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HARNESS_IMPORT = "import tests.webstores_browser_harness"


def _run_import(env_updates: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(env_updates)
    env.setdefault("MONGO_URL", "mongodb://localhost:27017")
    return subprocess.run(
        [sys.executable, "-c", HARNESS_IMPORT],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=15,
    )


def test_browser_harness_requires_explicit_test_flag():
    result = _run_import(
        {
            "WEBSTORES_BROWSER_HARNESS": "",
            "ENV": "test",
            "AUTH_DEV_BYPASS": "false",
            "DB_NAME": "webstores_browser_harness_missing_flag",
            "JWT_SECRET": "random-test-secret",
        }
    )
    assert result.returncode != 0
    assert "WEBSTORES_BROWSER_HARNESS=1 is required" in result.stderr


def test_browser_harness_refuses_production():
    result = _run_import(
        {
            "WEBSTORES_BROWSER_HARNESS": "1",
            "ENV": "production",
            "AUTH_DEV_BYPASS": "false",
            "DB_NAME": "webstores_browser_harness_prod",
            "JWT_SECRET": "random-test-secret",
        }
    )
    assert result.returncode != 0
    assert "cannot run in production" in result.stderr


def test_browser_harness_refuses_dev_bypass():
    result = _run_import(
        {
            "WEBSTORES_BROWSER_HARNESS": "1",
            "ENV": "test",
            "AUTH_DEV_BYPASS": "true",
            "DB_NAME": "webstores_browser_harness_dev_bypass",
            "JWT_SECRET": "random-test-secret",
        }
    )
    assert result.returncode != 0
    assert "requires AUTH_DEV_BYPASS=false" in result.stderr


def test_browser_harness_requires_isolated_database_name():
    result = _run_import(
        {
            "WEBSTORES_BROWSER_HARNESS": "1",
            "ENV": "test",
            "AUTH_DEV_BYPASS": "false",
            "DB_NAME": "signguy_mvp",
            "JWT_SECRET": "random-test-secret",
        }
    )
    assert result.returncode != 0
    assert "requires an isolated webstores_browser_harness_* DB_NAME" in result.stderr


def test_browser_harness_requires_random_jwt_secret():
    result = _run_import(
        {
            "WEBSTORES_BROWSER_HARNESS": "1",
            "ENV": "test",
            "AUTH_DEV_BYPASS": "false",
            "DB_NAME": "webstores_browser_harness_missing_secret",
            "JWT_SECRET": "dev-secret-do-not-use-in-prod",
        }
    )
    assert result.returncode != 0
    assert "requires random JWT_SECRET material" in result.stderr
