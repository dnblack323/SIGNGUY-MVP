"""Focused Stage 7 Stripe Connect and checkout boundary tests."""
from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest

from app.core.config import Settings
from app.core.db import db
from app.services import webstores as webstores_service
from app.services.webstore_payment_provider import (
    ProviderAuthority,
    ProviderResult,
    StripeWebstorePaymentProvider,
    VerifiedProviderPayment,
    get_webstore_payment_provider,
)
from app.services.webstore_payments import (
    process_verified_payment_event,
    reconcile_webstore_payment_status_event,
)


def _settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    values = {
        "STRIPE_ENABLED": "true",
        "STRIPE_MODE": "test",
        "STRIPE_SECRET_KEY": "sk_test_stage7",
        "STRIPE_PUBLISHABLE_KEY": "pk_test_stage7",
        "STRIPE_CONNECT_CLIENT_ID": "ca_stage7",
        "STRIPE_CONNECT_RETURN_URL": "https://example.test/connect/return",
        "STRIPE_CONNECT_REFRESH_URL": "https://example.test/connect/refresh",
        "STRIPE_CHECKOUT_SUCCESS_URL": "https://example.test/checkout/success",
        "STRIPE_CHECKOUT_CANCEL_URL": "https://example.test/checkout/cancel",
        "STRIPE_CONNECT_CHARGE_MODEL": "destination",
        "STRIPE_WEBHOOK_SECRET": "whsec_stage7",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return Settings()


@pytest.mark.asyncio
async def test_configured_factory_selects_real_adapter_without_network(monkeypatch: pytest.MonkeyPatch):
    settings = _settings(monkeypatch)
    provider = get_webstore_payment_provider(settings)
    assert isinstance(provider, StripeWebstorePaymentProvider)

    account_calls: list[dict] = []

    def create_account(**kwargs):
        account_calls.append(kwargs)
        return SimpleNamespace(id="acct_stage7")

    def create_link(**kwargs):
        return SimpleNamespace(url="https://connect.stripe.test/onboarding")

    monkeypatch.setattr("app.services.webstore_payment_provider.stripe.Account.create", create_account)
    monkeypatch.setattr("app.services.webstore_payment_provider.stripe.AccountLink.create", create_link)
    result = await provider.create_connected_account_onboarding_link(tenant_id="tenant-a", webstore_id="store-a")

    assert result.ok is True
    assert result.data["account_reference"] == "acct_stage7"
    assert result.data["onboarding_url"].startswith("https://")
    assert account_calls[0]["metadata"]["tenant_id"] == "tenant-a"


@pytest.mark.asyncio
async def test_checkout_session_uses_server_line_items_and_destination_account(monkeypatch: pytest.MonkeyPatch):
    settings = _settings(monkeypatch)
    provider = StripeWebstorePaymentProvider(settings)
    captured: dict = {}

    def create_session(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id="cs_stage7", url="https://checkout.stripe.test/cs_stage7", status="open", payment_status="unpaid")

    monkeypatch.setattr("app.services.webstore_payment_provider.stripe.checkout.Session.create", create_session)
    result = await provider.create_checkout_session(
        tenant_id="tenant-a",
        webstore_id="store-a",
        purchase_intent_id="intent-a",
        buyer_email="buyer@example.com",
        connected_account_reference="acct_stage7",
        currency="usd",
        line_items=[{"name": "Team Shirt", "quantity": 2, "unit_amount_cents": 2500}],
        idempotency_key="intent-a",
    )

    assert result.ok is True
    assert result.data["checkout_session_id"] == "cs_stage7"
    assert captured["line_items"][0]["price_data"]["unit_amount"] == 2500
    assert captured["payment_intent_data"]["transfer_data"] == {"destination": "acct_stage7"}
    assert captured["metadata"]["purchase_intent_id"] == "intent-a"


def test_stripe_webhook_parser_returns_typed_metadata_without_raw_payload(monkeypatch: pytest.MonkeyPatch):
    settings = _settings(monkeypatch)
    provider = StripeWebstorePaymentProvider(settings)
    event = {
        "id": "evt_stage7",
        "type": "checkout.session.completed",
        "account": "acct_stage7",
        "data": {
            "object": {
                "id": "cs_stage7",
                "payment_intent": "pi_stage7",
                "amount_total": 5000,
                "currency": "usd",
                "payment_status": "paid",
                "metadata": {"tenant_id": "tenant-a", "webstore_id": "store-a", "purchase_intent_id": "intent-a"},
            }
        },
    }
    monkeypatch.setattr("app.services.webstore_payment_provider.stripe.Webhook.construct_event", lambda *args: event)

    result = provider.verify_webhook_signature_and_parse(payload=b"{}", signature="sig")

    assert result.ok is True
    assert result.data["provider_event_id"] == "evt_stage7"
    assert result.data["provider_payment_id"] == "pi_stage7"
    assert result.data["raw_event_snapshot"]["event_type"] == "checkout.session.completed"
    assert "payload" not in result.data["raw_event_snapshot"]


def test_stripe_webhook_parser_keeps_unpaid_checkout_pending(monkeypatch: pytest.MonkeyPatch):
    settings = _settings(monkeypatch)
    provider = StripeWebstorePaymentProvider(settings)
    event = {
        "id": "evt_unpaid_stage7",
        "type": "checkout.session.completed",
        "account": "acct_stage7",
        "data": {
            "object": {
                "id": "cs_unpaid_stage7",
                "payment_intent": "pi_unpaid_stage7",
                "amount_total": 5000,
                "currency": "usd",
                "payment_status": "unpaid",
                "metadata": {"tenant_id": "tenant-a", "webstore_id": "store-a", "purchase_intent_id": "intent-a"},
            }
        },
    }
    monkeypatch.setattr("app.services.webstore_payment_provider.stripe.Webhook.construct_event", lambda *args: event)

    result = provider.verify_webhook_signature_and_parse(payload=b"{}", signature="sig")

    assert result.ok is True
    assert result.data["event_kind"] == "payment_pending"
    assert result.data["status"] == "pending"


def test_stripe_webhook_parser_normalizes_failed_payment(monkeypatch: pytest.MonkeyPatch):
    settings = _settings(monkeypatch)
    provider = StripeWebstorePaymentProvider(settings)
    event = {
        "id": "evt_failed_stage7",
        "type": "payment_intent.payment_failed",
        "account": "acct_stage7",
        "data": {
            "object": {
                "id": "pi_failed_stage7",
                "amount": 5000,
                "currency": "usd",
                "last_payment_error": {"code": "card_declined", "message": "Card was declined."},
                "metadata": {"tenant_id": "tenant-a", "webstore_id": "store-a", "purchase_intent_id": "intent-a"},
            }
        },
    }
    monkeypatch.setattr("app.services.webstore_payment_provider.stripe.Webhook.construct_event", lambda *args: event)

    result = provider.verify_webhook_signature_and_parse(payload=b"{}", signature="sig")

    assert result.ok is True
    assert result.data["event_kind"] == "payment_failure"
    assert result.data["failure_code"] == "card_declined"
    assert result.data["failure_reason"] == "Card was declined."


def test_stripe_webhook_parser_normalizes_financial_events_for_existing_ledger_service(monkeypatch: pytest.MonkeyPatch):
    settings = _settings(monkeypatch)
    provider = StripeWebstorePaymentProvider(settings)
    event = {
        "id": "evt_transfer_stage7",
        "type": "transfer.created",
        "account": "acct_stage7",
        "data": {
            "object": {
                "id": "tr_stage7",
                "amount": 2500,
                "currency": "usd",
                "status": "paid",
                "metadata": {
                    "tenant_id": "tenant-a",
                    "webstore_id": "store-a",
                    "provider_payment_reference": "pi_stage7",
                    "sequence": "2",
                },
            }
        },
    }
    monkeypatch.setattr("app.services.webstore_payment_provider.stripe.Webhook.construct_event", lambda *args: event)

    result = provider.verify_webhook_signature_and_parse(payload=b"{}", signature="sig")

    assert result.ok is True
    assert result.data["event_kind"] == "financial"
    assert result.data["event_type"] == "transfer"
    assert result.data["provider_payment_reference"] == "pi_stage7"
    assert result.data["sequence"] == 2
    assert result.data["raw_event_snapshot"]["event_type"] == "transfer.created"
    assert "payload" not in result.data["raw_event_snapshot"]


def test_stripe_webhook_parser_normalizes_refund_events(monkeypatch: pytest.MonkeyPatch):
    settings = _settings(monkeypatch)
    provider = StripeWebstorePaymentProvider(settings)
    event = {
        "id": "evt_refund_stage7",
        "type": "refund.created",
        "account": "acct_stage7",
        "data": {
            "object": {
                "id": "re_stage7",
                "payment_intent": "pi_stage7",
                "amount": 1200,
                "currency": "usd",
                "status": "pending",
                "metadata": {
                    "tenant_id": "tenant-a",
                    "webstore_id": "store-a",
                    "purchase_intent_id": "intent-a",
                    "idempotency_key": "refund-stage7",
                },
            }
        },
    }
    monkeypatch.setattr("app.services.webstore_payment_provider.stripe.Webhook.construct_event", lambda *args: event)

    result = provider.verify_webhook_signature_and_parse(payload=b"{}", signature="sig")

    assert result.ok is True
    assert result.data["event_kind"] == "refund"
    assert result.data["provider_refund_reference"] == "re_stage7"
    assert result.data["idempotency_key"] == "refund-stage7"


@pytest.mark.asyncio
async def test_webstore_payment_readiness_uses_its_connected_account(monkeypatch: pytest.MonkeyPatch):
    settings = _settings(monkeypatch)
    monkeypatch.setattr(webstores_service, "get_settings", lambda: settings)
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"tenant-readiness-stage7-{suffix}"
    webstore_id = f"store-readiness-stage7-{suffix}"
    await db.webstore_stripe_connect_records.insert_one(
        {
            "id": f"connect-readiness-stage7-{suffix}",
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "record_type": "connected_account",
            "provider_mode": "test",
            "connected_account_reference": "acct_stage7",
            "onboarding_state": "complete",
            "charges_enabled": True,
            "payouts_enabled": True,
            "requirements_currently_due": [],
        }
    )

    readiness = await webstores_service._payment_readiness({"id": webstore_id, "tenant_id": tenant_id})

    assert readiness["ready"] is True
    assert readiness["provider_authority"] is True
    assert readiness["provider_account_reference"] == "acct_stage7"


@pytest.mark.asyncio
async def test_refund_webhook_reuses_refund_and_ledger_rows(monkeypatch: pytest.MonkeyPatch):
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"tenant-refund-stage7-{suffix}"
    webstore_id = f"store-refund-stage7-{suffix}"
    intent_id = f"intent-refund-stage7-{suffix}"
    payment_id = f"payment-refund-stage7-{suffix}"
    refund_id = f"refund-refund-stage7-{suffix}"
    payment_reference = f"pi-refund-stage7-{suffix}"
    await db.webstore_purchase_intents.insert_one(
        {
            "id": intent_id,
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "public_slug": f"public-refund-stage7-{suffix}",
            "buyer_name": "Refund Buyer",
            "buyer_email": f"refund-{suffix}@example.com",
            "line_items": [],
            "total_cents": 2500,
            "currency": "usd",
            "status": "paid_order_created",
            "provider_payment_id": payment_reference,
            "canonical_payment_id": payment_id,
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
            "amount_cents": 2500,
            "currency": "usd",
            "stripe_payment_intent_id": payment_reference,
        }
    )
    await db.payments.insert_one(
        {
            "id": refund_id,
            "tenant_id": tenant_id,
            "invoice_id": f"webstore_purchase_intent:{intent_id}",
            "customer_id": f"customer-{suffix}",
            "order_id": f"order-{suffix}",
            "source": "stripe",
            "status": "pending",
            "amount_cents": 1200,
            "currency": "usd",
            "stripe_refund_id": f"re-{suffix}",
            "refund_of_payment_id": payment_id,
            "idempotency_key": f"refund-{suffix}",
        }
    )
    authority = ProviderAuthority("stripe", "test", "acct_stage7", "destination", True, True)
    result = ProviderResult.success(
        {
            "event_kind": "refund",
            "provider": "stripe",
            "provider_mode": "test",
            "provider_event_id": f"evt-refund-{suffix}",
            "provider_refund_reference": f"re-{suffix}",
                "provider_payment_reference": payment_reference,
                "provider_account_reference": "acct_stage7",
                "tenant_id": tenant_id,
                "webstore_id": webstore_id,
                "amount_cents": 1200,
            "currency": "usd",
            "status": "pending",
            "idempotency_key": f"refund-{suffix}",
        }
    )
    from app.services.webstore_payments import reconcile_webstore_refund_event

    first = await reconcile_webstore_refund_event(
        tenant_id=tenant_id, webstore_id=webstore_id, provider_result=result, provider_authority=authority
    )
    replay = await reconcile_webstore_refund_event(
        tenant_id=tenant_id, webstore_id=webstore_id, provider_result=result, provider_authority=authority
    )

    assert first["refund"]["id"] == refund_id
    assert replay["refund"]["id"] == refund_id
    assert await db.payments.count_documents({"tenant_id": tenant_id, "stripe_refund_id": f"re-{suffix}"}) == 1
    assert await db.webstore_ledger_entries.count_documents({"tenant_id": tenant_id, "source_id": refund_id}) == 1


@pytest.mark.asyncio
async def test_failed_refund_webhook_is_authority_checked_and_idempotent():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"tenant-failed-refund-stage7-{suffix}"
    webstore_id = f"store-failed-refund-stage7-{suffix}"
    authority = ProviderAuthority("stripe", "test", "acct_stage7", "destination", True, True)
    result = ProviderResult.success(
        {
            "event_kind": "refund",
            "provider": "stripe",
            "provider_mode": "test",
            "provider_event_id": f"evt-failed-refund-{suffix}",
            "provider_refund_reference": f"re-failed-{suffix}",
            "provider_payment_reference": f"pi-failed-refund-{suffix}",
            "provider_account_reference": "acct_stage7",
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "amount_cents": 1200,
            "currency": "usd",
            "status": "failed",
            "raw_event_snapshot": {"event_type": "refund.updated", "status": "failed"},
        }
    )
    from app.services.webstore_payments import reconcile_webstore_refund_event

    first = await reconcile_webstore_refund_event(
        tenant_id=tenant_id, webstore_id=webstore_id, provider_result=result, provider_authority=authority
    )
    replay = await reconcile_webstore_refund_event(
        tenant_id=tenant_id, webstore_id=webstore_id, provider_result=result, provider_authority=authority
    )

    assert first["already_processed"] is False
    assert replay["already_processed"] is True
    assert await db.webstore_activity_events.count_documents(
        {"tenant_id": tenant_id, "action": "webstore.refund_failed"}
    ) == 1
    assert await db.payments.count_documents({"tenant_id": tenant_id}) == 0


class _CheckoutFixture:
    def __init__(self):
        self.calls = 0

    async def create_checkout_session(self, **kwargs):
        self.calls += 1
        return ProviderResult.success(
            {
                "provider": "stripe",
                "provider_mode": "test",
                "account_reference": kwargs["connected_account_reference"],
                "checkout_session_id": "cs_fixture",
                "checkout_url": "https://checkout.stripe.test/cs_fixture",
                "checkout_status": "open",
            }
        )


@pytest.mark.asyncio
async def test_checkout_service_reuses_intent_and_never_creates_order(monkeypatch: pytest.MonkeyPatch):
    settings = _settings(monkeypatch)
    monkeypatch.setattr(webstores_service, "get_settings", lambda: settings)
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"tenant-stage7-{suffix}"
    webstore_id = f"store-stage7-{suffix}"
    public_slug = f"public-stage7-{suffix}"
    product_id = f"product-stage7-{suffix}"
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "Stage 7"})
    await db.webstores.insert_one(
        {
            "id": webstore_id,
            "tenant_id": tenant_id,
            "name": "Stage 7 Store",
            "slug": webstore_id,
            "public_slug": public_slug,
            "status": "live",
            "checkout_enabled": True,
        }
    )
    await db.webstore_stripe_connect_records.insert_one(
        {
            "id": f"connect-{suffix}",
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "record_type": "connected_account",
            "provider_mode": "test",
            "connected_account_reference": "acct_stage7",
            "onboarding_state": "complete",
            "charges_enabled": True,
            "payouts_enabled": True,
            "requirements_currently_due": [],
        }
    )
    await db.webstore_products.insert_one(
        {
            "id": product_id,
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "name": "Stage 7 Shirt",
            "description": "Approved shirt",
            "product_type": "shirt",
            "selling_price_cents": 2500,
            "status": "active",
            "public": True,
            "approval_status": "approved",
            "approval_revision": 1,
            "revision": 1,
            "fulfillment_methods": ["pickup"],
            "default_fulfillment_method": "pickup",
            "variants": [],
        }
    )
    provider = _CheckoutFixture()
    monkeypatch.setattr(webstores_service, "get_webstore_payment_provider", lambda settings: provider)

    fields = {
        "buyer_name": "Buyer",
        "buyer_email": f"buyer-{suffix}@example.com",
        "line_items": [{"product_id": product_id, "quantity": 1, "variant": {}, "personalization": {}}],
        "idempotency_key": f"checkout-{suffix}",
    }
    first = await webstores_service.create_checkout_session(public_slug, fields)
    replay = await webstores_service.create_checkout_session(public_slug, fields)

    assert first["checkout_available"] is True
    assert first["checkout"]["checkout_url"].startswith("https://")
    assert replay["purchase_intent"]["id"] == first["purchase_intent"]["id"]
    assert provider.calls == 1
    assert await db.orders.count_documents({"tenant_id": tenant_id}) == 0
    assert await db.webstore_purchase_intents.count_documents({"tenant_id": tenant_id}) == 1


