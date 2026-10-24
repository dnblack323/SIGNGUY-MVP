"""Private Realtime lifecycle over canonical Assistant and Gateway records."""

import asyncio
import hashlib
import json
import re
import uuid
from datetime import timedelta

from pymongo import ReturnDocument

from ..core.config import get_settings
from ..core.db import db
from ..core.time_utils import prepare_for_mongo, utc_now
from ..models.business_assistant import AssistantVoiceSession
from . import (
    ai_gateway,
    ai_gateway_execution,
    assistant_context,
    assistant_personality,
    assistant_tools,
    openai_realtime_provider,
)

RUNTIMES = {}
WORKER_ID = uuid.uuid4().hex
_reaper = None
TERMINAL = {"ended", "failed", "recovery_required"}


def configured() -> bool:
    s = get_settings()
    return bool(
        s.assistant_realtime_enabled
        and s.openai_realtime_enabled
        and s.openai_api_key
        and s.assistant_voice_model_profile_id
    )


async def actor(user: dict, refs=(), signature=None) -> dict:
    from .business_assistant import assert_assistant_access

    current = await assistant_context.fresh_actor(user)
    await assert_assistant_access(current)
    if signature and assistant_context.permission_signature(current) != signature:
        raise assistant_tools.ToolError("Permissions changed; voice session ended")
    for ref in refs:
        if not await assistant_tools.reference_allowed(current, ref):
            raise assistant_tools.ToolError(
                "Source access changed; voice session ended"
            )
    return current


