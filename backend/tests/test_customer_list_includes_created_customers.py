"""Regression: customers created through the API must appear in the default (active) list.

New customers persist ``merged_into=None``; the list filter used ``$exists: False`` and so returned
an empty Customers page for every shop whose customers were created in the app.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.deps import get_current_user
from server import app


@pytest_asyncio.fixture
async def owner_client():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-custlist-{suffix}"
    user = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "Customer List Shop"})
    await db.users.insert_one(user)
    app.dependency_overrides[get_current_user] = lambda: {**user}
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_created_customer_is_listed_archived_is_not(owner_client):
    kept = (await owner_client.post("/api/customers", json={"name": "Listed Customer"})).json()
    gone = (await owner_client.post("/api/customers", json={"name": "Archived Customer"})).json()
    assert (await owner_client.delete(f"/api/customers/{gone['id']}")).status_code in (200, 204)

    active = (await owner_client.get("/api/customers")).json()
    assert [c["id"] for c in active["items"]] == [kept["id"]]
    assert active["total"] == 1

    archived = (await owner_client.get("/api/customers", params={"status": "archived"})).json()
    assert [c["id"] for c in archived["items"]] == [gone["id"]]
