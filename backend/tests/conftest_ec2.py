"""EC2 — Async pytest fixtures.

Tests run in parallel across xdist workers against a shared MongoDB, so
fixtures MUST NOT globally delete data mid-run. Each test scopes its own
data via a unique tenant/user id and queries by that id.

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
async def clean_db():
    """Yield the module-level Motor `db` WITHOUT destructive cleanup.

    Tests must isolate via unique tenant/user ids (see `seeded_users`) so
    parallel workers don't clobber each other.
    """
    from app.core.db import db

    yield db


@pytest_asyncio.fixture()
async def seeded_users(clean_db) -> dict[str, Any]:
    """Two tenants + one owner user each. All ids are unique per test."""
    db = clean_db
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
