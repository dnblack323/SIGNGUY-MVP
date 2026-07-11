"""EC2 — Feature Entitlement.

Records that a tenant is entitled to a named feature (e.g. "webstores",
"wrap_lab", "ai_credits.pro"). Includes an optional quota + expiry so the
same shape can carry subscription-driven usage limits.

The platform-scoped WRITE API is deferred to the commercial/platform
checkpoint per the owner-approved plan. In EC2 only the tenant-scoped
READ endpoint + the `require_entitlement` dependency are exposed.
Tests seed entitlements directly via the database.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from .base import BaseDoc


class FeatureEntitlement(BaseDoc):
    tenant_id: str
    feature_key: str            # canonical key (dot-separated ok, e.g. "ai_credits.pro")
    enabled: bool = True
    quota: Optional[int] = None   # optional numeric quota; None = unlimited
    quota_used: Optional[int] = None
    expires_at: Optional[datetime] = None
    granted_by: Optional[str] = None  # platform actor / subscription id
    notes: Optional[str] = None
