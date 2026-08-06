"""EC20 platform admin service.

Adapts the original platform-admin workflows to the MVP data model:
PlatformPerm enforcement, shared audit_events, EC13 billing state, EC19
onboarding task state, and EC2 email observability.
"""
from __future__ import annotations

import html
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException, Request

from ..core.config import get_settings
from ..core.db import db
from ..core.permissions import PlatformPerm, has_platform_admin_access
from ..core.security import create_access_token
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.email import EmailLog
from ..models.tenant_billing import TenantBillingAccount
from .audit import record_audit
from .email import is_configured as email_configured, record_processed_activity, send_email

SETTINGS_ID = "global"
BROADCAST_HOURLY_CAP_TENANTS = 10
BROADCAST_HOURLY_CAP_TESTS = 30
BROADCAST_PLACEHOLDERS = ("tenant_name", "owner_email", "owner_first_name")


class PlatformAdminError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def require_platform_admin(user: dict, *, extra_permissions: set[str] | None = None) -> None:
    if not has_platform_admin_access(user, extra_permissions=extra_permissions):
        raise PlatformAdminError("platform_admin_required", "Platform Admin access is required", 403)


def _now_iso() -> str:
    return utc_now().isoformat()


def _request_meta(request: Request | None) -> dict[str, Any]:
    if not request:
        return {}
    forwarded_for = request.headers.get("x-forwarded-for") if request.headers else None
    ip = forwarded_for.split(",")[0].strip() if forwarded_for else (request.client.host if request.client else None)
    return {"ip_address": ip, "user_agent": request.headers.get("user-agent") if request.headers else None}


async def _audit(
    user: dict,
    *,
    tenant_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    summary: str,
    request: Request | None = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict:
    diff = {"metadata": metadata or {}, **_request_meta(request)}
    evt = await record_audit(
        tenant_id=tenant_id,
        actor_user_id=user["id"],
        actor_email=user.get("email", "platform"),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        diff=diff,
    )
    return serialize_doc(evt.model_dump())


async def _owner_for_tenant(tenant_id: str) -> dict | None:
    return await db.users.find_one(
        {"tenant_id": tenant_id, "role": "owner", "is_active": True},
        {"_id": 0, "password_hash": 0},
        sort=[("created_at", 1)],
    )


async def _tenant_name(tenant_id: str) -> str:
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0, "name": 1})
    return (tenant or {}).get("name") or tenant_id


async def _has_platform_user(tenant_id: str) -> bool:
    return await db.users.count_documents({
        "tenant_id": tenant_id,
        "$or": [
            {"platform_admin": True},
            {"platform_role": {"$in": ["PLATFORM_ADMIN", "PLATFORM_CREATOR", "admin", "owner"]}},
            {"permissions": {"$in": [PlatformPerm.PLATFORM_ADMIN.value, PlatformPerm.PLATFORM_CREATOR.value]}},
        ],
    }) > 0


async def _subscription_for_tenant(tenant_id: str) -> dict | None:
    account = await db.tenant_billing_accounts.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if account and account.get("current_subscription_id"):
        sub = await db.tenant_subscriptions.find_one({"tenant_id": tenant_id, "id": account["current_subscription_id"]}, {"_id": 0})
    else:
        sub = await db.tenant_subscriptions.find_one({"tenant_id": tenant_id}, {"_id": 0}, sort=[("updated_at", -1)])
    if sub:
        sub = serialize_doc(sub)
    return {"account": serialize_doc(account), "subscription": sub}


async def _founder_flag(tenant_id: str) -> bool:
    if await db.founder_tenant_contracts.count_documents({"tenant_id": tenant_id, "founder_status": {"$in": ["pending", "active", "grace"]}}):
        return True
    return await db.users.count_documents({"tenant_id": tenant_id, "is_founder": True}) > 0


async def list_tenants(user: dict, *, search: Optional[str] = None, limit: int = 1000) -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_TENANT_READ.value})
    query: dict[str, Any] = {}
    if search:
        owners = await db.users.distinct("tenant_id", {"email": {"$regex": search, "$options": "i"}})
        query = {"$or": [{"name": {"$regex": search, "$options": "i"}}, {"slug": {"$regex": search, "$options": "i"}}, {"id": {"$in": owners}}]}
    docs = await db.tenants.find(query, {"_id": 0}).sort("created_at", -1).limit(max(1, min(limit, 2000))).to_list(None)
    items = []
    for tenant in docs:
        owner = await _owner_for_tenant(tenant["id"])
        billing = await _subscription_for_tenant(tenant["id"])
        items.append({
            "id": tenant["id"],
            "name": tenant.get("name") or "Unnamed Shop",
            "slug": tenant.get("slug"),
            "owner_email": tenant.get("owner_email") or (owner or {}).get("email"),
            "plan": (billing.get("subscription") or {}).get("plan_product_id") or tenant.get("plan") or "unassigned",
            "status": "suspended" if tenant.get("is_active") is False else ((billing.get("account") or {}).get("status") or "active"),
            "is_active": tenant.get("is_active", True),
            "created_at": tenant.get("created_at"),
            "user_count": await db.users.count_documents({"tenant_id": tenant["id"]}),
            "is_founder": await _founder_flag(tenant["id"]),
        })
    return {"items": items, "total": len(items)}


