"""EC12 Phase 12G - community, founders, feedback, voting, and support routing."""
from __future__ import annotations

from datetime import datetime, timezone
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
    tenant_id = f"t-12g-{suffix}"
    other_tenant_id = f"t-12g-other-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    staff = {"id": f"staff-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "role": "staff", "is_active": True}
    platform_admin = {"id": f"platform-{suffix}", "tenant_id": tenant_id, "email": f"platform-{suffix}@example.com", "role": "owner", "is_active": True, "platform_admin": True, "platform_role": "admin"}
    other_owner = {"id": f"other-owner-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": tenant_id, "name": "Tenant"},
        {"id": other_tenant_id, "slug": other_tenant_id, "name": "Other Tenant"},
    ])
    await db.users.insert_many([owner, staff, platform_admin, other_owner])
    customer_id = f"cust-{suffix}"
    order_id = f"order-{suffix}"
    await db.customers.insert_one({"id": customer_id, "tenant_id": tenant_id, "name": "Acme"})
    await db.orders.insert_one({"id": order_id, "tenant_id": tenant_id, "customer_id": customer_id, "status": "confirmed", "created_at": _now(), "updated_at": _now()})
    file_id = f"file-{suffix}"
    await db.files.insert_one({"id": file_id, "tenant_id": tenant_id, "filename": "screenshot.png", "storage_path": f"{tenant_id}/shot.png", "content_type": "image/png"})
    portal_identity = {
        "id": f"pid-{suffix}", "tenant_id": tenant_id, "portal_type": "customer",
        "customer_id": customer_id, "email": f"customer-{suffix}@example.com", "status": "active",
        "permissions": ["portal:view_quotes"], "permissions_preset": "viewer_only",
    }
    await db.portal_identities.insert_one(portal_identity)
    customer_token = create_portal_token(portal_identity_id=portal_identity["id"], tenant_id=tenant_id, portal_type="customer", customer_id=customer_id)
    yield {
        "tenant_id": tenant_id, "other_tenant_id": other_tenant_id,
        "owner": owner, "staff": staff, "platform_admin": platform_admin, "other_owner": other_owner,
        "customer_id": customer_id, "order_id": order_id, "file_id": file_id, "customer_token": customer_token,
    }
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_spaces_posts_comments_votes_moderation_and_boundaries(ctx):
    before = {
        "feature_entitlements": await db.feature_entitlements.count_documents({"tenant_id": ctx["tenant_id"]}),
        "subscriptions": await db.subscriptions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "template_definitions": await db.template_definitions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "onboarding_tasks": await db.onboarding_tasks.count_documents({"tenant_id": ctx["tenant_id"]}),
    }

    async with await _client_as(ctx["owner"]) as owner:
        tenant_space = await owner.post("/api/community/spaces", json={"scope_type": "tenant", "name": "Shop community"})
        assert tenant_space.status_code == 201, tenant_space.text
        platform_denied = await owner.post("/api/community/spaces", json={"scope_type": "platform", "name": "Platform"})
        assert platform_denied.status_code == 403

    async with await _client_as(ctx["platform_admin"]) as platform:
        platform_space = await platform.post("/api/community/spaces", json={"scope_type": "platform", "name": "Platform ideas"})
        founders_space = await platform.post("/api/community/spaces", json={"scope_type": "founders", "name": "Founders area"})
        assert platform_space.status_code == 201
        assert founders_space.status_code == 201

    async with await _client_as(ctx["staff"]) as staff:
        spaces = await staff.get("/api/community/spaces")
        assert spaces.status_code == 200
        names = {s["name"] for s in spaces.json()["items"]}
        assert {"Shop community", "Platform ideas"} <= names
        assert "Founders area" not in names
        post = await staff.post("/api/community/posts", json={
            "space_id": tenant_space.json()["id"], "title": "Printer question", "body": "What media profile works best?",
            "linked_record_type": "customer", "linked_record_id": ctx["customer_id"], "idempotency_key": "post-1",
        })
        dup_post = await staff.post("/api/community/posts", json={
            "space_id": tenant_space.json()["id"], "title": "Changed", "body": "Duplicate should not create",
            "idempotency_key": "post-1",
        })
        assert post.status_code == 201, post.text
        assert dup_post.json()["id"] == post.json()["id"]
        comment = await staff.post(f"/api/community/posts/{post.json()['id']}/comments", json={"body": "Use the Avery ICC."})
        assert comment.status_code == 201
        vote_1 = await staff.post(f"/api/community/posts/{post.json()['id']}/vote", json={"active": True})
        vote_2 = await staff.post(f"/api/community/posts/{post.json()['id']}/vote", json={"active": True})
        assert vote_1.json()["vote_count"] == 1
        assert vote_2.json()["vote_count"] == 1
        secret_like = await staff.post("/api/community/posts", json={"space_id": tenant_space.json()["id"], "title": "Bad", "body": "Authorization: Bearer abc"})
        assert secret_like.status_code == 400

    async with await _client_as(ctx["other_owner"]) as other:
        hidden = await other.get("/api/community/posts", params={"space_id": tenant_space.json()["id"]})
        assert hidden.status_code == 404

    async with await _client_as(ctx["owner"]) as owner:
        moderated = await owner.post(f"/api/community/posts/{post.json()['id']}/moderate", json={"action": "pin", "reason": "Useful"})
        assert moderated.status_code == 200
        assert moderated.json()["pinned"] is True
        disabled = await owner.patch(f"/api/community/spaces/{tenant_space.json()['id']}", json={"voting_enabled": False})
        assert disabled.status_code == 200

    async with await _client_as(ctx["staff"]) as staff:
        blocked_vote = await staff.post(f"/api/community/posts/{post.json()['id']}/vote", json={"active": False})
        assert blocked_vote.status_code == 409
        founder_denied = await staff.post("/api/community/posts", json={"space_id": founders_space.json()["id"], "title": "Founder", "body": "No access yet"})
        assert founder_denied.status_code == 403

    async with await _client_as(ctx["platform_admin"]) as platform:
        grant = await platform.post("/api/community/founders/grants", json={"user_id": ctx["staff"]["id"], "tenant_id": ctx["tenant_id"], "reason": "founding tenant"})
        assert grant.status_code == 201, grant.text

    async with await _client_as(ctx["staff"]) as staff:
        founder_spaces = await staff.get("/api/community/spaces")
        assert "Founders area" in {s["name"] for s in founder_spaces.json()["items"]}

    async with await _token_client(ctx["customer_token"]) as portal:
        denied = await portal.get("/api/community/posts")
        assert denied.status_code in {401, 403}

    after = {
        "feature_entitlements": await db.feature_entitlements.count_documents({"tenant_id": ctx["tenant_id"]}),
        "subscriptions": await db.subscriptions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "template_definitions": await db.template_definitions.count_documents({"tenant_id": ctx["tenant_id"]}),
        "onboarding_tasks": await db.onboarding_tasks.count_documents({"tenant_id": ctx["tenant_id"]}),
    }
    assert after == before


