"""Real-provider lifecycle extension of EC16; uses its canonical ledgers and credits."""

from decimal import Decimal, InvalidOperation, ROUND_CEILING
from datetime import timedelta
import uuid

from pymongo import ReturnDocument

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.ai_gateway import (
    AIActionRequest,
    AIProviderCostLedgerEntry,
    AIUsageLedgerEntry,
)
from . import ai_gateway as gateway


def rates(profile: dict) -> tuple[Decimal, Decimal]:
    metadata = profile.get("metadata") or {}
    try:
        values = tuple(
            Decimal(str(metadata[k]))
            for k in ("input_usd_per_million_tokens", "output_usd_per_million_tokens")
        )
        if not metadata.get("pricing_source") or any(
            not v.is_finite() or v <= 0 for v in values
        ):
            raise ValueError()
        return values
    except (KeyError, InvalidOperation, ValueError):
        raise gateway.AIGatewayError(
            "assistant_rates_missing",
            "Configure sourced model input/output rates before paid execution",
            409,
        )


def estimate(profile: dict, input_tokens: int, output_tokens: int) -> int:
    incoming, outgoing = rates(profile)
    return int(
        (incoming * input_tokens + outgoing * output_tokens).to_integral_value(
            rounding=ROUND_CEILING
        )
    )


def realtime_rates(profile: dict) -> dict[str, Decimal]:
    try:
        metadata = profile["metadata"]
        raw = metadata["realtime_pricing"]
        keys = (
            "input_text",
            "input_audio",
            "cached_text",
            "cached_audio",
            "output_text",
            "output_audio",
            "transcription_usd_per_minute",
        )
        values = {k: Decimal(str(raw[k])) for k in keys}
        if (
            not metadata.get("pricing_source")
            or any(not v.is_finite() or v < 0 for v in values.values())
            or any(
                values[k] <= 0
                for k in (
                    "input_text",
                    "input_audio",
                    "output_text",
                    "output_audio",
                    "transcription_usd_per_minute",
                )
            )
        ):
            raise ValueError()
        return values
    except (KeyError, TypeError, InvalidOperation, ValueError):
        raise gateway.AIGatewayError(
            "voice_rates_missing",
            "Configure sourced text/audio/cache and transcription rates before voice",
            409,
        )


def realtime_cost(profile: dict, usage: dict) -> int:
    """Estimate money from observed modality counts; never label it actual billing."""
    rates_map = realtime_rates(profile)
    if usage.get("type") == "duration":
        seconds = Decimal(str(usage["seconds"]))
        if not seconds.is_finite() or seconds < 0:
            raise ValueError("Invalid transcription duration")
        cost = seconds * rates_map["transcription_usd_per_minute"] * 1000000 / 60
    else:
        incoming = usage["input_token_details"]
        outgoing = usage["output_token_details"]
        cached = incoming.get("cached_tokens_details") or {}
        if any(
            type(part.get(k)) is not int or part[k] < 0
            for part in (incoming, outgoing)
            for k in ("text_tokens", "audio_tokens")
        ):
            raise ValueError("Missing modality usage")
        if (
            incoming["text_tokens"] + incoming["audio_tokens"] != usage["input_tokens"]
            or outgoing["text_tokens"] + outgoing["audio_tokens"]
            != usage["output_tokens"]
        ):
            raise ValueError("Incomplete modality usage")
        if incoming.get("cached_tokens", 0) != sum(
            cached.get(k, 0) for k in ("text_tokens", "audio_tokens")
        ):
            raise ValueError("Incomplete cached usage")
        cost = Decimal(0)
        for name in ("text", "audio"):
            c = cached.get(f"{name}_tokens", 0)
            n = incoming[f"{name}_tokens"]
            if type(c) is not int or not 0 <= c <= n:
                raise ValueError("Invalid cached usage")
            cost += (
                (n - c) * rates_map[f"input_{name}"]
                + c * rates_map[f"cached_{name}"]
                + outgoing[f"{name}_tokens"] * rates_map[f"output_{name}"]
            )
    return int(cost.to_integral_value(rounding=ROUND_CEILING))