@pytest.mark.asyncio
async def test_verified_webhook_holds_payment_for_stage8_without_order_or_production(monkeypatch: pytest.MonkeyPatch):
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"tenant-webhook-stage7-{suffix}"
    webstore_id = f"store-webhook-stage7-{suffix}"
    intent_id = f"intent-webhook-stage7-{suffix}"
    await db.webstore_purchase_intents.insert_one(
        {
            "id": intent_id,
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "public_slug": f"public-webhook-stage7-{suffix}",
            "buyer_name": "Webhook Buyer",
            "buyer_email": f"webhook-{suffix}@example.com",
            "line_items": [],
            "product_subtotal_cents": 2500,
            "total_cents": 2500,
            "currency": "usd",
            "status": "pending_payment",
            "immutable_snapshot": {"financial_lines": []},
        }
    )
    authority = ProviderAuthority("stripe", "test", "acct_stage7", "destination", True, True)
    result = await process_verified_payment_event(
        verified_payment=VerifiedProviderPayment(
            provider="stripe",
            provider_mode="test",
            provider_account_reference="acct_stage7",
            provider_event_id=f"evt-webhook-stage7-{suffix}",
            provider_payment_id=f"pi-webhook-stage7-{suffix}",
            purchase_intent_id=intent_id,
            tenant_id=tenant_id,
            webstore_id=webstore_id,
            amount_cents=2500,
            currency="usd",
            raw_event_snapshot={"event_type": "checkout.session.completed", "amount_cents": 2500},
        ),
        provider_authority=authority,
        create_downstream_records=False,
    )

    intent = await db.webstore_purchase_intents.find_one({"id": intent_id}, {"_id": 0})
    event = await db.webstore_payment_events.find_one({"id": result["payment_event"]["id"]}, {"_id": 0})
    assert result["stage8_handoff"] is True
    assert intent["status"] == "payment_verified"
    assert intent.get("canonical_order_id") is None
    assert event["raw_event_snapshot"]["event_type"] == "checkout.session.completed"
    assert await db.orders.count_documents({"tenant_id": tenant_id}) == 0
    assert await db.work_orders.count_documents({"tenant_id": tenant_id}) == 0


