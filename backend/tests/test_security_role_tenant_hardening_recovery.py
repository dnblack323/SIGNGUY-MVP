"""Security role and tenant-hardening recovery checkpoint tests."""
from __future__ import annotations

from copy import deepcopy
import uuid

from pymongo.errors import DuplicateKeyError
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.permissions import (
    PLATFORM_CREATOR_ROLE,
    PlatformPerm,
    has_platform_admin_access,
    is_platform_creator_user,
    permissions_for_role,
)
from app.deps import get_current_user
from app.services import platform_creator as pc_service
from app.services.platform_creator import (
    PlatformCreatorError,
    assign_platform_creator_by_email,
    normalize_email,
    remove_platform_creator_by_email,
)
from scripts import bootstrap_platform_creator as bootstrap
from server import app


def _override(user: dict):
    async def _get():
        return {**user}

    return _get


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest_asyncio.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"security-recovery-{suffix}"
    other_tenant_id = f"security-recovery-other-{suffix}"
    tenant = {"id": tenant_id, "slug": tenant_id, "name": "Security Recovery"}
    other_tenant = {"id": other_tenant_id, "slug": other_tenant_id, "name": "Other Security Recovery"}
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "full_name": "Owner", "role": "owner", "is_active": True}
    staff = {"id": f"staff-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "full_name": "Staff", "role": "staff", "is_active": True}
    other_owner = {"id": f"other-owner-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "full_name": "Other Owner", "role": "owner", "is_active": True}
    platform_admin = {
        "id": f"platform-admin-{suffix}",
        "tenant_id": tenant_id,
        "email": f"platform-admin-{suffix}@example.com",
        "full_name": "Platform Admin",
        "role": "staff",
        "is_active": True,
        "platform_admin": True,
    }
    creator_target = {
        "id": f"creator-target-{suffix}",
        "tenant_id": tenant_id,
        "email": f"TheSigntistsLab.{suffix}@gmail.com",
        "full_name": "Creator Target",
        "role": "owner",
        "is_active": True,
    }
    await db.tenants.insert_many([tenant, other_tenant])
    await db.users.insert_many([owner, staff, other_owner, platform_admin, creator_target])
    yield {
        "suffix": suffix,
        "tenant_id": tenant_id,
        "other_tenant_id": other_tenant_id,
        "owner": owner,
        "staff": staff,
        "other_owner": other_owner,
        "platform_admin": platform_admin,
        "creator_target": creator_target,
    }
    app.dependency_overrides.pop(get_current_user, None)


def _valid_registration_payload(suffix: str) -> dict:
    return {
        "tenant_name": f"Registration {suffix}",
        "tenant_slug": f"registration-{suffix}",
        "owner_email": f"registration-{suffix}@example.com",
        "owner_full_name": "Registration Owner",
        "owner_password": "long-enough-password",
    }


def _pending_for(ctx: dict, *, action: str = "platform_creator.assigned") -> dict:
    return pc_service._build_pending_audit(
        actor=ctx["platform_admin"],
        target=ctx["creator_target"],
        action=action,
        summary=f"Test {action}",
        reason="Owner-approved outbox test",
        context={"test": ctx["suffix"]},
    )


@pytest.mark.asyncio
async def test_platform_creator_role_mapping_stays_out_of_tenant_roles(ctx):
    assert PlatformPerm.PLATFORM_CREATOR.value not in permissions_for_role("owner")
    assert PlatformPerm.PLATFORM_CREATOR.value not in permissions_for_role("admin")
    assert PlatformPerm.PLATFORM_CREATOR.value not in permissions_for_role("staff")
    assert has_platform_admin_access({"platform_admin": True})
    assert has_platform_admin_access({"platform_role": "admin"})
    assert has_platform_admin_access({"permissions": [PlatformPerm.PLATFORM_ADMIN.value]})
    assert has_platform_admin_access({"platform_role": PLATFORM_CREATOR_ROLE})
    assert has_platform_admin_access({"permissions": [PlatformPerm.PLATFORM_CREATOR.value]})
    assert is_platform_creator_user({"platform_role": PLATFORM_CREATOR_ROLE})


@pytest.mark.asyncio
async def test_platform_creator_assignment_removal_are_exact_idempotent_and_audited(ctx):
    target_email = ctx["creator_target"]["email"].lower()
    assigned = await assign_platform_creator_by_email(
        actor_user=ctx["platform_admin"],
        email=f"  {target_email.upper()}  ",
        reason="Owner-approved security recovery bootstrap",
        context={"test": ctx["suffix"]},
    )
    assert assigned["changed"] is True
    user = assigned["user"]
    assert user["platform_role"] == PLATFORM_CREATOR_ROLE
    assert user["platform_admin"] is True
    assert PlatformPerm.PLATFORM_CREATOR.value in user["permissions"]
    assert PlatformPerm.PLATFORM_ADMIN.value in user["permissions"]
    assert is_platform_creator_user(user)
    assert has_platform_admin_access(user)

    repeat = await assign_platform_creator_by_email(
        actor_user=ctx["platform_admin"],
        email=target_email,
        reason="Owner-approved security recovery bootstrap",
    )
    assert repeat["changed"] is False
    assert await db.audit_events.count_documents({"action": "platform_creator.assigned", "entity_id": user["id"]}) == 1

    with pytest.raises(PlatformCreatorError) as partial:
        await assign_platform_creator_by_email(
            actor_user=ctx["platform_admin"],
            email=f"lab.{ctx['suffix']}@gmail.com",
            reason="Should not partial match",
        )
    assert partial.value.code == "target_user_not_found"

    removed = await remove_platform_creator_by_email(
        actor_user=ctx["platform_admin"],
        email=target_email,
        reason="Owner-approved removal test",
    )
    assert removed["changed"] is True
    removed_user = removed["user"]
    assert removed_user.get("platform_role") != PLATFORM_CREATOR_ROLE
    assert PlatformPerm.PLATFORM_CREATOR.value not in set(removed_user.get("permissions") or [])
    assert await db.audit_events.count_documents({"action": "platform_creator.removed", "entity_id": user["id"]}) == 1

    repeat_remove = await remove_platform_creator_by_email(
        actor_user=ctx["platform_admin"],
        email=target_email,
        reason="Owner-approved removal test",
    )
    assert repeat_remove["changed"] is False
    assert await db.audit_events.count_documents({"action": "platform_creator.removed", "entity_id": user["id"]}) == 1


@pytest.mark.asyncio
async def test_ambiguous_exact_email_assignment_and_removal_change_nothing_and_audit_nothing(ctx):
    duplicate = {
        "id": f"duplicate-creator-{ctx['suffix']}",
        "tenant_id": ctx["other_tenant_id"],
        "email": ctx["creator_target"]["email"].lower(),
        "full_name": "Duplicate Creator",
        "role": "owner",
        "is_active": True,
        "platform_role": PLATFORM_CREATOR_ROLE,
        "platform_admin": True,
        "permissions": [PlatformPerm.PLATFORM_CREATOR.value, PlatformPerm.PLATFORM_ADMIN.value],
    }
    await db.users.insert_one(duplicate)

    with pytest.raises(PlatformCreatorError) as assign_denied:
        await assign_platform_creator_by_email(
            actor_user=ctx["platform_admin"],
            email=ctx["creator_target"]["email"],
            reason="Ambiguous assign test",
        )
    assert assign_denied.value.code == "target_email_ambiguous"

    with pytest.raises(PlatformCreatorError) as remove_denied:
        await remove_platform_creator_by_email(
            actor_user=ctx["platform_admin"],
            email=ctx["creator_target"]["email"],
            reason="Ambiguous remove test",
        )
    assert remove_denied.value.code == "target_email_ambiguous"

    original = await db.users.find_one({"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})
    dup = await db.users.find_one({"id": duplicate["id"], "tenant_id": ctx["other_tenant_id"]}, {"_id": 0})
    assert original.get("platform_role") != PLATFORM_CREATOR_ROLE
    assert PlatformPerm.PLATFORM_CREATOR.value not in set(original.get("permissions") or [])
    assert dup["platform_role"] == PLATFORM_CREATOR_ROLE
    assert await db.audit_events.count_documents({"action": {"$in": ["platform_creator.assigned", "platform_creator.removed"]}, "entity_id": {"$in": [original["id"], dup["id"]]}}) == 0


@pytest.mark.asyncio
async def test_assignment_race_failure_returns_no_success_and_writes_no_audit(ctx, monkeypatch):
    original_resolver = assign_platform_creator_by_email.__globals__["_find_active_user_by_normalized_email"]

    async def resolver_then_deactivate(email: str) -> dict:
        target = await original_resolver(email)
        await db.users.update_one({"id": target["id"], "tenant_id": target["tenant_id"]}, {"$set": {"is_active": False}})
        return target

    monkeypatch.setitem(assign_platform_creator_by_email.__globals__, "_find_active_user_by_normalized_email", resolver_then_deactivate)
    with pytest.raises(PlatformCreatorError) as raced:
        await assign_platform_creator_by_email(
            actor_user=ctx["platform_admin"],
            email=ctx["creator_target"]["email"],
            reason="Race assign test",
        )
    assert raced.value.code == "target_changed"
    target = await db.users.find_one({"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})
    assert target.get("platform_role") != PLATFORM_CREATOR_ROLE
    assert await db.audit_events.count_documents({"action": "platform_creator.assigned", "entity_id": ctx["creator_target"]["id"]}) == 0


@pytest.mark.asyncio
async def test_removal_race_failure_returns_no_success_and_writes_no_audit(ctx, monkeypatch):
    assigned = await assign_platform_creator_by_email(
        actor_user=ctx["platform_admin"],
        email=ctx["creator_target"]["email"],
        reason="Setup removal race",
    )
    assert assigned["changed"] is True
    await db.audit_events.delete_many({"entity_id": ctx["creator_target"]["id"]})

    original_resolver = remove_platform_creator_by_email.__globals__["_find_active_user_by_normalized_email"]

    async def resolver_then_change_email(email: str) -> dict:
        target = await original_resolver(email)
        await db.users.update_one({"id": target["id"], "tenant_id": target["tenant_id"]}, {"$set": {"email": f"changed-{ctx['suffix']}@example.com"}})
        return target

    monkeypatch.setitem(remove_platform_creator_by_email.__globals__, "_find_active_user_by_normalized_email", resolver_then_change_email)
    with pytest.raises(PlatformCreatorError) as raced:
        await remove_platform_creator_by_email(
            actor_user=ctx["platform_admin"],
            email=ctx["creator_target"]["email"],
            reason="Race remove test",
        )
    assert raced.value.code == "target_changed"
    target = await db.users.find_one({"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})
    assert target["platform_role"] == PLATFORM_CREATOR_ROLE
    assert await db.audit_events.count_documents({"action": "platform_creator.removed", "entity_id": ctx["creator_target"]["id"]}) == 0


@pytest.mark.asyncio
async def test_audit_delivery_failure_leaves_assignment_recoverable_outbox_and_retry_audits_once(ctx, monkeypatch):
    original_insert = assign_platform_creator_by_email.__globals__["_insert_pending_audit_documents"]
    calls = {"count": 0}

    async def fail_first_audit_delivery(pending: dict) -> None:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("forced audit delivery failure")
        await original_insert(pending)

    monkeypatch.setitem(assign_platform_creator_by_email.__globals__, "_insert_pending_audit_documents", fail_first_audit_delivery)
    with pytest.raises(RuntimeError):
        await assign_platform_creator_by_email(
            actor_user=ctx["platform_admin"],
            email=ctx["creator_target"]["email"],
            reason="Audit failure assignment test",
        )

    pending_user = await db.users.find_one({"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})
    assert pending_user["platform_role"] == PLATFORM_CREATOR_ROLE
    assert pending_user["platform_creator_pending_audit"]["action"] == "platform_creator.assigned"
    assert await db.audit_events.count_documents({"action": "platform_creator.assigned", "entity_id": ctx["creator_target"]["id"]}) == 0

    retried = await assign_platform_creator_by_email(
        actor_user=ctx["platform_admin"],
        email=ctx["creator_target"]["email"],
        reason="Audit failure assignment test",
    )
    assert retried["changed"] is False
    assert retried["audit_recovered"] is True
    assert await db.audit_events.count_documents({"action": "platform_creator.assigned", "entity_id": ctx["creator_target"]["id"]}) == 1
    recovered_user = await db.users.find_one({"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})
    assert "platform_creator_pending_audit" not in recovered_user


@pytest.mark.asyncio
async def test_audit_delivery_failure_leaves_removal_recoverable_outbox_and_retry_audits_once(ctx, monkeypatch):
    assigned = await assign_platform_creator_by_email(
        actor_user=ctx["platform_admin"],
        email=ctx["creator_target"]["email"],
        reason="Setup removal audit failure",
    )
    assert assigned["changed"] is True
    await db.audit_events.delete_many({"entity_id": ctx["creator_target"]["id"]})
    await db.activity_events.delete_many({"entity_id": ctx["creator_target"]["id"]})

    original_insert = remove_platform_creator_by_email.__globals__["_insert_pending_audit_documents"]
    calls = {"count": 0}

    async def fail_first_audit_delivery(pending: dict) -> None:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("forced audit delivery failure")
        await original_insert(pending)

    monkeypatch.setitem(remove_platform_creator_by_email.__globals__, "_insert_pending_audit_documents", fail_first_audit_delivery)
    with pytest.raises(RuntimeError):
        await remove_platform_creator_by_email(
            actor_user=ctx["platform_admin"],
            email=ctx["creator_target"]["email"],
            reason="Audit failure removal test",
        )

    pending_user = await db.users.find_one({"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})
    assert not is_platform_creator_user(pending_user)
    assert pending_user["platform_creator_pending_audit"]["action"] == "platform_creator.removed"
    assert await db.audit_events.count_documents({"action": "platform_creator.removed", "entity_id": ctx["creator_target"]["id"]}) == 0

    retried = await remove_platform_creator_by_email(
        actor_user=ctx["platform_admin"],
        email=ctx["creator_target"]["email"],
        reason="Audit failure removal test",
    )
    assert retried["changed"] is False
    assert retried["audit_recovered"] is True
    assert await db.audit_events.count_documents({"action": "platform_creator.removed", "entity_id": ctx["creator_target"]["id"]}) == 1
    recovered_user = await db.users.find_one({"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})
    assert "platform_creator_pending_audit" not in recovered_user


@pytest.mark.asyncio
async def test_duplicate_event_delivery_requires_exact_audit_and_activity_contents(ctx):
    pending = _pending_for(ctx)
    await pc_service._insert_pending_audit_documents(pending)
    await pc_service._insert_pending_audit_documents(pending)
    assert await db.audit_events.count_documents({"id": pending["audit_event_id"]}) == 1
    assert await db.activity_events.count_documents({"id": pending["activity_event_id"]}) == 1

    audit = await db.audit_events.find_one({"id": pending["audit_event_id"]}, {"_id": 0})
    activity = await db.activity_events.find_one({"id": pending["activity_event_id"]}, {"_id": 0})
    assert audit["created_at"] == pending["audit_created_at"]
    assert activity["created_at"] == pending["activity_created_at"]

    conflicting_audit = _pending_for(ctx)
    await db.audit_events.insert_one(
        {
            "id": conflicting_audit["audit_event_id"],
            "tenant_id": conflicting_audit["tenant_id"],
            "actor_user_id": conflicting_audit["actor_user_id"],
            "actor_email": conflicting_audit["actor_email"],
            "action": "platform_creator.conflicting",
            "entity_type": "user",
            "entity_id": conflicting_audit["entity_id"],
            "summary": "Conflicting audit",
            "diff": {},
            "created_at": conflicting_audit["audit_created_at"],
            "updated_at": conflicting_audit["audit_updated_at"],
        }
    )
    with pytest.raises(PlatformCreatorError) as audit_conflict:
        await pc_service._insert_pending_audit_documents(conflicting_audit)
    assert audit_conflict.value.code == "audit_outbox_conflict"

    conflicting_activity = _pending_for(ctx)
    audit_only = pc_service.AuditEvent(
        id=conflicting_activity["audit_event_id"],
        created_at=pc_service._parse_pending_timestamp(conflicting_activity["audit_created_at"], "audit_created_at"),
        updated_at=pc_service._parse_pending_timestamp(conflicting_activity["audit_updated_at"], "audit_updated_at"),
        tenant_id=conflicting_activity["tenant_id"],
        actor_user_id=conflicting_activity["actor_user_id"],
        actor_email=conflicting_activity["actor_email"],
        action=conflicting_activity["action"],
        entity_type=conflicting_activity["entity_type"],
        entity_id=conflicting_activity["entity_id"],
        summary=conflicting_activity["summary"],
        diff=conflicting_activity["diff"],
    )
    await db.audit_events.insert_one(pc_service.prepare_for_mongo(audit_only.model_dump()))
    await db.activity_events.insert_one(
        {
            "id": conflicting_activity["activity_event_id"],
            "tenant_id": conflicting_activity["tenant_id"],
            "module": conflicting_activity["module"],
            "action": "platform_creator.conflicting",
            "summary": "Conflicting activity",
            "entity_type": "user",
            "entity_id": conflicting_activity["entity_id"],
            "actor_user_id": conflicting_activity["actor_user_id"],
            "actor_email": conflicting_activity["actor_email"],
            "audit_event_id": conflicting_activity["audit_event_id"],
            "severity": "info",
            "metadata": {"schema_version": 999, "outcome": "conflict"},
            "created_at": conflicting_activity["activity_created_at"],
            "updated_at": conflicting_activity["activity_updated_at"],
        }
    )
    with pytest.raises(PlatformCreatorError) as activity_conflict:
        await pc_service._insert_pending_audit_documents(conflicting_activity)
    assert activity_conflict.value.code == "audit_outbox_conflict"


@pytest.mark.asyncio
async def test_duplicate_key_without_matching_stable_id_fails_closed(ctx, monkeypatch):
    pending = _pending_for(ctx)

    class MissingDuplicateCollection:
        async def insert_one(self, _doc):
            raise DuplicateKeyError("forced duplicate without stable id")

        async def find_one(self, _query, _projection=None):
            return None

    class UnusedCollection:
        async def insert_one(self, _doc):
            raise AssertionError("activity insert should not run after audit duplicate conflict")

    fake_db = type("FakeDb", (), {"audit_events": MissingDuplicateCollection(), "activity_events": UnusedCollection()})()
    monkeypatch.setattr(pc_service, "db", fake_db)
    with pytest.raises(PlatformCreatorError) as denied:
        await pc_service._insert_pending_audit_documents(pending)
    assert denied.value.code == "audit_outbox_conflict"


@pytest.mark.asyncio
async def test_conflicting_duplicate_event_keeps_pending_outbox_intact(ctx):
    pending = _pending_for(ctx)
    await db.users.update_one(
        {"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]},
        {"$set": {"platform_creator_pending_audit": pending}},
    )
    await db.audit_events.insert_one(
        {
            "id": pending["audit_event_id"],
            "tenant_id": pending["tenant_id"],
            "actor_user_id": pending["actor_user_id"],
            "actor_email": pending["actor_email"],
            "action": "platform_creator.conflicting",
            "entity_type": pending["entity_type"],
            "entity_id": pending["entity_id"],
            "summary": "Conflicting audit",
            "diff": {},
            "created_at": pending["audit_created_at"],
            "updated_at": pending["audit_updated_at"],
        }
    )
    target = await db.users.find_one({"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})
    with pytest.raises(PlatformCreatorError) as conflict:
        await pc_service._deliver_pending_platform_creator_audit(target)
    assert conflict.value.code == "audit_outbox_conflict"
    stored = await db.users.find_one({"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})
    assert stored["platform_creator_pending_audit"] == pending


@pytest.mark.asyncio
async def test_partial_delivery_recovers_existing_audit_and_missing_activity(ctx):
    pending = _pending_for(ctx)
    await db.users.update_one(
        {"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]},
        {"$set": {"platform_creator_pending_audit": pending}},
    )
    audit_evt = pc_service.AuditEvent(
        id=pending["audit_event_id"],
        created_at=pc_service._parse_pending_timestamp(pending["audit_created_at"], "audit_created_at"),
        updated_at=pc_service._parse_pending_timestamp(pending["audit_updated_at"], "audit_updated_at"),
        tenant_id=pending["tenant_id"],
        actor_user_id=pending["actor_user_id"],
        actor_email=pending["actor_email"],
        action=pending["action"],
        entity_type=pending["entity_type"],
        entity_id=pending["entity_id"],
        summary=pending["summary"],
        diff=pending["diff"],
    )
    await db.audit_events.insert_one(pc_service.prepare_for_mongo(audit_evt.model_dump()))

    target = await db.users.find_one({"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})
    delivered, recovered = await pc_service._deliver_pending_platform_creator_audit(target)
    assert recovered is True
    assert "platform_creator_pending_audit" not in delivered
    assert await db.audit_events.count_documents({"id": pending["audit_event_id"]}) == 1
    assert await db.activity_events.count_documents({"id": pending["activity_event_id"]}) == 1


@pytest.mark.asyncio
async def test_events_delivered_before_clear_retry_clears_unchanged_outbox(ctx):
    pending = _pending_for(ctx)
    await db.users.update_one(
        {"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]},
        {"$set": {"platform_creator_pending_audit": pending}},
    )
    await pc_service._insert_pending_audit_documents(pending)
    stored = await db.users.find_one({"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})
    assert stored["platform_creator_pending_audit"] == pending

    delivered, recovered = await pc_service._deliver_pending_platform_creator_audit(stored)
    assert recovered is True
    assert "platform_creator_pending_audit" not in delivered
    assert await db.audit_events.count_documents({"id": pending["audit_event_id"]}) == 1
    assert await db.activity_events.count_documents({"id": pending["activity_event_id"]}) == 1


@pytest.mark.asyncio
async def test_stale_delivery_cannot_clear_changed_or_replaced_outbox(ctx):
    pending = _pending_for(ctx)
    replacement = deepcopy(pending)
    replacement["activity_event_id"] = str(uuid.uuid4())
    await db.users.update_one(
        {"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]},
        {"$set": {"platform_creator_pending_audit": replacement}},
    )
    stale_target = {**ctx["creator_target"], "platform_creator_pending_audit": pending}
    with pytest.raises(PlatformCreatorError) as stale:
        await pc_service._deliver_pending_platform_creator_audit(stale_target)
    assert stale.value.code == "audit_outbox_clear_failed"
    current = await db.users.find_one({"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})
    assert current["platform_creator_pending_audit"] == replacement

    same_audit_different_action = deepcopy(pending)
    same_audit_different_action["action"] = "platform_creator.removed"
    same_audit_different_action["diff"]["outcome"] = "removed"
    await db.users.update_one(
        {"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]},
        {"$set": {"platform_creator_pending_audit": same_audit_different_action}},
    )
    with pytest.raises(PlatformCreatorError):
        await pc_service._deliver_pending_platform_creator_audit(stale_target)
    current = await db.users.find_one({"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})
    assert current["platform_creator_pending_audit"] == same_audit_different_action


@pytest.mark.asyncio
async def test_same_outbox_delivery_is_idempotent_after_concurrent_clear(ctx):
    pending = _pending_for(ctx)
    await db.users.update_one(
        {"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]},
        {"$set": {"platform_creator_pending_audit": pending}},
    )
    target = await db.users.find_one({"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})
    delivered, recovered = await pc_service._deliver_pending_platform_creator_audit(target)
    assert recovered is True
    assert "platform_creator_pending_audit" not in delivered

    stale_delivery, stale_recovered = await pc_service._deliver_pending_platform_creator_audit(target)
    assert stale_recovered is True
    assert "platform_creator_pending_audit" not in stale_delivery
    assert await db.audit_events.count_documents({"id": pending["audit_event_id"]}) == 1
    assert await db.activity_events.count_documents({"id": pending["activity_event_id"]}) == 1


@pytest.mark.asyncio
async def test_pending_outbox_preserves_original_mutation_timestamps_on_retry(ctx, monkeypatch):
    original_insert = assign_platform_creator_by_email.__globals__["_insert_pending_audit_documents"]
    calls = {"count": 0}

    async def fail_first_delivery(pending: dict) -> None:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("forced timestamp delivery failure")
        await original_insert(pending)

    monkeypatch.setitem(assign_platform_creator_by_email.__globals__, "_insert_pending_audit_documents", fail_first_delivery)
    with pytest.raises(RuntimeError):
        await assign_platform_creator_by_email(
            actor_user=ctx["platform_admin"],
            email=ctx["creator_target"]["email"],
            reason="Timestamp retry test",
        )
    pending_user = await db.users.find_one({"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})
    pending = pending_user["platform_creator_pending_audit"]
    original_audit_timestamp = pending["audit_created_at"]
    original_activity_timestamp = pending["activity_created_at"]

    retried = await assign_platform_creator_by_email(
        actor_user=ctx["platform_admin"],
        email=ctx["creator_target"]["email"],
        reason="Timestamp retry test",
    )
    assert retried["audit_recovered"] is True
    audit = await db.audit_events.find_one({"id": pending["audit_event_id"]}, {"_id": 0})
    activity = await db.activity_events.find_one({"id": pending["activity_event_id"]}, {"_id": 0})
    assert audit["created_at"] == original_audit_timestamp
    assert activity["created_at"] == original_activity_timestamp


@pytest.mark.asyncio
async def test_metadata_only_assignment_race_returns_target_changed_without_audit(ctx, monkeypatch):
    original_resolver = assign_platform_creator_by_email.__globals__["_find_active_user_by_normalized_email"]

    async def resolver_then_add_metadata(email: str) -> dict:
        target = await original_resolver(email)
        await db.users.update_one(
            {"id": target["id"], "tenant_id": target["tenant_id"]},
            {"$set": {"platform_creator_assignment_reason": "concurrent metadata"}},
        )
        return target

    monkeypatch.setitem(assign_platform_creator_by_email.__globals__, "_find_active_user_by_normalized_email", resolver_then_add_metadata)
    with pytest.raises(PlatformCreatorError) as raced:
        await assign_platform_creator_by_email(
            actor_user=ctx["platform_admin"],
            email=ctx["creator_target"]["email"],
            reason="Metadata race assign test",
        )
    assert raced.value.code == "target_changed"
    target = await db.users.find_one({"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})
    assert target.get("platform_role") != PLATFORM_CREATOR_ROLE
    assert await db.audit_events.count_documents({"action": "platform_creator.assigned", "entity_id": ctx["creator_target"]["id"]}) == 0


@pytest.mark.asyncio
async def test_metadata_only_removal_race_returns_target_changed_without_audit(ctx, monkeypatch):
    assigned = await assign_platform_creator_by_email(
        actor_user=ctx["platform_admin"],
        email=ctx["creator_target"]["email"],
        reason="Setup metadata removal race",
    )
    assert assigned["changed"] is True
    await db.audit_events.delete_many({"entity_id": ctx["creator_target"]["id"]})

    original_resolver = remove_platform_creator_by_email.__globals__["_find_active_user_by_normalized_email"]

    async def resolver_then_change_metadata(email: str) -> dict:
        target = await original_resolver(email)
        await db.users.update_one(
            {"id": target["id"], "tenant_id": target["tenant_id"]},
            {"$set": {"platform_creator_assigned_by": "concurrent-platform-admin"}},
        )
        return target

    monkeypatch.setitem(remove_platform_creator_by_email.__globals__, "_find_active_user_by_normalized_email", resolver_then_change_metadata)
    with pytest.raises(PlatformCreatorError) as raced:
        await remove_platform_creator_by_email(
            actor_user=ctx["platform_admin"],
            email=ctx["creator_target"]["email"],
            reason="Metadata race remove test",
        )
    assert raced.value.code == "target_changed"
    target = await db.users.find_one({"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})
    assert target["platform_role"] == PLATFORM_CREATOR_ROLE
    assert await db.audit_events.count_documents({"action": "platform_creator.removed", "entity_id": ctx["creator_target"]["id"]}) == 0


@pytest.mark.asyncio
async def test_present_null_metadata_is_distinct_from_missing_for_assignment_and_removal(ctx, monkeypatch):
    await db.users.update_one(
        {"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]},
        {"$set": {"platform_creator_removed_at": None}},
    )
    assigned = await assign_platform_creator_by_email(
        actor_user=ctx["platform_admin"],
        email=ctx["creator_target"]["email"],
        reason="Present null assignment",
    )
    assert assigned["changed"] is True

    removed = await remove_platform_creator_by_email(
        actor_user=ctx["platform_admin"],
        email=ctx["creator_target"]["email"],
        reason="Present null removal",
    )
    assert removed["changed"] is True

    await db.users.update_one(
        {"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]},
        {
            "$unset": {
                "platform_role": "",
                "platform_creator_removed_at": "",
                "platform_creator_pending_audit": "",
            },
            "$set": {
                "platform_admin": False,
                "permissions": [],
            },
        },
    )
    original_resolver = assign_platform_creator_by_email.__globals__["_find_active_user_by_normalized_email"]

    async def resolver_then_set_null(email: str) -> dict:
        target = await original_resolver(email)
        await db.users.update_one(
            {"id": target["id"], "tenant_id": target["tenant_id"]},
            {"$set": {"platform_creator_removed_at": None}},
        )
        return target

    monkeypatch.setitem(assign_platform_creator_by_email.__globals__, "_find_active_user_by_normalized_email", resolver_then_set_null)
    with pytest.raises(PlatformCreatorError) as raced:
        await assign_platform_creator_by_email(
            actor_user=ctx["platform_admin"],
            email=ctx["creator_target"]["email"],
            reason="Missing to present-null race",
        )
    assert raced.value.code == "target_changed"


@pytest.mark.asyncio
async def test_platform_creator_reason_is_sanitized_for_user_metadata_and_audit(ctx):
    raw_reason = "x" * 600
    safe_reason = raw_reason[:500]
    assigned = await assign_platform_creator_by_email(
        actor_user=ctx["platform_admin"],
        email=ctx["creator_target"]["email"],
        reason=raw_reason,
    )
    assert assigned["changed"] is True
    user = await db.users.find_one({"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})
    audit = await db.audit_events.find_one({"action": "platform_creator.assigned", "entity_id": ctx["creator_target"]["id"]}, {"_id": 0})
    assert user["platform_creator_assignment_reason"] == safe_reason
    assert audit["diff"]["reason"] == safe_reason
    assert raw_reason not in str(user)
    assert raw_reason not in str(audit)

    with pytest.raises(PlatformCreatorError):
        await remove_platform_creator_by_email(
            actor_user=ctx["platform_admin"],
            email=ctx["creator_target"]["email"],
            reason="Bearer abcdefghijklmnopqrstuvwxyz123456",
        )
    assert await db.audit_events.count_documents({"action": "platform_creator.removed", "entity_id": ctx["creator_target"]["id"]}) == 0


@pytest.mark.asyncio
async def test_audit_context_is_sanitized_without_mutating_original_context(ctx):
    unsafe_contexts = [
        {"source": {"api_key": "sk-test-should-not-persist"}},
        {"source": {"safe_nested_key": "still not allowed"}},
        {"source": ["nested", "list"]},
        {"source": "Bearer abcdefghijklmnopqrstuvwxyz123456"},
        {"source": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abcdefghijklmnopqrstuvwxyz123456.abcdefghijklmnopqrstuvwxyz123456"},
        {"source": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----"},
        {"source": "$2b$12$abcdefghijklmnopqrstuuabcdefghijklmnopqrstuuabcdefghijklmnop"},
    ]
    for index, context in enumerate(unsafe_contexts):
        with pytest.raises(PlatformCreatorError):
            await assign_platform_creator_by_email(
                actor_user=ctx["platform_admin"],
                email=ctx["creator_target"]["email"],
                reason=f"Unsafe context {index}",
                context=context,
            )
    assert await db.audit_events.count_documents({"action": "platform_creator.assigned", "entity_id": ctx["creator_target"]["id"]}) == 0

    safe_context = {"source": "owner_review", "method": "manual_bootstrap", "ignored": "not persisted"}
    original = deepcopy(safe_context)
    assigned = await assign_platform_creator_by_email(
        actor_user=ctx["platform_admin"],
        email=ctx["creator_target"]["email"],
        reason="Owner-approved safe context",
        context=safe_context,
    )
    assert assigned["changed"] is True
    assert safe_context == original
    audit = await db.audit_events.find_one({"action": "platform_creator.assigned", "entity_id": ctx["creator_target"]["id"]}, {"_id": 0})
    assert audit["diff"]["reason"] == "Owner-approved safe context"
    assert audit["diff"]["context"] == {"source": "owner_review", "method": "manual_bootstrap"}


@pytest.mark.asyncio
async def test_tenant_owner_cannot_assign_platform_creator(ctx):
    with pytest.raises(PlatformCreatorError) as denied:
        await assign_platform_creator_by_email(
            actor_user=ctx["owner"],
            email=ctx["creator_target"]["email"],
            reason="Tenant owner attempt",
        )
    assert denied.value.status_code == 403
    target = await db.users.find_one({"id": ctx["creator_target"]["id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})
    assert target.get("platform_role") != PLATFORM_CREATOR_ROLE
    assert PlatformPerm.PLATFORM_CREATOR.value not in set(target.get("permissions") or [])


@pytest.mark.asyncio
async def test_user_routes_reject_platform_fields_and_prevent_cross_tenant_update(ctx):
    async with await _client_as(ctx["owner"]) as client:
        denied_update = await client.patch(
            f"/api/users/{ctx['staff']['id']}",
            json={
                "platform_role": PLATFORM_CREATOR_ROLE,
                "platform_admin": True,
                "permissions": [PlatformPerm.PLATFORM_CREATOR.value],
                "platform_creator_pending_audit": {"audit_event_id": "forbidden"},
            },
        )
        assert denied_update.status_code == 422

        denied_create = await client.post(
            "/api/users",
            json={
                "email": f"new-{ctx['suffix']}@example.com",
                "full_name": "New Staff",
                "role": "staff",
                "password": "long-enough-password",
                "platform_role": PLATFORM_CREATOR_ROLE,
            },
        )
        assert denied_create.status_code == 422

        cross_tenant = await client.patch(
            f"/api/users/{ctx['other_owner']['id']}",
            json={"full_name": "Cross Tenant Mutation"},
        )
        assert cross_tenant.status_code == 404

        allowed = await client.patch(f"/api/users/{ctx['staff']['id']}", json={"full_name": "Updated Staff"})
        assert allowed.status_code == 200, allowed.text
        body = allowed.json()
        assert body["id"] == ctx["staff"]["id"]
        assert body["tenant_id"] == ctx["tenant_id"]

    other = await db.users.find_one({"id": ctx["other_owner"]["id"], "tenant_id": ctx["other_tenant_id"]}, {"_id": 0})
    assert other["full_name"] != "Cross Tenant Mutation"


@pytest.mark.asyncio
async def test_external_user_responses_hide_pending_outbox_and_password_hash(ctx):
    pending = pc_service._build_pending_audit(
        actor=ctx["platform_admin"],
        target=ctx["staff"],
        action="platform_creator.assigned",
        summary="Hidden pending outbox test",
        reason="Owner-approved hidden outbox test",
        context={"test": ctx["suffix"]},
    )
    await db.users.update_one(
        {"id": ctx["staff"]["id"], "tenant_id": ctx["tenant_id"]},
        {"$set": {"platform_creator_pending_audit": pending, "password_hash": "secret-hash"}},
    )

    async with await _client_as(ctx["owner"]) as client:
        listed = await client.get("/api/users")
        assert listed.status_code == 200, listed.text
        listed_staff = next(item for item in listed.json() if item["id"] == ctx["staff"]["id"])
        assert "platform_creator_pending_audit" not in listed_staff
        assert "password_hash" not in listed_staff

        updated = await client.patch(f"/api/users/{ctx['staff']['id']}", json={"full_name": "Still Hidden"})
        assert updated.status_code == 200, updated.text
        assert "platform_creator_pending_audit" not in updated.json()
        assert "password_hash" not in updated.json()

    auth_user = {**ctx["staff"], "platform_creator_pending_audit": pending, "password_hash": "secret-hash"}
    async with await _client_as(auth_user) as client:
        me = await client.get("/api/auth/me")
        assert me.status_code == 200, me.text
        assert "platform_creator_pending_audit" not in me.json()["user"]
        assert "password_hash" not in me.json()["user"]

    stored = await db.users.find_one({"id": ctx["staff"]["id"], "tenant_id": ctx["tenant_id"]}, {"_id": 0})
    assert stored["platform_creator_pending_audit"] == pending
    delivered, recovered = await pc_service._deliver_pending_platform_creator_audit(stored)
    assert recovered is True
    assert "platform_creator_pending_audit" not in delivered


def test_bootstrap_requires_explicit_email_reason_guard_and_matching_confirmation(monkeypatch):
    monkeypatch.setenv("PLATFORM_CREATOR_BOOTSTRAP_EMAIL", "stale@example.com")
    monkeypatch.setenv("ALLOW_PLATFORM_CREATOR_BOOTSTRAP", "true")

    monkeypatch.setattr("sys.argv", ["bootstrap_platform_creator.py", "assign", "--confirm-email", "stale@example.com", "--reason", "Owner approval"])
    with pytest.raises(SystemExit):
        bootstrap._parse_args()

    monkeypatch.setattr("sys.argv", ["bootstrap_platform_creator.py", "assign", "--email", "target@example.com", "--reason", "Owner approval"])
    with pytest.raises(SystemExit):
        bootstrap._parse_args()


@pytest.mark.asyncio
async def test_bootstrap_rejects_blank_invalid_and_mismatched_email(monkeypatch):
    monkeypatch.setenv("ALLOW_PLATFORM_CREATOR_BOOTSTRAP", "true")
    for email, confirm in [
        ("", ""),
        ("not-an-email", "not-an-email"),
        ("a@", "a@"),
        ("@example.com", "@example.com"),
        ("a@@example.com", "a@@example.com"),
        ("a @example.com", "a @example.com"),
        ("target@example.com", "other@example.com"),
    ]:
        monkeypatch.setattr(
            "sys.argv",
            ["bootstrap_platform_creator.py", "assign", "--email", email, "--confirm-email", confirm, "--reason", "Owner approval"],
        )
        assert await bootstrap._run() == 2


def test_platform_creator_normalize_email_rejects_malformed_values():
    assert normalize_email(" Valid.User@Example.com ") == "valid.user@example.com"
    for value in ("", "not-an-email", "a@", "@example.com", "a@@example.com", "a @example.com", "a@\nexample.com"):
        with pytest.raises(PlatformCreatorError):
            normalize_email(value)


@pytest.mark.asyncio
async def test_bootstrap_environment_email_cannot_override_explicit_email(monkeypatch):
    captured: dict[str, str] = {}

    async def fake_assign(**kwargs):
        captured["email"] = kwargs["email"]
        return {"changed": False}

    monkeypatch.setenv("ALLOW_PLATFORM_CREATOR_BOOTSTRAP", "true")
    monkeypatch.setenv("PLATFORM_CREATOR_BOOTSTRAP_EMAIL", "stale@example.com")
    monkeypatch.setattr(bootstrap, "assign_platform_creator_by_email", fake_assign)
    monkeypatch.setattr(
        "sys.argv",
        [
            "bootstrap_platform_creator.py",
            "assign",
            "--email",
            " Explicit@Example.com ",
            "--confirm-email",
            "explicit@example.com",
            "--reason",
            "Owner approval",
        ],
    )
    assert await bootstrap._run() == 0
    assert captured["email"] == "explicit@example.com"


@pytest.mark.asyncio
async def test_registration_rejects_unknown_and_platform_fields_while_valid_payload_still_succeeds(ctx):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        platform_payload = _valid_registration_payload(f"platform-{ctx['suffix']}")
        platform_payload.update(
            {
                "platform_role": PLATFORM_CREATOR_ROLE,
                "platform_admin": True,
                "platform_permissions": [PlatformPerm.PLATFORM_CREATOR.value],
                "PLATFORM_CREATOR": True,
                "permissions": [PlatformPerm.PLATFORM_ADMIN.value],
            }
        )
        denied = await client.post("/api/auth/register-tenant", json=platform_payload)
        assert denied.status_code == 422

        unknown_payload = _valid_registration_payload(f"unknown-{ctx['suffix']}")
        unknown_payload["unexpected"] = "field"
        unknown = await client.post("/api/auth/register-tenant", json=unknown_payload)
        assert unknown.status_code == 422

        valid = await client.post("/api/auth/register-tenant", json=_valid_registration_payload(f"valid-{ctx['suffix']}"))
        assert valid.status_code == 201, valid.text
        body = valid.json()
        assert body["user"]["role"] == "owner"
        assert body["tenant"]["slug"] == f"registration-valid-{ctx['suffix']}"
