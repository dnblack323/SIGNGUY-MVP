"""Focused Stage 8E Webstore lifecycle and historical confirmation tests."""
from __future__ import annotations

import uuid

import pytest

from app.core.db import db, ensure_indexes
from app.services import webstores as svc
from app.services.webstores import WebstoreError


def _user(tenant_id: str) -> dict:
    return {
        "id": "stage8e-staff",
        "tenant_id": tenant_id,
        "role": "owner",
        "email": "stage8e@example.com",
    }


async def _seed_store(suffix: str, *, status: str = "live") -> dict[str, str]:
    tenant_id = f"tenant-stage8e-{suffix}"
    webstore_id = f"webstore-stage8e-{suffix}"
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "Stage 8E Shop"})
    await db.webstores.insert_one(
        {
            "id": webstore_id,
            "tenant_id": tenant_id,
            "slug": f"stage8e-{suffix}",
            "public_slug": f"stage8e-public-{suffix}",
            "name": "Stage 8E Webstore",
            "status": status,
            "checkout_enabled": status == "live",
            "store_type": "general",
        }
    )
    return {"tenant_id": tenant_id, "webstore_id": webstore_id, "slug": f"stage8e-public-{suffix}"}


@pytest.mark.asyncio
async def test_close_pause_and_archive_block_checkout_but_preserve_history(monkeypatch: pytest.MonkeyPatch):
    await ensure_indexes()
    ctx = await _seed_store(uuid.uuid4().hex[:8])
    user = _user(ctx["tenant_id"])
    monkeypatch.setattr(
        svc,
        "provider_configuration_status",
        lambda *_args, **_kwargs: {
            "state": "ready",
            "label": "Ready",
            "reason": None,
            "violations": [],
            "provider_authority": True,
        },
    )

    paused = await svc.set_webstore_status(user, ctx["webstore_id"], "paused", reason="Temporary pause")
    assert paused["status"] == "paused"
    assert paused["checkout_enabled"] is False

    closed = await svc.set_webstore_status(user, ctx["webstore_id"], "closed", reason="Event ended")
    assert closed["status"] == "closed"
    with pytest.raises(WebstoreError) as checkout_error:
        await svc.create_purchase_intent(ctx["slug"], {"buyer_name": "Buyer", "buyer_email": "buyer@example.com", "line_items": []})
    assert checkout_error.value.code in {"webstore_not_live", "checkout_paused"}

    archived = await svc.set_webstore_status(user, ctx["webstore_id"], "archived", reason="History only")
    assert archived["status"] == "archived"
    active = await svc.list_webstores(user)
    assert ctx["webstore_id"] not in {item["id"] for item in active["items"]}
    archived_list = await svc.list_webstores(user, status="archived")
    assert ctx["webstore_id"] in {item["id"] for item in archived_list["items"]}


@pytest.mark.asyncio
async def test_phase6_lifecycle_route_uses_canonical_pause_and_reopen_gate(monkeypatch: pytest.MonkeyPatch):
    await ensure_indexes()
    ctx = await _seed_store(uuid.uuid4().hex[:8])
    user = _user(ctx["tenant_id"])

    async def ready_readiness(_user: dict, _webstore_id: str) -> dict:
        return {"ready": True, "gates": [], "payment_readiness": {"provider_authority": True}}

    monkeypatch.setattr(svc, "launch_readiness", ready_readiness)

    paused = await svc.transition_webstore_lifecycle(user, ctx["webstore_id"], "paused", reason="Temporarily paused")
    assert paused["webstore"]["status"] == "paused"
    assert paused["lifecycle_state"] == "paused"

    reopened = await svc.transition_webstore_lifecycle(user, ctx["webstore_id"], "live", reason="Reopened")
    assert reopened["webstore"]["status"] == "live"
    assert reopened["lifecycle_state"] == "live"


@pytest.mark.asyncio
async def test_closed_and_archived_confirmation_uses_token_and_safe_receipt_only():
    await ensure_indexes()
    suffix = uuid.uuid4().hex[:8]
    ctx = await _seed_store(suffix, status="archived")
    intent_id = f"intent-stage8e-{suffix}"
    order_id = f"order-stage8e-{suffix}"
    await db.orders.insert_one(
        {
            "id": order_id,
            "tenant_id": ctx["tenant_id"],
            "number": 8801,
            "status": "confirmed",
            "total_cents": 4200,
            "source_type": "webstore_purchase_intent",
            "source_id": intent_id,
        }
    )
    await db.webstore_purchase_intents.insert_one(
        {
            "id": intent_id,
            "tenant_id": ctx["tenant_id"],
            "webstore_id": ctx["webstore_id"],
            "public_slug": ctx["slug"],
            "confirmation_token": "token-stage8e",
            "buyer_name": "Receipt Buyer",
            "buyer_email": "receipt@example.com",
            "total_cents": 4200,
            "currency": "usd",
            "status": "paid_order_created",
            "fulfillment_status": "awaiting_production_handoff",
            "canonical_order_id": order_id,
            "provider_payment_reference": "pi-must-not-leak",
            "immutable_snapshot": {"internal_cost_cents": 999},
        }
    )

    result = await svc.public_confirmation(ctx["slug"], "token-stage8e")
    assert result["order"] == {"number": 8801, "status": "confirmed", "total_cents": 4200}
    assert result["purchase_intent"]["buyer_email"] == "receipt@example.com"
    assert "provider_payment_reference" not in str(result)
    assert "internal_cost_cents" not in str(result)
    assert order_id not in str(result)
    with pytest.raises(WebstoreError):
        await svc.public_confirmation(ctx["slug"], "wrong-token")


@pytest.mark.asyncio
async def test_relaunch_rechecks_readiness_and_records_audited_transition(monkeypatch):
    await ensure_indexes()
    ctx = await _seed_store(uuid.uuid4().hex[:8], status="closed")
    user = _user(ctx["tenant_id"])
    await db.webstores.update_one(
        {"tenant_id": ctx["tenant_id"], "id": ctx["webstore_id"]},
        {"$set": {"deadline_at": "2020-01-01T00:00:00+00:00"}},
    )
    with pytest.raises(WebstoreError) as expired:
        await svc.relaunch_webstore(user, ctx["webstore_id"])
    assert expired.value.code == "relaunch_deadline_passed"
    await db.webstores.update_one(
        {"tenant_id": ctx["tenant_id"], "id": ctx["webstore_id"]},
        {"$unset": {"deadline_at": ""}},
    )

    async def blocked_readiness(_user: dict, _webstore_id: str) -> dict:
        return {"ready": False, "gates": [{"key": "catalog", "blocking": True}]}

    monkeypatch.setattr(svc, "launch_readiness", blocked_readiness)
    with pytest.raises(WebstoreError) as blocked:
        await svc.relaunch_webstore(user, ctx["webstore_id"])
    assert blocked.value.code == "launch_gates_failed"

    async def ready_readiness(_user: dict, _webstore_id: str) -> dict:
        return {"ready": True, "gates": [], "payment_readiness": {"provider_authority": True}}

    monkeypatch.setattr(svc, "launch_readiness", ready_readiness)
    relaunched = await svc.relaunch_webstore(user, ctx["webstore_id"], reason="Current catalog reviewed")
    assert relaunched["webstore"]["status"] == "relaunch_ready"
    event = await db.webstore_lifecycle_events.find_one(
        {"tenant_id": ctx["tenant_id"], "webstore_id": ctx["webstore_id"], "to_status": "relaunch_ready"},
        {"_id": 0},
    )
    assert event["metadata"]["readiness_rechecked"] is True
