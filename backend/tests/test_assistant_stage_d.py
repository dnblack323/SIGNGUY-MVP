"""Stage D: real application services with strictly mocked paid transports."""

import asyncio
from copy import deepcopy
from datetime import timedelta
import json
import time
import uuid

import pytest
import pytest_asyncio

from app.core.db import db
from app.core.time_utils import utc_now
from app.services import assistant_realtime as voice, ai_gateway_execution as execution
from app.services import business_assistant as svc, openai_realtime_provider as provider
from app.services import assistant_context, assistant_personality
from tests.test_assistant_stage_b import ctx  # noqa: F401

OFFER = "v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"
RATES = {
    "input_text": "4",
    "input_audio": "32",
    "cached_text": "0.4",
    "cached_audio": "0.4",
    "output_text": "24",
    "output_audio": "64",
    "transcription_usd_per_minute": "0.006",
}
USAGE = {
    "input_tokens": 100,
    "output_tokens": 50,
    "input_token_details": {"text_tokens": 60, "audio_tokens": 40, "cached_tokens": 0},
    "output_token_details": {"text_tokens": 10, "audio_tokens": 40},
}


class Socket:
    def __init__(self):
        self.sent = []
        self.queue = asyncio.Queue()
        self.closed = False

    async def send(self, raw):
        self.sent.append(json.loads(raw))

    def __aiter__(self):
        return self

    async def __anext__(self):
        item = await self.queue.get()
        if item is None:
            raise StopAsyncIteration
        return json.dumps(item)

    async def close(self):
        self.closed = True
        await self.queue.put(None)


@pytest_asyncio.fixture
async def v(ctx, monkeypatch):
    settings = ctx["settings"]
    prior_capability = await db.ai_capabilities.find_one(
        {"capability_key": "assistant.voice_reply"}
    )
    await db.ai_governance_policies.update_one(
        {"tenant_id": ctx["tenant"]}, {"$set": {"max_cost_micros_per_day": 20000000}}
    )
    for key, value in {
        "assistant_realtime_enabled": True,
        "openai_realtime_enabled": True,
        "openai_realtime_model": "gpt-realtime-2.1",
        "assistant_voice_model_profile_id": ctx["profile"]["id"],
        "assistant_voice_max_responses": 4,
        "assistant_voice_max_seconds": 30,
        "assistant_voice_idle_seconds": 10,
    }.items():
        monkeypatch.setattr(settings, key, value)
    await db.ai_model_profiles.update_one(
        {"id": ctx["profile"]["id"]},
        {
            "$set": {
                "model_key": "gpt-realtime-2.1",
                "metadata.realtime_pricing": RATES,
                "metadata.supported_voices": [
                    "alloy",
                    "ash",
                    "coral",
                    "echo",
                    "sage",
                    "shimmer",
                ],
                "metadata.transcription_model": "whisper-1",
            }
        },
    )
    await db.ai_capabilities.update_one(
        {"capability_key": "assistant.voice_reply"},
        {
            "$set": {
                "capability_key": "assistant.voice_reply",
                "id": "voice-cap-" + ctx["tenant"],
                "status": "active",
                "billable": True,
                "default_credit_charge": 1,
                "feature_key": "business_assistant",
                "action_key": "voice",
                "entitlement_feature_key": "business_assistant",
                "allowed_model_profile_ids": [ctx["profile"]["id"]],
            }
        },
        upsert=True,
    )
    calls, hangups, sockets = [], [], []

    async def create(offer, session):
        calls.append(deepcopy(session))
        return "v=0\r\nmock-answer", f"rtc_{uuid.uuid4().hex}"

    async def attach(call_id):
        socket = Socket()
        sockets.append(socket)
        return socket

    async def hangup(call_id):
        hangups.append(call_id)
        return True

    monkeypatch.setattr(provider, "create_call", create)
    monkeypatch.setattr(provider, "attach", attach)
    monkeypatch.setattr(provider, "hangup", hangup)
    yield {**ctx, "voice_calls": calls, "hangups": hangups, "sockets": sockets}
    await voice.shutdown()
    await asyncio.sleep(0)
    await db.ai_capabilities.delete_one({"capability_key": "assistant.voice_reply"})
    if prior_capability:
        await db.ai_capabilities.insert_one(prior_capability)


async def start(v, **fields):
    convo = await svc.create_conversation(v["user"], {})
    fields = {
        "conversation_id": convo["id"],
        "offer_sdp": OFFER,
        "idempotency_key": uuid.uuid4().hex,
        **fields,
    }
    result = await voice.start(v["user"], fields)
    return result, voice.RUNTIMES[result["session_id"]], fields


