"""pytest configuration for backend tests.

The isolated test environment is selected and validated in ``pytest_configure`` — before
test modules are collected and therefore before any ``app`` module reads MongoDB settings.
See ``tests/_test_env.py``; there is no other test-database configuration path.
"""
import sys
from pathlib import Path

import pytest

# Ensure app package is importable when running from /app/backend
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.test_isolation import UnsafeTestTargetError  # noqa: E402  (stdlib-only, no DB access)
from tests import _test_env  # noqa: E402

# Re-export EC2 async fixtures so pytest auto-discovers them.
from tests.conftest_ec2 import isolated_db, seeded_users, _ensure_indexes_once  # noqa: E402, F401


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    try:
        _test_env.configure_for_pytest(num_processes=int(getattr(config.option, "numprocesses", 0) or 0))
    except (UnsafeTestTargetError, _test_env.TestEnvError) as exc:
        raise pytest.UsageError(f"Isolated test environment unavailable - refusing to run.\n  {exc}") from exc


def pytest_sessionfinish(session, exitstatus):
    _test_env.finish_for_pytest()
