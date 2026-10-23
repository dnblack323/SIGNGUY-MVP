# Business Assistant V1 — Stage E scoped review and results

Owner accepted Stage D engineering and mocked verification and expressly authorized Stage E implementation. This scoped assessment is covered by that authorization; no additional planning gate or broad audit. Existing worktree/branch and draft PR #63 remain canonical. Stage F, merge, deploy, paid evaluation and preview generation remain unauthorized.

| Subsystem | Quality and decision | Scoped work |
|---|---|---|
| B/D conversation/context/Gateway | Keep shared authority | Extend the existing tool registry with proposal-only operations, never confirmation/execution. Both transports use the same functions. |
| Existing proposal models/routes and UI | Needs cleanup at safety boundary | Fresh actor/source checks, validated editable payload, recorded source versions, expiry, atomic confirmation/execution and stable canonical identity; show exact preview, edit and actual result links. |
| Canonical task/note/Studio draft records | Reuse | Existing Task service already supports idempotency. Add bounded optional canonical note identity for retry safety; save professional drafts in the existing Studio draft mechanism. No sending or parallel stores. |
| Private approved memory | Reuse with focused improvements | Existing stores and access filters; explicit approval, stable keys, editing/deletion, duplicate checks, source provenance and bounded relevance. Never use memory as current financial/operational truth. |

User workflow: request action in text or voice; resolve permitted records or clarify ambiguity; review/edit exact proposal; confirm in interface; execute once through canonical service; show actual saved record. Memory is saved only by a deliberate interface approval and may be corrected/deleted. Personality affects conversational tone only, never action payload rules or professional customer drafts.

Verification: mocked model decisions with real disposable task/note/draft records, permission/source/tenant/user boundaries, expiry/concurrent retries/failures, text/voice shared tools, memory correction/deletion/login and frontend/browser/build checks. Actual provider behavior remains unverified. A separate live evaluation proposal will specify a $5 ceiling without activation; six preview recordings remain a separate $1 proposal.

## Completion and verified behavior

Stage E engineering is complete for owner review. B–D are preserved. The same text/voice registry now exposes three **proposal-only** actions: internal Task, Customer/Order note, and professional Customer/Quote follow-up email draft. The model cannot confirm/execute, send mail, modify financial records or approve memory. The visible interface reviews/edits exact content and destination, confirms that version, then creates one record through the existing Task, Communication or Studio mechanism. Result links read the actual canonical record with fresh permissions.

Previews expire after 30 minutes and confirmations after five. Editing invalidates consent. Current actor permissions, owned conversation, source access and captured source content are checked before execution. Atomic claims and deterministic canonical identities prevent duplicate records under concurrent confirmations/execution or changed retry keys. If a write succeeded before its response was lost, recovery only reads that identity; it never blindly repeats a write. An unresolved crash with no observed record requires operator review. A source/permission change requires a fresh preview.

Drafts use a neutral professional record-based template, independently of all five personalities, and can be edited before confirmation. This is a deliberate bounded implementation: no extra generative drafting request, mail transmission or automatic follow-up. The request understanding remains model-backed when configured. All automated/browser decisions here were mocked.

## Memory

Natural text or voice can prepare an editable private memory suggestion. It remains unsaved until the employee reviews the text and explicitly approves it in the existing memory editor. Approved entries can be viewed, corrected with version checking, and deleted. Topic reuse and normalized-content duplicate checks avoid practical conflicting entries; source links are retained on correction and rechecked on saving/retrieval. Identity changes clear the editor and cached private state.

Approved memory is shared across that employee's conversations in that shop. Initial context includes at most ten recent permitted entries; recall returns at most five relevant entries from a bounded scan of the 100 most recent, using word overlap. This is bounded retrieval, not semantic search, automatic learning, an unlimited transcript, or an external memory system. Existing request/history/output limits remain authoritative. Deletion/correction invalidates dependent context and active voice sessions; older dependent messages may be hidden instead of replayed. Current operational/financial facts are read again from canonical application tools, never treated as truth from historical memory.

## Browser evidence — disposable records and mocked AI/media

Completed the existing action run without recreating its implementation: conversational Task request, edit, explicit confirmation and actual saved Task; Customer note; professional Quote follow-up draft, edit/confirmation and actual unsent draft. Saved Task `14d985b9-e04a-4bb9-ae8c-3db73b07995c`; draft `887e1c14-2eaf-5278-9136-c28308650b8f`. Screenshots: `evidence/EC18_STAGE_E_SAVED_TASK.png` and `evidence/EC18_STAGE_E_SAVED_DRAFT.png`.

