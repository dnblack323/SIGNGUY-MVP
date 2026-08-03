"""Webstores Stage 3 branding workflow contracts."""
from __future__ import annotations

import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db, ensure_indexes
from app.core.portal_security import create_portal_token
from app.deps import get_current_user
from app.services import webstore_branding as branding_svc
from app.services.entitlements import _upsert_entitlement_for_tests
from server import app


def _override(user: dict):
    async def _get():
        return {**user}

    return _get


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def branding_ctx():
    await ensure_indexes()
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-webstore-stage3-{suffix}"
    other_tenant_id = f"t-webstore-stage3-other-{suffix}"
    staff = {"id": f"staff-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": f"shop-{suffix}", "name": f"Shop {suffix}"},
        {"id": other_tenant_id, "slug": f"other-shop-{suffix}", "name": f"Other Shop {suffix}"},
    ])
    await db.users.insert_one(staff)
    await _upsert_entitlement_for_tests(tenant_id=tenant_id, feature_key="webstores", enabled=True)
    yield {"suffix": suffix, "tenant_id": tenant_id, "other_tenant_id": other_tenant_id, "staff": staff}
    app.dependency_overrides.pop(get_current_user, None)


async def _seed_store(ctx: dict, *, store_type: str = "general", setup_state: str = "setup_complete", status: str = "draft") -> dict:
    suffix = uuid.uuid4().hex[:8]
    owner_id = f"owner-{suffix}"
    store_id = f"ws-{suffix}"
    public_slug = f"stage3-{suffix}"
    await db.webstore_owners.insert_one(
        {
            "id": owner_id,
            "tenant_id": ctx["tenant_id"],
            "name": "Stage Owner",
            "email": f"stage-owner-{suffix}@example.com",
            "status": "active",
        }
    )
    store = {
        "id": store_id,
        "tenant_id": ctx["tenant_id"],
        "owner_id": owner_id,
        "name": f"Stage 3 {store_type} Store",
        "slug": f"stage3-{suffix}",
        "public_slug": public_slug,
        "public_url": f"/p/webstores/{public_slug}",
        "store_type": store_type,
        "status": status,
        "setup_state": setup_state,
        "checkout_enabled": False,
        "stripe_payment_ready": False,
        "launch_packet_id": f"launch-packet-{suffix}",
        "owner_approved_at": "2026-01-01T00:00:00+00:00",
        "terms_fee_acknowledged": True,
    }
    await db.webstores.insert_one(store)
    await db.webstore_products.insert_one(
        {
            "id": f"product-{suffix}",
            "tenant_id": ctx["tenant_id"],
            "webstore_id": store_id,
            "name": "Preview Shirt",
            "description": "Public product",
            "category": "apparel",
            "product_type": "shirt",
            "selling_price_cents": 2500,
            "status": "active",
            "public": True,
            "featured": True,
            "approval_status": "approved",
            "approval_revision": 1,
            "revision": 1,
        }
    )
    return store


def _type_content(store_type: str) -> dict:
    return {
        "b2b": {"business_welcome": "Welcome purchasing team", "ordering_instructions": "Order through your account."},
        "fundraiser": {"campaign_message": "Support the booster club.", "organization_name": "Boosters"},
        "event": {"event_message": "Pick up your shirts at the event.", "event_display_name": "Summer Classic"},
        "promotional": {"campaign_message": "Limited seasonal promo.", "offer_wording": "Buy before Friday."},
        "employee": {"employee_ordering_instructions": "Use your employee ID at pickup.", "company_welcome": "Team gear"},
        "general": {"general_welcome": "Welcome shoppers.", "about_store": "Open store for branded items."},
    }[store_type]


