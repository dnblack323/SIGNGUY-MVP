"""EC10 Phase 10G - reusable templates."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.deps import get_current_user
from server import app


def _override(u):
    async def _get():
        return {**u}
    return _get


async def _staff_client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-ec10g-{suffix}"
    owner = {"id": f"u-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    customer = {"id": f"cust-{suffix}", "tenant_id": tenant_id, "name": "Template Customer", "archived": False}
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "Tenant"})
    await db.users.insert_one(owner)
    await db.customers.insert_one(customer)
    yield {"tenant_id": tenant_id, "owner": owner, "customer": customer}
    _clear()


@pytest.mark.asyncio
async def test_intake_template_apply_copies_body_and_later_edits_do_not_mutate_created_intake(ctx):
    async with await _staff_client(ctx["owner"]) as c:
        created = await c.post("/api/templates", json={
            "name": "Banner intake", "template_type": "intake",
            "body": {
                "customer_id": ctx["customer"]["id"], "project_name": "Banner job",
                "items": [{"category": "banners", "item_name": "Banner", "description": "13 oz banner", "quantity": 2}],
            },
        })
        assert created.status_code == 201, created.text
        template_id = created.json()["id"]
        applied = await c.post(f"/api/templates/{template_id}/apply", json={"target_type": "new_intake"})
        assert applied.status_code == 200, applied.text
        intake = applied.json()["record"]
        assert intake["source_type"] == "saved_template"
        assert intake["project_name"] == "Banner job"
        assert intake["items"][0]["item_name"] == "Banner"

        patched = await c.patch(f"/api/templates/{template_id}", json={"body": {"customer_id": ctx["customer"]["id"], "project_name": "Changed"}})
        assert patched.status_code == 200
        fetched = await c.get(f"/api/intake/{intake['id']}")
        assert fetched.json()["project_name"] == "Banner job"


@pytest.mark.asyncio
async def test_decision_option_template_copies_options_and_archive_blocks_apply(ctx):
    async with await _staff_client(ctx["owner"]) as c:
        room = await c.post("/api/decision-rooms", json={"title": "Template room", "customer_id": ctx["customer"]["id"]})
        assert room.status_code == 201, room.text
        room_id = room.json()["id"]
        tpl = await c.post("/api/templates", json={
            "name": "Good better best", "template_type": "decision_options",
            "body": {"options": [
                {"customer_label": "Good", "manual_price_cents": 10000},
                {"customer_label": "Best", "badge_type": "recommended", "manual_price_cents": 20000},
            ]},
        })
        assert tpl.status_code == 201, tpl.text
        template_id = tpl.json()["id"]
        applied = await c.post(f"/api/templates/{template_id}/apply", json={"target_type": "decision_room", "target_id": room_id})
        assert applied.status_code == 200, applied.text
        labels = [o["customer_label"] for o in applied.json()["record"]["options"]]
        assert labels == ["Good", "Best"]

        assert (await c.patch(f"/api/templates/{template_id}", json={"body": {"options": [{"customer_label": "Changed", "manual_price_cents": 1}]}})).status_code == 200
        unchanged_room = (await c.get(f"/api/decision-rooms/{room_id}")).json()
        assert [o["customer_label"] for o in unchanged_room["options"]] == ["Good", "Best"]

        archived = await c.post(f"/api/templates/{template_id}/archive")
        assert archived.status_code == 200
        blocked = await c.post(f"/api/templates/{template_id}/apply", json={"target_type": "decision_room", "target_id": room_id})
        assert blocked.status_code == 400
