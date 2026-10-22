"""Stage C private settings and static preview/readiness; no paid calls."""

import hashlib
import json
from pathlib import Path
import wave

import httpx
import pytest

from app.core.assistant_voices import VOICE_KEYS, voice_options
from app.core.db import db
from app.services import ai_gateway, assistant_personality, business_assistant as svc
from server import app
from tests.test_assistant_stage_b import ctx  # noqa: F401


@pytest.mark.asyncio
@pytest.mark.parametrize("voice", VOICE_KEYS)
async def test_voice_personality_combinations_isolation_and_relogin(ctx, voice):
    conversation = await svc.create_conversation(ctx["user"], {})
    memory = await svc.upsert_memory(
        ctx["user"], {"memory_key": "format", "content_text": "Concise"}
    )
    before = await ai_gateway.get_credit_account(ctx["tenant"])
    for personality in assistant_personality.PRESETS:
        result = await svc.update_preferences(
            ctx["user"], {"voice": voice, "personality_key": personality}
        )
        assert result["preferences"]["voice"] == voice
        assert result["preferences"]["personality_key"] == personality
        assert result["effective_voice"] == voice
        assert result["voices"] == voice_options()
        # Voice is data, never a second personality or permissions prompt.
        assert assistant_personality.PRESETS[personality][
            2
        ] in assistant_personality.instructions(result["preferences"])
    for other in (ctx["other"], ctx["foreign"]):
        own = (await svc.get_preferences(other))["preferences"]
        assert own["voice"] is None and own["personality_key"] == "ops_partner"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:

        async def login():
            result = await client.post(
                "/api/auth/login",
                json={
                    "tenant_slug": ctx["tenant"],
                    "email": ctx["user"]["email"],
                    "password": "isolated-test-password",
                },
            )
            assert result.status_code == 200
            client.headers["Authorization"] = "Bearer " + result.json()["access_token"]

        await login()
        assert (await client.post("/api/auth/logout")).status_code == 204
        await login()
        current = (await client.get("/api/assistant/preferences")).json()
        assert current["preferences"]["voice"] == voice
        assert current["preferences"]["personality_key"] == "sarcastic_funny"
        for bad in (
            {"voice": "unknown"},
            {"voice": "https://example.com/audio"},
            {"voice": voice, "tenant_id": "other"},
            {"voice": voice, "user_id": "other"},
        ):
            assert (
                await client.put("/api/assistant/preferences", json=bad)
            ).status_code == 422
        assert (
            await client.put(
                "/api/assistant/preferences", json={"personality_key": "wise_mentor"}
            )
        ).json()["preferences"]["voice"] == voice
        assert (
            await client.put("/api/assistant/preferences", json={"voice": voice})
        ).json()["preferences"]["personality_key"] == "wise_mentor"
    assert (await svc.get_conversation(ctx["user"], conversation["id"]))[
        "conversation"
    ]["id"] == conversation["id"]
    assert (await svc.list_memory(ctx["user"]))["items"][0]["id"] == memory["id"]
    assert (await ai_gateway.get_credit_account(ctx["tenant"])) == before
    assert ctx["calls"] == []


@pytest.mark.asyncio
async def test_paid_voice_is_blocked_even_with_provider_configuration(ctx, monkeypatch):
    monkeypatch.setattr(ctx["settings"], "openai_realtime_enabled", True)

    async def forbidden(**kwargs):
        raise AssertionError("Stage C must not create paid sessions")

    monkeypatch.setattr(svc, "_request_openai_realtime_client_secret", forbidden)
    before = await db.assistant_voice_sessions.count_documents(
        {"tenant_id": ctx["tenant"]}
    )
    with pytest.raises(svc.BusinessAssistantError) as error:
        await svc.create_realtime_session(ctx["user"], {})
    assert error.value.code == "voice_stage_not_available"
    assert (
        await db.assistant_voice_sessions.count_documents({"tenant_id": ctx["tenant"]})
        == before
    )
    config = svc.voice_config()
    assert config["configured"] is True and config["interactions_available"] is False
    assert config["preview_provider_requests"] == 0
    assert config["preview_credit_charge"] == 0
    assert "mock-not-a-live-key" not in json.dumps(config)


def test_every_selectable_voice_has_a_valid_bounded_attributed_sample():
    root = (
        Path(__file__).resolve().parents[2] / "frontend/public/assistant-voice-samples"
    )
    manifest = {
        row["voice"]: row for row in json.loads((root / "sources.json").read_text())
    }
    assert set(manifest) == set(VOICE_KEYS)
    for option in voice_options():
        name = option["key"]
        path = root / (name + ".wav")
        assert option["preview_path"] == f"/assistant-voice-samples/{name}.wav"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest[name]["sha256"]
        assert (
            manifest[name]["source"]
            == f"https://cdn.openai.com/API/docs/audio/{name}.wav"
        )
        with wave.open(str(path)) as audio:
            duration = audio.getnframes() / audio.getframerate()
            assert 0 < duration < 30
            assert (
                len(audio.readframes(audio.getnframes()))
                == audio.getnframes() * audio.getnchannels() * audio.getsampwidth()
            )