async def begin(
    user: dict,
    *,
    key: str,
    fingerprint: str,
    conversation_id: str,
    profile_id: str,
    max_input: int,
    max_output: int,
    max_calls: int,
    capability_key: str = "assistant.chat",
    voice_seconds: int = 0,
) -> tuple[dict, dict, bool]:
    scope = {"tenant_id": user["tenant_id"], "user_id": user["id"]}
    ledger_key = f"assistant:{user['id']}:{key}"
    existing = await db.ai_action_requests.find_one(
        {**scope, "idempotency_key": ledger_key}, {"_id": 0}
    )
    if existing:
        if existing.get("input_fingerprint") != fingerprint:
            raise gateway.AIGatewayError(
                "assistant_retry_conflict",
                "This request key belongs to different input",
                409,
            )
        return existing, {}, False
    capability = await db.ai_capabilities.find_one(
        {"capability_key": capability_key, "status": "active"}, {"_id": 0}
    )
    if not capability:
        raise gateway.AIGatewayError(
            "capability_not_available", "Assistant capability is not active", 409
        )
    profile = await gateway._select_model_profile(capability, profile_id)
    voice_reserve = 0
    if capability_key == "assistant.voice_reply":
        pricing = realtime_rates(profile)
        profile = {
            **profile,
            "metadata": {
                **profile["metadata"],
                "input_usd_per_million_tokens": str(
                    max(
                        pricing[k]
                        for k in (
                            "input_text",
                            "input_audio",
                            "cached_text",
                            "cached_audio",
                        )
                    )
                ),
                "output_usd_per_million_tokens": str(
                    max(pricing["output_text"], pricing["output_audio"])
                ),
            },
        }
        voice_reserve = int(
            (
                pricing["transcription_usd_per_minute"]
                * (voice_seconds + max_calls + 1)
                * 1000000
                / 60
            ).to_integral_value(rounding=ROUND_CEILING)
        )
    if profile.get("provider_key") != "openai":
        raise gateway.AIGatewayError(
            "assistant_provider_not_allowed",
            "The assistant requires an allowed OpenAI model profile",
            409,
        )
    charge = gateway._capability_credit_charge(capability)
    worst = (
        estimate(profile, max_input * max_calls, max_output * max_calls) + voice_reserve
    )
    if capability_key == "assistant.chat":
        from . import ai_text_pricing

        try:
            worst = (
                int(
                    ai_text_pricing.reserve(
                        profile, max_input, max_output
                    ).to_integral_value(rounding=ROUND_CEILING)
                )
                * max_calls
            )
        except ValueError as exc:
            raise gateway.AIGatewayError(
                "assistant_rates_missing",
                "Configure complete sourced text/cache/tier rates before execution",
                409,
            ) from exc
    policies = await gateway._active_policies(
        scope["tenant_id"], capability_key, profile_id
    )
    if not any(p.get("max_cost_micros_per_day") is not None for p in policies):
        raise gateway.AIGatewayError(
            "assistant_budget_missing",
            "Configure a provider spending limit before paid execution",
            409,
        )
    await gateway._ensure_credit_account(scope["tenant_id"])
    token = uuid.uuid4().hex
    lock = await db.ai_credit_accounts.find_one_and_update(
        {
            "tenant_id": scope["tenant_id"],
            "assistant_admission_lock": {"$exists": False},
        },
        {"$set": {"assistant_admission_lock": token}},
        return_document=ReturnDocument.AFTER,
    )
    if not lock:
        raise gateway.AIGatewayError(
            "assistant_admission_busy",
            "Another AI request is being admitted; retry with the same key",
            409,
        )
    action = None
    reserved = False
    try:
        # Recheck after the cross-process admission lock.
        existing = await db.ai_action_requests.find_one(
            {**scope, "idempotency_key": ledger_key}, {"_id": 0}
        )
        if existing:
            if existing.get("input_fingerprint") != fingerprint:
                raise gateway.AIGatewayError(
                    "assistant_retry_conflict",
                    "This request key belongs to different input",
                    409,
                )
            return existing, {}, False
        await gateway._enforce_governance(
            scope["tenant_id"], capability_key, profile_id, charge, worst
        )
        if capability_key == "assistant.voice_reply":
            from ..core.config import get_settings

            settings = get_settings()
            since = (
                utc_now()
                - timedelta(
                    seconds=max(1, settings.openai_realtime_rate_limit_window_seconds)
                )
            ).isoformat()
            recent = await db.ai_action_requests.count_documents(
                {
                    "tenant_id": scope["tenant_id"],
                    "capability_key": capability_key,
                    "created_at": {"$gte": since},
                }
            )
            if recent >= max(1, settings.openai_realtime_rate_limit_sessions):
                raise gateway.AIGatewayError(
                    "voice_rate_limit",
                    "Voice session start limit reached; continue in text or try later",
                    429,
                )
        action = AIActionRequest(
            **scope,
            capability_key=capability_key,
            feature_key="business_assistant",
            action_key="voice" if capability_key == "assistant.voice_reply" else "chat",
            provider_key="openai",
            model_key=profile["model_key"],
            model_profile_id=profile_id,
            session_id=conversation_id,
            idempotency_key=ledger_key,
            credit_charge_credits=charge,
            status="reserved",
        ).model_dump()
        action.update(
            input_fingerprint=fingerprint,
            provider_attempts=[],
            provider_usage_complete=True,
        )
        await db.ai_action_requests.insert_one(prepare_for_mongo(action))
        reserve = await gateway._reserve_credits(
            scope["tenant_id"], action["id"], charge, idempotency_key=ledger_key
        )
        reserved = True
        cost = AIProviderCostLedgerEntry(
            tenant_id=scope["tenant_id"],
            action_request_id=action["id"],
            provider_key="openai",
            model_key=profile["model_key"],
            estimated_cost_micros=worst,
            actual_cost_micros=None,
            status="estimated",
            reconciliation_status="reserved_maximum",
            idempotency_key=f"{ledger_key}:cost",
        ).model_dump()
        cost["pricing_snapshot"] = {
            k: profile["metadata"][k]
            for k in (
                "input_usd_per_million_tokens",
                "output_usd_per_million_tokens",
                "pricing_source",
            )
        }
        if capability_key == "assistant.voice_reply":
            cost["pricing_snapshot"]["realtime_pricing"] = profile["metadata"][
                "realtime_pricing"
            ]
        await db.ai_provider_cost_ledger_entries.insert_one(prepare_for_mongo(cost))
        action.update(
            status="executing",
            reserved_credit_ledger_entry_id=reserve["id"] if reserve else None,
            provider_cost_ledger_entry_id=cost["id"],
        )
        await db.ai_action_requests.update_one(
            {**scope, "id": action["id"]},
            {
                "$set": {
                    k: action[k]
                    for k in (
                        "status",
                        "reserved_credit_ledger_entry_id",
                        "provider_cost_ledger_entry_id",
                    )
                }
            },
        )
        return serialize_doc(action), profile, True
    except Exception:
        if action:
            if reserved:
                await gateway._release_credits(
                    scope["tenant_id"],
                    action["id"],
                    charge,
                    idempotency_key=ledger_key,
                    reason="admission_failed_before_dispatch",
                )
            await db.ai_action_requests.update_one(
                {**scope, "id": action["id"]}, {"$set": {"status": "blocked"}}
            )
        raise
    finally:
        await db.ai_credit_accounts.update_one(
            {"tenant_id": scope["tenant_id"], "assistant_admission_lock": token},
            {"$unset": {"assistant_admission_lock": ""}},
        )


