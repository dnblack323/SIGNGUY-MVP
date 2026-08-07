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
SAMPLE_DATA_PREFIX = "demo-platform-admin"


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


def _chunked(values: list[str], size: int = 5000) -> list[list[str]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        raw = str(value)
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _days_since(value: Any) -> int | None:
    parsed = _parse_iso(value)
    if not parsed:
        return None
    return max(0, (utc_now() - parsed.astimezone(timezone.utc)).days)


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


def _dunning_detail(account: dict | None, subscription: dict | None) -> dict[str, Any]:
    account = account or {}
    subscription = subscription or {}
    failed_since = subscription.get("first_payment_failed_at") or account.get("first_payment_failed_at")
    days_past_due = _days_since(failed_since)
    review_after_days = (
        account.get("dunning_review_after_days")
        or subscription.get("dunning_review_after_days")
        or account.get("dunning_failure_threshold")
    )
    review_after_days = int(review_after_days or 15)
    parsed_failed_since = _parse_iso(failed_since)
    review_eligible_at = (parsed_failed_since + timedelta(days=review_after_days)).isoformat() if parsed_failed_since else None
    return {
        "state": subscription.get("dunning_state") or "current",
        "failed_since": failed_since,
        "days_past_due": days_past_due,
        "last_failed_at": subscription.get("last_payment_failed_at") or account.get("last_payment_failed_at"),
        "last_paid_at": subscription.get("last_payment_succeeded_at") or account.get("last_payment_succeeded_at"),
        "manual_grace_until": subscription.get("manual_grace_until") or account.get("grace_period_until"),
        "review_after_days": review_after_days,
        "review_eligible_at": review_eligible_at,
        "suspension_review_eligible": days_past_due is not None and days_past_due >= review_after_days,
    }


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
    page_limit = max(1, min(limit, 2000))
    docs = await db.tenants.find(query, {"_id": 0}).sort("created_at", -1).limit(page_limit).to_list(None)
    tenant_ids = [tenant["id"] for tenant in docs if tenant.get("id")]

    owner_by_tenant: dict[str, dict[str, Any]] = {}
    user_count_by_tenant: dict[str, int] = {}
    account_by_tenant: dict[str, dict[str, Any]] = {}
    sub_by_tenant: dict[str, dict[str, Any]] = {}
    founder_ids: set[str] = set()

    if tenant_ids:
        for chunk in _chunked(tenant_ids):
            owner_rows = await db.users.find(
                {"tenant_id": {"$in": chunk}, "$or": [{"role": "owner"}, {"is_owner": True}]},
                {"_id": 0, "tenant_id": 1, "email": 1, "full_name": 1, "created_at": 1},
            ).sort("created_at", 1).to_list(None)
            for owner in owner_rows:
                owner_by_tenant.setdefault(owner["tenant_id"], owner)

            count_rows = await db.users.aggregate([
                {"$match": {"tenant_id": {"$in": chunk}}},
                {"$group": {"_id": "$tenant_id", "count": {"$sum": 1}}},
            ]).to_list(None)
            user_count_by_tenant.update({row["_id"]: row["count"] for row in count_rows})

            account_rows = await db.tenant_billing_accounts.find({"tenant_id": {"$in": chunk}}, {"_id": 0}).to_list(None)
            for account in account_rows:
                account_by_tenant.setdefault(account["tenant_id"], account)

            sub_rows = await db.tenant_subscriptions.find({"tenant_id": {"$in": chunk}}, {"_id": 0}).sort("updated_at", -1).to_list(None)
            for sub in sub_rows:
                account = account_by_tenant.get(sub.get("tenant_id"))
                if account and account.get("current_subscription_id") == sub.get("id"):
                    sub_by_tenant[sub["tenant_id"]] = sub
                else:
                    sub_by_tenant.setdefault(sub["tenant_id"], sub)

            founder_ids.update(await db.founder_tenant_contracts.distinct("tenant_id", {"tenant_id": {"$in": chunk}, "founder_status": {"$in": ["pending", "active", "grace"]}}))
            founder_ids.update(await db.users.distinct("tenant_id", {"tenant_id": {"$in": chunk}, "is_founder": True}))

    summary_founder_ids = set(await db.founder_tenant_contracts.distinct("tenant_id", {"founder_status": {"$in": ["pending", "active", "grace"]}}))
    summary_founder_ids.update(await db.users.distinct("tenant_id", {"is_founder": True}))
    items = []
    for tenant in docs:
        owner = owner_by_tenant.get(tenant["id"])
        account = account_by_tenant.get(tenant["id"]) or {}
        sub = sub_by_tenant.get(tenant["id"]) or {}
        items.append({
            "id": tenant["id"],
            "name": tenant.get("name") or "Unnamed Shop",
            "slug": tenant.get("slug"),
            "owner_email": tenant.get("owner_email") or (owner or {}).get("email"),
            "plan": sub.get("plan_product_id") or tenant.get("plan") or "unassigned",
            "status": "suspended" if tenant.get("is_active") is False else (account.get("status") or "active"),
            "is_active": tenant.get("is_active", True),
            "created_at": tenant.get("created_at"),
            "user_count": user_count_by_tenant.get(tenant["id"], 0),
            "is_founder": tenant["id"] in founder_ids,
        })
    return {
        "items": items,
        "total": await db.tenants.count_documents(query),
        "page_count": len(items),
        "summary": {
            "total_tenants": await db.tenants.count_documents({}),
            "total_users": await db.users.count_documents({}),
            "suspended_tenants": await db.tenants.count_documents({"is_active": False}),
            "founder_tenants": len(summary_founder_ids),
        },
    }


async def seed_sample_data(user: dict) -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_TENANT_WRITE.value})
    settings = get_settings()
    if settings.env == "production":
        raise PlatformAdminError("sample_data_disabled", "Sample data is disabled in production", 404)

    now = utc_now()
    now_iso = now.isoformat()
    tenants = [
        {
            "id": f"{SAMPLE_DATA_PREFIX}-alpha",
            "slug": "sample-sign-shop-alpha",
            "name": "Alpha Sign Co.",
            "owner_email": "owner@alphasigns.example.com",
            "plan": "signguy_pro_monthly",
            "is_active": True,
            "status": "active",
            "created_at": (now - timedelta(days=42)).isoformat(),
        },
        {
            "id": f"{SAMPLE_DATA_PREFIX}-beta",
            "slug": "sample-wrap-studio-beta",
            "name": "Beta Wrap Studio",
            "owner_email": "hello@betawraps.example.com",
            "plan": "signguy_founder_annual",
            "is_active": True,
            "status": "past_due",
            "created_at": (now - timedelta(days=18)).isoformat(),
            "is_founder": True,
        },
        {
            "id": f"{SAMPLE_DATA_PREFIX}-gamma",
            "slug": "sample-neon-garage-gamma",
            "name": "Gamma Neon Garage",
            "owner_email": "ops@gammaneon.example.com",
            "plan": "signguy_starter_monthly",
            "is_active": False,
            "status": "suspended",
            "created_at": (now - timedelta(days=9)).isoformat(),
            "suspension_reason": "Payment dunning reached suspension review.",
            "suspended_at": (now - timedelta(days=2)).isoformat(),
        },
    ]

    inserted = {
        "tenants": 0,
        "users": 0,
        "billing": 0,
        "email_logs": 0,
        "audit_events": 0,
        "analytics_events": 0,
        "ai_rows": 0,
        "trials": 0,
        "onboarding": 0,
    }

    async def upsert(collection: str, filter_doc: dict[str, Any], doc: dict[str, Any]) -> bool:
        prepared = prepare_for_mongo({**doc, "updated_at": doc.get("updated_at") or now_iso})
        result = await getattr(db, collection).update_one(filter_doc, {"$set": prepared}, upsert=True)
        return bool(result.upserted_id)

    for idx, tenant in enumerate(tenants):
        tenant_id = tenant["id"]
        inserted["tenants"] += int(await upsert("tenants", {"id": tenant_id}, tenant))

        owner_id = f"{tenant_id}-owner"
        manager_id = f"{tenant_id}-manager"
        for user_doc in [
            {
                "id": owner_id,
                "tenant_id": tenant_id,
                "email": tenant["owner_email"],
                "full_name": tenant["name"].replace("Co.", "Owner").replace("Studio", "Manager").replace("Garage", "Owner"),
                "role": "owner",
                "is_active": tenant.get("is_active", True),
                "password_hash": "sample-data-login-disabled",
                "created_at": tenant["created_at"],
                "last_login_at": (now - timedelta(days=idx + 1)).isoformat(),
                "is_founder": bool(tenant.get("is_founder")),
            },
            {
                "id": manager_id,
                "tenant_id": tenant_id,
                "email": f"manager+{idx}@signguy-demo.example.com",
                "full_name": f"{tenant['name']} Manager",
                "role": "admin",
                "is_active": tenant.get("is_active", True),
                "password_hash": "sample-data-login-disabled",
                "created_at": (now - timedelta(days=max(1, idx + 4))).isoformat(),
                "last_login_at": (now - timedelta(days=idx + 2)).isoformat(),
            },
        ]:
            inserted["users"] += int(await upsert("users", {"id": user_doc["id"], "tenant_id": tenant_id}, user_doc))

        billing_account_id = f"{tenant_id}-billing"
        subscription_id = f"{tenant_id}-subscription"
        dunning_state = "current" if idx == 0 else ("day_8_14_soft_restriction" if idx == 1 else "suspended")
        account_status = "active" if idx == 0 else ("past_due" if idx == 1 else "suspended")
        inserted["billing"] += int(await upsert("tenant_billing_accounts", {"id": billing_account_id, "tenant_id": tenant_id}, {
            "id": billing_account_id,
            "tenant_id": tenant_id,
            "billing_owner_user_id": owner_id,
            "billing_email": tenant["owner_email"],
            "status": account_status,
            "stripe_customer_id": f"cus_demo_{idx}",
            "current_subscription_id": subscription_id,
            "dunning_review_after_days": 15 + idx,
            "suspended_at": tenant.get("suspended_at"),
            "suspension_reason": tenant.get("suspension_reason"),
            "created_at": tenant["created_at"],
        }))
        inserted["billing"] += int(await upsert("tenant_subscriptions", {"id": subscription_id, "tenant_id": tenant_id}, {
            "id": subscription_id,
            "tenant_id": tenant_id,
            "billing_account_id": billing_account_id,
            "catalog_version_id": "sample-catalog-v1",
            "plan_product_id": tenant["plan"],
            "price_id": f"sample-price-{idx}",
            "billing_interval": "monthly" if idx != 1 else "annual",
            "status": "active" if idx == 0 else ("past_due" if idx == 1 else "unpaid"),
            "dunning_state": dunning_state,
            "stripe_subscription_id": f"sub_demo_{idx}",
            "stripe_customer_id": f"cus_demo_{idx}",
            "first_payment_failed_at": None if idx == 0 else (now - timedelta(days=idx * 4 + 2)).isoformat(),
            "last_payment_failed_at": None if idx == 0 else (now - timedelta(days=idx + 1)).isoformat(),
            "last_payment_succeeded_at": (now - timedelta(days=idx * 11 + 3)).isoformat(),
            "manual_grace_until": (now + timedelta(days=7)).isoformat() if idx == 1 else None,
            "created_at": tenant["created_at"],
        }))

        if tenant.get("is_founder"):
            inserted["billing"] += int(await upsert("founder_tenant_contracts", {"id": f"{tenant_id}-founder-contract", "tenant_id": tenant_id}, {
                "id": f"{tenant_id}-founder-contract",
                "tenant_id": tenant_id,
                "founder_status": "active",
                "created_at": tenant["created_at"],
            }))

        trial_status = "converted" if idx == 0 else ("extended_active" if idx == 1 else "free_expired")
        inserted["trials"] += int(await upsert("trial_records", {"id": f"{tenant_id}-trial", "tenant_id": tenant_id}, {
            "id": f"{tenant_id}-trial",
            "tenant_id": tenant_id,
            "billing_account_id": billing_account_id,
            "trial_kind": "free",
            "status": trial_status,
            "starts_at": tenant["created_at"],
            "ends_at": (now + timedelta(days=14 - (idx * 10))).isoformat(),
            "credit_allotment": 150,
            "created_by_user_id": owner_id,
        }))

        for task_key, status in {
            "company_profile": "completed",
            "pricing_setup_assistant": "completed" if idx != 2 else "in_progress",
            "customer_portal": "completed" if idx == 0 else "not_started",
            "first_order": "completed" if idx == 0 else "not_started",
        }.items():
            inserted["onboarding"] += int(await upsert("onboarding_task_states", {"tenant_id": tenant_id, "program_key": "shop_launch_v1", "task_key": task_key}, {
                "id": f"{tenant_id}-onboarding-{task_key}",
                "tenant_id": tenant_id,
                "program_key": "shop_launch_v1",
                "program_version": 1,
                "task_key": task_key,
                "level": "required" if task_key in {"company_profile", "pricing_setup_assistant", "first_order"} else "recommended",
                "status": status,
                "completed_at": (now - timedelta(days=idx + 1)).isoformat() if status == "completed" else None,
                "updated_by_user_id": user["id"],
                "created_at": tenant["created_at"],
            }))

        for day in range(0, 5):
            created = (now - timedelta(days=day + idx)).isoformat()
            inserted["analytics_events"] += int(await upsert("analytics_events", {"id": f"{tenant_id}-analytics-{day}"}, {
                "id": f"{tenant_id}-analytics-{day}",
                "event_type": ["page_view", "quote_created", "order_created", "ai_tool_used", "frontend_error"][day],
                "session_id": f"{tenant_id}-session-{day // 2}",
                "visitor_id": f"{tenant_id}-visitor-{day}",
                "user_id": owner_id,
                "tenant_id": tenant_id,
                "route": ["/", "/quotes", "/orders", "/studio", "/wp-admin"][day],
                "referrer": ["direct", "google", "direct", "facebook", "crawler"][day],
                "user_agent": "SignGuy Demo Browser",
                "is_bot": day == 4,
                "is_suspicious": day == 4,
                "timestamp": created,
                "metadata": {"sample": True},
            }))

        for related_type, collection in [("quote", "quotes"), ("order", "orders")]:
            inserted["analytics_events"] += int(await upsert(collection, {"id": f"{tenant_id}-{related_type}-sample"}, {
                "id": f"{tenant_id}-{related_type}-sample",
                "tenant_id": tenant_id,
                "customer_name": "Sample Customer",
                "status": "approved" if related_type == "quote" else "in_production",
                "created_at": (now - timedelta(days=idx + 1)).isoformat(),
                "updated_at": (now - timedelta(days=idx)).isoformat(),
            }))

        email_log_id = f"{tenant_id}-email-log"
        email_status = "delivered" if idx == 0 else ("sent" if idx == 1 else "failed")
        inserted["email_logs"] += int(await upsert("email_logs", {"id": email_log_id, "tenant_id": tenant_id}, {
            "id": email_log_id,
            "tenant_id": tenant_id,
            "related_type": "general",
            "template": "general",
            "to_email": tenant["owner_email"],
            "from_email": settings.sendgrid_from_email or "demo@signguy-ai.example.com",
            "subject": "Sample platform admin delivery row",
            "body": "Sample email used by the Platform Admin demo data.",
            "status": email_status,
            "error_message": "Mailbox rejected demo message" if email_status == "failed" else None,
            "sent_by": user["id"],
            "sendgrid_message_id": f"sg-demo-{idx}",
            "created_at": (now - timedelta(days=idx + 1)).isoformat(),
        }))
        inserted["email_logs"] += int(await upsert("email_activity", {"id": f"{email_log_id}-activity"}, {
            "id": f"{email_log_id}-activity",
            "tenant_id": tenant_id,
            "email_log_id": email_log_id,
            "provider": "sample",
            "provider_event_id": f"sample-provider-event-{tenant_id}",
            "event": "delivered" if idx == 0 else ("processed" if idx == 1 else "bounce"),
            "event_timestamp": (now - timedelta(days=idx)).isoformat(),
            "created_at": (now - timedelta(days=idx)).isoformat(),
            "reason": "Sample provider event",
        }))

        inserted["audit_events"] += int(await upsert("audit_events", {"id": f"{tenant_id}-audit"}, {
            "id": f"{tenant_id}-audit",
            "tenant_id": tenant_id,
            "actor_user_id": user["id"],
            "actor_email": user.get("email", "platform"),
            "action": "sample_data.seed",
            "entity_type": "tenant",
            "entity_id": tenant_id,
            "summary": f"Seeded sample Platform Admin tenant {tenant['name']}",
            "diff": {"metadata": {"sample": True}},
            "created_at": now_iso,
        }))

        inserted["ai_rows"] += int(await upsert("ai_usage_ledger_entries", {"id": f"{tenant_id}-ai-usage"}, {
            "id": f"{tenant_id}-ai-usage",
            "tenant_id": tenant_id,
            "user_id": owner_id,
            "feature_key": "design_image",
            "capability_key": "studio.design_image",
            "credits_charged": 12 + idx,
            "input_units": 800 + idx * 100,
            "output_units": 1,
            "created_at": (now - timedelta(days=idx + 1)).isoformat(),
        }))
        inserted["ai_rows"] += int(await upsert("ai_provider_cost_ledger_entries", {"id": f"{tenant_id}-ai-cost"}, {
            "id": f"{tenant_id}-ai-cost",
            "tenant_id": tenant_id,
            "provider_key": "sample-provider",
            "model_key": "sample-image-model",
            "actual_cost_cents": 18 + idx,
            "estimated_cost_micros": 180000 + idx * 10000,
            "actual_cost_micros": 180000 + idx * 10000,
            "input_units": 800 + idx * 100,
            "output_units": 1,
            "created_at": (now - timedelta(days=idx + 1)).isoformat(),
        }))
        inserted["ai_rows"] += int(await upsert("ai_credit_ledger_entries", {"id": f"{tenant_id}-ai-credit"}, {
            "id": f"{tenant_id}-ai-credit",
            "tenant_id": tenant_id,
            "credit_account_id": f"{tenant_id}-credits",
            "entry_type": "commit",
            "amount_credits": -(12 + idx),
            "created_at": (now - timedelta(days=idx + 1)).isoformat(),
        }))

    return {
        "ok": True,
        "sample_prefix": SAMPLE_DATA_PREFIX,
        "inserted": inserted,
        "tenant_ids": [tenant["id"] for tenant in tenants],
        "message": "Sample Platform Admin tenants and related activity are ready.",
    }


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
    audit_rows = await db.audit_events.find({"tenant_id": tenant_id}, {"_id": 0}).sort("created_at", -1).limit(25).to_list(25)
    impersonation_rows = await db.impersonation_logs.find({"tenant_id": tenant_id}, {"_id": 0}).sort("started_at", -1).limit(10).to_list(10)
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
        "billing": {**billing, "dunning": _dunning_detail(billing.get("account"), billing.get("subscription"))},
        "email_summary": email_summary,
        "onboarding": onboarding,
        "audit_events": [serialize_doc(row) for row in audit_rows],
        "impersonation_logs": [serialize_doc(row) for row in impersonation_rows],
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
        {"$set": {"status": "active", "dunning_state": "current", "first_payment_failed_at": None, "last_payment_failed_at": None, "last_payment_succeeded_at": now, "updated_at": now}},
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
        raise PlatformAdminError("invalid_threshold", "Review day must be a positive number or null", 400)
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise PlatformAdminError("tenant_not_found", "Tenant not found", 404)
    now = _now_iso()
    updated = await db.tenant_billing_accounts.update_one(
        {"tenant_id": tenant_id},
        {"$set": {"dunning_review_after_days": threshold, "updated_at": now}},
    )
    if updated.matched_count == 0:
        account = TenantBillingAccount(
            tenant_id=tenant_id,
            billing_email=tenant.get("owner_email"),
            status="pending",
        ).model_dump()
        account["dunning_review_after_days"] = threshold
        account["updated_at"] = now
        await db.tenant_billing_accounts.insert_one(prepare_for_mongo(account))
    await _audit(user, tenant_id=tenant_id, action="dunning.threshold_set", entity_type="tenant", entity_id=tenant_id, summary=f"Set dunning review day for {tenant.get('name')}", request=request, metadata={"review_after_days": threshold})
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


