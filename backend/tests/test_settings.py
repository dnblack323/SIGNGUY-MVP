"""EC2 — Settings service + router tests."""
from __future__ import annotations

import pytest

from app.services import settings as svc


@pytest.mark.asyncio
async def test_set_and_get_setting(seeded_users):
    tenant_id = seeded_users["tenant_a"]["id"]
    doc = await svc.set_setting(
        tenant_id=tenant_id,
        namespace="company_profile",
        key="phone",
        value="555-1212",
        updated_by="u1",
    )
    assert doc["value"] == "555-1212"
    assert doc["value_type"] == "string"

    fetched = await svc.get_setting(tenant_id=tenant_id, namespace="company_profile", key="phone")
    assert fetched is not None
    assert fetched["value"] == "555-1212"


@pytest.mark.asyncio
async def test_set_setting_upserts(seeded_users):
    tenant_id = seeded_users["tenant_a"]["id"]
    await svc.set_setting(tenant_id=tenant_id, namespace="company_profile", key="phone", value="v1")
    doc = await svc.set_setting(tenant_id=tenant_id, namespace="company_profile", key="phone", value="v2")
    assert doc["value"] == "v2"

    ns = await svc.list_namespace(tenant_id=tenant_id, namespace="company_profile")
    assert ns == {"phone": "v2"}


@pytest.mark.asyncio
async def test_set_many_bulk_upsert(seeded_users):
    tenant_id = seeded_users["tenant_a"]["id"]
    result = await svc.set_many(
        tenant_id=tenant_id,
        namespace="branding",
        values={"primary_color": "#123456", "email_signature": "Cheers"},
    )
    assert result == {"primary_color": "#123456", "email_signature": "Cheers"}


@pytest.mark.asyncio
async def test_list_all_groups_by_namespace(seeded_users):
    tenant_id = seeded_users["tenant_a"]["id"]
    await svc.set_setting(tenant_id=tenant_id, namespace="branding", key="primary_color", value="#abc")
    await svc.set_setting(tenant_id=tenant_id, namespace="company_profile", key="phone", value="555")
    all_ns = await svc.list_all(tenant_id=tenant_id)
    assert "branding" in all_ns
    assert all_ns["branding"]["primary_color"] == "#abc"
    assert all_ns["company_profile"]["phone"] == "555"


@pytest.mark.asyncio
async def test_settings_are_tenant_isolated(seeded_users):
    t_a = seeded_users["tenant_a"]["id"]
    t_b = seeded_users["tenant_b"]["id"]
    await svc.set_setting(tenant_id=t_a, namespace="branding", key="primary_color", value="#aaaaaa")
    await svc.set_setting(tenant_id=t_b, namespace="branding", key="primary_color", value="#bbbbbb")

    ns_a = await svc.list_namespace(tenant_id=t_a, namespace="branding")
    ns_b = await svc.list_namespace(tenant_id=t_b, namespace="branding")
    assert ns_a == {"primary_color": "#aaaaaa"}
    assert ns_b == {"primary_color": "#bbbbbb"}


@pytest.mark.asyncio
async def test_value_type_inference(seeded_users):
    tenant_id = seeded_users["tenant_a"]["id"]
    d1 = await svc.set_setting(tenant_id=tenant_id, namespace="notifications", key="enabled", value=True)
    d2 = await svc.set_setting(tenant_id=tenant_id, namespace="notifications", key="threshold", value=5)
    d3 = await svc.set_setting(tenant_id=tenant_id, namespace="notifications", key="rules", value={"a": 1})
    assert d1["value_type"] == "bool"
    assert d2["value_type"] == "int"
    assert d3["value_type"] == "json"