async def tenant_detail(user: dict, tenant_id: str) -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_TENANT_READ.value})
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise PlatformAdminError("tenant_not_found", "Tenant not found", 404)
    users = await db.users.find({"tenant_id": tenant_id}, {"_id": 0, "password_hash": 0}).sort("created_at", 1).to_list(1000)
    owner = next((u for u in users if u.get("role") == "owner"), None) or (users[0] if users else None)
    billing = await _subscription_for_tenant(tenant_id)
    email_summary = await email_logs_summary(user, tenant_id=tenant_id)
    onboarding = await onboarding_checklist(user, tenant_id)
    tenant_out = serialize_doc(tenant)
    tenant_out.update({
        "owner_email": tenant.get("owner_email") or (owner or {}).get("email"),
        "plan": (billing.get("subscription") or {}).get("plan_product_id") or tenant.get("plan") or "unassigned",
        "status": "suspended" if tenant.get("is_active") is False else ((billing.get("account") or {}).get("status") or "active"),
        "is_founder": await _founder_flag(tenant_id),
        "last_activity_at": await _last_activity_for_tenant(tenant_id, tenant),
    })
    return {
        "tenant": tenant_out,
        "users": [serialize_doc(u) for u in users],
        "billing": billing,
        "email_summary": email_summary,
        "onboarding": onboarding,
    }


async def suspend_tenant(user: dict, tenant_id: str, *, reason: str, request: Request | None = None) -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_TENANT_STATUS.value})
    clean_reason = (reason or "").strip()
    if not clean_reason:
        raise PlatformAdminError("reason_required", "Suspension requires a reason", 400)
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise PlatformAdminError("tenant_not_found", "Tenant not found", 404)
    if await _has_platform_user(tenant_id):
        raise PlatformAdminError("platform_tenant_protected", "Cannot suspend a tenant that contains a platform admin user", 400)
    now = _now_iso()
    patch = {
        "is_active": False,
        "suspension_reason": clean_reason,
        "suspended_at": now,
        "suspended_by": user["id"],
        "suspended_by_email": user.get("email"),
        "reactivated_at": None,
        "reactivated_by": None,
        "reactivated_by_email": None,
        "updated_at": now,
    }
    await db.tenants.update_one({"id": tenant_id}, {"$set": patch})
    await db.tenant_billing_accounts.update_one(
        {"tenant_id": tenant_id},
        {"$set": {"status": "suspended", "suspended_at": now, "suspension_reason": clean_reason, "updated_at": now}},
    )
    await _audit(user, tenant_id=tenant_id, action="tenant.suspend", entity_type="tenant", entity_id=tenant_id, summary=f"Suspended tenant {tenant.get('name')}", request=request, metadata={"reason": clean_reason})
    return await tenant_detail(user, tenant_id)


async def reactivate_tenant(user: dict, tenant_id: str, *, note: Optional[str] = None, notify_owner: bool = True, request: Request | None = None) -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_TENANT_STATUS.value})
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise PlatformAdminError("tenant_not_found", "Tenant not found", 404)
    now = _now_iso()
    patch = {
        "is_active": True,
        "suspension_reason": None,
        "suspended_at": None,
        "suspended_by": None,
        "suspended_by_email": None,
        "reactivated_at": now,
        "reactivated_by": user["id"],
        "reactivated_by_email": user.get("email"),
        "updated_at": now,
    }
    await db.tenants.update_one({"id": tenant_id}, {"$set": patch})
    await db.tenant_billing_accounts.update_one(
        {"tenant_id": tenant_id},
        {"$set": {"status": "active", "suspended_at": None, "suspension_reason": None, "updated_at": now}},
    )
    email_status = None
    if notify_owner:
        owner = await _owner_for_tenant(tenant_id)
        if owner and owner.get("email") and email_configured():
            body = f"Your {tenant.get('name') or 'SignGuy AI'} account is active again."
            if note:
                body += f"\n\nNote from SignGuy AI:\n{note.strip()}"
            ok, msg_id, err = send_email(to_email=owner["email"], subject=f"Your {tenant.get('name') or 'SignGuy AI'} account is active again", body_text=body, body_html=f"<p>{html.escape(body).replace(chr(10), '<br />')}</p>")
            email_status = {"ok": ok, "error": err}
            if ok or err:
                await _insert_email_log(tenant_id=tenant_id, to_email=owner["email"], subject="Your account is active again", body=body, sent_by=user["id"], ok=ok, msg_id=msg_id, error=err)
    await _audit(user, tenant_id=tenant_id, action="tenant.reactivate", entity_type="tenant", entity_id=tenant_id, summary=f"Reactivated tenant {tenant.get('name')}", request=request, metadata={"note": note, "notify_owner": notify_owner})
    result = await tenant_detail(user, tenant_id)
    result["email_status"] = email_status
    return result


