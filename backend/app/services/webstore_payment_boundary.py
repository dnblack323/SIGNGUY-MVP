"""Payment provider boundary helpers for Webstores."""
from __future__ import annotations

from .webstore_shared import *

def _provider_authority_from_record(record: Optional[dict], settings: Any) -> Optional[ProviderAuthority]:
    if not record or not record.get("connected_account_reference"):
        return None
    base_status = provider_configuration_status(settings)
    return ProviderAuthority(
        provider="stripe",
        mode=str(record.get("provider_mode") or settings.stripe_mode),  # type: ignore[arg-type]
        account_reference=str(record["connected_account_reference"]),
        charge_model=str(settings.stripe_charge_model),
        webhook_verified=bool(base_status.get("configured")),
        verified=str(record.get("onboarding_state") or "") == "complete",
        restriction_status=record.get("restriction_status"),
        charges_enabled=bool(record.get("charges_enabled")),
        payouts_enabled=bool(record.get("payouts_enabled")),
        requirements_currently_due=tuple(str(value) for value in record.get("requirements_currently_due") or []),
    )


def _safe_provider_result(data: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "provider",
        "provider_mode",
        "account_reference",
        "onboarding_url",
        "onboarding_state",
        "charges_enabled",
        "payouts_enabled",
        "requirements_currently_due",
        "requirements_past_due",
        "restriction_status",
        "details_submitted",
    }
    return {key: value for key, value in data.items() if key in allowed}


async def _persist_provider_result(tenant_id: str, webstore_id: str, store: dict[str, Any], data: dict[str, Any]) -> None:
    account_reference = data.get("account_reference") or data.get("connected_account_reference")
    existing = await db.webstore_stripe_connect_records.find_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "record_type": "connected_account"},
        {"_id": 0},
    )
    now = utc_now().isoformat()
    updates: dict[str, Any] = {
        "updated_at": now,
        "provider_name": "stripe",
        "provider_mode": data.get("provider_mode") or (existing or {}).get("provider_mode") or "test",
    }
    if account_reference:
        updates["connected_account_reference"] = str(account_reference)
        updates["stripe_account_id"] = str(account_reference)
    for key in (
        "onboarding_state",
        "charges_enabled",
        "payouts_enabled",
        "requirements_currently_due",
        "requirements_past_due",
        "restriction_status",
    ):
        if key in data:
            updates[key] = data[key]
    if any(key in data for key in ("charges_enabled", "payouts_enabled", "requirements_currently_due", "restriction_status")):
        updates["last_provider_verified_at"] = now
    charges_enabled = bool(data.get("charges_enabled", (existing or {}).get("charges_enabled")))
    payouts_enabled = bool(data.get("payouts_enabled", (existing or {}).get("payouts_enabled")))
    requirements_currently_due = data.get("requirements_currently_due", (existing or {}).get("requirements_currently_due") or [])
    updates["status"] = "provider_ready" if charges_enabled and payouts_enabled and not requirements_currently_due else "pending_provider"
    base = WebstoreStripeConnectRecord(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        owner_id=store.get("owner_id"),
        record_type="connected_account",
        provider_mode=str(updates["provider_mode"]),
    ).model_dump()
    await db.webstore_stripe_connect_records.update_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "record_type": "connected_account"},
        {"$set": updates, "$setOnInsert": base},
        upsert=True,
    )
    await db.webstores.update_one(
        {"tenant_id": tenant_id, "id": webstore_id},
        {
            "$set": {
                "payment_provider_mode": updates["provider_mode"],
                "provider_account_reference": updates.get("connected_account_reference") or (existing or {}).get("connected_account_reference"),
                "provider_onboarding_state": updates.get("onboarding_state") or (existing or {}).get("onboarding_state") or "not_started",
                "provider_charges_enabled": bool(updates.get("charges_enabled") or (existing or {}).get("charges_enabled")),
                "provider_payouts_enabled": bool(updates.get("payouts_enabled") or (existing or {}).get("payouts_enabled")),
                "provider_requirements_currently_due": updates.get("requirements_currently_due") or (existing or {}).get("requirements_currently_due") or [],
                "updated_at": now,
            }
        },
    )


async def provider_authority_for_webstore(tenant_id: str, webstore_id: str) -> ProviderAuthority:
    settings = get_settings()
    record = await db.webstore_stripe_connect_records.find_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "record_type": "connected_account"},
        {"_id": 0},
    )
    authority = _provider_authority_from_record(record, settings)
    status = provider_configuration_status(settings, authority)
    if authority is None or not status["provider_authority"]:
        raise WebstoreError("payment_provider_not_configured", status["reason"], 503)
    return authority


