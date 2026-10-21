"""Focused real-store regressions for Phase 3 synchronization and recovery."""
import asyncio

from app.core.db import db
from app.deps import get_current_user
from app.services import task_service
from app.services.commercial_entitlements import project_entitlements_for_tenant
from app.services.webstore_next_action import compute_next_action, sync_next_action_side_effects
from app.services.webstore_next_action_recovery import reconcile_next_actions
from app.services.webstore_setup_progress import setup_progress_for_staff
from server import app
from tests.test_webstores_phase3a_stage_next_action import ctx, _staff, _request, _open_tasks, _portal  # noqa: F401


async def _after_intake(ctx):
    async with await _staff(ctx["user"]) as client:
        store = await _request(client, ctx["suffix"])
    await db.webstores.update_one({"tenant_id": ctx["tenant_id"], "id": store["id"]}, {"$set": {
        "status": "questionnaire_submitted", "information_packet.sent_count": 1,
    }})
    await db.webstore_questionnaire_submissions.insert_one({
        "id": "reviewed-" + ctx["suffix"], "tenant_id": ctx["tenant_id"], "webstore_id": store["id"],
        "status": "reviewed", "revision": 1,
    })
    await sync_next_action_side_effects(ctx["tenant_id"], store["id"])
    return store


async def test_commercial_projection_closes_stale_entitlement_tasks_and_is_tenant_scoped(ctx):
    store = await _after_intake(ctx)
    entitlement_task = (await _open_tasks(ctx["tenant_id"], store["id"]))[0]
    assert ":next:entitlement:" in entitlement_task["idempotency_key"]
    async with await _staff(ctx["outsider"]) as client:
        foreign = await _request(client, ctx["suffix"] + "-foreign")
    foreign_before = await db.webstores.find_one({"tenant_id": ctx["outsider"]["tenant_id"], "id": foreign["id"]})
    await db.commercial_entitlement_rules.insert_one({
        "id": "ws-rule-" + ctx["suffix"], "product_id": "ws-plan-" + ctx["suffix"], "feature_key": "webstores", "enabled": True,
    })
    await db.tenant_subscriptions.insert_one({
        "id": "sub-" + ctx["suffix"], "tenant_id": ctx["tenant_id"], "plan_product_id": "ws-plan-" + ctx["suffix"], "status": "active",
    })
    await project_entitlements_for_tenant(tenant_id=ctx["tenant_id"])
    tasks = await _open_tasks(ctx["tenant_id"], store["id"])
    assert all(":next:entitlement:" not in t["idempotency_key"] for t in tasks)
    completed = await db.tasks.find_one({"tenant_id": ctx["tenant_id"], "id": entitlement_task["id"]})
    assert completed["status"] == "completed" and completed["completed_at"]
    await project_entitlements_for_tenant(tenant_id=ctx["tenant_id"])
    assert [t["id"] for t in await _open_tasks(ctx["tenant_id"], store["id"])] == [t["id"] for t in tasks]
    assert await db.webstores.find_one({"tenant_id": ctx["outsider"]["tenant_id"], "id": foreign["id"]}) == foreign_before
    await db.tenant_subscriptions.update_one({"tenant_id": ctx["tenant_id"]}, {"$set": {"status": "canceled"}})
    await project_entitlements_for_tenant(tenant_id=ctx["tenant_id"])
    renewed = (await _open_tasks(ctx["tenant_id"], store["id"]))[0]
    assert ":next:entitlement:" in renewed["idempotency_key"] and renewed["id"] != completed["id"]
    assert await db.tasks.find_one({"tenant_id": ctx["tenant_id"], "id": completed["id"]}) == completed


async def test_failed_sync_retries_and_does_not_publish_a_success_snapshot(ctx, monkeypatch):
    async with await _staff(ctx["user"]) as client:
        store = await _request(client, ctx["suffix"])
    before = (await db.webstores.find_one({"tenant_id": ctx["tenant_id"], "id": store["id"]}))["next_action_snapshot"]
    await db.webstores.update_one({"tenant_id": ctx["tenant_id"], "id": store["id"]}, {"$set": {"name": "Changed during failed sync"}})
    original = task_service.create_task
    attempts = []

    async def fail(**kwargs):
        attempts.append(1)
        raise OSError("simulated task write interruption")

    monkeypatch.setattr(task_service, "create_task", fail)
    assert await sync_next_action_side_effects(ctx["tenant_id"], store["id"]) is None
    assert len(attempts) == 3
    assert (await db.webstores.find_one({"tenant_id": ctx["tenant_id"], "id": store["id"]}))["next_action_snapshot"] == before
    assert (await db.webstore_next_action_locks.find_one({"tenant_id": ctx["tenant_id"], "webstore_id": store["id"]}))["failed_at"]
    monkeypatch.setattr(task_service, "create_task", original)
    result = await reconcile_next_actions(ctx["tenant_id"])
    assert result == {"checked": 1, "recovered": 1, "pending": 0, "failed": 0}
    tasks = await _open_tasks(ctx["tenant_id"], store["id"])
    assert len(tasks) == 1 and tasks[0]["title"].startswith("Changed during failed sync:")
    assert (await reconcile_next_actions(ctx["tenant_id"]))["recovered"] == 0


