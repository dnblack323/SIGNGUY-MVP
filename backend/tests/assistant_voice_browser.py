"""Disposable browser fixture only. Never imported by production application."""

import asyncio
import json
import uuid


async def configure(settings, db):
    from app.services import openai_realtime_provider
    from tests.test_assistant_stage_d import RATES, USAGE

    settings.assistant_realtime_enabled = settings.openai_realtime_enabled = True
    settings.assistant_voice_model_profile_id = "browser-voice-profile"
    settings.openai_realtime_model = "gpt-realtime-2.1"
    settings.assistant_voice_max_seconds = 60
    settings.assistant_voice_max_responses = 4
    settings.assistant_voice_idle_seconds = 20
    await db.ai_model_profiles.insert_one(
        {
            "id": "browser-voice-profile",
            "provider_config_id": "browser-provider",
            "provider_key": "openai",
            "model_key": "gpt-realtime-2.1",
            "status": "active",
            "metadata": {
                "realtime_pricing": RATES,
                "pricing_source": "LOCAL MOCK ONLY",
                "supported_voices": [
                    "alloy",
                    "ash",
                    "coral",
                    "echo",
                    "sage",
                    "shimmer",
                ],
                "transcription_model": "whisper-1",
            },
        }
    )
    await db.ai_capabilities.insert_one(
        {
            "id": "browser-voice",
            "capability_key": "assistant.voice_reply",
            "status": "active",
            "billable": True,
            "default_credit_charge": 1,
            "feature_key": "business_assistant",
            "allowed_model_profile_ids": ["browser-voice-profile"],
        }
    )
    await db.ai_governance_policies.update_one(
        {"id": "browser-budget"}, {"$set": {"max_cost_micros_per_day": 20000000}}
    )

    class Socket:
        def __init__(self):
            self.queue = asyncio.Queue()
            self.responses = 0
            self.seeded = False

        async def send(self, raw):
            event = json.loads(raw)
            if event["type"] == "response.create":
                self.responses += 1
                response_id = uuid.uuid4().hex
                output = (
                    [
                        {
                            "type": "function_call",
                            "name": "invoices",
                            "call_id": "browser-tool",
                            "arguments": '{"invoice_filter":"overdue"}',
                        }
                    ]
                    if self.responses == 1
                    else [
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_audio",
                                    "transcript": "Voice fixture: Invoice B-1001 has $125.00 overdue. Open its source record to review it.",
                                }
                            ],
                        }
                    ]
                )
                await self.queue.put(
                    {"type": "response.created", "response": {"id": response_id}}
                )
                await self.queue.put(
                    {
                        "type": "response.done",
                        "response": {
                            "id": response_id,
                            "status": "completed",
                            "usage": USAGE,
                            "output": output,
                        },
                    }
                )

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self.seeded:
                self.seeded = True
                await asyncio.sleep(1)
                return json.dumps(
                    {
                        "type": "conversation.item.input_audio_transcription.completed",
                        "item_id": "browser-utterance",
                        "transcript": "Which invoices are overdue?",
                        "usage": {"type": "duration", "seconds": 2},
                    }
                )
            event = await self.queue.get()
            if event is None:
                raise StopAsyncIteration
            return json.dumps(event)

        async def close(self):
            await self.queue.put(None)

    async def create(offer, session):
        return "v=0\r\nLOCAL MOCK", "rtc_" + uuid.uuid4().hex

    async def attach(call_id):
        return Socket()

    async def hangup(call_id):
        return True

    openai_realtime_provider.create_call = create
    openai_realtime_provider.attach = attach
    openai_realtime_provider.hangup = hangup


# Script is served only by this disposable test harness, not built into React.
SCRIPT = """<script>
window.RTCPeerConnection = class {
  addTrack() {} close() {} async createOffer() { return {type:'offer',sdp:'v=0\\r\\nm=audio 9 UDP/TLS/RTP/SAVPF 111\\r\\n'}; }
  async setLocalDescription() {} async setRemoteDescription() {}
};
Object.defineProperty(navigator, 'mediaDevices', { configurable:true, value:{getUserMedia:async()=>{
 const track={enabled:true,stop(){}}; return {getTracks:()=>[track],getAudioTracks:()=>[track]};
}}});
window.addEventListener('DOMContentLoaded',()=>{const e=document.createElement('div');e.textContent='LOCAL MOCK VOICE: simulated microphone, audio and provider; no paid calls'; e.style='position:fixed;top:0;left:0;z-index:99999;background:#fff3cd;color:black;font-size:12px';document.body.append(e);});
</script>"""
