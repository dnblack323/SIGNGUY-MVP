"""Webstores Phase 2a: one questionnaire template authority, conditional validation, immutable revisions."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db, ensure_indexes
from app.deps import get_current_user
from app.services import webstore_questionnaire_pack as pack
from server import app
from tests.webstore_questionnaire_answers import complete_answers

BASE_REQUIRED = complete_answers("event")


def _override(user: dict):
    async def _get():
        return {**user}

    return _get


async def _staff(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def ctx():
    await ensure_indexes()
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-ws-p2a-{suffix}"
    other_tenant_id = f"t-ws-p2a-other-{suffix}"
    user = {"id": f"user-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "role": "owner", "is_active": True}
    other_user = {"id": f"other-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": f"p2a-{suffix}", "name": f"P2a {suffix}"},
        {"id": other_tenant_id, "slug": f"p2a-other-{suffix}", "name": f"P2a other {suffix}"},
    ])
    await db.users.insert_many([user, other_user])
    yield {"suffix": suffix, "tenant_id": tenant_id, "other_tenant_id": other_tenant_id, "user": user, "other_user": other_user}
    app.dependency_overrides.pop(get_current_user, None)


async def _store_with_portal(client: AsyncClient, suffix: str, store_type: str = "event") -> tuple[dict, str]:
    owner = (await client.post(
        "/api/webstores/owners",
        json={"name": f"Owner {suffix}", "email": f"ws-owner-{suffix}@example.com", "create_portal_identity": False},
    )).json()
    created = await client.post(
        "/api/webstores",
        json={
            "owner_id": owner["id"],
            "name": f"P2a Store {suffix}",
            "slug": f"p2a-store-{suffix}",
            "store_type": store_type,
            "idempotency_key": f"p2a-{suffix}",
            "send_owner_invitation": True,
        },
    )
    assert created.status_code == 201, created.text
    store = created.json()
    assignment = (await client.get(f"/api/webstores/{store['id']}/assignments")).json()["items"][0]
    raw = (await client.post(f"/api/webstores/{store['id']}/assignments/{assignment['id']}/resend")).json()["invitation"]["invitation_url"].split("t=", 1)[1]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as public:
        token = (await public.post("/api/portal/webstores/invitations/accept", json={"token": raw})).json()["token"]
    return store, token


def _portal(token: str) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"})


async def _event_form_id(tenant_id: str) -> str:
    form = await db.form_templates.find_one({"tenant_id": tenant_id, "module": "webstores", "private_config.store_type": "event"}, {"_id": 0, "id": 1})
    return form["id"]


async def test_install_is_idempotent_tenant_scoped_and_hidden_from_templates_library(ctx):
    assert await pack.install_webstore_questionnaires(ctx["tenant_id"]) == len(pack.QUESTIONNAIRE_STORE_TYPES)
    assert await pack.install_webstore_questionnaires(ctx["tenant_id"]) == 0
    forms = [f async for f in db.form_templates.find({"tenant_id": ctx["tenant_id"], "module": "webstores"}, {"_id": 0})]
    assert {f["private_config"]["store_type"] for f in forms} == set(pack.QUESTIONNAIRE_STORE_TYPES)
    assert all(f["status"] == "published" and f["source_template_version"] == pack.WEBSTORE_STARTER_PACK_VERSION for f in forms)
    assert await db.form_templates.count_documents({"tenant_id": ctx["other_tenant_id"], "module": "webstores"}) == 0

    pack_doc = await db.template_packs.find_one({"id": pack.WEBSTORE_STARTER_PACK_ID}, {"_id": 0})
    questionnaire_ids = {f"webstore_starter_questionnaire_{t}" for t in pack.QUESTIONNAIRE_STORE_TYPES}
    assert pack_doc["pack_type"] == "starter" and questionnaire_ids <= set(pack_doc["included_template_ids"])
    async with await _staff(ctx["user"]) as client:
        library = await client.get("/api/templates", params={"template_type": "questionnaire"})
        assert library.status_code == 200, library.text
        listed = library.json().get("items", library.json())
        assert all((item.get("pack_id") != pack.WEBSTORE_STARTER_PACK_ID) for item in listed)


async def test_platform_pack_upgrade_never_overwrites_shop_copy(ctx):
    await pack.install_webstore_questionnaires(ctx["tenant_id"])
    form_id = await _event_form_id(ctx["tenant_id"])
    await db.form_templates.update_one({"id": form_id}, {"$set": {"name": "Shop's own event intake"}})
    source_id = "webstore_starter_questionnaire_event"
    await db.template_definitions.update_one({"id": source_id}, {"$set": {"version": 0}})
    await pack.ensure_platform_webstore_pack()  # re-upgrades the platform record
    await pack.install_webstore_questionnaires(ctx["tenant_id"])
    assert (await db.form_templates.find_one({"id": form_id}, {"_id": 0}))["name"] == "Shop's own event intake"
    assert await db.form_templates.count_documents({"tenant_id": ctx["tenant_id"], "private_config.store_type": "event"}) == 1


async def test_hidden_required_questions_do_not_block_and_visible_ones_do(ctx):
    async with await _staff(ctx["user"]) as client:
        store, token = await _store_with_portal(client, ctx["suffix"])
        form_id = await _event_form_id(ctx["tenant_id"])
        patched = await client.patch(
            f"/api/forms/templates/{form_id}",
            json={
                "status": "published",
                "sections": [{"id": "event", "title": "Event", "questions": [
                    {"key": "event_name", "label": "Event name", "type": "text", "required": True},
                    {"key": "event_fundraiser_enabled", "label": "Also raising funds?", "type": "select", "options": [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}]},
                    {"key": "fundraiser_name", "label": "Fundraiser name", "type": "text", "required": True,
                     "conditional": {"depends_on": "event_fundraiser_enabled", "operator": "equals", "value": "yes"}},
                ]}],
            },
        )
        assert patched.status_code == 200, patched.text

    answers = {**BASE_REQUIRED, "event_name": "Spring Fair", "event_fundraiser_enabled": "no"}
    async with _portal(token) as portal:
        blocked = await portal.post(f"/api/portal/webstores/{store['id']}/questionnaire", json={"answers": {**answers, "event_fundraiser_enabled": "yes"}})
        assert blocked.status_code == 400
        assert "fundraiser_name" in blocked.text
        missing_visible = await portal.post(f"/api/portal/webstores/{store['id']}/questionnaire", json={"answers": {k: v for k, v in answers.items() if k != "event_name"}})
        assert missing_visible.status_code == 400 and "event_name" in missing_visible.text
        ok = await portal.post(f"/api/portal/webstores/{store['id']}/questionnaire", json={"answers": answers})
        assert ok.status_code == 200, ok.text
        assert ok.json()["status"] == "submitted"


async def test_resubmission_creates_revision_two_and_preserves_revision_one(ctx):
    async with await _staff(ctx["user"]) as client:
        store, token = await _store_with_portal(client, ctx["suffix"])
    first_answers = {**BASE_REQUIRED, "event_name": "Spring Fair", "event_location": "Gym"}
    async with _portal(token) as portal:
        first = (await portal.post(f"/api/portal/webstores/{store['id']}/questionnaire", json={"answers": first_answers})).json()
    assert first["revision"] == 1 and first["supersedes_submission_id"] is None

    async with await _staff(ctx["user"]) as client:
        returned = await client.post(f"/api/webstores/{store['id']}/questionnaire/{first['id']}/return", json={"reason": "Please confirm the venue"})
        assert returned.status_code == 200, returned.text

    second_answers = {**first_answers, "event_location": "Town Park"}
    async with _portal(token) as portal:
        resumed = (await portal.get(f"/api/portal/webstores/{store['id']}/questionnaire")).json()
        assert resumed["submission"]["status"] == "returned_for_changes"
        second = await portal.post(f"/api/portal/webstores/{store['id']}/questionnaire", json={"answers": second_answers})
        assert second.status_code == 200, second.text
        second = second.json()
        repeat = (await portal.post(f"/api/portal/webstores/{store['id']}/questionnaire", json={"answers": first_answers})).json()
    assert second["id"] != first["id"]
    assert second["revision"] == 2 and second["supersedes_submission_id"] == first["id"]
    assert repeat["id"] == second["id"] and repeat["submitted_snapshot"]["answers"] == second_answers

    original = await db.webstore_questionnaire_submissions.find_one({"id": first["id"]}, {"_id": 0})
    assert original["revision"] == 1
    assert original["submitted_snapshot"]["answers"] == first_answers
    assert original["status"] == "returned_for_changes"


async def test_store_bound_to_legacy_template_ids_rebinds_to_form_maker(ctx):
    async with await _staff(ctx["user"]) as client:
        store, token = await _store_with_portal(client, ctx["suffix"])
    await db.webstores.update_one({"id": store["id"]}, {"$set": {"setup_requirements.questionnaire_template_ids": ["legacy-template-id"]}})
    async with _portal(token) as portal:
        q = (await portal.get(f"/api/portal/webstores/{store['id']}/questionnaire")).json()
    assert [t["store_type"] for t in q["templates"]] == ["base", "event"]
    rebound = await db.webstores.find_one({"id": store["id"]}, {"_id": 0, "setup_requirements": 1})
    assert rebound["setup_requirements"]["questionnaire_template_ids"] == [t["id"] for t in q["templates"]]

    async with await _staff(ctx["other_user"]) as other:
        assert (await other.get(f"/api/webstores/{store['id']}/questionnaire")).status_code == 404
