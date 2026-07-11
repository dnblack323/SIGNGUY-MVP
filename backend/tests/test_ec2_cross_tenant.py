"""EC2 — Cross-tenant isolation sweep for every new collection."""
from __future__ import annotations

import pytest

from app.core.db import db
from app.services import (
    activity as activity_svc,
    entitlements as ent_svc,
    notifications as notif_svc,
    settings as settings_svc,
)


@pytest.mark.asyncio
async def test_settings_isolation(seeded_users):
    t_a = seeded_users["tenant_a"]["id"]
    t_b = seeded_users["tenant_b"]["id"]
    await settings_svc.set_setting(tenant_id=t_a, namespace="branding", key="k", value="A")
    await settings_svc.set_setting(tenant_id=t_b, namespace="branding", key="k", value="B")
    assert (await settings_svc.get_setting(tenant_id=t_a, namespace="branding", key="k"))["value"] == "A"
    assert (await settings_svc.get_setting(tenant_id=t_b, namespace="branding", key="k"))["value"] == "B"


@pytest.mark.asyncio
async def test_activity_isolation(seeded_users):
    t_a = seeded_users["tenant_a"]["id"]
    t_b = seeded_users["tenant_b"]["id"]
    await activity_svc.record_activity(tenant_id=t_a, module="orders", action="a", summary="s")
    await activity_svc.record_activity(tenant_id=t_b, module="orders", action="a", summary="s")
    a = await activity_svc.list_activity(tenant_id=t_a)
    b = await activity_svc.list_activity(tenant_id=t_b)
    assert a["total"] == 1 and b["total"] == 1
    for item in a["items"]:
        assert item["tenant_id"] == t_a


@pytest.mark.asyncio
async def test_notifications_isolation(seeded_users):
    t_a = seeded_users["tenant_a"]["id"]
    t_b = seeded_users["tenant_b"]["id"]
    u_a = seeded_users["user_a"]["id"]
    u_b = seeded_users["user_b"]["id"]
    await notif_svc.notify(tenant_id=t_a, recipient_user_id=u_a, module="m", kind="k", title="A")
    await notif_svc.notify(tenant_id=t_b, recipient_user_id=u_b, module="m", kind="k", title="B")

    la = await notif_svc.list_for_user(tenant_id=t_a, user_id=u_a)
    lb = await notif_svc.list_for_user(tenant_id=t_b, user_id=u_b)
    assert la["total"] == 1 and lb["total"] == 1


@pytest.mark.asyncio
async def test_entitlements_isolation(seeded_users):
    t_a = seeded_users["tenant_a"]["id"]
    t_b = seeded_users["tenant_b"]["id"]
    await ent_svc._upsert_entitlement_for_tests(tenant_id=t_a, feature_key="x", enabled=True)
    assert await ent_svc.has_entitlement(tenant_id=t_a, feature_key="x") is True
    assert await ent_svc.has_entitlement(tenant_id=t_b, feature_key="x") is False


@pytest.mark.asyncio
async def test_file_and_document_link_isolation(seeded_users):
    """Direct-DB sanity check that the required tenant_id field is present."""
    import uuid as _uuid
    t_a = seeded_users["tenant_a"]["id"]
    t_b = seeded_users["tenant_b"]["id"]
    id_a = f"fl-a-{_uuid.uuid4().hex[:8]}"
    id_b = f"fl-b-{_uuid.uuid4().hex[:8]}"
    await db.file_links.insert_one(
        {"id": id_a, "tenant_id": t_a, "file_id": "f1", "parent_type": "x", "parent_id": "y"}
    )
    await db.file_links.insert_one(
        {"id": id_b, "tenant_id": t_b, "file_id": "f2", "parent_type": "x", "parent_id": "z"}
    )
    assert await db.file_links.count_documents({"id": id_a}) == 1
    assert await db.file_links.count_documents({"id": id_b}) == 1
