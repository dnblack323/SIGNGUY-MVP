"""Server-owned sideband events; no browser-provided transcript, tool or billing."""

import asyncio
from contextlib import suppress
from datetime import timedelta
import json
import time

from ..core.config import get_settings
from ..core.db import db
from ..core.time_utils import utc_now
from . import (
    ai_gateway,
    ai_gateway_execution,
    assistant_personality,
    assistant_tools,
    openai_realtime_provider,
)


class VoiceRuntime:
    def __init__(self, user, row, action, profile, prefs, refs):
        self.user, self.row, self.action, self.profile, self.prefs = (
            user,
            row,
            action,
            profile,
            prefs,
        )
        self.refs = {(r["source_type"], r["source_id"]): r for r in refs}
        self.ws = None
        self.tasks = []
        self.closing = False
        self.close_lock = asyncio.Lock()
        self.started = self.activity = time.monotonic()
        self.responses = 0
        self.completed = 0
        self.pending = False
        self.active_response = None
        self.speech = set()
        self.item_times = {}
        self.transcribed = set()
        self.latest_input = None
        self.seen_events = set()
        self.heard_speech = False
        self.input_active = False
        self.interrupted = False
        self.playing = False
        self.last_audio_response = None
        self.queued_turn = False
        self.scope = {
            "tenant_id": user["tenant_id"],
            "user_id": user["id"],
            "id": row["id"],
        }

    async def send(self, event):
        if self.ws and not self.closing:
            await self.ws.send(json.dumps(event))

    async def update(self, **fields):
        await db.assistant_voice_sessions.update_one(
            self.scope, {"$set": {f"metadata.{k}": v for k, v in fields.items()}}
        )

    def start_tasks(self):
        self.tasks = [
            asyncio.create_task(self.listen()),
            asyncio.create_task(self.watch()),
        ]

    async def check(self):
        from .assistant_realtime import actor, configured

        if (
            not configured()
            or not await db.ai_model_profiles.find_one(
                {"id": self.profile["id"], "status": "active"}
            )
            or not await db.ai_capabilities.find_one(
                {"capability_key": "assistant.voice_reply", "status": "active"}
            )
        ):
            raise assistant_tools.ToolError(
                "Voice configuration is no longer available"
            )

        return await actor(
            self.user, self.refs.values(), self.row["metadata"]["permission_signature"]
        )

    async def respond(self):
        if self.closing or self.pending:
            return
        settings = get_settings()
        if self.responses >= settings.assistant_voice_max_responses:
            await self.close("response_limit")
            return
        await self.check()
        await ai_gateway._enforce_governance(
            self.user["tenant_id"],
            "assistant.voice_reply",
            self.profile["id"],
            0,
            0,
            existing_request=True,
        )
        self.responses += 1
        self.pending = True
        self.active_response = None
        await db.ai_action_requests.update_one(
            {"tenant_id": self.user["tenant_id"], "id": self.action["id"]},
            {"$inc": {"provider_dispatch_count": 1}},
        )
        await self.update(state="thinking", response_count=self.responses)
        await self.send({"type": "response.create"})

    async def interrupt(self):
        if self.pending:
            self.interrupted = True
            await self.send({"type": "response.cancel"})
        if self.playing:
            await self.send({"type": "output_audio_buffer.clear"})
            self.playing = False
            # Generation may finish before the speaker buffer finishes playing.
            # Keep that saved transcript honest even after response.done.
            if self.last_audio_response:
                await db.assistant_messages.update_one(
                    {
                        "tenant_id": self.user["tenant_id"],
                        "conversation_id": self.row["conversation_id"],
                        "voice_session_id": self.row["id"],
                        "metadata.provider_event_id": self.last_audio_response,
                    },
                    {"$set": {"metadata.interrupted": True}},
                )
                await db.assistant_voice_sessions.update_one(
                    self.scope, {"$inc": {"metadata.revision": 1}}
                )
        await self.update(state="listening", interrupt_requested=False)

    async def listen(self):
        try:
            async for raw in self.ws:
                if self.closing:
                    return
                event = json.loads(raw)
                await self.handle(event)
        except asyncio.CancelledError:
            raise
        except Exception:
            await self.close("provider_failure", uncertain=True)
        finally:
            if not self.closing:
                await self.close("sideband_disconnected", uncertain=True)

    async def observe(self, event_id, usage):
        if any(
            a.get("provider_event_id") == event_id
            for a in self.action["provider_attempts"]
        ):
            return
        try:
            cost = ai_gateway_execution.realtime_cost(self.profile, usage)
        except (KeyError, TypeError, ValueError, ArithmeticError):
            cost = None
            self.action["provider_usage_complete"] = False
        payload_usage = (
            {"input_tokens": 0, "output_tokens": 0}
            if usage.get("type") == "duration"
            else usage
        )
        await ai_gateway_execution.observe(
            self.user,
            self.action,
            {"id": event_id, "usage": payload_usage},
            estimated_cost_micros=cost,
            usage_detail=usage,
        )
        observed = sum(
            a.get("estimated_cost_micros", 0) for a in self.action["provider_attempts"]
        )
        cost_row = await db.ai_provider_cost_ledger_entries.find_one(
            {
                "tenant_id": self.user["tenant_id"],
                "id": self.action["provider_cost_ledger_entry_id"],
            }
        )
        if cost_row and observed > cost_row["estimated_cost_micros"]:
            await db.ai_provider_cost_ledger_entries.update_one(
                {"tenant_id": self.user["tenant_id"], "id": cost_row["id"]},
                {"$max": {"estimated_cost_micros": observed}},
            )
            await self.close("reserved_cost_exceeded", uncertain=True)

    async def persist(
        self, role, text, *, event_id, interrupted=False, memory_preview=None
    ):
        from . import business_assistant as svc

        if self.closing or not text:
            return
        await self.check()
        found = await db.assistant_messages.find_one(
            {
                "tenant_id": self.user["tenant_id"],
                "conversation_id": self.row["conversation_id"],
                "voice_session_id": self.row["id"],
                "metadata.provider_event_id": event_id,
                "role": role,
            }
        )
        if found:
            return
        citations = []
        if role == "assistant":
            for ref in self.refs.values():
                if ref.get("source_label"):
                    citations.append(
                        await svc._create_citation(
                            self.user["tenant_id"],
                            conversation_id=self.row["conversation_id"],
                            **ref,
                        )
                    )
        if interrupted:
            text = (
                "[Interrupted; generated transcript may include unplayed speech] "
                + text
            )
        message = await svc._insert_message(
            self.user,
            conversation_id=self.row["conversation_id"],
            role=role,
            content_text=text[:12000],
            mode=self.row["metadata"].get("mode", "owner"),
            voice_session_id=self.row["id"],
            action_request_id=self.action["id"],
            citation_ids=[c["id"] for c in citations],
            metadata={
                "permission_signature": self.row["metadata"]["permission_signature"],
                "sources": list(self.refs.values()),
                "personality_key": self.prefs["personality_key"],
                "personality_version": assistant_personality.VERSION,
                "provider_event_id": event_id,
                "transcript_source": "provider_sideband",
                "interrupted": interrupted,
                "memory_preview": memory_preview,
            },
        )
        if (
            role == "user"
            and event_id.removeprefix("transcription:") in self.item_times
        ):
            await db.assistant_messages.update_one(
                {"tenant_id": self.user["tenant_id"], "id": message["id"]},
                {
                    "$set": {
                        "created_at": self.item_times[
                            event_id.removeprefix("transcription:")
                        ]
                    }
                },
            )
        await db.assistant_voice_sessions.update_one(
            self.scope, {"$inc": {"metadata.revision": 1}}
        )

    async def handle(self, event):
        kind = event.get("type")
        if kind not in {
            "error",
            "input_audio_buffer.speech_started",
            "input_audio_buffer.committed",
            "conversation.item.input_audio_transcription.completed",
            "conversation.item.input_audio_transcription.failed",
            "response.created",
            "output_audio_buffer.started",
            "output_audio_buffer.stopped",
            "response.done",
        }:
            # Media deltas are delivered directly to WebRTC. Do not retain their
            # IDs or mistake ordinary audio chunk volume for a control flood.
            return
        event_id = event.get("event_id")
        if event_id and event_id in self.seen_events:
            return
        if event_id:
            self.seen_events.add(event_id)
        if len(self.seen_events) > 2000:
            await self.close("event_limit", uncertain=True)
            return
        if kind == "error":
            # Cancel/clear of an already finished response is harmless. Other
            # protocol errors terminate rather than continuing unmetered.
            if event.get("error", {}).get("code") not in {
                "response_cancel_not_active",
                "output_audio_buffer_clear_not_active",
            }:
                await self.close("provider_error", uncertain=True)
            return
        if kind == "input_audio_buffer.speech_started":
            self.heard_speech = True
            self.input_active = True
            self.activity = time.monotonic()
            await self.check()
            await self.interrupt()
            await self.update(state="listening")
        elif kind == "input_audio_buffer.committed":
            self.input_active = True
            self.speech.add(event["item_id"])
            self.item_times.setdefault(event["item_id"], utc_now().isoformat())
            if (
                len(self.speech | self.transcribed)
                > get_settings().assistant_voice_max_responses
            ):
                await self.close("input_turn_limit", uncertain=True)
        elif kind == "conversation.item.input_audio_transcription.completed":
            item_id = event["item_id"]
            if item_id in self.transcribed:
                return
            self.transcribed.add(item_id)
            self.latest_input = item_id
            self.speech.discard(item_id)
            self.input_active = bool(self.speech)
            self.activity = time.monotonic()
            self.heard_speech = True
            await self.observe(f"transcription:{item_id}", event.get("usage") or {})
            await self.persist(
                "user", event.get("transcript", ""), event_id=f"transcription:{item_id}"
            )
            if not self.action["provider_usage_complete"]:
                await self.close("usage_incomplete", uncertain=True)
                return
            if len(self.transcribed) > get_settings().assistant_voice_max_responses:
                await self.close("input_turn_limit", uncertain=True)
                return
            self.queued_turn = self.pending
            await self.respond()
        elif kind == "conversation.item.input_audio_transcription.failed":
            await self.close("transcription_failed", uncertain=True)
        elif kind == "response.created":
            response_id = event.get("response", {}).get("id")
            if not self.pending or (
                self.active_response and response_id != self.active_response
            ):
                await self.close("unexpected_response", uncertain=True)
                return
            self.active_response = response_id
        elif kind == "output_audio_buffer.started":
            self.playing = True
            await self.update(state="speaking")
        elif kind == "output_audio_buffer.stopped":
            self.playing = False
            self.activity = time.monotonic()
            await self.update(state="listening")
        elif kind == "response.done":
            response = event.get("response") or {}
            response_id = response.get("id")
            if not response_id:
                await self.close("usage_missing", uncertain=True)
                return
            if any(
                a.get("provider_event_id") == response_id
                for a in self.action["provider_attempts"]
            ):
                return
            await self.observe(response_id, response.get("usage") or {})
            if not self.action["provider_usage_complete"] or self.closing:
                await self.close("usage_incomplete", uncertain=True)
                return
            self.pending = False
            self.active_response = None
            interrupted = self.interrupted or response.get("status") != "completed"
            self.interrupted = False
            self.activity = time.monotonic()
            await self.check()
            output = response.get("output") or []
            text = "\n".join(
                part.get("transcript") or part.get("text", "")
                for item in output
                if item.get("type") == "message"
                for part in item.get("content", [])
            )
            await self.persist(
                "assistant", text, event_id=response_id, interrupted=interrupted
            )
            if text:
                self.last_audio_response = response_id
            if text and not interrupted:
                self.completed += 1
            calls = [item for item in output if item.get("type") == "function_call"]
            if len(calls) > 4 or len(self.refs) > 100:
                await self.close("tool_limit", uncertain=True)
                return
            for call in calls if not interrupted else []:
                current = await self.check()
                try:
                    result = await assistant_tools.execute(
                        current,
                        call["name"],
                        json.loads(call.get("arguments") or "{}"),
                        timezone_name=self.prefs["timezone"],
                        conversation_id=self.row["conversation_id"],
                        request_key=f"{self.action['id']}:{self.latest_input}:{call['call_id']}",
                        mode=self.row["metadata"].get("mode", "owner"),
                    )
                except (ValueError, assistant_tools.ToolError):
                    result = {
                        "error": "Unavailable or not permitted; clarify without inventing facts"
                    }
                if self.closing:
                    return
                if result.get("proposal_id"):
                    await db.assistant_voice_sessions.update_one(
                        self.scope, {"$inc": {"metadata.revision": 1}}
                    )
                for ref in result.get("sources", []):
                    self.refs[(ref["source_type"], ref["source_id"])] = ref
                await self.check()
                if result.get("memory_preview"):
                    await self.persist(
                        "assistant",
                        "Review this private memory suggestion in the interface. It has not been saved.",
                        event_id=f"memory:{call['call_id']}",
                        memory_preview=result["memory_preview"],
                    )
                serialized = json.dumps(result, default=str)
                if (
                    len(serialized.encode())
                    > get_settings().assistant_max_context_bytes
                    or len(self.refs) > 100
                ):
                    await self.close("tool_context_limit", uncertain=True)
                    return
                await self.update(dependencies=list(self.refs.values()))
                await self.send(
                    {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": call["call_id"],
                            "output": serialized,
                        },
                    }
                )
            if calls and not interrupted:
                await self.respond()
            elif self.queued_turn:
                self.queued_turn = False
                await self.respond()
            elif not text:
                await self.update(state="listening")
            if not self.action["provider_usage_complete"]:
                await self.close("usage_incomplete", uncertain=True)

    async def watch(self):
        try:
            while not self.closing:
                await asyncio.sleep(1)
                row = await db.assistant_voice_sessions.find_one(self.scope, {"_id": 0})
                if not row or row["metadata"].get("stop_requested"):
                    await self.close("user_ended")
                    return
                await self.check()
                await ai_gateway._enforce_governance(
                    self.user["tenant_id"],
                    "assistant.voice_reply",
                    self.profile["id"],
                    0,
                    0,
                    existing_request=True,
                )
                now = time.monotonic()
                settings = get_settings()
                reason = None
                if now - self.started >= settings.assistant_voice_max_seconds:
                    reason = "duration_limit"
                elif now - self.activity >= settings.assistant_voice_idle_seconds:
                    reason = "idle_limit"
                elif (
                    row["metadata"].get("client_seen_at", "")
                    < (utc_now() - timedelta(seconds=12)).isoformat()
                ):
                    reason = "client_disconnected"
                if reason:
                    await self.close(reason)
                    return
                if row["metadata"].get("interrupt_requested"):
                    await self.interrupt()
                await self.update(
                    lease_expires_at=(utc_now() + timedelta(seconds=15)).isoformat()
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            await self.close("access_or_budget_changed", uncertain=True)

    async def close(self, reason, *, uncertain=False):
        from .assistant_realtime import RUNTIMES, release_conversation

        async with self.close_lock:
            if self.closing:
                return
            self.closing = True
            if self.playing:
                await self.interrupt()
            confirmed = not self.row.get("provider_session_id")
            try:
                if self.row.get("provider_session_id"):
                    confirmed = await openai_realtime_provider.hangup(
                        self.row["provider_session_id"]
                    )
            except Exception:
                confirmed = False
            if self.ws:
                with suppress(Exception):
                    await self.ws.close()
            for task in self.tasks:
                if task is not asyncio.current_task():
                    task.cancel()
            RUNTIMES.pop(self.row["id"], None)
            if not confirmed:
                await db.assistant_voice_sessions.update_one(
                    self.scope,
                    {
                        "$set": {
                            "status": "termination_pending",
                            "unavailable_reason": "Provider termination is pending; credits/cost reserve retained",
                            "metadata.lease_expires_at": utc_now().isoformat(),
                            "metadata.state": "ending",
                        }
                    },
                )
                return
            uncertain = (
                uncertain or self.pending or bool(self.speech) or self.input_active
            )
            if not self.heard_speech and not self.responses and not uncertain:
                await db.ai_action_requests.update_one(
                    {"tenant_id": self.user["tenant_id"], "id": self.action["id"]},
                    {"$set": {"provider_dispatch_count": 0}},
                )
            try:
                await ai_gateway_execution.finish(
                    self.user,
                    self.action,
                    self.profile,
                    succeeded=bool(self.completed),
                    uncertain=uncertain,
                )
                final_status = "ended"
            except Exception:
                final_status = "recovery_required"
                reason = "Accounting finalization incomplete; operator reconciliation required"
            await db.assistant_voice_sessions.update_one(
                self.scope,
                {
                    "$set": {
                        "status": final_status,
                        "unavailable_reason": reason,
                        "ended_at": utc_now().isoformat(),
                        "metadata.state": "ended",
                        "metadata.answer_sdp": None,
                    }
                },
            )
            await release_conversation(
                self.user, self.row["conversation_id"], self.row["metadata"]["lock_key"]
            )