Completion run verified Customer lookup from the fixture record, natural memory suggestion → review → explicit approval → correction, floating/full-page transition, mocked voice using the same conversation, text fallback, logout/login restoration, deletion and refresh. The actual Customer note link read note `a7a15dec-cc6a-5c83-b0e5-ca2dbe909945` and survived refresh. Evidence: `evidence/EC18_STAGE_E_MEMORY_LOGIN.png`, `evidence/EC18_STAGE_E_SAVED_NOTE.png`. After memory deletion, dependent older voice responses were hidden on conversation refresh. Automated context tests separately verify exclusion from future retrieval. The second disposable run closed with one note, one soft-deleted memory, zero emails (no Task/draft was repeated in that run); fixture database/server were shut down. No physical microphone, real speech quality, network/provider latency or live OpenAI compatibility claim.

## Verification and focused security review

- Relevant Assistant B/C/D/E, existing foundation/intelligence/voice and Gateway accounting/governance/contracts: **117 passed**, ten existing FastAPI/multipart deprecation warnings. Follow-up targeted E + Studio checks: **24 passed**, covering the final activity-list privacy correction.
- Affected frontend: **31 passed across five suites**. The final memory-source correction additionally passed all four Stage E UI tests. Production build passed; existing bundle-size and Node deprecation notices remain.
- Assistant ESLint: zero errors/warnings. Black checks cover the new helpers and formatted shared context/transport/tool/test files. Focused Flake8 correctness/import checks cover affected Python code; the pre-existing unused `doc` warning in unrelated `ai_studio.py` archive code (F841) is explicitly excluded only for that file. Whitespace checks pass. No dependencies changed. Standalone Bandit/Semgrep/Gitleaks are unavailable and are not claimed as run.
- One focused review found and fixed a private-draft leak through Studio's general activity list. Both draft/activity lists now use one current ownership/source/permission check, with regression coverage. Canonical notes and tasks retain their established application access rules; Assistant conversation/memory/proposals remain user-private.
- Covered cross-user/shop access, edits/stale revisions, duplicate confirmation/concurrent execution, deleted source, permission revocation, expiry, failure after a real canonical write, real Order note attachment, shop timezone/DST (independent of personal timezone), professional drafts across all five personalities, memory correction/deletion/source isolation and shared voice proposal-only behavior.
- Provider keys remain backend-only. Paid Realtime remains disabled by default; test activation requires the disposable mock harness. Existing Gateway reservations, usage limits, request/event deduplication, failed-call liability and estimated-versus-actual accounting are unchanged and regression-tested. Manual approval/record writes/memory saves do not fabricate a provider request or extra AI charge.

Required GitHub CI is the existing backend suite, frontend suite and production build against this Stage E commit and PR integration. **The exact SHA, workflow links and final totals are recorded in [draft PR #63](https://github.com/dnblack323/SIGNGUY-MVP/pull/63) and the final owner completion report**, avoiding a self-referential commit or unnecessary CI rerun solely to stamp a document. Local tests do not substitute for these checks.

## Remaining gates and Stage F readiness

No unresolved blocking defect was found in the verified Stage E scope. Live provider request/protocol compatibility, natural-language tool selection, real speech/transcription/interruption, latency and provider-billed cost reconciliation remain unverified. Observed usage is tracked; calculated dollar costs remain estimates and actual provider cost remains unknown until billing evidence exists. Unknown outcomes retain conservative liability and may require operator reconciliation.

The separate [minimal live evaluation proposal](BUSINESS_ASSISTANT_V1_LIVE_VERIFICATION_PROPOSAL.md) specifies a proposed **$5 maximum**, exact turn/session/output/context/admission limits and stop-on-first-failure behavior. It is prepared only, not authorized. Six commercially cleared own-account voice previews remain a separate **$1 maximum proposal** in the Stage D report; original downloaded documentation recordings remain excluded and production preview controls remain unavailable. No paid calls, previews, production activation or deployment occurred.

Existing independent Webstore #61 and dependency-maintenance #62 are unchanged. Temporary scripts, caches, disposable harness/tests, screenshots and uncleared audio are excluded from production build assets and Docker context.

Stage F can extend this existing implementation after owner authorization. Stage E engineering is ready for acceptance; commercial readiness is not established. **Stage F is not started. PR #63 remains draft and unmerged.**
