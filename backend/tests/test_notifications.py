"""EC2 — Notification service tests (per-user isolation)."""
from __future__ import annotations

import pytest

from app.services import notifications as svc


@pytest.mark.asyncio
async def test_notify_and_list(seeded_users):
    t = seeded_users["tenant_a"]["id"]
    u = seeded_users["user_a"]["id"]
    n = await svc.notify(
        tenant_id=t, recipient_user_id=u, module="orders", kind="order.created",
        title="New order", body="Order #1"
    )
    assert n.status == "unread"
    listed = await svc.list_for_user(tenant_id=t, user_id=u)
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == n.id


@pytest.mark.asyncio
async def test_unread_count_reflects_status(seeded_users):
    t = seeded_users["tenant_a"]["id"]
    u = seeded_users["user_a"]["id"]
    for i in range(3):
        await svc.notify(tenant_id=t, recipient_user_id=u, module="orders", kind="k", title=f"t{i}")
    assert await svc.unread_count(tenant_id=t, user_id=u) == 3

    listed = await svc.list_for_user(tenant_id=t, user_id=u)
    first_id = listed["items"][0]["id"]
    ok = await svc.mark_read(tenant_id=t, user_id=u, notification_id=first_id)
    assert ok
    assert await svc.unread_count(tenant_id=t, user_id=u) == 2


@pytest.mark.asyncio
async def test_dismiss_moves_out_of_unread(seeded_users):
    t = seeded_users["tenant_a"]["id"]
    u = seeded_users["user_a"]["id"]
    n = await svc.notify(tenant_id=t, recipient_user_id=u, module="m", kind="k", title="t")
    ok = await svc.dismiss(tenant_id=t, user_id=u, notification_id=n.id)
    assert ok
    assert await svc.unread_count(tenant_id=t, user_id=u) == 0


@pytest.mark.asyncio
async def test_mark_many_read(seeded_users):
    t = seeded_users["tenant_a"]["id"]
    u = seeded_users["user_a"]["id"]
    ids = []
    for i in range(4):
        n = await svc.notify(tenant_id=t, recipient_user_id=u, module="m", kind="k", title=f"t{i}")
        ids.append(n.id)
    modified = await svc.mark_many_read(tenant_id=t, user_id=u, ids=ids)
    assert modified == 4
    assert await svc.unread_count(tenant_id=t, user_id=u) == 0


@pytest.mark.asyncio
async def test_notifications_isolated_per_user_and_tenant(seeded_users):
    t_a = seeded_users["tenant_a"]["id"]
    t_b = seeded_users["tenant_b"]["id"]
    u_a = seeded_users["user_a"]["id"]
    u_b = seeded_users["user_b"]["id"]
    await svc.notify(tenant_id=t_a, recipient_user_id=u_a, module="m", kind="k", title="A")
    await svc.notify(tenant_id=t_b, recipient_user_id=u_b, module="m", kind="k", title="B")

    # User A cannot see user B's notifications even if they cross tenants
    listed_a = await svc.list_for_user(tenant_id=t_a, user_id=u_a)
    listed_b = await svc.list_for_user(tenant_id=t_b, user_id=u_b)
    assert listed_a["total"] == 1
    assert listed_b["total"] == 1
    assert listed_a["items"][0]["title"] == "A"
    assert listed_b["items"][0]["title"] == "B"

    # Cross-tenant read yields nothing
    cross = await svc.list_for_user(tenant_id=t_a, user_id=u_b)
    assert cross["total"] == 0


@pytest.mark.asyncio
async def test_mark_read_cannot_touch_other_users_row(seeded_users):
    t = seeded_users["tenant_a"]["id"]
    u_a = seeded_users["user_a"]["id"]
    u_b_id = "other-user"  # not owned by u_a
    n = await svc.notify(tenant_id=t, recipient_user_id=u_b_id, module="m", kind="k", title="hers")
    ok = await svc.mark_read(tenant_id=t, user_id=u_a, notification_id=n.id)
    assert ok is False
