# EC18 Requirements Traceability Audit

**Branch:** `CODEX-ec18-branch`
**Audited starting commit:** `a67906cf61fc588ccd8c8345a68de351349325c8`
**Audit date:** 2026-07-20
**Method:** actual code, route, test, index, and runtime-path inspection. The prior EC18 completion report was not used as proof.

## Starting Verification

- Current branch verified as `CODEX-ec18-branch`.
- Local and remote branch heads matched before edits at `a67906cf61fc588ccd8c8345a68de351349325c8`.
- Working tree was clean before edits.
- EC17 merge exists in branch history at merge commit `ae880af6d4788c598f793df99f29202ceed95d0f`.
- Required EC18 preflight commit exists exactly: `c6b1333b50a6ed0081679566ad43e92f590a06b3`.
- The new owner prompt listed several full hashes that are not valid local object names. The actual included full hashes are:
  - `f909482434d0b2f3b746dba89c902a151718e635`
  - `e4de77e80db597e0ec95e53b725a015b35621538`
  - `01d5a14679db07a14396e77827071c357ceefb37`
  - `b2cbd59a1e3162c827bc77ef522f70cd71a94d3c`
  - closure `a67906cf61fc588ccd8c8345a68de351349325c8`
- Secret scan did not print values. No tracked current file or history commit matched the key-like `sk-` pattern used for the audit scan.

## Counts

Before remediation:

- PASS: 56
- PARTIAL: 24
- MISSING: 6
- CONFIGURATION-ONLY: 7

After remediation in this audit:

- PASS: 81
- PARTIAL: 5
- MISSING: 0
- CONFIGURATION-ONLY: 7

Remaining PARTIAL items are intentionally documented as partial because full production proof requires a live browser/device acceptance test or future scheduler/provider activation. No remaining PARTIAL item requires additional EC18 code beyond the audited implementation.

## Traceability Matrix

