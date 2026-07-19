"""EC13 tenant commercial billing service."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.commercial_catalog import PlatformFeeTransactionContract
from ..models.tenant_billing import (
    BillingPortalSessionRecord,
    CheckoutSessionRecord,
    SetupPackagePurchase,
    TenantBillingAccount,
    TenantSubscription,
    TrialRecord,
)
from . import commercial_entitlements, stripe_billing
from .activity import record_activity_with_audit
from .commercial_catalog import require_platform_admin


class TenantBillingError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


SETUP_PACKAGE_PRICES_CENTS = {
    "diy": 0,
    "founder_kickstart": 29900,
    "standard": 49900,
    "full": 99900,
    "white_glove": 199900,
}


def _now_iso() -> str:
    return utc_now().isoformat()


def _parse_iso(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _is_platform_admin(user: dict) -> bool:
    return bool(
        user.get("platform_admin")
        or user.get("platform_role") in {"admin", "owner"}
        or "platform:admin" in set(user.get("permissions") or [])
        or "platform:subscription_admin" in set(user.get("permissions") or [])
    )


def _is_tenant_billing_admin(user: dict) -> bool:
    return user.get("role") in {"owner", "admin"}


def _require_tenant_billing_admin(user: dict, tenant_id: str) -> None:
    if _is_platform_admin(user):
        return
    if user.get("tenant_id") != tenant_id or not _is_tenant_billing_admin(user):
        raise TenantBillingError("subscription_manage_required", "Tenant billing admin access is required", 403)


async def _audit(user: dict, tenant_id: str, action: str, entity_type: str, entity_id: str, summary: str, metadata: Optional[dict] = None) -> None:
    await record_activity_with_audit(
        tenant_id=tenant_id,
        actor_user_id=user["id"],
        actor_email=user.get("email", "billing"),
        module="commercial_billing",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        metadata=metadata or {},
    )


async def ensure_billing_account(user: dict, *, tenant_id: Optional[str] = None, billing_email: Optional[str] = None, terms_version: Optional[str] = None) -> dict:
    target_tenant_id = tenant_id or user["tenant_id"]
    _require_tenant_billing_admin(user, target_tenant_id)
    tenant = await db.tenants.find_one({"id": target_tenant_id}, {"_id": 0})
    if not tenant:
        raise TenantBillingError("tenant_not_found", "Tenant not found", 404)
    existing = await db.tenant_billing_accounts.find_one({"tenant_id": target_tenant_id}, {"_id": 0})
    if existing:
        return serialize_doc(existing)
    doc = TenantBillingAccount(
        tenant_id=target_tenant_id,
        billing_owner_user_id=user["id"] if user.get("tenant_id") == target_tenant_id else None,
        billing_email=billing_email or user.get("email"),
        terms_version=terms_version,
    ).model_dump()
    await db.tenant_billing_accounts.insert_one(prepare_for_mongo(doc))
    await _audit(user, target_tenant_id, "commercial.billing_account_created", "tenant_billing_account", doc["id"], "Tenant billing account created")
    return serialize_doc(doc)


async def get_billing_account_for_user(user: dict, *, tenant_id: Optional[str] = None) -> dict:
    target_tenant_id = tenant_id or user["tenant_id"]
    if target_tenant_id != user["tenant_id"] and not _is_platform_admin(user):
        raise TenantBillingError("tenant_scope_forbidden", "Billing account lookup is tenant-scoped", 403)
    doc = await db.tenant_billing_accounts.find_one({"tenant_id": target_tenant_id}, {"_id": 0})
    if not doc:
        raise TenantBillingError("billing_account_not_found", "Billing account not found", 404)
    return serialize_doc(doc)


async def billing_state(user: dict, *, tenant_id: Optional[str] = None) -> dict:
    account = await get_billing_account_for_user(user, tenant_id=tenant_id)
    sub = None
    if account.get("current_subscription_id"):
        sub = await db.tenant_subscriptions.find_one({"tenant_id": account["tenant_id"], "id": account["current_subscription_id"]}, {"_id": 0})
    trial = None
    if account.get("trial_record_id"):
        trial = await db.trial_records.find_one({"tenant_id": account["tenant_id"], "id": account["trial_record_id"]}, {"_id": 0})
    setup_cursor = db.setup_package_purchases.find({"tenant_id": account["tenant_id"]}, {"_id": 0}).sort("created_at", -1)
    return {
        "billing_account": account,
        "subscription": serialize_doc(sub),
        "trial": serialize_doc(trial),
        "setup_purchases": [serialize_doc(doc) async for doc in setup_cursor],
    }


async def _account(tenant_id: str) -> dict:
    doc = await db.tenant_billing_accounts.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not doc:
        raise TenantBillingError("billing_account_not_found", "Create a billing account first", 404)
    return doc


async def _price(price_id: str) -> dict:
    doc = await db.commercial_prices.find_one({"id": price_id}, {"_id": 0})
    if not doc:
        raise TenantBillingError("price_not_found", "Commercial price not found", 404)
    return doc


async def _product(product_id: str) -> dict:
    doc = await db.commercial_products.find_one({"id": product_id}, {"_id": 0})
    if not doc:
        raise TenantBillingError("product_not_found", "Commercial product not found", 404)
    return doc


async def _require_runtime_price(price_id: str) -> tuple[dict, dict, dict]:
    price = await _price(price_id)
    product = await _product(price["product_id"])
    catalog = await db.commercial_catalog_versions.find_one({"id": price["catalog_version_id"]}, {"_id": 0})
    if not catalog or catalog.get("status") != "published":
        raise TenantBillingError("catalog_not_published", "Checkout requires a published catalog price", 409)
    if product.get("status") != "active" or not product.get("publishable"):
        raise TenantBillingError("product_not_purchasable", "Product is not available for purchase", 409)
    if not (price.get("is_active") and price.get("is_public") and price.get("approved_by_owner")):
        raise TenantBillingError("price_not_purchasable", "Price is not active, public, and owner-approved", 409)
    return price, product, catalog


async def start_free_trial(user: dict) -> dict:
    _require_tenant_billing_admin(user, user["tenant_id"])
    account = await ensure_billing_account(user)
    existing = await db.trial_records.find_one({"tenant_id": user["tenant_id"], "trial_kind": "free"}, {"_id": 0})
    if existing:
        raise TenantBillingError("free_trial_already_used", "Free trial already exists for this tenant", 409)
    now = utc_now()
    trial = TrialRecord(
        tenant_id=user["tenant_id"],
        billing_account_id=account["id"],
        trial_kind="free",
        status="free_active",
        starts_at=now.isoformat(),
        ends_at=(now + timedelta(hours=48)).isoformat(),
        credit_allotment=25,
        created_by_user_id=user["id"],
    ).model_dump()
    await db.trial_records.insert_one(prepare_for_mongo(trial))
    await db.tenant_billing_accounts.update_one(
        {"id": account["id"]},
        {"$set": {"status": "trialing", "trial_record_id": trial["id"], "updated_at": _now_iso()}},
    )
    await commercial_entitlements.project_entitlements_for_tenant(tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user.get("email", "billing"))
    await _audit(user, user["tenant_id"], "commercial.free_trial_started", "trial_record", trial["id"], "Free trial started")
    return serialize_doc(trial)


async def expire_trials(*, as_of: Optional[datetime] = None) -> dict:
    now = as_of or utc_now()
    changed = 0
    async for trial in db.trial_records.find({"status": {"$in": ["free_active", "extended_active"]}}, {"_id": 0}):
        ends_at = _parse_iso(trial.get("ends_at"))
        if ends_at and ends_at <= now:
            new_status = "free_expired" if trial["trial_kind"] == "free" else "extended_expired"
            await db.trial_records.update_one({"id": trial["id"]}, {"$set": {"status": new_status, "updated_at": now.isoformat()}})
            await commercial_entitlements.project_entitlements_for_tenant(tenant_id=trial["tenant_id"])
            changed += 1
    return {"expired": changed}


async def start_extended_trial_checkout(user: dict, *, idempotency_key: str, success_url: str, cancel_url: str) -> dict:
    _require_tenant_billing_admin(user, user["tenant_id"])
    account = await ensure_billing_account(user)
    existing = await db.trial_records.find_one({"tenant_id": user["tenant_id"], "trial_kind": "extended", "status": {"$ne": "forfeited"}}, {"_id": 0})
    if existing:
        raise TenantBillingError("extended_trial_already_exists", "Extended trial already exists for this tenant", 409)
    session = await create_checkout_session(
        user,
        session_type="extended_trial",
        idempotency_key=idempotency_key,
        success_url=success_url,
        cancel_url=cancel_url,
        amount_cents=2000,
        price_id=None,
        setup_package_key=None,
    )
    now = utc_now()
    trial = TrialRecord(
        tenant_id=user["tenant_id"],
        billing_account_id=account["id"],
        trial_kind="extended",
        status="extended_pending_payment",
        starts_at=now.isoformat(),
        ends_at=(now + timedelta(days=7)).isoformat(),
        credit_allotment=75,
        conversion_credit_cents=2000,
        conversion_credit_expires_at=(now + timedelta(days=21)).isoformat(),
        checkout_session_id=session["id"],
        created_by_user_id=user["id"],
    ).model_dump()
    await db.trial_records.insert_one(prepare_for_mongo(trial))
    await _audit(user, user["tenant_id"], "commercial.extended_trial_checkout_created", "checkout_session", session["id"], "Extended trial checkout created")
    return {"checkout_session": session, "trial": serialize_doc(trial)}


async def create_checkout_session(
    user: dict,
    *,
    session_type: str,
    idempotency_key: str,
    success_url: str,
    cancel_url: str,
    price_id: Optional[str] = None,
    amount_cents: Optional[int] = None,
    setup_package_key: Optional[str] = None,
) -> dict:
    _require_tenant_billing_admin(user, user["tenant_id"])
    account = await ensure_billing_account(user)
    existing = await db.checkout_session_records.find_one(
        {"tenant_id": user["tenant_id"], "idempotency_key": idempotency_key},
        {"_id": 0},
    )
    if existing:
        return serialize_doc(existing)
    pending = await db.checkout_session_records.find_one(
        {"tenant_id": user["tenant_id"], "session_type": session_type, "status": "created"},
        {"_id": 0},
    )
    if pending and session_type in {"subscription", "setup_package", "extended_trial"}:
        raise TenantBillingError("pending_checkout_exists", "A pending checkout already exists for this tenant and purchase type", 409)

    price = product = None
    currency = "usd"
    mode = "payment"
    if price_id:
        price, product, _ = await _require_runtime_price(price_id)
        currency = price.get("currency", "usd")
        amount_cents = price["amount_cents"]
        mode = "subscription" if price["billing_interval"] in {"monthly", "annual"} and session_type == "subscription" else "payment"
    elif amount_cents is not None:
        if not isinstance(amount_cents, int) or amount_cents < 0:
            raise TenantBillingError("integer_cents_required", "amount_cents must be an integer number of cents", 400)
    else:
        raise TenantBillingError("price_or_amount_required", "A price_id or amount_cents is required", 400)

    doc = CheckoutSessionRecord(
        tenant_id=user["tenant_id"],
        billing_account_id=account["id"],
        session_type=session_type,  # type: ignore[arg-type]
        product_id=product["id"] if product else None,
        price_id=price_id,
        setup_package_key=setup_package_key,
        amount_cents=amount_cents,
        currency=currency,
        idempotency_key=idempotency_key,
        created_by_user_id=user["id"],
    ).model_dump()
    checkout = stripe_billing.create_checkout_session(
        tenant_id=user["tenant_id"],
        internal_checkout_session_id=doc["id"],
        session_type=session_type,
        mode=mode,
        price_id=price.get("stripe_price_id") if price else None,
        amount_cents=amount_cents,
        currency=currency,
        billing_interval=price.get("billing_interval") if price else None,
        success_url=success_url,
        cancel_url=cancel_url,
        idempotency_key=idempotency_key,
        customer_email=account.get("billing_email") or user.get("email"),
        stripe_customer_id=account.get("stripe_customer_id"),
    )
    doc["stripe_checkout_session_id"] = checkout["id"]
    doc["checkout_url"] = checkout["url"]
    if checkout.get("expires_at"):
        doc["expires_at"] = str(checkout["expires_at"])
    try:
        await db.checkout_session_records.insert_one(prepare_for_mongo(doc))
    except DuplicateKeyError:
        existing = await db.checkout_session_records.find_one({"tenant_id": user["tenant_id"], "idempotency_key": idempotency_key}, {"_id": 0})
        if existing:
            return serialize_doc(existing)
        raise
    await _audit(user, user["tenant_id"], "commercial.checkout_created", "checkout_session", doc["id"], "Checkout session created", {"session_type": session_type})
    return serialize_doc(doc)


async def create_setup_package_checkout(user: dict, *, package_key: str, idempotency_key: str, success_url: str, cancel_url: str) -> dict:
    if package_key not in SETUP_PACKAGE_PRICES_CENTS:
        raise TenantBillingError("invalid_setup_package", "Unknown setup package", 400)
    session = await create_checkout_session(
        user,
        session_type="setup_package",
        idempotency_key=idempotency_key,
        success_url=success_url,
        cancel_url=cancel_url,
        amount_cents=SETUP_PACKAGE_PRICES_CENTS[package_key],
        setup_package_key=package_key,
    )
    account = await _account(user["tenant_id"])
    existing = await db.setup_package_purchases.find_one({"checkout_session_id": session["id"]}, {"_id": 0})
    if existing:
        return {"checkout_session": session, "setup_purchase": serialize_doc(existing)}
    purchase = SetupPackagePurchase(
        tenant_id=user["tenant_id"],
        billing_account_id=account["id"],
        package_key=package_key,
        checkout_session_id=session["id"],
        amount_cents=SETUP_PACKAGE_PRICES_CENTS[package_key],
        status="paid" if SETUP_PACKAGE_PRICES_CENTS[package_key] == 0 else "pending_payment",
        paid_at=_now_iso() if SETUP_PACKAGE_PRICES_CENTS[package_key] == 0 else None,
    ).model_dump()
    await db.setup_package_purchases.insert_one(prepare_for_mongo(purchase))
    return {"checkout_session": session, "setup_purchase": serialize_doc(purchase)}


async def waive_setup_package(user: dict, *, tenant_id: str, package_key: str, reason: str) -> dict:
    try:
        require_platform_admin(user)
    except Exception:
        raise TenantBillingError("platform_admin_required", "Platform admin access is required", 403)
    if package_key not in SETUP_PACKAGE_PRICES_CENTS:
        raise TenantBillingError("invalid_setup_package", "Unknown setup package", 400)
    clean_reason = (reason or "").strip()
    if not clean_reason:
        raise TenantBillingError("waiver_reason_required", "A setup package waiver requires a reason", 400)
    account = await _account(tenant_id)
    purchase = SetupPackagePurchase(
        tenant_id=tenant_id,
        billing_account_id=account["id"],
        package_key=package_key,
        status="waived",
        amount_cents=SETUP_PACKAGE_PRICES_CENTS[package_key],
        waived_by_user_id=user["id"],
        waiver_reason=clean_reason,
    ).model_dump()
    await db.setup_package_purchases.insert_one(prepare_for_mongo(purchase))
    await _audit(user, tenant_id, "commercial.setup_package_waived", "setup_package_purchase", purchase["id"], "Setup package waived", {"package_key": package_key, "reason": clean_reason})
    return serialize_doc(purchase)


async def complete_checkout_session(*, stripe_checkout_session_id: str, stripe_subscription_id: Optional[str] = None, stripe_customer_id: Optional[str] = None) -> dict:
    session = await db.checkout_session_records.find_one({"stripe_checkout_session_id": stripe_checkout_session_id}, {"_id": 0})
    if not session:
        raise TenantBillingError("checkout_session_not_found", "Checkout session not found", 404)
    if session["status"] == "completed":
        return serialize_doc(session)
    now = utc_now()
    await db.checkout_session_records.update_one({"id": session["id"]}, {"$set": {"status": "completed", "completed_at": now.isoformat(), "updated_at": now.isoformat()}})
    tenant_id = session["tenant_id"]
    if stripe_customer_id:
        await db.tenant_billing_accounts.update_one({"id": session["billing_account_id"]}, {"$set": {"stripe_customer_id": stripe_customer_id, "updated_at": now.isoformat()}})

    if session["session_type"] == "subscription":
        price, product, catalog = await _require_runtime_price(session["price_id"])
        interval_days = 365 if price["billing_interval"] == "annual" else 30
        founder = await db.founder_tenant_contracts.find_one({"tenant_id": tenant_id, "founder_status": {"$in": ["pending", "active", "grace"]}}, {"_id": 0})
        sub = TenantSubscription(
            tenant_id=tenant_id,
            billing_account_id=session["billing_account_id"],
            catalog_version_id=catalog["id"],
            plan_product_id=product["id"],
            price_id=price["id"],
            billing_interval=price["billing_interval"],
            status="active",
            dunning_state="current",
            stripe_subscription_id=stripe_subscription_id,
            stripe_customer_id=stripe_customer_id,
            founder_contract_id=founder.get("id") if founder else None,
            current_period_start=now.isoformat(),
            current_period_end=(now + timedelta(days=interval_days)).isoformat(),
        ).model_dump()
        await db.tenant_subscriptions.insert_one(prepare_for_mongo(sub))
        await db.tenant_billing_accounts.update_one(
            {"id": session["billing_account_id"]},
            {"$set": {"status": "active", "current_subscription_id": sub["id"], "updated_at": now.isoformat()}},
        )
        await commercial_entitlements.project_entitlements_for_tenant(tenant_id=tenant_id)
    elif session["session_type"] == "setup_package":
        await db.setup_package_purchases.update_one(
            {"checkout_session_id": session["id"]},
            {"$set": {"status": "paid", "paid_at": now.isoformat(), "updated_at": now.isoformat()}},
        )
    elif session["session_type"] == "extended_trial":
        await db.trial_records.update_one(
            {"checkout_session_id": session["id"]},
            {"$set": {"status": "extended_active", "starts_at": now.isoformat(), "ends_at": (now + timedelta(days=7)).isoformat(), "updated_at": now.isoformat()}},
        )
        await db.tenant_billing_accounts.update_one(
            {"id": session["billing_account_id"]},
            {"$set": {"status": "trialing", "updated_at": now.isoformat()}},
        )
        await commercial_entitlements.project_entitlements_for_tenant(tenant_id=tenant_id)
    return serialize_doc(await db.checkout_session_records.find_one({"id": session["id"]}, {"_id": 0}))


async def create_billing_portal_session(user: dict, *, return_url: str) -> dict:
    _require_tenant_billing_admin(user, user["tenant_id"])
    account = await _account(user["tenant_id"])
    portal = stripe_billing.create_billing_portal_session(
        tenant_id=user["tenant_id"],
        billing_account_id=account["id"],
        stripe_customer_id=account.get("stripe_customer_id"),
        return_url=return_url,
    )
    doc = BillingPortalSessionRecord(
        tenant_id=user["tenant_id"],
        billing_account_id=account["id"],
        stripe_billing_portal_session_id=portal["id"],
        portal_url=portal["url"],
        return_url=return_url,
        created_by_user_id=user["id"],
    ).model_dump()
    await db.billing_portal_session_records.insert_one(prepare_for_mongo(doc))
    await _audit(user, user["tenant_id"], "commercial.billing_portal_created", "billing_portal_session", doc["id"], "Billing portal session created")
    return serialize_doc(doc)


async def schedule_cancellation(user: dict, *, subscription_id: str, reason: Optional[str] = None) -> dict:
    sub = await db.tenant_subscriptions.find_one({"tenant_id": user["tenant_id"], "id": subscription_id}, {"_id": 0})
    if not sub:
        raise TenantBillingError("subscription_not_found", "Subscription not found", 404)
    _require_tenant_billing_admin(user, sub["tenant_id"])
    patch = {"status": "cancellation_scheduled", "cancel_at_period_end": True, "cancellation_reason": reason, "updated_at": _now_iso()}
    await db.tenant_subscriptions.update_one({"id": subscription_id}, {"$set": patch})
    await _audit(user, sub["tenant_id"], "commercial.subscription_cancellation_scheduled", "tenant_subscription", subscription_id, "Subscription cancellation scheduled")
    return serialize_doc(await db.tenant_subscriptions.find_one({"id": subscription_id}, {"_id": 0}))


async def schedule_downgrade(user: dict, *, subscription_id: str, price_id: str) -> dict:
    sub = await db.tenant_subscriptions.find_one({"tenant_id": user["tenant_id"], "id": subscription_id}, {"_id": 0})
    if not sub:
        raise TenantBillingError("subscription_not_found", "Subscription not found", 404)
    _require_tenant_billing_admin(user, sub["tenant_id"])
    price, product, _ = await _require_runtime_price(price_id)
    patch = {
        "scheduled_downgrade_price_id": price["id"],
        "scheduled_downgrade_product_id": product["id"],
        "scheduled_change_at": sub.get("current_period_end"),
        "updated_at": _now_iso(),
    }
    await db.tenant_subscriptions.update_one({"id": subscription_id}, {"$set": patch})
    await _audit(user, sub["tenant_id"], "commercial.subscription_downgrade_scheduled", "tenant_subscription", subscription_id, "Subscription downgrade scheduled")
    return serialize_doc(await db.tenant_subscriptions.find_one({"id": subscription_id}, {"_id": 0}))


def dunning_state_for(first_payment_failed_at: Optional[str], *, as_of: Optional[datetime] = None, suspended: bool = False, manual_grace_until: Optional[str] = None) -> str:
    if suspended:
        return "suspended"
    now = as_of or utc_now()
    grace_until = _parse_iso(manual_grace_until)
    if grace_until and grace_until >= now:
        return "manually_extended"
    failed_at = _parse_iso(first_payment_failed_at)
    if not failed_at:
        return "current"
    age_days = max(0, (now - failed_at).days)
    if age_days <= 7:
        return "day_1_7_warning"
    if age_days <= 14:
        return "day_8_14_soft_restriction"
    return "eligible_for_suspension"


async def handle_invoice_payment_failed(*, stripe_subscription_id: str, occurred_at: Optional[datetime] = None) -> dict:
    sub = await db.tenant_subscriptions.find_one({"stripe_subscription_id": stripe_subscription_id}, {"_id": 0})
    if not sub:
        raise TenantBillingError("subscription_not_found", "Subscription not found", 404)
    processed_at = utc_now()
    failure_at = occurred_at or processed_at
    first_failed_at = sub.get("first_payment_failed_at") or failure_at.isoformat()
    dunning_state = dunning_state_for(first_failed_at, as_of=processed_at, manual_grace_until=sub.get("manual_grace_until"))
    await db.tenant_subscriptions.update_one(
        {"id": sub["id"]},
        {"$set": {"status": "past_due", "first_payment_failed_at": first_failed_at, "dunning_state": dunning_state, "updated_at": processed_at.isoformat()}},
    )
    await db.tenant_billing_accounts.update_one({"id": sub["billing_account_id"]}, {"$set": {"status": "past_due", "updated_at": processed_at.isoformat()}})
    return serialize_doc(await db.tenant_subscriptions.find_one({"id": sub["id"]}, {"_id": 0}))


async def handle_invoice_payment_succeeded(*, stripe_subscription_id: str, occurred_at: Optional[datetime] = None) -> dict:
    sub = await db.tenant_subscriptions.find_one({"stripe_subscription_id": stripe_subscription_id}, {"_id": 0})
    if not sub:
        raise TenantBillingError("subscription_not_found", "Subscription not found", 404)
    now = occurred_at or utc_now()
    await db.tenant_subscriptions.update_one(
        {"id": sub["id"]},
        {"$set": {"status": "active", "dunning_state": "current", "first_payment_failed_at": None, "last_payment_succeeded_at": now.isoformat(), "updated_at": now.isoformat()}},
    )
    await db.tenant_billing_accounts.update_one({"id": sub["billing_account_id"]}, {"$set": {"status": "active", "updated_at": now.isoformat()}})
    await commercial_entitlements.project_entitlements_for_tenant(tenant_id=sub["tenant_id"])
    return serialize_doc(await db.tenant_subscriptions.find_one({"id": sub["id"]}, {"_id": 0}))


async def apply_manual_grace(user: dict, *, subscription_id: str, grace_until: str, reason: str) -> dict:
    try:
        require_platform_admin(user)
    except Exception:
        raise TenantBillingError("platform_admin_required", "Platform admin access is required", 403)
    sub = await db.tenant_subscriptions.find_one({"id": subscription_id}, {"_id": 0})
    if not sub:
        raise TenantBillingError("subscription_not_found", "Subscription not found", 404)
    if not reason.strip():
        raise TenantBillingError("grace_reason_required", "Manual grace requires a reason", 400)
    patch = {"manual_grace_until": grace_until, "manual_grace_reason": reason.strip(), "dunning_state": "manually_extended", "updated_at": _now_iso()}
    await db.tenant_subscriptions.update_one({"id": subscription_id}, {"$set": patch})
    await _audit(user, sub["tenant_id"], "commercial.manual_grace_applied", "tenant_subscription", subscription_id, "Manual billing grace applied", {"reason": reason.strip()})
    return serialize_doc(await db.tenant_subscriptions.find_one({"id": subscription_id}, {"_id": 0}))


async def suspend_subscription(user: dict, *, subscription_id: str, reason: str) -> dict:
    try:
        require_platform_admin(user)
    except Exception:
        raise TenantBillingError("platform_admin_required", "Platform admin access is required", 403)
    sub = await db.tenant_subscriptions.find_one({"id": subscription_id}, {"_id": 0})
    if not sub:
        raise TenantBillingError("subscription_not_found", "Subscription not found", 404)
    if not reason.strip():
        raise TenantBillingError("suspension_reason_required", "Suspension requires a reason", 400)
    now = _now_iso()
    await db.tenant_subscriptions.update_one({"id": subscription_id}, {"$set": {"dunning_state": "suspended", "status": "unpaid", "updated_at": now}})
    await db.tenant_billing_accounts.update_one({"id": sub["billing_account_id"]}, {"$set": {"status": "suspended", "suspended_at": now, "suspension_reason": reason.strip(), "updated_at": now}})
    await commercial_entitlements.project_entitlements_for_tenant(tenant_id=sub["tenant_id"], actor_user_id=user["id"], actor_email=user.get("email", "platform"))
    await _audit(user, sub["tenant_id"], "commercial.subscription_suspended", "tenant_subscription", subscription_id, "Subscription suspended", {"reason": reason.strip()})
    return serialize_doc(await db.tenant_subscriptions.find_one({"id": subscription_id}, {"_id": 0}))


async def process_stripe_billing_event(event: dict) -> dict:
    event_type = event.get("type")
    obj = ((event.get("data") or {}).get("object") or {})
    if event_type == "checkout.session.completed":
        return {
            "handled": True,
            "checkout_session": await complete_checkout_session(
                stripe_checkout_session_id=obj["id"],
                stripe_subscription_id=obj.get("subscription"),
                stripe_customer_id=obj.get("customer"),
            ),
        }
    if event_type == "invoice.payment_failed":
        sub_id = obj.get("subscription")
        if not sub_id:
            return {"handled": False, "reason": "missing_subscription"}
        return {"handled": True, "subscription": await handle_invoice_payment_failed(stripe_subscription_id=sub_id)}
    if event_type == "invoice.payment_succeeded":
        sub_id = obj.get("subscription")
        if not sub_id:
            return {"handled": False, "reason": "missing_subscription"}
        return {"handled": True, "subscription": await handle_invoice_payment_succeeded(stripe_subscription_id=sub_id)}
    if event_type == "customer.subscription.deleted":
        sub_id = obj.get("id")
        sub = await db.tenant_subscriptions.find_one({"stripe_subscription_id": sub_id}, {"_id": 0})
        if not sub:
            return {"handled": False, "reason": "subscription_not_found"}
        now = _now_iso()
        await db.tenant_subscriptions.update_one({"id": sub["id"]}, {"$set": {"status": "canceled", "canceled_at": now, "updated_at": now}})
        await db.tenant_billing_accounts.update_one({"id": sub["billing_account_id"]}, {"$set": {"status": "canceled", "updated_at": now}})
        await commercial_entitlements.project_entitlements_for_tenant(tenant_id=sub["tenant_id"])
        return {"handled": True}
    return {"handled": False, "reason": "event_not_relevant"}


async def assess_platform_fee_for_payment(user: dict, *, payment_id: str, transaction_type: str = "standard_customer_payment") -> dict:
    try:
        require_platform_admin(user)
    except Exception:
        raise TenantBillingError("platform_admin_required", "Platform admin access is required", 403)
    payment = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not payment:
        raise TenantBillingError("payment_not_found", "Customer payment not found", 404)
    existing = await db.platform_fee_transactions.find_one(
        {
            "tenant_id": payment["tenant_id"],
            "source_transaction_type": "ec4_customer_payment",
            "source_transaction_id": payment_id,
            "reversal_of_fee_transaction_id": None,
        },
        {"_id": 0},
    )
    if existing:
        return serialize_doc(existing)
    founder = await db.founder_tenant_contracts.find_one({"tenant_id": payment["tenant_id"], "founder_status": {"$in": ["pending", "active", "grace"]}}, {"_id": 0})
    account_status = "founder_active" if founder else "ga"
    schedule = await db.platform_fee_schedules.find_one(
        {"account_status": account_status, "transaction_type": transaction_type, "is_active": True},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if not schedule:
        raise TenantBillingError("platform_fee_schedule_not_found", "No active platform-fee schedule exists", 404)
    basis_cents = int(payment["amount_cents"])
    fee_cents = int((Decimal(basis_cents) * Decimal(schedule["rate_basis_points"]) / Decimal(10000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    doc = PlatformFeeTransactionContract(
        tenant_id=payment["tenant_id"],
        source_transaction_type="ec4_customer_payment",
        source_transaction_id=payment_id,
        fee_schedule_id=schedule["id"],
        basis_amount_cents=basis_cents,
        platform_fee_cents=fee_cents,
        currency=payment.get("currency", "usd"),
        snapshot_rate_basis_points=schedule["rate_basis_points"],
        status="assessed",
        created_by_user_id=user["id"],
    ).model_dump()
    await db.platform_fee_transactions.insert_one(prepare_for_mongo(doc))
    await _audit(user, payment["tenant_id"], "commercial.platform_fee_assessed", "platform_fee_transaction", doc["id"], "Platform fee assessed from EC4 payment", {"payment_id": payment_id})
    return serialize_doc(doc)
