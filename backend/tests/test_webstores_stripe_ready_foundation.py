"""Stripe-ready Webstores foundation contracts.

These tests deliberately prove that the placeholder foundation cannot create
provider, Payment, Order, or checkout state.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.core.security_guards import collect_webstore_stripe_violations
from app.services.webstore_payment_provider import (
    PAYMENT_PROVIDER_NOT_CONFIGURED,
    NotConfiguredWebstorePaymentProvider,
    ProviderAuthority,
    ProviderFinancialEvent,
    ProviderResult,
    VerifiedProviderPayment,
    get_webstore_payment_provider,
    provider_configuration_status,
)
from app.services.webstore_payments import process_verified_payment_event
from app.services.webstore_payments import initiate_webstore_refund, reconcile_webstore_financial_event
from app.services.webstores import WebstoreError, _payment_readiness, create_purchase_intent, list_webstores
from app.core.db import db
from server import app


def _settings(monkeypatch: pytest.MonkeyPatch, **values: str) -> Settings:
    defaults = {
        "STRIPE_ENABLED": "true",
        "STRIPE_MODE": "test",
        "STRIPE_SECRET_KEY": "sk_test_foundation_only",
        "STRIPE_PUBLISHABLE_KEY": "pk_test_foundation_only",
        "STRIPE_CONNECT_CLIENT_ID": "ca_foundation_only",
        "STRIPE_CONNECT_RETURN_URL": "https://example.test/stripe/return",
        "STRIPE_CONNECT_REFRESH_URL": "https://example.test/stripe/refresh",
        "STRIPE_CHECKOUT_SUCCESS_URL": "https://example.test/checkout/success",
        "STRIPE_CHECKOUT_CANCEL_URL": "https://example.test/checkout/cancel",
        "STRIPE_CONNECT_CHARGE_MODEL": "deferred",
        "STRIPE_WEBHOOK_SECRET": "webhook-foundation-only",
    }
    defaults.update(values)
    for key, value in defaults.items():
        monkeypatch.setenv(key, value)
    return Settings()


def test_stripe_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch):
    settings = _settings(monkeypatch, STRIPE_ENABLED="false")
    status = provider_configuration_status(settings)
    assert status["state"] == "not_configured"
    assert status["provider_authority"] is False
    assert status["violations"] == []


def test_placeholder_values_and_deferred_model_fail_closed(monkeypatch: pytest.MonkeyPatch):
    settings = _settings(
        monkeypatch,
        STRIPE_SECRET_KEY="",
        STRIPE_PUBLISHABLE_KEY="",
        STRIPE_CONNECT_CHARGE_MODEL="deferred",
    )
    codes = {item.code for item in collect_webstore_stripe_violations(settings)}
    assert "webstore_stripe_credentials_missing" in codes
    assert "webstore_stripe_charge_model_deferred" in codes
    assert provider_configuration_status(settings)["provider_authority"] is False


def test_mode_mismatch_and_invalid_callbacks_fail_closed(monkeypatch: pytest.MonkeyPatch):
    settings = _settings(
        monkeypatch,
        STRIPE_MODE="live",
        STRIPE_SECRET_KEY="sk_test_foundation_only",
        STRIPE_PUBLISHABLE_KEY="pk_test_foundation_only",
        STRIPE_CONNECT_RETURN_URL="not-a-url",
    )
    codes = {item.code for item in collect_webstore_stripe_violations(settings)}
    assert "webstore_stripe_mode_mismatch" in codes
    assert "webstore_stripe_callback_url_invalid" in codes


@pytest.mark.asyncio
async def test_stored_readiness_flags_do_not_make_webstore_payment_ready(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STRIPE_ENABLED", "false")
    readiness = await _payment_readiness({"stripe_payment_ready": True, "payment_readiness_status": "ready"})
    assert readiness["ready"] is False
    assert readiness["provider_authority"] is False
    assert readiness["stored_flags_ignored"] is True


@pytest.mark.asyncio
async def test_staff_webstore_list_masks_stored_checkout_flag_without_provider_authority(monkeypatch: pytest.MonkeyPatch):
    settings = _settings(monkeypatch, STRIPE_ENABLED="false")
    monkeypatch.setattr("app.services.webstores.get_settings", lambda: settings)
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-list-provider-{suffix}"
    await db.webstores.insert_one(
        {
            "id": f"ws-list-provider-{suffix}",
            "tenant_id": tenant_id,
            "name": "Stored Checkout Fixture",
            "slug": f"stored-checkout-{suffix}",
            "public_slug": f"stored-checkout-public-{suffix}",
            "status": "live",
            "checkout_enabled": True,
            "payment_readiness_status": "live_ready",
        }
    )
    result = await list_webstores({"tenant_id": tenant_id, "role": "owner"})
    assert result["items"][0]["checkout_enabled"] is False
    assert result["items"][0]["checkout_unavailable_reason"]


@pytest.mark.asyncio
async def test_disabled_provider_has_typed_failures_and_no_fake_checkout():
    provider = get_webstore_payment_provider()
    assert isinstance(provider, NotConfiguredWebstorePaymentProvider)
    result = await provider.create_checkout_session(amount_cents=1000, currency="usd")
    assert result.ok is False
    assert result.code == PAYMENT_PROVIDER_NOT_CONFIGURED


@pytest.mark.asyncio
async def test_public_checkout_fails_before_store_or_intent_lookup(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STRIPE_ENABLED", "false")
    with pytest.raises(WebstoreError) as error:
        await create_purchase_intent("missing-public-slug", {"buyer_name": "Buyer", "buyer_email": "buyer@example.com", "line_items": []})
    assert error.value.code == "payment_provider_not_configured"


@pytest.mark.asyncio
async def test_development_webhook_harness_is_unavailable_without_dev_bypass(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(get_settings(), "auth_dev_bypass", False, raising=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/webhooks/webstores/test-provider", content=b"{}")
    assert response.status_code == 404


def test_provider_status_never_serializes_secrets(monkeypatch: pytest.MonkeyPatch):
    settings = _settings(monkeypatch, STRIPE_ENABLED="true", STRIPE_CONNECT_CHARGE_MODEL="destination")
    status = provider_configuration_status(settings)
    rendered = repr(status)
    assert settings.stripe_secret_key not in rendered
    assert settings.stripe_publishable_key not in rendered
    assert settings.stripe_webhook_secret not in rendered


class _TypedProviderFixture:
    def __init__(self, refund_data: dict, event_data: dict):
        self.refund_data = refund_data
        self.event_data = event_data
        self.refund_calls = 0
        self.event_calls = 0

    async def create_refund(self, **kwargs):
        self.refund_calls += 1
        return ProviderResult.success(self.refund_data)

    async def reconcile_provider_event(self, **kwargs):
        self.event_calls += 1
        return ProviderResult.success(self.event_data)


async def _seed_refundable_webstore(suffix: str) -> dict:
    tenant_id = f"t-refund-{suffix}"
    webstore_id = f"ws-refund-{suffix}"
    payment_id = f"payment-refund-{suffix}"
    intent_id = f"intent-refund-{suffix}"
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "Refund Store"})
    await db.webstores.insert_one({"id": webstore_id, "tenant_id": tenant_id, "name": "Refund Store", "slug": webstore_id, "public_slug": webstore_id, "status": "live"})
    await db.webstore_purchase_intents.insert_one(
        {
            "id": intent_id,
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "public_slug": webstore_id,
            "buyer_name": "Refund Buyer",
            "buyer_email": f"refund-{suffix}@example.com",
            "line_items": [],
            "product_subtotal_cents": 1000,
            "total_cents": 1000,
            "currency": "usd",
            "status": "paid_order_created",
            "canonical_order_id": f"order-{suffix}",
            "canonical_payment_id": payment_id,
            "provider_payment_id": f"pi_test_{suffix}",
        }
    )
    await db.payments.insert_one(
        {
            "id": payment_id,
            "tenant_id": tenant_id,
            "invoice_id": f"webstore_purchase_intent:{intent_id}",
            "customer_id": f"customer-{suffix}",
            "order_id": f"order-{suffix}",
            "source": "stripe",
            "status": "confirmed",
            "amount_cents": 1000,
            "currency": "usd",
            "stripe_payment_intent_id": f"pi_test_{suffix}",
        }
    )
    return {"tenant_id": tenant_id, "webstore_id": webstore_id, "payment_id": payment_id, "intent_id": intent_id, "provider_payment_id": f"pi_test_{suffix}"}


@pytest.mark.asyncio
async def test_unconfigured_refund_has_no_canonical_mutation():
    ctx = await _seed_refundable_webstore(uuid.uuid4().hex[:8])
    with pytest.raises(WebstoreError) as error:
        await initiate_webstore_refund(
            tenant_id=ctx["tenant_id"],
            webstore_id=ctx["webstore_id"],
            payment_id=ctx["payment_id"],
            amount_cents=100,
            reason="Buyer requested refund",
            actor_user_id="staff",
            actor_email="staff@example.com",
        )
    assert error.value.code == "payment_provider_not_configured"
    assert await db.payments.count_documents({"tenant_id": ctx["tenant_id"], "refund_of_payment_id": ctx["payment_id"]}) == 0
    assert await db.webstore_ledger_entries.count_documents({"tenant_id": ctx["tenant_id"], "entry_type": "refund"}) == 0


@pytest.mark.asyncio
async def test_provider_refund_is_reconciled_before_canonical_recording_and_is_idempotent():
    suffix = uuid.uuid4().hex[:8]
    ctx = await _seed_refundable_webstore(suffix)
    authority = ProviderAuthority("test-fixture", "test", "acct_test_fixture", "test-fixture", True, True)
    provider = _TypedProviderFixture(
        {
            "provider": "test-fixture",
            "provider_mode": "test",
            "provider_account_reference": "acct_test_fixture",
            "provider_payment_reference": ctx["provider_payment_id"],
            "provider_refund_reference": f"re_test_fixture_{suffix}",
            "amount_cents": 100,
            "currency": "usd",
            "status": "pending",
            "idempotency_key": "refund-idem",
        },
        {},
    )
    first = await initiate_webstore_refund(
        tenant_id=ctx["tenant_id"], webstore_id=ctx["webstore_id"], payment_id=ctx["payment_id"], amount_cents=100,
        reason="Buyer requested refund", actor_user_id="staff", actor_email="staff@example.com", idempotency_key="refund-idem",
        provider=provider, provider_authority=authority,
    )
    replay = await initiate_webstore_refund(
        tenant_id=ctx["tenant_id"], webstore_id=ctx["webstore_id"], payment_id=ctx["payment_id"], amount_cents=100,
        reason="Buyer requested refund", actor_user_id="staff", actor_email="staff@example.com", idempotency_key="refund-idem",
        provider=provider, provider_authority=authority,
    )
    assert first["refund"]["id"] == replay["refund"]["id"]
    assert provider.refund_calls == 2
    assert await db.payments.count_documents({"tenant_id": ctx["tenant_id"], "refund_of_payment_id": ctx["payment_id"]}) == 1


@pytest.mark.asyncio
async def test_payout_and_dispute_reconciliation_accept_only_typed_events_and_reject_conflicts():
    ctx = await _seed_refundable_webstore(uuid.uuid4().hex[:8])
    authority = ProviderAuthority("test-fixture", "test", "acct_test_fixture", "test-fixture", True, True)
    event_data = {
        "event_type": "payout",
        "provider": "test-fixture",
        "provider_mode": "test",
        "provider_account_reference": "acct_test_fixture",
        "provider_event_id": "evt_payout_fixture",
        "provider_payment_reference": ctx["provider_payment_id"],
        "amount_cents": 100,
        "currency": "usd",
        "status": "paid",
        "sequence": 1,
        "raw_event_snapshot": {"event_type": "transfer.created", "provider_event_id": "evt_payout_fixture"},
    }
    provider = _TypedProviderFixture({}, event_data)
    first = await reconcile_webstore_financial_event(
        tenant_id=ctx["tenant_id"], webstore_id=ctx["webstore_id"], provider=provider, provider_authority=authority,
    )
    replay = await reconcile_webstore_financial_event(
        tenant_id=ctx["tenant_id"], webstore_id=ctx["webstore_id"], provider_event=ProviderFinancialEvent(**event_data), provider_authority=authority,
    )
    assert first["already_processed"] is False
    assert replay["already_processed"] is True
    activity = await db.webstore_activity_events.find_one(
        {"tenant_id": ctx["tenant_id"], "action": "webstore.provider_financial_event_reconciled"},
        {"_id": 0},
    )
    assert activity["metadata"]["raw_event_snapshot"]["event_type"] == "transfer.created"
    conflict = ProviderFinancialEvent(**{**event_data, "amount_cents": 200})
    with pytest.raises(WebstoreError) as error:
        await reconcile_webstore_financial_event(
            tenant_id=ctx["tenant_id"], webstore_id=ctx["webstore_id"], provider_event=conflict, provider_authority=authority,
        )
    assert error.value.code == "provider_event_conflict"


@pytest.mark.parametrize(
    ("authority", "expected_state"),
    [
        (ProviderAuthority("stripe", "test", "acct_test", "deferred", True, True), "test_configuration_incomplete"),
        (ProviderAuthority("stripe", "test", "acct_test", "destination", True, False), "connected_verification_required"),
        (ProviderAuthority("stripe", "test", "acct_test", "destination", True, True, restriction_status="restricted"), "restricted"),
        (ProviderAuthority("stripe", "test", "acct_test", "destination", True, True), "ready_for_test_checkout"),
        (ProviderAuthority("stripe", "live", "acct_live", "destination", True, True), "live_ready"),
    ],
)
def test_provider_status_maps_all_authoritative_states(monkeypatch: pytest.MonkeyPatch, authority, expected_state):
    settings = _settings(
        monkeypatch,
        STRIPE_ENABLED="true",
        STRIPE_MODE=authority.mode,
        STRIPE_SECRET_KEY=f"sk_{authority.mode}_foundation_only",
        STRIPE_PUBLISHABLE_KEY=f"pk_{authority.mode}_foundation_only",
        STRIPE_CONNECT_CHARGE_MODEL=authority.charge_model,
    )
    status = provider_configuration_status(settings, authority)
    assert status["state"] == expected_state
    assert status["label"] in {
        "Connected — verification required",
        "Test configuration incomplete",
        "Restricted",
        "Ready for test checkout",
        "Live ready",
    }
    if expected_state in {"ready_for_test_checkout", "live_ready"}:
        assert status["provider_authority"] is True


def test_provider_status_rejects_connected_account_mode_mismatch(monkeypatch: pytest.MonkeyPatch):
    settings = _settings(
        monkeypatch,
        STRIPE_ENABLED="true",
        STRIPE_MODE="live",
        STRIPE_SECRET_KEY="sk_live_mode_mismatch",
        STRIPE_PUBLISHABLE_KEY="pk_live_mode_mismatch",
        STRIPE_CONNECT_CHARGE_MODEL="destination",
    )
    authority = ProviderAuthority("stripe", "test", "acct_test", "destination", True, True)

    status = provider_configuration_status(settings, authority)

    assert status["state"] == "connected_verification_required"
    assert status["provider_authority"] is False
    assert "webstore_stripe_mode_mismatch" in status["violations"]


@pytest.mark.asyncio
async def test_typed_verified_payment_conversion_is_exactly_once_and_excludes_raw_payload(monkeypatch: pytest.MonkeyPatch):
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-provider-conversion-{suffix}"
    intent_id = f"intent-{suffix}"
    webstore_id = f"ws-{suffix}"
    payment_id = f"pi_test_{suffix}"
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "Provider Conversion"})
    await db.webstores.insert_one({"id": webstore_id, "tenant_id": tenant_id, "name": "Provider Conversion", "slug": webstore_id, "public_slug": webstore_id, "status": "live"})
    await db.webstore_purchase_intents.insert_one(
        {
            "id": intent_id,
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "public_slug": webstore_id,
            "buyer_name": "Typed Buyer",
            "buyer_email": f"typed-{suffix}@example.com",
            "line_items": [],
            "product_subtotal_cents": 1000,
            "total_cents": 1000,
            "currency": "usd",
            "status": "pending_payment",
            "idempotency_key": f"intent-{suffix}",
            "canonical_order_id": None,
            "canonical_payment_id": None,
            "immutable_snapshot": {"financial_lines": []},
        }
    )
    authority = ProviderAuthority("test-fixture", "test", "acct_test_fixture", "test-fixture", True, True)
    verified = VerifiedProviderPayment(
        provider="test-fixture",
        provider_mode="test",
        provider_account_reference="acct_test_fixture",
        provider_event_id=f"evt_{suffix}",
        provider_payment_id=payment_id,
        purchase_intent_id=intent_id,
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        amount_cents=1000,
        currency="usd",
    )
    first = await process_verified_payment_event(provider_authority=authority, verified_payment=verified)
    replay = await process_verified_payment_event(provider_authority=authority, verified_payment=verified)
    assert first["order"]["id"] == replay["order_id"]
    assert await db.orders.count_documents({"tenant_id": tenant_id}) == 1
    assert await db.payments.count_documents({"tenant_id": tenant_id}) == 1
    assert await db.webstore_payment_events.count_documents({"tenant_id": tenant_id}) == 1
    event = await db.webstore_payment_events.find_one({"tenant_id": tenant_id}, {"_id": 0})
    assert "raw_event_snapshot" not in event