async def mark_paid(user: dict, tenant_id: str, *, note: Optional[str] = None, request: Request | None = None) -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_SUBSCRIPTION_ADMIN.value})
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise PlatformAdminError("tenant_not_found", "Tenant not found", 404)
    now = _now_iso()
    await db.tenant_subscriptions.update_many(
        {"tenant_id": tenant_id},
        {"$set": {"status": "active", "dunning_state": "current", "first_payment_failed_at": None, "last_payment_succeeded_at": now, "updated_at": now}},
    )
    await db.tenant_billing_accounts.update_one(
        {"tenant_id": tenant_id},
        {"$set": {"status": "active", "suspended_at": None, "suspension_reason": None, "updated_at": now}},
    )
    auto_reactivated = tenant.get("is_active") is False
    if auto_reactivated:
        await db.tenants.update_one(
            {"id": tenant_id},
            {"$set": {"is_active": True, "reactivated_at": now, "reactivated_by": user["id"], "reactivated_by_email": user.get("email"), "updated_at": now}},
        )
    await _audit(user, tenant_id=tenant_id, action="payment.manual_mark_paid", entity_type="tenant", entity_id=tenant_id, summary=f"Manually marked {tenant.get('name')} paid", request=request, metadata={"note": note, "auto_reactivated": auto_reactivated})
    result = await tenant_detail(user, tenant_id)
    result["auto_reactivated"] = auto_reactivated
    return result


async def set_dunning_threshold(user: dict, tenant_id: str, *, threshold: Optional[int], request: Request | None = None) -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_SUBSCRIPTION_ADMIN.value})
    if threshold is not None and threshold < 1:
        raise PlatformAdminError("invalid_threshold", "Threshold must be a positive number or null", 400)
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise PlatformAdminError("tenant_not_found", "Tenant not found", 404)
    now = _now_iso()
    updated = await db.tenant_billing_accounts.update_one(
        {"tenant_id": tenant_id},
        {"$set": {"dunning_failure_threshold": threshold, "updated_at": now}},
    )
    if updated.matched_count == 0:
        account = TenantBillingAccount(
            tenant_id=tenant_id,
            billing_email=tenant.get("owner_email"),
            status="pending",
        ).model_dump()
        account["dunning_failure_threshold"] = threshold
        account["updated_at"] = now
        await db.tenant_billing_accounts.insert_one(prepare_for_mongo(account))
    await _audit(user, tenant_id=tenant_id, action="dunning.threshold_set", entity_type="tenant", entity_id=tenant_id, summary=f"Set dunning threshold for {tenant.get('name')}", request=request, metadata={"threshold": threshold})
    return await tenant_detail(user, tenant_id)


async def start_impersonation(user: dict, *, target_user_id: str, request: Request | None = None) -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_TENANT_READ.value})
    target = await db.users.find_one({"id": target_user_id, "is_active": True}, {"_id": 0, "password_hash": 0})
    if not target:
        raise PlatformAdminError("target_user_not_found", "Target user not found", 404)
    tenant = await db.tenants.find_one({"id": target["tenant_id"]}, {"_id": 0})
    if not tenant:
        raise PlatformAdminError("tenant_not_found", "Tenant not found", 404)
    log = {
        "id": str(uuid.uuid4()),
        "platform_admin_user_id": user["id"],
        "platform_admin_email": user.get("email"),
        "target_user_id": target["id"],
        "target_user_email": target.get("email"),
        "tenant_id": target["tenant_id"],
        "tenant_name": tenant.get("name"),
        "started_at": _now_iso(),
        "ended_at": None,
        "duration_seconds": None,
        **_request_meta(request),
    }
    await db.impersonation_logs.insert_one(prepare_for_mongo(log))
    token = create_access_token(
        subject=target["id"],
        tenant_id=target["tenant_id"],
        extra={
            "impersonating": True,
            "impersonation_log_id": log["id"],
            "platform_admin_id": user["id"],
            "platform_admin_email": user.get("email"),
        },
    )
    await _audit(user, tenant_id=target["tenant_id"], action="impersonation.start", entity_type="user", entity_id=target["id"], summary=f"Started impersonating {target.get('email')}", request=request, metadata={"impersonation_log_id": log["id"]})
    return {"access_token": token, "token_type": "bearer", "impersonation_log": serialize_doc(log), "target_user": serialize_doc(target), "tenant": serialize_doc(tenant)}


async def end_impersonation(user: dict, *, log_id: str, request: Request | None = None) -> dict:
    require_platform_admin(user)
    log = await db.impersonation_logs.find_one({"id": log_id}, {"_id": 0})
    if not log:
        raise PlatformAdminError("impersonation_log_not_found", "Impersonation log not found", 404)
    if not log.get("ended_at"):
        now = utc_now()
        try:
            started = datetime.fromisoformat(str(log["started_at"]).replace("Z", "+00:00"))
        except Exception:
            started = now
        await db.impersonation_logs.update_one(
            {"id": log_id},
            {"$set": {"ended_at": now.isoformat(), "duration_seconds": max(0, int((now - started).total_seconds()))}},
        )
    await _audit(user, tenant_id=log["tenant_id"], action="impersonation.exit", entity_type="user", entity_id=log["target_user_id"], summary=f"Ended impersonation for {log.get('target_user_email')}", request=request, metadata={"impersonation_log_id": log_id})
    return serialize_doc(await db.impersonation_logs.find_one({"id": log_id}, {"_id": 0}))


