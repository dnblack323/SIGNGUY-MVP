# Business Assistant V1 — consolidated release-readiness report

October 23, 2026. Stages A–E are accepted for their approved engineering scope. Stage F's free verification and necessary corrections are complete for owner review in the existing worktree/branch and draft PR #63. **NOT commercially ready or activated.** No merge, deployment, paid model call or paid preview generation occurred.

## Status and implemented scope

| Capability | Implemented | Verification | Commercial activation |
|---|---|---|---|
| Provider-backed text, meaningful follow-up context, private saved conversations, bounded history and record citations | Yes | Mock transport + real disposable auth/API/database; live Responses compatibility unverified | Disabled by default |
| Customer lookup/history, Orders/due dates, Work Orders/recorded stages, unpaid/overdue invoices, Quote follow-ups, Tasks and Shop Schedule | Yes, eight bounded tools | Canonical application reads and financial projection, permission/isolation/financial edge-case tests; browser records | No paid activation |
| Five personalities and six independent saved voice preferences | Yes | All-five/all-six combinations, provider-request instructions, isolation and login tests; all eleven choices exercised in browser | Settings usable without provider spend |
| Realtime WebRTC audio, server sideband/tool control, shared history, transcripts, mute/interruption/end/reconnect/text fallback | Yes | Mocked provider/events/media; real shared services/record persistence | Disabled by default; live speech/protocol/cost blocker |
| Internal Task, Customer/Order note, professional editable follow-up draft | Yes | Exact editable previews and explicit version confirmation; real canonical records; concurrency/stale/expiry/crash tests | No automatic sending or autonomous writes |
| Explicitly approved private memory, conversational suggestions, correction/deletion, source-linked bounded cross-conversation retrieval | Yes | Real store, current-source/access filters, future-conversation/deletion and login tests | No automatic learning or external memory service |
| Six audible voice previews | Playback code ready; approved recordings absent | Existing free-playback/error tests, expected six static paths, disabled production controls | **Unavailable until valid original samples are generated, inspected and approved** |

Only model decisions and media/provider transport were simulated. Passing mocked tests does not verify OpenAI understanding, voice quality, latency, exact wire compatibility, or billing. No feature is live-provider-verified in this assessment.

## Final end-to-end browser acceptance

Completed the requested 15-step scenario in one conversation: full-page Assistant → Orders due tomorrow → Order detail → its Customer's unpaid invoices → Task request/edit/confirm → actual saved Task → Customer note → professional Quote draft/edit/confirm → actual unsent draft → conversational memory suggestion/explicit approval → floating Assistant → simulated spoken follow-up in the same context → end voice/logout/login → restored conversation, Task and approved memory. Ash and Sarcastic & Funny also restored after login. The fixture verified that the shared voice context contained the previous Order discussion and approved preference before emitting its simulated utterance.

Additional browser checks covered Work Order status, Quote candidates, today's/tomorrow's Task/Schedule paths (automated tests cover both dates), Customer search, separately linked Order note, memory correction/deletion and refresh. Customer-scoped invoice results returned B-1001/$125 and excluded another Customer's $999.99 invoice. After memory deletion, dependent earlier responses were hidden on refresh rather than replayed. Automated tests verify exclusion from future context across different conversations.

Actual disposable records observed through their application result links:

| Record | Canonical ID | Verified behavior |
|---|---|---|
| Task | `3f37c801-8bbc-47bb-aa67-ea479e35aa94` | Edited content, shop timezone due date, survives login |
| Customer note | `709eeabe-f66a-59e6-8b2b-ba49c0d51187` | Exact content and Customer destination |
| Order note | `0d494aa6-f636-5d1f-9e29-64fcef431f07` | Exact content and Order destination |
| Studio email draft | `ddf826c4-7726-55bb-9919-3dcb9d1502e5` | Edited professional body, Quote/Customer links, explicitly unsent |

Shutdown counts: two Tasks (one pre-seeded + one created), two notes, one draft, one soft-deleted memory, **zero email logs**. Disposable servers/databases were closed and test tabs removed. Screenshots: [restored actual Task](../evidence/EC18_STAGE_F_RESTORED_TASK.png), [mobile settings](../evidence/EC18_STAGE_F_MOBILE_SETTINGS.png). A 375×812 view kept records/settings usable. Radio labels and button states were inspected; the main message input now has an accessible label and a workflow regression uses it. This is focused accessibility/responsive verification, not a complete WCAG certification.