def _valid_branding(store: dict, *, display_name: str | None = None) -> dict:
    return {
        "brand_basics": {
            "display_name": display_name or f"{store['name']} Display",
            "tagline": "Built for the community",
            "primary_logo": {"url": "https://assets.example.test/logo.png", "alt_text": "Store logo"},
            "alternate_logo": {"url": "https://assets.example.test/logo-dark.webp", "alt_text": "Store logo for dark backgrounds"},
            "favicon": {"file_id": "favicon-upload", "file_name": "favicon.svg", "alt_text": "Store icon"},
            "social_image": {"url": "https://assets.example.test/social.jpg", "alt_text": "Social sharing preview"},
        },
        "colors_fonts": {
            "primary_color": "#0f172a",
            "secondary_color": "#1e293b",
            "accent_color": "#2563eb",
            "page_background_color": "#ffffff",
            "main_text_color": "#111827",
            "button_background_color": "#2563eb",
            "button_text_color": "#ffffff",
            "heading_font": "serif",
            "body_font": "system",
            "button_corner_style": "rounded",
        },
        "header": {
            "show_header": True,
            "display_mode": "both",
            "logo_size": "large",
            "background_color": "#ffffff",
            "announcement_enabled": True,
            "announcement_text": "Order before Friday",
            "announcement_background_color": "#fef3c7",
            "announcement_text_color": "#92400e",
            "announcement_link_destination": "catalog",
        },
        "hero": {
            "show_hero": True,
            "image": {"url": "https://assets.example.test/hero.webp", "alt_text": "Hero artwork"},
            "image_focal_position": "right",
            "overlay_color": "#000000",
            "headline": "Shop the official store",
            "supporting_text": "Approved designs and pickup details.",
            "primary_button_enabled": True,
            "primary_button_label": "Shop products",
            "primary_button_destination": "catalog",
        },
        "store_information": {
            "show_section": True,
            "welcome_heading": "Welcome",
            "welcome_text": "Thanks for visiting.",
            "supporting_image": {"url": "https://assets.example.test/info.png", "alt_text": "Pickup table"},
            "store_instructions": "Pickup details are shown here.",
            "contact_display": "store",
        },
        "store_type_content": _type_content(store["store_type"]),
        "catalog_introduction": {"show_catalog_area": True, "heading": "Products", "introduction": "Browse the approved products.", "background_color": "#ffffff"},
        "footer": {
            "show_footer": True,
            "background_color": "#0f172a",
            "text_color": "#ffffff",
            "display_mode": "both",
            "message": "Questions? Contact the shop.",
            "show_contact": True,
            "show_social_links": True,
            "show_policy_links": True,
            "show_powered_by": True,
        },
    }


async def _portal_identity(ctx: dict, store: dict, *, role: str, status: str = "active") -> tuple[dict, str]:
    suffix = uuid.uuid4().hex[:8]
    identity = {
        "id": f"portal-{role}-{suffix}",
        "tenant_id": ctx["tenant_id"],
        "portal_type": f"webstore_{role}" if role == "owner" else "webstore_manager",
        "webstore_owner_id": store["owner_id"],
        "webstore_id": store["id"] if role == "manager" else None,
        "email": f"{role}-{suffix}@example.com",
        "full_name": f"{role.title()} User",
        "permissions": [f"portal:webstore_{role}_admin"] if role == "owner" else ["portal:webstore_manager_ops"],
        "permissions_preset": "webstore_owner_admin" if role == "owner" else "webstore_manager_ops",
        "status": "active",
        "magic_link_only": True,
    }
    await db.portal_identities.insert_one(identity)
    await db.webstore_access_assignments.insert_one(
        {
            "id": f"assignment-{role}-{suffix}",
            "tenant_id": ctx["tenant_id"],
            "webstore_id": store["id"],
            "owner_id": store["owner_id"],
            "role": role,
            "email": identity["email"],
            "portal_identity_id": identity["id"],
            "status": status,
            "is_primary_owner": role == "owner",
        }
    )
    token = create_portal_token(
        portal_identity_id=identity["id"],
        tenant_id=ctx["tenant_id"],
        portal_type=identity["portal_type"],
    )
    return identity, token


async def _portal_identity_without_assignment(ctx: dict, *, role: str = "manager") -> tuple[dict, str]:
    suffix = uuid.uuid4().hex[:8]
    identity = {
        "id": f"portal-unassigned-{role}-{suffix}",
        "tenant_id": ctx["tenant_id"],
        "portal_type": "webstore_owner" if role == "owner" else "webstore_manager",
        "webstore_owner_id": f"unassigned-owner-{suffix}",
        "webstore_id": None,
        "email": f"unassigned-{role}-{suffix}@example.com",
        "full_name": "Unassigned Portal User",
        "permissions": ["portal:webstore_owner_admin"] if role == "owner" else ["portal:webstore_manager_ops"],
        "permissions_preset": "webstore_owner_admin" if role == "owner" else "webstore_manager_ops",
        "status": "active",
        "magic_link_only": True,
    }
    await db.portal_identities.insert_one(identity)
    token = create_portal_token(
        portal_identity_id=identity["id"],
        tenant_id=ctx["tenant_id"],
        portal_type=identity["portal_type"],
    )
    return identity, token


