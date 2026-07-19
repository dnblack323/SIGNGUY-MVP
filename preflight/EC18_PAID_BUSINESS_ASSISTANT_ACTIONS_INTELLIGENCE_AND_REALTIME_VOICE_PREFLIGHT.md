# EC18 Paid Business Assistant, Actions, Intelligence, and Realtime Voice Preflight

**Status:** PREFLIGHT COMPLETE - READY TO BUILD
**Date:** 2026-07-19
**Branch:** `CODEX-ec18-branch`
**Starting HEAD:** `ae880af6d4788c598f793df99f29202ceed95d0f`
**Upstream:** `origin/CODEX-ec18-branch`
**Remote parity:** `origin/main` and `origin/CODEX-ec18-branch` both at `ae880af6d4788c598f793df99f29202ceed95d0f`
**EC17 closure ancestor:** `be0b868135adfe2ba15b43505e29197bdc1511e1` present in history before EC18 work
**Working tree at preflight start:** clean

## 1. Authority

The owner authorized EC18 implementation on `CODEX-ec18-branch` after EC17 was merged to `main`. This prompt supplies the separate H1/H4 authorization required by the master planning documents for EC18 only.

Controlling inputs:

- `specs_pack/extracted/EC18_Paid_Business_Assistant_Actions_Intelligence_and_Voice.docx`
- Owner EC18 implementation authorization prompt dated 2026-07-19
- Current official OpenAI Realtime, WebRTC, voice-agent, tool-calling, and safety guidance
- EC16 shared AI gateway contracts and evidence
- EC17 Studio AI tool and generated-asset contracts
- EC13 entitlement and commercial billing boundaries
- EC4 customer invoice/payment, EC14 Webstore, EC15 Wrap Lab, EC12 productivity, EC11 production, EC8 workforce, EC7 finance/inventory, and canonical core record contracts

## 2. Holds and Boundaries

Resolved for EC18:

- H1 is closed for EC18 only.
- H4 is closed for EC18 only.
- The owner selected OpenAI Realtime speech-to-speech voice architecture for EC18.

Still active:

- H7 remains active for final AI-credit prices, included AI-credit amounts, final production model locking, production API-key provisioning, other provider families, BYOK, MCP, and unrelated commercial-provider decisions.
- EC19 and later checkpoints remain not started.

Explicit EC18 exclusions:

- No Stripe products, Checkout Sessions, subscriptions, billing portal, webhooks, trials, setup-package purchases, or AI-credit-pack implementation.
- No EC4 invoice/payment mutation, Webstore payout mutation, or pricing mutation.
- No Meta/Facebook activation.
- No silent email sending, content publishing, export/print/email action, destructive action, pricing change, or record mutation.
- No AI-generated direct database mutation. Actions must use structured preview, edit, confirm, canonical service execution, result capture, and audit.
- No raw voice audio storage by default.

## 3. Three Implementation Stages

EC18 uses exactly three owner-facing implementation stages:

1. **EC18A - Assistant Foundation and Action Safety**
   - Backend assistant contracts, conversation/message storage, context snapshots, structured action proposals, confirmation/execution states, memory/routine/insight/voice metadata, audit records, indexes, permissions, tenant isolation, EC13 entitlement checks, and EC16 capability activation.

2. **EC18B - OpenAI Realtime Voice and Assistant UI**
   - Backend short-lived Realtime credential endpoint, config-safe unavailable behavior, provider boundary, WebRTC browser voice client, assistant launcher, drawer/workspace UI, voice states, text fallback, action cards, mode selector, source citations, and EC17 delegation links.

3. **EC18C - Business Intelligence, Routines, Hardening, and Closure**
   - Source-linked BI tools, proactive non-mutating insights, routines, quick actions, safe bulk proposals, memory controls, email/document drafts, cost/usage metering hooks, frontend/backend tests, docs, CI, and final closure evidence.

## 4. EC16 Capability Contract

EC18 may activate these approved capability identifiers:

- `assistant.email_draft`
- `assistant.chat`
- `assistant.action_parse`
- `assistant.voice_transcription`
- `assistant.voice_reply`
- `assistant.intent_classify`
- `assistant.navigation_classify`
- `assistant.memory_compress`

EC18 must not activate these deferred identifiers:

- `integration.facebook.message_classify`
- `integration.facebook.order_extract`
- `order.service_prefill`
- `studio.text.bulk_followup`

Capability registration must use EC16 provider, model, capability, prompt, gateway request, context packet, usage ledger, provider-cost ledger, credit ledger, governance, idempotency, and audit contracts.

## 5. OpenAI Realtime Boundary

OpenAI Realtime implementation rules:

- `OPENAI_API_KEY` is backend-only.
- The browser receives only short-lived Realtime client credentials from the backend.
- Permanent API keys must never appear in frontend bundles, logs, database records, or API responses.
- Backend credential creation must include a privacy-preserving stable safety identifier when required by official OpenAI guidance.
- Realtime model, voice, enablement, timeout, transcript retention, and turn-detection defaults must be centrally configurable.
- If no OpenAI key is configured, voice returns a safe unavailable state and text assistant remains available where possible.
- Tests use mocks/fakes and must never call the live OpenAI API.
- Browser Realtime tool calls may create backend action proposals only; they may not mutate app records directly.