async def start(user: dict, fields: dict) -> dict:
    from . import business_assistant as svc
    from .assistant_voice_runtime import VoiceRuntime

    user = await actor(user)
    if not configured():
        raise svc.BusinessAssistantError(
            "voice_not_configured",
            "Voice is not enabled with an allowed model, sourced rates and budgets. Text remains available.",
            503,
        )
    offer = fields.get("offer_sdp", "")
    key = fields.get("idempotency_key", "")
    if (
        not isinstance(offer, str)
        or not offer.startswith("v=0")
        or len(offer) > 64000
        or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", key)
    ):
        raise svc.BusinessAssistantError(
            "invalid_voice_request",
            "Use a bounded media SDP offer and stable request key",
            422,
        )
    # No browser control channel: only authenticated backend sideband may create
    # Responses, change session policy, submit tool outputs or report usage.
    if (
        "m=application" in offer.lower()
        or "sctp" in offer.lower()
        or "m=video" in offer.lower()
        or "m=audio" not in offer.lower()
    ):
        raise svc.BusinessAssistantError(
            "voice_media_only",
            "Voice accepts audio-only SDP without a browser data channel",
            422,
        )
    convo = await svc._conversation(
        user, fields.get("conversation_id"), mode=fields.get("mode")
    )
    scope = {"tenant_id": user["tenant_id"], "user_id": user["id"]}
    session_id = uuid.uuid5(
        uuid.NAMESPACE_URL, f"voice:{user['tenant_id']}:{user['id']}:{key}"
    ).hex
    fingerprint = hashlib.sha256(
        json.dumps(fields, sort_keys=True).encode()
    ).hexdigest()
    prior = await db.assistant_voice_sessions.find_one(
        {**scope, "id": session_id}, {"_id": 0}
    )
    if prior:
        if (
            prior.get("metadata", {}).get("fingerprint") == fingerprint
            and prior.get("status") == "active"
            and prior.get("metadata", {}).get("answer_sdp")
        ):
            await actor(
                user,
                prior["metadata"].get("dependencies", []),
                prior["metadata"].get("permission_signature"),
            )
            return {
                "configured": True,
                "session_id": session_id,
                "conversation_id": convo["id"],
                "answer_sdp": prior["metadata"]["answer_sdp"],
                "voice": prior["voice"],
            }
        raise svc.BusinessAssistantError(
            "voice_request_recorded",
            "This voice request is already recorded and will not be dispatched again",
            409,
        )
    lock_key = f"voice:{session_id}"
    locked = await db.assistant_conversations.find_one_and_update(
        {**scope, "id": convo["id"], "active_turn": {"$exists": False}},
        {"$set": {"active_turn": lock_key}},
        return_document=ReturnDocument.AFTER,
    )
    if not locked:
        raise svc.BusinessAssistantError(
            "assistant_turn_busy",
            "End the current text/voice turn before starting another",
            409,
        )
    settings = get_settings()
    action = profile = runtime = None
    dispatched = False
    row = None
    try:
        prefs_result = await svc.get_preferences(user)
        prefs = prefs_result["preferences"]
        context = await svc._validate_context(
            user,
            fields.get("context") or convo.get("active_context") or {},
            conversation_id=convo["id"],
            mode=svc._mode_key(fields.get("mode")),
        )
        messages, refs, memory = await assistant_context.inputs(
            user, convo["id"], settings.assistant_max_history_messages, context
        )
        messages.append({"role": "user", "content": json.dumps(memory)})
        instructions = assistant_personality.instructions(prefs)
        # Realtime's wire schema lacks Responses API's strict flag. The schema
        # and backend validator still come from the one shared tool registry.
        tools = [
            {k: v for k, v in tool.items() if k != "strict"}
            for tool in assistant_tools.tool_definitions(user)
        ]
        instruction_bytes = len(
            json.dumps({"instructions": instructions, "tools": tools}).encode()
        )
        while (
            len(json.dumps(messages).encode()) + instruction_bytes
            > settings.assistant_max_context_bytes
            and len(messages) > 1
        ):
            messages.pop(0)
        if (
            instruction_bytes > 16000
            or len(json.dumps(messages).encode()) + instruction_bytes
            > settings.assistant_max_context_bytes
        ):
            raise assistant_tools.ToolError(
                "Voice context is too large; narrow the conversation"
            )
        # Validate compatibility before reserving or contacting a provider.
        model = await db.ai_model_profiles.find_one(
            {"id": settings.assistant_voice_model_profile_id, "status": "active"},
            {"_id": 0},
        )
        metadata = (model or {}).get("metadata") or {}
        if (
            not model
            or model.get("model_key") != settings.openai_realtime_model
            or model["model_key"] != "gpt-realtime-2.1"
            or prefs_result["effective_voice"]
            not in metadata.get("supported_voices", [])
            or metadata.get("transcription_model")
            not in {"gpt-transcribe", "whisper-1"}
        ):
            raise svc.BusinessAssistantError(
                "voice_model_incompatible",
                "Configure the current compatible Realtime model, supported voices and transcription profile",
                409,
            )
        row = AssistantVoiceSession(
            id=session_id,
            **scope,
            conversation_id=convo["id"],
            status="created",
            model_key=model["model_key"],
            voice=prefs_result["effective_voice"],
        ).model_dump()
        row["metadata"] = {
            "request_key": key,
            "fingerprint": fingerprint,
            "lock_key": lock_key,
            "worker_id": WORKER_ID,
            "mode": svc._mode_key(fields.get("mode")),
            "permission_signature": assistant_context.permission_signature(user),
            "dependencies": refs,
            "record_references": memory["record_references"],
            "state": "connecting",
            "stop_requested": False,
            "client_seen_at": utc_now().isoformat(),
            "lease_expires_at": (utc_now() + timedelta(seconds=45)).isoformat(),
            "expires_at": (
                utc_now() + timedelta(seconds=settings.assistant_voice_max_seconds)
            ).isoformat(),
        }
        await db.assistant_voice_sessions.insert_one(prepare_for_mongo(row))
        action, profile, created = await ai_gateway_execution.begin(
            user,
            key=f"voice:{key}",
            fingerprint=fingerprint,
            conversation_id=convo["id"],
            profile_id=model["id"],
            max_input=settings.assistant_voice_context_tokens + instruction_bytes,
            max_output=settings.assistant_voice_max_output_tokens,
            max_calls=settings.assistant_voice_max_responses,
            capability_key="assistant.voice_reply",
            voice_seconds=settings.assistant_voice_max_seconds,
        )
        if not created:
            raise svc.BusinessAssistantError(
                "voice_request_recorded",
                "Voice accounting is already recorded; no redispatch",
                409,
            )
        row["metadata"].update(
            action_id=action["id"],
            pricing_profile={
                "id": profile["id"],
                "model_key": profile["model_key"],
                "metadata": {
                    k: profile["metadata"][k]
                    for k in (
                        "realtime_pricing",
                        "pricing_source",
                        "input_usd_per_million_tokens",
                        "output_usd_per_million_tokens",
                    )
                },
            },
            response_limit=settings.assistant_voice_max_responses,
        )
        await db.assistant_voice_sessions.update_one(
            {**scope, "id": session_id}, {"$set": {"metadata": row["metadata"]}}
        )
        runtime = VoiceRuntime(user, row, action, profile, prefs, refs)
        RUNTIMES[session_id] = runtime
        renewed = await db.assistant_voice_sessions.update_one(
            {
                **scope,
                "id": session_id,
                "status": "created",
                "metadata.lease_expires_at": {"$gt": utc_now().isoformat()},
            },
            {
                "$set": {
                    "metadata.lease_expires_at": (
                        utc_now() + timedelta(seconds=45)
                    ).isoformat()
                }
            },
        )
        if not renewed.matched_count:
            raise svc.BusinessAssistantError(
                "voice_start_expired",
                "Voice setup expired safely; start a new session",
                409,
            )
        await db.ai_action_requests.update_one(
            {**scope, "id": action["id"]}, {"$set": {"provider_dispatch_count": 1}}
        )
        session = {
            "type": "realtime",
            "model": model["model_key"],
            "instructions": instructions,
            "tools": tools,
            "tool_choice": "auto",
            "output_modalities": ["audio"],
            "max_output_tokens": settings.assistant_voice_max_output_tokens,
            "audio": {
                "input": {
                    "transcription": {"model": metadata["transcription_model"]},
                    "turn_detection": {
                        "type": "server_vad",
                        "create_response": False,
                        "interrupt_response": True,
                    },
                },
                "output": {"voice": row["voice"]},
            },
            "truncation": {
                "type": "retention_ratio",
                "retention_ratio": 0.8,
                "token_limits": {
                    "post_instructions": settings.assistant_voice_context_tokens
                },
            },
        }
        dispatched = True
        answer, call_id = await asyncio.wait_for(
            openai_realtime_provider.create_call(offer, session),
            timeout=min(15, max(1, settings.openai_realtime_timeout_seconds)),
        )
        row["provider_session_id"] = call_id
        await db.assistant_voice_sessions.update_one(
            {**scope, "id": session_id}, {"$set": {"provider_session_id": call_id}}
        )
        runtime.ws = await asyncio.wait_for(
            openai_realtime_provider.attach(call_id), timeout=12
        )
        await asyncio.wait_for(seed_history(runtime, messages), timeout=5)
        await db.assistant_voice_sessions.update_one(
            {**scope, "id": session_id},
            {
                "$set": {
                    "status": "active",
                    "metadata.answer_sdp": answer,
                    "metadata.state": "listening",
                    "started_at": utc_now().isoformat(),
                }
            },
        )
        runtime.start_tasks()
        return {
            "configured": True,
            "session_id": session_id,
            "conversation_id": convo["id"],
            "answer_sdp": answer,
            "voice": row["voice"],
            "max_seconds": settings.assistant_voice_max_seconds,
        }
    except Exception as exc:
        if runtime:
            await runtime.close("connection_failed", uncertain=dispatched)
        else:
            if row:
                await db.assistant_voice_sessions.update_one(
                    {**scope, "id": session_id},
                    {
                        "$set": {
                            "status": "failed",
                            "unavailable_reason": "Voice admission failed",
                        }
                    },
                )
            await release_conversation(user, convo["id"], lock_key)
        if isinstance(
            exc,
            (
                svc.BusinessAssistantError,
                ai_gateway.AIGatewayError,
                assistant_tools.ToolError,
            ),
        ):
            raise
        raise svc.BusinessAssistantError(
            "voice_connection_failed",
            "Voice connection failed safely. No automatic paid retry was sent; text remains available.",
            502,
        ) from exc


