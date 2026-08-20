"""Shared event and provider helpers for Webstore payments."""
from __future__ import annotations

import asyncio
from typing import Optional

from ..core.db import db
from ..core.time_utils import serialize_doc, utc_now
from .webstore_context import WebstoreError
from .webstore_payment_provider import ProviderAuthority, provider_configuration_status

def _now_iso() -> str:
    return utc_now().isoformat()


def _event_key(provider: str, provider_event_id: str) -> dict[str, str]:
    return {"provider": provider, "provider_event_id": provider_event_id}


async def _existing_event(provider: str, provider_event_id: str) -> Optional[dict]:
    return serialize_doc(await db.webstore_payment_events.find_one(_event_key(provider, provider_event_id), {"_id": 0}))


async def _wait_for_terminal_event(provider: str, provider_event_id: str) -> Optional[dict]:
    for _ in range(200):
        event = await _existing_event(provider, provider_event_id)
        if event and event.get("status") != "processing":
            return event
        await asyncio.sleep(0.01)
    return await _existing_event(provider, provider_event_id)


def _event_response(event: dict) -> dict:
    return {
        "payment_event": event,
        "already_processed": event.get("status") in {"processed", "failed", "duplicate"},
        "order_id": event.get("canonical_order_id"),
        "payment_id": event.get("canonical_payment_id"),
    }


def _require_provider_authority(authority: Optional[ProviderAuthority] = None) -> None:
    if authority is not None:
        if authority.verified and authority.webhook_verified and authority.charge_model != "deferred":
            return
        raise WebstoreError(
            "payment_provider_not_configured",
            "Provider-authoritative Webstore payment processing is unavailable until provider verification is complete.",
            503,
        )
    status = provider_configuration_status()
    if not status["provider_authority"]:
        raise WebstoreError(
            "payment_provider_not_configured",
            "Provider-authoritative Webstore payment processing is unavailable until the Stripe adapter is implemented and verified.",
            503,
        )
