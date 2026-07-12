"""EC8 phase 8e — Certification router (manager-facing): issue/renew/revoke/matrix."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import serialize_doc
from ..deps import require_permission
from ..services import certification_service, equipment_service
from ..services.certification_service import CertificationError

router = APIRouter(prefix="/certifications", tags=["certifications"])


def _raise(e: CertificationError):
    raise HTTPException(status_code=e.status_code, detail=e.detail)


class IssueIn(BaseModel):
    employee_id: str
    equipment_id: Optional[str] = None
    certification_type: Optional[str] = None
    source_training_assignment_id: Optional[str] = None
    issued_date: Optional[str] = None
    expiration_date: Optional[str] = None
    trainer_user_id: Optional[str] = None
    required_score: Optional[int] = None
    actual_score: Optional[int] = None
    practical_signoff_result: Optional[str] = None
    restrictions: Optional[str] = None


class RenewIn(BaseModel):
    expiration_date: Optional[str] = None
    source_training_assignment_id: Optional[str] = None
    trainer_user_id: Optional[str] = None
    actual_score: Optional[int] = None


class RevokeIn(BaseModel):
    reason: str


@router.get("")
async def list_certifications(employee_id: Optional[str] = None, equipment_id: Optional[str] = None, status: Optional[str] = None,
                                user: dict = Depends(require_permission(Perm.CERTIFICATION_READ))) -> dict:
    return {"items": await certification_service.list_certifications(tenant_id=user["tenant_id"], employee_id=employee_id, equipment_id=equipment_id, status=status)}


@router.get("/matrix")
async def certification_matrix(user: dict = Depends(require_permission(Perm.CERTIFICATION_READ))) -> dict:
    """Employee x Equipment grid — cell = the most relevant Certification (or none)."""
    employees = [serialize_doc(d) async for d in db.employees.find({"tenant_id": user["tenant_id"], "status": {"$ne": "archived"}}, {"_id": 0})]
    equipment = await equipment_service.list_equipment(tenant_id=user["tenant_id"])
    certs = await certification_service.list_certifications(tenant_id=user["tenant_id"])
    by_cell: dict[tuple, dict] = {}
    for c in certs:
        if not c.get("equipment_id"):
            continue
        key = (c["employee_id"], c["equipment_id"])
        prior = by_cell.get(key)
        if not prior or c["created_at"] > prior["created_at"]:
            by_cell[key] = c
    rows = []
    for emp in employees:
        cells = []
        for eq in equipment:
            cert = by_cell.get((emp["id"], eq["id"]))
            cells.append({
                "equipment_id": eq["id"], "certification": cert,
                "status": certification_service.effective_status(cert) if cert else "missing",
            })
        rows.append({"employee_id": emp["id"], "employee_name": emp["name"], "cells": cells})
    return {"employees": [{"id": e["id"], "name": e["name"]} for e in employees],
            "equipment": [{"id": e["id"], "name": e["name"]} for e in equipment], "rows": rows}


@router.post("", status_code=201)
async def issue(payload: IssueIn, user: dict = Depends(require_permission(Perm.CERTIFICATION_MANAGE))) -> dict:
    try:
        return await certification_service.issue_certification(
            tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"], **payload.model_dump(),
        )
    except CertificationError as e:
        _raise(e)


@router.get("/{certification_id}")
async def get_certification(certification_id: str, user: dict = Depends(require_permission(Perm.CERTIFICATION_READ))) -> dict:
    try:
        return await certification_service.get_certification(tenant_id=user["tenant_id"], certification_id=certification_id)
    except CertificationError as e:
        _raise(e)


@router.post("/{certification_id}/renew")
async def renew(certification_id: str, payload: RenewIn, user: dict = Depends(require_permission(Perm.CERTIFICATION_MANAGE))) -> dict:
    try:
        return await certification_service.renew_certification(
            tenant_id=user["tenant_id"], certification_id=certification_id, actor_user_id=user["id"], actor_email=user["email"], **payload.model_dump(),
        )
    except CertificationError as e:
        _raise(e)


@router.post("/{certification_id}/revoke")
async def revoke(certification_id: str, payload: RevokeIn, user: dict = Depends(require_permission(Perm.CERTIFICATION_MANAGE))) -> dict:
    try:
        return await certification_service.revoke_certification(
            tenant_id=user["tenant_id"], certification_id=certification_id, actor_user_id=user["id"], actor_email=user["email"], reason=payload.reason,
        )
    except CertificationError as e:
        _raise(e)


class SettingsUpdateIn(BaseModel):
    expiring_alert_windows_days: Optional[list[int]] = None


@router.get("/settings/alerts")
async def get_alert_settings(user: dict = Depends(require_permission(Perm.CERTIFICATION_READ))) -> dict:
    return await certification_service.get_certification_settings(tenant_id=user["tenant_id"])


@router.put("/settings/alerts")
async def update_alert_settings(payload: SettingsUpdateIn, user: dict = Depends(require_permission(Perm.CERTIFICATION_MANAGE))) -> dict:
    from ..services import settings as settings_service
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates")
    await settings_service.set_many(tenant_id=user["tenant_id"], namespace="certification", values=updates, updated_by=user["id"])
    return await certification_service.get_certification_settings(tenant_id=user["tenant_id"])
