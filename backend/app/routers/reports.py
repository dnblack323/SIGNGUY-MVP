"""EC7 phase 7d — Curated reports + CSV export + Custom Report Builder router.

Route order matters — `/custom/*` handlers are registered BEFORE the
parameterized `/{key}/*` handlers so FastAPI matches them first.
"""
from __future__ import annotations
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from ..core.permissions import Perm, permissions_for_role
from ..deps import require_permission
from ..services import reports_service, csv_export
from ..services.audit import record_audit

router = APIRouter(prefix="/reports", tags=["reports"])


def _perms_for_user(user: dict) -> set[str]:
    return set(permissions_for_role(user.get("role", "staff")))


class RunReportIn(BaseModel):
    filters: dict[str, Any] = Field(default_factory=dict)
    preview_limit: int = 500


class ExportIn(BaseModel):
    filters: dict[str, Any] = Field(default_factory=dict)


class CustomRunIn(BaseModel):
    dataset: str
    fields: list[str]
    filters: dict[str, Any] = Field(default_factory=dict)
    group_by: list[str] = Field(default_factory=list)
    sort: list[dict[str, Any]] = Field(default_factory=list)
    limit: int = 500


@router.get("")
async def list_reports(user: dict = Depends(require_permission(Perm.REPORT_READ))) -> dict:
    reports = reports_service.list_reports_for_user(_perms_for_user(user))
    datasets = reports_service.list_datasets_for_user(_perms_for_user(user))
    return {"reports": reports, "custom_datasets": datasets}


# --- Custom Report Builder (registered BEFORE parameterized routes) ---
@router.post("/custom/preview")
async def custom_preview(payload: CustomRunIn,
                         user: dict = Depends(require_permission(Perm.REPORT_READ))) -> dict:
    try:
        return await reports_service.run_custom_report(
            dataset_key=payload.dataset, tenant_id=user["tenant_id"],
            user_perms=_perms_for_user(user),
            fields=payload.fields, filters=payload.filters,
            group_by=payload.group_by, sort=payload.sort, limit=payload.limit,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="permission_denied")
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@router.post("/custom/export.csv")
async def custom_export(payload: CustomRunIn,
                         user: dict = Depends(require_permission(Perm.REPORT_READ))) -> Response:
    try:
        result = await reports_service.run_custom_report(
            dataset_key=payload.dataset, tenant_id=user["tenant_id"],
            user_perms=_perms_for_user(user),
            fields=payload.fields, filters=payload.filters,
            group_by=payload.group_by, sort=payload.sort, limit=25000,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="permission_denied")
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    columns = [{"key": f, "label": f, "money": f.endswith("_cents")} for f in payload.fields]
    csv_text = csv_export.build_csv(columns=columns, rows=result["rows"], max_rows=25000)
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"],
        actor_email=user["email"], action="report.custom_export",
        entity_type="report_custom", entity_id=payload.dataset,
        summary=f"Exported custom report ({payload.dataset})",
        diff={"row_count": result["row_count"], "fields": payload.fields,
              "filters": payload.filters},
    )
    return Response(
        content=csv_text, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="custom_{payload.dataset}.csv"'},
    )


# --- Curated reports (parameterized) ---
@router.post("/{key}/run")
async def run_report(key: str, payload: RunReportIn,
                     user: dict = Depends(require_permission(Perm.REPORT_READ))) -> dict:
    try:
        return await reports_service.run_report(
            key=key, tenant_id=user["tenant_id"],
            filters=payload.filters, user_perms=_perms_for_user(user),
            preview_limit=payload.preview_limit,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="permission_denied")
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@router.post("/{key}/export.csv")
async def export_csv(key: str, payload: ExportIn,
                     user: dict = Depends(require_permission(Perm.REPORT_READ))) -> Response:
    try:
        result = await reports_service.run_report(
            key=key, tenant_id=user["tenant_id"],
            filters=payload.filters, user_perms=_perms_for_user(user),
            preview_limit=25000,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="permission_denied")
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    csv_text = csv_export.build_csv(
        columns=result["columns"], rows=result["rows"], max_rows=25000,
    )
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"],
        actor_email=user["email"], action="report.export",
        entity_type="report", entity_id=key,
        summary=f"Exported CSV: {result['title']}",
        diff={"row_count": result["row_count"], "filters": payload.filters},
    )
    safe_key = key.replace(".", "_")
    return Response(
        content=csv_text, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_key}.csv"'},
    )