async def utterance(runtime, text="What is the next step?", item="input1"):
    await runtime.handle({"type": "input_audio_buffer.committed", "item_id": item})
    await runtime.handle(
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "item_id": item,
            "transcript": text,
            "usage": {"type": "duration", "seconds": 2},
        }
    )


async def answer(
    runtime,
    text="Review the recorded status.",
    response="response1",
    status="completed",
    output=None,
    usage=USAGE,
):
    await runtime.handle({"type": "response.created", "response": {"id": response}})
    await runtime.handle(
        {
            "type": "response.done",
            "response": {
                "id": response,
                "status": status,
                "usage": deepcopy(usage),
                "output": (
                    output
                    if output is not None
                    else [
                        {
                            "type": "message",
                            "content": [{"type": "output_audio", "transcript": text}],
                        }
                    ]
                ),
            },
        }
    )


@pytest.mark.asyncio
async def test_shared_transcripts_context_private_history_and_duplicate_accounting(v):
    result, runtime, fields = await start(v)
    again = await voice.start(v["user"], fields)
    assert again["session_id"] == result["session_id"]
    assert len(v["voice_calls"]) == 1
    assert "mock-not-a-live-key" not in str(result)
    session = v["voice_calls"][0]
    assert session["audio"]["input"]["turn_detection"]["create_response"] is False
    assert {t["name"] for t in session["tools"]} == {
        "find_customers",
        "customer_history",
        "recent_orders",
        "work_order_status",
        "invoices",
        "quote_followups",
        "tasks",
        "shop_schedule",
    }
    await utterance(runtime)
    await answer(runtime)
    await runtime.handle(
        {"type": "response.done", "response": {"id": "response1", "usage": USAGE}}
    )  # duplicate delivery
    await runtime.close("user_ended")
    history = await svc.get_conversation(v["user"], result["conversation_id"])
    assert [m["role"] for m in history["messages"]] == ["user", "assistant"]
    assert all(
        m["metadata"]["transcript_source"] == "provider_sideband"
        for m in history["messages"]
    )
    messages, _, _ = await assistant_context.inputs(
        v["user"], result["conversation_id"], 20
    )
    assert any("Review the recorded status" in m["content"] for m in messages)
    _, resumed, _ = await start(v, conversation_id=result["conversation_id"])
    assert any("Review the recorded status" in str(e) for e in resumed.ws.sent)
    await resumed.close("user_ended")
    costs = await db.ai_provider_cost_ledger_entries.find_one(
        {"action_request_id": runtime.action["id"]}
    )
    assert costs["actual_cost_micros"] is None
    assert costs["estimated_cost_micros"] == 4520  # 4320 modality tokens + 200 ASR
    assert costs["reconciliation_status"] == "usage_reported_cost_estimated"
    assert (
        await db.ai_usage_ledger_entries.count_documents(
            {"action_request_id": runtime.action["id"]}
        )
        == 1
    )
    for user in (v["other"], v["foreign"]):
        with pytest.raises(svc.BusinessAssistantError):
            await voice.status(user, result["session_id"])
        with pytest.raises(svc.BusinessAssistantError):
            await svc.get_conversation(user, result["conversation_id"])
    with pytest.raises(svc.BusinessAssistantError):
        await voice.start(v["user"], fields)


@pytest.mark.asyncio
async def test_read_tools_links_and_fresh_permissions(v):
    order = {
        "id": uuid.uuid4().hex,
        "tenant_id": v["tenant"],
        "number": "O-42",
        "title": "Johnson truck wrap",
        "status": "production",
        "created_at": utc_now().isoformat(),
    }
    await db.orders.insert_one(order)
    result, runtime, _ = await start(v)
    await utterance(runtime, "What's happening with the Johnson truck wrap?")
    await answer(
        runtime,
        response="tool1",
        output=[
            {
                "type": "function_call",
                "name": "recent_orders",
                "call_id": "call1",
                "arguments": json.dumps({"query": "Johnson"}),
            }
        ],
    )
    tool_output = runtime.ws.sent[-2]["item"]["output"]
    assert "Johnson truck wrap" in tool_output and order["id"] in tool_output
    await answer(runtime, response="answer2", text="Order O-42 is in production.")
    history = await svc.get_conversation(v["user"], result["conversation_id"])
    assert (
        history["messages"][-1]["metadata"]["sources"][0]["route"]
        == f"/orders/{order['id']}"
    )
    await db.users.update_one(
        {"id": v["user"]["id"]},
        {"$set": {"role": "staff", "permissions": ["ai_assistant:use"]}},
    )
    with pytest.raises(Exception, match="Permissions changed|Source access"):
        await runtime.check()
    hidden = await svc.get_conversation(
        await assistant_context.fresh_actor(v["user"]), result["conversation_id"]
    )
    assert "Order O-42 is in production" not in str(hidden)
    await runtime.close("access_changed", uncertain=True)


