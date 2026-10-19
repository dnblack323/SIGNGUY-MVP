"""Webstores Phase 1 - payment safety locks (Stage A0).

Covers: direct-charge-only Stripe Connect configuration, the separate Connect
webhook secret, the per-product platform-fee lock, the go-live payment gate,
retired per-store Stripe actions, and the removed QR placeholder link.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.db import db
from app.core.security_guards import collect_webstore_stripe_violations
from app.deps import get_current_user
from app.services.webstore_payment_provider import ProviderAuthority, provider_configuration_status
from app.services.webstore_payment_provider_stripe import StripeWebstorePaymentProvider
from app.services.webstore_shared_contracts import _locked_platform_fee_basis_points
from app.services.webstore_context import WebstoreError
from server import app


def _stripe_settings(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> Settings:
    values = {
        "STRIPE_ENABLED": "true",
        "STRIPE_MODE": "test",
        "STRIPE_SECRET_KEY": "sk_test_phase1",
        "STRIPE_PUBLISHABLE_KEY": "pk_test_phase1",
        "STRIPE_CONNECT_CLIENT_ID": "ca_phase1",
        "STRIPE_CONNECT_RETURN_URL": "https://example.test/connect/return",
        "STRIPE_CONNECT_REFRESH_URL": "https://example.test/connect/refresh",
        "STRIPE_CHECKOUT_SUCCESS_URL": "https://example.test/checkout/success",
        "STRIPE_CHECKOUT_CANCEL_URL": "https://example.test/checkout/cancel",
        "STRIPE_CONNECT_CHARGE_MODEL": "direct",
        "STRIPE_WEBHOOK_SECRET": "whsec_platform_phase1",
        "STRIPE_CONNECT_WEBHOOK_SECRET": "whsec_connect_phase1",
    }
    values.update(overrides)
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return Settings()


def _codes(settings: Settings) -> set[str]:
    return {violation.code for violation in collect_webstore_stripe_violations(settings)}


# ---------------------------------------------------------------- charge model


def test_direct_charge_model_is_the_only_accepted_model(monkeypatch: pytest.MonkeyPatch):
    assert _codes(_stripe_settings(monkeypatch)) == set()


@pytest.mark.parametrize("model", ["destination", "separate"])
def test_platform_merchant_charge_models_are_rejected(monkeypatch: pytest.MonkeyPatch, model: str):
    settings = _stripe_settings(monkeypatch, STRIPE_CONNECT_CHARGE_MODEL=model)
    assert "webstore_stripe_charge_model_not_allowed" in _codes(settings)
    assert provider_configuration_status(settings)["provider_authority"] is False


def test_unknown_and_deferred_charge_models_still_fail_closed(monkeypatch: pytest.MonkeyPatch):
    assert "webstore_stripe_charge_model_invalid" in _codes(_stripe_settings(monkeypatch, STRIPE_CONNECT_CHARGE_MODEL="split"))
    assert "webstore_stripe_charge_model_deferred" in _codes(_stripe_settings(monkeypatch, STRIPE_CONNECT_CHARGE_MODEL="deferred"))


@pytest.mark.parametrize("model", ["destination", "separate", "test-fixture"])
def test_non_direct_provider_authority_never_grants_checkout(monkeypatch: pytest.MonkeyPatch, model: str):
    settings = _stripe_settings(monkeypatch)
    authority = ProviderAuthority("stripe", "test", "acct_phase1", model, True, True)
    status = provider_configuration_status(settings, authority)
    assert status["provider_authority"] is False
    assert status["violations"] == ["webstore_stripe_charge_model_not_allowed"]


@pytest.mark.asyncio
async def test_checkout_adapter_refuses_non_direct_model_without_calling_stripe(monkeypatch: pytest.MonkeyPatch):
    settings = _stripe_settings(monkeypatch)
    settings.stripe_charge_model = "destination"
    calls: list[dict] = []
    monkeypatch.setattr(
        "app.services.webstore_payment_provider.stripe.checkout.Session.create",
        lambda **kwargs: calls.append(kwargs),
    )
    result = await StripeWebstorePaymentProvider(settings).create_checkout_session(
        tenant_id="tenant-a",
        webstore_id="store-a",
        purchase_intent_id="intent-a",
        connected_account_reference="acct_phase1",
        line_items=[{"name": "Shirt", "quantity": 1, "unit_amount_cents": 2500}],
        idempotency_key="intent-a",
    )
    assert result.ok is False
    assert calls == []


# -------------------------------------------------------------- webhook secret


def test_connect_webhook_secret_is_required_and_must_differ_from_platform_secret(monkeypatch: pytest.MonkeyPatch):
    missing = _stripe_settings(monkeypatch, STRIPE_CONNECT_WEBHOOK_SECRET="")
    assert "webstore_stripe_webhook_unavailable" in _codes(missing)
    shared = _stripe_settings(monkeypatch, STRIPE_CONNECT_WEBHOOK_SECRET="whsec_platform_phase1")
    assert "webstore_stripe_webhook_secret_shared" in _codes(shared)


def _signature(payload: bytes, secret: str) -> str:
    timestamp = int(time.time())
    signed = f"{timestamp}.".encode("utf-8") + payload
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def test_webstore_webhook_rejects_events_signed_with_the_platform_secret(monkeypatch: pytest.MonkeyPatch):
    settings = _stripe_settings(monkeypatch)
    provider = StripeWebstorePaymentProvider(settings)
    payload = json.dumps({"id": "evt_phase1", "object": "event", "type": "customer.created", "data": {"object": {}}}).encode("utf-8")

    platform_signed = provider.verify_webhook_signature_and_parse(payload=payload, signature=_signature(payload, "whsec_platform_phase1"))
    assert platform_signed.ok is False

    connect_signed = provider.verify_webhook_signature_and_parse(payload=payload, signature=_signature(payload, "whsec_connect_phase1"))
    assert connect_signed.ok is True
    assert connect_signed.data["ignored"] is True


# ---------------------------------------------------------------- platform fee


def test_platform_fee_lock_defaults_to_zero_and_rejects_other_values():
    assert _locked_platform_fee_basis_points(None) == 0
    assert _locked_platform_fee_basis_points("") == 0
    assert _locked_platform_fee_basis_points(0) == 0
    with pytest.raises(WebstoreError) as excinfo:
        _locked_platform_fee_basis_points(200)
    assert excinfo.value.code == "platform_fee_locked"


def _override(user: dict):
    async def _get():
        return {**user}

    return _get


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest_asyncio.fixture
async def phase1_ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-phase1-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "Phase 1 Tenant"})
    await db.users.insert_one(owner)
    yield {"tenant_id": tenant_id, "owner": owner, "suffix": suffix}
    app.dependency_overrides.pop(get_current_user, None)


async def _create_store(client: AsyncClient, suffix: str) -> dict:
    owner_resp = await client.post(
        "/api/webstores/owners",
        json={"name": "Store Chair", "email": f"chair-{suffix}@example.com", "organization": "Boosters"},
    )
    assert owner_resp.status_code == 201, owner_resp.text
    store_resp = await client.post(
        "/api/webstores",
        json={"owner_id": owner_resp.json()["id"], "name": f"Phase1 Store {suffix}", "slug": f"phase1-{suffix}", "store_type": "general"},
    )
    assert store_resp.status_code == 201, store_resp.text
    return store_resp.json()


@pytest.mark.asyncio
async def test_api_refuses_nonzero_platform_fee_on_templates_and_products(phase1_ctx):
    suffix = phase1_ctx["suffix"]
    async with await _client_as(phase1_ctx["owner"]) as client:
        store = await _create_store(client, suffix)

        refused_template = await client.post(
            "/api/webstores/product-templates",
            json={"template_name": f"Tee {suffix}", "product_category": "apparel", "product_type": "t_shirt", "platform_fee_basis_points": 200},
        )
        assert refused_template.status_code == 400, refused_template.text

        template = await client.post(
            "/api/webstores/product-templates",
            json={"template_name": f"Tee {suffix}", "product_category": "apparel", "product_type": "t_shirt"},
        )
        assert template.status_code == 201, template.text
        assert template.json()["platform_fee_basis_points"] == 0
        refused_template_patch = await client.patch(
            f"/api/webstores/product-templates/{template.json()['id']}",
            json={"expected_revision": template.json()["revision"], "platform_fee_basis_points": 150},
        )
        assert refused_template_patch.status_code == 400, refused_template_patch.text

        refused_product = await client.post(
            f"/api/webstores/{store['id']}/products",
            json={"name": "Shirt", "selling_price_cents": 2500, "platform_fee_basis_points": 200},
        )
        assert refused_product.status_code == 400, refused_product.text

        product = await client.post(f"/api/webstores/{store['id']}/products", json={"name": "Shirt", "selling_price_cents": 2500})
        assert product.status_code == 201, product.text
        assert product.json()["platform_fee_basis_points"] == 0
        refused_patch = await client.patch(
            f"/api/webstores/{store['id']}/products/{product.json()['id']}",
            json={"expected_revision": product.json()["revision"], "platform_fee_basis_points": 100},
        )
        assert refused_patch.status_code == 400, refused_patch.text


# ---------------------------------------------------- retired per-store actions


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["connect", "resume_onboarding", "disconnect"])
async def test_per_store_stripe_onboarding_and_disconnect_are_retired(phase1_ctx, action: str):
    async with await _client_as(phase1_ctx["owner"]) as client:
        store = await _create_store(client, f"{phase1_ctx['suffix']}-{action}")
        status = await client.get(f"/api/webstores/{store['id']}/payment-provider")
        assert status.status_code == 200, status.text
        actions = status.json()["actions"]
        assert actions["connect"] is False
        assert actions["resume_onboarding"] is False
        assert actions["disconnect"] is False

        retired = await client.post(f"/api/webstores/{store['id']}/payment-provider/{action}")
        assert retired.status_code == 409, retired.text
        assert await db.webstore_stripe_connect_records.count_documents({"tenant_id": phase1_ctx["tenant_id"], "webstore_id": store["id"]}) == 0