Ordinary `staff` access was correctly denied by the current role-based application policy. The complete browser scenario used an internal `admin`, with existing permissions. No auth override or permission-policy expansion was introduced. Owner must decide whether initial release remains owner/admin-only or separately authorize a least-privilege staff-access policy; per-user test dictionaries are not evidence that production supports custom permission grants.

## Focused security and quality findings

| Boundary | Finding and action | Evidence/limit |
|---|---|---|
| Authoritative shop lookups | Corrected missing Order→Customer→invoice follow-up: permitted Orders expose their accessible Customer reference; exact Customer search works; invoices accept a validated Customer restriction | Same canonical invoice reconciliation, no new formula/write; excludes other Customer/shop, denies missing source and missing Customer permission |
| Pending provider termination | Corrected browser continuing local media while remote hangup was pending | Stop microphone/speaker/peer immediately; retain session identity, server recovery and spending reservation; prohibit a second dispatch |
| Permission changes and cached views | Corrected Stage E action previews remaining cached after access failure | Clear proposals/messages/sources and hide private memory/action views; require refreshed sign-in; current backend permissions remain authoritative |
| Shared conversation/tools/prompts/Gateway | Keep existing authority; no second Assistant, personality catalog, memory DB or billing ledger | B–E regressions retained; source revocation/ownership and current action permissions checked at execution; no model confirm/execute/send tool |
| Retrieved-data injection | Policy treats records/history/preferences/memory as untrusted; forbidden execution attempt rejected even when a Customer record contains malicious instructions | Mocked adversarial output exercises backend boundaries; **not** proof a live model always follows the policy |
| Financial and private data | Existing integer-cent projection; source/history/citation/memory and private draft/activity checks retained | Partial payments/refunds/zero/multiple/date/deleted-source, tenant/user/permission and generic billing-history tests |
| Provider/session/accounting | Backend-only credentials, media-only browser, server-owned tool/event/usage control, bounded responses/context/session; conservative credit/cost reservation and duplicate protection | Failed/unknown outcomes do not trigger paid retries; incomplete accounting retains liability and may require operator reconciliation |

No further blocking defect was found within the verified Assistant scope. No broad audit, unrelated cleanup, Webstore/pricing/payment change, dependency upgrade or redesign occurred. A legacy push-to-talk/turn-detection metadata setting does not implement a hold-to-talk UI; supported voice controls are start/end, server VAD, mute, interrupt and explicit reconnect. The transcript-retention environment label is descriptive: there is no automatic transcript-purge worker. Retention/deletion policy must be decided before commercial activation; raw audio is not stored by this application.

Available checks: focused Flake8 correctness/import checks, Black, Assistant ESLint, whitespace, production asset exclusion, `pip check` (no broken requirements), and Yarn dependency audit. Bandit, Semgrep, Gitleaks, pip-audit and Ruff were not installed; **not run or claimed passed**. `npm audit` could not operate because the project uses yarn.lock without package-lock; the matching Yarn audit completed instead.