async def payment_provider_status(user: dict, webstore_id: str) -> dict[str, Any]:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _get_store(user["tenant_id"], webstore_id)
    settings = get_settings()
    record = await db.webstore_stripe_connect_records.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "record_type": "connected_account"},
        {"_id": 0},
    )
    authority = _provider_authority_from_record(record, settings)
    status = provider_configuration_status(settings, authority)
    record = serialize_doc(record) if record else {}
    return {
        "webstore_id": webstore_id,
        "provider": "stripe",
        "status": status,
        "store_state": {
            "mode": record.get("provider_mode") or store.get("payment_provider_mode") or "test",
            "onboarding_state": record.get("onboarding_state") or store.get("provider_onboarding_state") or "not_started",
            "charges_enabled": bool(record.get("charges_enabled") or store.get("provider_charges_enabled")),
            "payouts_enabled": bool(record.get("payouts_enabled") or store.get("provider_payouts_enabled")),
            "requirements_currently_due": record.get("requirements_currently_due") or store.get("provider_requirements_currently_due") or [],
            "requirements_past_due": record.get("requirements_past_due") or store.get("provider_requirements_past_due") or [],
            "restriction_status": record.get("restriction_status"),
            "last_verified_at": record.get("last_provider_verified_at"),
            "provider_account_reference": record.get("connected_account_reference") or store.get("provider_account_reference"),
            "provider_authority": bool(status["provider_authority"]),
        },
        "actions": {
            "connect": True,
            "resume_onboarding": True,
            "refresh_status": True,
            "view_requirements": True,
            "disconnect": bool(record.get("connected_account_reference") or store.get("provider_account_reference")),
        },
    }


async def payment_provider_action(user: dict, webstore_id: str, action: str) -> dict[str, Any]:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    store = await _get_store(user["tenant_id"], webstore_id)
    settings = get_settings()
    if action not in {"connect", "resume_onboarding", "refresh_status", "view_requirements", "disconnect"}:
        raise WebstoreError("payment_provider_action_invalid", "Unsupported payment provider action", 400)
    record = await db.webstore_stripe_connect_records.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "record_type": "connected_account"},
        {"_id": 0},
    )
    record = serialize_doc(record) if record else {}
    provider = get_webstore_payment_provider(get_settings())
    if action in {"connect", "resume_onboarding"}:
        result = await provider.create_connected_account_onboarding_link(
            tenant_id=user["tenant_id"],
            webstore_id=webstore_id,
            owner_id=store.get("owner_id"),
            connected_account_reference=record.get("connected_account_reference"),
        )
    elif action == "refresh_status":
        result = await provider.synchronize_payment_readiness(
            tenant_id=user["tenant_id"],
            webstore_id=webstore_id,
            connected_account_reference=record.get("connected_account_reference"),
        )
    elif action == "view_requirements":
        result = await provider.retrieve_connected_account_status(
            tenant_id=user["tenant_id"],
            webstore_id=webstore_id,
            connected_account_reference=record.get("connected_account_reference"),
        )
    else:
        result = await provider.reconcile_provider_event(tenant_id=user["tenant_id"], webstore_id=webstore_id, action=action)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action=f"webstore.payment_provider_{action}",
        entity_type="webstore",
        entity_id=webstore_id,
        summary="Webstore payment provider action requested",
        metadata={"provider": "stripe", "result_code": result.code, "provider_authority": False},
    )
    if not result.ok:
        raise WebstoreError("payment_provider_not_configured", result.message, 503)
    result_data = dict(result.data or {})
    if result_data:
        await _persist_provider_result(user["tenant_id"], webstore_id, store, result_data)
    updated = await db.webstore_stripe_connect_records.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "record_type": "connected_account"},
        {"_id": 0},
    )
    authority = _provider_authority_from_record(updated, settings)
    status = provider_configuration_status(settings, authority)
    await db.webstores.update_one(
        {"tenant_id": user["tenant_id"], "id": webstore_id, "status": "live"},
        {"$set": {"checkout_enabled": bool(status["provider_authority"]), "updated_at": _now_iso()}},
    )
    return {"status": status, "result": {"ok": True, "code": result.code, **_safe_provider_result(result_data)}}

__all__ = [name for name in globals() if not name.startswith("__")]