async def observe(
    user: dict,
    action: dict,
    response: dict,
    *,
    estimated_cost_micros: int | None = None,
    usage_detail: dict | None = None,
    profile: dict | None = None,
) -> None:
    usage = response.get("usage") or {}
    if not isinstance(usage, dict):
        usage = {}
    event = response.get("id")
    valid = bool(event) and all(
        type(usage.get(k)) is int and usage[k] >= 0
        for k in ("input_tokens", "output_tokens")
    )
    attempt = {
        "provider_event_id": event,
        "input_tokens": usage.get("input_tokens") if valid else None,
        "output_tokens": usage.get("output_tokens") if valid else None,
        "usage_observed": valid,
    }
    if profile is not None:
        from . import ai_text_pricing

        try:
            amount, usage_detail = ai_text_pricing.cost(profile, response)
            estimated_cost_micros = int(
                amount.to_integral_value(rounding=ROUND_CEILING)
            )
            attempt["estimated_cost_micros_decimal"] = str(amount)
        except (ValueError, TypeError, ArithmeticError):
            action["provider_cost_complete"] = False
            usage_detail = {"provider_usage": usage, "cost_unavailable": True}
    if estimated_cost_micros is not None:
        attempt["estimated_cost_micros"] = estimated_cost_micros
    if usage_detail is not None:
        attempt["usage_detail"] = usage_detail
    if event and any(
        a.get("provider_event_id") == event for a in action["provider_attempts"]
    ):
        raise gateway.AIGatewayError(
            "duplicate_provider_event",
            "Duplicate provider response; no repeated accounting",
            502,
        )
    action["provider_attempts"].append(attempt)
    action["provider_usage_complete"] &= valid
    await db.ai_action_requests.update_one(
        {"tenant_id": user["tenant_id"], "user_id": user["id"], "id": action["id"]},
        {
            "$set": {
                "provider_attempts": action["provider_attempts"],
                "provider_usage_complete": action["provider_usage_complete"],
                "provider_cost_complete": action.get("provider_cost_complete", True),
            }
        },
    )
    if profile is not None and action.get("provider_cost_complete", True):
        observed = sum(
            a.get("estimated_cost_micros", 0) for a in action["provider_attempts"]
        )
        cost_row = await db.ai_provider_cost_ledger_entries.find_one(
            {
                "tenant_id": user["tenant_id"],
                "id": action["provider_cost_ledger_entry_id"],
            },
            {"_id": 0},
        )
        if cost_row and observed > cost_row["estimated_cost_micros"]:
            await db.ai_provider_cost_ledger_entries.update_one(
                {"tenant_id": user["tenant_id"], "id": cost_row["id"]},
                {"$max": {"estimated_cost_micros": observed}},
            )
            raise gateway.AIGatewayError(
                "assistant_reservation_exceeded",
                "Observed provider usage exceeded its reservation; no further dispatch",
                502,
            )


