"""EC2 — Async pytest fixtures.

Each xdist worker has its own disposable database (see ``tests/_test_env.py``) that is
dropped when the run ends, so nothing here deletes data. Tests within one worker still
scope their data by unique tenant/user ids and query by those ids.

The `_ensure_indexes_once` fixture is session-scoped so the EC2 unique indexes
are created exactly once before any test runs.
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest_asyncio


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _ensure_indexes_once():
    from app.core.db import ensure_indexes

    await ensure_indexes()
    yield


@pytest_asyncio.fixture()
async def isolated_db():
    """Yield the module-level Motor `db`, bound to this worker's disposable test database.

    Not cleaned between tests: isolate via unique tenant/user ids (see `seeded_users`).
    """
    from app.core.db import db

    yield db


@pytest_asyncio.fixture()
async def seeded_users(isolated_db) -> dict[str, Any]:
    """Two tenants + one owner user each. All ids are unique per test."""
    db = isolated_db
    suffix = uuid.uuid4().hex[:8]
    tenant_a = {"id": f"tenant-a-{suffix}", "name": f"Alpha {suffix}", "slug": f"alpha-{suffix}"}
    tenant_b = {"id": f"tenant-b-{suffix}", "name": f"Bravo {suffix}", "slug": f"bravo-{suffix}"}
    await db.tenants.insert_many([tenant_a, tenant_b])
    user_a = {
        "id": f"user-a-{suffix}",
        "tenant_id": tenant_a["id"],
        "email": f"owner-a-{suffix}@example.com",
        "role": "owner",
        "is_active": True,
    }
    user_b = {
        "id": f"user-b-{suffix}",
        "tenant_id": tenant_b["id"],
        "email": f"owner-b-{suffix}@example.com",
        "role": "owner",
        "is_active": True,
    }
    await db.users.insert_many([user_a, user_b])
    return {"tenant_a": tenant_a, "tenant_b": tenant_b, "user_a": user_a, "user_b": user_b}
