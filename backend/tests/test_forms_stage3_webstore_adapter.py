"""Focused Stage 3A/3B tests for shared Form Maker and Webstores adapter."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db, ensure_indexes
from app.core.portal_security import hash_token
from app.deps import get_current_user
from server import app


def _override(user: dict):
    async def _get():
        return {**user}

    return _get


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def forms_ctx():
    await ensure_indexes()
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-forms-stage3-{suffix}"
    other_tenant_id = f"t-forms-stage3-other-{suffix}"
    user = {"id": f"user-{suffix}", "tenant_id": tenant_id, "email": f"user-{suffix}@example.com", "role": "owner", "is_active": True}
    other_user = {"id": f"other-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True}
    no_perm_user = {"id": f"noperm-{suffix}", "tenant_id": tenant_id, "email": f"noperm-{suffix}@example.com", "role": "viewer", "is_active": True}
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": f"forms-{suffix}", "name": f"Forms {suffix}"},
        {"id": other_tenant_id, "slug": f"forms-other-{suffix}", "name": f"Other Forms {suffix}"},
    ])
    await db.users.insert_many([user, other_user, no_perm_user])
    yield {"suffix": suffix, "tenant_id": tenant_id, "other_tenant_id": other_tenant_id, "user": user, "other_user": other_user, "no_perm_user": no_perm_user}
    app.dependency_overrides.pop(get_current_user, None)


def _donor_questions() -> list[dict]:
    return [
        {"key": "intro", "label": "Intro", "type": "heading"},
        {"key": "copy", "label": "Instructions", "type": "paragraph"},
        {"key": "name", "label": "Name", "type": "text", "required": True, "validation": {"min_length": 2}},
        {"key": "details", "label": "Details", "type": "textarea"},
        {"key": "quantity", "label": "Quantity", "type": "number", "validation": {"min": 1, "max": 10}},
        {"key": "email", "label": "Email", "type": "email", "required": True},
        {"key": "phone", "label": "Phone", "type": "phone"},
        {"key": "dropdown", "label": "Dropdown", "type": "select", "options": [{"value": "a", "label": "A"}, {"value": "b", "label": "B"}]},
        {"key": "multi", "label": "Multi", "type": "multi_select", "options": [{"value": "x", "label": "X"}]},
        {"key": "radio", "label": "Radio", "type": "radio", "required": True, "options": [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}]},
        {"key": "conditional_details", "label": "Conditional Details", "type": "text", "required": True, "conditional": {"depends_on": "radio", "operator": "equals", "value": "yes"}},
        {"key": "checks", "label": "Checks", "type": "checkbox", "options": [{"value": "one", "label": "One"}]},
        {"key": "date", "label": "Date", "type": "date"},
        {"key": "upload", "label": "Upload", "type": "file_upload", "accept_file_types": ["image/*", ".pdf"], "max_file_size_mb": 25},
        {"key": "signature", "label": "Signature", "type": "signature"},
    ]


@pytest.mark.asyncio
async def test_shared_form_public_request_validation_version_single_use_and_tenant_isolation(forms_ctx):
    async with await _client_as(forms_ctx["no_perm_user"]) as no_perm:
        denied = await no_perm.get("/api/forms/templates")
        assert denied.status_code == 403

    async with await _client_as(forms_ctx["user"]) as client:
        created = await client.post(
            "/api/forms/templates",
            json={
                "name": "Donor Dynamic Form",
                "module": "webstores",
                "context_type": "webstore",
                "status": "published",
                "questions": _donor_questions(),
                "private_config": {"internal_only": True},
            },
        )
        assert created.status_code == 201, created.text
        template = created.json()
        assert {q["type"] for q in template["sections"][0]["questions"]} >= {
            "text", "textarea", "number", "email", "phone", "select", "multi_select", "radio", "checkbox", "date", "file_upload", "signature", "heading", "paragraph",
        }

        request = await client.post("/api/forms/requests", json={"template_id": template["id"], "context_type": "webstore", "context_id": "ws-1"})
        assert request.status_code == 201, request.text
        request_body = request.json()
        token = request_body["request_token"]
        assert request_body["template_version"] == 1
        assert datetime.fromisoformat(request_body["expires_at"]) > datetime.now(timezone.utc)

        updated = await client.patch(
            f"/api/forms/templates/{template['id']}",
            json={"questions": [{**_donor_questions()[2], "label": "Changed Name"}]},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["version"] == 2
        assert updated.json()["status"] == "draft"

    public = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    async with public:
        opened = await public.get(f"/api/public/forms/requests/{token}")
        assert opened.status_code == 200, opened.text
        assert opened.json()["template"]["version"] == 1
        assert "private_config" not in opened.json()["template"]

        invalid = await public.post(
            f"/api/public/forms/requests/{token}/responses",
            json={"answers": {"name": "A", "email": "bad", "radio": "yes"}},
        )
        assert invalid.status_code == 400

    foreign_file = {
        "id": f"foreign-file-{forms_ctx['suffix']}",
        "tenant_id": forms_ctx["other_tenant_id"],
        "storage_key": f"SignGuy/tenants/{forms_ctx['other_tenant_id']}/files/x.pdf",
        "original_filename": "foreign.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 12,
        "uploaded_by": forms_ctx["other_user"]["id"],
        "visibility": "customer_visible",
        "sha256": f"sha-{forms_ctx['suffix']}",
    }
    await db.files.insert_one(foreign_file)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as public:
        foreign_attachment = await public.post(
            f"/api/public/forms/requests/{token}/responses",
            json={
                "answers": {"name": "Alice", "email": "alice@example.com", "quantity": 2, "radio": "no"},
                "attachments": [{"file_id": foreign_file["id"], "field_key": "upload"}],
            },
        )
        assert foreign_attachment.status_code == 404

        submitted = await public.post(
            f"/api/public/forms/requests/{token}/responses",
            json={
                "respondent_email": "alice@example.com",
                "answers": {
                    "name": "Alice",
                    "details": "Notes",
                    "quantity": 2,
                    "email": "alice@example.com",
                    "phone": "555-1212",
                    "dropdown": "a",
                    "multi": ["x"],
                    "radio": "no",
                    "checks": ["one"],
                    "date": "2026-09-01",
                    "upload": {"file_name": "logo.pdf", "field_key": "upload"},
                    "signature": "Alice",
                },
                "attachments": [{"file_name": "logo.pdf", "content_type": "application/pdf", "size_bytes": 123, "field_key": "upload"}],
            },
        )
        assert submitted.status_code == 201, submitted.text
        response = submitted.json()
        assert response["template_version"] == 1
        assert response["submitted_snapshot"]["template"]["sections"][0]["questions"][2]["label"] == "Name"

        replay = await public.post(f"/api/public/forms/requests/{token}/responses", json={"answers": {"name": "Replay"}})
        assert replay.status_code == 409
        reopened = await public.get(f"/api/public/forms/requests/{token}")
        assert reopened.status_code == 409

    async with await _client_as(forms_ctx["other_user"]) as other:
        invisible_templates = await other.get("/api/forms/templates", params={"module": "webstores"})
        assert invisible_templates.status_code == 200
        assert all(item["id"] != template["id"] for item in invisible_templates.json()["items"])
        invisible_responses = await other.get("/api/forms/responses", params={"template_id": template["id"]})
        assert invisible_responses.status_code == 200
        assert invisible_responses.json()["items"] == []

    async with await _client_as(forms_ctx["user"]) as client:
        responses = await client.get("/api/forms/responses", params={"template_id": template["id"]})
        assert responses.status_code == 200
        assert responses.json()["items"][0]["answers"]["name"] == "Alice"


async def _create_webstore(client: AsyncClient, suffix: str, *, store_type: str = "event") -> dict:
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
            "name": f"Stage Three Store {suffix}",
            "slug": f"stage-three-store-{suffix}",
            "store_type": store_type,
            "idempotency_key": f"stage3-create-{suffix}",
            "send_owner_invitation": True,
        },
    )
    assert store_resp.status_code == 201, store_resp.text
    return {"owner": owner, "store": store_resp.json()}


@pytest.mark.asyncio
async def test_webstore_adapter_idempotent_seeding_canonical_authority_and_response_preservation(forms_ctx):
    async with await _client_as(forms_ctx["user"]) as client:
        created = await _create_webstore(client, forms_ctx["suffix"], store_type="event")
        first = await client.get(f"/api/webstores/{created['store']['id']}/questionnaire")
        second = await client.get(f"/api/webstores/{created['store']['id']}/questionnaire")
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        shared_count = await db.form_templates.count_documents({"tenant_id": forms_ctx["tenant_id"], "module": "webstores"})
        await client.get(f"/api/webstores/{created['store']['id']}/questionnaire")
        assert await db.form_templates.count_documents({"tenant_id": forms_ctx["tenant_id"], "module": "webstores"}) == shared_count

        legacy_write = await client.post(
            "/api/webstores/setup/questionnaire-templates",
            json={"title": "Conflicting Legacy Edit", "store_type": "event", "sections": []},
        )
        assert legacy_write.status_code == 409

        event_template = next(item for item in first.json()["templates"] if item["store_type"] == "event")
        shared_form_id = event_template["shared_form_template_id"]
        patched = await client.patch(
            f"/api/forms/templates/{shared_form_id}",
            json={
                "name": "Canonical Event Intake",
                "status": "published",
                "sections": [{"id": "event", "title": "Canonical Event", "questions": [{"key": "event_name", "label": "Event Name", "type": "text", "required": True}]}],
            },
        )
        assert patched.status_code == 200, patched.text
        rebound = await client.get(f"/api/webstores/{created['store']['id']}/questionnaire")
        assert any(item["title"] == "Canonical Event Intake" and item["version"] == patched.json()["version"] for item in rebound.json()["templates"])

        assignment = (await client.get(f"/api/webstores/{created['store']['id']}/assignments")).json()["items"][0]
        raw = (await client.post(f"/api/webstores/{created['store']['id']}/assignments/{assignment['id']}/resend")).json()["invitation"]["invitation_url"].split("t=", 1)[1]

    public = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    async with public:
        token = (await public.post("/api/portal/webstores/invitations/accept", json={"token": raw})).json()["token"]

    answers = {"store_name": "Owner Name", "event_location": "Town Park"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"}) as portal:
        submitted = await portal.post(f"/api/portal/webstores/{created['store']['id']}/questionnaire", json={"answers": answers})
        assert submitted.status_code == 200, submitted.text
        submission = submitted.json()
        assert submission["submitted_snapshot"]["answers"] == answers
        assert "event_name" in submission["missing_info_flags"]

    async with await _client_as(forms_ctx["user"]) as client:
        preview = await client.post(
            f"/api/webstores/{created['store']['id']}/questionnaire/apply-preview",
            json={"submission_id": submission["id"], "selected_answer_keys": ["store_name"], "proposed_values": {"store_name": "Reviewed Name"}},
        )
        assert preview.status_code == 200, preview.text
        assert preview.json()["dry_run"] is True
        assert preview.json()["proposed_changes"][0]["from"] == created["store"]["name"]
        assert preview.json()["proposed_changes"][0]["to"] == "Reviewed Name"

        applied = await client.post(
            f"/api/webstores/{created['store']['id']}/questionnaire/apply",
            json={
                "submission_id": submission["id"],
                "selected_answer_keys": ["store_name"],
                "proposed_values": {"store_name": "Reviewed Name"},
                "reason": "Verified owner answer",
                "idempotency_key": f"apply-stage3-{forms_ctx['suffix']}",
            },
        )
        assert applied.status_code == 200, applied.text
        assert applied.json()["application"]["applied_changes"][0]["answer_key"] == "store_name"
        latest = (await client.get(f"/api/webstores/{created['store']['id']}/questionnaire-response")).json()["submission"]
        assert latest["submitted_snapshot"]["answers"] == answers
        store = (await client.get(f"/api/webstores/{created['store']['id']}")).json()["webstore"]
        assert store["name"] == "Reviewed Name"

    assert await db.form_templates.count_documents({"tenant_id": forms_ctx["other_tenant_id"], "module": "webstores"}) == 0