async def _owners_by_tenant(tenant_ids: list[str]) -> dict[str, dict[str, Any]]:
    owners: dict[str, dict[str, Any]] = {}
    if not tenant_ids:
        return owners
    for chunk in _chunked(sorted({tenant_id for tenant_id in tenant_ids if tenant_id})):
        rows = await db.users.find(
            {"tenant_id": {"$in": chunk}, "$or": [{"role": "owner"}, {"is_owner": True}]},
            {"_id": 0, "tenant_id": 1, "email": 1, "full_name": 1, "created_at": 1},
        ).sort("created_at", 1).to_list(None)
        for row in rows:
            owners.setdefault(row["tenant_id"], row)
    return owners


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
    tenants = await db.tenants.find(q, {"_id": 0}).to_list(None)
    owner_by_tenant = await _owners_by_tenant([tenant["id"] for tenant in tenants if tenant.get("id")])
    recipients: list[dict] = []
    seen: set[str] = set()
    for tenant in tenants:
        owner = owner_by_tenant.get(tenant["id"])
        email = (tenant.get("owner_email") or (owner or {}).get("email") or "").strip()
        key = email.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        recipients.append({"tenant_id": tenant["id"], "email": email, "tenant": {**tenant, "owner_email": email, "owner_name": (owner or {}).get("full_name")}})
    return recipients


