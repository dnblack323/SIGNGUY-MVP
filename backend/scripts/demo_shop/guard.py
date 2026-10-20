"""Fail-closed target verification for the demo-shop seeder. Runs before any app import.

The seeder may only ever touch ONE database: the developer's local ``signguy_local`` on a
loopback MongoDB, with ENV=development. A disposable test-run database (created by
``python -m tests._test_env run``) is accepted only when ``--disposable`` is given, so the
seeder itself can be verified without going near development data. Nothing here can be
pointed at production, a remote server, or any other database name.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values

from app.core.offline_mode import apply_offline_environment
from app.core.test_isolation import RUN_ID_VAR, UnsafeTestTargetError, validate_test_target

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEV_DATABASE = "signguy_local"
DEV_MONGO_HOST_PORTS = {("localhost", 27017), ("127.0.0.1", 27017)}


class UnsafeDemoTargetError(RuntimeError):
    """The seed/reset target is not the verified local development database."""


@dataclass(frozen=True)
class DemoTarget:
    mode: str  # "development" | "disposable"
    mongo_url: str
    db_name: str


def _flag(value: str | None) -> bool:
    return (value or "").strip().lower() == "true"


def resolve_target(*, disposable: bool, env_file: str | None = None, storage_path: str | None = None) -> DemoTarget:
    """Verify the target and prepare an offline process environment. Raises if anything is off."""
    if "pytest" in sys.modules:
        raise UnsafeDemoTargetError("The demo seeder never runs inside pytest")
    if RUN_ID_VAR in os.environ:
        if not disposable:
            raise UnsafeDemoTargetError("A disposable test environment is active; pass --disposable to seed it")
        try:
            db_name = validate_test_target(os.environ)
        except UnsafeTestTargetError as exc:
            raise UnsafeDemoTargetError(str(exc)) from exc
        target = DemoTarget("disposable", os.environ["MONGO_URL"], db_name)
        os.environ["DEV_LOGIN_PLATFORM_CREATOR"] = "true"  # a dev .env supplies this for the real target
    else:
        if disposable:
            raise UnsafeDemoTargetError("--disposable requires an active `python -m tests._test_env run` environment")
        if _flag(os.environ.get("CI")) or _flag(os.environ.get("GITHUB_ACTIONS")):
            raise UnsafeDemoTargetError("The development reset/seed never runs in CI")
        env_path = Path(env_file) if env_file else BACKEND_DIR / ".env"
        if not env_path.is_file():
            raise UnsafeDemoTargetError(f"Development environment file not found: {env_path} (use --env-file)")
        file_values = dotenv_values(env_path)
        cfg = {**file_values, **{k: v for k, v in os.environ.items() if k in ("MONGO_URL", "DB_NAME", "ENV", "AUTH_DEV_BYPASS")}}
        db_name, url = cfg.get("DB_NAME") or "", cfg.get("MONGO_URL") or ""
        parsed = urlparse(url)
        if db_name != DEV_DATABASE:
            raise UnsafeDemoTargetError(f"DB_NAME is {db_name!r}; the seeder only ever targets {DEV_DATABASE!r}")
        if parsed.scheme != "mongodb" or (parsed.hostname, parsed.port or 27017) not in DEV_MONGO_HOST_PORTS or parsed.username:
            raise UnsafeDemoTargetError(f"MONGO_URL must be the local unauthenticated MongoDB on localhost:27017, got {parsed.hostname}:{parsed.port}")
        if (cfg.get("ENV") or "development").strip().lower() != "development":
            raise UnsafeDemoTargetError(f"ENV is {cfg.get('ENV')!r}; the seeder requires ENV=development")
        if not _flag(cfg.get("AUTH_DEV_BYPASS")):
            raise UnsafeDemoTargetError("AUTH_DEV_BYPASS must be true in the local development .env")
        target = DemoTarget("development", url, db_name)
        for key, value in file_values.items():  # the app's config reads backend/.env only; honour the chosen file
            if value is not None:
                os.environ.setdefault(key, value)

    if storage_path:
        # Seeded artwork must land where the running app reads files from: <backend>/.data/object_storage.
        resolved = Path(storage_path).resolve()
        if resolved.parts[-2:] != (".data", "object_storage") or not resolved.parent.parent.is_dir():
            raise UnsafeDemoTargetError("--storage-path must be a <backend>/.data/object_storage directory of a checkout")
        os.environ["OBJECT_STORAGE_PATH"] = str(resolved)

    # Never send mail, charge cards or call AI providers while seeding.
    apply_offline_environment(os.environ)
    os.environ["ENV"] = "development"
    os.environ["AUTH_DEV_BYPASS"] = "true"
    return target