@pytest.mark.asyncio
async def test_verified_payment_rejects_wrong_webstore_reference():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"tenant-isolation-stage7-{suffix}"
    webstore_id = f"store-isolation-stage7-{suffix}"
    wrong_webstore_id = f"store-other-stage7-{suffix}"
    intent_id = f"intent-isolation-stage7-{suffix}"
    await db.webstore_purchase_intents.insert_one(
        {
            "id": intent_id,
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "public_slug": f"public-isolation-stage7-{suffix}",
            "buyer_name": "Isolation Buyer",
            "buyer_email": f"isolation-{suffix}@example.com",
            "line_items": [],
            "total_cents": 2500,
            "currency": "usd",
            "status": "pending_payment",
        }
    )
    authority = ProviderAuthority("stripe", "test", "acct_stage7", "destination", True, True)

    with pytest.raises(webstores_service.WebstoreError) as error:
        await process_verified_payment_event(
            verified_payment=VerifiedProviderPayment(
                provider="stripe",
                provider_mode="test",
                provider_account_reference="acct_stage7",
                provider_event_id=f"evt-isolation-stage7-{suffix}",
                provider_payment_id=f"pi-isolation-stage7-{suffix}",
                purchase_intent_id=intent_id,
                tenant_id=tenant_id,
                webstore_id=wrong_webstore_id,
                amount_cents=2500,
                currency="usd",
            ),
            provider_authority=authority,
            create_downstream_records=False,
        )

    assert error.value.code == "webstore_event_mismatch"
    assert await db.webstore_payment_events.count_documents({"tenant_id": tenant_id}) == 0
    assert await db.payments.count_documents({"tenant_id": tenant_id}) == 0