async def broadcast_counts(user: dict) -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_BROADCAST_WRITE.value})
    tenants = await db.tenants.find({}, {"_id": 0, "id": 1, "name": 1, "owner_email": 1, "is_active": 1}).to_list(None)
    owner_by_tenant = await _owners_by_tenant([tenant["id"] for tenant in tenants if tenant.get("id")])
    founder_ids = set(await db.founder_tenant_contracts.distinct("tenant_id", {"founder_status": {"$in": ["pending", "active", "grace"]}}))
    founder_ids.update(await db.users.distinct("tenant_id", {"is_founder": True}))

    def count_for(predicate) -> int:
        seen: set[str] = set()
        for tenant in tenants:
            if not predicate(tenant):
                continue
            owner = owner_by_tenant.get(tenant["id"])
            email = (tenant.get("owner_email") or (owner or {}).get("email") or "").strip().lower()
            if email:
                seen.add(email)
        return len(seen)

    counts = {
        "all_owners": count_for(lambda _tenant: True),
        "active_only": count_for(lambda tenant: tenant.get("is_active") is not False),
        "suspended_only": count_for(lambda tenant: tenant.get("is_active") is False),
        "founders_only": count_for(lambda tenant: tenant.get("id") in founder_ids),
    }
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


async def email_logs_summary(user: dict, *, tenant_id: Optional[str] = None, status: Optional[str] = None, to_email: Optional[str] = None, since: Optional[str] = None) -> dict:
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
    total = await db.email_logs.count_documents(q)
    counts = {status: await db.email_logs.count_documents({**q, "status": status}) for status in ("sent", "delivered", "failed", "skipped", "queued")}
    log_ids = await db.email_logs.distinct("id", q) if total else []
    activity_scope: dict[str, Any] = {"email_log_id": {"$in": log_ids}} if log_ids else {"email_log_id": "__none__"}
    bounced = len(await db.email_activity.distinct("email_log_id", {**activity_scope, "event": {"$in": ["bounce", "dropped"]}}))
    complaints = len(await db.email_activity.distinct("email_log_id", {**activity_scope, "event": "spamreport"}))
    delivered_events = len(await db.email_activity.distinct("email_log_id", {**activity_scope, "event": "delivered"}))
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