async def seed_history(runtime, messages):
    for message in messages:
        await runtime.send(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": message["role"],
                    "content": [
                        {
                            "type": (
                                "output_text"
                                if message["role"] == "assistant"
                                else "input_text"
                            ),
                            "text": message["content"],
                        }
                    ],
                },
            }
        )


async def release_conversation(user: dict, conversation_id: str, lock_key: str):
    await db.assistant_conversations.update_one(
        {
            "tenant_id": user["tenant_id"],
            "user_id": user["id"],
            "id": conversation_id,
            "active_turn": lock_key,
        },
        {"$unset": {"active_turn": ""}},
    )


async def owned(user: dict, session_id: str) -> dict:
    from .business_assistant import BusinessAssistantError

    await actor(user)
    row = await db.assistant_voice_sessions.find_one(
        {"tenant_id": user["tenant_id"], "user_id": user["id"], "id": session_id},
        {"_id": 0},
    )
    if not row:
        raise BusinessAssistantError(
            "voice_session_not_found", "Voice session not found", 404
        )
    return row


async def status(user: dict, session_id: str) -> dict:
    row = await owned(user, session_id)
    await actor(
        user,
        row["metadata"].get("dependencies", []),
        row["metadata"].get("permission_signature"),
    )
    await db.assistant_voice_sessions.update_one(
        {"tenant_id": user["tenant_id"], "user_id": user["id"], "id": session_id},
        {"$set": {"metadata.client_seen_at": utc_now().isoformat()}},
    )
    return {
        "session_id": session_id,
        "conversation_id": row["conversation_id"],
        "status": row["status"],
        "state": row["metadata"].get("state", row["status"]),
        "reason": row.get("unavailable_reason"),
        "voice": row["voice"],
        "revision": row["metadata"].get("revision", 0),
        "expires_at": row["metadata"].get("expires_at"),
    }


