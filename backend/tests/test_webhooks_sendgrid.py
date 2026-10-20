"""EC2 — SendGrid Signed Event Webhook (ECDSA) + processing tests.

Signs with a throwaway P-256 key generated per test run, exactly as SendGrid
signs `timestamp + raw_body`. Live route enablement stays disabled by config.
"""
from __future__ import annotations

import json
import time

import pytest
from ellipticcurve.ecdsa import Ecdsa
from ellipticcurve.privateKey import PrivateKey

from app.services.sendgrid_webhook import process_events, verify_signature

_PRIVATE_KEY = PrivateKey()
TEST_PUBLIC_KEY = "".join(line for line in _PRIVATE_KEY.publicKey().toPem().strip().splitlines() if "PUBLIC KEY" not in line)
OTHER_PUBLIC_KEY = "".join(line for line in PrivateKey().publicKey().toPem().strip().splitlines() if "PUBLIC KEY" not in line)


def _sign(body: bytes, ts: str) -> str:
    return Ecdsa.sign(ts + body.decode("utf-8"), _PRIVATE_KEY).toBase64()


def test_verify_signature_accepts_correct_signature():
    ts = str(int(time.time()))
    body = b'[{"event":"delivered","sg_event_id":"abc"}]'
    assert verify_signature(public_key=TEST_PUBLIC_KEY, signature_header=_sign(body, ts), timestamp_header=ts, raw_body=body) is True


def test_verify_signature_rejects_tampered_body():
    ts = str(int(time.time()))
    body = b'[{"event":"delivered","sg_event_id":"abc"}]'
    sig = _sign(body, ts)
    assert verify_signature(public_key=TEST_PUBLIC_KEY, signature_header=sig, timestamp_header=ts, raw_body=body + b" ") is False


def test_verify_signature_rejects_wrong_key_and_timestamp():
    ts = str(int(time.time()))
    body = b'[{"event":"delivered","sg_event_id":"abc"}]'
    sig = _sign(body, ts)
    assert verify_signature(public_key=OTHER_PUBLIC_KEY, signature_header=sig, timestamp_header=ts, raw_body=body) is False
    assert verify_signature(public_key=TEST_PUBLIC_KEY, signature_header=sig, timestamp_header=str(int(ts) + 1), raw_body=body) is False


def test_verify_signature_rejects_missing_headers_and_garbage():
    body = b"[]"
    assert verify_signature(public_key=TEST_PUBLIC_KEY, signature_header="", timestamp_header="1", raw_body=body) is False
    assert verify_signature(public_key=TEST_PUBLIC_KEY, signature_header="x", timestamp_header="", raw_body=body) is False
    assert verify_signature(public_key=TEST_PUBLIC_KEY, signature_header="not-base64-sig", timestamp_header="1", raw_body=body) is False
    assert verify_signature(public_key="not-a-key", signature_header=_sign(body, "1"), timestamp_header="1", raw_body=body) is False


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
    orig_key = s.sendgrid_webhook_public_key
    s.sendgrid_webhook_enabled = False
    s.sendgrid_webhook_public_key = None
    try:
        from server import app  # type: ignore
        client = TestClient(app)
        resp = client.post("/api/webhooks/sendgrid", content=b"[]")
        assert resp.status_code == 404
    finally:
        s.sendgrid_webhook_enabled = orig_enabled
        s.sendgrid_webhook_public_key = orig_key


def test_sendgrid_route_rejects_invalid_signature(monkeypatch):
    from fastapi.testclient import TestClient

    from app.core import config as cfg
    s = cfg.get_settings()
    orig_enabled = s.sendgrid_webhook_enabled
    orig_key = s.sendgrid_webhook_public_key
    s.sendgrid_webhook_enabled = True
    s.sendgrid_webhook_public_key = TEST_PUBLIC_KEY
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
        s.sendgrid_webhook_public_key = orig_key


def test_sendgrid_route_accepts_valid_signature(monkeypatch):
    from fastapi.testclient import TestClient

    from app.core import config as cfg
    s = cfg.get_settings()
    orig_enabled = s.sendgrid_webhook_enabled
    orig_key = s.sendgrid_webhook_public_key
    s.sendgrid_webhook_enabled = True
    s.sendgrid_webhook_public_key = TEST_PUBLIC_KEY
    try:
        from server import app  # type: ignore
        client = TestClient(app)
        ts = str(int(time.time()))
        body = json.dumps([]).encode()
        sig = _sign(body, ts)
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
        s.sendgrid_webhook_public_key = orig_key


@pytest.mark.asyncio
async def test_events_match_tenant_by_message_id_never_by_recipient(seeded_users):
    """An event whose recipient matches a log but whose message id does not is unresolved."""
    import uuid as _uuid
    from app.core.db import db

    suffix = _uuid.uuid4().hex[:8]
    tenant_id = seeded_users["tenant_a"]["id"]
    await db.email_logs.insert_one({
        "id": f"email-log-r-{suffix}", "tenant_id": tenant_id, "to_email": f"shared-{suffix}@example.com",
        "sendgrid_message_id": f"msg-{suffix}", "related_type": "webstore", "related_id": "ws-1",
    })
    no_id = {"event": "delivered", "sg_event_id": f"e1-{suffix}", "email": f"shared-{suffix}@example.com", "timestamp": int(time.time())}
    wrong_id = {**no_id, "sg_event_id": f"e2-{suffix}", "sg_message_id": f"other-{suffix}.filter0001"}
    right_id = {**no_id, "sg_event_id": f"e3-{suffix}", "sg_message_id": f"msg-{suffix}.filter0001.123"}
    counts = await process_events([no_id, wrong_id, right_id])
    assert counts["unresolved_tenant"] == 2
    rows = [r async for r in db.email_activity.find({"provider_event_id": {"$in": [f"e1-{suffix}", f"e2-{suffix}", f"e3-{suffix}"]}}, {"_id": 0})]
    assert [(r["provider_event_id"], r["tenant_id"], r["email_log_id"]) for r in rows] == [(f"e3-{suffix}", tenant_id, f"email-log-r-{suffix}")]