async def test_transient_failure_retries_without_duplicate_tasks(ctx, monkeypatch):
    async with await _staff(ctx["user"]) as client:
        store = await _request(client, ctx["suffix"])
    original = task_service.create_task
    calls = []

    async def once(**kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise OSError("temporary")
        return await original(**kwargs)

    monkeypatch.setattr(task_service, "create_task", once)
    assert await sync_next_action_side_effects(ctx["tenant_id"], store["id"])
    assert len(calls) == 2 and len(await _open_tasks(ctx["tenant_id"], store["id"])) == 1


async def test_expired_lease_and_missing_task_recover_without_losing_completed_history(ctx):
    async with await _staff(ctx["user"]) as client:
        store = await _request(client, ctx["suffix"])
    task = (await _open_tasks(ctx["tenant_id"], store["id"]))[0]
    await task_service.transition_task(tenant_id=ctx["tenant_id"], task_id=task["id"], target="completed",
                                       actor_user_id="system", actor_email="system", system_complete=True)
    completed = await db.tasks.find_one({"tenant_id": ctx["tenant_id"], "id": task["id"]})
    await db.webstore_next_action_locks.update_one({"tenant_id": ctx["tenant_id"], "webstore_id": store["id"]},
                                                  {"$set": {"until": "2000-01-01", "owner": "interrupted-worker", "pending": True}})
    await asyncio.gather(*(reconcile_next_actions(ctx["tenant_id"]) for _ in range(4)))
    active = await _open_tasks(ctx["tenant_id"], store["id"])
    assert len(active) == 1 and active[0]["id"] != completed["id"]
    assert await db.tasks.find_one({"tenant_id": ctx["tenant_id"], "id": task["id"]}) == completed
    lock = await db.webstore_next_action_locks.find_one({"tenant_id": ctx["tenant_id"], "webstore_id": store["id"]})
    assert lock["until"] == "" and not lock.get("failed_at")


async def test_owner_turn_and_live_monitoring_close_staff_tasks_and_use_canonical_progress(ctx):
    async with await _staff(ctx["user"]) as client:
        store = await _request(client, ctx["suffix"])
        sent = await client.post(f"/api/webstores/{store['id']}/information-packet/send", json={})
    assert await _open_tasks(ctx["tenant_id"], store["id"]) == []
    assert (await compute_next_action(await db.webstores.find_one({"tenant_id": ctx["tenant_id"], "id": store["id"]})))["actor"] == "owner"
    await db.webstores.update_one({"tenant_id": ctx["tenant_id"], "id": store["id"]}, {"$set": {"status": "live"}})
    # An obsolete generated task may survive an interrupted earlier update.
    await db.tasks.update_one({"tenant_id": ctx["tenant_id"], "webstore_id": store["id"]}, {"$set": {"status": "in_progress"}})
    await reconcile_next_actions(ctx["tenant_id"])
    assert await _open_tasks(ctx["tenant_id"], store["id"]) == []
    progress = await setup_progress_for_staff(ctx["user"], store["id"])
    assert progress["setup_label"] == "Live" and all(s["status"] != "deferred" for s in progress["steps"])
    raw_token = sent.json()["questionnaire_link"].split("t=", 1)[1]
    from httpx import AsyncClient, ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as public:
        token = (await public.post("/api/portal/webstores/invitations/accept", json={"token": raw_token})).json()["token"]
    app.dependency_overrides.pop(get_current_user, None)
    async with _portal(token) as owner:
        detail = (await owner.get(f"/api/portal/webstores/{store['id']}")).json()
        progress = (await owner.get(f"/api/portal/webstores/{store['id']}/setup-progress")).json()
        assert (await owner.post("/api/webstores/reconcile-next-actions")).status_code == 401
    assert progress["setup_label"] == detail["journey"]["stage"]["label"] == "Live"
    assert progress["steps"][0]["status_label"] == detail["journey"]["next_action"]["text"] == "Your store is live."
    assert "Staff setup review" not in str(progress["steps"])


async def test_recovery_api_cannot_target_another_tenant(ctx):
    store = await _after_intake(ctx)
    before = await db.webstores.find_one({"tenant_id": ctx["tenant_id"], "id": store["id"]})
    async with await _staff(ctx["outsider"]) as client:
        response = await client.post("/api/webstores/reconcile-next-actions", json={"tenant_id": ctx["tenant_id"]})
    assert response.status_code == 200 and response.json()["checked"] == 0
    assert await db.webstores.find_one({"tenant_id": ctx["tenant_id"], "id": store["id"]}) == before


async def test_owner_packet_approval_keeps_owner_turn_and_tasks_in_step(ctx):
    from app.core.portal_security import create_portal_token
    from app.services.entitlements import _upsert_entitlement_for_tests
    from tests.test_ec14_webstores import _build_launchable_store

    async with await _staff(ctx["user"]) as client:
        built = await _build_launchable_store(client, ctx["suffix"])
        store_id = built["store"]["id"]
    await _upsert_entitlement_for_tests(tenant_id=ctx["tenant_id"], feature_key="webstores")
    app.dependency_overrides.pop(get_current_user, None)
    token = create_portal_token(portal_identity_id=built["webstore_owner"]["portal_identity_id"],
                                tenant_id=ctx["tenant_id"], portal_type="webstore_owner")
    await sync_next_action_side_effects(ctx["tenant_id"], store_id)
    async with _portal(token) as owner:
        response = await owner.post(f"/api/portal/webstores/{store_id}/launch-packets/{built['packet']['id']}/approve", json={})
        assert response.status_code == 200, response.text
        detail = (await owner.get(f"/api/portal/webstores/{store_id}")).json()
        progress = (await owner.get(f"/api/portal/webstores/{store_id}/setup-progress")).json()
    assert detail["journey"]["next_action"]["for_you"] is True
    assert detail["journey"]["next_action"]["key"] == "terms_current"
    assert progress["steps"][0]["status_label"] == detail["journey"]["next_action"]["text"]
    assert await _open_tasks(ctx["tenant_id"], store_id) == []
    stored = await db.webstores.find_one({"tenant_id": ctx["tenant_id"], "id": store_id})
    assert stored["next_action_snapshot"]["key"] == "terms_current"


async def test_active_lease_is_not_stolen_or_reported_recovered(ctx):
    from datetime import timedelta
    from app.core.time_utils import utc_now

    async with await _staff(ctx["user"]) as client:
        store = await _request(client, ctx["suffix"])
    await db.webstore_next_action_locks.update_one({"tenant_id": ctx["tenant_id"], "webstore_id": store["id"]}, {
        "$set": {"until": (utc_now() + timedelta(seconds=30)).isoformat(), "owner": "active-worker"},
    })
    result = await reconcile_next_actions(ctx["tenant_id"])
    assert result["pending"] == 1 and result["recovered"] == 0
    lock = await db.webstore_next_action_locks.find_one({"tenant_id": ctx["tenant_id"], "webstore_id": store["id"]})
    assert lock["owner"] == "active-worker" and lock["pending"] is True


async def test_provider_update_recovers_tasks_outside_webstore_routes(ctx):
    from app.services.webstore_payment_boundary import _persist_provider_result

    async with await _staff(ctx["user"]) as client:
        store = await _request(client, ctx["suffix"])
    await db.webstores.update_one({"tenant_id": ctx["tenant_id"], "id": store["id"]}, {"$set": {"status": "live"}})
    await _persist_provider_result(ctx["tenant_id"], store["id"], store, {
        "provider_mode": "test", "charges_enabled": True, "payouts_enabled": True, "requirements_currently_due": ["fixture"],
    })
    await _persist_provider_result(ctx["tenant_id"], store["id"], store, {
        "provider_mode": "test", "charges_enabled": False, "payouts_enabled": False, "requirements_currently_due": [],
    })
    assert await _open_tasks(ctx["tenant_id"], store["id"]) == []
    updated = await db.webstores.find_one({"tenant_id": ctx["tenant_id"], "id": store["id"]})
    assert updated["next_action_snapshot"]["key"] == "monitor_orders"
    assert updated["provider_charges_enabled"] is False and updated["provider_payouts_enabled"] is False
    assert updated["provider_requirements_currently_due"] == []
