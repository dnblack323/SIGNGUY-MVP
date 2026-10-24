"""Backend-only unified Realtime transport; no paid requests."""

import json
import httpx
import pytest
from app.services import openai_realtime_provider as provider
from app.core.config import get_settings


@pytest.mark.asyncio
async def test_unified_call_uses_backend_key_and_validates_location(monkeypatch):
    captured = []
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "mock-backend-only")

    async def send(self, url, **kwargs):
        captured.append((url, kwargs))
        return httpx.Response(
            201,
            text="answer",
            headers={"Location": "/v1/realtime/calls/rtc_test"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", send)
    assert await provider.create_call("offer", {"type": "realtime"}) == (
        "answer",
        "rtc_test",
    )
    assert captured[0][1]["headers"]["Authorization"] == "Bearer mock-backend-only"
    assert json.loads(captured[0][1]["files"]["session"][1]) == {"type": "realtime"}
    assert await provider.hangup("rtc_test") is False
    assert await provider.hangup("../other") is False


@pytest.mark.asyncio
async def test_sideband_credentials_never_returned_to_browser(monkeypatch):
    captured = {}

    async def connect(url, **kwargs):
        captured.update(url=url, **kwargs)
        return "mock-socket"

    monkeypatch.setattr(provider, "connect", connect)
    assert await provider.attach("rtc_test") == "mock-socket"
    assert captured["url"] == "wss://api.openai.com/v1/realtime?call_id=rtc_test"
    assert "Authorization" in captured["additional_headers"]
