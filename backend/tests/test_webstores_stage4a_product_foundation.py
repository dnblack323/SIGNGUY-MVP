"""Webstores Stage 4A product-foundation contracts."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from pymongo.errors import DuplicateKeyError

from app.core.db import db, ensure_indexes
from app.core.portal_security import create_portal_token
from app.deps import get_current_user
from app.services import storage
from app.services import webstores as webstore_svc
from app.services.entitlements import _upsert_entitlement_for_tests
from app.services.portal_identity import create_portal_identity
from server import app


def _override(user: dict):
    async def _get():
        return {**user}

    return _get


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _portal_client(token: str) -> AsyncClient:
    app.dependency_overrides.pop(get_current_user, None)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"})


@pytest.fixture
async def stage4a_ctx():
    await ensure_indexes()
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-webstore-stage4a-{suffix}"
    other_tenant_id = f"t-webstore-stage4a-other-{suffix}"
    staff = {"id": f"staff-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "role": "owner", "is_active": True}
    other_staff = {"id": f"other-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True}
    platform_creator = {
        "id": f"creator-{suffix}",
        "tenant_id": tenant_id,
        "email": f"creator-{suffix}@example.com",
        "role": "owner",
        "platform_role": "PLATFORM_CREATOR",
        "is_active": True,
    }
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": f"shop-{suffix}", "name": f"Shop {suffix}"},
        {"id": other_tenant_id, "slug": f"other-shop-{suffix}", "name": f"Other Shop {suffix}"},
    ])
    await db.users.insert_many([staff, other_staff, platform_creator])
    await _upsert_entitlement_for_tests(tenant_id=tenant_id, feature_key="webstores", enabled=True)
    yield {"suffix": suffix, "tenant_id": tenant_id, "other_tenant_id": other_tenant_id, "staff": staff, "other_staff": other_staff, "platform_creator": platform_creator}
    app.dependency_overrides.pop(get_current_user, None)


async def _create_store(client: AsyncClient, suffix: str, *, store_type: str = "general") -> dict:
    owner_resp = await client.post(
        "/api/webstores/owners",
        json={"name": f"Store Owner {suffix}", "email": f"webstore-owner-{suffix}@example.com"},
    )
    assert owner_resp.status_code == 201, owner_resp.text
    store_resp = await client.post(
        "/api/webstores",
        json={
            "owner_id": owner_resp.json()["id"],
            "name": f"Stage 4A Store {suffix}",
            "slug": f"stage4a-store-{suffix}",
            "store_type": store_type,
        },
    )
    assert store_resp.status_code == 201, store_resp.text
    return {**store_resp.json(), "owner": owner_resp.json()}


async def _seed_setup_file(ctx: dict, webstore_id: str, *, extension: str = "png", content_type: str = "image/png") -> dict:
    file_id = f"file-{uuid.uuid4().hex}"
    storage_key = f"tests/{ctx['tenant_id']}/{file_id}.{extension}"
    storage.put_bytes(storage_key, b"stage4a-image", content_type)
    doc = {
        "id": file_id,
        "tenant_id": ctx["tenant_id"],
        "webstore_id": webstore_id,
        "category": "product_image",
        "file_name": f"product.{extension}",
        "extension": extension,
        "content_type": content_type,
        "detected_content_type": content_type,
        "size_bytes": 13,
        "storage_key": storage_key,
        "uploaded_by_actor_type": "staff",
        "status": "active",
        "version": 1,
        "safe_preview_available": True,
        "inline_preview_allowed": True,
        "private_download_only": False,
        "svg_sanitized": extension != "svg",
    }
    await db.webstore_setup_files.insert_one(doc)
    return doc


async def _activity_actions(ctx: dict, webstore_id: str, product_id: str) -> list[dict]:
    return [
        doc
        async for doc in db.webstore_activity_events.find(
            {"tenant_id": ctx["tenant_id"], "webstore_id": webstore_id, "entity_id": product_id},
            {"_id": 0},
        ).sort("created_at", 1)
    ]


class _CollectionProxy:
    def __init__(self, collection, insert_one):
        self._collection = collection
        self.insert_one = insert_one

    def __getattr__(self, name):
        return getattr(self._collection, name)


class _DbProxy:
    def __init__(self, database, products_collection):
        self._database = database
        self.webstore_products = products_collection

    def __getattr__(self, name):
        return getattr(self._database, name)


@pytest.mark.asyncio
async def test_stage4a_patch_routes_require_revision_and_update_atomically(stage4a_ctx):
    async with await _client_as(stage4a_ctx["staff"]) as client:
        store = await _create_store(client, f"revision-{stage4a_ctx['suffix']}")
        template_resp = await client.post(
            "/api/webstores/product-templates",
            json={
                "template_name": "Revision Template",
                "product_category": "Apparel",
                "product_type": "shirt",
                "webstore_id": store["id"],
                "default_title": "Revision Shirt",
            },
        )
        assert template_resp.status_code == 201, template_resp.text
        template = template_resp.json()
        category_resp = await client.post(f"/api/webstores/{store['id']}/product-categories", json={"name": "Revision Wear"})
        assert category_resp.status_code == 201, category_resp.text
        category = category_resp.json()
        product_resp = await client.post(
            f"/api/webstores/{store['id']}/products",
            json={"name": "Revision Product", "product_type": "shirt", "category_id": category["id"]},
        )
        assert product_resp.status_code == 201, product_resp.text
        product = product_resp.json()

        missing_template = await client.patch(
            f"/api/webstores/product-templates/{template['id']}",
            json={"default_title": "Missing revision template"},
        )
        missing_product = await client.patch(
            f"/api/webstores/{store['id']}/products/{product['id']}",
            json={"name": "Missing revision product"},
        )
        missing_category = await client.patch(
            f"/api/webstores/{store['id']}/product-categories/{category['id']}",
            json={"name": "Missing revision category"},
        )
        assert missing_template.status_code == 422
        assert missing_product.status_code == 422
        assert missing_category.status_code == 422
        assert (await db.webstore_product_templates.find_one({"id": template["id"]}, {"_id": 0}))["default_title"] == "Revision Shirt"
        assert (await db.webstore_products.find_one({"id": product["id"]}, {"_id": 0}))["name"] == "Revision Product"
        assert (await db.webstore_product_categories.find_one({"id": category["id"]}, {"_id": 0}))["name"] == "Revision Wear"

        template_ok = await client.patch(
            f"/api/webstores/product-templates/{template['id']}",
            json={"expected_revision": template["revision"], "webstore_id": store["id"], "default_title": "Revision Shirt Updated"},
        )
        assert template_ok.status_code == 200, template_ok.text
        assert template_ok.json()["revision"] == template["revision"] + 1
        product_ok = await client.patch(
            f"/api/webstores/{store['id']}/products/{product['id']}",
            json={"expected_revision": product["revision"], "name": "Revision Product Updated"},
        )
        assert product_ok.status_code == 200, product_ok.text
        assert product_ok.json()["revision"] == product["revision"] + 1
        category_ok = await client.patch(
            f"/api/webstores/{store['id']}/product-categories/{category['id']}",
            json={"expected_revision": category["revision"], "name": "Revision Wear Updated"},
        )
        assert category_ok.status_code == 200, category_ok.text
        assert category_ok.json()["revision"] == category["revision"] + 1

        stale_template = await client.patch(
            f"/api/webstores/product-templates/{template['id']}",
            json={"expected_revision": template["revision"], "webstore_id": store["id"], "default_title": "Stale template"},
        )
        stale_product = await client.patch(
            f"/api/webstores/{store['id']}/products/{product['id']}",
            json={"expected_revision": product["revision"], "name": "Stale product"},
        )
        stale_category = await client.patch(
            f"/api/webstores/{store['id']}/product-categories/{category['id']}",
            json={"expected_revision": category["revision"], "name": "Stale category"},
        )
        assert stale_template.status_code == 409
        assert "Reload" in stale_template.text
        assert stale_product.status_code == 409
        assert "Reload" in stale_product.text
        assert stale_category.status_code == 409
        assert "Reload" in stale_category.text
        assert (await db.webstore_product_templates.find_one({"id": template["id"]}, {"_id": 0}))["default_title"] == "Revision Shirt Updated"
        assert (await db.webstore_products.find_one({"id": product["id"]}, {"_id": 0}))["name"] == "Revision Product Updated"
        assert (await db.webstore_product_categories.find_one({"id": category["id"]}, {"_id": 0}))["name"] == "Revision Wear Updated"


@pytest.mark.asyncio
async def test_stage4a_duplicate_key_recovery_branch_returns_original_product(stage4a_ctx, monkeypatch):
    async with await _client_as(stage4a_ctx["staff"]) as client:
        store = await _create_store(client, f"race-{stage4a_ctx['suffix']}")
        original_insert = db.webstore_products.insert_one
        branch_exercised = {"value": False}

        async def insert_then_raise(doc, *args, **kwargs):
            branch_exercised["value"] = True
            await original_insert(doc, *args, **kwargs)
            raise DuplicateKeyError("simulated concurrent idempotent product insert")

        monkeypatch.setattr(webstore_svc, "db", _DbProxy(db, _CollectionProxy(db.webstore_products, insert_then_raise)))
        race = await client.post(
            f"/api/webstores/{store['id']}/products",
            json={"name": "Race Product", "product_type": "shirt", "idempotency_key": "race-key"},
        )
        assert race.status_code == 201, race.text
        assert branch_exercised["value"] is True
        product = race.json()
        assert product["name"] == "Race Product"
        assert product["stage4a_idempotency_key"] == "race-key"
        assert await db.webstore_products.count_documents({"tenant_id": stage4a_ctx["tenant_id"], "webstore_id": store["id"], "stage4a_idempotency_key": "race-key"}) == 1

        replay = await client.post(
            f"/api/webstores/{store['id']}/products",
            json={"name": "Race Product", "product_type": "shirt", "idempotency_key": "race-key"},
        )
        assert replay.status_code == 201, replay.text
        assert replay.json()["id"] == product["id"]
        assert replay.json().get("artwork_associations", []) == []
        assert replay.json().get("mockup_associations", []) == []
        assert replay.json().get("customer_images", {}) == {}

        conflict_seed_key = "race-conflict-key"

        async def insert_conflict_then_raise(doc, *args, **kwargs):
            conflicting = dict(doc)
            conflicting["id"] = f"conflicting-{uuid.uuid4().hex}"
            conflicting["stage4a_idempotency_payload_hash"] = "different-payload"
            await original_insert(conflicting, *args, **kwargs)
            raise DuplicateKeyError("simulated conflicting concurrent idempotent product insert")

        monkeypatch.setattr(webstore_svc, "db", _DbProxy(db, _CollectionProxy(db.webstore_products, insert_conflict_then_raise)))
        conflict = await client.post(
            f"/api/webstores/{store['id']}/products",
            json={"name": "Race Conflict", "product_type": "shirt", "idempotency_key": conflict_seed_key},
        )
        assert conflict.status_code == 409
        assert await db.webstore_products.count_documents({"tenant_id": stage4a_ctx["tenant_id"], "webstore_id": store["id"], "stage4a_idempotency_key": conflict_seed_key}) == 1

        monkeypatch.setattr(webstore_svc, "db", db)
        intentional = await client.post(
            f"/api/webstores/{store['id']}/products",
            json={"name": "Intentional Copy", "product_type": "shirt", "idempotency_key": "race-key-2"},
        )
        assert intentional.status_code == 201, intentional.text
        assert intentional.json()["id"] != product["id"]


@pytest.mark.asyncio
async def test_stage4a_template_scopes_copy_independently_and_idempotently(stage4a_ctx):
    async with await _client_as(stage4a_ctx["staff"]) as staff_client:
        store = await _create_store(staff_client, stage4a_ctx["suffix"])
        image = await _seed_setup_file(stage4a_ctx, store["id"])
        template_artwork = await staff_client.post(
            f"/api/webstores/{store['id']}/artwork",
            json={"file_id": image["id"], "purpose": "reusable production art", "notes": "private reusable art"},
        )
        assert template_artwork.status_code == 201, template_artwork.text
        template_mockup = await staff_client.post(
            f"/api/webstores/{store['id']}/mockups",
            json={"mockup_file_id": image["id"], "purpose": "reusable mockup", "alt_text": "Reusable mockup"},
        )
        assert template_mockup.status_code == 201, template_mockup.text

        platform_denied = await staff_client.post(
            "/api/webstores/product-templates",
            json={"scope": "platform", "template_name": "Platform Shirt", "product_category": "Apparel", "product_type": "shirt"},
        )
        assert platform_denied.status_code == 403

        tenant_template_resp = await staff_client.post(
            "/api/webstores/product-templates",
            json={
                "template_name": "Spirit Shirt",
                "product_category": "Apparel",
                "product_type": "shirt",
                "webstore_id": store["id"],
                "default_title": "Spirit Shirt Product",
                "default_short_description": "Short customer copy",
                "default_description": "Full customer copy",
                "suggested_category_name": "Team Wear",
                "production_method": "DTF",
                "supplier_source_info": "private supplier",
                "default_production_notes": "private production note",
                "default_customer_images": {"primary": {"file_id": image["id"], "alt_text": "Spirit shirt front"}},
                "default_artwork_associations": [{"artwork_id": template_artwork.json()["id"], "purpose": "template art"}],
                "default_mockup_associations": [{"mockup_id": template_mockup.json()["id"], "purpose": "template mockup", "alt_text": "Template mockup"}],
            },
        )
        assert tenant_template_resp.status_code == 201, tenant_template_resp.text
        tenant_template = tenant_template_resp.json()

        missing_store_image = await staff_client.post(
            "/api/webstores/product-templates",
            json={
                "template_name": "Unsafe Tenant Template",
                "product_category": "Apparel",
                "product_type": "shirt",
                "default_customer_images": {"primary": {"file_id": image["id"], "alt_text": "Private image"}},
            },
        )
        assert missing_store_image.status_code == 400

    async with await _client_as(stage4a_ctx["platform_creator"]) as creator_client:
        platform_template_resp = await creator_client.post(
            "/api/webstores/product-templates",
            json={
                "scope": "platform",
                "template_name": "Platform Starter",
                "product_category": "General",
                "product_type": "starter",
                "default_title": "Platform Default",
                "default_customer_images": {"primary": {"url": "https://assets.example.test/starter.png", "alt_text": "Starter"}},
            },
        )
        assert platform_template_resp.status_code == 201, platform_template_resp.text
        platform_template = platform_template_resp.json()

    async with await _client_as(stage4a_ctx["staff"]) as staff_client:
        template_list = (await staff_client.get("/api/webstores/product-templates/list")).json()["items"]
        assert {tenant_template["id"], platform_template["id"]}.issubset({tpl["id"] for tpl in template_list})

        first = await staff_client.post(
            f"/api/webstores/{store['id']}/products",
            json={"source_template_id": tenant_template["id"], "idempotency_key": "copy-spirit-shirt"},
        )
        assert first.status_code == 201, first.text
        product = first.json()
        assert product["status"] == "draft"
        assert product["public"] is False
        assert product["source_template_id"] == tenant_template["id"]
        assert product["source_template_revision"] == tenant_template["revision"]
        assert product["images"][0]["file_id"] == image["id"]
        assert product["artwork_associations"][0]["artwork_id"] == template_artwork.json()["id"]
        assert product["mockup_associations"][0]["mockup_id"] == template_mockup.json()["id"]
        assert product["selling_price_cents"] == 0
        assert product["variants"] == []

        replay = await staff_client.post(
            f"/api/webstores/{store['id']}/products",
            json={"source_template_id": tenant_template["id"], "idempotency_key": "copy-spirit-shirt"},
        )
        assert replay.status_code == 201, replay.text
        assert replay.json()["id"] == product["id"]

        conflict = await staff_client.post(
            f"/api/webstores/{store['id']}/products",
            json={"name": "Different action", "product_type": "general", "idempotency_key": "copy-spirit-shirt"},
        )
        assert conflict.status_code == 409

        intentional_copy = await staff_client.post(f"/api/webstores/{store['id']}/products", json={"source_template_id": tenant_template["id"], "idempotency_key": "copy-spirit-shirt-2"})
        assert intentional_copy.status_code == 201, intentional_copy.text
        assert intentional_copy.json()["id"] != product["id"]

        template_update = await staff_client.patch(
            f"/api/webstores/product-templates/{tenant_template['id']}",
            json={
                "expected_revision": tenant_template["revision"],
                "webstore_id": store["id"],
                "default_title": "Updated Template Name",
                "default_customer_images": {},
                "default_artwork_associations": [],
                "default_mockup_associations": [],
            },
        )
        assert template_update.status_code == 200, template_update.text

        products_after = (await staff_client.get(f"/api/webstores/{store['id']}/products")).json()["items"]
        copied_after = next(item for item in products_after if item["id"] == product["id"])
        assert copied_after["name"] == "Spirit Shirt Product"
        assert copied_after["images"][0]["file_id"] == image["id"]
        assert copied_after["artwork_associations"][0]["artwork_id"] == template_artwork.json()["id"]
        assert copied_after["mockup_associations"][0]["mockup_id"] == template_mockup.json()["id"]

        updated_template = template_update.json()
        archive = await staff_client.post(f"/api/webstores/product-templates/{tenant_template['id']}/archive", json={"expected_revision": updated_template["revision"]})
        assert archive.status_code == 200, archive.text
        blocked = await staff_client.post(f"/api/webstores/{store['id']}/products", json={"source_template_id": tenant_template["id"], "idempotency_key": "archived-template-copy"})
        assert blocked.status_code == 409

    async with await _client_as(stage4a_ctx["other_staff"]) as other_client:
        hidden = await other_client.get("/api/webstores/product-templates/list")
        assert tenant_template["id"] not in {tpl["id"] for tpl in hidden.json()["items"]}
        cross_tenant_asset = await other_client.post(
            "/api/webstores/product-templates",
            json={
                "template_name": "Cross Tenant Asset",
                "product_category": "Apparel",
                "product_type": "shirt",
                "webstore_id": store["id"],
                "default_artwork_associations": [{"artwork_id": template_artwork.json()["id"]}],
            },
        )
        assert cross_tenant_asset.status_code in {403, 404}


@pytest.mark.asyncio
async def test_stage4a_product_categories_lifecycle_revision_public_redaction_and_images(stage4a_ctx):
    async with await _client_as(stage4a_ctx["staff"]) as client:
        store = await _create_store(client, f"category-{stage4a_ctx['suffix']}")
        image = await _seed_setup_file(stage4a_ctx, store["id"])
        category_resp = await client.post(f"/api/webstores/{store['id']}/product-categories", json={"name": "Team Wear", "description": "Customer-facing category"})
        assert category_resp.status_code == 201, category_resp.text
        category = category_resp.json()
        duplicate = await client.post(f"/api/webstores/{store['id']}/product-categories", json={"name": " team  wear "})
        assert duplicate.status_code == 409

        product_resp = await client.post(
            f"/api/webstores/{store['id']}/products",
            json={"name": "Draft Hoodie", "product_type": "hoodie", "category_id": category["id"], "customer_images": {"primary": {"file_id": image["id"], "alt_text": "Hoodie front"}}},
        )
        assert product_resp.status_code == 201, product_resp.text
        product = product_resp.json()
        assert product["status"] == "draft"
        assert product["public"] is False
        assert product["category_id"] == category["id"]

        publication_denied = await client.post(
            f"/api/webstores/{store['id']}/products",
            json={"name": "Published Too Soon", "product_type": "hoodie", "status": "active", "public": True, "featured": True},
        )
        assert publication_denied.status_code == 400

        catalog_update = await client.patch(
            f"/api/webstores/{store['id']}/products/{product['id']}",
            json={
                "expected_revision": product["revision"],
                "selling_price_cents": 2500,
                "production_cost_cents": 900,
                "store_owner_share_cents": 300,
                "variants": [{"size": "L", "color": "Black", "sku": "SKU-1-L-BLK", "selling_price_cents": 2600}],
                "sku": "SKU-1",
                "personalization_enabled": True,
                "personalization_fields": [{"key": "player_name", "label": "Player name", "type": "text", "required": True}],
                "launch_packet_include": True,
            },
        )
        assert catalog_update.status_code == 200, catalog_update.text
        catalog_product = catalog_update.json()
        assert catalog_product["selling_price_cents"] == 2500
        assert catalog_product["production_cost_cents"] == 900
        assert catalog_product["store_owner_share_cents"] == 300
        assert catalog_product["variants"][0]["sku"] == "SKU-1-L-BLK"
        assert catalog_product["personalization_fields"][0]["key"] == "player_name"
        assert catalog_product["launch_packet_eligible"] is True

        float_money_denied = await client.patch(
            f"/api/webstores/{store['id']}/products/{product['id']}",
            json={"expected_revision": catalog_product["revision"], "selling_price_cents": 25.5},
        )
        assert float_money_denied.status_code == 422

        missing_alt = await client.patch(
            f"/api/webstores/{store['id']}/products/{product['id']}",
            json={"expected_revision": catalog_product["revision"], "customer_images": {"secondary": {"file_id": image["id"]}}},
        )
        assert missing_alt.status_code == 400

        update = await client.patch(
            f"/api/webstores/{store['id']}/products/{product['id']}",
            json={
                "expected_revision": catalog_product["revision"],
                "name": "Updated Draft Hoodie",
                "short_description": "Customer safe",
                "customer_images": {
                    "primary": {"file_id": image["id"], "alt_text": "Updated hoodie front"},
                    "secondary": {"url": "https://assets.example.test/hoodie-detail.webp", "alt_text": "Hoodie detail"},
                },
            },
        )
        assert update.status_code == 200, update.text
        updated = update.json()
        stale = await client.patch(
            f"/api/webstores/{store['id']}/products/{product['id']}",
            json={"expected_revision": product["revision"], "name": "Stale update"},
        )
        assert stale.status_code == 409

        archive_in_use = await client.post(f"/api/webstores/{store['id']}/product-categories/{category['id']}/archive", json={"expected_revision": category["revision"]})
        assert archive_in_use.status_code == 409
        archive_product = await client.post(f"/api/webstores/{store['id']}/products/{product['id']}/archive", json={"expected_revision": updated["revision"]})
        assert archive_product.status_code == 200, archive_product.text
        stale_restore = await client.post(f"/api/webstores/{store['id']}/products/{product['id']}/restore", json={"expected_revision": updated["revision"]})
        assert stale_restore.status_code == 409
        restore_product = await client.post(f"/api/webstores/{store['id']}/products/{product['id']}/restore", json={"expected_revision": archive_product.json()["revision"]})
        assert restore_product.status_code == 200, restore_product.text
        assert restore_product.json()["status"] == "draft"
        assert restore_product.json()["public"] is False

        await db.webstores.update_one({"id": store["id"], "tenant_id": stage4a_ctx["tenant_id"]}, {"$set": {"status": "live"}})
        await db.webstore_products.insert_one(
            {
                "id": f"legacy-public-{stage4a_ctx['suffix']}",
                "tenant_id": stage4a_ctx["tenant_id"],
                "webstore_id": store["id"],
                "name": "Legacy Public Shirt",
                "description": "Legacy compatible",
                "category": "Legacy",
                "product_type": "shirt",
                "selling_price_cents": 2500,
                "production_cost_cents": 700,
                "store_owner_share_cents": 300,
                "supplier_source_info": "private supplier",
                "production_notes": "private production",
                "customer_images": {"primary": {"file_id": image["id"], "alt_text": "Legacy front", "file_name": image["file_name"], "content_type": image["content_type"]}},
                "status": "active",
                "public": True,
                "featured": True,
                "variants": [{"private": "not-stage4a-public"}],
            }
        )

    public = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    async with public:
        public_resp = await public.get(f"/api/public/webstores/{store['public_slug']}")
        assert public_resp.status_code == 200, public_resp.text
        products = public_resp.json()["products"]
        assert [item["name"] for item in products] == ["Legacy Public Shirt"]
        public_product = products[0]
        assert "production_cost_cents" not in public_product
        assert "store_owner_share_cents" not in public_product
        assert "supplier_source_info" not in public_product
        assert "variants" not in public_product
        assert "file_id" not in public_product["images"][0]
        assert public_product["images"][0]["url"].startswith("/api/public/webstores/")

        image_resp = await public.get(f"/api/public/webstores/{store['public_slug']}/product-images/{public_product['id']}/primary")
        assert image_resp.status_code == 200
        draft_image = await public.get(f"/api/public/webstores/{store['public_slug']}/product-images/{updated['id']}/primary")
        assert draft_image.status_code == 404


@pytest.mark.asyncio
async def test_batch1_catalog_validation_for_skus_variants_bundles_and_readiness(stage4a_ctx):
    async with await _client_as(stage4a_ctx["staff"]) as client:
        store = await _create_store(client, f"batch1-{stage4a_ctx['suffix']}")
        image = await _seed_setup_file(stage4a_ctx, store["id"])
        category = (await client.post(f"/api/webstores/{store['id']}/product-categories", json={"name": "Apparel"})).json()

        base_resp = await client.post(
            f"/api/webstores/{store['id']}/products",
            json={
                "name": "Batch One Shirt",
                "product_type": "shirt",
                "category_id": category["id"],
                "sku": "B1-SHIRT",
                "selling_price_cents": 2500,
                "production_cost_cents": 900,
                "store_owner_share_cents": 300,
                "customer_images": {"primary": {"file_id": image["id"], "alt_text": "Batch shirt"}},
                "variants": [
                    {"size": "M", "color": "Black", "sku": "B1-SHIRT-M-BLK", "selling_price_cents": 2500},
                    {"size": "L", "color": "Black", "sku": "B1-SHIRT-L-BLK", "selling_price_cents": 2600},
                ],
            },
        )
        assert base_resp.status_code == 201, base_resp.text
        base = base_resp.json()
        assert base["catalog_status"] == "ready"

        duplicate_sku = await client.post(
            f"/api/webstores/{store['id']}/products",
            json={"name": "Duplicate SKU", "product_type": "shirt", "sku": "B1-SHIRT"},
        )
        assert duplicate_sku.status_code == 409

        duplicate_combo = await client.patch(
            f"/api/webstores/{store['id']}/products/{base['id']}",
            json={
                "expected_revision": base["revision"],
                "variants": [
                    {"size": "M", "color": "Black", "sku": "UNIQUE-1"},
                    {"size": "M", "color": "Black", "sku": "UNIQUE-2"},
                ],
            },
        )
        assert duplicate_combo.status_code == 409

        share_exceeds_price = await client.patch(
            f"/api/webstores/{store['id']}/products/{base['id']}",
            json={"expected_revision": base["revision"], "store_owner_share_cents": 3000},
        )
        assert share_exceeds_price.status_code == 400

        addon = (await client.post(f"/api/webstores/{store['id']}/products", json={"name": "Sticker Add On", "product_type": "sticker"})).json()
        bundled = await client.patch(
            f"/api/webstores/{store['id']}/products/{base['id']}",
            json={"expected_revision": base["revision"], "bundle_items": [{"product_id": addon["id"], "quantity": 2}]},
        )
        assert bundled.status_code == 200, bundled.text
        assert bundled.json()["bundle_items"][0]["product_id"] == addon["id"]
        assert bundled.json()["bundle_items"][0]["quantity"] == 2

        self_bundle = await client.patch(
            f"/api/webstores/{store['id']}/products/{base['id']}",
            json={"expected_revision": bundled.json()["revision"], "bundle_items": [{"product_id": base["id"], "quantity": 1}]},
        )
        assert self_bundle.status_code == 409

        ready = await client.patch(
            f"/api/webstores/{store['id']}/products/{base['id']}",
            json={"expected_revision": bundled.json()["revision"], "status": "ready", "launch_packet_include": True},
        )
        assert ready.status_code == 200, ready.text
        assert ready.json()["status"] == "ready"
        assert ready.json()["launch_packet_eligible"] is True
        assert ready.json()["launch_packet_include"] is True


@pytest.mark.asyncio
async def test_stage4a_product_image_activity_metadata_and_staff_preview(stage4a_ctx):
    async with await _client_as(stage4a_ctx["staff"]) as client:
        store = await _create_store(client, f"images-{stage4a_ctx['suffix']}")
        primary_one = await _seed_setup_file(stage4a_ctx, store["id"], extension="png", content_type="image/png")
        primary_two = await _seed_setup_file(stage4a_ctx, store["id"], extension="webp", content_type="image/webp")
        secondary_one = await _seed_setup_file(stage4a_ctx, store["id"], extension="jpg", content_type="image/jpeg")
        secondary_two = await _seed_setup_file(stage4a_ctx, store["id"], extension="png", content_type="image/png")
        removed_file = await _seed_setup_file(stage4a_ctx, store["id"], extension="png", content_type="image/png")
        await db.webstore_setup_files.update_one({"id": removed_file["id"]}, {"$set": {"status": "removed"}})
        download_only = await _seed_setup_file(stage4a_ctx, store["id"], extension="eps", content_type="application/postscript")
        other_store = await _create_store(client, f"other-images-{stage4a_ctx['suffix']}")
        other_store_file = await _seed_setup_file(stage4a_ctx, other_store["id"], extension="png", content_type="image/png")
        product_resp = await client.post(f"/api/webstores/{store['id']}/products", json={"name": "Image Product", "product_type": "shirt"})
        assert product_resp.status_code == 201, product_resp.text
        product = product_resp.json()

        setup_list = await client.get(f"/api/webstores/{store['id']}/setup-files")
        assert setup_list.status_code == 200, setup_list.text
        setup_item = next(item for item in setup_list.json()["items"] if item["id"] == primary_one["id"])
        assert setup_item["preview_url"] == f"/api/webstores/{store['id']}/setup-files/{primary_one['id']}/preview"
        assert "storage_key" not in setup_item
        preview = await client.get(setup_item["preview_url"])
        assert preview.status_code == 200
        assert preview.content == b"stage4a-image"
        assert preview.headers["content-type"].startswith("image/png")
        assert (await client.get(f"/api/webstores/{store['id']}/setup-files/{removed_file['id']}/preview")).status_code == 404
        assert (await client.get(f"/api/webstores/{store['id']}/setup-files/{download_only['id']}/preview")).status_code == 400
        assert (await client.get(f"/api/webstores/{store['id']}/setup-files/{other_store_file['id']}/preview")).status_code == 404

        primary_added = await client.patch(
            f"/api/webstores/{store['id']}/products/{product['id']}",
            json={"expected_revision": product["revision"], "customer_images": {"primary": {"file_id": primary_one["id"], "alt_text": "Primary one"}}},
        )
        assert primary_added.status_code == 200, primary_added.text
        product = primary_added.json()
        first_activity = (await _activity_actions(stage4a_ctx, store["id"], product["id"]))[-1]
        assert first_activity["action"] == "webstore.product_image_added"
        assert first_activity["metadata"] == {
            "image_association_id": "primary_image",
            "image_slot": "primary",
            "image_role": "Primary",
            "image_action": "added",
        }

        primary_replaced = await client.patch(
            f"/api/webstores/{store['id']}/products/{product['id']}",
            json={"expected_revision": product["revision"], "customer_images": {"primary": {"file_id": primary_two["id"], "alt_text": "Primary two"}}},
        )
        assert primary_replaced.status_code == 200, primary_replaced.text
        product = primary_replaced.json()
        assert (await _activity_actions(stage4a_ctx, store["id"], product["id"]))[-1]["action"] == "webstore.product_image_replaced"

        primary_removed = await client.patch(
            f"/api/webstores/{store['id']}/products/{product['id']}",
            json={"expected_revision": product["revision"], "customer_images": {}},
        )
        assert primary_removed.status_code == 200, primary_removed.text
        product = primary_removed.json()
        removed_activity = (await _activity_actions(stage4a_ctx, store["id"], product["id"]))[-1]
        assert removed_activity["action"] == "webstore.product_image_removed"
        assert removed_activity["metadata"]["image_role"] == "Primary"

        both_added = await client.patch(
            f"/api/webstores/{store['id']}/products/{product['id']}",
            json={
                "expected_revision": product["revision"],
                "customer_images": {
                    "primary": {"file_id": primary_one["id"], "alt_text": "Primary one"},
                    "secondary": {"file_id": secondary_one["id"], "alt_text": "Secondary one"},
                },
            },
        )
        assert both_added.status_code == 200, both_added.text
        product = both_added.json()
        recent = (await _activity_actions(stage4a_ctx, store["id"], product["id"]))[-3:]
        assert recent[0]["action"] == "webstore.product_draft_updated"
        assert {event["metadata"].get("image_role") for event in recent[1:]} == {"Primary", "Secondary"}

        secondary_replaced = await client.patch(
            f"/api/webstores/{store['id']}/products/{product['id']}",
            json={
                "expected_revision": product["revision"],
                "customer_images": {
                    "primary": {"file_id": primary_one["id"], "alt_text": "Primary one"},
                    "secondary": {"file_id": secondary_two["id"], "alt_text": "Secondary two"},
                },
            },
        )
        assert secondary_replaced.status_code == 200, secondary_replaced.text
        product = secondary_replaced.json()
        assert (await _activity_actions(stage4a_ctx, store["id"], product["id"]))[-1]["metadata"]["image_role"] == "Secondary"

        secondary_removed = await client.patch(
            f"/api/webstores/{store['id']}/products/{product['id']}",
            json={
                "expected_revision": product["revision"],
                "customer_images": {"primary": {"file_id": primary_one["id"], "alt_text": "Primary one"}},
            },
        )
        assert secondary_removed.status_code == 200, secondary_removed.text
        product = secondary_removed.json()
        assert product["customer_images"]["primary"]["file_id"] == primary_one["id"]
        assert "secondary" not in product.get("customer_images", {})
        staff_detail = await client.get(f"/api/webstores/{store['id']}")
        staff_product = next(item for item in staff_detail.json()["products"] if item["id"] == product["id"])
        staff_image = staff_product["images"][0]
        assert staff_image["preview_url"] == f"/api/webstores/{store['id']}/setup-files/{primary_one['id']}/preview"
        assert staff_image["file_id"] == primary_one["id"]

        activity_docs = await _activity_actions(stage4a_ctx, store["id"], product["id"])
        serialized_activity = str(activity_docs)
        for private_value in (primary_one["id"], primary_two["id"], secondary_one["id"], secondary_two["id"], primary_one["storage_key"]):
            assert private_value not in serialized_activity
        assert all("image_association_id" in doc.get("metadata", {}) for doc in activity_docs if doc["action"].startswith("webstore.product_image_"))

        await db.webstores.update_one({"id": store["id"], "tenant_id": stage4a_ctx["tenant_id"]}, {"$set": {"status": "live"}})
        await db.webstore_products.update_one(
            {"id": product["id"], "tenant_id": stage4a_ctx["tenant_id"]},
            {"$set": {"status": "active", "public": True, "selling_price_cents": 2500}},
        )

    public = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    async with public:
        public_resp = await public.get(f"/api/public/webstores/{store['public_slug']}")
        assert public_resp.status_code == 200, public_resp.text
        public_product = next(item for item in public_resp.json()["products"] if item["id"] == product["id"])
        assert "file_id" not in public_product["images"][0]
        assert "preview_url" not in public_product["images"][0]
        assert "activity" not in public_product

    async with await _client_as(stage4a_ctx["staff"]) as client:
        owner_identity = await create_portal_identity(
            tenant_id=stage4a_ctx["tenant_id"],
            portal_type="webstore_owner",
            webstore_owner_id=store["owner"]["id"],
            email=f"image-owner-{stage4a_ctx['suffix']}@example.com",
            full_name="Image Owner",
        )
        manager_identity = await create_portal_identity(
            tenant_id=stage4a_ctx["tenant_id"],
            portal_type="webstore_manager",
            webstore_owner_id=store["owner"]["id"],
            webstore_id=store["id"],
            email=f"image-manager-{stage4a_ctx['suffix']}@example.com",
            full_name="Image Manager",
        )
        for identity, role in ((owner_identity, "owner"), (manager_identity, "manager")):
            await db.webstore_access_assignments.insert_one(
                {
                    "id": f"image-assign-{identity['id']}",
                    "tenant_id": stage4a_ctx["tenant_id"],
                    "webstore_id": store["id"],
                    "portal_identity_id": identity["id"],
                    "owner_id": store["owner"]["id"],
                    "email": identity["email"],
                    "role": role,
                    "status": "active",
                }
            )

    for identity in (owner_identity, manager_identity):
        token = create_portal_token(portal_identity_id=identity["id"], tenant_id=stage4a_ctx["tenant_id"], portal_type=identity["portal_type"])
        async with await _portal_client(token) as portal:
            detail = await portal.get(f"/api/portal/webstores/{store['id']}")
            assert detail.status_code == 200, detail.text
            portal_product = next(item for item in detail.json()["products"] if item["id"] == product["id"])
            assert "file_id" not in portal_product["images"][0]
            assert "preview_url" not in portal_product["images"][0]
            assert "activity" not in portal_product


@pytest.mark.asyncio
async def test_stage4a_portal_owner_manager_read_only_and_redacted(stage4a_ctx):
    async with await _client_as(stage4a_ctx["staff"]) as client:
        store = await _create_store(client, f"portal-{stage4a_ctx['suffix']}")
        product_resp = await client.post(
            f"/api/webstores/{store['id']}/products",
            json={"name": "Portal Visible Draft", "product_type": "shirt", "supplier_source_info": "private supplier", "production_notes": "private notes"},
        )
        assert product_resp.status_code == 201, product_resp.text
        product = product_resp.json()
        owner_identity = await create_portal_identity(
            tenant_id=stage4a_ctx["tenant_id"],
            portal_type="webstore_owner",
            webstore_owner_id=store["owner"]["id"],
            email=f"owner-portal-{stage4a_ctx['suffix']}@example.com",
            full_name="Owner Portal",
        )
        manager_identity = await create_portal_identity(
            tenant_id=stage4a_ctx["tenant_id"],
            portal_type="webstore_manager",
            webstore_owner_id=store["owner"]["id"],
            webstore_id=store["id"],
            email=f"manager-portal-{stage4a_ctx['suffix']}@example.com",
            full_name="Manager Portal",
        )
        revoked_identity = await create_portal_identity(
            tenant_id=stage4a_ctx["tenant_id"],
            portal_type="webstore_manager",
            webstore_owner_id=store["owner"]["id"],
            webstore_id=store["id"],
            email=f"revoked-portal-{stage4a_ctx['suffix']}@example.com",
            full_name="Revoked Manager",
        )
        for identity, role, status in (
            (owner_identity, "owner", "active"),
            (manager_identity, "manager", "active"),
            (revoked_identity, "manager", "revoked"),
        ):
            await db.webstore_access_assignments.insert_one(
                {
                    "id": f"assign-{identity['id']}",
                    "tenant_id": stage4a_ctx["tenant_id"],
                    "webstore_id": store["id"],
                    "portal_identity_id": identity["id"],
                    "owner_id": store["owner"]["id"],
                    "email": identity["email"],
                    "role": role,
                    "status": status,
                }
            )

    owner_token = create_portal_token(portal_identity_id=owner_identity["id"], tenant_id=stage4a_ctx["tenant_id"], portal_type="webstore_owner")
    manager_token = create_portal_token(portal_identity_id=manager_identity["id"], tenant_id=stage4a_ctx["tenant_id"], portal_type="webstore_manager")
    revoked_token = create_portal_token(portal_identity_id=revoked_identity["id"], tenant_id=stage4a_ctx["tenant_id"], portal_type="webstore_manager")
    for token in (owner_token, manager_token):
        async with await _portal_client(token) as portal:
            detail = await portal.get(f"/api/portal/webstores/{store['id']}")
            assert detail.status_code == 200, detail.text
            portal_product = next(item for item in detail.json()["products"] if item["id"] == product["id"])
            assert portal_product["name"] == "Portal Visible Draft"
            assert "production_cost_cents" not in portal_product
            assert "supplier_source_info" not in portal_product
            assert "production_notes" not in portal_product
            write_attempt = await portal.patch(f"/api/webstores/{store['id']}/products/{product['id']}", json={"name": "Portal Edit"})
            assert write_attempt.status_code in {401, 403}

    async with await _portal_client(revoked_token) as revoked:
        denied = await revoked.get(f"/api/portal/webstores/{store['id']}")
        assert denied.status_code == 403


@pytest.mark.asyncio
async def test_stage4a_artwork_mockup_and_cross_scope_denials(stage4a_ctx):
    async with await _client_as(stage4a_ctx["staff"]) as client:
        store = await _create_store(client, f"assets-{stage4a_ctx['suffix']}")
        other_store = await _create_store(client, f"other-assets-{stage4a_ctx['suffix']}")
        file_doc = await _seed_setup_file(stage4a_ctx, store["id"], extension="webp", content_type="image/webp")
        other_file = await _seed_setup_file(stage4a_ctx, other_store["id"], extension="png", content_type="image/png")
        unsupported_file = await _seed_setup_file(stage4a_ctx, store["id"], extension="eps", content_type="application/postscript")
        product = (await client.post(f"/api/webstores/{store['id']}/products", json={"name": "Asset Product", "product_type": "shirt"})).json()

        unsupported_image = await client.patch(
            f"/api/webstores/{store['id']}/products/{product['id']}",
            json={"expected_revision": product["revision"], "customer_images": {"primary": {"file_id": unsupported_file["id"], "alt_text": "Unsupported"}}},
        )
        assert unsupported_image.status_code == 400
        cross_store_image = await client.patch(
            f"/api/webstores/{store['id']}/products/{product['id']}",
            json={"expected_revision": product["revision"], "customer_images": {"primary": {"file_id": other_file["id"], "alt_text": "Wrong store"}}},
        )
        assert cross_store_image.status_code == 404

        artwork = await client.post(
            f"/api/webstores/{store['id']}/artwork",
            json={"product_id": product["id"], "file_id": file_doc["id"], "purpose": "production source", "notes": "private art"},
        )
        assert artwork.status_code == 201, artwork.text
        mockup = await client.post(
            f"/api/webstores/{store['id']}/mockups",
            json={"product_id": product["id"], "mockup_file_id": file_doc["id"], "purpose": "customer preview", "alt_text": "Preview mockup", "staff_note": "private mockup note"},
        )
        assert mockup.status_code == 201, mockup.text
        associated = await client.patch(
            f"/api/webstores/{store['id']}/products/{product['id']}",
            json={
                "expected_revision": product["revision"],
                "artwork_associations": [{"artwork_id": artwork.json()["id"], "purpose": "print source"}],
                "mockup_associations": [{"mockup_id": mockup.json()["id"], "purpose": "preview", "alt_text": "Product mockup"}],
            },
        )
        assert associated.status_code == 200, associated.text
        assert associated.json()["artwork_associations"][0]["artwork_id"] == artwork.json()["id"]
        assert associated.json()["mockup_associations"][0]["mockup_id"] == mockup.json()["id"]
        removed = await client.patch(
            f"/api/webstores/{store['id']}/products/{product['id']}",
            json={"expected_revision": associated.json()["revision"], "artwork_associations": [], "mockup_associations": []},
        )
        assert removed.status_code == 200, removed.text
        actions = {
            doc["action"]
            async for doc in db.webstore_activity_events.find(
                {"tenant_id": stage4a_ctx["tenant_id"], "webstore_id": store["id"], "entity_id": product["id"]},
                {"_id": 0, "action": 1, "metadata": 1},
            )
        }
        assert "webstore.product_artwork_associated" in actions
        assert "webstore.product_artwork_removed" in actions
        assert "webstore.product_mockup_associated" in actions
        assert "webstore.product_mockup_removed" in actions

    async with await _client_as(stage4a_ctx["other_staff"]) as other_client:
        guessed = await other_client.patch(f"/api/webstores/{store['id']}/products/{product['id']}", json={"expected_revision": product["revision"], "name": "Cross tenant"})
        assert guessed.status_code in {403, 404}