@pytest.mark.asyncio
async def test_failed_payment_event_is_idempotent_and_does_not_create_commerce_records():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"tenant-failed-stage7-{suffix}"
    webstore_id = f"store-failed-stage7-{suffix}"
    intent_id = f"intent-failed-stage7-{suffix}"
    payment_reference = f"pi-failed-stage7-{suffix}"
    await db.webstore_purchase_intents.insert_one(
        {
            "id": intent_id,
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "public_slug": f"public-failed-stage7-{suffix}",
            "buyer_name": "Failed Buyer",
            "buyer_email": f"failed-{suffix}@example.com",
            "line_items": [],
            "total_cents": 2500,
            "currency": "usd",
            "status": "pending_payment",
        }
    )
    authority = ProviderAuthority("stripe", "test", "acct_stage7", "destination", True, True)
    result = ProviderResult.success(
        {
            "event_kind": "payment_failure",
            "provider": "stripe",
            "provider_mode": "test",
            "provider_event_id": f"evt-failed-{suffix}",
            "provider_payment_id": payment_reference,
            "purchase_intent_id": intent_id,
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "provider_account_reference": "acct_stage7",
            "amount_cents": 2500,
            "currency": "usd",
            "status": "payment_failed",
            "failure_code": "card_declined",
            "failure_reason": "Card was declined.",
            "raw_event_snapshot": {"event_type": "payment_intent.payment_failed"},
        }
    )

    first = await reconcile_webstore_payment_status_event(
        tenant_id=tenant_id, webstore_id=webstore_id, provider_result=result, provider_authority=authority
    )
    replay = await reconcile_webstore_payment_status_event(
        tenant_id=tenant_id, webstore_id=webstore_id, provider_result=result, provider_authority=authority
    )

    intent = await db.webstore_purchase_intents.find_one({"id": intent_id}, {"_id": 0})
    assert first["payment_event"]["status"] == "failed"
    assert replay["already_processed"] is True
    assert intent["status"] == "payment_failed"
    assert await db.webstore_payment_events.count_documents({"tenant_id": tenant_id}) == 1
    assert await db.payments.count_documents({"tenant_id": tenant_id}) == 0
    assert await db.orders.count_documents({"tenant_id": tenant_id}) == 0
    assert await db.work_orders.count_documents({"tenant_id": tenant_id}) == 0