async def control(user: dict, session_id: str, operation: str) -> dict:
    row = await owned(user, session_id)
    if row["status"] in TERMINAL:
        return {"status": row["status"]}
    await db.assistant_voice_sessions.update_one(
        {"tenant_id": user["tenant_id"], "user_id": user["id"], "id": session_id},
        {"$set": {f"metadata.{operation}_requested": True}},
    )
    runtime = RUNTIMES.get(session_id)
    if runtime and operation == "stop":
        await runtime.close("user_ended")
    for _ in range(20 if operation == "stop" else 1):
        current = await owned(user, session_id)
        if current["status"] in TERMINAL:
            return {"status": current["status"]}
        if operation == "stop":
            await asyncio.sleep(0.2)
    return {"status": "ending" if operation == "stop" else "interrupting"}


async def recover_expired():
    """Any worker can terminate expired leases. Never create/retry a provider call."""
    query = {
        "status": {"$in": ["created", "active", "termination_pending"]},
        "metadata.lease_expires_at": {"$lt": utc_now().isoformat()},
    }
    async for row in db.assistant_voice_sessions.find(query, {"_id": 0}).limit(20):
        claimed = await db.assistant_voice_sessions.find_one_and_update(
            {"tenant_id": row["tenant_id"], "id": row["id"], **query},
            {
                "$set": {
                    "metadata.lease_expires_at": (
                        utc_now() + timedelta(seconds=15)
                    ).isoformat()
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if not claimed:
            continue
        user = {"id": row["user_id"], "tenant_id": row["tenant_id"]}
        try:
            if row.get(
                "provider_session_id"
            ) and not await openai_realtime_provider.hangup(row["provider_session_id"]):
                continue
            action = await db.ai_action_requests.find_one(
                {
                    **{"tenant_id": row["tenant_id"], "user_id": row["user_id"]},
                    "id": row["metadata"].get("action_id"),
                },
                {"_id": 0},
            )
            if action:
                await ai_gateway_execution.finish(
                    user,
                    action,
                    row["metadata"]["pricing_profile"],
                    succeeded=False,
                    uncertain=True,
                )
            await db.assistant_voice_sessions.update_one(
                {"tenant_id": row["tenant_id"], "id": row["id"]},
                {
                    "$set": {
                        "status": "recovery_required",
                        "unavailable_reason": "Interrupted server session terminated; incomplete usage requires reconciliation",
                    }
                },
            )
            await release_conversation(
                user, row["conversation_id"], row["metadata"]["lock_key"]
            )
        except Exception:
            # Keep the lease/liability for a bounded next recovery attempt.
            continue


async def start_recovery():
    global _reaper

    async def run():
        while True:
            try:
                await recover_expired()
            except Exception:
                pass
            await asyncio.sleep(3)

    _reaper = asyncio.create_task(run())


async def shutdown():
    if _reaper:
        _reaper.cancel()
        await asyncio.gather(_reaper, return_exceptions=True)
    await asyncio.gather(
        *(
            runtime.close("server_shutdown", uncertain=True)
            for runtime in list(RUNTIMES.values())
        ),
        return_exceptions=True,
    )
