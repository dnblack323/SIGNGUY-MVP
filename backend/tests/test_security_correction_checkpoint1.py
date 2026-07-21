"""Security correction checkpoint 1 regression tests."""
from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.permissions import PLATFORM_CREATOR_ROLE, PlatformPerm
from app.deps import get_current_user
from app.services.platform_creator import PlatformCreatorError, assign_platform_creator_by_email
from server import app


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _override(user: dict):
    async def _get():
        return {**user}

    return _get


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest_asyncio.fixture
async def security_ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_a = f"sec-a-{suffix}"
    tenant_b = f"sec-b-{suffix}"
    owner_a = {
        "id": f"owner-a-{suffix}",
        "tenant_id": tenant_a,
        "email": f"owner-a-{suffix}@example.com",
        "role": "owner",
        "is_active": True,
    }
    owner_b = {
        "id": f"owner-b-{suffix}",
        "tenant_id": tenant_b,
        "email": f"owner-b-{suffix}@example.com",
        "role": "owner",
        "is_active": True,
    }
    platform_admin = {
        "id": f"platform-admin-{suffix}",
        "tenant_id": tenant_a,
        "email": f"platform-admin-{suffix}@example.com",
        "role": "staff",
        "is_active": True,
        "platform_admin": True,
        "platform_role": "admin",
    }
    creator_email = f"platform-creator-{suffix}@example.com"
    platform_creator = {
        "id": f"platform-creator-{suffix}",
        "tenant_id": tenant_a,
        "email": creator_email,
        "role": "staff",
        "is_active": True,
    }
    await db.tenants.insert_many([
        {"id": tenant_a, "slug": tenant_a, "name": "Security A"},
        {"id": tenant_b, "slug": tenant_b, "name": "Security B"},
    ])
    await db.users.insert_many([owner_a, owner_b, platform_admin, platform_creator])
    yield {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "owner_a": owner_a,
        "owner_b": owner_b,
        "platform_admin": platform_admin,
        "platform_creator": platform_creator,
        "creator_email": creator_email,
        "suffix": suffix,
    }
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_tenant_cannot_read_update_or_delete_another_tenant_records(security_ctx):
    other_customer = {
        "id": f"cust-b-{security_ctx['suffix']}",
        "tenant_id": security_ctx["tenant_b"],
        "name": "Other Customer",
        "archived": False,
        "created_at": _now(),
    }
    await db.customers.insert_one(other_customer)

    async with await _client_as(security_ctx["owner_a"]) as client:
        read = await client.get(f"/api/customers/{other_customer['id']}")
        update = await client.patch(f"/api/customers/{other_customer['id']}", json={"name": "Mutated"})
        delete = await client.delete(f"/api/customers/{other_customer['id']}")

    assert read.status_code == 404
    assert update.status_code == 404
    assert delete.status_code == 404
    saved = await db.customers.find_one({"id": other_customer["id"], "tenant_id": security_ctx["tenant_b"]}, {"_id": 0})
    assert saved["name"] == "Other Customer"
    assert saved.get("archived") is False


@pytest.mark.asyncio
async def test_tenant_scoped_reread_returns_only_authenticated_tenant_record(security_ctx):
    customer = {
        "id": f"cust-a-{security_ctx['suffix']}",
        "tenant_id": security_ctx["tenant_a"],
        "name": "Tenant Customer",
        "archived": False,
        "created_at": _now(),
    }
    await db.customers.insert_one(customer)

    async with await _client_as(security_ctx["owner_a"]) as client:
        response = await client.patch(f"/api/customers/{customer['id']}", json={"name": "Tenant Customer Updated"})

    assert response.status_code == 200, response.text
    assert response.json()["tenant_id"] == security_ctx["tenant_a"]
    assert response.json()["name"] == "Tenant Customer Updated"


@pytest.mark.asyncio
async def test_child_records_cannot_be_attached_to_another_tenant_parent(security_ctx):
    other_order = {
        "id": f"order-b-{security_ctx['suffix']}",
        "tenant_id": security_ctx["tenant_b"],
        "customer_id": f"cust-b-{security_ctx['suffix']}",
        "job_name": "Other Order",
        "number": 1,
        "status": "draft",
        "created_at": _now(),
    }

    await db.orders.insert_one(other_order)
    async with await _client_as(security_ctx["owner_a"]) as client:
        response = await client.post(
            f"/api/orders/{other_order['id']}/items",
            json={"description": "Wrong tenant", "quantity": 1, "unit_price_cents": 100},
        )

    assert response.status_code == 404
    assert await db.order_items.count_documents({"tenant_id": security_ctx["tenant_b"], "order_id": other_order["id"]}) == 0


@pytest.mark.asyncio
async def test_tenant_admin_cannot_access_platform_admin_api_or_assign_platform_creator(security_ctx):
    async with await _client_as(security_ctx["owner_a"]) as client:
        response = await client.post("/api/commercial/catalog/versions", json={"version": f"sec-{security_ctx['suffix']}"})

    assert response.status_code == 403
    with pytest.raises(PlatformCreatorError) as err:
        await assign_platform_creator_by_email(
            actor_user=security_ctx["owner_a"],
            email=security_ctx["creator_email"],
            reason="tenant admin attempt",
        )
    assert err.value.code == "platform_admin_required"


@pytest.mark.asyncio
async def test_ordinary_user_cannot_self_promote_with_tenant_user_update(security_ctx):
    async with await _client_as(security_ctx["owner_a"]) as client:
        response = await client.patch(
            f"/api/users/{security_ctx['owner_a']['id']}",
            json={"platform_role": PLATFORM_CREATOR_ROLE, "platform_admin": True, "full_name": "Still Tenant Owner"},
        )

    assert response.status_code == 200, response.text
    saved = await db.users.find_one({"id": security_ctx["owner_a"]["id"], "tenant_id": security_ctx["tenant_a"]}, {"_id": 0})
    assert saved.get("platform_role") is None
    assert saved.get("platform_admin") is not True


@pytest.mark.asyncio
async def test_platform_creator_assignment_is_stored_audited_and_grants_platform_access(security_ctx):
    assigned = await assign_platform_creator_by_email(
        actor_user=security_ctx["platform_admin"],
        email=security_ctx["creator_email"],
        reason="owner-approved checkpoint test",
    )

    assert assigned["platform_role"] == PLATFORM_CREATOR_ROLE
    assert assigned["platform_admin"] is True
    assert PlatformPerm.PLATFORM_CREATOR.value in assigned["permissions"]
    audit = await db.audit_events.find_one(
        {
            "tenant_id": security_ctx["tenant_a"],
            "entity_type": "user",
            "entity_id": security_ctx["platform_creator"]["id"],
            "action": "platform_creator.assigned",
        },
        {"_id": 0},
    )
    assert audit is not None

    async with await _client_as(assigned) as client:
        response = await client.post(
            "/api/commercial/catalog/versions",
            json={"version": f"creator-{security_ctx['suffix']}", "notes": "stored role access"},
        )

    assert response.status_code == 201, response.text
