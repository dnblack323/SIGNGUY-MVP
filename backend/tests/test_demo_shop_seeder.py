"""The developer-only demo-shop seeder: unsafe targets are refused, and a seeded shop is complete and idempotent.

The seeder only ever targets the local ``signguy_local`` (never run here) or an owned disposable test database.
The full-seed test gives the seeder its own owned database (outside this worker's database) and drops it afterwards.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from pymongo import MongoClient

from app.core import test_isolation as iso
from tests import _test_env

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_ENV_KEYS = {"DB_NAME", "MONGO_URL", "PYTEST_XDIST_WORKER", "ENV", "AUTH_DEV_BYPASS"}
CI_KEYS = {"CI", "GITHUB_ACTIONS"}


def _clean_env(*, keep_ci: bool = False, **extra: str) -> dict[str, str]:
    drop = TEST_ENV_KEYS if keep_ci else TEST_ENV_KEYS | CI_KEYS
    env = {k: v for k, v in os.environ.items() if not k.startswith("SIGNGUY_TEST_") and k not in drop}
    env.update(extra)
    return env


def _demo(*args: str, env: dict[str, str], timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "scripts.demo_shop", *args], cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=timeout)


def _dev_env_file(tmp_path: Path, **overrides: str) -> str:
    values = {"MONGO_URL": "mongodb://localhost:27017", "DB_NAME": "signguy_local", "ENV": "development", "AUTH_DEV_BYPASS": "true", **overrides}
    path = tmp_path / ".env"
    path.write_text("\n".join(f"{k}={v}" for k, v in values.items()), encoding="utf-8")
    return str(path)


def test_the_seeder_refuses_to_run_inside_pytest():
    from scripts.demo_shop.guard import UnsafeDemoTargetError, resolve_target

    with pytest.raises(UnsafeDemoTargetError):
        resolve_target(disposable=True)


@pytest.mark.parametrize("override,expect", [
    ({"DB_NAME": "signguy_mvp"}, "only ever targets"),
    ({"DB_NAME": "signguy_test_deadbeef0001_main"}, "only ever targets"),
    ({"MONGO_URL": "mongodb://db.example.com:27017"}, "local unauthenticated MongoDB"),
    ({"MONGO_URL": "mongodb://localhost:27018"}, "local unauthenticated MongoDB"),
    ({"MONGO_URL": "mongodb://user:pw@localhost:27017"}, "local unauthenticated MongoDB"),
    ({"MONGO_URL": "mongodb+srv://u:p@cluster0.example.mongodb.net/x"}, "local unauthenticated MongoDB"),
    ({"ENV": "production"}, "requires ENV=development"),
    ({"AUTH_DEV_BYPASS": "false"}, "AUTH_DEV_BYPASS"),
])
def test_unsafe_development_targets_are_refused_before_any_connection(tmp_path, override, expect):
    result = _demo("seed", "--env-file", _dev_env_file(tmp_path, **override), env=_clean_env())
    assert result.returncode == 2
    assert "REFUSING TO RUN" in result.stderr and expect in result.stderr


def test_missing_env_file_is_refused(tmp_path):
    result = _demo("seed", "--env-file", str(tmp_path / "nope.env"), env=_clean_env())
    assert result.returncode == 2 and "not found" in result.stderr


def test_ci_is_refused(tmp_path):
    result = _demo("seed", "--env-file", _dev_env_file(tmp_path), env=_clean_env(CI="true"))
    assert result.returncode == 2 and "never runs in CI" in result.stderr


def test_reset_needs_the_exact_database_name_confirmation(tmp_path):
    for args in (["reset"], ["reset", "--confirm", "signguy_mvp"], ["reset", "--confirm", "yes"]):
        result = _demo(*args, "--env-file", _dev_env_file(tmp_path), env=_clean_env())
        assert result.returncode == 2, result.stdout
        assert "requires --confirm signguy_local" in result.stderr


def test_active_test_environment_requires_the_disposable_flag(tmp_path):
    env = _clean_env(**{k: os.environ[k] for k in (iso.RUN_ID_VAR, iso.OWNER_TOKEN_VAR, "DB_NAME", "MONGO_URL")})
    result = _demo("seed", env=env)
    assert result.returncode == 2 and "--disposable" in result.stderr


def test_disposable_flag_without_a_test_environment_is_refused():
    result = _demo("seed", "--disposable", env=_clean_env())
    assert result.returncode == 2 and "requires an active" in result.stderr


def test_disposable_reset_never_drops_anything():
    env = _clean_env(**{k: os.environ[k] for k in (iso.RUN_ID_VAR, iso.OWNER_TOKEN_VAR, "DB_NAME", "MONGO_URL")})
    result = _demo("reset", "--disposable", "--confirm", os.environ["DB_NAME"], env=env)
    assert result.returncode == 2 and "only ever drops the local development database" in result.stderr


def test_storage_path_must_be_an_app_object_storage_directory(tmp_path):
    result = _demo("seed", "--env-file", _dev_env_file(tmp_path), "--storage-path", str(tmp_path), env=_clean_env())
    assert result.returncode == 2 and "object_storage" in result.stderr


def test_demo_shop_seed_is_complete_coherent_and_idempotent():
    """Seed twice into a dedicated owned database, then run the read-only verification."""
    run_id, token_sha = os.environ[iso.RUN_ID_VAR], _test_env._sha(os.environ[iso.OWNER_TOKEN_VAR])
    db_name = iso.test_db_name(run_id, "gw95")
    client = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=5000)
    client[db_name][iso.OWNER_COLLECTION].insert_one({"_id": "owner", "run_id": run_id, "token_sha256": token_sha, "worker": "gw95"})
    env = _clean_env(keep_ci=True, **{k: os.environ[k] for k in (iso.RUN_ID_VAR, iso.OWNER_TOKEN_VAR, "MONGO_URL", "OBJECT_STORAGE_PATH", "JWT_SECRET")}, DB_NAME=db_name)
    try:
        first = _demo("seed", "--disposable", env=env)
        assert first.returncode == 0, first.stdout[-1500:] + first.stderr[-1500:]
        assert "created:" in first.stdout and "'customers': 18" in first.stdout
        second = _demo("seed", "--disposable", env=env)
        assert second.returncode == 0, second.stderr[-1500:]
        created = [line for line in second.stdout.splitlines() if line.startswith("created:")]
        assert created == ["created: {}"], created
        counts = {c: client[db_name][c].count_documents({}) for c in ("tenants", "customers", "orders", "invoices", "work_orders", "webstores", "wrap_projects", "employees")}
        assert counts == {"tenants": 1, "customers": 18, "orders": 20, "invoices": 20, "work_orders": 20, "webstores": 4, "wrap_projects": 5, "employees": 4}
        assert "webstore_questionnaire_templates" not in client[db_name].list_collection_names()
        verify = _demo("verify", "--disposable", env=env)
        assert verify.returncode == 0, verify.stdout[-3000:]
        assert "0 failed" in verify.stdout
    finally:
        _test_env.drop_owned_database(client, db_name, run_id, token_sha)
        client.close()
