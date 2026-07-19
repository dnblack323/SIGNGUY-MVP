"""EC13 Phase 13A - commercial billing catalog and core contract tests."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.portal_security import create_portal_token
from app.deps import get_current_user
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
    tenant_id = f"t-13a-{suffix}"
    other_tenant_id = f"t-13a-other-{suffix}"
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
        "tenant_id": tenant_id,
        "other_tenant_id": other_tenant_id,
        "owner": owner,
        "staff": staff,
        "platform_admin": platform_admin,
        "other_owner": other_owner,
        "portal_token": portal_token,
    }
    app.dependency_overrides.pop(get_current_user, None)


async def _draft_catalog(client: AsyncClient, version_suffix: str) -> dict:
    response = await client.post(
        "/api/commercial/catalog/versions",
        json={"version": f"ec13a-{version_suffix}", "effective_at": _now(), "notes": "Phase 13A test catalog"},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _active_core_product(client: AsyncClient, catalog_id: str, key: str = "signguy-core") -> dict:
    response = await client.post(
        "/api/commercial/catalog/products",
        json={
            "catalog_version_id": catalog_id,
            "product_key": key,
            "name": "SignGuy Core",
            "product_type": "core",
            "status": "active",
            "owner_checkpoint": "EC13",
            "publishable": True,
            "stripe_sync_enabled": False,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_catalog_publish_price_immutability_and_purchase_rules(ctx):
    before = {
        "invoices": await db.invoices.count_documents({"tenant_id": ctx["tenant_id"]}),
        "payments": await db.payments.count_documents({"tenant_id": ctx["tenant_id"]}),
        "feature_entitlements": await db.feature_entitlements.count_documents({"tenant_id": ctx["tenant_id"]}),
    }

    async with await _client_as(ctx["owner"]) as owner:
        denied = await owner.post("/api/commercial/catalog/versions", json={"version": f"owner-denied-{uuid.uuid4().hex[:6]}"})
        assert denied.status_code == 403

    async with await _client_as(ctx["platform_admin"]) as platform:
        catalog = await _draft_catalog(platform, uuid.uuid4().hex[:6])
        product = await _active_core_product(platform, catalog["id"])
        duplicate_product = await platform.post(
            "/api/commercial/catalog/products",
            json={
                "catalog_version_id": catalog["id"],
                "product_key": "signguy-core",
                "name": "Duplicate",
                "product_type": "core",
            },
        )
        assert duplicate_product.status_code == 409

        publish_without_price = await platform.post(f"/api/commercial/catalog/versions/{catalog['id']}/publish")
        assert publish_without_price.status_code == 409

        float_price = await platform.post(
            "/api/commercial/catalog/prices",
            json={
                "catalog_version_id": catalog["id"],
                "product_id": product["id"],
                "price_key": "core-monthly-float",
                "billing_interval": "monthly",
                "amount_cents": 1999.5,
                "approved_by_owner": True,
            },
        )
        assert float_price.status_code == 422

        unapproved_active = await platform.post(
            "/api/commercial/catalog/prices",
            json={
                "catalog_version_id": catalog["id"],
                "product_id": product["id"],
                "price_key": "core-monthly-unapproved",
                "billing_interval": "monthly",
                "amount_cents": 19900,
                "is_active": True,
            },
        )
        assert unapproved_active.status_code == 409

        monthly = await platform.post(
            "/api/commercial/catalog/prices",
            json={
                "catalog_version_id": catalog["id"],
                "product_id": product["id"],
                "price_key": "core-monthly",
                "billing_interval": "monthly",
                "amount_cents": 19900,
                "is_active": True,
                "is_public": True,
                "approved_by_owner": True,
            },
        )
        annual = await platform.post(
            "/api/commercial/catalog/prices",
            json={
                "catalog_version_id": catalog["id"],
                "product_id": product["id"],
                "price_key": "core-annual",
                "billing_interval": "annual",
                "amount_cents": 199000,
                "is_active": True,
                "is_public": True,
                "approved_by_owner": True,
            },
        )
        assert monthly.status_code == 201, monthly.text
        assert annual.status_code == 201, annual.text

        revision = await platform.post(
            f"/api/commercial/catalog/prices/{monthly.json()['id']}/revisions",
            json={
                "price_key": "core-monthly-v2",
                "amount_cents": 24900,
                "billing_interval": "monthly",
                "is_active": True,
                "is_public": True,
                "approved_by_owner": True,
            },
        )
        assert revision.status_code == 201, revision.text
        assert revision.json()["replaces_price_id"] == monthly.json()["id"]

        published = await platform.post(f"/api/commercial/catalog/versions/{catalog['id']}/publish")
        assert published.status_code == 200, published.text
        assert published.json()["status"] == "published"

        locked_catalog = await platform.patch(f"/api/commercial/catalog/versions/{catalog['id']}", json={"notes": "mutate"})
        locked_price = await platform.patch(f"/api/commercial/catalog/prices/{monthly.json()['id']}", json={"amount_cents": 29900})
        locked_revision = await platform.post(
            f"/api/commercial/catalog/prices/{monthly.json()['id']}/revisions",
            json={
                "price_key": "core-monthly-v3",
                "amount_cents": 29900,
                "billing_interval": "monthly",
                "is_active": True,
                "is_public": True,
                "approved_by_owner": True,
            },
        )
        assert locked_catalog.status_code == 409
        assert locked_price.status_code == 409
        assert locked_revision.status_code == 409
        original = await db.commercial_prices.find_one({"id": monthly.json()["id"]}, {"_id": 0})
        assert original["amount_cents"] == 19900

        eligible = await platform.get(f"/api/commercial/catalog/products/{product['id']}/purchase-eligibility")
        assert eligible.status_code == 200
        assert eligible.json()["purchasable"] is True

    async with await _client_as(ctx["platform_admin"]) as platform:
        second_catalog = await _draft_catalog(platform, uuid.uuid4().hex[:6])
        inactive_product = await platform.post(
            "/api/commercial/catalog/products",
            json={
                "catalog_version_id": second_catalog["id"],
                "product_key": "inactive-core",
                "name": "Inactive Core",
                "product_type": "core",
                "status": "inactive",
            },
        )
        unavailable_with_stripe = await platform.post(
            "/api/commercial/catalog/products",
            json={
                "catalog_version_id": second_catalog["id"],
                "product_key": "future-sms",
                "name": "Future SMS",
                "product_type": "usage_category",
                "status": "unavailable",
                "stripe_sync_enabled": True,
                "publishable": True,
            },
        )
        assert inactive_product.status_code == 201
        assert unavailable_with_stripe.status_code == 409
        inactive_price = await platform.post(
            "/api/commercial/catalog/prices",
            json={
                "catalog_version_id": second_catalog["id"],
                "product_id": inactive_product.json()["id"],
                "price_key": "inactive-monthly",
                "billing_interval": "monthly",
                "amount_cents": 1000,
                "is_active": True,
                "is_public": True,
                "approved_by_owner": True,
            },
        )
        inactive_eligible = await platform.get(f"/api/commercial/catalog/products/{inactive_product.json()['id']}/purchase-eligibility")
        assert inactive_price.status_code == 409
        assert inactive_eligible.json()["purchasable"] is False

    after = {
        "invoices": await db.invoices.count_documents({"tenant_id": ctx["tenant_id"]}),
        "payments": await db.payments.count_documents({"tenant_id": ctx["tenant_id"]}),
        "feature_entitlements": await db.feature_entitlements.count_documents({"tenant_id": ctx["tenant_id"]}),
    }
    assert after == before


@pytest.mark.asyncio
async def test_entitlement_contracts_founder_preservation_and_tenant_isolation(ctx):
    await db.users.update_one({"id": ctx["staff"]["id"], "tenant_id": ctx["tenant_id"]}, {"$set": {"founder_access": True}})
    await db.founder_access.insert_one({
        "id": f"fa-{uuid.uuid4().hex[:8]}",
        "tenant_id": ctx["tenant_id"],
        "user_id": ctx["staff"]["id"],
        "granted_by_user_id": ctx["platform_admin"]["id"],
        "revoked_at": None,
        "created_at": _now(),
        "updated_at": _now(),
    })
    before = {
        "feature_entitlements": await db.feature_entitlements.count_documents({"tenant_id": ctx["tenant_id"]}),
        "founder_access": await db.founder_access.count_documents({"tenant_id": ctx["tenant_id"]}),
    }

    async with await _client_as(ctx["platform_admin"]) as platform:
        catalog = await _draft_catalog(platform, uuid.uuid4().hex[:6])
        product = await _active_core_product(platform, catalog["id"], key="entitled-core")
        rule = await platform.post(
            "/api/commercial/catalog/entitlement-rules",
            json={
                "catalog_version_id": catalog["id"],
                "product_id": product["id"],
                "feature_key": "subscription.core",
                "entitlement_scope": "plan",
                "quota_interval": "monthly",
            },
        )
        assert rule.status_code == 201, rule.text
        assert await db.feature_entitlements.count_documents({"tenant_id": ctx["tenant_id"]}) == before["feature_entitlements"]

        unavailable = await platform.post(
            "/api/commercial/catalog/products",
            json={
                "catalog_version_id": catalog["id"],
                "product_key": "future-smart-pricing",
                "name": "Future Smart Pricing",
                "product_type": "addon",
                "status": "unavailable",
                "owner_checkpoint": "future-smart-pricing",
            },
        )
        unavailable_rule = await platform.post(
            "/api/commercial/catalog/entitlement-rules",
            json={
                "catalog_version_id": catalog["id"],
                "product_id": unavailable.json()["id"],
                "feature_key": "smart_pricing.future",
                "entitlement_scope": "addon",
            },
        )
        assert unavailable.status_code == 201
        assert unavailable_rule.status_code == 409

        user_scoped_founder = await platform.post(
            "/api/commercial/founder-contracts",
            json={
                "tenant_id": ctx["tenant_id"],
                "user_id": ctx["staff"]["id"],
                "founder_slot_number": 1,
                "founder_status": "active",
            },
        )
        founder = await platform.post(
            "/api/commercial/founder-contracts",
            json={"tenant_id": ctx["tenant_id"], "founder_slot_number": 1, "founder_status": "active"},
        )
        duplicate_active = await platform.post(
            "/api/commercial/founder-contracts",
            json={"tenant_id": ctx["tenant_id"], "founder_slot_number": 2, "founder_status": "grace"},
        )
        assert user_scoped_founder.status_code == 400
        assert founder.status_code == 201, founder.text
        assert founder.json()["tenant_id"] == ctx["tenant_id"]
        assert founder.json()["ec12_founder_access_preserved"] is True
        assert duplicate_active.status_code == 409

    staff_doc = await db.users.find_one({"id": ctx["staff"]["id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})
    assert staff_doc["founder_access"] is True
    assert await db.founder_access.count_documents({"tenant_id": ctx["tenant_id"]}) == before["founder_access"]

    async with await _client_as(ctx["owner"]) as owner:
        own = await owner.get("/api/commercial/founder-contracts")
        cross = await owner.get("/api/commercial/founder-contracts", params={"tenant_id": ctx["other_tenant_id"]})
        assert own.status_code == 200
        assert {item["tenant_id"] for item in own.json()["items"]} == {ctx["tenant_id"]}
        assert cross.status_code == 403

    async with await _token_client(ctx["portal_token"]) as portal:
        denied = await portal.get("/api/commercial/catalog/versions")
        assert denied.status_code in {401, 403}


@pytest.mark.asyncio
async def test_platform_fee_reversal_contracts_are_append_only_and_audited(ctx):
    async with await _client_as(ctx["platform_admin"]) as platform:
        original = await platform.post(
            "/api/commercial/platform-fee-transactions",
            json={
                "tenant_id": ctx["tenant_id"],
                "source_transaction_type": "ec4_customer_payment",
                "source_transaction_id": f"pay-{uuid.uuid4().hex[:8]}",
                "basis_amount_cents": 10000,
                "platform_fee_cents": 500,
                "snapshot_rate_basis_points": 500,
                "provider_fee_cents": 59,
            },
        )
        assert original.status_code == 201, original.text
        full_reversal = await platform.post(
            f"/api/commercial/platform-fee-transactions/{original.json()['id']}/reversals",
            json={"refund_basis_amount_cents": 10000},
        )
        partial_reversal = await platform.post(
            f"/api/commercial/platform-fee-transactions/{original.json()['id']}/reversals",
            json={"refund_basis_amount_cents": 2500},
        )
        no_reason_adjustment = await platform.post(
            f"/api/commercial/platform-fee-transactions/{original.json()['id']}/adjustments",
            json={"platform_fee_cents": -25, "adjustment_reason": ""},
        )
        adjustment = await platform.post(
            f"/api/commercial/platform-fee-transactions/{original.json()['id']}/adjustments",
            json={"platform_fee_cents": -25, "basis_amount_cents": 0, "adjustment_reason": "Owner-approved rounding exception"},
        )
        assert full_reversal.status_code == 201, full_reversal.text
        assert full_reversal.json()["status"] == "reversed"
        assert full_reversal.json()["platform_fee_cents"] == 500
        assert partial_reversal.status_code == 201, partial_reversal.text
        assert partial_reversal.json()["status"] == "partially_reversed"
        assert partial_reversal.json()["platform_fee_cents"] == 125
        assert no_reason_adjustment.status_code == 400
        assert adjustment.status_code == 201, adjustment.text
        assert adjustment.json()["status"] == "adjusted"

    original_after = await db.platform_fee_transactions.find_one({"id": original.json()["id"]}, {"_id": 0})
    assert original_after["status"] == "assessed"
    assert original_after["basis_amount_cents"] == 10000
    assert original_after["platform_fee_cents"] == 500
    assert original_after["provider_fee_cents"] == 59
    assert await db.platform_fee_transactions.count_documents({"reversal_of_fee_transaction_id": original.json()["id"]}) == 3
    assert await db.audit_events.count_documents({"module": {"$exists": False}, "entity_type": "platform_fee_transaction"}) >= 3


@pytest.mark.asyncio
async def test_phase13a_indexes_and_static_boundaries():
    catalog_indexes = await db.commercial_catalog_versions.index_information()
    product_indexes = await db.commercial_products.index_information()
    price_indexes = await db.commercial_prices.index_information()
    founder_indexes = await db.founder_tenant_contracts.index_information()
    assert any(spec.get("unique") and spec["key"] == [("version", 1)] for spec in catalog_indexes.values())
    assert any(spec.get("unique") and spec["key"] == [("catalog_version_id", 1), ("product_key", 1)] for spec in product_indexes.values())
    assert any(spec.get("unique") and spec["key"] == [("catalog_version_id", 1), ("price_key", 1)] for spec in price_indexes.values())
    assert any(spec.get("unique") and spec["key"] == [("tenant_id", 1)] for spec in founder_indexes.values())

    backend_root = Path(__file__).resolve().parents[1]
    model_source = (backend_root / "app" / "models" / "commercial_catalog.py").read_text()
    service_source = (backend_root / "app" / "services" / "commercial_catalog.py").read_text()
    assert "amount_cents" in model_source
    assert "amount: " not in model_source
    assert "stripe." not in service_source
    assert "checkout" not in service_source.lower()
    assert "feature_entitlements.insert" not in service_source
    assert "feature_entitlements.update" not in service_source
    assert not (backend_root / "app" / "routers" / "ec19.py").exists()