@pytest.mark.asyncio
async def test_staff_saves_all_branding_categories_and_publishes_owner_approved_version(branding_ctx):
    store = await _seed_store(branding_ctx, store_type="fundraiser", status="live")
    branding = _valid_branding(store)
    async with await _client_as(branding_ctx["staff"]) as client:
        save = await client.patch(f"/api/webstores/{store['id']}/branding/draft", json={"content": branding})
        assert save.status_code == 200, save.text
        saved = save.json()
        assert saved["branding"]["draft"]["brand_basics"]["display_name"] == branding["brand_basics"]["display_name"]
        assert saved["branding"]["draft"]["brand_basics"]["alternate_logo"]["url"].endswith("logo-dark.webp")
        assert saved["branding"]["draft"]["colors_fonts"]["heading_font"] == "serif"
        assert saved["branding"]["draft"]["header"]["announcement_link_destination"] == "catalog"
        assert saved["branding"]["draft"]["hero"]["image_focal_position"] == "right"
        assert saved["branding"]["draft"]["store_information"]["supporting_image"]["url"].endswith("info.png")
        assert saved["branding"]["draft"]["store_type_content"]["campaign_message"] == "Support the booster club."
        assert saved["branding"]["draft"]["catalog_introduction"]["heading"] == "Products"
        assert saved["branding"]["draft"]["footer"]["show_policy_links"] is True
        assert saved["permissions"]["can_control_whole_sections"] is True

        review = await client.post(f"/api/webstores/{store['id']}/branding/request-review", json={"note": "Ready"})
        assert review.status_code == 200, review.text
        assert review.json()["branding"]["status"] == "waiting_owner_approval"

    _, owner_token = await _portal_identity(branding_ctx, store, role="owner")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {owner_token}"}) as portal:
        approve = await portal.post(f"/api/portal/webstores/{store['id']}/branding/approve", json={"note": "Approved"})
        assert approve.status_code == 200, approve.text
        assert approve.json()["branding"]["status"] == "owner_approved"

    async with await _client_as(branding_ctx["staff"]) as client:
        publish = await client.post(f"/api/webstores/{store['id']}/branding/publish")
        assert publish.status_code == 200, publish.text
        assert publish.json()["branding"]["status"] == "published"
        assert len(publish.json()["history"]) == 1

    public = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    async with public:
        storefront = await public.get(f"/api/public/webstores/{store['public_slug']}")
        assert storefront.status_code == 200, storefront.text
        body = storefront.json()
        assert body["webstore"]["branding"]["brand_basics"]["display_name"] == branding["brand_basics"]["display_name"]
        assert body["webstore"]["branding"]["hero"]["image"]["url"] == "https://assets.example.test/hero.webp"
        assert "submitted_snapshot" not in body["webstore"]["branding"]
        assert "submitted_hash" not in body["webstore"]["branding"]
        assert "feedback_note" not in body["webstore"]["branding"]
        assert "activity" not in body["webstore"]["branding"]
        assert "owner_decision" not in body["webstore"]["branding"]

    async with await _client_as(branding_ctx["staff"]) as client:
        branding_state = await client.get(f"/api/webstores/{store['id']}/branding")
        activity = branding_state.json()["activity"]
        actions = {row["action"] for row in activity}
        assert {
            "webstore.branding_draft_saved",
            "webstore.branding_review_requested",
            "webstore.branding_owner_approved",
            "webstore.branding_published",
        }.issubset(actions)
        assert all(row.get("actor_email") and row.get("created_at") for row in activity)