async def end_current_impersonation(user: dict, *, request: Request | None = None) -> dict:
    impersonation = user.get("impersonation") or {}
    log_id = impersonation.get("impersonation_log_id")
    if not log_id:
        raise PlatformAdminError("impersonation_log_required", "No active impersonation log was found", 400)
    log = await db.impersonation_logs.find_one({"id": log_id}, {"_id": 0})
    if not log:
        raise PlatformAdminError("impersonation_log_not_found", "Impersonation log not found", 404)
    if not log.get("ended_at"):
        now = utc_now()
        try:
            started = datetime.fromisoformat(str(log["started_at"]).replace("Z", "+00:00"))
        except Exception:
            started = now
        await db.impersonation_logs.update_one(
            {"id": log_id},
            {"$set": {"ended_at": now.isoformat(), "duration_seconds": max(0, int((now - started).total_seconds()))}},
        )
    actor = {
        "id": impersonation.get("platform_admin_id") or log.get("platform_admin_user_id") or "platform",
        "email": impersonation.get("platform_admin_email") or log.get("platform_admin_email") or "platform",
        "platform_admin": True,
    }
    await _audit(actor, tenant_id=log["tenant_id"], action="impersonation.exit", entity_type="user", entity_id=log["target_user_id"], summary=f"Ended impersonation for {log.get('target_user_email')}", request=request, metadata={"impersonation_log_id": log_id})
    return serialize_doc(await db.impersonation_logs.find_one({"id": log_id}, {"_id": 0}))


async def list_impersonation_logs(user: dict, *, tenant_id: Optional[str] = None, limit: int = 200) -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_AUDIT_READ.value})
    q = {"tenant_id": tenant_id} if tenant_id else {}
    rows = await db.impersonation_logs.find(q, {"_id": 0}).sort("started_at", -1).limit(max(1, min(limit, 1000))).to_list(None)
    return {"items": [serialize_doc(r) for r in rows], "total": len(rows)}


async def _last_activity_for_tenant(tenant_id: str, tenant: dict) -> Optional[str]:
    candidates = [tenant.get("updated_at"), tenant.get("created_at")]
    latest_user = await db.users.find_one({"tenant_id": tenant_id, "last_login_at": {"$type": "string"}}, {"_id": 0, "last_login_at": 1}, sort=[("last_login_at", -1)])
    latest_audit = await db.audit_events.find_one({"tenant_id": tenant_id}, {"_id": 0, "created_at": 1}, sort=[("created_at", -1)])
    latest_order = await db.orders.find_one({"tenant_id": tenant_id}, {"_id": 0, "updated_at": 1, "created_at": 1}, sort=[("updated_at", -1)])
    latest_quote = await db.quotes.find_one({"tenant_id": tenant_id}, {"_id": 0, "updated_at": 1, "created_at": 1}, sort=[("updated_at", -1)])
    candidates.extend([
        (latest_user or {}).get("last_login_at"),
        (latest_audit or {}).get("created_at"),
        (latest_order or {}).get("updated_at") or (latest_order or {}).get("created_at"),
        (latest_quote or {}).get("updated_at") or (latest_quote or {}).get("created_at"),
    ])
    values = [str(v) for v in candidates if v]
    return max(values) if values else None


async def onboarding_checklist(user: dict, tenant_id: str) -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_TENANT_READ.value})
    from . import onboarding as onboarding_service

    scoped_user = {**user, "tenant_id": tenant_id, "role": "owner"}
    dashboard = await onboarding_service.dashboard(scoped_user)
    return {"items": dashboard["tasks"], "progress": dashboard["progress"]}


async def update_onboarding_item(user: dict, tenant_id: str, item_id: str, *, completed: bool, note: Optional[str] = None, request: Request | None = None) -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_TENANT_WRITE.value})
    from . import onboarding as onboarding_service

    status = "completed" if completed else "in_progress"
    scoped_user = {**user, "tenant_id": tenant_id, "role": "owner"}
    await onboarding_service.update_task_status(scoped_user, item_id, status, reason=note)
    await _audit(user, tenant_id=tenant_id, action="onboarding.checklist.update", entity_type="onboarding_task_state", entity_id=item_id, summary="Platform Admin updated onboarding checklist item", request=request, metadata={"completed": completed, "note": note})
    return await onboarding_checklist(user, tenant_id)


async def get_platform_settings() -> dict:
    doc = await db.platform_settings.find_one({"id": SETTINGS_ID}, {"_id": 0})
    if not doc:
        doc = {"id": SETTINGS_ID, "announcement": None, "maintenance": {"enabled": False}}
        await db.platform_settings.insert_one(prepare_for_mongo(doc))
    return serialize_doc(doc)


def _announcement_active(announcement: dict | None) -> bool:
    if not announcement or not announcement.get("message"):
        return False
    expires_at = announcement.get("expires_at")
    if not expires_at:
        return True
    try:
        parsed = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed > utc_now()
    except Exception:
        return True


async def public_announcement() -> dict:
    settings = await get_platform_settings()
    ann = settings.get("announcement")
    if not _announcement_active(ann):
        return {"active": False, "message": None, "severity": "info", "dismissable": True}
    return {"active": True, **serialize_doc(ann)}


async def public_maintenance() -> dict:
    settings = await get_platform_settings()
    return serialize_doc(settings.get("maintenance") or {"enabled": False})


