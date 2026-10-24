"""Test-only HTTP double. Never imported by application code or enabled by a flag."""
import base64
import io
import json
from pathlib import Path

import httpx
from PIL import Image, ImageOps

from app.services import openai_image_provider as provider


def image_bytes():
    source = Image.open(Path(__file__).parent / "fixtures/webstore-blue-tshirt.jpg")
    image = ImageOps.pad(source.convert("RGB"), (1024, 1024), color="white")
    output = io.BytesIO(); image.save(output, "PNG")
    return output.getvalue()


def response_payload(data=None):
    return {"data": [{"b64_json": base64.b64encode(image_bytes() if data is None else data).decode()}],
            "usage": {"input_tokens": 100, "output_tokens": 2000, "total_tokens": 2100,
                      "input_tokens_details": {"text_tokens": 100, "image_tokens": 0},
                      "output_tokens_details": {"image_tokens": 2000, "text_tokens": 0}}}


def install(monkeypatch, handler=None):
    calls = []

    async def transport(request):
        calls.append(request)
        assert str(request.url) == provider.ENDPOINT
        body = json.loads(request.content)
        assert body["model"] == provider.MODEL and body["n"] == 1
        if handler:
            return await handler(request)
        return httpx.Response(200, json=response_payload(), headers={"x-request-id": "isolated-provider-" + request.headers["x-client-request-id"]})

    monkeypatch.setattr(provider, "client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(transport)))
    settings = provider.get_settings()
    monkeypatch.setattr(settings, "openai_image_generation_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "isolated-transport-test-key")
    return calls