@pytest.mark.asyncio
async def test_owner_manager_assignment_scope_and_role_rules_are_enforced(branding_ctx):
    store = await _seed_store(branding_ctx, store_type="employee")
    other_store = await _seed_store(branding_ctx, store_type="general")
    _, manager_token = await _portal_identity(branding_ctx, store, role="manager")
    _, owner_token = await _portal_identity(branding_ctx, store, role="owner")
    _, unassigned_token = await _portal_identity_without_assignment(branding_ctx, role="manager")
    revoked_store = await _seed_store(branding_ctx, store_type="general")
    _, revoked_token = await _portal_identity(branding_ctx, revoked_store, role="manager", status="revoked")

    for token in (manager_token, owner_token):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"}) as portal:
            for section, field in (("header", "show_header"), ("hero", "show_hero"), ("catalog_introduction", "show_catalog_area")):
                hidden = _valid_branding(store)
                hidden[section][field] = False
                denied = await portal.patch(f"/api/portal/webstores/{store['id']}/branding/draft", json={"content": hidden})
                assert denied.status_code == 403, f"{section}.{field} was not staff-only"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {manager_token}"}) as portal:
        save = await portal.patch(f"/api/portal/webstores/{store['id']}/branding/draft", json={"content": _valid_branding(store)})
        assert save.status_code == 200, save.text
        review = await portal.post(f"/api/portal/webstores/{store['id']}/branding/request-review", json={})
        assert review.status_code == 200, review.text
        approval_denied = await portal.post(f"/api/portal/webstores/{store['id']}/branding/approve", json={})
        assert approval_denied.status_code == 403
        cross_store_denied = await portal.get(f"/api/portal/webstores/{other_store['id']}/branding")
        assert cross_store_denied.status_code == 403

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {owner_token}"}) as portal:
        owner_review_denied = await portal.post(f"/api/portal/webstores/{store['id']}/branding/request-review", json={})
        assert owner_review_denied.status_code == 403
        empty_change_denied = await portal.post(f"/api/portal/webstores/{store['id']}/branding/request-changes", json={"note": ""})
        assert empty_change_denied.status_code == 400
        change = await portal.post(f"/api/portal/webstores/{store['id']}/branding/request-changes", json={"note": "Use the blue logo"})
        assert change.status_code == 200, change.text
        assert change.json()["branding"]["feedback_note"] == "Use the blue logo"
        assert any(
            row["action"] == "webstore.branding_changes_requested" and row.get("metadata", {}).get("note") == "Use the blue logo"
            for row in change.json()["activity"]
        )
        owner_cross_store_denied = await portal.get(f"/api/portal/webstores/{other_store['id']}/branding")
        assert owner_cross_store_denied.status_code == 403

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {unassigned_token}"}) as portal:
        unassigned_denied = await portal.get(f"/api/portal/webstores/{store['id']}/branding")
        assert unassigned_denied.status_code == 403

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {revoked_token}"}) as portal:
        denied = await portal.get(f"/api/portal/webstores/{revoked_store['id']}/branding")
        assert denied.status_code == 403


@pytest.mark.parametrize("store_type", ["b2b", "fundraiser", "event", "promotional", "employee", "general"])
@pytest.mark.asyncio
async def test_all_six_webstore_types_validate_and_preserve_type_specific_branding(branding_ctx, store_type):
    store = await _seed_store(branding_ctx, store_type=store_type)
    async with await _client_as(branding_ctx["staff"]) as client:
        save = await client.patch(f"/api/webstores/{store['id']}/branding/draft", json={"content": _valid_branding(store)})
        assert save.status_code == 200, save.text
        draft = save.json()["branding"]["draft"]
        assert draft["store_type_content"] == {**draft["store_type_content"], **_type_content(store_type)}
        review = await client.post(f"/api/webstores/{store['id']}/branding/request-review", json={})
        assert review.status_code == 200, review.text