@pytest.mark.asyncio
async def test_feature_requests_bug_reports_votes_and_platform_status_controls(ctx):
    async with await _client_as(ctx["staff"]) as staff:
        feature_a = await staff.post("/api/community/feature-requests", json={"title": "Batch reminders", "description": "Let shops schedule reminder nudges.", "idempotency_key": "feature-a"})
        feature_a_dup = await staff.post("/api/community/feature-requests", json={"title": "Changed", "description": "Duplicate", "idempotency_key": "feature-a"})
        feature_b = await staff.post("/api/community/feature-requests", json={"title": "Reminder sequences", "description": "Another version of the same idea."})
        assert feature_a.status_code == 201, feature_a.text
        assert feature_a_dup.json()["id"] == feature_a.json()["id"]
        assert feature_b.status_code == 201
        vote = await staff.post(f"/api/community/feature-requests/{feature_a.json()['id']}/vote", json={"active": True})
        assert vote.status_code == 200
        assert vote.json()["vote_count"] == 1
        bug = await staff.post("/api/community/bug-reports", json={
            "title": "Board filter resets", "description": "The filter resets after a refresh.",
            "severity": "medium", "attachment_file_ids": [ctx["file_id"]],
            "browser_metadata": {"user_agent": "pytest", "authorization": "Bearer secret", "screen": "1440x900"},
            "idempotency_key": "bug-a",
        })
        bug_dup = await staff.post("/api/community/bug-reports", json={"title": "Changed", "description": "Duplicate", "idempotency_key": "bug-a"})
        assert bug.status_code == 201, bug.text
        assert bug_dup.json()["id"] == bug.json()["id"]
        assert "authorization" not in bug.text.lower()
        status_denied = await staff.patch(f"/api/community/feature-requests/{feature_a.json()['id']}/status", json={"status": "planned"})
        assert status_denied.status_code == 403

    async with await _client_as(ctx["platform_admin"]) as platform:
        status = await platform.patch(f"/api/community/feature-requests/{feature_a.json()['id']}/status", json={"status": "planned", "staff_response": "Queued for review"})
        assert status.status_code == 200, status.text
        assert status.json()["status"] == "planned"
        marked_duplicate = await platform.post(f"/api/community/feature-requests/{feature_b.json()['id']}/duplicate", json={"duplicate_of_request_id": feature_a.json()["id"]})
        assert marked_duplicate.status_code == 200, marked_duplicate.text
        assert marked_duplicate.json()["status"] == "duplicate"
        assert await db.community_votes.count_documents({"record_type": "feature_request", "record_id": feature_a.json()["id"], "active": True}) == 1
        bug_status = await platform.patch(f"/api/community/bug-reports/{bug.json()['id']}/status", json={"status": "confirmed", "staff_response": "Reproduced"})
        assert bug_status.status_code == 200
        assert bug_status.json()["status"] == "confirmed"
        second_bug = await platform.post("/api/community/bug-reports", json={"title": "Same board reset", "description": "Duplicate bug"})
        bug_duplicate = await platform.post(f"/api/community/bug-reports/{second_bug.json()['id']}/duplicate", json={"duplicate_of_bug_id": bug.json()["id"]})
        assert bug_duplicate.status_code == 200
        assert bug_duplicate.json()["status"] == "duplicate"


