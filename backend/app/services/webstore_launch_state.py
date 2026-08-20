"""Launch readiness state helpers for Webstores."""
from __future__ import annotations

from .webstore_shared import *
from .webstore_payment_boundary import _provider_authority_from_record

async def _payment_readiness(store: dict) -> dict[str, Any]:
    settings = get_settings()
    record = await db.webstore_stripe_connect_records.find_one(
        {"tenant_id": store.get("tenant_id"), "webstore_id": store.get("id"), "record_type": "connected_account"},
        {"_id": 0},
    )
    authority = _provider_authority_from_record(record, settings)
    provider_status = provider_configuration_status(settings, authority)
    state = provider_status["state"]
    return {
        "state": state,
        "label": provider_status["label"],
        "ready": bool(provider_status["provider_authority"]),
        "required": True,
        "provider_authority": bool(provider_status["provider_authority"]),
        "provider_mode": (record or {}).get("provider_mode") or getattr(settings, "stripe_mode", "test"),
        "provider_account_reference": (record or {}).get("connected_account_reference"),
        "requirements_currently_due": (record or {}).get("requirements_currently_due") or [],
        "reason": provider_status["reason"],
        "violations": provider_status["violations"],
        "stored_flags_ignored": True,
    }


async def _terms_acceptance(tenant_id: str, webstore_id: str, terms_version: str, portal_identity_id: Optional[str] = None) -> Optional[dict]:
    query: dict[str, Any] = {
        "tenant_id": tenant_id,
        "webstore_id": webstore_id,
        "terms_version": terms_version,
        "status": "current",
    }
    if portal_identity_id:
        query["portal_identity_id"] = portal_identity_id
    doc = await db.webstore_terms_acceptances.find_one(query, {"_id": 0}, sort=[("accepted_at", -1)])
    return serialize_doc(doc) if doc else None


async def _open_change_requests(tenant_id: str, webstore_id: str) -> list[dict[str, Any]]:
    return [
        serialize_doc(doc)
        async for doc in db.webstore_change_requests.find(
            {"tenant_id": tenant_id, "webstore_id": webstore_id, "status": {"$in": ["open", "answered"]}},
            {"_id": 0},
        ).sort([("created_at", 1)])
    ]