@pytest.mark.asyncio
async def test_interruption_transcript_excluded_from_future_context(v):
    result, runtime, _ = await start(v)
    await utterance(runtime)
    await runtime.handle({"type": "output_audio_buffer.started"})
    await runtime.interrupt()
    await answer(
        runtime,
        status="cancelled",
        text="A response interrupted before complete playback.",
    )
    history = await svc.get_conversation(v["user"], result["conversation_id"])
    assert history["messages"][-1]["metadata"]["interrupted"] is True
    messages, _, _ = await assistant_context.inputs(
        v["user"], result["conversation_id"], 20
    )
    assert "before complete playback" not in str(messages)
    assert {e["type"] for e in runtime.ws.sent} >= {
        "response.cancel",
        "output_audio_buffer.clear",
    }
    await runtime.close("user_ended")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "personality",
    [
        "ops_partner",
        "wise_mentor",
        "cheerful_helper",
        "no_bs_direct",
        "sarcastic_funny",
    ],
)
async def test_saved_voice_independent_of_personality_in_provider_instructions(
    v, personality
):
    # Use the canonical catalog keys rather than creating voice-only personalities.
    await svc.update_preferences(
        v["user"], {"personality_key": personality, "voice": "ash"}
    )
    _, runtime, _ = await start(v)
    assert v["voice_calls"][-1]["audio"]["output"]["voice"] == "ash"
    assert v["voice_calls"][-1]["instructions"] == assistant_personality.instructions(
        (await svc.get_preferences(v["user"]))["preferences"]
    )
    assert (await svc.get_preferences(v["other"]))["preferences"]["voice"] != "ash"
    await runtime.close("user_ended")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change", ["duration", "idle", "client", "budget", "permission"]
)
async def test_watchdog_terminates_limits_and_permission_changes(v, change):
    result, runtime, _ = await start(v)
    if change == "duration":
        runtime.started = time.monotonic() - 100
    elif change == "idle":
        runtime.activity = time.monotonic() - 100
    elif change == "client":
        await runtime.update(
            client_seen_at=(utc_now() - timedelta(seconds=30)).isoformat()
        )
    elif change == "budget":
        await db.ai_governance_policies.update_one(
            {"tenant_id": v["tenant"]}, {"$set": {"max_cost_micros_per_day": 1}}
        )
    else:
        await db.users.update_one(
            {"id": v["user"]["id"]}, {"$set": {"is_active": False}}
        )
    for _ in range(25):
        if runtime.closing:
            break
        await asyncio.sleep(0.1)
    row = await db.assistant_voice_sessions.find_one({"id": result["session_id"]})
    assert row["status"] == "ended", row
    assert v["hangups"] and runtime.ws.closed


@pytest.mark.asyncio
async def test_missing_usage_failure_and_orphan_recovery_retain_liability(
    v, monkeypatch
):
    result, runtime, _ = await start(v)
    await utterance(runtime)
    await answer(runtime, usage={})
    row = await db.assistant_voice_sessions.find_one({"id": result["session_id"]})
    assert row["status"] == "ended" and row["unavailable_reason"] == "usage_incomplete"
    cost = await db.ai_provider_cost_ledger_entries.find_one(
        {"action_request_id": runtime.action["id"]}
    )
    assert (
        cost["reconciliation_status"] == "incomplete_reserved_maximum"
        and cost["estimated_cost_micros"] > 0
    )
    _, second, _ = await start(v)

    async def no_hangup(call_id):
        return False

    monkeypatch.setattr(provider, "hangup", no_hangup)
    await second.close("connection_failed", uncertain=True)
    row = await db.assistant_voice_sessions.find_one({"id": second.row["id"]})
    assert row["status"] == "termination_pending"
    assert await db.assistant_conversations.find_one(
        {"id": row["conversation_id"], "active_turn": {"$exists": True}}
    )

    async def yes_hangup(call_id):
        return True

    monkeypatch.setattr(provider, "hangup", yes_hangup)
    await voice.recover_expired()
    row = await db.assistant_voice_sessions.find_one({"id": second.row["id"]})
    assert row["status"] == "recovery_required"
    assert not await db.assistant_conversations.find_one(
        {"id": row["conversation_id"], "active_turn": {"$exists": True}}
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "offer",
    [
        "invalid",
        OFFER + "m=application 9 UDP/DTLS/SCTP webrtc-datachannel",
        OFFER + "m=video 9 UDP/TLS/RTP/SAVPF 96",
    ],
)
async def test_browser_cannot_send_control_channel(v, offer):
    with pytest.raises(svc.BusinessAssistantError):
        await start(v, offer_sdp=offer)
    assert not v["voice_calls"]


