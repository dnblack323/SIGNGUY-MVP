"""EC14 - Webstores Stripe Connect boundary.

Phase 14 creates local boundary records only. It does not call Stripe APIs,
open Checkout Sessions, process webhooks, or mutate EC4/EC13 billing records.
"""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc
from ..models.webstore import WebstoreStripeConnectRecord


async def create_local_checkout_record(
    *,
    tenant_id: str,
    webstore_id: str,
    buyer_order_id: str,
    amount_cents: int,
    currency: str = "usd",
    idempotency_key: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict:
    if idempotency_key:
        existing = await db.webstore_stripe_connect_records.find_one(
            {"tenant_id": tenant_id, "webstore_id": webstore_id, "record_type": "checkout_session", "idempotency_key": idempotency_key},
            {"_id": 0},
        )
        if existing:
            return serialize_doc(existing)  # type: ignore[return-value]
    record = WebstoreStripeConnectRecord(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        record_type="checkout_session",
        status="local_only",
        amount_cents=amount_cents,
        currency=currency,
        idempotency_key=idempotency_key,
        checkout_url=f"/p/webstores/checkout/{buyer_order_id}",
        metadata={"buyer_order_id": buyer_order_id, **(metadata or {})},
    ).model_dump()
    await db.webstore_stripe_connect_records.insert_one(prepare_for_mongo(record))
    return serialize_doc(record)  # type: ignore[return-value]


async def create_local_onboarding_record(
    *,
    tenant_id: str,
    webstore_id: str,
    owner_id: str,
    idempotency_key: Optional[str] = None,
) -> dict:
    record = WebstoreStripeConnectRecord(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        owner_id=owner_id,
        record_type="account_onboarding",
        status="local_only",
        idempotency_key=idempotency_key,
        metadata={"provider_calls": "not_authorized_in_ec14"},
    ).model_dump()
    await db.webstore_stripe_connect_records.insert_one(prepare_for_mongo(record))
    return serialize_doc(record)  # type: ignore[return-value]