@pytest.mark.asyncio
async def test_validation_blocks_bad_images_missing_alt_and_publish_before_readiness(branding_ctx):
    store = await _seed_store(branding_ctx, store_type="general", setup_state="not_started")
    bad = _valid_branding(store)
    bad["brand_basics"]["primary_logo"] = {"url": "https://assets.example.test/logo.ai", "alt_text": "Logo"}
    async with await _client_as(branding_ctx["staff"]) as client:
        rejected = await client.patch(f"/api/webstores/{store['id']}/branding/draft", json={"content": bad})
        assert rejected.status_code == 400

        missing_alt = _valid_branding(store)
        missing_alt["hero"]["image"] = {"url": "https://assets.example.test/hero.png"}
        saved = await client.patch(f"/api/webstores/{store['id']}/branding/draft", json={"content": missing_alt})
        assert saved.status_code == 200, saved.text
        assert "alternate text" in saved.json()["branding"]["validation"]["errors"][0]
        review_denied = await client.post(f"/api/webstores/{store['id']}/branding/request-review", json={})
        assert review_denied.status_code == 409

        readable_warning = _valid_branding(store)
        readable_warning["colors_fonts"]["button_background_color"] = "#ffffff"
        readable_warning["colors_fonts"]["button_text_color"] = "#ffffff"
        saved_warning = await client.patch(f"/api/webstores/{store['id']}/branding/draft", json={"content": readable_warning})
        assert saved_warning.status_code == 200, saved_warning.text
        assert saved_warning.json()["branding"]["validation"]["warnings"]
        review = await client.post(f"/api/webstores/{store['id']}/branding/request-review", json={})
        assert review.status_code == 200, review.text

    _, owner_token = await _portal_identity(branding_ctx, store, role="owner")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {owner_token}"}) as portal:
        approved = await portal.post(f"/api/portal/webstores/{store['id']}/branding/approve", json={})
        assert approved.status_code == 200, approved.text

    async with await _client_as(branding_ctx["staff"]) as client:
        publish_denied = await client.post(f"/api/webstores/{store['id']}/branding/publish")
        assert publish_denied.status_code == 409
        assert "Complete Store Setup" in publish_denied.text


@pytest.mark.parametrize("ext", ["jpg", "jpeg", "png", "webp"])
@pytest.mark.asyncio
async def test_supported_image_formats_save_for_public_branding_slots(branding_ctx, ext):
    store = await _seed_store(branding_ctx, store_type="general")
    branding = _valid_branding(store)
    branding["hero"]["image"] = {"url": f"https://assets.example.test/hero.{ext}", "alt_text": "Hero artwork"}
    branding["store_information"]["supporting_image"] = {"url": f"https://assets.example.test/info.{ext}", "alt_text": "Store information"}
    branding["brand_basics"]["social_image"] = {"url": f"https://assets.example.test/social.{ext}", "alt_text": "Social preview"}
    async with await _client_as(branding_ctx["staff"]) as client:
        saved = await client.patch(f"/api/webstores/{store['id']}/branding/draft", json={"content": branding})
        assert saved.status_code == 200, saved.text
        draft = saved.json()["branding"]["draft"]
        assert draft["hero"]["image"]["url"].endswith(f".{ext}")
        assert draft["store_information"]["supporting_image"]["url"].endswith(f".{ext}")
        assert draft["brand_basics"]["social_image"]["url"].endswith(f".{ext}")


@pytest.mark.asyncio
async def test_svg_is_logo_only_and_unsupported_artwork_is_rejected(branding_ctx):
    store = await _seed_store(branding_ctx, store_type="general")
    async with await _client_as(branding_ctx["staff"]) as client:
        logo_svg = _valid_branding(store)
        logo_svg["brand_basics"]["primary_logo"] = {"file_id": "logo-file", "file_name": "logo.svg", "alt_text": "Logo"}
        accepted = await client.patch(f"/api/webstores/{store['id']}/branding/draft", json={"content": logo_svg})
        assert accepted.status_code == 200, accepted.text

        unsafe_logo_svg_url = _valid_branding(store)
        unsafe_logo_svg_url["brand_basics"]["primary_logo"] = {"url": "https://assets.example.test/logo.svg", "alt_text": "Logo"}
        rejected_svg_url = await client.patch(f"/api/webstores/{store['id']}/branding/draft", json={"content": unsafe_logo_svg_url})
        assert rejected_svg_url.status_code == 400
        assert "safe-upload" in rejected_svg_url.text

        hero_svg = _valid_branding(store)
        hero_svg["hero"]["image"] = {"url": "https://assets.example.test/hero.svg", "alt_text": "Hero"}
        rejected_svg = await client.patch(f"/api/webstores/{store['id']}/branding/draft", json={"content": hero_svg})
        assert rejected_svg.status_code == 400
        assert "SVG for logos only" in rejected_svg.text

        eps_art = _valid_branding(store)
        eps_art["brand_basics"]["primary_logo"] = {"url": "https://assets.example.test/logo.eps", "alt_text": "Logo"}
        rejected_eps = await client.patch(f"/api/webstores/{store['id']}/branding/draft", json={"content": eps_art})
        assert rejected_eps.status_code == 400
        assert "web-ready" in rejected_eps.text

        pdf_art = _valid_branding(store)
        pdf_art["store_information"]["supporting_image"] = {"url": "https://assets.example.test/info.pdf", "alt_text": "Info"}
        rejected_pdf = await client.patch(f"/api/webstores/{store['id']}/branding/draft", json={"content": pdf_art})
        assert rejected_pdf.status_code == 400