async def list_audit_log(
    user: dict,
    *,
    action: Optional[str] = None,
    actor_email: Optional[str] = None,
    tenant_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 200,
) -> dict:
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
    date_filter: dict[str, str] = {}
    if since:
        date_filter["$gte"] = since
    if until:
        date_filter["$lte"] = until
    if date_filter:
        q["created_at"] = date_filter
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


def _date_bounds(range_key: str, custom_start: Optional[str] = None, custom_end: Optional[str] = None) -> tuple[str, str]:
    now = utc_now()
    if range_key == "custom" and custom_start:
        start = datetime.fromisoformat(str(custom_start).replace("Z", "+00:00"))
        end_raw = custom_end or now.isoformat()
        end = datetime.fromisoformat(str(end_raw).replace("Z", "+00:00"))
        return start.isoformat(), end.isoformat()
    if range_key == "yesterday":
        day = now - timedelta(days=1)
        start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start.isoformat(), end.isoformat()
    days = {"today": 0, "7d": 7, "14d": 14, "30d": 30}.get(range_key, 30)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0) if days == 0 else now - timedelta(days=days)
    return start.isoformat(), now.isoformat()


def _referrer_source(referrer: str | None) -> str:
    value = (referrer or "").lower()
    if not value:
        return "Direct"
    if "google" in value:
        return "Google"
    if "facebook" in value or "fb.com" in value:
        return "Facebook"
    if "instagram" in value:
        return "Instagram"
    if "twitter" in value or "t.co" in value or "x.com" in value:
        return "Twitter/X"
    if "linkedin" in value:
        return "LinkedIn"
    if "localhost" in value or "127.0.0.1" in value:
        return "Internal/Test"
    if "mail" in value or "email" in value or "newsletter" in value:
        return "Email"
    return "Other"


