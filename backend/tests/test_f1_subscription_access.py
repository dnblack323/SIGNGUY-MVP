"""F1 — Subscription access control.

Uses real signed staff tokens (no dependency overrides) so the commercial
read-only middleware and the route guards run exactly as in production.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.security import create_access_token
from app.deps import get_current_user
from app.services import commercial_entitlements, tenant_billing
from app.services.entitlements import has_entitlement
from server import app


def _iso(delta: timedelta = timedelta()) -> str:
    return (datetime.now(timezone.utc) + delta).isoformat()


def _client(user: dict) -> AsyncClient:
    token = create_access_token(subject=user["id"], tenant_id=user["tenant_id"])
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"})


async def _make_shop(label: str) -> dict:
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-f1-{label}-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    staff = {"id": f"staff-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "role": "staff", "is_active": True}
    customer = {"id": f"cust-{suffix}", "tenant_id": tenant_id, "name": "F1 Customer", "email": f"cust-{suffix}@example.com"}
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": f"F1 {label}", "is_active": True})
    await db.users.insert_many([owner, staff])
    await db.customers.insert_one(customer)
    return {"tenant_id": tenant_id, "owner": owner, "staff": staff, "customer": customer, "suffix": suffix}


async def _add_trial(shop: dict, *, ends_in: timedelta, status: str = "free_active") -> None:
    await db.trial_records.insert_one({
        "id": f"trial-{uuid.uuid4().hex[:8]}", "tenant_id": shop["tenant_id"], "billing_account_id": f"ba-{shop['suffix']}",
        "trial_kind": "free", "status": status, "starts_at": _iso(-timedelta(days=2)), "ends_at": _iso(ends_in),
    })


async def _add_subscription(shop: dict, *, product_id: str = "prod-core", **fields) -> dict:
    sub = {
        "id": f"sub-{uuid.uuid4().hex[:8]}", "tenant_id": shop["tenant_id"], "billing_account_id": f"ba-{shop['suffix']}",
        "plan_product_id": product_id, "add_on_product_ids": [], "status": "active", "dunning_state": "current", **fields,
    }
    await db.tenant_subscriptions.insert_one(dict(sub))
    return sub


async def _add_rule(*, product_id: str, feature_key: str, scope: str = "plan") -> None:
    await db.commercial_entitlement_rules.insert_one({
        "id": f"rule-{uuid.uuid4().hex[:8]}", "catalog_version_id": "cat-f1", "product_id": product_id,
        "feature_key": feature_key, "entitlement_scope": scope, "enabled": True, "source_priority": 100,
    })


@pytest_asyncio.fixture(autouse=True)
async def _no_overrides():
    app.dependency_overrides.pop(get_current_user, None)
    yield
    app.dependency_overrides.pop(get_current_user, None)


async def _create_customer(shop: dict, who: str = "owner"):
    async with _client(shop[who]) as client:
        return await client.post("/api/customers", json={"name": f"New {uuid.uuid4().hex[:6]}"})


# --- Core read-only mode -----------------------------------------------------


@pytest.mark.asyncio
async def test_unbilled_shop_is_not_restricted():
    shop = await _make_shop("unbilled")
    assert (await _create_customer(shop)).status_code == 201
    access = await commercial_entitlements.resolve_commercial_access(tenant_id=shop["tenant_id"])
    assert access["state"] == "unbilled" and access["read_only"] is False


@pytest.mark.asyncio
async def test_valid_trial_has_full_access():
    shop = await _make_shop("trial")
    await _add_trial(shop, ends_in=timedelta(hours=10))
    assert (await _create_customer(shop)).status_code == 201
    async with _client(shop["owner"]) as client:
        me = (await client.get("/api/auth/me")).json()
    assert me["commercial_access"]["state"] == "full"
    assert me["commercial_access"]["trial_ends_at"]


@pytest.mark.asyncio
async def test_expired_trial_is_read_only_without_admin_action():
    shop = await _make_shop("expired")
    # Trial record still says "free_active": nobody ran the expiry job.
    await _add_trial(shop, ends_in=-timedelta(minutes=5))
    denied = await _create_customer(shop)
    assert denied.status_code == 402
    assert denied.json()["detail"]["code"] == "subscription_inactive"
    async with _client(shop["owner"]) as client:
        listing = await client.get("/api/customers")
        assert listing.status_code == 200
        assert any(row["id"] == shop["customer"]["id"] for row in listing.json().get("items", listing.json()))
        detail = await client.get(f"/api/customers/{shop['customer']['id']}")
        assert detail.status_code == 200
        me = (await client.get("/api/auth/me")).json()
        assert me["commercial_access"]["read_only"] is True
        # Billing, account recovery and support stay reachable.
        assert (await client.post("/api/billing/account", json={})).status_code != 402
        assert (await client.post("/api/community/support", json={"request_type": "bug", "subject": "s", "description": "d"})).status_code != 402
        assert (await client.post("/api/reports/customers/export.csv", json={})).status_code != 402
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anon:
        reset = await anon.post("/api/auth/request-password-reset", json={"tenant_slug": shop["tenant_id"], "email": shop["owner"]["email"]})
        assert reset.status_code == 202


@pytest.mark.asyncio
async def test_active_subscription_has_full_access():
    shop = await _make_shop("active")
    await _add_trial(shop, ends_in=-timedelta(days=5), status="free_expired")
    await _add_subscription(shop)
    assert (await _create_customer(shop)).status_code == 201


@pytest.mark.asyncio
async def test_suspended_subscription_is_read_only_and_records_preserved():
    shop = await _make_shop("suspended")
    await _add_subscription(shop, status="unpaid", dunning_state="suspended")
    before = await db.customers.count_documents({"tenant_id": shop["tenant_id"]})
    assert (await _create_customer(shop)).status_code == 402
    async with _client(shop["owner"]) as client:
        assert (await client.get(f"/api/customers/{shop['customer']['id']}")).status_code == 200
    assert await db.customers.count_documents({"tenant_id": shop["tenant_id"]}) == before


@pytest.mark.asyncio
async def test_past_due_keeps_core_access_per_dunning_rule():
    shop = await _make_shop("pastdue")
    await _add_subscription(shop, status="past_due", dunning_state="eligible_for_suspension", first_payment_failed_at=_iso(-timedelta(days=20)))
    # C2: day 15+ is only *eligible* for suspension; core stays writable.
    assert (await _create_customer(shop)).status_code == 201


@pytest.mark.asyncio
async def test_platform_admin_is_not_restricted():
    shop = await _make_shop("platform")
    await _add_subscription(shop, status="canceled")
    admin = {"id": f"pa-{shop['suffix']}", "tenant_id": shop["tenant_id"], "email": f"pa-{shop['suffix']}@example.com",
             "role": "staff", "is_active": True, "platform_admin": True, "platform_role": "admin"}
    await db.users.insert_one(dict(admin))
    shop["admin"] = admin
    assert (await _create_customer(shop, "owner")).status_code == 402
    async with _client(admin) as client:
        assert (await client.post("/api/customers", json={"name": "Support fix"})).status_code != 402


@pytest.mark.asyncio
async def test_read_only_state_is_tenant_isolated():
    lapsed = await _make_shop("iso-lapsed")
    paying = await _make_shop("iso-paying")
    await _add_trial(lapsed, ends_in=-timedelta(hours=1))
    await _add_subscription(paying)
    assert (await _create_customer(lapsed)).status_code == 402
    assert (await _create_customer(paying)).status_code == 201


@pytest.mark.asyncio
async def test_staff_permissions_still_apply_for_paying_shop():
    shop = await _make_shop("perms")
    await _add_subscription(shop)
    async with _client(shop["staff"]) as client:
        denied = await client.post("/api/wrap-lab/vehicles", json={"customer_id": shop["customer"]["id"], "make": "Ford", "model": "Transit"})
    assert denied.status_code == 403


# --- Paid add-on entitlements ------------------------------------------------


@pytest.mark.asyncio
async def test_wrap_lab_is_core_not_a_paid_add_on():
    """Owner decision 2026-10-14: Wrap Lab is included in Core; Webstores is the only add-on."""
    vehicle = {"make": "Ford", "model": "Transit"}
    active = await _make_shop("wrap-core")
    await _add_subscription(active)  # no wrap_lab entitlement row
    async with _client(active["owner"]) as client:
        created = await client.post("/api/wrap-lab/vehicles", json={"customer_id": active["customer"]["id"], **vehicle})
    assert created.status_code in {200, 201}

    suspended = await _make_shop("wrap-suspended")
    await _add_subscription(suspended, status="unpaid", dunning_state="suspended")
    async with _client(suspended["owner"]) as client:
        blocked = await client.post("/api/wrap-lab/vehicles", json={"customer_id": suspended["customer"]["id"], **vehicle})
        assert blocked.status_code == 402 and blocked.json()["detail"]["code"] == "subscription_inactive"
        assert (await client.get("/api/wrap-lab/projects")).status_code == 200


@pytest.mark.asyncio
async def test_trial_entitlement_expires_automatically(monkeypatch):
    shop = await _make_shop("trial-ent")
    product_id = f"prod-trial-{shop['suffix']}"
    feature_key = f"f1_trial_{shop['suffix']}"
    await _add_rule(product_id=product_id, feature_key=feature_key, scope="trial")
    await _add_trial(shop, ends_in=-timedelta(minutes=1))
    trial = await db.trial_records.find_one({"tenant_id": shop["tenant_id"]}, {"_id": 0})
    # Project while the trial was still running (clock set before its end)...
    monkeypatch.setattr(commercial_entitlements, "utc_now", lambda: datetime.fromisoformat(trial["ends_at"]) - timedelta(hours=1))
    await commercial_entitlements.project_entitlements_for_tenant(tenant_id=shop["tenant_id"])
    row = await db.feature_entitlements.find_one({"tenant_id": shop["tenant_id"], "feature_key": feature_key}, {"_id": 0})
    assert row["enabled"] is True and row["expires_at"]
    # ...and at the real clock it has lapsed with no admin call.
    assert await has_entitlement(tenant_id=shop["tenant_id"], feature_key=feature_key) is False


_ADMIN = {"role": "staff", "is_active": True, "platform_admin": True, "platform_role": "admin", "email": "pa@example.com"}


async def _paid_shop(label: str) -> tuple[dict, dict, str]:
    shop = await _make_shop(label)
    product_id = f"prod-{label}-{shop['suffix']}"
    feature_key = f"f1_{label}_{shop['suffix']}"
    await _add_rule(product_id=product_id, feature_key=feature_key)
    sub = await _add_subscription(shop, product_id=product_id, stripe_subscription_id=f"stripe-{shop['suffix']}")
    await commercial_entitlements.project_entitlements_for_tenant(tenant_id=shop["tenant_id"])
    assert await has_entitlement(tenant_id=shop["tenant_id"], feature_key=feature_key) is True
    return shop, sub, feature_key


@pytest.mark.asyncio
async def test_past_due_day_15_keeps_paid_features_until_formal_suspension():
    shop, sub, feature_key = await _paid_shop("pastdue-ent")
    # C2: day 15+ is only *eligible* for suspension; nothing is revoked automatically.
    await tenant_billing.handle_invoice_payment_failed(
        stripe_subscription_id=sub["stripe_subscription_id"], occurred_at=datetime.now(timezone.utc) - timedelta(days=20)
    )
    stored = await db.tenant_subscriptions.find_one({"id": sub["id"]}, {"_id": 0})
    assert stored["dunning_state"] == "eligible_for_suspension"
    await commercial_entitlements.project_entitlements_for_tenant(tenant_id=shop["tenant_id"])
    assert await has_entitlement(tenant_id=shop["tenant_id"], feature_key=feature_key) is True
    assert (await _create_customer(shop)).status_code == 201

    # Approved administrative suspension revokes paid access and core writes.
    admin = {**_ADMIN, "id": f"pa-{shop['suffix']}", "tenant_id": shop["tenant_id"]}
    await tenant_billing.suspend_subscription(admin, subscription_id=sub["id"], reason="Day 15 review")
    assert await has_entitlement(tenant_id=shop["tenant_id"], feature_key=feature_key) is False
    assert (await _create_customer(shop)).status_code == 402

    # Successful payment restores both.
    await tenant_billing.handle_invoice_payment_succeeded(stripe_subscription_id=sub["stripe_subscription_id"])
    assert await has_entitlement(tenant_id=shop["tenant_id"], feature_key=feature_key) is True
    assert (await _create_customer(shop)).status_code == 201


@pytest.mark.asyncio
async def test_authorized_reactivation_restores_paid_access():
    from app.services import platform_admin

    shop, sub, feature_key = await _paid_shop("reactivate")
    admin = {**_ADMIN, "id": f"pa-{shop['suffix']}", "tenant_id": shop["tenant_id"]}
    await tenant_billing.suspend_subscription(admin, subscription_id=sub["id"], reason="Unpaid")
    assert await has_entitlement(tenant_id=shop["tenant_id"], feature_key=feature_key) is False
    await platform_admin.mark_paid(admin, shop["tenant_id"], note="Paid by check")
    assert await has_entitlement(tenant_id=shop["tenant_id"], feature_key=feature_key) is True
    assert (await _create_customer(shop)).status_code == 201


@pytest.mark.asyncio
async def test_suspension_disables_paid_features_and_isolation():
    shop = await _make_shop("susp-ent")
    other = await _make_shop("susp-other")
    product_id = f"prod-susp-{shop['suffix']}"
    feature_key = f"f1_susp_{shop['suffix']}"
    await _add_rule(product_id=product_id, feature_key=feature_key)
    sub = await _add_subscription(shop, product_id=product_id)
    await commercial_entitlements.project_entitlements_for_tenant(tenant_id=shop["tenant_id"])
    admin = {"id": "pa-susp", "tenant_id": shop["tenant_id"], "email": "pa@example.com", "role": "staff",
             "is_active": True, "platform_admin": True, "platform_role": "admin"}
    await tenant_billing.suspend_subscription(admin, subscription_id=sub["id"], reason="Day 15 dunning")
    assert await has_entitlement(tenant_id=shop["tenant_id"], feature_key=feature_key) is False
    assert await has_entitlement(tenant_id=other["tenant_id"], feature_key=feature_key) is False
    assert await db.feature_entitlements.count_documents({"tenant_id": other["tenant_id"]}) == 0


# --- Review findings (PR #42) ------------------------------------------------


@pytest.mark.asyncio
async def test_pending_checkouts_do_not_lock_an_unrestricted_shop():
    shop = await _make_shop("pending")
    # Started an extended-trial checkout and a plan checkout, paid for neither.
    await db.trial_records.insert_one({
        "id": f"trial-{shop['suffix']}", "tenant_id": shop["tenant_id"], "billing_account_id": f"ba-{shop['suffix']}",
        "trial_kind": "extended", "status": "extended_pending_payment", "starts_at": None, "ends_at": None,
    })
    await _add_subscription(shop, status="incomplete", dunning_state="current")
    access = await commercial_entitlements.resolve_commercial_access(tenant_id=shop["tenant_id"])
    assert access["state"] == "unbilled" and access["read_only"] is False
    assert (await _create_customer(shop)).status_code == 201


@pytest.mark.asyncio
async def test_read_only_gets_do_not_create_or_change_records():
    shop = await _make_shop("ro-get")
    await _add_trial(shop, ends_in=-timedelta(hours=1))
    employee_id = f"emp-{shop['suffix']}"
    await db.employees.insert_one({"id": employee_id, "tenant_id": shop["tenant_id"], "name": "Crew", "status": "active", "hourly_rate_cents": 2500})
    week = "2026-10-12"
    async with _client(shop["owner"]) as client:
        schedule = await client.get("/api/schedules", params={"period_start": week})
        timesheet = await client.get("/api/timesheets/weekly", params={"week_start": week, "employee_id": employee_id})
        payroll = await client.get("/api/payroll/periods/current", params={"period_start": week})
    assert schedule.status_code == 200 and schedule.json()["schedule"]["is_preview"] is True
    assert timesheet.status_code == 200 and timesheet.json()["is_preview"] is True
    assert payroll.status_code == 200 and payroll.json()["period"]["is_preview"] is True
    for collection in ("schedules", "timesheets", "pay_periods"):
        assert await db[collection].count_documents({"tenant_id": shop["tenant_id"]}) == 0, collection


@pytest.mark.asyncio
async def test_read_only_get_shows_existing_records_without_updating_them():
    shop = await _make_shop("ro-existing")
    await _add_subscription(shop, status="unpaid", dunning_state="suspended")
    employee_id = f"emp-{shop['suffix']}"
    await db.employees.insert_one({"id": employee_id, "tenant_id": shop["tenant_id"], "name": "Crew", "status": "active"})
    await db.timesheets.insert_one({
        "id": f"ts-{shop['suffix']}", "tenant_id": shop["tenant_id"], "employee_id": employee_id, "week_start": "2026-10-10",
        "week_end": "2026-10-16", "status": "pending", "worked_minutes": 999, "updated_at": "2026-10-12T00:00:00+00:00",
    })
    async with _client(shop["owner"]) as client:
        shown = await client.get("/api/timesheets/weekly", params={"week_start": "2026-10-12", "employee_id": employee_id})
    assert shown.status_code == 200 and shown.json()["id"] == f"ts-{shop['suffix']}"
    stored = await db.timesheets.find_one({"id": f"ts-{shop['suffix']}"}, {"_id": 0})
    assert stored["worked_minutes"] == 999 and stored["updated_at"] == "2026-10-12T00:00:00+00:00"


@pytest.mark.asyncio
async def test_active_shop_get_keeps_existing_create_behavior():
    shop = await _make_shop("active-get")
    await _add_subscription(shop)
    async with _client(shop["owner"]) as client:
        schedule = await client.get("/api/schedules", params={"period_start": "2026-10-12"})
    assert schedule.status_code == 200 and "is_preview" not in schedule.json()["schedule"]
    assert await db.schedules.count_documents({"tenant_id": shop["tenant_id"]}) == 1


@pytest.mark.asyncio
async def test_ai_studio_is_not_gated_as_a_separate_add_on():
    """Owner direction 2026-10-14: AI Studio and the Business Assistant are included
    with the standard subscription and limited by EC16 credits, so F1 adds no
    separate add-on gate to Studio records."""
    shop = await _make_shop("studio")
    await _add_subscription(shop)  # paying shop holding no ai_studio entitlement row
    prompt = {"tool_key": "content_writer", "mode_key": "business_copy", "name": "Shop copy", "template": "Write {{topic}}."}
    async with _client(shop["owner"]) as client:
        assert (await client.post("/api/ai-studio/prompts", json=prompt)).status_code == 201
        assert (await client.get("/api/ai-studio/prompts")).status_code == 200