async def set_announcement(user: dict, *, message: Optional[str], severity: str = "info", dismissable: bool = True, expires_at: Optional[str] = None, request: Request | None = None) -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_SETTINGS_WRITE.value})
    severity = (severity or "info").lower()
    if severity not in {"info", "warning", "critical"}:
        raise PlatformAdminError("invalid_severity", "Severity must be info, warning, or critical", 400)
    now = _now_iso()
    if not message or not message.strip():
        await db.platform_settings.update_one({"id": SETTINGS_ID}, {"$set": {"announcement": None, "updated_at": now}}, upsert=True)
        await _audit(user, tenant_id=user["tenant_id"], action="announcement.clear", entity_type="platform_settings", entity_id=SETTINGS_ID, summary="Cleared announcement banner", request=request)
        return {"announcement": None}
    ann = {"message": message.strip(), "severity": severity, "dismissable": dismissable, "expires_at": expires_at, "updated_at": now, "updated_by_email": user.get("email")}
    await db.platform_settings.update_one({"id": SETTINGS_ID}, {"$set": {"announcement": ann, "updated_at": now}}, upsert=True)
    await _audit(user, tenant_id=user["tenant_id"], action="announcement.set", entity_type="platform_settings", entity_id=SETTINGS_ID, summary="Published announcement banner", request=request, metadata={"severity": severity, "expires_at": expires_at})
    return {"announcement": ann}


async def set_maintenance(user: dict, *, enabled: bool, message: Optional[str] = None, request: Request | None = None) -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_SETTINGS_WRITE.value})
    now = _now_iso()
    maintenance = {"enabled": bool(enabled), "message": (message or "Scheduled maintenance in progress").strip() if enabled else None, "started_at": now if enabled else None, "started_by_email": user.get("email") if enabled else None}
    await db.platform_settings.update_one({"id": SETTINGS_ID}, {"$set": {"maintenance": maintenance, "updated_at": now}}, upsert=True)
    await _audit(user, tenant_id=user["tenant_id"], action="maintenance.enable" if enabled else "maintenance.disable", entity_type="platform_settings", entity_id=SETTINGS_ID, summary="Enabled maintenance mode" if enabled else "Disabled maintenance mode", request=request, metadata={"message": maintenance.get("message")})
    return {"maintenance": maintenance}


def _owner_first_name(tenant: dict, email: str) -> str:
    name = (tenant.get("owner_name") or "").strip()
    if name:
        return name.split()[0]
    local = (email or "").split("@", 1)[0].replace(".", " ").replace("_", " ").replace("-", " ").strip()
    return (local.split()[0].capitalize() if local else "there")


def _render_broadcast(text: str, context: dict[str, str]) -> str:
    out = text or ""
    for key in BROADCAST_PLACEHOLDERS:
        out = out.replace("{{" + key + "}}", html.escape(str(context.get(key) or ""), quote=True))
    return out


async def _broadcast_recipients(user: dict, *, target: str = "all_owners", tenant_ids: Optional[list[str]] = None, test_to: Optional[str] = None) -> list[dict]:
    if test_to:
        tenant = await db.tenants.find_one({"id": user["tenant_id"]}, {"_id": 0}) or {"id": user["tenant_id"], "name": "Example Tenant", "owner_email": test_to}
        return [{"tenant_id": tenant.get("id"), "email": test_to.strip(), "tenant": tenant}]
    q: dict[str, Any] = {}
    if tenant_ids:
        q["id"] = {"$in": tenant_ids}
    elif target == "active_only":
        q["is_active"] = {"$ne": False}
    elif target == "suspended_only":
        q["is_active"] = False
    elif target == "founders_only":
        ids = await db.founder_tenant_contracts.distinct("tenant_id", {"founder_status": {"$in": ["pending", "active", "grace"]}})
        ids.extend(await db.users.distinct("tenant_id", {"is_founder": True}))
        q["id"] = {"$in": sorted({i for i in ids if i})}
    tenants = await db.tenants.find(q, {"_id": 0}).to_list(10000)
    recipients: list[dict] = []
    seen: set[str] = set()
    for tenant in tenants:
        owner = await _owner_for_tenant(tenant["id"])
        email = (tenant.get("owner_email") or (owner or {}).get("email") or "").strip()
        key = email.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        recipients.append({"tenant_id": tenant["id"], "email": email, "tenant": {**tenant, "owner_email": email, "owner_name": (owner or {}).get("full_name")}})
    return recipients


async def broadcast_counts(user: dict) -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_BROADCAST_WRITE.value})
    counts = {}
    for key in ("all_owners", "active_only", "suspended_only", "founders_only"):
        counts[key] = len(await _broadcast_recipients(user, target=key))
    return counts


async def _check_broadcast_rate(user: dict, *, is_test: bool) -> None:
    since = (utc_now() - timedelta(hours=1)).isoformat()
    rows = await db.audit_events.find({"actor_user_id": user["id"], "action": "broadcast_email.send", "created_at": {"$gte": since}}, {"_id": 0, "diff": 1}).to_list(500)
    tests = sum(1 for r in rows if ((r.get("diff") or {}).get("metadata") or {}).get("test_to"))
    full = len(rows) - tests
    if is_test and tests >= BROADCAST_HOURLY_CAP_TESTS:
        raise PlatformAdminError("broadcast_test_rate_limited", "Broadcast test rate limit reached", 429)
    if not is_test and full >= BROADCAST_HOURLY_CAP_TENANTS:
        raise PlatformAdminError("broadcast_rate_limited", "Broadcast rate limit reached", 429)


