"""EC2 — Settings routes.

- GET  /api/settings                     -> all namespaces for tenant
- GET  /api/settings/{namespace}         -> {key: value} for that namespace
- PUT  /api/settings/{namespace}         -> bulk upsert namespace values
- PUT  /api/settings/{namespace}/{key}   -> single-key upsert

Values are typed JSON. Secrets MUST NOT be stored via these routes.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import settings as svc
from ..services.activity import record_activity_with_audit

router = APIRouter(prefix="/settings", tags=["settings"])


_NAMESPACE_ALLOWED = set(svc.KNOWN_NAMESPACES)


def _guard_namespace(ns: str) -> None:
    if ns not in _NAMESPACE_ALLOWED:
        raise HTTPException(status_code=400, detail=f"Unknown settings namespace: {ns}")


@router.get("")
async def get_all(user: dict = Depends(require_permission(Perm.SETTINGS_READ))) -> dict:
    return {"namespaces": await svc.list_all(tenant_id=user["tenant_id"])}


@router.get("/{namespace}")
async def get_namespace(namespace: str, user: dict = Depends(require_permission(Perm.SETTINGS_READ))) -> dict:
    _guard_namespace(namespace)
    return {"namespace": namespace, "values": await svc.list_namespace(tenant_id=user["tenant_id"], namespace=namespace)}


@router.put("/{namespace}")
async def put_namespace(
    namespace: str,
    payload: dict[str, Any] = Body(...),
    user: dict = Depends(require_permission(Perm.SETTINGS_WRITE)),
) -> dict:
    _guard_namespace(namespace)
    values = await svc.set_many(
        tenant_id=user["tenant_id"], namespace=namespace, values=payload, updated_by=user["id"]
    )
    await record_activity_with_audit(
        tenant_id=user["tenant_id"],
        actor_user_id=user["id"],
        actor_email=user["email"],
        module="settings",
        action="settings.update",
        entity_type="settings",
        entity_id=namespace,
        summary=f"Settings updated in namespace '{namespace}' ({len(payload)} keys)",
        diff={"namespace": namespace, "keys": sorted(payload.keys())},
    )
    return {"namespace": namespace, "values": values}


@router.put("/{namespace}/{key}")
async def put_single(
    namespace: str,
    key: str,
    payload: dict[str, Any] = Body(...),
    user: dict = Depends(require_permission(Perm.SETTINGS_WRITE)),
) -> dict:
    _guard_namespace(namespace)
    if "value" not in payload:
        raise HTTPException(status_code=400, detail="Body must include a 'value' field")
    doc = await svc.set_setting(
        tenant_id=user["tenant_id"],
        namespace=namespace,
        key=key,
        value=payload["value"],
        updated_by=user["id"],
    )
    await record_activity_with_audit(
        tenant_id=user["tenant_id"],
        actor_user_id=user["id"],
        actor_email=user["email"],
        module="settings",
        action="settings.update",
        entity_type="settings",
        entity_id=f"{namespace}.{key}",
        summary=f"Setting '{namespace}.{key}' updated",
        diff={"namespace": namespace, "key": key},
    )
    return {"setting": doc}
