"""EC2 — Shared Webhook framework.

Every inbound webhook lands here first: `record_received` writes an initial
row in `webhook_events` with dedupe key (provider, provider_event_id).
Downstream processors update the row's status (verified / processed / failed
/ duplicate) via `mark_*` helpers.

This module deliberately does NOT persist raw provider payloads by default.
Callers may pass a small trimmed metadata dict describing the event.
Signature secrets never appear in the collection.
"""
from __future__ import annotations

from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.webhook_event import WebhookEvent


async def record_received(
    *,
    provider: str,
    provider_event_id: str,
    event_type: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> tuple[WebhookEvent, bool]:
    """Insert a webhook_event row. Returns (event, is_duplicate).

    If a row for (provider, provider_event_id) already exists, is_duplicate=True
    and the existing row is returned in-place. Explicit pre-check keeps behavior
    deterministic when the unique index has not yet been created (e.g. an
    isolated test harness).
    """
    existing = await db.webhook_events.find_one(
        {"provider": provider, "provider_event_id": provider_event_id},
        {"_id": 0},
    )
    if existing:
        await db.webhook_events.update_one(
            {"provider": provider, "provider_event_id": provider_event_id},
            {"$set": {"processing_status": "duplicate", "updated_at": utc_now().isoformat()}},
        )
        return WebhookEvent(**existing), True

    evt = WebhookEvent(
        provider=provider,
        provider_event_id=provider_event_id,
        received_at=utc_now(),
        event_type=event_type,
        metadata=metadata,
    )
    try:
        await db.webhook_events.insert_one(prepare_for_mongo(evt.model_dump()))
        return evt, False
    except DuplicateKeyError:
        existing = await db.webhook_events.find_one(
            {"provider": provider, "provider_event_id": provider_event_id},
            {"_id": 0},
        )
        if existing:
            await db.webhook_events.update_one(
                {"provider": provider, "provider_event_id": provider_event_id},
                {"$set": {"processing_status": "duplicate", "updated_at": utc_now().isoformat()}},
            )
            return WebhookEvent(**existing), True
        return evt, True


async def mark_verified(*, provider: str, provider_event_id: str, tenant_id: Optional[str] = None) -> None:
    patch: dict[str, Any] = {
        "signature_verified": True,
        "processing_status": "verified",
        "updated_at": utc_now().isoformat(),
    }
    if tenant_id:
        patch["tenant_id"] = tenant_id
    await db.webhook_events.update_one(
        {"provider": provider, "provider_event_id": provider_event_id},
        {"$set": patch},
    )


async def mark_processed(*, provider: str, provider_event_id: str) -> None:
    await db.webhook_events.update_one(
        {"provider": provider, "provider_event_id": provider_event_id},
        {"$set": {"processing_status": "processed", "updated_at": utc_now().isoformat()}},
    )


async def mark_failed(
    *,
    provider: str,
    provider_event_id: str,
    error_code: str,
    error_message: str,
) -> None:
    await db.webhook_events.update_one(
        {"provider": provider, "provider_event_id": provider_event_id},
        {
            "$set": {
                "processing_status": "failed",
                "error_code": error_code,
                "error_message": error_message,
                "updated_at": utc_now().isoformat(),
            }
        },
    )


async def list_events(
    *,
    provider: Optional[str] = None,
    processing_status: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
) -> dict[str, Any]:
    q: dict[str, Any] = {}
    if provider:
        q["provider"] = provider
    if processing_status:
        q["processing_status"] = processing_status
    total = await db.webhook_events.count_documents(q)
    cursor = (
        db.webhook_events.find(q, {"_id": 0})
        .sort("received_at", -1)
        .skip(skip)
        .limit(limit)
    )
    return {
        "items": [serialize_doc(d) async for d in cursor],
        "total": total,
        "limit": limit,
        "skip": skip,
    }