@pytest.mark.asyncio
async def test_published_branding_stays_live_while_replacement_draft_is_reviewed(branding_ctx):
    store = await _seed_store(branding_ctx, store_type="general", status="live")
    _, owner_token = await _portal_identity(branding_ctx, store, role="owner")
    first = _valid_branding(store, display_name="First Published")
    replacement = _valid_branding(store, display_name="Replacement Draft")

    async with await _client_as(branding_ctx["staff"]) as client:
        assert (await client.patch(f"/api/webstores/{store['id']}/branding/draft", json={"content": first})).status_code == 200
        assert (await client.post(f"/api/webstores/{store['id']}/branding/request-review", json={})).status_code == 200
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {owner_token}"}) as portal:
        assert (await portal.post(f"/api/portal/webstores/{store['id']}/branding/approve", json={})).status_code == 200
    async with await _client_as(branding_ctx["staff"]) as client:
        assert (await client.post(f"/api/webstores/{store['id']}/branding/publish")).status_code == 200
        assert (await client.patch(f"/api/webstores/{store['id']}/branding/draft", json={"content": replacement})).status_code == 200

    public = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    async with public:
        storefront = await public.get(f"/api/public/webstores/{store['public_slug']}")
        assert storefront.status_code == 200, storefront.text
        assert storefront.json()["webstore"]["branding"]["brand_basics"]["display_name"] == "First Published"

    async with await _client_as(branding_ctx["staff"]) as client:
        assert (await client.post(f"/api/webstores/{store['id']}/branding/request-review", json={})).status_code == 200
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {owner_token}"}) as portal:
        assert (await portal.post(f"/api/portal/webstores/{store['id']}/branding/approve", json={})).status_code == 200
    async with await _client_as(branding_ctx["staff"]) as client:
        published = await client.post(f"/api/webstores/{store['id']}/branding/publish")
        assert published.status_code == 200, published.text
        assert len(published.json()["history"]) == 2

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as public_after_replacement:
        updated = await public_after_replacement.get(f"/api/public/webstores/{store['public_slug']}")
        assert updated.json()["webstore"]["branding"]["brand_basics"]["display_name"] == "Replacement Draft"


@pytest.mark.asyncio
async def test_public_storefront_never_exposes_unpublished_draft_and_keeps_hidden_sections(branding_ctx):
    store = await _seed_store(branding_ctx, store_type="general", status="live")
    _, owner_token = await _portal_identity(branding_ctx, store, role="owner")
    hidden = _valid_branding(store, display_name="Hidden Section Store")
    hidden["header"]["show_header"] = False
    hidden["hero"]["show_hero"] = False
    hidden["catalog_introduction"]["show_catalog_area"] = False

    async with await _client_as(branding_ctx["staff"]) as client:
        assert (await client.patch(f"/api/webstores/{store['id']}/branding/draft", json={"content": hidden})).status_code == 200

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as public_before_publish:
        before = await public_before_publish.get(f"/api/public/webstores/{store['public_slug']}")
        assert before.status_code == 200, before.text
        assert before.json()["webstore"]["branding"] == {}

    async with await _client_as(branding_ctx["staff"]) as client:
        assert (await client.post(f"/api/webstores/{store['id']}/branding/request-review", json={})).status_code == 200
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {owner_token}"}) as portal:
        assert (await portal.post(f"/api/portal/webstores/{store['id']}/branding/approve", json={})).status_code == 200
    async with await _client_as(branding_ctx["staff"]) as client:
        assert (await client.post(f"/api/webstores/{store['id']}/branding/publish")).status_code == 200

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as public_after_publish:
        after = await public_after_publish.get(f"/api/public/webstores/{store['public_slug']}")
        branding = after.json()["webstore"]["branding"]
        assert branding["header"]["show_header"] is False
        assert branding["hero"]["show_hero"] is False
        assert branding["catalog_introduction"]["show_catalog_area"] is False
        assert "submitted_snapshot" not in branding


