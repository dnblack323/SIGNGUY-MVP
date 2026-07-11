"""EC2 — Feature Entitlement (tenant-readable only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import entitlements as svc

router = APIRouter(prefix="/entitlements", tags=["entitlements"])


@router.get("")
async def list_(user: dict = Depends(require_permission(Perm.SETTINGS_READ))) -> dict:
    items = await svc.list_entitlements(tenant_id=user["tenant_id"])
    return {"items": items, "total": len(items)}


@router.get("/{feature_key}")
async def get_one(feature_key: str, user: dict = Depends(require_permission(Perm.SETTINGS_READ))) -> dict:
    doc = await svc.get_entitlement(tenant_id=user["tenant_id"], feature_key=feature_key)
    if not doc:
        raise HTTPException(status_code=404, detail="Entitlement not found")
    return {"entitlement": doc, "has_access": await svc.has_entitlement(tenant_id=user["tenant_id"], feature_key=feature_key)}
