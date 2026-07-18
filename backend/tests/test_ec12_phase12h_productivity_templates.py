"""EC12 Phase 12H - productivity and communication templates."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.portal_security import create_portal_token
from app.deps import get_current_user
from server import app


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
    tenant_id = f"t-12h-{suffix}"
    other_tenant_id = f"t-12h-other-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    staff = {"id": f"staff-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "role": "staff", "is_active": True}
    platform_admin = {"id": f"platform-{suffix}", "tenant_id": tenant_id, "email": f"platform-{suffix}@example.com", "role": "owner", "is_active": True, "platform_admin": True, "platform_role": "admin"}
    other_owner = {"id": f"other-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "Tenant"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Other"},
    ])
    await db.users.insert_many([owner, staff, platform_admin, other_owner])
    customer_id = f"cust-{suffix}"
    await db.customers.insert_one({"id": customer_id, "tenant_id": tenant_id, "name": "Acme"})
    portal_identity = {
        "id": f"pid-{suffix}", "tenant_id": tenant_id, "portal_type": "customer",
        "customer_id": customer_id, "email": f"customer-{suffix}@example.com", "status": "active",
        "permissions": ["portal:view_quotes"], "permissions_preset": "viewer_only",
    }
    employee_identity = {
        "id": f"epid-{suffix}", "tenant_id": tenant_id, "portal_type": "employee",
        "employee_id": f"emp-{suffix}", "email": f"employee-{suffix}@example.com", "status": "active",
        "permissions": [], "permissions_preset": "custom",
    }
    await db.portal_identities.insert_many([portal_identity, employee_identity])
    customer_token = create_portal_token(portal_identity_id=portal_identity["id"], tenant_id=tenant_id, portal_type="customer", customer_id=customer_id)
    employee_token = create_portal_token(portal_identity_id=employee_identity["id"], tenant_id=tenant_id, portal_type="employee", employee_id=employee_identity["employee_id"])
    yield {
        "tenant_id": tenant_id, "other_tenant_id": other_tenant_id,
        "owner": owner, "staff": staff, "platform_admin": platform_admin, "other_owner": other_owner,
        "customer_token": customer_token, "employee_token": employee_token,
    }
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_ec12_types_validation_preview_and_no_second_template_engine(ctx):
    before_collections = set(await db.list_collection_names())
    valid_types = [
        "task", "task_checklist", "appointment", "appointment_confirmation", "appointment_reminder",
        "message", "announcement", "note", "daily_digest", "email", "sms", "support_response",
        "bug_response", "feature_request_response", "time_off_response",
    ]
    async with await _client_as(ctx["owner"]) as c:
        for template_type in valid_types:
            created = await c.post("/api/templates", json={
                "name": f"{template_type} template", "template_type": template_type,
                "body": {"channels": {"in_app": "Hello {{customer_name}} from {{shop_name}}"}},
            })
            assert created.status_code == 201, created.text
            assert created.json()["channels"] == ["in_app"]
            assert set(created.json()["placeholders"]) == {"customer_name", "shop_name"}
        unknown_type = await c.post("/api/templates", json={"name": "Bad", "template_type": "random", "body": {}})
        assert unknown_type.status_code == 400
        unknown_placeholder = await c.post("/api/templates/validate", json={
            "template_type": "message", "body": {"channels": {"in_app": "Hi {{unknown_value}}"}},
        })
        assert unknown_placeholder.status_code == 200
        assert unknown_placeholder.json()["valid"] is False
        unsafe = await c.post("/api/templates", json={
            "name": "Unsafe", "template_type": "message", "body": {"channels": {"in_app": "Authorization: Bearer abc"}},
        })
        assert unsafe.status_code == 400
        long_sms = await c.post("/api/templates", json={
            "name": "Long SMS", "template_type": "sms", "body": {"channels": {"sms_body": "x" * 321}},
        })
        assert long_sms.status_code == 400
        rendered = await c.post(f"/api/templates/{created.json()['id']}/preview", json={"context": {"customer_name": "Wrap Co", "shop_name": "Main Shop"}})
        assert rendered.status_code == 200
        assert rendered.json()["rendered"]["in_app"] == "Hello Wrap Co from Main Shop"
        applied = await c.post(f"/api/templates/{created.json()['id']}/apply", json={"target_type": "message", "context": {"customer_name": "Wrap Co"}})
        assert applied.status_code == 200
        assert applied.json()["mutated"] is False
        assert applied.json()["sent"] is False

    after_collections = set(await db.list_collection_names())
    assert "template_definitions" in after_collections
    assert "template_packs" in after_collections
    assert "task_templates" not in after_collections - before_collections
    assert "message_templates" not in after_collections - before_collections
    assert "support_templates" not in after_collections - before_collections


@pytest.mark.asyncio
async def test_platform_master_tenant_copy_source_updates_and_starter_pack(ctx):
    before = {
        "feature_entitlements": await db.feature_entitlements.count_documents({"tenant_id": ctx["tenant_id"]}),
        "subscriptions": await db.subscriptions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "billing": await db.get_collection("billing_records").count_documents({"tenant_id": ctx["tenant_id"]}),
        "sms": await db.get_collection("sms_messages").count_documents({"tenant_id": ctx["tenant_id"]}),
        "email_logs": await db.email_logs.count_documents({"tenant_id": ctx["tenant_id"]}),
        "onboarding_tasks": await db.onboarding_tasks.count_documents({"tenant_id": ctx["tenant_id"]}),
    }

    async with await _client_as(ctx["platform_admin"]) as platform:
        master = await platform.post("/api/templates/platform-masters", json={
            "name": "Platform appointment confirmation",
            "template_type": "appointment_confirmation",
            "starter_template": True,
            "pack_id": "starter_ec12_productivity",
            "body": {"channels": {"email_subject": "Appointment with {{shop_name}}", "email_body": "Hi {{customer_name}}, see you {{appointment_date}}."}},
        })
        assert master.status_code == 201, master.text
        assert master.json()["owner_scope"] == "platform"
        assert master.json()["version"] == 1

    async with await _client_as(ctx["owner"]) as owner:
        listed = await owner.get("/api/templates", params={"template_type": "appointment_confirmation"})
        assert master.json()["id"] in {t["id"] for t in listed.json()["items"]}
        edit_denied = await owner.patch(f"/api/templates/{master.json()['id']}", json={"name": "Tenant edit"})
        archive_denied = await owner.post(f"/api/templates/{master.json()['id']}/archive")
        assert edit_denied.status_code == 404
        assert archive_denied.status_code == 404
        installed = await owner.post(f"/api/templates/starter/{master.json()['id']}/install")
        assert installed.status_code == 201, installed.text
        copy = installed.json()
        assert copy["tenant_id"] == ctx["tenant_id"]
        assert copy["owner_scope"] == "tenant"
        assert copy["source_template_id"] == master.json()["id"]
        assert copy["source_template_version"] == 1
        assert copy["tenant_modified"] is False
        edited = await owner.patch(f"/api/templates/{copy['id']}", json={"body": {"channels": {"email_subject": "Edited {{shop_name}}", "email_body": "Tenant copy changed."}}})
        assert edited.status_code == 200, edited.text
        assert edited.json()["tenant_modified"] is True

    async with await _client_as(ctx["platform_admin"]) as platform:
        updated_master = await platform.patch(f"/api/templates/platform-masters/{master.json()['id']}", json={
            "body": {"channels": {"email_subject": "New source {{shop_name}}", "email_body": "New master body for {{customer_name}}."}},
        })
        assert updated_master.status_code == 200, updated_master.text
        assert updated_master.json()["version"] == 2
        deactivated = await platform.patch(f"/api/templates/platform-masters/{master.json()['id']}", json={"active": False, "source_status": "deprecated"})
        assert deactivated.status_code == 200

    async with await _client_as(ctx["owner"]) as owner:
        comparison = await owner.get(f"/api/templates/{copy['id']}/source-comparison")
        assert comparison.status_code == 200
        assert comparison.json()["update_available"] is True
        fetched_copy = await owner.get(f"/api/templates/{copy['id']}")
        assert fetched_copy.status_code == 200
        assert fetched_copy.json()["body"]["channels"]["email_subject"] == "Edited {{shop_name}}"
        duplicate = await owner.post(f"/api/templates/{copy['id']}/duplicate")
        assert duplicate.status_code == 201
        assert duplicate.json()["id"] != copy["id"]
        archived = await owner.post(f"/api/templates/{copy['id']}/archive")
        restored = await owner.post(f"/api/templates/{copy['id']}/restore")
        assert archived.status_code == 200
        assert restored.status_code == 200
        pack_1 = await owner.post("/api/templates/packs/starter/install")
        pack_2 = await owner.post("/api/templates/packs/starter/install")
        assert pack_1.status_code == 200, pack_1.text
        assert pack_2.status_code == 200, pack_2.text
        assert pack_1.json()["installed_count"] == pack_2.json()["installed_count"]
        pack_list = await owner.get("/api/templates/packs/list")
        assert pack_list.status_code == 200
        pack = pack_list.json()["items"][0]
        assert pack["starter_pack"] is True
        assert pack["premium_reserved"] is False

    after = {
        "feature_entitlements": await db.feature_entitlements.count_documents({"tenant_id": ctx["tenant_id"]}),
        "subscriptions": await db.subscriptions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "billing": await db.get_collection("billing_records").count_documents({"tenant_id": ctx["tenant_id"]}),
        "sms": await db.get_collection("sms_messages").count_documents({"tenant_id": ctx["tenant_id"]}),
        "email_logs": await db.email_logs.count_documents({"tenant_id": ctx["tenant_id"]}),
        "onboarding_tasks": await db.onboarding_tasks.count_documents({"tenant_id": ctx["tenant_id"]}),
    }
    assert after == before


@pytest.mark.asyncio
async def test_template_security_portal_denial_and_ec12_render_integrations(ctx):
    async with await _client_as(ctx["owner"]) as owner:
        task = await owner.post("/api/templates", json={"name": "Task", "template_type": "task", "body": {"channels": {"task_title": "Call {{customer_name}}", "task_description": "Due {{due_date}}"}}})
        appointment = await owner.post("/api/templates", json={"name": "Appointment", "template_type": "appointment_confirmation", "body": {"channels": {"email_body": "Appointment {{appointment_date}} at {{appointment_time}}"}}})
        message = await owner.post("/api/templates", json={"name": "Message", "template_type": "message", "body": {"channels": {"in_app": "Message {{contact_name}}"}}})
        announcement = await owner.post("/api/templates", json={"name": "Announcement", "template_type": "announcement", "body": {"channels": {"announcement_body": "Notice for {{shop_name}}"}}})
        digest = await owner.post("/api/templates", json={"name": "Digest", "template_type": "daily_digest", "body": {"channels": {"digest_section": "Digest due {{due_date}}"}}})
        support = await owner.post("/api/templates", json={"name": "Support", "template_type": "support_response", "body": {"channels": {"in_app": "Support {{support_request_number}}"}}})
        bug = await owner.post("/api/templates", json={"name": "Bug", "template_type": "bug_response", "body": {"channels": {"in_app": "Bug {{bug_report_title}}"}}})
        feature = await owner.post("/api/templates", json={"name": "Feature", "template_type": "feature_request_response", "body": {"channels": {"in_app": "Feature {{feature_request_title}}"}}})
        time_off = await owner.post("/api/templates", json={"name": "Time off", "template_type": "time_off_response", "body": {"channels": {"in_app": "Time off {{employee_name}}"}}})
        for resp in [task, appointment, message, announcement, digest, support, bug, feature, time_off]:
            assert resp.status_code == 201, resp.text
            rendered = await owner.post(f"/api/templates/{resp.json()['id']}/apply", json={
                "target_type": resp.json()["template_type"],
                "context": {"customer_name": "Acme", "shop_name": "Main", "support_request_number": "SUP-1"},
            })
            assert rendered.status_code == 200
            assert rendered.json()["mutated"] is False
            assert rendered.json()["sent"] is False

    async with await _client_as(ctx["other_owner"]) as other:
        isolated = await other.get(f"/api/templates/{task.json()['id']}")
        assert isolated.status_code == 404

    async with await _token_client(ctx["customer_token"]) as customer:
        denied = await customer.get("/api/templates")
        assert denied.status_code in {401, 403}

    async with await _token_client(ctx["employee_token"]) as employee:
        denied = await employee.get("/api/templates")
        assert denied.status_code in {401, 403}