@pytest.mark.asyncio
async def test_editing_submitted_or_approved_branding_requires_new_review(branding_ctx):
    store = await _seed_store(branding_ctx, store_type="general", status="live")
    _, owner_token = await _portal_identity(branding_ctx, store, role="owner")
    initial = _valid_branding(store, display_name="Submitted Branding")
    changed = _valid_branding(store, display_name="Changed Branding")

    async with await _client_as(branding_ctx["staff"]) as client:
        assert (await client.patch(f"/api/webstores/{store['id']}/branding/draft", json={"content": initial})).status_code == 200
        assert (await client.post(f"/api/webstores/{store['id']}/branding/request-review", json={})).status_code == 200
        resaved = await client.patch(f"/api/webstores/{store['id']}/branding/draft", json={"content": changed})
        assert resaved.status_code == 200, resaved.text
        assert resaved.json()["branding"]["status"] == "draft"
        publish_denied = await client.post(f"/api/webstores/{store['id']}/branding/publish")
        assert publish_denied.status_code == 409
        assert "Owner approval is required" in publish_denied.text

        assert (await client.post(f"/api/webstores/{store['id']}/branding/request-review", json={})).status_code == 200
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {owner_token}"}) as portal:
        assert (await portal.post(f"/api/portal/webstores/{store['id']}/branding/approve", json={})).status_code == 200

    approved_edit = _valid_branding(store, display_name="Edited After Approval")
    async with await _client_as(branding_ctx["staff"]) as client:
        edited = await client.patch(f"/api/webstores/{store['id']}/branding/draft", json={"content": approved_edit})
        assert edited.status_code == 200, edited.text
        assert edited.json()["branding"]["status"] == "draft"
        denied = await client.post(f"/api/webstores/{store['id']}/branding/publish")
        assert denied.status_code == 409


@pytest.mark.asyncio
async def test_publish_uses_complete_existing_launch_readiness_dimensions(branding_ctx):
    store = await _seed_store(branding_ctx, store_type="general", status="live")
    await _upsert_entitlement_for_tests(tenant_id=branding_ctx["tenant_id"], feature_key="webstores", enabled=False)
    await db.webstore_products.delete_many({"tenant_id": branding_ctx["tenant_id"], "webstore_id": store["id"]})
    await db.webstores.update_one(
        {"tenant_id": branding_ctx["tenant_id"], "id": store["id"]},
        {
            "$set": {"checkout_enabled": True, "stripe_payment_ready": False},
            "$unset": {"launch_packet_id": "", "owner_approved_at": "", "terms_fee_acknowledged": ""},
        },
    )
    _, owner_token = await _portal_identity(branding_ctx, store, role="owner")
    async with await _client_as(branding_ctx["staff"]) as client:
        assert (await client.patch(f"/api/webstores/{store['id']}/branding/draft", json={"content": _valid_branding(store)})).status_code == 200
        assert (await client.post(f"/api/webstores/{store['id']}/branding/request-review", json={})).status_code == 200
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {owner_token}"}) as portal:
        assert (await portal.post(f"/api/portal/webstores/{store['id']}/branding/approve", json={})).status_code == 200
    async with await _client_as(branding_ctx["staff"]) as client:
        denied = await client.post(f"/api/webstores/{store['id']}/branding/publish")
        assert denied.status_code == 409
        body = denied.text
        assert "entitlement" in body
        assert "active public product" in body
        assert "launch packet" in body
        assert "Store Owner launch approval" in body
        assert "fee terms" in body
        assert "Payment readiness" in body


@pytest.mark.asyncio
async def test_published_version_numbers_are_atomic_and_unique(branding_ctx):
    store = await _seed_store(branding_ctx, store_type="general")
    versions = await asyncio.gather(
        *[branding_svc._next_published_version(branding_ctx["tenant_id"], store["id"]) for _ in range(8)]
    )
    assert sorted(versions) == list(range(1, 9))
