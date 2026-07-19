"""EC13 remaining commercial billing phases."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.portal_security import create_portal_token
from app.deps import get_current_user
from app.services import tenant_billing
from server import app


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _override(user: dict):
    async def _get():
        return {**user}

    return _get


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _token_client(token: str) -> AsyncClient:
    app.dependency_overrides.pop(get_current_user, None)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"})


@pytest_asyncio.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-13rest-{suffix}"
    other_tenant_id = f"t-13rest-other-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    staff = {"id": f"staff-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "role": "staff", "is_active": True}
    platform_admin = {
        "id": f"platform-{suffix}",
        "tenant_id": tenant_id,
        "email": f"platform-{suffix}@example.com",
        "role": "staff",
        "is_active": True,
        "platform_admin": True,
        "platform_role": "admin",
    }
    other_owner = {"id": f"other-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "Tenant"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Other Tenant"},
    ])
    await db.users.insert_many([owner, staff, platform_admin, other_owner])
    portal_identity = {
        "id": f"portal-{suffix}",
        "tenant_id": tenant_id,
        "portal_type": "customer",
        "customer_id": f"customer-{suffix}",
        "email": f"portal-{suffix}@example.com",
        "status": "active",
    }
    await db.portal_identities.insert_one(portal_identity)
    portal_token = create_portal_token(
        portal_identity_id=portal_identity["id"],
        tenant_id=tenant_id,
        portal_type="customer",
        customer_id=portal_identity["customer_id"],
    )
    yield {
        "suffix": suffix,
        "tenant_id": tenant_id,
        "other_tenant_id": other_tenant_id,
        "owner": owner,
        "staff": staff,
        "platform_admin": platform_admin,
        "other_owner": other_owner,
        "portal_token": portal_token,
    }
    app.dependency_overrides.pop(get_current_user, None)


async def _published_catalog(platform: AsyncClient, suffix: str) -> dict:
    catalog = await platform.post("/api/commercial/catalog/versions", json={"version": f"ec13-rest-{suffix}", "effective_at": _now()})
    assert catalog.status_code == 201, catalog.text
    product = await platform.post(
        "/api/commercial/catalog/products",
        json={
            "catalog_version_id": catalog.json()["id"],
            "product_key": f"core-{suffix}",
            "name": "SignGuy Core",
            "product_type": "core",
            "status": "active",
            "owner_checkpoint": "EC13",
            "publishable": True,
        },
    )
    price = await platform.post(
        "/api/commercial/catalog/prices",
        json={
            "catalog_version_id": catalog.json()["id"],
            "product_id": product.json()["id"],
            "price_key": f"core-monthly-{suffix}",
            "billing_interval": "monthly",
            "amount_cents": 14900,
            "is_active": True,
            "is_public": True,
            "approved_by_owner": True,
        },
    )
    annual = await platform.post(
        "/api/commercial/catalog/prices",
        json={
            "catalog_version_id": catalog.json()["id"],
            "product_id": product.json()["id"],
            "price_key": f"core-annual-{suffix}",
            "billing_interval": "annual",
            "amount_cents": 149000,
            "is_active": True,
            "is_public": True,
            "approved_by_owner": True,
        },
    )
    rule = await platform.post(
        "/api/commercial/catalog/entitlement-rules",
        json={
            "catalog_version_id": catalog.json()["id"],
            "product_id": product.json()["id"],
            "feature_key": f"subscription.core.{suffix}",
            "entitlement_scope": "plan",
        },
    )
    trial_rule = await platform.post(
        "/api/commercial/catalog/entitlement-rules",
        json={
            "catalog_version_id": catalog.json()["id"],
            "product_id": product.json()["id"],
            "feature_key": f"trial.core.{suffix}",
            "entitlement_scope": "trial",
            "quota": 25,
        },
    )
    fee_schedule = await platform.post(
        "/api/commercial/platform-fee-schedules",
        json={
            "catalog_version_id": catalog.json()["id"],
            "fee_key": f"ga-standard-{suffix}",
            "account_status": "ga",
            "transaction_type": "standard_customer_payment",
            "rate_basis_points": 100,
            "is_active": True,
        },
    )
    published = await platform.post(f"/api/commercial/catalog/versions/{catalog.json()['id']}/publish")
    assert product.status_code == 201, product.text
    assert price.status_code == 201, price.text
    assert annual.status_code == 201, annual.text
    assert rule.status_code == 201, rule.text
    assert trial_rule.status_code == 201, trial_rule.text
    assert fee_schedule.status_code == 201, fee_schedule.text
    assert published.status_code == 200, published.text
    return {"catalog": catalog.json(), "product": product.json(), "price": price.json(), "annual": annual.json(), "feature_key": f"subscription.core.{suffix}", "trial_key": f"trial.core.{suffix}"}


@pytest.mark.asyncio
async def test_billing_account_trials_checkout_subscription_and_entitlement_projection(ctx):
    before = {
        "invoices": await db.invoices.count_documents({"tenant_id": ctx["tenant_id"]}),
        "payments": await db.payments.count_documents({"tenant_id": ctx["tenant_id"]}),
    }
    async with await _client_as(ctx["platform_admin"]) as platform:
        catalog = await _published_catalog(platform, ctx["suffix"])

    async with await _client_as(ctx["staff"]) as staff:
        denied = await staff.post("/api/billing/account", json={})
        assert denied.status_code == 403

    async with await _client_as(ctx["owner"]) as owner:
        account = await owner.post("/api/billing/account", json={"terms_version": "2026-07"})
        free_trial = await owner.post("/api/billing/trials/free")
        duplicate_trial = await owner.post("/api/billing/trials/free")
        checkout = await owner.post(
            "/api/billing/checkout-sessions",
            json={
                "session_type": "subscription",
                "price_id": catalog["price"]["id"],
                "idempotency_key": f"sub-{ctx['suffix']}",
                "success_url": "https://app.example/success",
                "cancel_url": "https://app.example/cancel",
            },
        )
        checkout_dup = await owner.post(
            "/api/billing/checkout-sessions",
            json={
                "session_type": "subscription",
                "price_id": catalog["price"]["id"],
                "idempotency_key": f"sub-{ctx['suffix']}",
                "success_url": "https://app.example/success",
                "cancel_url": "https://app.example/cancel",
            },
        )
        assert account.status_code == 201, account.text
        assert free_trial.status_code == 201, free_trial.text
        assert free_trial.json()["credit_allotment"] == 25
        assert duplicate_trial.status_code == 409
        assert checkout.status_code == 201, checkout.text
        assert checkout_dup.json()["id"] == checkout.json()["id"]

    completed = await tenant_billing.complete_checkout_session(
        stripe_checkout_session_id=checkout.json()["stripe_checkout_session_id"],
        stripe_subscription_id=f"sub_{ctx['suffix']}",
        stripe_customer_id=f"cus_{ctx['suffix']}",
    )
    assert completed["status"] == "completed"
    subscription = await db.tenant_subscriptions.find_one({"tenant_id": ctx["tenant_id"]}, {"_id": 0})
    assert subscription["status"] == "active"
    assert subscription["billing_interval"] == "monthly"
    account_doc = await db.tenant_billing_accounts.find_one({"tenant_id": ctx["tenant_id"]}, {"_id": 0})
    assert account_doc["status"] == "active"
    assert account_doc["stripe_customer_id"] == f"cus_{ctx['suffix']}"
    entitlement = await db.feature_entitlements.find_one({"tenant_id": ctx["tenant_id"], "feature_key": catalog["feature_key"]}, {"_id": 0})
    assert entitlement["enabled"] is True
    assert entitlement["granted_by"] == "commercial_billing"
    assert await db.invoices.count_documents({"tenant_id": ctx["tenant_id"]}) == before["invoices"]
    assert await db.payments.count_documents({"tenant_id": ctx["tenant_id"]}) == before["payments"]

    async with await _client_as(ctx["owner"]) as owner:
        state = await owner.get("/api/billing/state")
        cross = await owner.get("/api/billing/state", params={"tenant_id": ctx["other_tenant_id"]})
        portal = await owner.post("/api/billing/portal-sessions", json={"return_url": "https://app.example/billing"})
        assert state.status_code == 200
        assert state.json()["subscription"]["id"] == subscription["id"]
        assert cross.status_code == 403
        assert portal.status_code == 201

    async with await _token_client(ctx["portal_token"]) as portal_client:
        denied = await portal_client.get("/api/billing/state")
        assert denied.status_code in {401, 403}


@pytest.mark.asyncio
async def test_setup_packages_waivers_extended_trial_and_no_ec19_handoff(ctx):
    async with await _client_as(ctx["platform_admin"]) as platform:
        await _published_catalog(platform, f"setup-{ctx['suffix']}")
    async with await _client_as(ctx["owner"]) as owner:
        await owner.post("/api/billing/account", json={})
        setup = await owner.post(
            "/api/billing/setup-packages/checkout",
            json={
                "package_key": "standard",
                "idempotency_key": f"setup-{ctx['suffix']}",
                "success_url": "https://app.example/success",
                "cancel_url": "https://app.example/cancel",
            },
        )
        extended = await owner.post(
            "/api/billing/trials/extended-checkout",
            json={
                "idempotency_key": f"extended-{ctx['suffix']}",
                "success_url": "https://app.example/success",
                "cancel_url": "https://app.example/cancel",
            },
        )
        assert setup.status_code == 201, setup.text
        assert setup.json()["setup_purchase"]["amount_cents"] == 49900
        assert setup.json()["setup_purchase"]["status"] == "pending_payment"
        assert setup.json()["setup_purchase"]["ec19_handoff_status"] == "not_started"
        assert extended.status_code == 201, extended.text
        assert extended.json()["trial"]["status"] == "extended_pending_payment"
        assert extended.json()["trial"]["conversion_credit_cents"] == 2000

    await tenant_billing.complete_checkout_session(stripe_checkout_session_id=setup.json()["checkout_session"]["stripe_checkout_session_id"])
    await tenant_billing.complete_checkout_session(stripe_checkout_session_id=extended.json()["checkout_session"]["stripe_checkout_session_id"])
    paid_setup = await db.setup_package_purchases.find_one({"checkout_session_id": setup.json()["checkout_session"]["id"]}, {"_id": 0})
    active_extended = await db.trial_records.find_one({"checkout_session_id": extended.json()["checkout_session"]["id"]}, {"_id": 0})
    assert paid_setup["status"] == "paid"
    assert paid_setup["ec19_handoff_status"] == "not_started"
    assert active_extended["status"] == "extended_active"

    async with await _client_as(ctx["owner"]) as owner:
        denied_waiver = await owner.post("/api/billing/setup-packages/waivers", json={"tenant_id": ctx["tenant_id"], "package_key": "founder_kickstart", "reason": "not platform"})
        assert denied_waiver.status_code == 403
    async with await _client_as(ctx["platform_admin"]) as platform:
        no_reason = await platform.post("/api/billing/setup-packages/waivers", json={"tenant_id": ctx["tenant_id"], "package_key": "founder_kickstart", "reason": ""})
        waiver = await platform.post("/api/billing/setup-packages/waivers", json={"tenant_id": ctx["tenant_id"], "package_key": "founder_kickstart", "reason": "Owner-approved Founder setup waiver"})
        assert no_reason.status_code == 400
        assert waiver.status_code == 201, waiver.text
        assert waiver.json()["status"] == "waived"
        assert waiver.json()["amount_cents"] == 29900


@pytest.mark.asyncio
async def test_dunning_cancellation_downgrade_platform_fees_and_boundaries(ctx):
    async with await _client_as(ctx["platform_admin"]) as platform:
        catalog = await _published_catalog(platform, f"dun-{ctx['suffix']}")

    async with await _client_as(ctx["owner"]) as owner:
        await owner.post("/api/billing/account", json={})
        checkout = await owner.post(
            "/api/billing/checkout-sessions",
            json={
                "session_type": "subscription",
                "price_id": catalog["price"]["id"],
                "idempotency_key": f"dun-sub-{ctx['suffix']}",
                "success_url": "https://app.example/success",
                "cancel_url": "https://app.example/cancel",
            },
        )
    await tenant_billing.complete_checkout_session(
        stripe_checkout_session_id=checkout.json()["stripe_checkout_session_id"],
        stripe_subscription_id=f"sub_dun_{ctx['suffix']}",
        stripe_customer_id=f"cus_dun_{ctx['suffix']}",
    )
    subscription = await db.tenant_subscriptions.find_one({"tenant_id": ctx["tenant_id"]}, {"_id": 0})

    failed = await tenant_billing.handle_invoice_payment_failed(
        stripe_subscription_id=subscription["stripe_subscription_id"],
        occurred_at=datetime.now(timezone.utc) - timedelta(days=9),
    )
    assert failed["status"] == "past_due"
    assert failed["dunning_state"] == "day_8_14_soft_restriction"

    async with await _client_as(ctx["owner"]) as owner:
        cancel = await owner.post(f"/api/billing/subscriptions/{subscription['id']}/cancel", json={"reason": "testing"})
        downgrade = await owner.post(f"/api/billing/subscriptions/{subscription['id']}/downgrade", json={"price_id": catalog["annual"]["id"]})
        assert cancel.status_code == 200, cancel.text
        assert cancel.json()["cancel_at_period_end"] is True
        assert downgrade.status_code == 200, downgrade.text
        assert downgrade.json()["scheduled_downgrade_price_id"] == catalog["annual"]["id"]

    async with await _client_as(ctx["platform_admin"]) as platform:
        no_reason_grace = await platform.post(f"/api/billing/platform/subscriptions/{subscription['id']}/grace", json={"grace_until": _now(), "reason": ""})
        grace = await platform.post(
            f"/api/billing/platform/subscriptions/{subscription['id']}/grace",
            json={"grace_until": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(), "reason": "Owner-approved billing grace"},
        )
        suspend = await platform.post(f"/api/billing/platform/subscriptions/{subscription['id']}/suspend", json={"reason": "Dunning threshold reached"})
        assert no_reason_grace.status_code == 400
        assert grace.status_code == 200
        assert grace.json()["dunning_state"] == "manually_extended"
        assert suspend.status_code == 200
        assert suspend.json()["dunning_state"] == "suspended"

        payment = {
            "id": f"pay-{ctx['suffix']}",
            "tenant_id": ctx["tenant_id"],
            "invoice_id": f"inv-{ctx['suffix']}",
            "customer_id": f"cust-{ctx['suffix']}",
            "source": "manual",
            "status": "confirmed",
            "amount_cents": 10000,
            "currency": "usd",
            "created_at": _now(),
            "updated_at": _now(),
        }
        await db.payments.insert_one(payment)
        fee = await platform.post("/api/billing/platform/platform-fees/assess-payment", json={"payment_id": payment["id"]})
        fee_dup = await platform.post("/api/billing/platform/platform-fees/assess-payment", json={"payment_id": payment["id"]})
        assert fee.status_code == 201, fee.text
        assert fee.json()["basis_amount_cents"] == 10000
        assert fee.json()["platform_fee_cents"] == 100
        assert fee_dup.json()["id"] == fee.json()["id"]

    payment_after = await db.payments.find_one({"id": f"pay-{ctx['suffix']}"}, {"_id": 0})
    assert payment_after["amount_cents"] == 10000
    entitlement = await db.feature_entitlements.find_one({"tenant_id": ctx["tenant_id"], "feature_key": catalog["feature_key"]}, {"_id": 0})
    assert entitlement["enabled"] is False
    assert not await db.get_collection("webstore_payouts").count_documents({"tenant_id": ctx["tenant_id"]})


@pytest.mark.asyncio
async def test_stripe_billing_event_processor_is_idempotent_and_separate_from_ec4(ctx):
    async with await _client_as(ctx["platform_admin"]) as platform:
        catalog = await _published_catalog(platform, f"evt-{ctx['suffix']}")
    async with await _client_as(ctx["owner"]) as owner:
        await owner.post("/api/billing/account", json={})
        checkout = await owner.post(
            "/api/billing/checkout-sessions",
            json={
                "session_type": "subscription",
                "price_id": catalog["price"]["id"],
                "idempotency_key": f"evt-sub-{ctx['suffix']}",
                "success_url": "https://app.example/success",
                "cancel_url": "https://app.example/cancel",
            },
        )

    event = {
        "id": f"evt-{ctx['suffix']}",
        "type": "checkout.session.completed",
        "livemode": False,
        "data": {
            "object": {
                "id": checkout.json()["stripe_checkout_session_id"],
                "subscription": f"sub_evt_{ctx['suffix']}",
                "customer": f"cus_evt_{ctx['suffix']}",
                "metadata": {"tenant_id": ctx["tenant_id"]},
            }
        },
    }
    first = await tenant_billing.process_stripe_billing_event(event)
    second = await tenant_billing.process_stripe_billing_event(event)
    assert first["handled"] is True
    assert second["checkout_session"]["status"] == "completed"
    assert await db.payments.count_documents({"tenant_id": ctx["tenant_id"]}) == 0
    assert await db.invoices.count_documents({"tenant_id": ctx["tenant_id"]}) == 0

    failed = await tenant_billing.process_stripe_billing_event({
        "id": f"evt-failed-{ctx['suffix']}",
        "type": "invoice.payment_failed",
        "data": {"object": {"subscription": f"sub_evt_{ctx['suffix']}"}},
    })
    succeeded = await tenant_billing.process_stripe_billing_event({
        "id": f"evt-paid-{ctx['suffix']}",
        "type": "invoice.payment_succeeded",
        "data": {"object": {"subscription": f"sub_evt_{ctx['suffix']}"}},
    })
    assert failed["handled"] is True
    assert failed["subscription"]["status"] == "past_due"
    assert succeeded["handled"] is True
    assert succeeded["subscription"]["status"] == "active"
    assert succeeded["subscription"]["dunning_state"] == "current"
