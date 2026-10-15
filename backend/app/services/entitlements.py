"""EC2 — Feature Entitlement service.

Read-only + check APIs are exposed in EC2. Platform-scoped writes are deferred
to the commercial checkpoint. Tests seed entitlement records directly via
`_upsert_entitlement_for_tests`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.feature_entitlement import FeatureEntitlement


async def list_entitlements(*, tenant_id: str) -> list[dict]:
    cursor = db.feature_entitlements.find({"tenant_id": tenant_id}, {"_id": 0})
    return [serialize_doc(doc) async for doc in cursor]  # type: ignore[misc]


async def get_entitlement(*, tenant_id: str, feature_key: str) -> Optional[dict]:
    doc = await db.feature_entitlements.find_one(
        {"tenant_id": tenant_id, "feature_key": feature_key}, {"_id": 0}
    )
    return serialize_doc(doc)


async def has_entitlement(*, tenant_id: str, feature_key: str) -> bool:
    doc = await get_entitlement(tenant_id=tenant_id, feature_key=feature_key)
    if not doc:
        return False
    if not doc.get("enabled"):
        return False
    exp = doc.get("expires_at")
    if exp:
        try:
            when = datetime.fromisoformat(exp) if isinstance(exp, str) else exp
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if when < datetime.now(timezone.utc):
                return False
        except Exception:
            pass
    quota = doc.get("quota")
    used = doc.get("quota_used") or 0
    if isinstance(quota, int) and used >= quota:
        return False
    return True


async def _upsert_entitlement_for_tests(
    *,
    tenant_id: str,
    feature_key: str,
    enabled: bool = True,
    quota: Optional[int] = None,
    quota_used: Optional[int] = None,
    expires_at: Optional[datetime] = None,
    notes: Optional[str] = None,
) -> dict:
    """Test-only helper. Do NOT expose over HTTP.

    The platform-scoped entitlement write API is deferred to the commercial
    checkpoint; tests seed rows directly.
    """
    existing = await db.feature_entitlements.find_one(
        {"tenant_id": tenant_id, "feature_key": feature_key}, {"_id": 0}
    )
    if existing:
        patch = {
            "enabled": enabled,
            "quota": quota,
            "quota_used": quota_used,
            "expires_at": expires_at.isoformat() if isinstance(expires_at, datetime) else expires_at,
            "notes": notes,
            "updated_at": utc_now().isoformat(),
        }
        await db.feature_entitlements.update_one(
            {"tenant_id": tenant_id, "feature_key": feature_key},
            {"$set": patch},
        )
        doc = await db.feature_entitlements.find_one(
            {"tenant_id": tenant_id, "feature_key": feature_key}, {"_id": 0}
        )
        return serialize_doc(doc)  # type: ignore[return-value]

    ent = FeatureEntitlement(
        tenant_id=tenant_id,
        feature_key=feature_key,
        enabled=enabled,
        quota=quota,
        quota_used=quota_used,
        expires_at=expires_at,
        notes=notes,
    )
    await db.feature_entitlements.insert_one(prepare_for_mongo(ent.model_dump()))
    return serialize_doc(ent.model_dump())  # type: ignore[return-value]
