"""EC2 — SendGrid webhook signature + processing tests.

Uses a test-only shared secret. Live route enablement stays disabled by config.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest

from app.services.sendgrid_webhook import process_events, verify_signature


TEST_SECRET = "unit-test-webhook-secret-do-not-ship"


def _sign(secret: str, body: bytes, ts: str) -> str:
    mac = hmac.new(secret.encode(), ts.encode() + body, hashlib.sha256).digest()
    return base64.b64encode(mac).decode()


def test_verify_signature_accepts_correct_signature():
    ts = str(int(time.time()))
    body = b'[{"event":"delivered","sg_event_id":"abc"}]'
    sig = _sign(TEST_SECRET, body, ts)
    assert verify_signature(secret=TEST_SECRET, signature_header=sig, timestamp_header=ts, raw_body=body) is True


def test_verify_signature_rejects_tampered_body():
    ts = str(int(time.time()))
    body = b'[{"event":"delivered","sg_event_id":"abc"}]'
    sig = _sign(TEST_SECRET, body, ts)
    tampered = body + b"tampered"
    assert verify_signature(secret=TEST_SECRET, signature_header=sig, timestamp_header=ts, raw_body=tampered) is False


def test_verify_signature_rejects_wrong_secret():
    ts = str(int(time.time()))
    body = b'[{"event":"delivered","sg_event_id":"abc"}]'
    sig = _sign(TEST_SECRET, body, ts)
    assert verify_signature(secret="different-secret", signature_header=sig, timestamp_header=ts, raw_body=body) is False


def test_verify_signature_rejects_missing_headers():
    body = b"{}"
    assert verify_signature(secret=TEST_SECRET, signature_header="", timestamp_header="1", raw_body=body) is False
    assert verify_signature(secret=TEST_SECRET, signature_header="x", timestamp_header="", raw_body=body) is False


@pytest.mark.asyncio
async def test_process_events_dedupes_by_event_id(seeded_users):
    import uuid as _uuid
    from app.core.db import db

    # Seed an email_log so events resolve tenant_id
    tenant_id = seeded_users["tenant_a"]["id"]
    suffix = _uuid.uuid4().hex[:8]
    log_id = f"email-log-{suffix}"
    sg_msg_id = f"sg-message-id-{suffix}"
    sg_evt_id = f"sg-e-{suffix}"
    await db.email_logs.insert_one({
        "id": log_id,
        "tenant_id": tenant_id,
        "to_email": "customer@example.com",
        "sendgrid_message_id": sg_msg_id,
        "related_type": "invoice",
        "related_id": "inv-1",
    })

    events = [
        {"event": "delivered", "sg_event_id": sg_evt_id, "sg_message_id": sg_msg_id,
         "email": "customer@example.com", "timestamp": int(time.time())},
    ]
    counts_first = await process_events(events)
    counts_second = await process_events(events)  # replay
    assert counts_first["received"] == 1
    assert counts_first["duplicate"] == 0
    assert counts_second["duplicate"] == 1

    # Exactly one email_activity persisted
    activity_count = await db.email_activity.count_documents({"provider_event_id": sg_evt_id})
    assert activity_count == 1


@pytest.mark.asyncio
async def test_process_events_marks_unresolved_tenant(seeded_users):
    import uuid as _uuid
    from app.core.db import db

    sg_evt_id = f"sg-e-unresolved-{_uuid.uuid4().hex[:8]}"
    events = [
        {"event": "delivered", "sg_event_id": sg_evt_id,
         "sg_message_id": "no-such-message", "email": "unknown@example.com",
         "timestamp": int(time.time())},
    ]
    counts = await process_events(events)
    assert counts["unresolved_tenant"] == 1

    wh = await db.webhook_events.find_one({"provider_event_id": sg_evt_id}, {"_id": 0})
    assert wh is not None
    assert wh["processing_status"] == "failed"
    assert wh["error_code"] == "tenant_unresolved"


def test_sendgrid_route_disabled_returns_404(monkeypatch):
    """When SENDGRID_WEBHOOK_ENABLED is false the route MUST 404 (no leakage)."""
    from fastapi.testclient import TestClient

    # Force-disable in the running settings
    from app.core import config as cfg
    s = cfg.get_settings()
    orig_enabled = s.sendgrid_webhook_enabled
    orig_secret = s.sendgrid_webhook_secret
    s.sendgrid_webhook_enabled = False
    s.sendgrid_webhook_secret = None
    try:
        from server import app  # type: ignore
        client = TestClient(app)
        resp = client.post("/api/webhooks/sendgrid", content=b"[]")
        assert resp.status_code == 404
    finally:
        s.sendgrid_webhook_enabled = orig_enabled
        s.sendgrid_webhook_secret = orig_secret


def test_sendgrid_route_rejects_invalid_signature(monkeypatch):
    from fastapi.testclient import TestClient

    from app.core import config as cfg
    s = cfg.get_settings()
    orig_enabled = s.sendgrid_webhook_enabled
    orig_secret = s.sendgrid_webhook_secret
    s.sendgrid_webhook_enabled = True
    s.sendgrid_webhook_secret = TEST_SECRET
    try:
        from server import app  # type: ignore
        client = TestClient(app)
        resp = client.post(
            "/api/webhooks/sendgrid",
            content=b"[]",
            headers={
                "X-Twilio-Email-Event-Webhook-Signature": "not-a-real-sig",
                "X-Twilio-Email-Event-Webhook-Timestamp": "1",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 401
    finally:
        s.sendgrid_webhook_enabled = orig_enabled
        s.sendgrid_webhook_secret = orig_secret


def test_sendgrid_route_accepts_valid_signature(monkeypatch):
    from fastapi.testclient import TestClient

    from app.core import config as cfg
    s = cfg.get_settings()
    orig_enabled = s.sendgrid_webhook_enabled
    orig_secret = s.sendgrid_webhook_secret
    s.sendgrid_webhook_enabled = True
    s.sendgrid_webhook_secret = TEST_SECRET
    try:
        from server import app  # type: ignore
        client = TestClient(app)
        ts = str(int(time.time()))
        body = json.dumps([]).encode()
        sig = _sign(TEST_SECRET, body, ts)
        resp = client.post(
            "/api/webhooks/sendgrid",
            content=body,
            headers={
                "X-Twilio-Email-Event-Webhook-Signature": sig,
                "X-Twilio-Email-Event-Webhook-Timestamp": ts,
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["ok"] is True
    finally:
        s.sendgrid_webhook_enabled = orig_enabled
        s.sendgrid_webhook_secret = orig_secret