async def _insert_email_log(*, tenant_id: Optional[str], to_email: str, subject: str, body: str, sent_by: str, ok: bool, msg_id: Optional[str], error: Optional[str]) -> dict:
    settings = get_settings()
    log = EmailLog(
        tenant_id=tenant_id or "platform",
        related_type="general",
        to_email=to_email,
        from_email=settings.sendgrid_from_email or "unset@localhost",
        subject=subject,
        body=body,
        status="sent" if ok else "failed",
        error_message=error,
        sent_by=sent_by,
        sendgrid_message_id=msg_id,
    ).model_dump()
    await db.email_logs.insert_one(prepare_for_mongo(log))
    await record_processed_activity(tenant_id=tenant_id or "platform", email_log_id=log["id"], to_email=to_email, sendgrid_message_id=msg_id, ok=ok, error=error)
    return serialize_doc(log)


async def send_broadcast(user: dict, *, subject: str, html_body: str, target: str = "all_owners", tenant_ids: Optional[list[str]] = None, test_to: Optional[str] = None, request: Request | None = None) -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_BROADCAST_WRITE.value})
    if not email_configured():
        raise PlatformAdminError("email_not_configured", "Email service is not configured. Set SENDGRID_API_KEY and SENDGRID_FROM_EMAIL.", 503)
    if not subject.strip() or not html_body.strip():
        raise PlatformAdminError("broadcast_content_required", "Subject and body are required", 400)
    await _check_broadcast_rate(user, is_test=bool(test_to))
    recipients = await _broadcast_recipients(user, target=target, tenant_ids=tenant_ids, test_to=test_to)
    if not recipients:
        raise PlatformAdminError("broadcast_no_recipients", "No recipients matched the selected audience", 400)
    sent: list[str] = []
    failed: list[dict[str, str]] = []
    for row in recipients:
        tenant = row["tenant"]
        context = {"tenant_name": tenant.get("name") or "", "owner_email": row["email"], "owner_first_name": _owner_first_name(tenant, row["email"])}
        rendered_subject = _render_broadcast(subject, context)
        rendered_html = _render_broadcast(html_body, context)
        text_body = re.sub(r"<[^>]+>", "", rendered_html)
        ok, msg_id, err = send_email(to_email=row["email"], subject=rendered_subject, body_text=text_body, body_html=rendered_html)
        await _insert_email_log(tenant_id=row.get("tenant_id"), to_email=row["email"], subject=rendered_subject, body=text_body, sent_by=user["id"], ok=ok, msg_id=msg_id, error=err)
        if ok:
            sent.append(row["email"])
        else:
            failed.append({"email": row["email"], "error": err or "unknown"})
    await _audit(user, tenant_id=user["tenant_id"], action="broadcast_email.send", entity_type="platform_broadcast", entity_id=str(uuid.uuid4()), summary=f"Broadcast email sent: {subject[:120]}", request=request, metadata={"subject": subject, "target": target, "tenant_ids": tenant_ids, "test_to": test_to, "recipient_count": len(recipients), "sent_count": len(sent), "failed_count": len(failed)})
    return {"mode": "test" if test_to else "broadcast", "matched_recipients": len(recipients), "sent_count": len(sent), "failed_count": len(failed), "failed": failed[:25]}


async def email_logs_summary(user: dict, *, tenant_id: Optional[str] = None, since: Optional[str] = None) -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_TENANT_READ.value})
    q: dict[str, Any] = {}
    if tenant_id:
        q["tenant_id"] = tenant_id
    if since:
        q["created_at"] = {"$gte": since}
    total = await db.email_logs.count_documents(q)
    counts = {status: await db.email_logs.count_documents({**q, "status": status}) for status in ("sent", "delivered", "failed", "skipped", "queued")}
    bounced = await db.email_activity.count_documents({**({"tenant_id": tenant_id} if tenant_id else {}), "event": {"$in": ["bounce", "dropped"]}})
    complaints = await db.email_activity.count_documents({**({"tenant_id": tenant_id} if tenant_id else {}), "event": "spamreport"})
    delivered_events = await db.email_activity.count_documents({**({"tenant_id": tenant_id} if tenant_id else {}), "event": "delivered"})
    return {"total": total, "delivered": max(counts.get("delivered", 0), delivered_events), "pending": counts.get("sent", 0) + counts.get("queued", 0), "bounced": bounced, "complaints": complaints, "failed": counts.get("failed", 0), "by_status": counts}


async def list_email_logs(user: dict, *, tenant_id: Optional[str] = None, status: Optional[str] = None, to_email: Optional[str] = None, since: Optional[str] = None, limit: int = 200) -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_TENANT_READ.value})
    q: dict[str, Any] = {}
    if tenant_id:
        q["tenant_id"] = tenant_id
    if status:
        q["status"] = status
    if to_email:
        q["to_email"] = {"$regex": to_email, "$options": "i"}
    if since:
        q["created_at"] = {"$gte": since}
    rows = await db.email_logs.find(q, {"_id": 0}).sort("created_at", -1).limit(max(1, min(limit, 500))).to_list(None)
    for row in rows:
        row["events"] = await db.email_activity.find({"email_log_id": row["id"]}, {"_id": 0}).sort("event_timestamp", -1).to_list(50)
    return {"items": [serialize_doc(r) for r in rows], "total": len(rows)}