The documented default model at implementation start is `gpt-realtime-2.1`, configured through `OPENAI_REALTIME_MODEL`.

## 6. Permissions and Tenant Isolation

Every assistant route is staff-only and requires:

- active tenant staff authentication;
- paid Business Assistant entitlement through EC13/EC2 entitlement projection;
- `ai_assistant:use`;
- target-record read permission before context read;
- target mutation permission before proposing or executing a mutation;
- tenant validation for every conversation, memory entry, citation, action proposal, voice session, routine, insight, and target reference.

Mode selection changes suggestions and available tools only. It never grants extra permissions.

## 7. Action Safety Lifecycle

Supported action states:

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

Required rules:

- Any state-changing, sending, export, print, publishing, pricing, record mutation, or affects-another-person action requires preview/edit/confirm.
- Bulk proposals must show counts, affected records, skipped/unauthorized records, expected changes, warnings, and per-record canonical execution results.
- Stale context requires reconfirmation.
- Idempotency is required for action execution.
- Success may only be reported after canonical service confirmation.
- Denied, failed, sensitive, stale, and executed actions are audited.

## 8. Evidence and Data Answering

Assistant BI answers must include structured evidence:

- source type;
- source id;
- source link or route;
- date range;
- updated timestamp when available;
- calculation basis;
- missing data categories.

The assistant must not hallucinate revenue, cost, margin, profit, schedule, staffing, inventory, or production data. Profit and margin answers must disclose inputs and mark incomplete results as estimates.

## 9. Required Indexes

EC18 must add indexes for:

- assistant conversations by tenant/user/status/updated time;
- conversation context and pinned record references;
- assistant messages by tenant/conversation/created time;
- assistant messages by EC16 action request;
- structured action proposals by tenant/conversation/status/expiration;
- action proposal idempotent execution;
- action confirmations/executions by tenant/proposal/status;
- assistant memory by tenant/user/status/key and by source reference;
- routines by tenant/user/status/next run;
- insights by tenant/status/dedupe/window;
- voice sessions by tenant/user/status/created time and provider session id;
- assistant activity/audit lookup by tenant/action/created time.

## 10. Required Tests

Targeted tests must verify:

- platform-only EC18 capability bootstrap and inactive identifier exclusion;
- Business Assistant entitlement and `ai_assistant:use` enforcement;
- portal-token rejection;
- tenant isolation for conversations, memory, actions, voice sessions, insights, and citations;
- context snapshots validate record IDs and read permissions;
- proposal/edit/confirm/cancel/expire/execute/stale lifecycle;
- no silent email send, pricing mutation, invoice/payment mutation, Webstore payout mutation, Stripe call, or direct AI DB mutation;
- unsupported actions return safe results;
- BI answers cite source records and disclose missing data;
- OpenAI Realtime credential endpoint hides permanent keys and handles missing config safely;
- Realtime provider calls are mocked in tests;
- frontend assistant launcher/workspace, text fallback, voice states, action cards, source citations, mode selector, and configuration errors.

## 11. Expected Files

Documentation and tracking:

- `preflight/EC18_PAID_BUSINESS_ASSISTANT_ACTIONS_INTELLIGENCE_AND_REALTIME_VOICE_PREFLIGHT.md`
- `docs/modules/ec18_business_assistant.md`
- `evidence/EC18_IMPLEMENTATION_COMPLETION_REPORT.md`
- `memory/MASTER_CHECKPOINT_CHECKLIST.md`
- `memory/checkpoint_reference_table.md`
- `memory/owner_specification_hold_register.md`
- `memory/progress_register.md`

Backend:

- `backend/app/models/business_assistant.py`
- `backend/app/services/business_assistant.py`
- `backend/app/routers/business_assistant.py`
- `backend/app/core/config.py`
- `backend/app/core/db.py`
- `backend/server.py`
- `backend/tests/test_ec18_assistant_foundation.py`
- `backend/tests/test_ec18_assistant_voice.py`
- `backend/tests/test_ec18_assistant_intelligence.py`

Frontend:

- `frontend/src/lib/businessAssistant.js`
- `frontend/src/components/assistant/AssistantLauncher.jsx`
- `frontend/src/components/assistant/AssistantPanel.jsx`
- `frontend/src/pages/BusinessAssistantPage.jsx`
- `frontend/src/App.js`
- `frontend/src/components/app-shell/AppShell.jsx`
- `frontend/src/lib/navigation.js`
- `frontend/src/__tests__/BusinessAssistantPage.test.jsx`

## 12. Preflight Result

EC18 is authorized and ready to implement. The preflight confirms the branch is clean, current with `origin/main`, and starts from the EC17 merge commit. EC19 and later checkpoints remain held. No EC18 implementation occurred before this preflight.