Current Yarn audit: **4 critical, 198 high, 86 moderate, 1 low affected paths**. There are 98 npm advisory records mapping to 88 unique GHSA IDs; all map into the prior [dependency classification](../evidence/EC18_STAGE_B_DEPENDENCY_CLASSIFICATION.csv). Critical packages remain transitive `tar`, `shell-quote` and `proxy-addr`, in install/build/dev-server paths rather than deployed browser/Python execution. This is not a supply-chain exemption or blanket clearance. Existing browser/conditional and tooling advisories remain [maintenance issue #62](https://github.com/dnblack323/SIGNGUY-MVP/issues/62). No newly confirmed reachable Assistant vulnerability justified a dependency change. Deployment-wide dependency clearance remains a separate release concern. Existing Webstore #61 was not worked on; any CI failure must be reported rather than hidden by rerunning.

## Automated verification and CI

- Relevant Assistant B–F, existing foundation/intelligence/voice, Gateway accounting/governance/contracts and Studio tests: **122 passed**, ten existing FastAPI/multipart deprecation warnings. Final targeted F tests rechecked after the cross-shop exact-ID assertion.
- Affected frontend: **33 passed across five suites**; the final message-label workflow additionally passed its two page tests.
- Production build passed; existing bundle-size and Node deprecation notices remain. Assistant ESLint zero errors/warnings; focused Flake8, Black and whitespace checks passed. Production assets exclude test harnesses, scripts, caches, evidence and uncleared audio. No dependencies changed.
- Required final-commit backend suite, frontend suite and build run in existing GitHub CI. Exact SHA, run links and final counts are recorded in [PR #63](https://github.com/dnblack323/SIGNGUY-MVP/pull/63) and the final owner report. This avoids an extra CI-triggering commit merely to stamp this document. The PR remains draft and unmerged.

## Live-test gate — prepared, not authorized

The existing [separate $5 proposal](BUSINESS_ASSISTANT_V1_LIVE_VERIFICATION_PROPOSAL.md) covers real text + follow-up, spoken conversation + follow-up, one read-only record lookup, interruption, transcription, observed usage and estimated-versus-provider-billed reconciliation. No substitute mocked test is counted as this gate passing.

Official documentation rechecked October 23: [Realtime sideband/call control](https://developers.openai.com/api/docs/guides/voice-server-controls?voice-api=realtime) still describes server control via call ID; [gpt-realtime-2.1](https://developers.openai.com/api/docs/models/gpt-realtime-2.1) documents tool use and the existing sourced rate family. Documentation is not account/model-access or compatibility proof. Preserve the selected model; no migration to another voice API is implied.

**Not safe to run on production defaults or merely set the enable flags.** Before any authorized paid attempt, all of these preconditions must be recorded:

1. Owner selects the exact allowed Responses text profile and approves the $5 total. A backend-only key for a dedicated evaluation project/account and actual access to `gpt-realtime-2.1`, the selected stock voice, and `whisper-1` (or a supported configured transcription model) must be verified without speculative paid calls. No real customer data or production DB/environment.
2. Configure the isolated process's effective text limits to two provider responses/turn, 256 output tokens and 16 KiB total request context, two user turns. These text settings are runtime attributes, **not currently environment overrides**; a controlled evaluation launcher must apply/assert them before admission. Voice environment caps: 60 seconds, 15 idle, four responses, 256 output tokens; set the runtime voice context bound to 2,048. The evaluation supervisor must enforce three utterances and at most one read tool/turn, while the server's ordinary input-turn ceiling is linked to its response ceiling. Stop if those tighter proposed limits are not in effect; do not silently use normal defaults.
3. Active OpenAI provider/model/capability allowlists, sourced text/audio/cache/transcription rates, disposable entitlement/credits, and a $4.50 Gateway provider-cost policy plus $0.50 contingency must admit the **conservative complete-run** cost. Calculate it from the actual chosen text rates and all bounded voice/transcription inputs before enabling. Check applicable taxes/account charges and ensure no concurrent spender; account alerts alone are not a hard cap. If the inclusive $5 bound cannot be established, stop before dispatch.
4. A real microphone/speaker, HTTPS or localhost, network access to Responses and Realtime call/sideband/hangup endpoints, and a running recovery worker are required. First unsupported protocol, inaccurate fact, unauthorized tool, missing usage, interruption/hangup failure, overrun or uncertain accounting stops the attempt. No automatic retries/reconnect, no second session, no model fallback. Keep conservative liability until reconciled.

These unresolved owner/configuration prerequisites prevent immediate execution; they do not require a new product stage. Live compatibility, prompt/tool behavior, real speech/transcription/interruption and provider billing remain **release blockers** even after this free closeout.

## Voice-preview gate

All six paths and the existing click-only static player are ready: `alloy`, `ash`, `coral`, `echo`, `sage`, `shimmer` at `/assistant-voice-samples/<voice>.wav`. Selection is independent of playback/personality; no preview click calls a provider. Existing tests cover free playback/failure/cleanup. No downloaded documentation recording was used in this run or included in production.

The separate **$1 total proposal** for six original own-account recordings, exact original script, no retries, provenance/hashes and AI disclosure remains in the [Stage D report](BUSINESS_ASSISTANT_V1_STAGE_D_REVIEW.md#six-preview-recordings-researched-proposal-not-executed). No generation allowance is authorized. After generation/inspection/owner approval, install those six assets, explicitly update the catalog's availability/provenance and approved packaging exclusion, and run existing playback tests. This is a bounded asset/catalog activation, not a Stage C redesign; dropping files in place does **not** automatically enable production previews.

## Owner configuration and commercial decisions

| Decision | Current behavior / required approval |
|---|---|
| Text model | Select an allowed Responses/tool-calling profile, sourced input/output rates and account access. No production model was selected or changed here. |
| Voice model/transcription | Engineering targets `gpt-realtime-2.1`, six catalog voices and a sourced compatible transcription profile. Actual account access/quality remains unverified. |
| Session duration and usage | Current normal defaults: 180 seconds/session, 45 idle, 12 responses, 600 output tokens/response, 4,096 post-instruction context tokens; voice starts normally limited to 10 per 60-second window. Approve commercial values after measurements. |
| Text limits | Current runtime defaults: 20 history messages, 32,000 context bytes, 1,000 output tokens, three provider responses/turn, 20-second request timeout. No unlimited history. |
| Monthly AI allowance and credits | Approve included credits/month, per-capability charges, top-up/overage/refund policy through existing Gateway/commercial configuration. No subscription price, entitlement or allowance was changed. |
| Shop provider budgets | Approve daily cost cap and request policies. Current admission requires a configured cost policy and reserves conservative liabilities; unknown outcomes may block more work until reconciled. |
| Provider-cost reporting | Observed token/modality/cache/transcription usage is provider-reported when complete; dollar costs remain estimates; `actual_cost_micros` stays unknown until verified provider billing is available. Decide who reconciles and how verified bills are imported/reviewed. |
| Exhausted credits/budgets | Deny new paid dispatch; preserve text/history/settings access as permitted. No silent fallback, free paid request, automatic top-up or unmetered retry. Voice stops when access/budget changes; local media now stops even if remote hangup remains pending. |
| Employee access / retention | Existing owner/admin permissions work; default staff lacks Assistant use/Task creation. Separately approve least-privilege staff policy and transcript retention/deletion procedure before advertising those capabilities. No automatic purge is implied by a retention label. |
| Environment and activation | Backend-only `OPENAI_API_KEY`; `ASSISTANT_TEXT_ENABLED`, `ASSISTANT_TEXT_MODEL_PROFILE_ID`; `ASSISTANT_REALTIME_ENABLED`, `OPENAI_REALTIME_ENABLED`, `ASSISTANT_VOICE_MODEL_PROFILE_ID`, `OPENAI_REALTIME_MODEL`; voice caps `ASSISTANT_VOICE_MAX_SECONDS`, `ASSISTANT_VOICE_IDLE_SECONDS`, `ASSISTANT_VOICE_MAX_RESPONSES`, `ASSISTANT_VOICE_MAX_OUTPUT_TOKENS`, start window `OPENAI_REALTIME_RATE_LIMIT_SESSIONS`/`OPENAI_REALTIME_RATE_LIMIT_WINDOW_SECONDS`, transport `OPENAI_REALTIME_TIMEOUT_SECONDS`. Enabled flags default false; credentials alone never activate. |

Production activation additionally requires approved entitlements/allowlists/credits/budgets, resolved live and preview gates, retained startup/auth/tenant controls, owner-approved data/retention and operational reconciliation policy, current CI, and **separate merge/deployment authorization**. Neither this report nor Stage F creates that authorization.

## Final disposition

Free Stage F verification is complete for engineering acceptance. The branch retains B–E and only the necessary F corrections, tests and consolidated evidence. Known limits: bounded word-based memory, professional template drafts (not autonomous email), no actual voice quality/cost proof, no approved audible previews, no automatic transcript purge, and operator review for uncertain provider/canonical outcomes. No claim of commercial readiness. **Stop at the live-testing/preview approval gate.**