async def list_audit_log(user: dict, *, action: Optional[str] = None, actor_email: Optional[str] = None, tenant_id: Optional[str] = None, entity_type: Optional[str] = None, limit: int = 200) -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_AUDIT_READ.value})
    q: dict[str, Any] = {}
    if action:
        q["action"] = action
    if actor_email:
        q["actor_email"] = {"$regex": actor_email, "$options": "i"}
    if tenant_id:
        q["tenant_id"] = tenant_id
    if entity_type:
        q["entity_type"] = entity_type
    rows = await db.audit_events.find(q, {"_id": 0}).sort("created_at", -1).limit(max(1, min(limit, 1000))).to_list(None)
    return {"items": [serialize_doc(r) for r in rows], "total": len(rows)}


async def audit_actions(user: dict) -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_AUDIT_READ.value})
    actions = await db.audit_events.distinct("action")
    entity_types = await db.audit_events.distinct("entity_type")
    return {"actions": sorted([a for a in actions if a]), "entity_types": sorted([e for e in entity_types if e])}


async def audit_entry(user: dict, entry_id: str) -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_AUDIT_READ.value})
    doc = await db.audit_events.find_one({"id": entry_id}, {"_id": 0})
    if not doc:
        raise PlatformAdminError("audit_entry_not_found", "Audit entry not found", 404)
    return serialize_doc(doc)


def _date_bounds(range_key: str) -> tuple[str, str]:
    now = utc_now()
    days = {"today": 0, "7d": 7, "14d": 14, "30d": 30}.get(range_key, 30)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0) if days == 0 else now - timedelta(days=days)
    return start.isoformat(), now.isoformat()


