"""Webstores Stage 2 setup and owner-intake contracts."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db, ensure_indexes
from app.core.portal_security import hash_token
from app.deps import get_current_user
from app.services.webstore_setup import WEBSTORE_SETUP_STATES
from server import app


def _override(user: dict):
    async def _get():
        return {**user}

    return _get


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def stage2_ctx():
    await ensure_indexes()
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-webstore-stage2-{suffix}"
    other_tenant_id = f"t-webstore-stage2-other-{suffix}"
    user = {"id": f"user-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    other_user = {"id": f"other-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": f"shop-{suffix}", "name": f"Shop {suffix}"},
        {"id": other_tenant_id, "slug": f"other-shop-{suffix}", "name": f"Other Shop {suffix}"},
    ])
    await db.users.insert_many([user, other_user])
    yield {"suffix": suffix, "tenant_id": tenant_id, "other_tenant_id": other_tenant_id, "user": user, "other_user": other_user}
    app.dependency_overrides.pop(get_current_user, None)


async def _create_store(client: AsyncClient, suffix: str, *, store_type: str = "event") -> dict:
    owner_resp = await client.post(
        "/api/webstores/owners",
        json={"name": f"Store Owner {suffix}", "email": f"store-owner-{suffix}@example.com", "create_portal_identity": False},
    )
    assert owner_resp.status_code == 201, owner_resp.text
    owner = owner_resp.json()
    store_resp = await client.post(
        "/api/webstores",
        json={
            "owner_id": owner["id"],
            "name": f"Stage Two Store {suffix}",
            "slug": f"stage-two-store-{suffix}",
            "store_type": store_type,
            "target_launch_at": "2026-09-01",
            "deadline_at": "2026-09-20",
            "manager_emails": [f"manager-{suffix}@example.com"],
            "idempotency_key": f"stage2-create-{suffix}",
            "send_owner_invitation": True,
        },
    )
    assert store_resp.status_code == 201, store_resp.text
    return {"owner": owner, "store": store_resp.json()}


@pytest.mark.asyncio
async def test_stage2_create_store_creates_hashed_invitation_assignments_and_is_idempotent(stage2_ctx):
    async with await _client_as(stage2_ctx["user"]) as client:
        created = await _create_store(client, stage2_ctx["suffix"], store_type="fundraiser")
        replay_resp = await client.post(
            "/api/webstores",
            json={
                "owner_id": created["owner"]["id"],
                "name": "Replay should not duplicate",
                "store_type": "fundraiser",
                "idempotency_key": f"stage2-create-{stage2_ctx['suffix']}",
            },
        )
        assert replay_resp.status_code == 201, replay_resp.text
        assert replay_resp.json()["id"] == created["store"]["id"]

        assignments = (await client.get(f"/api/webstores/{created['store']['id']}/assignments")).json()["items"]
        assert {a["role"] for a in assignments} == {"owner", "manager"}
        assert sum(1 for a in assignments if a["is_primary_owner"]) == 1
        assert all(a["status"] in {"invited", "active"} for a in assignments)

    invitations = [
        doc
        async for doc in db.webstore_invitations.find(
            {"tenant_id": stage2_ctx["tenant_id"], "webstore_id": created["store"]["id"]},
            {"_id": 0},
        )
    ]
    assert len(invitations) == 2
    assert all(doc.get("token_hash") and "token" not in doc for doc in invitations)
    assert await db.webstores.count_documents({"tenant_id": stage2_ctx["tenant_id"], "creation_idempotency_key": f"stage2-create-{stage2_ctx['suffix']}"}) == 1


@pytest.mark.asyncio
async def test_invitation_acceptance_is_one_time_and_owner_portal_is_assignment_scoped(stage2_ctx):
    async with await _client_as(stage2_ctx["user"]) as client:
        created = await _create_store(client, stage2_ctx["suffix"])
        assignment_resp = await client.post(
            f"/api/webstores/{created['store']['id']}/assignments",
            json={"role": "owner", "email": f"second-owner-{stage2_ctx['suffix']}@example.com", "name": "Second Owner"},
        )
        assert assignment_resp.status_code == 201, assignment_resp.text
        raw = assignment_resp.json()["invitation"]["invitation_url"].split("t=", 1)[1]

    invite = await db.webstore_invitations.find_one({"token_hash": hash_token(raw)}, {"_id": 0})
    assert invite and invite["status"] in {"sent", "send_failed", "pending"}

    public = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    async with public:
        accept = await public.post("/api/portal/webstores/invitations/accept", json={"token": raw})
        assert accept.status_code == 200, accept.text
        token = accept.json()["token"]
        replay = await public.post("/api/portal/webstores/invitations/accept", json={"token": raw})
        assert replay.status_code == 410

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"}) as portal:
        owned = await portal.get("/api/portal/webstores")
        assert owned.status_code == 200, owned.text
        assert [store["id"] for store in owned.json()["items"]] == [created["store"]["id"]]
        detail = await portal.get(f"/api/portal/webstores/{created['store']['id']}")
        assert detail.status_code == 200, detail.text

    other_store = {"id": f"other-ws-{stage2_ctx['suffix']}", "tenant_id": stage2_ctx["tenant_id"], "owner_id": created["owner"]["id"], "name": "Other", "slug": f"other-{stage2_ctx['suffix']}", "public_slug": f"other-public-{stage2_ctx['suffix']}", "store_type": "general", "status": "draft"}
    await db.webstores.insert_one(other_store)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"}) as portal:
        forbidden = await portal.get(f"/api/portal/webstores/{other_store['id']}")
        assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_questionnaire_snapshot_safe_apply_and_reversal_are_non_pricing(stage2_ctx):
    async with await _client_as(stage2_ctx["user"]) as client:
        created = await _create_store(client, stage2_ctx["suffix"], store_type="event")
        assignment = (await client.get(f"/api/webstores/{created['store']['id']}/assignments")).json()["items"][0]
        resend = await client.post(f"/api/webstores/{created['store']['id']}/assignments/{assignment['id']}/resend")
        raw = resend.json()["invitation"]["invitation_url"].split("t=", 1)[1]

    public = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    async with public:
        accepted = await public.post("/api/portal/webstores/invitations/accept", json={"token": raw})
    token = accepted.json()["token"]

    answers = {
        "store_name": "Owner Supplied Name",
        "event_location": "Town Park",
        "selling_price_cents": 1,
        "stripe_payment_ready": True,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"}) as portal:
        draft = await portal.post(f"/api/portal/webstores/{created['store']['id']}/questionnaire/draft", json={"answers": answers})
        assert draft.status_code == 200, draft.text
        submitted = await portal.post(f"/api/portal/webstores/{created['store']['id']}/questionnaire", json={"answers": answers})
        assert submitted.status_code == 200, submitted.text
        submission_id = submitted.json()["id"]
        assert submitted.json()["submitted_snapshot"]["answers"] == answers

    async with await _client_as(stage2_ctx["user"]) as client:
        preview = await client.post(
            f"/api/webstores/{created['store']['id']}/questionnaire/apply-preview",
            json={"submission_id": submission_id, "selected_answer_keys": []},
        )
        assert preview.status_code == 200, preview.text
        rejected = {row["answer_key"] for row in preview.json()["rejected_changes"]}
        assert {"selling_price_cents", "stripe_payment_ready"} <= rejected
        assert any(row["target"] == "name" and row["to"] == "Owner Supplied Name" for row in preview.json()["proposed_changes"])

        apply = await client.post(
            f"/api/webstores/{created['store']['id']}/questionnaire/apply",
            json={"submission_id": submission_id, "reason": "Owner verified", "idempotency_key": f"apply-{stage2_ctx['suffix']}"},
        )
        assert apply.status_code == 200, apply.text
        replay = await client.post(
            f"/api/webstores/{created['store']['id']}/questionnaire/apply",
            json={"submission_id": submission_id, "reason": "Owner verified", "idempotency_key": f"apply-{stage2_ctx['suffix']}"},
        )
        assert replay.json()["idempotent_replay"] is True
        store = await db.webstores.find_one({"tenant_id": stage2_ctx["tenant_id"], "id": created["store"]["id"]}, {"_id": 0})
        assert store["name"] == "Owner Supplied Name"
        assert store.get("stripe_payment_ready") is False
        assert "selling_price_cents" not in store

        reversed_resp = await client.post(
            f"/api/webstores/{created['store']['id']}/answer-applications/{apply.json()['application']['id']}/reverse",
            json={"reason": "Incorrect owner response"},
        )
        assert reversed_resp.status_code == 200, reversed_resp.text
        reverted = await db.webstores.find_one({"tenant_id": stage2_ctx["tenant_id"], "id": created["store"]["id"]}, {"_id": 0})
        assert reverted["name"] == created["store"]["name"]


@pytest.mark.asyncio
async def test_setup_files_are_validated_stored_versioned_and_allowlisted(stage2_ctx):
    async with await _client_as(stage2_ctx["user"]) as client:
        created = await _create_store(client, stage2_ctx["suffix"])
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        upload = await client.post(
            f"/api/webstores/{created['store']['id']}/setup-files",
            data={"category": "logo"},
            files={"file": ("logo.png", png, "image/png")},
        )
        assert upload.status_code == 201, upload.text
        file_doc = upload.json()["file"]
        assert "storage_key" not in file_doc
        assert file_doc["private_download_only"] is False

        mismatch = await client.post(
            f"/api/webstores/{created['store']['id']}/setup-files",
            data={"category": "logo"},
            files={"file": ("logo.png", b"not-a-png", "image/png")},
        )
        assert mismatch.status_code == 400

        blocked = await client.post(
            f"/api/webstores/{created['store']['id']}/setup-files",
            data={"category": "script"},
            files={"file": ("run.exe", b"MZ", "application/octet-stream")},
        )
        assert blocked.status_code == 400

        replacement = await client.post(
            f"/api/webstores/{created['store']['id']}/setup-files",
            data={"category": "logo", "replaces_file_id": file_doc["id"]},
            files={"file": ("logo2.png", png, "image/png")},
        )
        assert replacement.status_code == 201, replacement.text
        assert replacement.json()["file"]["version"] == 2
        previous = await db.webstore_setup_files.find_one({"tenant_id": stage2_ctx["tenant_id"], "id": file_doc["id"]}, {"_id": 0})
        assert previous["status"] == "replaced"


@pytest.mark.asyncio
async def test_stage2_indexes_and_states_are_registered(stage2_ctx):
    await ensure_indexes()
    expected = {
        "webstore_access_assignments",
        "webstore_invitations",
        "webstore_questionnaire_templates",
        "webstore_setup_files",
        "webstore_answer_applications",
    }
    for collection_name in expected:
        indexes = await db[collection_name].index_information()
        indexed_keys = [tuple(key for key, _ in spec["key"]) for spec in indexes.values()]
        assert ("id",) in indexed_keys
    assert "setup_complete" in WEBSTORE_SETUP_STATES
