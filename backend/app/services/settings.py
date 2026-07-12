"""EC2 — Tenant Settings service (namespace + key store).

Provides get/list/set/merge operations on the `settings` collection.
All operations are tenant-scoped. Secrets are prohibited by convention —
integration status/keys go through `integration_status.py`, not here.
"""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.settings import Setting

# Reserved namespaces — used to fence off well-known configuration slices.
KNOWN_NAMESPACES: tuple[str, ...] = (
    "company_profile",
    "invoicing_defaults",
    "branding",
    "portal",
    "sales_tax",
    "notifications",
    "documents",
    "payroll",
)


def _infer_value_type(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, (dict, list)):
        return "json"
    return "string"


async def get_setting(*, tenant_id: str, namespace: str, key: str) -> Optional[dict]:
    doc = await db.settings.find_one(
        {"tenant_id": tenant_id, "namespace": namespace, "key": key},
        {"_id": 0},
    )
    return serialize_doc(doc)


async def list_namespace(*, tenant_id: str, namespace: str) -> dict[str, Any]:
    """Return {key: value} map for a namespace."""
    cursor = db.settings.find(
        {"tenant_id": tenant_id, "namespace": namespace},
        {"_id": 0, "key": 1, "value": 1},
    )
    return {doc["key"]: doc.get("value") async for doc in cursor}


async def list_all(*, tenant_id: str) -> dict[str, dict[str, Any]]:
    """Return {namespace: {key: value}}."""
    out: dict[str, dict[str, Any]] = {}
    cursor = db.settings.find(
        {"tenant_id": tenant_id},
        {"_id": 0, "namespace": 1, "key": 1, "value": 1},
    )
    async for doc in cursor:
        ns = doc["namespace"]
        out.setdefault(ns, {})[doc["key"]] = doc.get("value")
    return out


async def set_setting(
    *,
    tenant_id: str,
    namespace: str,
    key: str,
    value: Any,
    updated_by: Optional[str] = None,
) -> dict:
    """Upsert a single (namespace, key) value. Returns the persisted document."""
    now = utc_now()
    existing = await db.settings.find_one(
        {"tenant_id": tenant_id, "namespace": namespace, "key": key},
        {"_id": 0},
    )
    if existing:
        await db.settings.update_one(
            {"tenant_id": tenant_id, "namespace": namespace, "key": key},
            {
                "$set": {
                    "value": value,
                    "value_type": _infer_value_type(value),
                    "updated_by": updated_by,
                    "updated_at": now.isoformat(),
                }
            },
        )
        doc = await db.settings.find_one(
            {"tenant_id": tenant_id, "namespace": namespace, "key": key}, {"_id": 0}
        )
        return serialize_doc(doc)  # type: ignore[return-value]

    setting = Setting(
        tenant_id=tenant_id,
        namespace=namespace,
        key=key,
        value=value,
        value_type=_infer_value_type(value),
        updated_by=updated_by,
    )
    await db.settings.insert_one(prepare_for_mongo(setting.model_dump()))
    return serialize_doc(setting.model_dump())  # type: ignore[return-value]


async def set_many(
    *,
    tenant_id: str,
    namespace: str,
    values: dict[str, Any],
    updated_by: Optional[str] = None,
) -> dict[str, Any]:
    """Bulk-upsert all (key -> value) pairs for a namespace."""
    for k, v in values.items():
        await set_setting(
            tenant_id=tenant_id,
            namespace=namespace,
            key=k,
            value=v,
            updated_by=updated_by,
        )
    return await list_namespace(tenant_id=tenant_id, namespace=namespace)
