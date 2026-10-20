"""Safety tests for the test-isolation machinery itself (tests/_test_env.py).

These prove that a test run can only ever touch databases it created, refuses the
developer database and other unsafe targets before any write, and keeps live
integrations and file storage inside the disposable run.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from pymongo import MongoClient

from app.core import test_isolation as iso
from app.core.config import get_settings
from tests import _test_env
from tests.live_server import live_base_url

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _clean_env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("SIGNGUY_TEST_") and k not in {"DB_NAME", "MONGO_URL", "PYTEST_XDIST_WORKER"}}
    env.update(extra)
    return env


def _run_pytest(env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_ec2_permissions.py", "-q", "-n", "0", "-p", "no:cacheprovider"],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=120,
    )


def _run_id() -> str:
    return os.environ[iso.RUN_ID_VAR]


# ---------------------------------------------------------------- this run is isolated

def test_this_run_uses_only_its_own_disposable_database():
    s = get_settings()
    assert s.db_name == os.environ["DB_NAME"]
    assert s.db_name.startswith(f"{iso.TEST_DB_PREFIX}{_run_id()}_")
    assert s.db_name not in iso.FORBIDDEN_DB_NAMES
    assert s.mongo_url == os.environ["MONGO_URL"]
    assert iso.validate_test_target(os.environ) == s.db_name
    client = MongoClient(s.mongo_url, serverSelectionTimeoutMS=5000)
    assert client[s.db_name][iso.OWNER_COLLECTION].find_one({"_id": "owner"})["run_id"] == _run_id()
    foreign = [n for n in client.list_database_names() if n not in _test_env.SYSTEM_DBS and not n.startswith(f"{iso.TEST_DB_PREFIX}{_run_id()}_")]
    assert foreign == [], "the test server must hold nothing but this run's databases"


def test_workers_do_not_share_a_database():
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    assert os.environ["DB_NAME"].endswith(f"_{worker}")


def test_live_integrations_and_storage_are_disabled_and_disposable():
    s = get_settings()
    assert s.env == "test"
    for secret in (s.sendgrid_api_key, s.stripe_api_key, s.stripe_secret_key, s.stripe_webhook_secret,
                   s.openai_api_key, s.ai_provider_api_key, s.sms_provider_key, s.google_oauth_client_secret):
        assert secret is None
    assert not (s.ai_enabled or s.sms_enabled or s.stripe_enabled or s.stripe_writes_enabled or s.stripe_webhook_enabled or s.openai_realtime_enabled)
    storage = Path(s.object_storage_path).resolve()
    assert _test_env.RUNS_ROOT.resolve() in storage.parents and storage.parent.name == _run_id()


# ---------------------------------------------------------------- validator

@pytest.mark.parametrize("db_name", ["signguy_local", "signguy_mvp", "signguy_test_main", "signguy_test_gw0_0bc0f519", "signguy_ci", "prod", ""])
def test_database_names_not_owned_by_this_run_are_rejected(db_name):
    with pytest.raises(iso.UnsafeTestTargetError):
        iso.parse_run_db_name(db_name, _run_id())


def test_another_runs_database_is_rejected():
    with pytest.raises(iso.UnsafeTestTargetError):
        iso.parse_run_db_name(iso.test_db_name("0" * 12, "gw0"), _run_id())


@pytest.mark.parametrize("url", [
    "mongodb://localhost:27017", "mongodb://127.0.0.1", "mongodb+srv://u:p@cluster0.example.mongodb.net/x",
    "mongodb://db.internal.example.com:27018", "mongodb://10.0.0.5:27018", "",
])
def test_unsafe_mongo_urls_are_rejected_outside_ci(url):
    with pytest.raises(iso.UnsafeTestTargetError):
        iso.validate_mongo_url(url, {"CI": "false"})


def test_default_port_is_only_allowed_in_ci():
    iso.validate_mongo_url("mongodb://localhost:27017", {"CI": "true"})
    iso.validate_mongo_url("mongodb://127.0.0.1:50123", {})


@pytest.mark.parametrize("mutation", [
    {iso.OWNER_TOKEN_VAR: ""}, {"DB_NAME": "signguy_local"}, {"MONGO_URL": "mongodb://localhost:27017"},
    {iso.RUN_ID_VAR: "not-a-run-id"}, {"ENV": "production"},
])
def test_validate_test_target_fails_closed(mutation):
    env = {**os.environ, "CI": "false", **mutation}
    with pytest.raises(iso.UnsafeTestTargetError):
        iso.validate_test_target(env)


# ---------------------------------------------------------------- HTTP safety

@pytest.mark.parametrize("url", ["http://localhost:8001", "http://127.0.0.1:8000", "https://app.signguy.example", "http://127.0.0.1", ""])
def test_http_tests_cannot_target_the_dev_or_remote_application(url):
    with pytest.raises(iso.UnsafeTestTargetError):
        iso.validate_test_api_url(url)


def test_externally_supplied_api_base_url_is_refused(monkeypatch):
    monkeypatch.setenv("SIGNGUY_API_BASE_URL", "http://localhost:8001")
    with pytest.raises(iso.UnsafeTestTargetError):
        live_base_url()


# ---------------------------------------------------------------- ownership-checked cleanup

def test_cleanup_never_drops_a_database_it_does_not_own():
    client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=5000)
    token_sha = _test_env._sha(os.environ[iso.OWNER_TOKEN_VAR])
    unmarked = iso.test_db_name(_run_id(), "gw98")
    foreign_marker = iso.test_db_name(_run_id(), "gw99")
    client[unmarked]["x"].insert_one({"keep": True})
    client[foreign_marker][iso.OWNER_COLLECTION].insert_one({"_id": "owner", "run_id": _run_id(), "token_sha256": "someone-else"})
    try:
        assert _test_env.drop_owned_database(client, unmarked, _run_id(), token_sha) is False
        assert _test_env.drop_owned_database(client, foreign_marker, _run_id(), token_sha) is False
        assert {unmarked, foreign_marker} <= set(client.list_database_names())
        with pytest.raises(iso.UnsafeTestTargetError):  # name lookalike from a different run / the dev db
            _test_env.drop_owned_database(client, "signguy_local", _run_id(), token_sha)
        with pytest.raises(iso.UnsafeTestTargetError):
            _test_env.drop_owned_database(client, "signguy_test_gw0_0bc0f519", _run_id(), token_sha)
    finally:
        client.drop_database(unmarked)
        client.drop_database(foreign_marker)


def test_owned_database_is_dropped_when_marker_matches():
    client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=5000)
    name = iso.test_db_name(_run_id(), "gw97")
    token_sha = _test_env._sha(os.environ[iso.OWNER_TOKEN_VAR])
    client[name][iso.OWNER_COLLECTION].insert_one({"_id": "owner", "run_id": _run_id(), "token_sha256": token_sha})
    assert _test_env.drop_owned_database(client, name, _run_id(), token_sha) is True
    assert name not in client.list_database_names()


# ---------------------------------------------------------------- startup refusal (separate process)

def test_startup_refuses_the_development_database_name():
    result = _run_pytest(_clean_env(DB_NAME="signguy_local"))
    assert result.returncode != 0
    assert "refusing to run" in (result.stdout + result.stderr).lower()
    assert "passed" not in result.stdout


def test_startup_refuses_a_preset_mongo_url():
    result = _run_pytest(_clean_env(MONGO_URL="mongodb://localhost:27017"))
    assert result.returncode != 0
    assert "refusing to run" in (result.stdout + result.stderr).lower()


def test_startup_refuses_the_dev_port_as_an_external_test_server_outside_ci():
    result = _run_pytest(_clean_env(SIGNGUY_TEST_MONGO_URL="mongodb://localhost:27017", CI="false"))
    assert result.returncode != 0
    assert "refusing to run" in (result.stdout + result.stderr).lower()


def test_startup_refuses_a_remote_external_test_server():
    result = _run_pytest(_clean_env(SIGNGUY_TEST_MONGO_URL="mongodb+srv://u:p@cluster0.example.mongodb.net/x"))
    assert result.returncode != 0
    assert "refusing to run" in (result.stdout + result.stderr).lower()


def test_startup_refuses_when_no_mongod_is_available():
    result = _run_pytest(_clean_env(SIGNGUY_TEST_MONGOD=str(BACKEND_DIR / "no-such-mongod.exe")))
    assert result.returncode != 0
    text = (result.stdout + result.stderr).lower()
    assert "refusing to run" in text and "development database" in text


def test_importing_the_app_outside_a_bootstrapped_run_fails_closed():
    code = "import sys, pytest; sys.path.insert(0, '.'); from app.core.config import get_settings; get_settings()"
    result = subprocess.run([sys.executable, "-c", code], cwd=BACKEND_DIR, env=_clean_env(DB_NAME="signguy_local", MONGO_URL="mongodb://localhost:27017"),
                            capture_output=True, text=True, timeout=60)
    assert result.returncode != 0 and "UnsafeTestTargetError" in result.stderr


@pytest.mark.parametrize("script", ["tests/_seed_ui_ctx.py", "tests/e2e_portal_pay_curl.py", "scripts/smoke_backend.py", "scripts/poc_core.py"])
def test_standalone_scripts_refuse_the_development_target(script):
    env = _clean_env(DB_NAME="signguy_local", MONGO_URL="mongodb://localhost:27017", SIGNGUY_TEST_API_BASE_URL="http://localhost:8001")
    result = subprocess.run([sys.executable, script], cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 2
    assert "REFUSING TO RUN" in result.stderr