@pytest.mark.asyncio
async def test_provider_failure_no_automatic_retry_and_client_billing_rejected(
    v, monkeypatch
):
    async def failed(offer, session):
        raise TimeoutError("mock connection failure")

    monkeypatch.setattr(provider, "create_call", failed)
    with pytest.raises(svc.BusinessAssistantError, match="Voice connection failed"):
        await start(v)
    assert not voice.RUNTIMES
    with pytest.raises(svc.BusinessAssistantError):
        await svc.record_voice_usage(v["user"], "anything", {})


def test_modality_cached_and_transcription_cost_estimates():
    profile = {"metadata": {"pricing_source": "mock", "realtime_pricing": RATES}}
    usage = deepcopy(USAGE)
    usage["input_token_details"].update(
        cached_tokens=30, cached_tokens_details={"text_tokens": 10, "audio_tokens": 20}
    )
    assert execution.realtime_cost(profile, usage) == 3652
    assert execution.realtime_cost(profile, {"type": "duration", "seconds": 2}) == 200
    with pytest.raises(ValueError):
        execution.realtime_cost(profile, {**usage, "input_tokens": 101})


@pytest.mark.asyncio
@pytest.mark.parametrize("block", ["disabled", "rates", "model", "budget", "credits"])
async def test_admission_gates_before_any_provider_request(v, block):
    if block == "disabled":
        v["settings"].assistant_realtime_enabled = False
    elif block == "rates":
        await db.ai_model_profiles.update_one(
            {"id": v["profile"]["id"]}, {"$unset": {"metadata.realtime_pricing": ""}}
        )
    elif block == "model":
        await db.ai_model_profiles.update_one(
            {"id": v["profile"]["id"]}, {"$set": {"metadata.supported_voices": []}}
        )
    elif block == "budget":
        await db.ai_governance_policies.update_one(
            {"tenant_id": v["tenant"]}, {"$set": {"max_cost_micros_per_day": 1}}
        )
    else:
        await db.ai_credit_accounts.update_one(
            {"tenant_id": v["tenant"]},
            {"$set": {"included_balance_credits": 0, "purchased_balance_credits": 0}},
        )
    with pytest.raises(Exception):
        await start(v)
    assert not v["voice_calls"]


@pytest.mark.asyncio
async def test_reserved_cost_overrun_stops_and_previous_day_liability_counts(v):
    result, runtime, _ = await start(v)
    await db.ai_provider_cost_ledger_entries.update_one(
        {"id": runtime.action["provider_cost_ledger_entry_id"]},
        {
            "$set": {
                "estimated_cost_micros": 1,
                "created_at": (utc_now() - timedelta(days=2)).isoformat(),
            }
        },
    )
    await utterance(runtime)
    row = await db.assistant_voice_sessions.find_one({"id": result["session_id"]})
    assert row["unavailable_reason"] == "reserved_cost_exceeded"
    cost = await db.ai_provider_cost_ledger_entries.find_one(
        {"id": runtime.action["provider_cost_ledger_entry_id"]}
    )
    assert cost["estimated_cost_micros"] >= 200
    await db.ai_governance_policies.update_one(
        {"tenant_id": v["tenant"]}, {"$set": {"max_cost_micros_per_day": 199}}
    )
    with pytest.raises(Exception, match="cost limit"):
        await start(v)
    assert len(v["voice_calls"]) == 1


