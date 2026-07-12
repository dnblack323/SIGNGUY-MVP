"""EC8 phase 8e — Equipment service (CRUD + document linking + access report).

Equipment is never hard-deleted (`archive_equipment` sets status="archived")
so historical Training/Certification/Work Order references stay resolvable.
Document linking reuses the existing EC2 `DocumentLink` model via
`services/documents_service.py` — no second file-storage system.
"""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.equipment import Equipment
from . import documents_service
from .activity import record_activity_with_audit

ENTITY_TYPE = "equipment"


class EquipmentError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _sync_certification_required(fields: dict) -> dict:
    """access_policy is the sole source of truth — certification_required is
    always kept in sync, never allowed to drift independently (per Phase 8e
    spec item 10: 'do not infer policy from a loose combination of booleans
    if that creates ambiguity' — so we go the other way: the boolean is
    ALWAYS derived FROM the enum)."""
    if "access_policy" in fields:
        fields["certification_required"] = fields["access_policy"] != "no_required"
    return fields


async def create_equipment(*, tenant_id: str, actor_user_id: str, actor_email: str, **fields: Any) -> dict:
    fields = _sync_certification_required(fields)
    doc = Equipment(tenant_id=tenant_id, created_by=actor_user_id, updated_by=actor_user_id, **fields).model_dump()
    await db.equipment.insert_one(prepare_for_mongo(dict(doc)))
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="equipment_created", entity_type="equipment", entity_id=doc["id"],
        summary=f"Equipment created: {doc['name']}",
    )
    doc.pop("_id", None)
    return serialize_doc(doc)


async def get_equipment(*, tenant_id: str, equipment_id: str) -> dict:
    doc = await db.equipment.find_one({"id": equipment_id, "tenant_id": tenant_id}, {"_id": 0})
    if not doc:
        raise EquipmentError(404, "Equipment not found")
    return serialize_doc(doc)


async def list_equipment(*, tenant_id: str, status: Optional[str] = None, category: Optional[str] = None) -> list[dict]:
    q: dict[str, Any] = {"tenant_id": tenant_id}
    if status:
        q["status"] = status
    if category:
        q["category"] = category
    cur = db.equipment.find(q, {"_id": 0}).sort("name", 1)
    return [serialize_doc(d) async for d in cur]


async def update_equipment(*, tenant_id: str, equipment_id: str, actor_user_id: str, actor_email: str, **fields: Any) -> dict:
    existing = await get_equipment(tenant_id=tenant_id, equipment_id=equipment_id)
    fields = _sync_certification_required(fields)
    fields["updated_by"] = actor_user_id
    fields["updated_at"] = utc_now().isoformat()
    await db.equipment.update_one({"id": equipment_id, "tenant_id": tenant_id}, {"$set": fields})
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="equipment_updated", entity_type="equipment", entity_id=equipment_id,
        summary=f"Equipment updated: {existing['name']}", diff={"before": {k: existing.get(k) for k in fields}, "after": fields},
    )
    return await get_equipment(tenant_id=tenant_id, equipment_id=equipment_id)


async def archive_equipment(*, tenant_id: str, equipment_id: str, actor_user_id: str, actor_email: str) -> dict:
    existing = await get_equipment(tenant_id=tenant_id, equipment_id=equipment_id)
    if existing["status"] == "archived":
        raise EquipmentError(400, "Equipment is already archived")
    await db.equipment.update_one(
        {"id": equipment_id, "tenant_id": tenant_id},
        {"$set": {"status": "archived", "updated_by": actor_user_id, "updated_at": utc_now().isoformat()}},
    )
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="equipment_archived", entity_type="equipment", entity_id=equipment_id,
        summary=f"Equipment archived: {existing['name']}",
    )
    return await get_equipment(tenant_id=tenant_id, equipment_id=equipment_id)


async def link_document(*, tenant_id: str, equipment_id: str, document_id: str, portal_visible: bool, actor_user_id: str) -> dict:
    await get_equipment(tenant_id=tenant_id, equipment_id=equipment_id)  # 404 if missing/cross-tenant
    try:
        return await documents_service.link_document(
            tenant_id=tenant_id, document_id=document_id, entity_type=ENTITY_TYPE, entity_id=equipment_id,
            portal_visible=portal_visible, created_by=actor_user_id,
        )
    except ValueError:
        raise EquipmentError(404, "Document not found")


async def unlink_document(*, tenant_id: str, link_id: str) -> None:
    ok = await documents_service.unlink_document(tenant_id=tenant_id, link_id=link_id)
    if not ok:
        raise EquipmentError(404, "Document link not found")


async def list_documents(*, tenant_id: str, equipment_id: str) -> list[dict]:
    return await documents_service.list_linked_documents(tenant_id=tenant_id, entity_type=ENTITY_TYPE, entity_id=equipment_id)


async def equipment_detail(*, tenant_id: str, equipment_id: str) -> dict:
    """Equipment detail: identity + documents + required Training + certified
    Employees + pending Training + expiring Certifications + activity —
    composes existing Training/Certification services (no duplicate logic)."""
    from . import certification_service, training_service

    equipment = await get_equipment(tenant_id=tenant_id, equipment_id=equipment_id)
    documents = await list_documents(tenant_id=tenant_id, equipment_id=equipment_id)
    required_training = await training_service.list_training_definitions(tenant_id=tenant_id, equipment_id=equipment_id)
    certs = await certification_service.list_certifications(tenant_id=tenant_id, equipment_id=equipment_id)
    pending_assignments = await training_service.list_assignments(
        tenant_id=tenant_id, equipment_id=equipment_id, status_in=["not_started", "in_progress", "pending_signoff"],
    )
    return {
        "equipment": equipment, "documents": documents, "required_training": required_training,
        "certifications": certs, "pending_training": pending_assignments,
        "active_certification_count": sum(1 for c in certs if c["status"] == "certified"),
        "expiring_certification_count": sum(1 for c in certs if c.get("expires_soon")),
    }


async def access_report(*, tenant_id: str) -> list[dict]:
    """Equipment Access Report — reused by `reports_service.py`."""
    from . import certification_service

    equipment_list = await list_equipment(tenant_id=tenant_id)
    rows = []
    for eq in equipment_list:
        certs = await certification_service.list_certifications(tenant_id=tenant_id, equipment_id=eq["id"])
        rows.append({
            "equipment_name": eq["name"], "category": eq["category"], "status": eq["status"],
            "access_policy": eq["access_policy"], "safety_sensitive": eq["safety_sensitive"],
            "certified_employee_count": sum(1 for c in certs if c["status"] == "certified"),
            "expiring_soon_count": sum(1 for c in certs if c.get("expires_soon")),
            "expired_count": sum(1 for c in certs if c["status"] == "expired"),
            "revoked_count": sum(1 for c in certs if c["status"] == "revoked"),
        })
    return rows
