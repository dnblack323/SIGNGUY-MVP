"""EC8 phase 8e — Equipment router (manager-facing)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import equipment_service
from ..services.equipment_service import EquipmentError

router = APIRouter(prefix="/equipment", tags=["equipment"])


def _raise(e: EquipmentError):
    raise HTTPException(status_code=e.status_code, detail=e.detail)


class EquipmentIn(BaseModel):
    name: str
    category: str = "other"
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    location: Optional[str] = None
    status: str = "active"
    safety_sensitive: bool = False
    access_policy: str = "no_required"
    description: Optional[str] = None
    operating_notes: Optional[str] = None
    safety_notes: Optional[str] = None
    training_requirements: Optional[str] = None
    maintenance_reference: Optional[str] = None


class EquipmentUpdateIn(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None
    safety_sensitive: Optional[bool] = None
    access_policy: Optional[str] = None
    description: Optional[str] = None
    operating_notes: Optional[str] = None
    safety_notes: Optional[str] = None
    training_requirements: Optional[str] = None
    maintenance_reference: Optional[str] = None


@router.get("")
async def list_equipment(status: Optional[str] = None, category: Optional[str] = None,
                          user: dict = Depends(require_permission(Perm.EQUIPMENT_READ))) -> dict:
    return {"items": await equipment_service.list_equipment(tenant_id=user["tenant_id"], status=status, category=category)}


@router.post("", status_code=201)
async def create_equipment(payload: EquipmentIn, user: dict = Depends(require_permission(Perm.EQUIPMENT_MANAGE))) -> dict:
    try:
        return await equipment_service.create_equipment(
            tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"], **payload.model_dump(),
        )
    except EquipmentError as e:
        _raise(e)


@router.get("/access-report")
async def access_report(user: dict = Depends(require_permission(Perm.EQUIPMENT_READ))) -> dict:
    return {"items": await equipment_service.access_report(tenant_id=user["tenant_id"])}


@router.get("/{equipment_id}")
async def get_equipment(equipment_id: str, user: dict = Depends(require_permission(Perm.EQUIPMENT_READ))) -> dict:
    try:
        return await equipment_service.equipment_detail(tenant_id=user["tenant_id"], equipment_id=equipment_id)
    except EquipmentError as e:
        _raise(e)


@router.patch("/{equipment_id}")
async def update_equipment(equipment_id: str, payload: EquipmentUpdateIn, user: dict = Depends(require_permission(Perm.EQUIPMENT_MANAGE))) -> dict:
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates")
    try:
        return await equipment_service.update_equipment(
            tenant_id=user["tenant_id"], equipment_id=equipment_id, actor_user_id=user["id"], actor_email=user["email"], **updates,
        )
    except EquipmentError as e:
        _raise(e)


@router.post("/{equipment_id}/archive")
async def archive_equipment(equipment_id: str, user: dict = Depends(require_permission(Perm.EQUIPMENT_MANAGE))) -> dict:
    try:
        return await equipment_service.archive_equipment(tenant_id=user["tenant_id"], equipment_id=equipment_id, actor_user_id=user["id"], actor_email=user["email"])
    except EquipmentError as e:
        _raise(e)


class LinkDocumentIn(BaseModel):
    document_id: str
    portal_visible: bool = False


@router.post("/{equipment_id}/documents")
async def link_document(equipment_id: str, payload: LinkDocumentIn, user: dict = Depends(require_permission(Perm.EQUIPMENT_MANAGE))) -> dict:
    try:
        return await equipment_service.link_document(
            tenant_id=user["tenant_id"], equipment_id=equipment_id, document_id=payload.document_id,
            portal_visible=payload.portal_visible, actor_user_id=user["id"],
        )
    except EquipmentError as e:
        _raise(e)


@router.delete("/documents/{link_id}")
async def unlink_document(link_id: str, user: dict = Depends(require_permission(Perm.EQUIPMENT_MANAGE))) -> dict:
    try:
        await equipment_service.unlink_document(tenant_id=user["tenant_id"], link_id=link_id)
        return {"ok": True}
    except EquipmentError as e:
        _raise(e)
