"""Help & Documentation V1: packaged content integrity, idempotent sync, search, deep links, permissions."""
from __future__ import annotations

import re
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.deps import get_current_user
from app.help_content import catalog, load_articles
from app.services import help_center
from server import app

# The contract with Guided Onboarding (docs/modules/help_article_slug_registry.md).
ONBOARDING_SLUGS = {
    "getting-started", "company-profile", "pricing-setup", "employees-and-permissions",
    "production-workflow", "customer-portal", "first-order", "webstore-setup",
}
# Slugs the onboarding task catalog links to today; they must resolve (as a slug or an alias).
ONBOARDING_CATALOG_SLUGS = {
    "company-profile", "branding", "pricing-foundation", "production-workflows", "employees",
    "invoices-and-payments", "customer-portal", "customers", "orders", "time-clock", "shop-schedule",
}


def _known_names() -> set[str]:
    articles = load_articles()
    return {a["slug"] for a in articles} | {n for a in articles for n in a["aliases"]}


def test_packaged_content_is_consistent():
    articles = load_articles()
    slugs = [a["slug"] for a in articles]
    assert len(slugs) == len(set(slugs))
    known = _known_names()
    assert ONBOARDING_SLUGS <= set(slugs)
    assert ONBOARDING_CATALOG_SLUGS <= known
    assert set(catalog.ONBOARDING_ARTICLE_SLUGS.values()) == ONBOARDING_SLUGS
    assert {a["category"] for a in articles} <= set(catalog.CATEGORY_KEYS)
    for item in catalog.CONTEXTUAL_HELP:
        assert item["article_slug"] in known, item
    link = re.compile(r"/help/docs\?article=([a-z0-9-]+)")
    for article in articles:
        for target in link.findall(article["body"]):
            assert target in known, f"{article['slug']} links to unknown article {target}"
        for target in article["related"]:
            assert target in set(slugs)
        assert article["summary"] and article["body"]


def test_release_notes_have_identifier_and_date():
    releases = [a for a in load_articles() if a["category"] == "release_notes"]
    assert releases
    for release in releases:
        assert re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", release["release"])
        assert release["release_date"].replace("-", ".") == release["release"]


