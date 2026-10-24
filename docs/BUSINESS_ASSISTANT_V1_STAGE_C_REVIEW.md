# Business Assistant V1 — Stage C boundary and review

## Final closeout — October 22, 2026

Stage C implementation is saved separately after B in commit `dd1e508`. The closeout correction retains all voice settings/preview code but **does not approve commercial redistribution of the downloaded recordings**. No explicit grant covering those six CDN recordings was established from the official speech guide, Services Agreement or Service Terms. Public availability and attribution are not themselves a redistribution license. This is an unresolved asset-clearance blocker to commercial in-app audible previews, not a claim that all OpenAI API speech is prohibited commercially.

- [Services Agreement §4.1/4.4](https://openai.com/policies/services-agreement/): customer output ownership applies to customer-generated output; other users' output is excluded. It does not establish our ownership of pre-existing documentation recordings.
- [Service Terms §8/§10](https://openai.com/policies/service-terms/): ChatGPT Voice Output has separate noncommercial restrictions; do not apply that automatically to API speech. Downloaded Licensed Materials have restrictive terms unless an applicable open-source license grants additional rights. No matching asset-specific license was found.
- [Official speech guide](https://developers.openai.com/api/docs/guides/text-to-speech): demonstrates audio/AI disclosure but supplies no identified redistribution grant for the six checked files. The MIT license in `openai/openai-fm` covers that repository; its tree at `434b7f7622900c7341bfe9f9737858fcfc310e8f` contains click/pressed WAVs, not these voice recordings, so it cannot be assumed to license the CDN clips.
- Exact six source URLs, original/bundled hashes and durations remain in [preview provenance](../evidence/EC18_STAGE_C_PREVIEW_SOURCES.json). Recordings are preserved only in ignored local `.cache/stage-c/voice-preview-recordings`, removed from public assets, and excluded from production Docker context. Owner-local harness playback requires explicit local-review mode; that harness is excluded from production.
- Production still offers all six voice selections with independent saved personality. Preview buttons clearly explain unavailability and cannot play audio or generate paid substitutes. To unblock, obtain asset-specific permission or separately authorize creation of our own six API samples, retaining applicable AI-disclosure/use restrictions. No message to OpenAI or paid request was sent.

Final local verification: **51 backend tests; 21 affected frontend tests; production build; ESLint 0 errors/warnings; Flake8; Black; whitespace checks passed**. Full Stage B text regressions were included. Production build inspection found no WAV recordings, cache, test harness, provenance JSON or browser screenshots. `.dockerignore` now excludes caches, evidence and backend/frontend test artifacts; backend Docker's source copy honors these exclusions, while final frontend nginx receives only compiled build assets. Actual container-image execution was not performed.

Final browser verification after the correction: all six preview buttons were visibly disabled with the licensing explanation; independent Ash/Sarcastic selection saved successfully; the full-page Assistant retained Ash and answered a canonical invoice question using the local scripted provider. Earlier refresh/logout/login/dock and sample-playback evidence remains recorded with its limits. [Current settings screenshot](../evidence/EC18_STAGE_C_SETTINGS.png). The disposable browser/server was closed and its owned test database cleaned through the existing harness.

Focused security/functional conclusion: no unresolved blocking code defect identified in authorized C settings/readiness; paid Realtime remains backend-blocked even with credentials configured. Commercial in-app preview asset clearance remains unresolved. Full Realtime, shared transcripts/tools/session usage and live provider verification stay in D. No merge or D start. Current-head full GitHub CI and exact closeout commit are recorded on [PR #63 checks](https://github.com/dnblack323/SIGNGUY-MVP/pull/63/checks), separately from local results and the earlier green `dd1e508` run.

Earlier implementation notes below are historical; the production asset restrictions above take precedence.

October 21, 2026. The owner accepted Stage B and authorized Stage C implementation. This restores the original C/D split: **C = independent saved voice, existing sample playback and microphone/interface readiness; D = complete Realtime integration**. The earlier note combining Realtime into C is superseded. No paid generation, Stage D–F, merge or deployment is authorized.

Scoped code-quality assessment before implementation:

| Boundary | Assessment | Stage C change |
|---|---|---|
| Canonical User preferences and shared Assistant state | Keep | Validate compatible voice keys; extend the existing preferences response and settings. Preserve personality and conversation records. |
| Existing settings and full-page/floating panel | Needs bounded cleanup | Reuse the panel and media playback; add sample comparison and safe microphone readiness with cleanup, cancellation and text fallback. |
| Existing Realtime path | Incomplete for commercial activation | Preserve for D, fail closed before any paid session creation during C. Do not extend its separate prompts/tools or browser-derived usage. |
| Gateway credits, budgets and accounting | Keep | No generated preview endpoint or new ledger. Static samples and local microphone checks incur no provider usage. Full voice reservation, observation and enforced sessions remain D. |

Use only voices documented for Realtime and with a verified public prerecorded sample. Bundle samples with source attribution, fetched from the public documentation CDN without API credentials. Play only after a click; never synthesize a fallback. These samples demonstrate the voice, not a selected personality or future live quality. If samples cannot be obtained, disclose the unavailable preview rather than substituting another voice.

Verification: per-user/shop persistence, invalid voice rejection, all voice/personality combinations, no provider dispatch from selection/preview/readiness, local media start/stop/denial/cancellation/unmount, affected Stage B tests and production build. Live voice quality/latency is explicitly unverified.
