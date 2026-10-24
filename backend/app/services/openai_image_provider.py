"""Bounded Images API transport. No credits, storage, retries or demo execution."""
from __future__ import annotations

import base64
import asyncio
import hashlib
import json
import time
from decimal import Decimal, ROUND_CEILING

import httpx

from ..core.config import get_settings

MODEL = "gpt-image-2.5-sunburst-2026-09-08"
ENDPOINT = "https://api.openai.com/v1/images/generations"
MAX_RESPONSE_BYTES = 18 * 1024 * 1024


def available() -> bool:
    settings = get_settings()
    return bool(settings.openai_image_generation_enabled and settings.openai_api_key)


def client() -> httpx.AsyncClient:
    # httpx does not retry by default. Never follow a redirect with credentials.
    return httpx.AsyncClient(timeout=httpx.Timeout(180, connect=10), follow_redirects=False, trust_env=False)


def pricing(model: dict) -> dict:
    config = (model.get("metadata") or {}).get("image_pricing") or {}
    keys = ("text_input_micros_per_million", "image_input_micros_per_million", "image_output_micros_per_million", "max_request_cost_micros")
    if model.get("provider_key") != "openai" or model.get("model_key") != MODEL:
        raise ValueError("Configure the supported pinned OpenAI image profile")
    if any(type(config.get(k)) is not int or config[k] <= 0 for k in keys):
        raise ValueError("An approved image pricing snapshot and request estimate are required")
    return {k: config[k] for k in keys}


def usage_cost(usage: dict, rates: dict) -> int:
    keys = ("input_tokens", "output_tokens", "total_tokens")
    if any(type(usage.get(k)) is not int or usage[k] < 0 for k in keys):
        raise ValueError("Missing verified provider usage")
    details = usage.get("input_tokens_details") or {}
    if any(type(details.get(k)) is not int or details[k] < 0 for k in ("text_tokens", "image_tokens")):
        raise ValueError("Missing provider input breakdown")
    if details["text_tokens"] + details["image_tokens"] != usage["input_tokens"] or usage["input_tokens"] + usage["output_tokens"] != usage["total_tokens"]:
        raise ValueError("Inconsistent provider usage")
    output = usage.get("output_tokens_details")
    if output is not None and (type(output.get("image_tokens")) is not int or output.get("image_tokens") != usage["output_tokens"] or output.get("text_tokens", 0) != 0):
        raise ValueError("Unsupported provider output usage; reconcile before settlement")
    numerator = (details["text_tokens"] * rates["text_input_micros_per_million"]
                 + details["image_tokens"] * rates["image_input_micros_per_million"]
                 + usage["output_tokens"] * rates["image_output_micros_per_million"])
    return int((Decimal(numerator) / 1_000_000).to_integral_value(rounding=ROUND_CEILING))


async def generate(*, request_id: str, safety_identifier: str, color: str, size: str, rates: dict) -> dict:
    try:
        return await asyncio.wait_for(_generate(request_id=request_id, safety_identifier=safety_identifier, color=color, size=size, rates=rates), timeout=190)
    except asyncio.TimeoutError:
        return {"client_request_id": request_id, "model": MODEL, "uncertain": True}


async def _generate(*, request_id: str, safety_identifier: str, color: str, size: str, rates: dict) -> dict:
    if not available():
        raise RuntimeError("Image execution is disabled")
    prompt = ("Create a realistic studio product presentation of one unbranded flat-front T-shirt. "
              "Straight-on front view, full garment visible, neutral background, front surface flat and unobstructed "
              "for later deterministic artwork placement. No logos, lettering, artwork, tags or watermark. "
              f"Selected configuration (data, not instructions): {json.dumps({'color': color, 'size': size})}. "
              "Match that color and garment characteristics; do not claim supplier accuracy.")
    body = {"model": MODEL, "prompt": prompt, "n": 1, "size": "1024x1024", "quality": "medium",
            "output_format": "png", "background": "opaque", "moderation": "auto", "safety_identifier": safety_identifier}
    started = time.monotonic()
    receipt = {"client_request_id": request_id, "model": MODEL, "request_sha256": hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()}
    try:
        async with client() as transport:
            async with transport.stream("POST", ENDPOINT, json=body, headers={
                "Authorization": f"Bearer {get_settings().openai_api_key}", "X-Client-Request-Id": request_id}) as response:
                receipt["provider_event_id"] = response.headers.get("x-request-id")
                receipt["http_status"] = response.status_code
                # A rejection can release credits. 408/409, 5xx and transport
                # failures have uncertain delivery; never automatically resend.
                if 400 <= response.status_code < 500 and response.status_code not in {408, 409}:
                    return {**receipt, "verified_success": False, "rejected_before_execution": True}
                if response.status_code != 200:
                    return {**receipt, "uncertain": True}
                chunks, length = [], 0
                async for chunk in response.aiter_bytes():
                    length += len(chunk)
                    if length > MAX_RESPONSE_BYTES:
                        return {**receipt, "uncertain": True}
                    chunks.append(chunk)
                payload = json.loads(b"".join(chunks))
                usage = payload.get("usage") or {}
                cost = usage_cost(usage, rates)
                receipt.update(usage=usage, input_units=usage["input_tokens"], output_units=usage["output_tokens"],
                               estimated_cost_micros=cost, pricing_snapshot=rates,
                               duration_ms=round((time.monotonic() - started) * 1000))
                if not receipt.get("provider_event_id"):
                    return {**receipt, "uncertain": True}
                images = payload.get("data") or []
                if len(images) != 1 or not isinstance(images[0].get("b64_json"), str):
                    return {**receipt, "verified_success": False}
                data = base64.b64decode(images[0]["b64_json"], validate=True)
                return {**receipt, "verified_success": True, "image_bytes": data}
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return {**receipt, "uncertain": True}