@pytest.mark.asyncio
async def test_due_orders_and_upcoming_schedule_use_shared_authoritative_tools(v):
    from app.services import assistant_tools

    tomorrow = (utc_now() + timedelta(days=1)).date().isoformat()
    await db.orders.insert_many(
        [
            {
                "id": "tomorrow-" + v["tenant"],
                "tenant_id": v["tenant"],
                "number": "T1",
                "title": "Johnson",
                "due_date": tomorrow,
            },
            {
                "id": "other-date-" + v["tenant"],
                "tenant_id": v["tenant"],
                "number": "T2",
                "due_date": "2020-01-01",
            },
            {
                "id": "foreign-" + v["tenant"],
                "tenant_id": v["foreign"]["tenant_id"],
                "number": "T3",
                "due_date": tomorrow,
            },
        ]
    )
    found = await assistant_tools.execute(
        v["user"], "recent_orders", {"due_day": "tomorrow"}
    )
    assert [r["id"] for r in found["items"]] == ["tomorrow-" + v["tenant"]]
    await db.calendar_events.insert_many(
        [
            {
                "id": "install-" + v["tenant"],
                "tenant_id": v["tenant"],
                "title": "Installation Johnson",
                "start_at": (utc_now() + timedelta(days=3)).isoformat(),
                "end_at": (utc_now() + timedelta(days=3, hours=1)).isoformat(),
                "status": "scheduled",
                "visibility": "shop",
            },
            {
                "id": "private-" + v["tenant"],
                "tenant_id": v["tenant"],
                "title": "Installation private",
                "start_at": (utc_now() + timedelta(days=2)).isoformat(),
                "end_at": (utc_now() + timedelta(days=2, hours=1)).isoformat(),
                "visibility": "internal",
                "created_by_user_id": v["other"]["id"],
            },
        ]
    )
    found = await assistant_tools.execute(
        v["user"],
        "shop_schedule",
        {"schedule_window": "next_30_days", "query": "Installation"},
    )
    assert [r["title"] for r in found["items"]] == ["Installation Johnson"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "selected", ["alloy", "ash", "coral", "echo", "sage", "shimmer"]
)
async def test_all_six_saved_voices_reach_model_without_changing_personality(
    v, selected
):
    await svc.update_preferences(
        v["user"], {"voice": selected, "personality_key": "sarcastic_funny"}
    )
    _, runtime, _ = await start(v)
    assert v["voice_calls"][-1]["audio"]["output"]["voice"] == selected
    assert runtime.prefs["personality_key"] == "sarcastic_funny"
    assert not any("strict" in t for t in v["voice_calls"][-1]["tools"])
    await runtime.close("user_ended")


@pytest.mark.asyncio
async def test_interruption_after_generation_before_playback_completes(v):
    result, runtime, _ = await start(v)
    await utterance(runtime)
    await runtime.handle({"type": "output_audio_buffer.started"})
    await answer(runtime, text="Words that may not have played yet.")
    assert not runtime.pending and runtime.playing
    await runtime.interrupt()
    history = await svc.get_conversation(v["user"], result["conversation_id"])
    assert history["messages"][-1]["metadata"]["interrupted"] is True
    messages, _, _ = await assistant_context.inputs(
        v["user"], result["conversation_id"], 20
    )
    assert "may not have played" not in str(messages)


@pytest.mark.asyncio
async def test_source_linked_memory_and_deleted_record_end_voice(v):
    order_id = uuid.uuid4().hex
    await db.orders.insert_one(
        {"id": order_id, "tenant_id": v["tenant"], "number": "memory-order"}
    )
    await db.assistant_memory_entries.insert_one(
        {
            "id": uuid.uuid4().hex,
            "tenant_id": v["tenant"],
            "user_id": v["user"]["id"],
            "status": "active",
            "memory_key": "preferred-reference",
            "content_text": "Use the approved wrap reference",
            "source_type": "order",
            "source_id": order_id,
        }
    )
    _, runtime, _ = await start(v)
    assert "approved wrap reference" in str(runtime.ws.sent)
    await db.orders.delete_one({"tenant_id": v["tenant"], "id": order_id})
    with pytest.raises(Exception, match="Source access"):
        await runtime.check()
    for _ in range(25):
        if runtime.closing:
            break
        await asyncio.sleep(0.1)
    assert runtime.closing
    _, resumed, _ = await start(v)
    assert "approved wrap reference" not in str(resumed.ws.sent)


@pytest.mark.asyncio
async def test_voice_start_rate_limit_uses_existing_shared_gateway_lock(v, monkeypatch):
    monkeypatch.setattr(v["settings"], "openai_realtime_rate_limit_sessions", 1)
    _, runtime, _ = await start(v)
    await runtime.close("user_ended")
    with pytest.raises(Exception, match="session start limit"):
        await start(v)
    assert len(v["voice_calls"]) == 1
