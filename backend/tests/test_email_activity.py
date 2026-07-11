"""EC2 — Email Activity dual-source tests.

`email_activity` is written both from internal outbound sends (provider='internal')
and from inbound SendGrid webhook events (provider='sendgrid'). Both must:
  - stamp tenant_id
  - be unique per (provider, provider_event_id)
"""
from __future__ import annotations

import uuid as _uuid

import pytest

from app.core.db import db
from app.services.email import record_processed_activity


@pytest.mark.asyncio
async def test_internal_processed_activity_writes_row(seeded_users):
    t = seeded_users["tenant_a"]["id"]
    log_id = f"log-{_uuid.uuid4().hex[:8]}"
    await record_processed_activity(
        tenant_id=t,
        email_log_id=log_id,
        to_email="c@example.com",
        sendgrid_message_id="sg-msg-1",
        related_entity_type="invoice",
        related_entity_id="inv-1",
        ok=True,
    )
    doc = await db.email_activity.find_one({"tenant_id": t, "email_log_id": log_id}, {"_id": 0})
    assert doc is not None
    assert doc["provider"] == "internal"
    assert doc["email_log_id"] == log_id
    assert doc["event"] == "processed"


@pytest.mark.asyncio
async def test_failed_send_records_dropped_event(seeded_users):
    t = seeded_users["tenant_a"]["id"]
    log_id = f"log-{_uuid.uuid4().hex[:8]}"
    await record_processed_activity(
        tenant_id=t,
        email_log_id=log_id,
        to_email="c@example.com",
        sendgrid_message_id=None,
        ok=False,
        error="sendgrid_not_configured",
    )
    doc = await db.email_activity.find_one({"tenant_id": t, "email_log_id": log_id}, {"_id": 0})
    assert doc is not None
    assert doc["event"] == "dropped"
    assert doc["reason"] == "sendgrid_not_configured"


@pytest.mark.asyncio
async def test_internal_activity_is_tenant_scoped(seeded_users):
    t_a = seeded_users["tenant_a"]["id"]
    t_b = seeded_users["tenant_b"]["id"]
    log_a = f"log-a-{_uuid.uuid4().hex[:8]}"
    log_b = f"log-b-{_uuid.uuid4().hex[:8]}"
    await record_processed_activity(
        tenant_id=t_a, email_log_id=log_a, to_email="a@example.com", sendgrid_message_id=None
    )
    await record_processed_activity(
        tenant_id=t_b, email_log_id=log_b, to_email="b@example.com", sendgrid_message_id=None
    )
    assert await db.email_activity.count_documents({"tenant_id": t_a, "email_log_id": log_a}) == 1
    assert await db.email_activity.count_documents({"tenant_id": t_b, "email_log_id": log_b}) == 1

