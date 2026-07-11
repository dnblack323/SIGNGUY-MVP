"""EC2 — Activity service tests (envelope + audit linkage)."""
from __future__ import annotations

import pytest

from app.core.db import db
from app.services.activity import record_activity, record_activity_with_audit


@pytest.mark.asyncio
async def test_record_activity_persists(seeded_users):
    t = seeded_users["tenant_a"]["id"]
    evt = await record_activity(
        tenant_id=t, module="orders", action="order.created",
        summary="Order #1 created", entity_type="order", entity_id="ord-1",
        severity="success",
    )
    doc = await db.activity_events.find_one({"id": evt.id}, {"_id": 0})
    assert doc is not None
    assert doc["tenant_id"] == t
    assert doc["severity"] == "success"


@pytest.mark.asyncio
async def test_record_activity_with_audit_writes_both(seeded_users):
    t = seeded_users["tenant_a"]["id"]
    audit_id, activity = await record_activity_with_audit(
        tenant_id=t,
        actor_user_id="u1",
        actor_email="u1@example.com",
        module="invoices",
        action="invoice.paid",
        entity_type="invoice",
        entity_id="inv-1",
        summary="Invoice inv-1 paid",
        severity="success",
    )
    # Both rows must exist and be linked
    audit_doc = await db.audit_events.find_one({"id": audit_id}, {"_id": 0})
    activity_doc = await db.activity_events.find_one({"id": activity.id}, {"_id": 0})
    assert audit_doc is not None
    assert activity_doc is not None
    assert activity_doc["audit_event_id"] == audit_id