@pytest.mark.asyncio
async def test_pending_payment_event_is_idempotent_without_marking_intent_failed():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"tenant-pending-stage7-{suffix}"
    webstore_id = f"store-pending-stage7-{suffix}"
    intent_id = f"intent-pending-stage7-{suffix}"
    payment_reference = f"pi-pending-stage7-{suffix}"
    await db.webstore_purchase_intents.insert_one(
        {
            "id": intent_id,
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "public_slug": f"public-pending-stage7-{suffix}",
            "buyer_name": "Pending Buyer",
            "buyer_email": f"pending-{suffix}@example.com",
            "line_items": [],
            "total_cents": 2500,
            "currency": "usd",
            "status": "pending_payment",
        }
    )
    authority = ProviderAuthority("stripe", "test", "acct_stage7", "destination", True, True)
    result = ProviderResult.success(
        {
            "event_kind": "payment_pending",
            "provider": "stripe",
            "provider_mode": "test",
            "provider_event_id": f"evt-pending-{suffix}",
            "provider_payment_id": payment_reference,
            "purchase_intent_id": intent_id,
            "tenant_id": tenant_id,
            "webstore_id": webstore_id,
            "provider_account_reference": "acct_stage7",
            "amount_cents": 2500,
            "currency": "usd",
            "status": "pending",
            "raw_event_snapshot": {"event_type": "checkout.session.completed", "payment_status": "unpaid"},
        }
    )

    first = await reconcile_webstore_payment_status_event(
        tenant_id=tenant_id, webstore_id=webstore_id, provider_result=result, provider_authority=authority
    )
    replay = await reconcile_webstore_payment_status_event(
        tenant_id=tenant_id, webstore_id=webstore_id, provider_result=result, provider_authority=authority
    )

    intent = await db.webstore_purchase_intents.find_one({"id": intent_id}, {"_id": 0})
    assert first["payment_event"]["status"] == "processing"
    assert replay["payment_event"]["id"] == first["payment_event"]["id"]
    assert intent["status"] == "pending_payment"
    assert intent["reconciliation_state"] == "provider_pending"
    assert await db.webstore_payment_events.count_documents({"tenant_id": tenant_id}) == 1
    assert await db.payments.count_documents({"tenant_id": tenant_id}) == 0
    assert await db.orders.count_documents({"tenant_id": tenant_id}) == 0
