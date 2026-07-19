# EC18 Business Assistant, Actions, Intelligence, and Realtime Voice

**Status:** implemented on `CODEX-ec18-branch`
**Entitlement:** `business_assistant`
**Primary permission:** `ai_assistant:use`
**Credit display:** `AI credits apply`

## Scope

EC18 implements the paid Business Assistant over the existing EC13 entitlement and EC16 AI gateway contracts. It adds tenant-scoped conversations, messages, source citations, validated context snapshots, structured action proposals, safe execution records, memory controls, routines, proactive insights, quick actions, AI Studio delegation, voice-session metadata, and an OpenAI Realtime browser voice boundary.

EC18 does not implement Stripe products, Checkout Sessions, subscriptions, billing portal sessions, webhooks, trials, setup-package purchases, AI-credit packs, EC4 customer invoice/payment mutations, Webstore payout changes, Meta/Facebook activation, EC19 help/onboarding, BYOK, MCP, final credit prices, or final production provider activation.

## Backend Contracts

Primary router: `backend/app/routers/business_assistant.py`

Primary service: `backend/app/services/business_assistant.py`

Primary models: `backend/app/models/business_assistant.py`

Routes:

- `GET /api/assistant/catalog`
- `POST /api/assistant/platform/bootstrap`
- `POST /api/assistant/conversations`
- `GET /api/assistant/conversations`
- `GET /api/assistant/conversations/{conversation_id}`
- `POST /api/assistant/messages`
- `POST /api/assistant/actions/proposals`
- `PATCH /api/assistant/actions/proposals/{proposal_id}`
- `POST /api/assistant/actions/proposals/{proposal_id}/confirm`
- `POST /api/assistant/actions/proposals/{proposal_id}/cancel`
- `POST /api/assistant/actions/proposals/{proposal_id}/execute`
- `GET /api/assistant/memory`
- `POST /api/assistant/memory`
- `DELETE /api/assistant/memory/{memory_id}`
- `GET /api/assistant/routines`
- `POST /api/assistant/routines`
- `GET /api/assistant/quick-actions`
- `POST /api/assistant/delegations/studio`
- `GET /api/assistant/insights`
- `POST /api/assistant/insights/{insight_id}/dismiss`
- `GET /api/assistant/voice/config`
- `POST /api/assistant/voice/sessions`
- `POST /api/assistant/voice/sessions/{voice_session_id}/usage`

## Capability Identifiers

EC18 activates these EC16 capability IDs through platform bootstrap:

- `assistant.email_draft`
- `assistant.chat`
- `assistant.action_parse`
- `assistant.voice_transcription`
- `assistant.voice_reply`
- `assistant.intent_classify`
- `assistant.navigation_classify`
- `assistant.memory_compress`

Still deferred and inactive:

- `integration.facebook.message_classify`
- `integration.facebook.order_extract`
- `order.service_prefill`
- `studio.text.bulk_followup`

## Action Safety

Action lifecycle:

- `proposed`
- `edited`
- `confirmed`
- `canceled`
- `expired`
- `executing`
- `succeeded`
- `failed`
- `stale`
- `unsupported`

Execution rules:

- State-changing or affects-another-person actions require preview, edit, confirm, and execution.
- Action execution requires an `Idempotency-Key`.
- Target records are rechecked for tenant scope and stale `updated_at` values before confirmation/execution.
- Success is recorded only after a canonical local service result.
- Email actions create editable drafts only and never send automatically.
- Document actions create editable drafts only and never export, print, or email automatically.
- Bulk email actions create per-target editable drafts and report per-target results; they never send.
- Unsupported actions return an audited unsupported proposal and do not mutate records.

## Evidence and BI

Assistant answers are deterministic local BI summaries backed by tenant data. They include source citations for supported questions such as latest invoice, overdue invoices, money this week, quote follow-ups, production blockers, workers today, and incomplete margin/profit questions.

Profit and margin answers explicitly disclose missing cost categories and mark incomplete results as estimates. The assistant does not invent revenue, cost, margin, profit, schedule, staffing, inventory, or production data.

## Voice Boundary

OpenAI Realtime voice follows the backend-issued short-lived credential model:

- `OPENAI_API_KEY` stays backend-only.
- The browser receives only the short-lived Realtime credential response.
- Backend credential creation sends a privacy-preserving `OpenAI-Safety-Identifier`.
- The browser uses WebRTC for speech-to-speech Realtime sessions.
- If no OpenAI key is configured or `OPENAI_REALTIME_ENABLED=false`, voice returns `OpenAI Voice is not configured` and no fake session is created.
- Raw voice audio is not stored by default.
- Voice usage is metered only from explicit provider usage events; EC18 does not invent usage or cost.

Configuration:

- `OPENAI_API_KEY`
- `OPENAI_REALTIME_ENABLED`
- `OPENAI_REALTIME_MODEL` default `gpt-realtime-2.1`
- `OPENAI_REALTIME_VOICE` default `alloy`
- `OPENAI_REALTIME_TIMEOUT_SECONDS`
- `OPENAI_REALTIME_TURN_DETECTION`
- `OPENAI_REALTIME_PUSH_TO_TALK_DEFAULT`
- `OPENAI_REALTIME_RATE_LIMIT_SESSIONS`
- `OPENAI_REALTIME_RATE_LIMIT_WINDOW_SECONDS`
- `ASSISTANT_TRANSCRIPT_RETENTION`

Official OpenAI sources used for the implementation boundary:

- <https://developers.openai.com/api/docs/guides/realtime-webrtc>
- <https://developers.openai.com/api/docs/guides/realtime>
- <https://developers.openai.com/api/docs/guides/realtime-server-controls>
- <https://developers.openai.com/api/docs/guides/realtime-websocket>
- <https://developers.openai.com/api/docs/guides/voice-agents>
- <https://developers.openai.com/api/docs/guides/safety-best-practices>

## Frontend

Frontend files:

- `frontend/src/pages/BusinessAssistantPage.jsx`
- `frontend/src/components/assistant/AssistantPanel.jsx`
- `frontend/src/components/assistant/AssistantLauncher.jsx`
- `frontend/src/lib/businessAssistant.js`

The assistant is available at `/studio/assistant` and through a persistent launcher for users with `ai_assistant:use`.

UI capabilities:

- mode selector: Owner, Operations, Finance, Production, Workforce;
- contextual record indicator from query-string context;
- text assistant conversation;
- source/citation display;
- quick actions;
- action proposal cards;
- voice states: idle, connecting, listening, thinking, speaking, interrupted, reconnecting, unavailable, error;
- push-to-talk default with optional VAD toggle;
- interrupt and end controls;
- transcript area;
- unavailable/configuration warning;
- Studio delegation links.

## Indexes

EC18 adds indexes for conversations, messages, context snapshots, source citations, action proposals, action executions, memory entries, routines, insights, voice sessions, idempotency, status queues, provider session lookup, tenant/user lookup, and source-reference lookup in `backend/app/core/db.py`.

## Tests

Targeted tests:

- `backend/tests/test_ec18_assistant_foundation.py`
- `backend/tests/test_ec18_assistant_voice.py`
- `backend/tests/test_ec18_assistant_intelligence.py`
- `frontend/src/__tests__/BusinessAssistantPage.test.jsx`

Regression coverage includes entitlement and permission enforcement, portal rejection, tenant isolation, source-linked BI, no invoice/payment mutation, proposal confirmation/execution lifecycle, draft-only email behavior, OpenAI key non-exposure, mocked Realtime credential issuance, memory controls, routines, insights, quick actions, Studio delegation, safe bulk drafts, and voice unavailable behavior.
