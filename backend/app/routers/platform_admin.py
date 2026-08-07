"""EC20 Platform Admin, analytics, support, broadcasts, and governance routes."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field, StrictInt

from ..deps import get_current_user
from ..services import platform_admin as svc
from ..services.platform_admin import PlatformAdminError

router = APIRouter(prefix="/platform-admin", tags=["platform-admin"])
public_router = APIRouter(prefix="/platform", tags=["platform"])
analytics_router = APIRouter(tags=["platform-analytics"])


def _raise(exc: PlatformAdminError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


class SuspendIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class ReactivateIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=1000)
    notify_owner: bool = True


class MarkPaidIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=1000)


class DunningThresholdIn(BaseModel):
    threshold: Optional[StrictInt] = Field(default=None, ge=1, le=20)


class ImpersonateIn(BaseModel):
    target_user_id: str = Field(min_length=1)


class ChecklistIn(BaseModel):
    completed: bool
    note: Optional[str] = Field(default=None, max_length=1000)


class AnnouncementIn(BaseModel):
    message: Optional[str] = Field(default=None, max_length=2000)
    severity: str = "info"
    dismissable: bool = True
    expires_at: Optional[str] = None


class MaintenanceIn(BaseModel):
    enabled: bool
    message: Optional[str] = Field(default=None, max_length=1000)


class BroadcastIn(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    html_body: str = Field(min_length=1, max_length=50_000)
    target: Optional[str] = "all_owners"
    tenant_ids: Optional[list[str]] = Field(default=None, max_length=1000)
    test_to: Optional[EmailStr] = None


class AnalyticsEventIn(BaseModel):
    event_type: str
    session_id: str
    visitor_id: str
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    route: Optional[str] = None
    referrer: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Optional[dict] = None


@router.get("/tenants")
async def list_tenants(
    search: Optional[str] = None,
    limit: int = Query(1000, ge=1, le=2000),
    user: dict = Depends(get_current_user),
) -> dict:
    try:
        return await svc.list_tenants(user, search=search, limit=limit)
    except PlatformAdminError as exc:
        _raise(exc)


@router.post("/sample-data/seed")
async def seed_sample_data(user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.seed_sample_data(user)
    except PlatformAdminError as exc:
        _raise(exc)


@router.get("/tenants/{tenant_id}")
async def tenant_detail(tenant_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.tenant_detail(user, tenant_id)
    except PlatformAdminError as exc:
        _raise(exc)


@router.post("/tenants/{tenant_id}/suspend")
async def suspend_tenant(tenant_id: str, payload: SuspendIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.suspend_tenant(user, tenant_id, reason=payload.reason, request=request)
    except PlatformAdminError as exc:
        _raise(exc)


@router.post("/tenants/{tenant_id}/reactivate")
async def reactivate_tenant(tenant_id: str, payload: ReactivateIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.reactivate_tenant(user, tenant_id, note=payload.note, notify_owner=payload.notify_owner, request=request)
    except PlatformAdminError as exc:
        _raise(exc)


@router.post("/tenants/{tenant_id}/mark-paid")
async def mark_paid(tenant_id: str, payload: MarkPaidIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.mark_paid(user, tenant_id, note=payload.note, request=request)
    except PlatformAdminError as exc:
        _raise(exc)


@router.put("/tenants/{tenant_id}/dunning-threshold")
async def set_dunning_threshold(tenant_id: str, payload: DunningThresholdIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.set_dunning_threshold(user, tenant_id, threshold=payload.threshold, request=request)
    except PlatformAdminError as exc:
        _raise(exc)


@router.post("/impersonate")
async def impersonate(payload: ImpersonateIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.start_impersonation(user, target_user_id=payload.target_user_id, request=request)
    except PlatformAdminError as exc:
        _raise(exc)


@router.post("/exit-impersonation")
async def exit_impersonation(request: Request, log_id: Optional[str] = None, user: dict = Depends(get_current_user)) -> dict:
    try:
        if log_id:
            return await svc.end_impersonation(user, log_id=log_id, request=request)
        return await svc.end_current_impersonation(user, request=request)
    except PlatformAdminError as exc:
        _raise(exc)


@router.get("/impersonation-logs")
async def impersonation_logs(tenant_id: Optional[str] = None, limit: int = Query(200, ge=1, le=1000), user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.list_impersonation_logs(user, tenant_id=tenant_id, limit=limit)
    except PlatformAdminError as exc:
        _raise(exc)


@router.post("/impersonation-logs/{log_id}/end")
async def end_impersonation_log(log_id: str, request: Request, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.end_impersonation(user, log_id=log_id, request=request)
    except PlatformAdminError as exc:
        _raise(exc)


@router.get("/tenants/{tenant_id}/checklist")
async def get_checklist(tenant_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.onboarding_checklist(user, tenant_id)
    except PlatformAdminError as exc:
        _raise(exc)


@router.patch("/tenants/{tenant_id}/checklist/{item_id}")
async def update_checklist(tenant_id: str, item_id: str, payload: ChecklistIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.update_onboarding_item(user, tenant_id, item_id, completed=payload.completed, note=payload.note, request=request)
    except PlatformAdminError as exc:
        _raise(exc)


@router.get("/tenants/{tenant_id}/checklist/progress")
async def checklist_progress(tenant_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        result = await svc.onboarding_checklist(user, tenant_id)
        return result["progress"]
    except PlatformAdminError as exc:
        _raise(exc)


@public_router.get("/announcement")
async def public_announcement() -> dict:
    return await svc.public_announcement()


@public_router.get("/maintenance")
async def public_maintenance() -> dict:
    return await svc.public_maintenance()


@router.get("/settings")
async def platform_settings(user: dict = Depends(get_current_user)) -> dict:
    try:
        svc.require_platform_admin(user)
        return await svc.get_platform_settings()
    except PlatformAdminError as exc:
        _raise(exc)


@router.put("/announcement")
async def set_announcement(payload: AnnouncementIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.set_announcement(user, message=payload.message, severity=payload.severity, dismissable=payload.dismissable, expires_at=payload.expires_at, request=request)
    except PlatformAdminError as exc:
        _raise(exc)


@router.put("/maintenance")
async def set_maintenance(payload: MaintenanceIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.set_maintenance(user, enabled=payload.enabled, message=payload.message, request=request)
    except PlatformAdminError as exc:
        _raise(exc)


@router.get("/broadcast-email/audience-counts")
async def broadcast_counts(user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.broadcast_counts(user)
    except PlatformAdminError as exc:
        _raise(exc)


@router.post("/broadcast-email")
async def broadcast_email(payload: BroadcastIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.send_broadcast(
            user,
            subject=payload.subject,
            html_body=payload.html_body,
            target=payload.target or "all_owners",
            tenant_ids=payload.tenant_ids,
            test_to=str(payload.test_to) if payload.test_to else None,
            request=request,
        )
    except PlatformAdminError as exc:
        _raise(exc)


@router.get("/email-logs/summary")
async def email_logs_summary(tenant_id: Optional[str] = None, since: Optional[str] = None, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.email_logs_summary(user, tenant_id=tenant_id, since=since)
    except PlatformAdminError as exc:
        _raise(exc)


@router.get("/email-logs")
async def email_logs(
    tenant_id: Optional[str] = None,
    tenant: Optional[str] = None,
    status: Optional[str] = None,
    to_email: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = Query(200, ge=1, le=500),
    user: dict = Depends(get_current_user),
) -> dict:
    try:
        return await svc.list_email_logs(user, tenant_id=tenant_id or tenant, status=status, to_email=to_email, since=since, limit=limit)
    except PlatformAdminError as exc:
        _raise(exc)


@router.get("/audit-log")
async def audit_log(
    action: Optional[str] = None,
    actor_email: Optional[str] = None,
    tenant_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    limit: int = Query(200, ge=1, le=1000),
    user: dict = Depends(get_current_user),
) -> dict:
    try:
        return await svc.list_audit_log(user, action=action, actor_email=actor_email, tenant_id=tenant_id, entity_type=entity_type, limit=limit)
    except PlatformAdminError as exc:
        _raise(exc)


@router.get("/audit-log/actions")
async def audit_log_actions(user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.audit_actions(user)
    except PlatformAdminError as exc:
        _raise(exc)


@router.get("/audit-log/{entry_id}")
async def audit_log_entry(entry_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.audit_entry(user, entry_id)
    except PlatformAdminError as exc:
        _raise(exc)


@router.get("/analytics")
async def platform_analytics(
    range: str = "30d",
    custom_start: Optional[str] = None,
    custom_end: Optional[str] = None,
    user: dict = Depends(get_current_user),
) -> dict:
    try:
        return await svc.analytics(user, range_key=range, custom_start=custom_start, custom_end=custom_end)
    except PlatformAdminError as exc:
        _raise(exc)


@analytics_router.post("/analytics/event")
async def ingest_analytics(payload: AnalyticsEventIn, request: Request) -> dict:
    try:
        return await svc.ingest_analytics_event(payload.model_dump(exclude_none=True), request=request)
    except PlatformAdminError as exc:
        _raise(exc)