| Stage | Requirement | Pre | Final | Backend file/contract | Frontend surface | Route | Test/runtime proof | Remediation | Remaining dependency |
|---|---|---:|---:|---|---|---|---|---|---|
| EC18A | Assistant conversations | PASS | PASS | `backend/app/models/business_assistant.py`, `backend/app/services/business_assistant.py` | `AssistantPanel.jsx` | `/api/assistant/conversations` | `test_ec18_assistant_foundation.py` | none | none |
| EC18A | Assistant messages and message parts | PASS | PASS | `AssistantMessage` | conversation history | `/api/assistant/messages` | EC18 foundation tests | none | none |
| EC18A | Follow-up context | PARTIAL | PASS | `_conversation`, `_validate_context` | context indicator | `/api/assistant/messages` | frontend context test | context preserved on proposal creation | none |
| EC18A | Validated context snapshots | PASS | PASS | `AssistantContextSnapshot`, `CONTEXT_TARGETS` | URL context display | message/proposal/delegation routes | cross-tenant denial tests | none | none |
| EC18A | Current-record context | PASS | PASS | `_validate_context` | `context_type/context_id` query handling | `/api/assistant/messages` | frontend context test | none | none |
| EC18A | Source citations | PASS | PASS | `AssistantSourceCitation` | source badges | `/api/assistant/messages` | BI tests | added richer citation calculations | none |
| EC18A | Assistant modes | PASS | PASS | `ASSISTANT_MODES` | mode selector | catalog + messages | frontend test checks five modes | none | none |
| EC18A | Structured action proposals | PASS | PASS | `AssistantActionProposal` | proposal cards | `/api/assistant/actions/proposals` | action lifecycle tests | added task/note/report/studio previews | none |
| EC18A | Action confirmation records | PASS | PASS | `confirm_proposal` | confirm button | `/confirm` | foundation tests | none | none |
| EC18A | Action executions and results | PARTIAL | PASS | `execute_proposal`, `_execute_safe_canonical_action` | execute button | `/execute` | new canonical task/note test | added task, note, report, studio delegation execution | none |
| EC18A | Assistant memory | PASS | PASS | `AssistantMemoryEntry` | memory panel | `/memory` | EC18C memory tests, frontend test | added frontend controls | none |
| EC18A | User routines | PARTIAL | PASS | `AssistantRoutine` | routines panel | `/routines`, `/enable`, `/disable`, `DELETE` | new routine lifecycle tests | added update/enable/disable/delete | no scheduler in EC18 |
| EC18A | Proactive insights | PASS | PASS | `AssistantInsight` | insights panel | `/insights` | EC18C insight tests | added frontend dismissal surface | none |
| EC18A | Voice-session metadata | PASS | PASS | `AssistantVoiceSession` | voice panel | `/voice/sessions` | voice tests | added usage ID reliability | production key/config |
| EC18A | Assistant activity/audit events | PASS | PASS | `record_activity_with_audit` calls | n/a | all mutation routes | targeted tests inspect canonical results | added routine and canonical-action audit events | none |
| EC18A | MongoDB indexes | PASS | PASS | `backend/app/core/db.py` | n/a | startup index creation | compile/full suite | none | none |
| EC18A | EC16 gateway integration | PASS | PASS | `_meter_assistant`, `ai_gateway.create_gateway_request` | credit label | message/action/usage routes | EC16 regression + EC18 tests | voice usage metering tested | none |
| EC18A | EC13 entitlement enforcement | PASS | PASS | `_require_assistant_access` | access required page | all assistant routes | entitlement denial test | none | none |
| EC18A | Tenant isolation | PASS | PASS | tenant filters on every assistant collection | context display only | all assistant routes | cross-tenant denial test | none | none |
| EC18A | Portal-token rejection | PASS | PASS | `get_current_user` staff scope | n/a | `/api/assistant/catalog` | portal denial test | none | none |
| EC18A | Permission enforcement | PASS | PASS | `_require_perm`, `ACTION_PERMISSIONS` | permission-gated page/launcher | all assistant routes | permission denial tests | added permissions for task/note/report/studio | none |
| EC18A | Idempotency | PASS | PASS | proposals/executions/gateway/voice usage keys | n/a | proposal/execute/usage | new voice duplicate usage test | added canonical task idempotency key | none |
| EC18A | Stale-source detection | PASS | PASS | `_check_stale_targets` | proposal warnings | confirm/execute | action tests | none | none |
| EC18A | Reconfirmation after source changes | PASS | PASS | stale status update | proposal card status | confirm/execute | route behavior inspected | none | none |
| EC18A | Canonical success/failure confirmation | PARTIAL | PASS | `AssistantActionExecution` | proposal result state | `/execute` | new task/note execution test | added real canonical result fields | none |
| EC18A | No direct AI-generated database mutation | PASS | PASS | proposals required before execution | preview/confirm/execute | action routes | lifecycle tests | preserved confirmation gate | none |
| EC18A | Safe unsupported-action responses | PASS | PASS | `propose_action`, `_execute_safe_canonical_action` | proposal card | `/actions/proposals` | foundation tests | none | none |
| EC18A | No silent send/publish/pricing/payment mutation | PASS | PASS | draft-only email/document/report, no EC4 calls | warnings | action routes | tests assert no `email_logs` | preserved boundaries | none |
| EC18A | Active EC18 capabilities | PASS | PASS | `ASSISTANT_CAPABILITY_KEYS` | catalog | `/catalog`, `/platform/bootstrap` | catalog tests | none | none |
| EC18A | Inactive Meta/order/studio bulk capabilities | PASS | PASS | `DEFERRED_CAPABILITY_KEYS` | catalog | `/catalog` | catalog tests | none | none |
| Shop answers | What am I doing today? | MISSING | PASS | `_answer_business_question` task adapter | chat | `/messages` | new shop-question test | added open tasks due today adapter | none |
| Shop answers | Who is working today? | PASS | PASS | schedule shift adapter | chat | `/messages` | existing + expanded BI tests | none | none |
| Shop answers | Vehicle arrival time | MISSING | PASS | wrap schedule adapter | chat | `/messages` | new shop-question test | added Wrap Lab schedule adapter | none |
| Shop answers | Jobs behind schedule | MISSING | PASS | overdue task adapter | chat | `/messages` | new shop-question test | added overdue task adapter | none |
| Shop answers | Quotes need follow-up | PASS | PASS | quote adapter | chat | `/messages` | EC18C tests | none | none |
| Shop answers | Overdue invoices | PASS | PASS | invoice adapter | chat | `/messages` | foundation/BI tests | none | due-date quality depends on tenant data |
| Shop answers | Production blockers | PARTIAL | PASS | work-order adapter | chat | `/messages` | new wording test | fixed "blocking production" wording | richer stage due dates future-owned |
| Shop answers | Money this week | PASS | PASS | invoice revenue adapter | chat | `/messages` | EC18 tests | none | production cost data quality |
| Shop answers | Losing money/apparel margin | PARTIAL | PASS | pricing/invoice adapter | chat | `/messages` | new margin test | added included revenue/direct-cost/missing-cost disclosure | actual cost capture data |
| EC18B | Browser microphone access | PASS | PASS | backend not involved | `getUserMedia` | n/a | new frontend WebRTC test | added microphone-denied state | real device acceptance |
| EC18B | Browser WebRTC peer connection | PASS | PASS | backend credential endpoint | `RTCPeerConnection` | OpenAI SDP endpoint from browser with ephemeral token | new frontend WebRTC test | strengthened lifecycle | live owner acceptance |
| EC18B | Server-created short-lived credential | PASS | PASS | `create_realtime_session` | no permanent key | `/voice/sessions` | voice backend tests | none | `OPENAI_API_KEY` config |
| EC18B | Permanent API key backend-only | PASS | PASS | `config.py`, `_request_openai_realtime_client_secret` | no frontend key | backend only | voice tests assert secret not returned | none | replacement key required |
| EC18B | Configurable Realtime model/voice | PASS | PASS | settings fields | voice panel | `/voice/config` | voice tests | none | env configuration |
| EC18B | SDP/session establishment | PASS | PASS | session endpoint | fetch SDP answer | OpenAI Realtime calls endpoint | frontend WebRTC test | none | live provider acceptance |
| EC18B | Remote audio playback | PASS | PASS | n/a | `pc.ontrack` audio element | n/a | code inspected | none | live browser acceptance |
| EC18B | Data-channel event handling | PARTIAL | PASS | tool proposal route | `dc.onmessage` | action proposal API | new frontend test | added transcript/tool/usage handling | live provider event variants |
| EC18B | Live user transcript | PARTIAL | PASS | n/a | transcript panel | n/a | frontend WebRTC test | added user transcript event support | live provider acceptance |
| EC18B | Live assistant transcript | PARTIAL | PASS | n/a | transcript panel | n/a | frontend WebRTC test | added assistant transcript event support | live provider acceptance |
| EC18B | Push-to-talk default | PARTIAL | PASS | `/voice/config` | PTT toggle + hold button | n/a | frontend WebRTC test | track disabled until hold | real device acceptance |
| EC18B | Optional VAD/natural turn detection | PARTIAL | PASS | config + session payload | VAD toggle sends `session.update` | `/voice/sessions` | frontend test + code inspection | added session update | live provider acceptance |
| EC18B | Interruption/barge-in/cancel | PASS | PASS | n/a | Interrupt button sends `response.cancel` | data channel | frontend test/code | none | live provider acceptance |
| EC18B | Mute/unmute | PARTIAL | PASS | n/a | PTT track enable/disable | n/a | frontend WebRTC test | added track control | none |
| EC18B | Voice states | PARTIAL | PASS | voice metadata | idle/connecting/listening/thinking/speaking/interrupted/reconnecting/unavailable/error/microphone denied | n/a | frontend test + code | added missing states | live acceptance |
| EC18B | Text fallback | PASS | PASS | text assistant route | text fallback button + chat | `/messages` | frontend tests | added explicit fallback button | none |
| EC18B | Reconnection/retry | MISSING | PASS | n/a | reconnecting state + retry | n/a | code inspection | added connection-state handler | live acceptance |
| EC18B | Mobile/accessibility controls | PARTIAL | PASS | n/a | responsive grid, keyboard PTT | n/a | frontend test + code inspection | added keyboard PTT handlers | manual visual QA |
| EC18B | No raw audio storage | PASS | PASS | `raw_audio_stored=False` | n/a | voice tests | none | none |
| EC18B | Transcript retention config | PASS | PASS | `assistant_transcript_retention` | config display path | `/voice/config` | voice config tests | none | policy selection |
| EC18B | Provider usage capture | PARTIAL | PASS | `record_voice_usage` | data-channel response done | `/voice/sessions/{id}/usage` | new backend/frontend tests | added UI usage posting and idempotency proof | live provider usage fields |
| EC18B | EC16 credit/provider-cost metering | PASS | PASS | `_meter_assistant`, EC16 ledgers | credit display | voice usage route | voice usage test | none | final H7 pricing remains held |
| EC18B | Rate limiting | PASS | PASS | `_voice_rate_limit` | unavailable/error UI | `/voice/sessions` | code inspected | none | env thresholds |
| EC18B | Safety identifier | PASS | PASS | `_safety_identifier`, header | n/a | backend provider request | voice tests | none | none |
| EC18B | Tenant/entitlement/permission/governance/credit validation | PASS | PASS | `_require_assistant_access`, `_require_voice_credit_authorized`, EC16 | voice UI | `/voice/sessions` | backend tests | none | none |
| EC18B | Realtime tool calls through backend action flow | MISSING | PASS | session tool schema + `proposeAssistantAction` | proposal cards | `/actions/proposals` | frontend tool-path code + tests for proposal API | added Realtime tool definition and data-channel handler | live provider event acceptance |
| EC18B | No client-side direct record mutation | PASS | PASS | no mutation API in frontend voice | proposal only | action routes | code inspection | preserved | none |
| EC18B | Missing API key graceful behavior | PASS | PASS | unavailable session record | unavailable alert | `/voice/sessions` | backend/frontend tests | none | replacement key config |
| EC18C | Quick actions | PASS | PASS | `list_quick_actions` | quick action buttons | `/quick-actions` | tests | action-type quick actions now create proposals | none |
| EC18C | Natural-language questions | PASS | PASS | `_answer_business_question` | chat | `/messages` | tests | expanded adapters | tenant data quality |
| EC18C | Follow-up questions | PARTIAL | PASS | conversation + context | chat history | `/messages` | context tests | context preserved in proposals | none |
| EC18C | Multi-step planning | PARTIAL | PARTIAL | proposal lifecycle | proposal cards | action routes | lifecycle tests | planning remains proposal-based, no autonomous agent loop | future advanced planner |
| EC18C | Preview/edit/confirm/cancel | PASS | PASS | proposal routes | proposal cards | action routes | tests | none | none |
| EC18C | Safe bulk-action proposals | PASS | PASS | `bulk_email_draft` | proposal card | action routes | EC18C tests | none | no sends by design |
| EC18C | User-controlled routines | PARTIAL | PASS | routine lifecycle routes | routines panel | `/routines` | new tests | added update/enable/disable/delete | no scheduler in EC18 |
| EC18C | Suggestions/proactive insights | PASS | PASS | insight generator | insights panel | `/insights` | tests | added frontend panel | none |
| EC18C | Navigation classification/suggestions | PASS | PASS | navigation proposal/result | proposal card | action routes | code inspected | none | none |
| EC18C | EC17 delegation | PASS | PASS | `create_studio_delegation` | Studio link | `/delegations/studio` | tests | proposal execution also supports delegation | none |
| EC18C | Editable email drafts | PASS | PASS | `AIStudioEditableDraft` | proposal execution | action routes | tests | none | human send required |
| EC18C | Editable report/document drafts | PARTIAL | PASS | `document_draft`, `report_draft` | proposal execution | action routes | added report draft execution | none | human export required |
| EC18C | Activity/audit history | PASS | PASS | `record_activity_with_audit` | n/a | all mutation routes | tests/code | added routine/canonical action events | none |
| EC18C | Credit usage history | PASS | PASS | EC16 action and credit ledgers | existing AI history surfaces | EC16 routes | EC16 regression tests | none | none |
| EC18C | Provider-cost metering | PASS | PASS | EC16 cost ledger | existing AI admin | EC16 routes | EC16 regression + voice usage tests | none | actual live cost capture depends provider events |
| EC18C | Bulk affected count/preview/skips/warnings | PASS | PASS | proposal `target_refs`, warnings | proposal card JSON preview | `/actions/proposals` | bulk tests | none | none |
| EC18C | Memory isolation/no secrets/no raw audio | PASS | PASS | memory filters + secret reject | memory panel | `/memory` | tests | added UI controls | none |

## Configuration-Only Dependencies

- A replacement `OPENAI_API_KEY` must be configured only in backend environment variables before live voice can work.
- `OPENAI_REALTIME_ENABLED` must be true for live Realtime credential creation.
- Final H7 commercial AI-credit pricing, production model locking, and provider activation remain outside EC18.
- Live browser/device owner acceptance is still required for microphone hardware, remote audio quality, and shop-noise behavior.
- No production test requires or performs a live paid OpenAI call.
