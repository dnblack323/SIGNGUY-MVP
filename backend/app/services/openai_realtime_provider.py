"""Backend-only media SDP/sideband transport. Tests replace every boundary."""

import json
import re
from urllib.parse import urlparse

import httpx
from websockets.asyncio.client import connect

from ..core.config import get_settings

BASE = "https://api.openai.com/v1/realtime/calls"


async def create_call(offer: str, session: dict) -> tuple[str, str]:
    settings = get_settings()
    async with httpx.AsyncClient(
        timeout=settings.openai_realtime_timeout_seconds
    ) as client:
        response = await client.post(
            BASE,
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            files={"sdp": (None, offer), "session": (None, json.dumps(session))},
        )
        response.raise_for_status()
        location = urlparse(response.headers.get("location", ""))
        call_id = location.path.rsplit("/", 1)[-1]
        if location.netloc not in {"", "api.openai.com"} or not re.fullmatch(
            r"rtc_[A-Za-z0-9_-]{1,160}", call_id
        ):
            raise ValueError("Provider returned an invalid call identifier")
        return response.text, call_id


async def attach(call_id: str):
    return await connect(
        f"wss://api.openai.com/v1/realtime?call_id={call_id}",
        additional_headers={"Authorization": f"Bearer {get_settings().openai_api_key}"},
        max_size=262144,
        open_timeout=10,
        close_timeout=2,
    )


async def hangup(call_id: str) -> bool:
    if not re.fullmatch(r"rtc_[A-Za-z0-9_-]{1,160}", call_id):
        return False
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.post(
            f"{BASE}/{call_id}/hangup",
            headers={"Authorization": f"Bearer {get_settings().openai_api_key}"},
        )
        return response.status_code in {200, 204, 404, 410}