async def analytics(user: dict, *, range_key: str = "30d", custom_start: Optional[str] = None, custom_end: Optional[str] = None) -> dict:
    require_platform_admin(user, extra_permissions={PlatformPerm.PLATFORM_ANALYTICS_READ.value})
    start, end = _date_bounds(range_key, custom_start=custom_start, custom_end=custom_end)
    date_filter = {"$gte": start, "$lte": end}
    tenants = await db.tenants.count_documents({})
    users = await db.users.count_documents({})
    active_users = await db.users.count_documents({"is_active": True})
    suspended_tenants = await db.tenants.count_documents({"is_active": False})
    new_users = await db.users.count_documents({"created_at": date_filter})
    new_orders = await db.orders.count_documents({"created_at": date_filter})
    new_quotes = await db.quotes.count_documents({"created_at": date_filter})
    new_webstores = await db.webstores.count_documents({"created_at": date_filter})
    total_orders = await db.orders.count_documents({})
    total_quotes = await db.quotes.count_documents({})
    total_webstores = await db.webstores.count_documents({})
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
    page_views = await db.analytics_events.count_documents({"timestamp": date_filter, "event_type": "page_view"})
    logged_in_events = await db.analytics_events.count_documents({"timestamp": date_filter, "user_id": {"$nin": [None, ""]}})
    anonymous_events = max(0, events - logged_in_events)
    bot_events = await db.analytics_events.count_documents({"timestamp": date_filter, "is_bot": True})
    errors = await db.analytics_events.count_documents({"timestamp": date_filter, "event_type": {"$in": ["error", "api_error", "frontend_error"]}})
    suspicious = await db.analytics_events.count_documents({"timestamp": date_filter, "$or": [{"is_bot": True}, {"is_suspicious": True}]})
    route_rows = await db.analytics_events.aggregate([
        {"$match": {"timestamp": date_filter, "route": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$route", "events": {"$sum": 1}, "requests": {"$sum": 1}, "sessions": {"$addToSet": "$session_id"}, "visitors": {"$addToSet": "$visitor_id"}, "users": {"$addToSet": "$user_id"}, "last_accessed": {"$max": "$timestamp"}}},
        {"$project": {"route": "$_id", "events": 1, "requests": 1, "sessions": {"$size": "$sessions"}, "visitors": {"$size": "$visitors"}, "unique_visitors": {"$size": "$visitors"}, "unique_users": {"$size": "$users"}, "last_accessed": 1, "_id": 0}},
        {"$sort": {"events": -1}},
        {"$limit": 50},
    ]).to_list(50)
    referrer_rows = await db.analytics_events.aggregate([
        {"$match": {"timestamp": date_filter, "referrer": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$referrer", "events": {"$sum": 1}, "visitors": {"$addToSet": "$visitor_id"}}},
        {"$project": {"referrer": "$_id", "events": 1, "visitors": {"$size": "$visitors"}, "_id": 0}},
        {"$sort": {"events": -1}},
        {"$limit": 25},
    ]).to_list(25)
    referrer_sources: dict[str, dict[str, Any]] = {}
    for row in referrer_rows:
        source = _referrer_source(row.get("referrer"))
        referrer_sources.setdefault(source, {"source": source, "requests": 0, "unique_visitors": 0, "logged_in": 0})
        referrer_sources[source]["requests"] += row.get("events", 0)
        referrer_sources[source]["unique_visitors"] += row.get("visitors", 0)
    total_referrer_requests = sum(row["requests"] for row in referrer_sources.values()) or 1
    referrer_source_rows = []
    for row in sorted(referrer_sources.values(), key=lambda item: -item["requests"]):
        row["pct"] = round((row["requests"] / total_referrer_requests) * 100, 1)
        referrer_source_rows.append(row)
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
    avg_req_per_session = round(events / max(sessions_total, 1), 1)
    user_rows = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).limit(100).to_list(100)
    analytics_users = []
    for row in user_rows:
        tenant_id = row.get("tenant_id")
        user_id = row.get("id")
        tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0, "name": 1})
        analytics_users.append({
            "id": user_id,
            "full_name": row.get("full_name"),
            "email": row.get("email"),
            "role": row.get("platform_role") or row.get("role"),
            "company_name": (tenant or {}).get("name"),
            "tenant_id": tenant_id,
            "is_active": row.get("is_active", True),
            "created_at": row.get("created_at"),
            "last_login_at": row.get("last_login_at"),
            "orders": await db.orders.count_documents({"tenant_id": tenant_id, "created_at": date_filter}) if tenant_id else 0,
            "quotes": await db.quotes.count_documents({"tenant_id": tenant_id, "created_at": date_filter}) if tenant_id else 0,
            "webstores": await db.webstores.count_documents({"tenant_id": tenant_id, "created_at": date_filter}) if tenant_id else 0,
            "admin_actions": await db.audit_events.count_documents({"actor_user_id": user_id, "created_at": date_filter}) if user_id else 0,
            "page_views": await db.analytics_events.count_documents({"user_id": user_id, "event_type": "page_view", "timestamp": date_filter}) if user_id else 0,
        })
    session_rows = await db.analytics_events.aggregate([
        {"$match": {"timestamp": date_filter}},
        {"$group": {"_id": "$session_id", "visitor_id": {"$first": "$visitor_id"}, "user_id": {"$first": "$user_id"}, "ip_address": {"$first": "$ip_address"}, "user_agent": {"$first": "$user_agent"}, "referrer": {"$first": "$referrer"}, "first_seen": {"$min": "$timestamp"}, "last_seen": {"$max": "$timestamp"}, "requests": {"$sum": 1}, "is_bot": {"$max": "$is_bot"}, "routes": {"$addToSet": "$route"}}},
        {"$project": {"session_id": "$_id", "visitor_id": 1, "user_id": 1, "ip_address": 1, "user_agent": 1, "referrer": 1, "first_seen": 1, "last_seen": 1, "requests": 1, "is_bot": 1, "is_logged_in": {"$cond": [{"$ifNull": ["$user_id", False]}, True, False]}, "route_count": {"$size": "$routes"}, "_id": 0}},
        {"$sort": {"last_seen": -1}},
        {"$limit": 100},
    ]).to_list(100)
    error_rows = await db.analytics_events.aggregate([
        {"$match": {"timestamp": date_filter, "event_type": {"$in": ["error", "api_error", "frontend_error"]}}},
        {"$group": {"_id": {"event_type": "$event_type", "route": "$route", "message": {"$ifNull": ["$metadata.message", "Unknown"]}}, "count": {"$sum": 1}, "last_occurred": {"$max": "$timestamp"}, "first_occurred": {"$min": "$timestamp"}, "users": {"$addToSet": "$user_id"}}},
        {"$project": {"event_type": "$_id.event_type", "route": "$_id.route", "message": "$_id.message", "count": 1, "last_occurred": 1, "first_occurred": 1, "affected_users": {"$size": "$users"}, "_id": 0}},
        {"$sort": {"count": -1}},
        {"$limit": 100},
    ]).to_list(100)
    suspicious_rows = await db.analytics_events.aggregate([
        {"$match": {"timestamp": date_filter, "$or": [{"is_bot": True}, {"is_suspicious": True}]}},
        {"$group": {"_id": {"ip_address": "$ip_address", "user_agent": "$user_agent"}, "requests": {"$sum": 1}, "session_ids": {"$addToSet": "$session_id"}, "routes": {"$addToSet": "$route"}, "first_seen": {"$min": "$timestamp"}, "last_seen": {"$max": "$timestamp"}, "is_bot": {"$max": "$is_bot"}, "is_suspicious": {"$max": "$is_suspicious"}}},
        {"$project": {"ip_address": "$_id.ip_address", "user_agent": "$_id.user_agent", "requests": 1, "session_count": {"$size": "$session_ids"}, "route_count": {"$size": "$routes"}, "first_seen": 1, "last_seen": 1, "is_bot": 1, "is_suspicious": 1, "label": {"$cond": ["$is_bot", "Likely Bot", "Suspicious Path"]}, "_id": 0}},
        {"$sort": {"requests": -1}},
        {"$limit": 50},
    ]).to_list(50)
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
            "new_webstores": new_webstores,
            "total_orders": total_orders,
            "total_quotes": total_quotes,
            "total_webstores": total_webstores,
            "audit_actions": audit_actions_count,
            "subscriptions": subscriptions,
            "trialing_subscriptions": trialing,
            "active_subscriptions": active_subs,
            "dunning_subscriptions": dunning,
            "analytics_events": events,
            "total_events": events,
            "page_views": page_views,
            "total_sessions": sessions_total,
            "total_visitors": visitors_total,
            "logged_in_visits": logged_in_events,
            "anonymous_visits": anonymous_events,
            "bot_events": bot_events,
            "avg_req_per_session": avg_req_per_session,
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
        "referrer_sources": referrer_source_rows,
        "users": analytics_users,
        "sessions_detail": session_rows,
        "errors_detail": {
            "errors": error_rows,
            "total_errors": errors,
            "frontend_errors": await db.analytics_events.count_documents({"timestamp": date_filter, "event_type": "frontend_error"}),
            "api_errors": await db.analytics_events.count_documents({"timestamp": date_filter, "event_type": "api_error"}),
        },
        "suspicious_detail": {
            "suspicious": suspicious_rows,
            "total_bot": bot_events,
            "total_suspicious": suspicious,
            "total_events": events,
            "bot_pct": round((bot_events / max(events, 1)) * 100, 1),
        },
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
