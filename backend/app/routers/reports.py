"""Report Catalog and Custom Report Builder API.

The router is intentionally metadata-first. Saved definitions, export history,
and schedule runs are tracked, but report values always come from a fresh
tenant-scoped read through reports_service.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from ..core.db import db
from ..core.permissions import Perm, permissions_for_role
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..deps import require_permission
from ..models.reporting import (
    ReportDefinition,
    ReportExport,
    ReportExportFormat,
    ReportSchedule,
    ReportScheduleRun,
)
from ..services import reports_service
from ..services.audit import record_audit
from ..services.report_export import build_export

router = APIRouter(prefix="/reports", tags=["reports"])

SUPPORTED_EXPORT_FORMATS = {"csv", "xlsx", "pdf", "print"}
SPECIALIZED_EXPORT_FORMATS = {"accounting_csv", "payroll_csv", "tax_csv"}
VALID_DEFINITION_VISIBILITIES = {"private", "shared_users", "shared_roles"}
VALID_SCHEDULE_CADENCES = {"daily", "weekly", "monthly", "pay_period", "event_triggered"}


def _perms_for_user(user: dict) -> set[str]:
    return set(permissions_for_role(user.get("role", "staff")))


def _role_for_user(user: dict) -> str:
    return str(user.get("role") or "staff")


def _definition_access_query(user: dict, *, include_archived: bool = False) -> dict[str, Any]:
    status_filter: Any = {"$ne": "archived"} if not include_archived else {"$in": ["active", "archived"]}
    return {
        "tenant_id": user["tenant_id"],
        "status": status_filter,
        "$or": [
            {"owner_user_id": user["id"]},
            {"shared_user_ids": user["id"]},
            {"shared_role_keys": _role_for_user(user)},
        ],
    }


async def _load_definition(definition_id: str, user: dict, *, include_archived: bool = False) -> dict[str, Any]:
    doc = await db.report_definitions.find_one(
        {"id": definition_id, **_definition_access_query(user, include_archived=include_archived)},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="report_definition_not_found")
    return doc


def _assert_definition_owner(doc: dict[str, Any], user: dict) -> None:
    if doc.get("owner_user_id") == user["id"]:
        return
    raise HTTPException(status_code=403, detail="permission_denied")


def _validate_supported_export_format(export_format: str) -> None:
    if export_format in SUPPORTED_EXPORT_FORMATS:
        return
    if export_format in SPECIALIZED_EXPORT_FORMATS:
        raise HTTPException(status_code=400, detail="specialized_export_not_implemented")
    raise HTTPException(status_code=400, detail="unsupported_export_format")


def _reject_unsupported_builder_features(*, calculated_fields: list[dict[str, Any]] | None = None,
                                         comparisons: list[str] | None = None,
                                         dashboard_widget: dict[str, Any] | None = None) -> None:
    if calculated_fields:
        raise HTTPException(status_code=400, detail="calculated_fields_not_implemented")
    if comparisons:
        raise HTTPException(status_code=400, detail="comparisons_not_implemented")
    if dashboard_widget:
        raise HTTPException(status_code=400, detail="dashboard_widget_publish_not_implemented")


async def _run_definition(doc: dict[str, Any], user: dict, override_filters: dict[str, Any] | None = None, *, limit: int = 500) -> dict[str, Any]:
    filters = {**(doc.get("filters") or {}), **(override_filters or {})}
    try:
        if doc.get("source_kind") == "standard":
            return await reports_service.run_report(
                key=doc["standard_report_key"],
                tenant_id=user["tenant_id"],
                filters=filters,
                user_perms=_perms_for_user(user),
                preview_limit=limit,
            )
        return await reports_service.run_custom_report(
            dataset_key=doc["custom_dataset"],
            tenant_id=user["tenant_id"],
            user_perms=_perms_for_user(user),
            fields=doc.get("fields") or [],
            filters=filters,
            group_by=doc.get("group_by") or [],
            sort=doc.get("sort") or [],
            limit=limit,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="permission_denied")
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


async def _record_export(
    *,
    user: dict,
    result: dict[str, Any],
    export_format: ReportExportFormat,
    report_definition_id: str | None = None,
    standard_report_key: str | None = None,
    custom_dataset: str | None = None,
) -> tuple[bytes, str, str, dict[str, Any]]:
    _validate_supported_export_format(export_format)
    content, content_type, filename = build_export(result=result, export_format=export_format)
    model = ReportExport(
        tenant_id=user["tenant_id"],
        report_definition_id=report_definition_id,
        standard_report_key=standard_report_key,
        custom_dataset=custom_dataset,
        requested_by_user_id=user["id"],
        requested_by_email=user.get("email", ""),
        export_format=export_format,
        status="completed",
        row_count=int(result.get("row_count") or len(result.get("rows") or [])),
        file_name=filename,
        content_type=content_type,
        filters=result.get("filters") or {},
        completed_at=utc_now().isoformat(),
    )
    doc = prepare_for_mongo(model.model_dump())
    await db.report_exports.insert_one(doc)
    await record_audit(
        tenant_id=user["tenant_id"],
        actor_user_id=user["id"],
        actor_email=user.get("email", ""),
        action="report.export",
        entity_type="report_export",
        entity_id=model.id,
        summary=f"Exported report as {export_format}",
        diff={
            "report_definition_id": report_definition_id,
            "standard_report_key": standard_report_key,
            "custom_dataset": custom_dataset,
            "row_count": model.row_count,
            "format": export_format,
        },
    )
    return content, content_type, filename, doc


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


class SaveReportIn(BaseModel):
    name: str
    description: Optional[str] = None
    source_kind: str = "standard"
    standard_report_key: Optional[str] = None
    custom_dataset: Optional[str] = None
    fields: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    group_by: list[str] = Field(default_factory=list)
    sort: list[dict[str, Any]] = Field(default_factory=list)
    calculated_fields: list[dict[str, Any]] = Field(default_factory=list)
    comparisons: list[str] = Field(default_factory=list)
    layout: dict[str, Any] = Field(default_factory=dict)
    export_defaults: dict[str, Any] = Field(default_factory=dict)
    dashboard_widget: Optional[dict[str, Any]] = None
    visibility: str = "private"
    shared_user_ids: list[str] = Field(default_factory=list)
    shared_role_keys: list[str] = Field(default_factory=list)


class UpdateReportIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    visibility: Optional[str] = None
    shared_user_ids: Optional[list[str]] = None
    shared_role_keys: Optional[list[str]] = None
    layout: Optional[dict[str, Any]] = None
    export_defaults: Optional[dict[str, Any]] = None
    dashboard_widget: Optional[dict[str, Any]] = None


class ScheduleIn(BaseModel):
    report_definition_id: str
    cadence: str
    timezone: str = "UTC"
    delivery_time: Optional[str] = None
    delivery_formats: list[ReportExportFormat] = Field(default_factory=lambda: ["csv"])
    recipient_user_ids: list[str] = Field(default_factory=list)
    recipient_emails: list[str] = Field(default_factory=list)
    next_run_at: Optional[str] = None


@router.get("")
async def list_reports(user: dict = Depends(require_permission(Perm.REPORT_READ))) -> dict:
    reports = reports_service.list_reports_for_user(_perms_for_user(user))
    datasets = reports_service.list_datasets_for_user(_perms_for_user(user))
    return {
        "authority": {
            "title": "SIGNGUY AI | REPORT CATALOG & CUSTOM REPORT BUILDER SPEC",
            "pages": 11,
            "location": "Business & Finance -> Reports",
        },
        "official_webstore_types": ["B2B", "Fundraiser", "Event", "Promotional", "General"],
        "reports": reports,
        "custom_datasets": datasets,
        "blocked_requirements": reports_service.BLOCKED_REPORT_REQUIREMENTS,
    }


@router.post("/custom/preview")
async def custom_preview(payload: CustomRunIn, user: dict = Depends(require_permission(Perm.REPORT_READ))) -> dict:
    try:
        return await reports_service.run_custom_report(
            dataset_key=payload.dataset,
            tenant_id=user["tenant_id"],
            user_perms=_perms_for_user(user),
            fields=payload.fields,
            filters=payload.filters,
            group_by=payload.group_by,
            sort=payload.sort,
            limit=payload.limit,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="permission_denied")
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@router.post("/custom/export/{export_format}")
async def custom_export(export_format: ReportExportFormat, payload: CustomRunIn, user: dict = Depends(require_permission(Perm.REPORT_READ))) -> Response:
    result = await custom_preview(payload, user)
    content, content_type, filename, _ = await _record_export(
        user=user,
        result=result,
        export_format=export_format,
        custom_dataset=payload.dataset,
    )
    return Response(content=content, media_type=content_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/custom/export.csv")
async def custom_export_csv(payload: CustomRunIn, user: dict = Depends(require_permission(Perm.REPORT_READ))) -> Response:
    return await custom_export("csv", payload, user)


@router.get("/exports/history")
async def export_history(user: dict = Depends(require_permission(Perm.REPORT_READ))) -> dict:
    rows = []
    async for doc in db.report_exports.find({"tenant_id": user["tenant_id"]}, {"_id": 0}).sort("created_at", -1).limit(100):
        rows.append(serialize_doc(doc))
    return {"exports": rows}


@router.get("/saved")
async def list_saved_reports(user: dict = Depends(require_permission(Perm.REPORT_READ))) -> dict:
    rows = []
    async for doc in db.report_definitions.find(_definition_access_query(user, include_archived=True), {"_id": 0}).sort("updated_at", -1).limit(200):
        rows.append(serialize_doc(doc))
    return {"saved_reports": rows}


@router.post("/saved")
async def create_saved_report(payload: SaveReportIn, user: dict = Depends(require_permission(Perm.REPORT_WRITE))) -> dict:
    if payload.source_kind not in {"standard", "custom"}:
        raise HTTPException(status_code=400, detail="invalid_source_kind")
    if payload.visibility not in VALID_DEFINITION_VISIBILITIES:
        raise HTTPException(status_code=400, detail="invalid_visibility")
    _reject_unsupported_builder_features(
        calculated_fields=payload.calculated_fields,
        comparisons=payload.comparisons,
        dashboard_widget=payload.dashboard_widget,
    )
    if payload.source_kind == "standard":
        if not payload.standard_report_key:
            raise HTTPException(status_code=400, detail="missing_standard_report_key")
        await reports_service.run_report(
            key=payload.standard_report_key,
            tenant_id=user["tenant_id"],
            filters=payload.filters,
            user_perms=_perms_for_user(user),
            preview_limit=1,
        )
    else:
        if not payload.custom_dataset:
            raise HTTPException(status_code=400, detail="missing_custom_dataset")
        await reports_service.run_custom_report(
            dataset_key=payload.custom_dataset,
            tenant_id=user["tenant_id"],
            user_perms=_perms_for_user(user),
            fields=payload.fields,
            filters=payload.filters,
            group_by=payload.group_by,
            sort=payload.sort,
            limit=1,
        )
    model = ReportDefinition(
        tenant_id=user["tenant_id"],
        name=payload.name,
        description=payload.description,
        owner_user_id=user["id"],
        owner_email=user.get("email", ""),
        source_kind=payload.source_kind,  # type: ignore[arg-type]
        standard_report_key=payload.standard_report_key,
        custom_dataset=payload.custom_dataset,
        fields=payload.fields,
        filters=payload.filters,
        group_by=payload.group_by,
        sort=payload.sort,
        calculated_fields=[],
        comparisons=[],
        layout=payload.layout,
        export_defaults=payload.export_defaults,
        dashboard_widget=payload.dashboard_widget,
        visibility=payload.visibility,  # type: ignore[arg-type]
        shared_user_ids=payload.shared_user_ids,
        shared_role_keys=payload.shared_role_keys,
    )
    doc = prepare_for_mongo(model.model_dump())
    await db.report_definitions.insert_one(doc)
    await record_audit(
        tenant_id=user["tenant_id"],
        actor_user_id=user["id"],
        actor_email=user.get("email", ""),
        action="report_definition.create",
        entity_type="report_definition",
        entity_id=model.id,
        summary=f"Created saved report: {model.name}",
        diff={"source_kind": model.source_kind, "standard_report_key": model.standard_report_key, "custom_dataset": model.custom_dataset},
    )
    return {"saved_report": serialize_doc(doc)}


@router.get("/saved/{definition_id}")
async def get_saved_report(definition_id: str, user: dict = Depends(require_permission(Perm.REPORT_READ))) -> dict:
    doc = await _load_definition(definition_id, user, include_archived=True)
    return {"saved_report": serialize_doc(doc)}


@router.patch("/saved/{definition_id}")
async def update_saved_report(definition_id: str, payload: UpdateReportIn, user: dict = Depends(require_permission(Perm.REPORT_WRITE))) -> dict:
    doc = await _load_definition(definition_id, user, include_archived=True)
    _assert_definition_owner(doc, user)
    update = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    if "visibility" in update and update["visibility"] not in VALID_DEFINITION_VISIBILITIES:
        raise HTTPException(status_code=400, detail="invalid_visibility")
    if update.get("dashboard_widget"):
        raise HTTPException(status_code=400, detail="dashboard_widget_publish_not_implemented")
    if not update:
        return {"saved_report": serialize_doc(doc)}
    update["updated_at"] = utc_now().isoformat()
    await db.report_definitions.update_one({"id": definition_id, "tenant_id": user["tenant_id"]}, {"$set": update})
    out = await db.report_definitions.find_one({"id": definition_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    return {"saved_report": serialize_doc(out)}


@router.post("/saved/{definition_id}/duplicate")
async def duplicate_saved_report(definition_id: str, user: dict = Depends(require_permission(Perm.REPORT_WRITE))) -> dict:
    doc = await _load_definition(definition_id, user, include_archived=True)
    clone = dict(doc)
    clone.pop("_id", None)
    now = utc_now().isoformat()
    out = {
        **clone,
        "id": str(uuid.uuid4()),
        "tenant_id": user["tenant_id"],
        "name": f"{doc.get('name')} Copy",
        "owner_user_id": user["id"],
        "owner_email": user.get("email", ""),
        "parent_definition_id": definition_id,
        "status": "active",
        "archived_at": None,
        "created_at": now,
        "updated_at": now,
    }
    await db.report_definitions.insert_one(out)
    return {"saved_report": serialize_doc(out)}


@router.post("/saved/{definition_id}/archive")
async def archive_saved_report(definition_id: str, user: dict = Depends(require_permission(Perm.REPORT_WRITE))) -> dict:
    doc = await _load_definition(definition_id, user, include_archived=True)
    _assert_definition_owner(doc, user)
    await db.report_definitions.update_one(
        {"id": definition_id, "tenant_id": user["tenant_id"]},
        {"$set": {"status": "archived", "archived_at": utc_now().isoformat(), "updated_at": utc_now().isoformat()}},
    )
    return {"status": "archived"}


@router.post("/saved/{definition_id}/restore")
async def restore_saved_report(definition_id: str, user: dict = Depends(require_permission(Perm.REPORT_WRITE))) -> dict:
    doc = await _load_definition(definition_id, user, include_archived=True)
    _assert_definition_owner(doc, user)
    await db.report_definitions.update_one(
        {"id": definition_id, "tenant_id": user["tenant_id"]},
        {"$set": {"status": "active", "archived_at": None, "updated_at": utc_now().isoformat()}},
    )
    return {"status": "active"}


@router.post("/saved/{definition_id}/run")
async def run_saved_report(definition_id: str, payload: RunReportIn, user: dict = Depends(require_permission(Perm.REPORT_READ))) -> dict:
    doc = await _load_definition(definition_id, user)
    return await _run_definition(doc, user, payload.filters, limit=payload.preview_limit)


@router.post("/saved/{definition_id}/export/{export_format}")
async def export_saved_report(definition_id: str, export_format: ReportExportFormat, payload: ExportIn, user: dict = Depends(require_permission(Perm.REPORT_READ))) -> Response:
    doc = await _load_definition(definition_id, user)
    result = await _run_definition(doc, user, payload.filters, limit=25000)
    content, content_type, filename, _ = await _record_export(
        user=user,
        result=result,
        export_format=export_format,
        report_definition_id=definition_id,
        standard_report_key=doc.get("standard_report_key"),
        custom_dataset=doc.get("custom_dataset"),
    )
    return Response(content=content, media_type=content_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/schedules")
async def list_schedules(user: dict = Depends(require_permission(Perm.REPORT_READ))) -> dict:
    rows = []
    async for doc in db.report_schedules.find({"tenant_id": user["tenant_id"], "status": {"$ne": "archived"}}, {"_id": 0}).sort("created_at", -1).limit(100):
        rows.append(serialize_doc(doc))
    return {"schedules": rows}


@router.post("/schedules")
async def create_schedule(payload: ScheduleIn, user: dict = Depends(require_permission(Perm.REPORT_WRITE))) -> dict:
    if payload.cadence not in VALID_SCHEDULE_CADENCES:
        raise HTTPException(status_code=400, detail="invalid_schedule_cadence")
    for fmt in payload.delivery_formats:
        _validate_supported_export_format(fmt)
    await _load_definition(payload.report_definition_id, user)
    model = ReportSchedule(
        tenant_id=user["tenant_id"],
        report_definition_id=payload.report_definition_id,
        owner_user_id=user["id"],
        owner_email=user.get("email", ""),
        cadence=payload.cadence,  # type: ignore[arg-type]
        timezone=payload.timezone,
        delivery_time=payload.delivery_time,
        delivery_formats=payload.delivery_formats,
        recipient_user_ids=payload.recipient_user_ids,
        recipient_emails=payload.recipient_emails,
        next_run_at=payload.next_run_at,
    )
    doc = prepare_for_mongo(model.model_dump())
    await db.report_schedules.insert_one(doc)
    return {"schedule": serialize_doc(doc)}


@router.post("/schedules/{schedule_id}/run")
async def run_schedule(schedule_id: str, user: dict = Depends(require_permission(Perm.REPORT_WRITE))) -> dict:
    schedule = await db.report_schedules.find_one({"id": schedule_id, "tenant_id": user["tenant_id"], "status": {"$ne": "archived"}}, {"_id": 0})
    if not schedule:
        raise HTTPException(status_code=404, detail="schedule_not_found")
    existing_run = await db.report_schedule_runs.find_one(
        {"tenant_id": user["tenant_id"], "schedule_id": schedule_id, "status": "running"},
        {"_id": 0, "id": 1},
    )
    if existing_run:
        raise HTTPException(status_code=409, detail="schedule_run_already_running")
    definition = await _load_definition(schedule["report_definition_id"], user)
    started = utc_now().isoformat()
    run = ReportScheduleRun(
        tenant_id=user["tenant_id"],
        schedule_id=schedule_id,
        report_definition_id=schedule["report_definition_id"],
        started_at=started,
        status="running",
        permissions_revalidated=True,
    )
    run_doc = prepare_for_mongo(run.model_dump())
    await db.report_schedule_runs.insert_one(run_doc)
    export_ids: list[str] = []
    try:
        result = await _run_definition(definition, user, {}, limit=25000)
        for fmt in schedule.get("delivery_formats") or ["csv"]:
            _, _, _, export_doc = await _record_export(
                user=user,
                result=result,
                export_format=fmt,
                report_definition_id=schedule["report_definition_id"],
                standard_report_key=definition.get("standard_report_key"),
                custom_dataset=definition.get("custom_dataset"),
            )
            export_ids.append(export_doc["id"])
        await db.report_schedule_runs.update_one(
            {"id": run.id, "tenant_id": user["tenant_id"]},
            {"$set": {"status": "succeeded", "finished_at": utc_now().isoformat(), "export_ids": export_ids}},
        )
        await db.report_schedules.update_one(
            {"id": schedule_id, "tenant_id": user["tenant_id"]},
            {"$set": {"last_run_at": started, "updated_at": utc_now().isoformat()}},
        )
        out = await db.report_schedule_runs.find_one({"id": run.id, "tenant_id": user["tenant_id"]}, {"_id": 0})
        return {"schedule_run": serialize_doc(out)}
    except Exception as ex:
        await db.report_schedule_runs.update_one(
            {"id": run.id, "tenant_id": user["tenant_id"]},
            {"$set": {"status": "failed", "finished_at": utc_now().isoformat(), "failure_reason": str(ex)}},
        )
        raise


@router.post("/schedules/{schedule_id}/archive")
async def archive_schedule(schedule_id: str, user: dict = Depends(require_permission(Perm.REPORT_WRITE))) -> dict:
    result = await db.report_schedules.update_one(
        {"id": schedule_id, "tenant_id": user["tenant_id"]},
        {"$set": {"status": "archived", "updated_at": utc_now().isoformat()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="schedule_not_found")
    return {"status": "archived"}


@router.post("/{key}/run")
async def run_report(key: str, payload: RunReportIn, user: dict = Depends(require_permission(Perm.REPORT_READ))) -> dict:
    try:
        return await reports_service.run_report(
            key=key,
            tenant_id=user["tenant_id"],
            filters=payload.filters,
            user_perms=_perms_for_user(user),
            preview_limit=payload.preview_limit,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="permission_denied")
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@router.post("/{key}/export/{export_format}")
async def export_report(key: str, export_format: ReportExportFormat, payload: ExportIn, user: dict = Depends(require_permission(Perm.REPORT_READ))) -> Response:
    try:
        result = await reports_service.run_report(
            key=key,
            tenant_id=user["tenant_id"],
            filters=payload.filters,
            user_perms=_perms_for_user(user),
            preview_limit=25000,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="permission_denied")
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    content, content_type, filename, _ = await _record_export(
        user=user,
        result=result,
        export_format=export_format,
        standard_report_key=key,
    )
    return Response(content=content, media_type=content_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/{key}/export.csv")
async def export_csv(key: str, payload: ExportIn, user: dict = Depends(require_permission(Perm.REPORT_READ))) -> Response:
    return await export_report(key, "csv", payload, user)
