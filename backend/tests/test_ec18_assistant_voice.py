"""EC18B - OpenAI Realtime voice boundary tests."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.db import db
from app.deps import get_current_user
from app.services import ai_gateway
from app.services import business_assistant as assistant_svc
from app.services.entitlements import _upsert_entitlement_for_tests
from server import app


def _override(user: dict):
    async def _get():
        return {**user}

    return _get


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest_asyncio.fixture
async def voice_ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-ec18-voice-{suffix}"
    owner = {"id": f"owner-{suffix}", "tenant_id": tenant_id, "email": f"owner-{suffix}@example.com", "role": "owner", "is_active": True}
    platform_admin = {
        "id": f"platform-{suffix}",
        "tenant_id": tenant_id,
        "email": f"platform-{suffix}@example.com",
        "role": "owner",
        "is_active": True,
        "platform_admin": True,
        "platform_role": "admin",
    }
    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "EC18 Voice Tenant"})
    await db.users.insert_many([owner, platform_admin])
    await _upsert_entitlement_for_tests(tenant_id=tenant_id, feature_key="business_assistant", enabled=True)
    async with await _client_as(platform_admin) as platform:
        boot = await platform.post("/api/assistant/platform/bootstrap")
        assert boot.status_code == 201, boot.text
    await ai_gateway.grant_credits(platform_admin, tenant_id, {"included_credits": 20, "reason": "EC18 voice test"})
    yield {"tenant_id": tenant_id, "owner": owner}
    app.dependency_overrides.pop(get_current_user, None)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_configured_realtime_session_uses_backend_key_ephemeral_secret_and_safety_id(monkeypatch, voice_ctx):
    get_settings.cache_clear()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-never-return")
    monkeypatch.setenv("OPENAI_REALTIME_ENABLED", "true")
    monkeypatch.setenv("OPENAI_REALTIME_MODEL", "gpt-realtime-2.1")
    monkeypatch.setenv("OPENAI_REALTIME_VOICE", "verse")
    get_settings.cache_clear()
    captured = {}

    async def fake_request(*, settings, safety_id, payload):
        captured["url"] = "https://api.openai.com/v1/realtime/client_secrets"
        captured["headers"] = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "OpenAI-Safety-Identifier": safety_id,
        }
        captured["json"] = payload
        return {"id": f"realtime-session-test-{voice_ctx['tenant_id']}", "value": "eph-test-secret", "expires_at": 9999999999}

    monkeypatch.setattr(assistant_svc, "_request_openai_realtime_client_secret", fake_request)

    async with await _client_as(voice_ctx["owner"]) as client:
        response = await client.post("/api/assistant/voice/sessions", json={})
        assert response.status_code == 201, response.text

    body = response.json()
    assert body["configured"] is True
    assert body["model"] == "gpt-realtime-2.1"
    assert body["voice"] == "verse"
    assert body["realtime"]["value"] == "eph-test-secret"
    assert "sk-test-never-return" not in str(body)
    assert captured["url"] == "https://api.openai.com/v1/realtime/client_secrets"
    assert captured["headers"]["Authorization"] == "Bearer sk-test-never-return"
    assert captured["headers"]["OpenAI-Safety-Identifier"]
    assert captured["json"]["session"]["type"] == "realtime"
    assert captured["json"]["session"]["model"] == "gpt-realtime-2.1"
    assert "turn_detection" not in captured["json"]["session"]
    assert captured["json"]["session"]["audio"]["input"]["turn_detection"]["type"] == "server_vad"
    assert captured["json"]["session"]["tools"][0]["name"] == "propose_assistant_action"

    stored = await db.assistant_voice_sessions.find_one({"tenant_id": voice_ctx["tenant_id"], "provider_session_id": f"realtime-session-test-{voice_ctx['tenant_id']}"}, {"_id": 0})
    assert stored["raw_audio_stored"] is False
    assert stored["status"] == "created"

    async with await _client_as(voice_ctx["owner"]) as client:
        usage = await client.post(
            f"/api/assistant/voice/sessions/{stored['id']}/usage",
            json={"provider_event_id": f"provider-event-{voice_ctx['tenant_id']}", "input_audio_seconds": 3, "output_audio_seconds": 4},
        )
        assert usage.status_code == 201, usage.text
        duplicate = await client.post(
            f"/api/assistant/voice/sessions/{stored['id']}/usage",
            json={"provider_event_id": f"provider-event-{voice_ctx['tenant_id']}", "input_audio_seconds": 3, "output_audio_seconds": 4},
        )
        assert duplicate.status_code == 201, duplicate.text

    updated = await db.assistant_voice_sessions.find_one({"tenant_id": voice_ctx["tenant_id"], "id": stored["id"]}, {"_id": 0})
    assert updated["input_audio_seconds"] == 3
    assert updated["output_audio_seconds"] == 4
    assert len(updated["usage_event_ids"]) == 1
