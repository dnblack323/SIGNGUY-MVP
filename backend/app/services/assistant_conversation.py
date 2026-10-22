"""One private text/tool conversation path, ready for future voice reuse."""

import hashlib
import json
import re

import httpx
from pymongo import ReturnDocument

from ..core.config import get_settings
from ..core.db import db
from . import (
    ai_gateway,
    ai_gateway_execution,
    assistant_context,
    assistant_personality,
    assistant_tools,
    openai_assistant_provider,
)


async def ask(user: dict, fields: dict) -> dict:
    from . import business_assistant as svc

    await svc.assert_assistant_access(user)
    user = await assistant_context.fresh_actor(user)
    await svc.assert_assistant_access(user)
    prompt = str(fields.get("message") or "").strip()
    key = str(fields.get("idempotency_key") or "")
    if (
        not prompt
        or len(prompt) > 4000
        or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", key)
    ):
        raise svc.BusinessAssistantError(
            "invalid_assistant_request",
            "Use a message of 1–4000 characters and a stable request key",
            400,
        )
    scope = {"tenant_id": user["tenant_id"], "user_id": user["id"]}
    fingerprint = hashlib.sha256(
        json.dumps(
            {"input": fields, "access": assistant_context.permission_signature(user)},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    prior = await db.ai_action_requests.find_one(
        {**scope, "idempotency_key": f"assistant:{user['id']}:{key}"}, {"_id": 0}
    )
    conversation_id = fields.get("conversation_id") or (prior or {}).get("session_id")
    mode = svc._mode_key(fields.get("mode"))
    convo = await svc._conversation(user, conversation_id, mode=mode)
    context_fields = fields.get("context") or convo.get("active_context") or {}
    context = await svc._validate_context(
        user, context_fields, conversation_id=convo["id"], mode=mode
    )
    settings = get_settings()
    if (
        not settings.assistant_text_enabled
        or not settings.openai_api_key
        or not settings.assistant_text_model_profile_id
    ):
        raise svc.BusinessAssistantError(
            "assistant_not_configured",
            "Real assistant text is not configured. No AI request was sent.",
            503,
        )
    prefs = (await svc.get_preferences(user))["preferences"]
    signature = assistant_context.permission_signature(user)
    lock = await db.assistant_conversations.find_one_and_update(
        {**scope, "id": convo["id"], "active_turn": {"$exists": False}},
        {"$set": {"active_turn": key}},
        return_document=ReturnDocument.AFTER,
    )
    if not lock:
        raise svc.BusinessAssistantError(
            "assistant_turn_busy",
            "A turn is already pending. Retry with the same key after it completes.",
            409,
        )
    action = None
    profile = {}
    dispatch_count = 0
    finalized = False
    try:
        action, profile, created = await ai_gateway_execution.begin(
            user,
            key=key,
            fingerprint=fingerprint,
            conversation_id=convo["id"],
            profile_id=settings.assistant_text_model_profile_id,
            max_input=settings.assistant_max_context_bytes + 1024,
            max_output=settings.assistant_max_output_tokens,
            max_calls=settings.assistant_max_provider_calls,
        )
        if not created:
            if action.get("status") == "succeeded" and action.get("assistant_result"):
                saved = action["assistant_result"]
                dependencies = (
                    saved.get("assistant_message", {})
                    .get("metadata", {})
                    .get("sources", [])
                )
                for ref in dependencies or saved.get("sources", []):
                    if not await assistant_tools.reference_allowed(user, ref):
                        raise svc.BusinessAssistantError(
                            "assistant_retry_access_changed",
                            "Saved result access changed; start a new request",
                            409,
                        )
                return action["assistant_result"]
            raise svc.BusinessAssistantError(
                "assistant_request_pending_or_failed",
                "This request is already recorded; it will not be dispatched or charged again.",
                409,
            )
        inputs, refs, prompt_data = await assistant_context.inputs(
            user, convo["id"], settings.assistant_max_history_messages, context
        )
        if context:
            await db.assistant_conversations.update_one(
                {**scope, "id": convo["id"]},
                {
                    "$set": {
                        "active_context": {
                            "source_entity_type": context["source_entity_type"],
                            "source_entity_id": context["source_entity_id"],
                        }
                    }
                },
            )
        dependencies = {(ref["source_type"], ref["source_id"]): ref for ref in refs}
        prompt_data["user_message"] = prompt
        inputs.append({"role": "user", "content": json.dumps(prompt_data)})
        user_msg = await svc._insert_message(
            user,
            conversation_id=convo["id"],
            role="user",
            content_text=prompt,
            mode=mode,
            metadata={
                "permission_signature": signature,
                "sources": context.get("source_links", []) if context else [],
            },
        )
        sources = []
        missing = []
        answer = ""
        for _ in range(settings.assistant_max_provider_calls):
            current = await assistant_context.fresh_actor(user)
            await svc.assert_assistant_access(current)
            if assistant_context.permission_signature(current) != signature:
                raise assistant_tools.ToolError(
                    "Permissions changed during this turn; start a new request"
                )
            payload = {
                "model": profile["model_key"],
                "instructions": assistant_personality.instructions(prefs),
                "input": inputs,
                "tools": assistant_tools.tool_definitions(current),
                "store": False,
                "max_output_tokens": settings.assistant_max_output_tokens,
                "parallel_tool_calls": False,
            }
            # Bytes give a conservative token bound; never silently truncate a tool call/output pair.
            while (
                len(json.dumps(payload, ensure_ascii=True).encode())
                > settings.assistant_max_context_bytes
                and len(inputs) > 1
                and "type" not in inputs[0]
            ):
                inputs.pop(0)
            if (
                len(json.dumps(payload, ensure_ascii=True).encode())
                > settings.assistant_max_context_bytes
            ):
                raise assistant_tools.ToolError(
                    "Context limit reached; narrow the question or start a new conversation"
                )
            await db.ai_action_requests.update_one(
                {**scope, "id": action["id"]}, {"$inc": {"provider_dispatch_count": 1}}
            )
            dispatch_count += 1
            response = await openai_assistant_provider.respond(payload)
            if not isinstance(response, dict) or not isinstance(
                response.get("output"), list
            ):
                raise assistant_tools.ToolError("Invalid provider response")
            await ai_gateway_execution.observe(user, action, response)
            output = response.get("output") or []
            if any(not isinstance(item, dict) for item in output):
                raise assistant_tools.ToolError("Invalid provider output")
            if response.get("status") not in {None, "completed"}:
                raise assistant_tools.ToolError(
                    "The provider did not complete its response"
                )
            calls = [item for item in output if item.get("type") == "function_call"]
            if len(calls) > 4:
                raise assistant_tools.ToolError("Tool-call limit exceeded")
            if not calls:
                answer = "\n".join(
                    part.get("text", "")
                    for item in output
                    if item.get("type") == "message"
                    for part in item.get("content", [])
                    if part.get("type") == "output_text"
                ).strip()
                if not answer:
                    raise assistant_tools.ToolError("The provider returned no answer")
                break
            inputs.extend(output)
            for call in calls:
                current = await assistant_context.fresh_actor(user)
                if assistant_context.permission_signature(current) != signature:
                    raise assistant_tools.ToolError(
                        "Permissions changed during the turn"
                    )
                try:
                    args = json.loads(call.get("arguments") or "{}")
                    result = await assistant_tools.execute(
                        current, call["name"], args, timezone_name=prefs["timezone"]
                    )
                except (ValueError, assistant_tools.ToolError):
                    result = {
                        "error": "Tool unavailable, invalid arguments, or not permitted. Clarify the request; do not invent facts."
                    }
                for ref in result.get("sources", []):
                    if ref not in sources:
                        sources.append(ref)
                    dependencies[(ref["source_type"], ref["source_id"])] = ref
                if len(dependencies) > 100:
                    raise assistant_tools.ToolError(
                        "Source context limit reached; narrow the question"
                    )
                missing.extend(result.get("missing_data", []))
                inputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call["call_id"],
                        "output": json.dumps(result, default=str),
                    }
                )
        if not answer:
            raise assistant_tools.ToolError(
                "Conversation request limit reached; narrow the question"
            )
        # Permissions are checked after model completion too, before returning any generated text.
        current = await assistant_context.fresh_actor(user)
        await svc.assert_assistant_access(current)
        if assistant_context.permission_signature(current) != signature:
            raise assistant_tools.ToolError("Permissions changed during the turn")
        if any(
            [
                not await assistant_tools.reference_allowed(current, ref)
                for ref in dependencies.values()
            ]
        ):
            raise assistant_tools.ToolError("Source access changed during the turn")
        citations = [
            await svc._create_citation(
                user["tenant_id"], conversation_id=convo["id"], **ref
            )
            for ref in sources
        ]
        assistant_msg = await svc._insert_message(
            user,
            conversation_id=convo["id"],
            role="assistant",
            content_text=answer,
            mode=mode,
            citation_ids=[c["id"] for c in citations],
            action_request_id=action["id"],
            metadata={
                "permission_signature": signature,
                "sources": list(dependencies.values()),
                "personality_key": prefs["personality_key"],
                "personality_version": assistant_personality.VERSION,
                "missing_data": list(dict.fromkeys(missing)),
            },
        )
        result = {
            "conversation": {k: v for k, v in convo.items() if k != "active_turn"},
            "user_message": user_msg,
            "assistant_message": assistant_msg,
            "answer": answer,
            "sources": citations,
            "missing_data": list(dict.fromkeys(missing)),
            "action_request": {"id": action["id"], "capability_key": "assistant.chat"},
            "credit_display": svc.CREDIT_DISPLAY,
        }
        # Persist result before finalization: incomplete accounting can never cause redispatch.
        await db.ai_action_requests.update_one(
            {**scope, "id": action["id"]}, {"$set": {"assistant_result": result}}
        )
        await ai_gateway_execution.finish(user, action, profile, succeeded=True)
        finalized = True
        await svc._audit(
            user,
            "assistant.message_answered",
            "assistant_conversation",
            convo["id"],
            "Provider-backed assistant turn completed",
        )
        return result
    except ai_gateway.AIGatewayError as exc:
        raise svc.BusinessAssistantError(exc.code, exc.detail, exc.status_code) from exc
    except (
        httpx.HTTPError,
        assistant_tools.ToolError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        RuntimeError,
    ) as exc:
        raise svc.BusinessAssistantError(
            "assistant_response_failed",
            "Assistant could not complete this request. Its request key prevents duplicate paid dispatch. Check configuration or narrow the question.",
            502,
        ) from exc
    finally:
        try:
            if action and profile and not finalized:
                await ai_gateway_execution.finish(
                    user,
                    action,
                    profile,
                    succeeded=False,
                    uncertain=dispatch_count > len(action["provider_attempts"]),
                )
        finally:
            await db.assistant_conversations.update_one(
                {**scope, "id": convo["id"], "active_turn": key},
                {"$unset": {"active_turn": ""}},
            )