@pytest.mark.asyncio
async def test_support_routing_visibility_internal_notes_and_notifications(ctx):
    async with await _client_as(ctx["staff"]) as staff:
        tenant_route = await staff.get("/api/community/support/route-preview", params={"request_type": "shop_configuration_question"})
        platform_route = await staff.get("/api/community/support/route-preview", params={"request_type": "product_bug"})
        assert tenant_route.json()["destination_type"] == "tenant_admin"
        assert platform_route.json()["destination_type"] == "platform_admin"
        wrong_destination = await staff.post("/api/community/support", json={
            "request_type": "product_bug", "destination_type": "tenant_admin",
            "subject": "Bug", "description": "This should route to the platform.",
        })
        assert wrong_destination.status_code == 400
        tenant_ticket = await staff.post("/api/community/support", json={
            "request_type": "shop_configuration_question", "subject": "Need setup help",
            "description": "How should we configure teams?", "linked_customer_id": ctx["customer_id"], "idempotency_key": "support-tenant",
        })
        tenant_ticket_dup = await staff.post("/api/community/support", json={
            "request_type": "shop_configuration_question", "subject": "Changed",
            "description": "Duplicate", "idempotency_key": "support-tenant",
        })
        platform_ticket = await staff.post("/api/community/support", json={
            "request_type": "product_bug", "subject": "Upload failure",
            "description": "Uploads fail for larger files.", "idempotency_key": "support-platform",
        })
        assert tenant_ticket.status_code == 201, tenant_ticket.text
        assert tenant_ticket_dup.json()["id"] == tenant_ticket.json()["id"]
        assert platform_ticket.status_code == 201, platform_ticket.text
        assert tenant_ticket.json()["destination_type"] == "tenant_admin"
        assert platform_ticket.json()["destination_type"] == "platform_admin"
        update_denied = await staff.patch(f"/api/community/support/{tenant_ticket.json()['id']}", json={"status": "acknowledged"})
        assert update_denied.status_code == 403

    async with await _client_as(ctx["owner"]) as owner:
        visible = await owner.get("/api/community/support")
        ids = {t["id"] for t in visible.json()["items"]}
        assert tenant_ticket.json()["id"] in ids
        assert platform_ticket.json()["id"] not in ids
        note = await owner.post(f"/api/community/support/{tenant_ticket.json()['id']}/notes", json={"body": "Tenant admin internal note"})
        assert note.status_code == 201, note.text
        with_notes = await owner.get(f"/api/community/support/{tenant_ticket.json()['id']}", params={"include_internal_notes": True})
        assert len(with_notes.json()["internal_notes"]) == 1
        tenant_resolved = await owner.patch(f"/api/community/support/{tenant_ticket.json()['id']}", json={"status": "resolved"})
        assert tenant_resolved.status_code == 200
        assert tenant_resolved.json()["closed_at"]

    async with await _client_as(ctx["platform_admin"]) as platform:
        all_support = await platform.get("/api/community/support")
        assert platform_ticket.json()["id"] in {t["id"] for t in all_support.json()["items"]}
        platform_note = await platform.post(f"/api/community/support/{platform_ticket.json()['id']}/notes", json={"body": "Platform internal note"})
        assert platform_note.status_code == 201
        platform_view = await platform.get(f"/api/community/support/{platform_ticket.json()['id']}", params={"include_internal_notes": True})
        assert len(platform_view.json()["internal_notes"]) == 1
        platform_update = await platform.patch(f"/api/community/support/{platform_ticket.json()['id']}", json={"status": "acknowledged", "priority": "high"})
        assert platform_update.status_code == 200
        assert platform_update.json()["priority"] == "high"

    async with await _client_as(ctx["other_owner"]) as other:
        hidden = await other.get(f"/api/community/support/{tenant_ticket.json()['id']}")
        assert hidden.status_code == 404

    assert await db.notifications.count_documents({"module": "community"}) >= 1
