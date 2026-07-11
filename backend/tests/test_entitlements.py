"""EC2 — Feature Entitlement service tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services import entitlements as svc


@pytest.mark.asyncio
async def test_no_entitlement_means_no_access(seeded_users):
    t = seeded_users["tenant_a"]["id"]
    assert await svc.has_entitlement(tenant_id=t, feature_key="webstores") is False


@pytest.mark.asyncio
async def test_seeded_entitlement_grants_access(seeded_users):
    t = seeded_users["tenant_a"]["id"]
    await svc._upsert_entitlement_for_tests(tenant_id=t, feature_key="webstores", enabled=True)
    assert await svc.has_entitlement(tenant_id=t, feature_key="webstores") is True


@pytest.mark.asyncio
async def test_disabled_entitlement_is_denied(seeded_users):
    t = seeded_users["tenant_a"]["id"]
    await svc._upsert_entitlement_for_tests(tenant_id=t, feature_key="wrap_lab", enabled=False)
    assert await svc.has_entitlement(tenant_id=t, feature_key="wrap_lab") is False


@pytest.mark.asyncio
async def test_expired_entitlement_is_denied(seeded_users):
    t = seeded_users["tenant_a"]["id"]
    await svc._upsert_entitlement_for_tests(
        tenant_id=t,
        feature_key="ai_credits.pro",
        enabled=True,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    assert await svc.has_entitlement(tenant_id=t, feature_key="ai_credits.pro") is False


@pytest.mark.asyncio
async def test_quota_exhausted_denies(seeded_users):
    t = seeded_users["tenant_a"]["id"]
    await svc._upsert_entitlement_for_tests(
        tenant_id=t, feature_key="ai_credits.pro", enabled=True, quota=10, quota_used=10
    )
    assert await svc.has_entitlement(tenant_id=t, feature_key="ai_credits.pro") is False


@pytest.mark.asyncio
async def test_entitlements_are_tenant_scoped(seeded_users):
    t_a = seeded_users["tenant_a"]["id"]
    t_b = seeded_users["tenant_b"]["id"]
    await svc._upsert_entitlement_for_tests(tenant_id=t_a, feature_key="webstores", enabled=True)
    assert await svc.has_entitlement(tenant_id=t_a, feature_key="webstores") is True
    assert await svc.has_entitlement(tenant_id=t_b, feature_key="webstores") is False

    items_a = await svc.list_entitlements(tenant_id=t_a)
    items_b = await svc.list_entitlements(tenant_id=t_b)
    assert len(items_a) == 1
    assert len(items_b) == 0


@pytest.mark.asyncio
async def test_require_entitlement_dep_rejects_when_absent(seeded_users):
    """require_entitlement returns a callable that raises 402 when not entitled."""
    from fastapi import HTTPException

    from app.deps import require_entitlement

    dep = require_entitlement("wrap_lab")
    t = seeded_users["tenant_a"]["id"]
    user = {"tenant_id": t, "id": "u1"}

    with pytest.raises(HTTPException) as exc:
        await dep(user=user)
    assert exc.value.status_code == 402


@pytest.mark.asyncio
async def test_require_entitlement_dep_passes_when_present(seeded_users):
    from app.deps import require_entitlement

    dep = require_entitlement("webstores")
    t = seeded_users["tenant_a"]["id"]
    user = {"tenant_id": t, "id": "u1"}
    await svc._upsert_entitlement_for_tests(tenant_id=t, feature_key="webstores", enabled=True)

    result = await dep(user=user)
    assert result is user