async def finish(
    user: dict, action: dict, profile: dict, *, succeeded: bool, uncertain: bool = False
) -> None:
    scope = {"tenant_id": user["tenant_id"], "user_id": user["id"], "id": action["id"]}
    claim = await db.ai_action_requests.find_one_and_update(
        {**scope, "status": "executing", "finalizing": {"$ne": True}},
        {"$set": {"finalizing": True}},
        return_document=ReturnDocument.AFTER,
    )
    if not claim:
        return
    key = action["idempotency_key"]
    no_dispatch = not claim.get("provider_dispatch_count")
    complete = (
        bool(action["provider_attempts"])
        and action["provider_usage_complete"]
        and not uncertain
    )
    incoming = sum(a.get("input_tokens") or 0 for a in action["provider_attempts"])
    outgoing = sum(a.get("output_tokens") or 0 for a in action["provider_attempts"])
    usage = AIUsageLedgerEntry(
        tenant_id=user["tenant_id"],
        user_id=user["id"],
        action_request_id=action["id"],
        capability_key=action["capability_key"],
        feature_key="business_assistant",
        action_key=action.get("action_key", "chat"),
        provider_key="openai",
        model_key=profile["model_key"],
        input_units=incoming,
        output_units=outgoing,
        status="final" if complete or no_dispatch else "estimated",
        result_status="succeeded" if succeeded else "failed",
        session_id=action["session_id"],
        credits_charged=action["credit_charge_credits"] if succeeded else 0,
        idempotency_key=f"{key}:usage",
    ).model_dump()
    usage.update(
        usage_source=(
            "no_provider_request"
            if no_dispatch
            else "provider_reported" if complete else "incomplete"
        ),
        provider_attempts=action["provider_attempts"],
    )
    try:
        await db.ai_usage_ledger_entries.insert_one(prepare_for_mongo(usage))
        cost_update = {
            "usage_ledger_entry_id": usage["id"],
            "input_units": incoming,
            "output_units": outgoing,
            "actual_cost_micros": None,
            "status": "estimated",
            "reconciliation_status": (
                "usage_reported_cost_estimated"
                if complete
                else "incomplete_reserved_maximum"
            ),
        }
        if complete and action.get("provider_cost_complete", True):
            cost_update["estimated_cost_micros"] = (
                int(
                    sum(
                        (
                            Decimal(
                                a.get(
                                    "estimated_cost_micros_decimal",
                                    str(a["estimated_cost_micros"]),
                                )
                            )
                            for a in action["provider_attempts"]
                        ),
                        Decimal(0),
                    ).to_integral_value(rounding=ROUND_CEILING)
                )
                if all(
                    "estimated_cost_micros" in a for a in action["provider_attempts"]
                )
                else estimate(profile, incoming, outgoing)
            )
        elif complete:
            cost_update["reconciliation_status"] = "unpriced_usage_reserved_maximum"
        elif no_dispatch:
            cost_update.update(
                estimated_cost_micros=0, reconciliation_status="no_dispatch"
            )
        await db.ai_provider_cost_ledger_entries.update_one(
            {
                "tenant_id": user["tenant_id"],
                "id": action["provider_cost_ledger_entry_id"],
            },
            {"$set": cost_update},
        )
        if succeeded:
            await gateway._commit_credits(
                user["tenant_id"],
                action["id"],
                action["credit_charge_credits"],
                idempotency_key=key,
            )
        else:
            await gateway._release_credits(
                user["tenant_id"],
                action["id"],
                action["credit_charge_credits"],
                idempotency_key=key,
                reason="assistant_failed",
            )
        await db.ai_action_requests.update_one(
            scope,
            {
                "$set": {
                    "status": "succeeded" if succeeded else "failed",
                    "usage_ledger_entry_id": usage["id"],
                    "provider_usage_complete": complete,
                    "updated_at": utc_now().isoformat(),
                }
            },
        )
    except Exception:
        # Fail closed. A finalization failure is never permission to redispatch or charge again.
        await db.ai_action_requests.update_one(
            scope, {"$set": {"finalization_incomplete": True}}
        )
        raise