async def analytics(user: dict, *, range_key: str = "30d") -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_ANALYTICS_READ.value})
    start, end = _date_bounds(range_key)
    date_filter = {"$gte": start, "$lte": end}
    tenants = await db.tenants.count_documents({})
    users = await db.users.count_documents({})
    active_users = await db.users.count_documents({"is_active": True})
    suspended_tenants = await db.tenants.count_documents({"is_active": False})
    new_users = await db.users.count_documents({"created_at": date_filter})
    new_orders = await db.orders.count_documents({"created_at": date_filter})
    new_quotes = await db.quotes.count_documents({"created_at": date_filter})
    audit_actions_count = await db.audit_events.count_documents({"created_at": date_filter})
    ai_usage = await db.ai_usage_ledger_entries.count_documents({"created_at": date_filter})
    ai_cost_rows = await db.ai_provider_cost_ledger_entries.count_documents({"created_at": date_filter})
    ai_credits = await db.ai_credit_ledger_entries.count_documents({"created_at": date_filter})
    ai_cost = await db.ai_provider_cost_ledger_entries.aggregate([
        {"$match": {"created_at": date_filter}},
        {"$group": {"_id": None, "actual_cost_cents": {"$sum": {"$ifNull": ["$actual_cost_cents", 0]}}, "estimated_cost_micros": {"$sum": "$estimated_cost_micros"}, "actual_cost_micros": {"$sum": "$actual_cost_micros"}, "input_units": {"$sum": "$input_units"}, "output_units": {"$sum": "$output_units"}}},
    ]).to_list(1)
    ai_credit_totals = await db.ai_credit_ledger_entries.aggregate([
        {"$match": {"created_at": date_filter}},
        {"$group": {"_id": "$entry_type", "credits": {"$sum": "$amount_credits"}, "count": {"$sum": 1}}},
        {"$sort": {"credits": -1}},
    ]).to_list(20)
    subscriptions = await db.tenant_subscriptions.count_documents({})
    trialing = await db.tenant_subscriptions.count_documents({"status": "trialing"})
    active_subs = await db.tenant_subscriptions.count_documents({"status": "active"})
    dunning = await db.tenant_subscriptions.count_documents({"dunning_state": {"$ne": "current"}})
    events = await db.analytics_events.count_documents({"timestamp": date_filter})
    errors = await db.analytics_events.count_documents({"timestamp": date_filter, "event_type": {"$in": ["error", "api_error", "frontend_error"]}})
    suspicious = await db.analytics_events.count_documents({"timestamp": date_filter, "$or": [{"is_bot": True}, {"is_suspicious": True}]})
    route_rows = await db.analytics_events.aggregate([
        {"$match": {"timestamp": date_filter, "route": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$route", "events": {"$sum": 1}, "sessions": {"$addToSet": "$session_id"}, "visitors": {"$addToSet": "$visitor_id"}}},
        {"$project": {"route": "$_id", "events": 1, "sessions": {"$size": "$sessions"}, "visitors": {"$size": "$visitors"}, "_id": 0}},
        {"$sort": {"events": -1}},
        {"$limit": 25},
    ]).to_list(25)
    referrer_rows = await db.analytics_events.aggregate([
        {"$match": {"timestamp": date_filter, "referrer": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$referrer", "events": {"$sum": 1}, "visitors": {"$addToSet": "$visitor_id"}}},
        {"$project": {"referrer": "$_id", "events": 1, "visitors": {"$size": "$visitors"}, "_id": 0}},
        {"$sort": {"events": -1}},
        {"$limit": 25},
    ]).to_list(25)
    event_rows = await db.analytics_events.aggregate([
        {"$match": {"timestamp": date_filter}},
        {"$group": {"_id": "$event_type", "events": {"$sum": 1}, "sessions": {"$addToSet": "$session_id"}}},
        {"$project": {"event_type": "$_id", "events": 1, "sessions": {"$size": "$sessions"}, "_id": 0}},
        {"$sort": {"events": -1}},
        {"$limit": 25},
    ]).to_list(25)
    ai_feature_rows = await db.ai_usage_ledger_entries.aggregate([
        {"$match": {"created_at": date_filter}},
        {"$group": {"_id": "$feature_key", "uses": {"$sum": 1}, "credits": {"$sum": "$credits_charged"}, "input_units": {"$sum": "$input_units"}, "output_units": {"$sum": "$output_units"}}},
        {"$project": {"feature_key": "$_id", "uses": 1, "credits": 1, "input_units": 1, "output_units": 1, "_id": 0}},
        {"$sort": {"uses": -1}},
        {"$limit": 25},
    ]).to_list(25)
    sessions_total = len(await db.analytics_events.distinct("session_id", {"timestamp": date_filter}))
    visitors_total = len(await db.analytics_events.distinct("visitor_id", {"timestamp": date_filter}))
    active_tenants = len(set(await db.orders.distinct("tenant_id", {"created_at": date_filter}) + await db.quotes.distinct("tenant_id", {"created_at": date_filter}) + await db.users.distinct("tenant_id", {"last_login_at": date_filter})))
    trial_rows = await db.trial_records.aggregate([
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]).to_list(20)
    buckets = []
    for i in range(6, -1, -1):
        day = utc_now() - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()
        df = {"$gte": day_start, "$lte": day_end}
        buckets.append({"date": day.strftime("%b %d"), "orders": await db.orders.count_documents({"created_at": df}), "quotes": await db.quotes.count_documents({"created_at": df}), "users": await db.users.count_documents({"created_at": df}), "events": await db.analytics_events.count_documents({"timestamp": df})})
    return {
        "overview": {
            "total_tenants": tenants,
            "total_users": users,
            "active_users": active_users,
            "suspended_tenants": suspended_tenants,
            "new_users": new_users,
            "new_orders": new_orders,
            "new_quotes": new_quotes,
            "audit_actions": audit_actions_count,
            "subscriptions": subscriptions,
            "trialing_subscriptions": trialing,
            "active_subscriptions": active_subs,
            "dunning_subscriptions": dunning,
            "analytics_events": events,
            "error_events": errors,
            "suspicious_events": suspicious,
            "ai_usage_events": ai_usage,
            "ai_cost_rows": ai_cost_rows,
            "ai_credit_rows": ai_credits,
            "sessions": sessions_total,
            "visitors": visitors_total,
            "active_tenants_in_period": active_tenants,
        },
        "routes": route_rows,
        "referrers": referrer_rows,
        "feature_usage": event_rows,
        "ai_feature_usage": ai_feature_rows,
        "ai_cost": ai_cost[0] if ai_cost else {"actual_cost_cents": 0, "estimated_cost_micros": 0, "actual_cost_micros": 0, "input_units": 0, "output_units": 0},
        "ai_credit_activity": [{"entry_type": r.get("_id") or "unknown", "credits": r.get("credits", 0), "count": r.get("count", 0)} for r in ai_credit_totals],
        "commercial_conversion": {"subscriptions": subscriptions, "active": active_subs, "trialing": trialing, "dunning": dunning},
        "trial_funnel": [{"status": r.get("_id") or "unknown", "count": r.get("count", 0)} for r in trial_rows],
        "activity_chart": buckets,
        "range": range_key,
        "period_start": start,
        "period_end": end,
    }


async def ingest_analytics_event(payload: dict[str, Any], request: Request | None = None) -> dict:
    event_type = str(payload.get("event_type") or "")[:64]
    session_id = str(payload.get("session_id") or "")[:96]
    visitor_id = str(payload.get("visitor_id") or "")[:96]
    if not event_type or not session_id or not visitor_id:
        raise PlatformAdminError("invalid_analytics_event", "event_type, session_id, and visitor_id are required", 422)
    ua = str(payload.get("user_agent") or (request.headers.get("user-agent") if request else "") or "")[:512]
    route = str(payload.get("route") or "")[:256]
    ua_lower = ua.lower()
    bot = any(signal in ua_lower for signal in ("bot", "crawler", "spider", "curl/", "wget/", "python-requests", "nmap", "sqlmap"))
    suspicious = any(path in route for path in ("/wp-admin", "/phpmyadmin", "/.env", "/xmlrpc.php", "/.git"))
    doc = {"id": str(uuid.uuid4()), "event_type": event_type, "session_id": session_id, "visitor_id": visitor_id, "user_id": payload.get("user_id"), "tenant_id": payload.get("tenant_id"), "route": route, "referrer": str(payload.get("referrer") or "")[:512], "user_agent": ua, "ip_address": _request_meta(request).get("ip_address"), "is_bot": bot, "is_suspicious": suspicious, "timestamp": _now_iso(), "metadata": payload.get("metadata") or {}}
    await db.analytics_events.insert_one(prepare_for_mongo(doc))
    return {"ok": True}
