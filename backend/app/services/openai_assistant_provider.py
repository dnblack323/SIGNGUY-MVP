"""Backend-only Responses transport. Automated callers replace this boundary."""

import httpx

from ..core.config import get_settings


async def respond(payload: dict) -> dict:
    settings = get_settings()
    if not settings.assistant_text_enabled or not settings.openai_api_key:
        raise RuntimeError("Assistant text provider is not configured")
    async with httpx.AsyncClient(
        timeout=settings.assistant_provider_timeout_seconds
    ) as client:
        response = await client.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json=payload,
        )
        response.raise_for_status()
        return response.json()