@pytest_asyncio.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id, other_tenant_id = f"t-help-{suffix}", f"t-help-other-{suffix}"
    users = {
        "owner": {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True},
        "staff": {"id": f"staff-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "role": "staff", "is_active": True},
        "other": {"id": f"other-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True},
        "platform": {"id": f"platform-{suffix}", "tenant_id": tenant_id, "email": f"platform-{suffix}@example.com", "role": "staff", "is_active": True, "platform_admin": True, "platform_role": "admin"},
    }
    await db.tenants.insert_many([{"id": tenant_id, "slug": tenant_id, "name": "Help Tenant"}, {"id": other_tenant_id, "slug": other_tenant_id, "name": "Other Help Tenant"}])
    await db.users.insert_many([dict(u) for u in users.values()])
    await help_center.sync_seed_content()
    yield {"suffix": suffix, "tenant_id": tenant_id, "other_tenant_id": other_tenant_id, **users}
    app.dependency_overrides.pop(get_current_user, None)


async def _as(user: dict) -> AsyncClient:
    async def _get():
        return {**user}

    app.dependency_overrides[get_current_user] = _get
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_sync_is_idempotent_and_never_duplicates(ctx):
    first = await help_center.sync_seed_content()
    second = await help_center.sync_seed_content()
    assert second["inserted"] == {"help_articles": 0, "contextual_help": 0}
    assert second["updated"] == 0 and second["archived"] == 0
    for article in load_articles():
        assert await db.help_articles.count_documents({"slug": article["slug"]}) == 1
    for item in catalog.CONTEXTUAL_HELP:
        assert await db.contextual_help_definitions.count_documents({"surface_key": item["surface_key"], "help_key": item["help_key"]}) == 1
    assert first["archived"] == 0


@pytest.mark.asyncio
async def test_sync_updates_seed_content_but_preserves_custom_edits_and_archives_retired(ctx, monkeypatch):
    base = tuple(load_articles())
    slug_a, slug_b, slug_gone = (f"zz-{n}-{ctx['suffix']}" for n in ("a", "b", "gone"))

    def synthetic(slug: str, body: str) -> dict:
        item = {"slug": slug, "title": slug, "category": "support", "module": "support", "summary": "s", "order": 999, "links": [],
                "body": body, "search_keywords": [], "aliases": [], "related": []}
        item["seed_hash"] = f"hash-{body}"
        return item

    monkeypatch.setattr(help_center, "load_articles", lambda: base + (synthetic(slug_a, "one"), synthetic(slug_b, "one"), synthetic(slug_gone, "one")))
    await help_center.sync_seed_content()
    assert (await db.help_articles.find_one({"slug": slug_a}))["body"] == "one"

    async with await _as(ctx["platform"]) as platform:
        edited = await platform.post("/api/help/platform/articles", json={"slug": slug_b, "title": "Custom B", "category": "support", "body": "customized", "status": "published"})
        assert edited.status_code == 201, edited.text

    monkeypatch.setattr(help_center, "load_articles", lambda: base + (synthetic(slug_a, "two"), synthetic(slug_b, "two")))
    result = await help_center.sync_seed_content()
    assert result["updated"] == 1 and result["archived"] == 1
    assert (await db.help_articles.find_one({"slug": slug_a}))["body"] == "two"
    assert (await db.help_articles.find_one({"slug": slug_b}))["body"] == "customized"
    assert (await db.help_articles.find_one({"slug": slug_gone}))["status"] == "archived"


@pytest.mark.asyncio
async def test_list_search_categories_and_deep_links(ctx):
    async with await _as(ctx["owner"]) as owner:
        listing = await owner.get("/api/help/articles")
        assert listing.status_code == 200
        items = listing.json()["items"]
        assert len(items) >= len(load_articles()) - 1
        assert all("body" not in item for item in items), "list responses stay lightweight"
        assert all(item["status"] == "published" for item in items)

        by_body = await owner.get("/api/help/articles", params={"q": "gross-pay ledger"})
        assert any(i["slug"] == "time-clock" for i in by_body.json()["items"])
        assert by_body.json()["items"][0]["snippet"]

        by_label = await owner.get("/api/help/articles", params={"q": "customers sales"})
        assert {i["category"] for i in by_label.json()["items"]} >= {"customers_sales"}

        multi = await owner.get("/api/help/articles", params={"q": "deposit invoice"})
        assert any(i["slug"] == "invoices-and-payments" for i in multi.json()["items"])

        nothing = await owner.get("/api/help/articles", params={"q": "zzqqxx-no-such-topic"})
        assert nothing.status_code == 200 and nothing.json()["items"] == []

        special = await owner.get("/api/help/articles", params={"q": "(.*[+"})
        assert special.status_code == 200, "regex metacharacters are escaped, not executed"

        scoped = await owner.get("/api/help/articles", params={"category": "webstores"})
        assert scoped.json()["items"] and {i["category"] for i in scoped.json()["items"]} == {"webstores"}

        categories = await owner.get("/api/help/categories")
        counts = {c["key"]: c["count"] for c in categories.json()["items"]}
        assert counts["customers_sales"] >= 6 and counts["release_notes"] >= 5

        for slug in ONBOARDING_SLUGS:
            article = await owner.get(f"/api/help/articles/{slug}")
            assert article.status_code == 200, slug
            assert article.json()["body"]
        aliased = await owner.get("/api/help/articles/production-workflows")
        assert aliased.status_code == 200 and aliased.json()["slug"] == "production-workflow"
        unknown = await owner.get("/api/help/articles/no-such-article")
        assert unknown.status_code == 404


@pytest.mark.asyncio
async def test_drafts_are_invisible_to_tenants_and_content_is_platform_managed(ctx):
    slug = f"draft-{ctx['suffix']}"
    async with await _as(ctx["platform"]) as platform:
        created = await platform.post("/api/help/platform/articles", json={"slug": slug, "title": "Draft", "category": "support", "body": "secret draft", "status": "draft"})
        assert created.status_code == 201
        clash = await platform.post("/api/help/platform/articles", json={"slug": f"clash-{ctx['suffix']}", "title": "Clash", "category": "support", "body": "x", "aliases": ["production-workflows"]})
        assert clash.status_code == 409
        assert (await platform.get(f"/api/help/articles/{slug}", params={"include_archived": True})).status_code == 200

    for who in ("owner", "other"):
        async with await _as(ctx[who]) as client:
            assert (await client.get(f"/api/help/articles/{slug}")).status_code == 404
            assert (await client.get(f"/api/help/articles/{slug}", params={"include_archived": True})).status_code == 404, "tenant users cannot opt in to drafts"
            listing = await client.get("/api/help/articles", params={"include_archived": True, "q": "secret draft"})
            assert listing.json()["items"] == []
            denied = await client.post("/api/help/platform/articles", json={"slug": f"x-{slug}", "title": "Nope", "body": "Nope"})
            assert denied.status_code == 403
            denied_status = await client.post("/api/help/platform/articles/getting-started/status", json={"status": "archived"})
            assert denied_status.status_code == 403
    async with await _as(ctx["staff"]) as staff:
        assert (await staff.get("/api/help/articles/getting-started")).status_code == 200


@pytest.mark.asyncio
async def test_contextual_help_links_resolve_to_published_articles(ctx):
    async with await _as(ctx["owner"]) as owner:
        for surface in ("pricing.foundation", "production.workflows", "orders.list", "invoices.detail", "employees.list",
                        "webstores.questionnaire", "webstores.fulfillment", "approvals.center"):
            res = await owner.get(f"/api/help/contextual/{surface}")
            assert res.status_code == 200
            items = res.json()["items"]
            assert items, surface
            for item in items:
                assert (await owner.get(f"/api/help/articles/{item['article_slug']}")).status_code == 200, item


@pytest.mark.asyncio
async def test_help_center_has_no_second_support_queue(ctx):
    async with await _as(ctx["owner"]) as owner:
        res = await owner.post("/api/help/support/escalations", json={"subject": "s", "message": "m"})
        assert res.status_code in {404, 405}
    assert await db.support_escalations.count_documents({"tenant_id": ctx["tenant_id"]}) == 0
