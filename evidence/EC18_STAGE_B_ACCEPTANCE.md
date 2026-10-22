# Business Assistant Stage B final acceptance evidence

**Subsequent owner acceptance:** Stage B explicitly accepted October 21, 2026 for its approved scope, with the limitations below. Commit 7fa5e8a / draft PR #63 passed hosted CI: 1,457 backend tests, 237 frontend tests and production build. Historical pending-acceptance statements below are superseded; commercial readiness, live provider compatibility and merge remain unapproved.

October 21, 2026. Owner approved the intended functional scope and authorized this focused acceptance check, commit, draft PR and CI. Full Stage B acceptance is still pending. No Stage C implementation, live OpenAI call, paid evaluation, merge or release was authorized or performed.

## Webstore comparison and diagnosis

Baseline: unmodified `origin/main` **7973c8b** (current main after PR #59); Assistant code baseline remains **0f1c1cb**. `git archive origin/main` was extracted inside the existing Assistant worktree's ignored `.cache/stage-b-acceptance/unchanged-main`. The original Webstore test and production files were not edited. Each pytest invocation used the existing owned, disposable MongoDB bootstrap; no developer database/server or real provider was used.

- Original test `backend/tests/test_webstores_stage4a_product_foundation.py::test_stage4a_product_image_activity_metadata_and_staff_preview` on unchanged main: **failed** at line 723, returning `webstore.product_image_added` before the expected `webstore.product_draft_updated`.
- Subsequent read-only instrumented main executions: **passed**. Assistant branch original test: **passed**. The bounded diagnostic was not a CI retry policy and introduced no sleeps, increased timeouts or changed assertions.
- A separate diagnostic fixture against the unchanged feed inserted draft_updated, Primary-image and Secondary-image events with exactly the same created_at. Reversing the feed to oldest-first did not preserve insertion chronology, reproducing the missing total-order contract. Original tests and production code stayed untouched.
- `webstore_staff_product_updates.py` writes the draft event then image events sequentially. `webstore_activity_feed` sorts solely on created_at descending. Equal timestamps have no insertion/sequence tie-breaker. A random UUID tie-breaker would not establish chronology.
- **Confirmed:** pre-existing intermittent test failure, independent of Stage B, and unstable feed ordering for timestamp ties. **Likely mechanism of the naturally observed failure:** timestamp collision. The failing run's database was disposed before diagnostic capture, so do not claim its exact timestamp collision was directly observed. Not evidence of a Stage B Webstore regression.
- Separate tracked correction: [Webstore issue #61](https://github.com/dnblack323/SIGNGUY-MVP/issues/61). No unrelated Webstore production fix or assertion weakening is included in the Assistant PR.

SHA-256 comparison against unchanged main:

| File | Assistant SHA-256 | Main comparison |
|---|---|---|
| `backend/tests/test_webstores_stage4a_product_foundation.py` | `0187836263b302ca1034b27df618afc45a889e51995ebd04da9fe8a834ad03ae` | identical |
| `backend/app/services/webstore_shared_audit.py` | `c982a0471e239655c8bb396b889cfb360244a6b0991a7983ff4f3165d8051dbe` | identical |
| `backend/app/services/webstore_shared_catalog.py` | `c29317c20d1091ba5c8f66a7782c6b2c3373450f13dc1c99b18c237edc6cf567` | identical |
| `backend/app/services/webstore_staff_product_updates.py` | `3ab00fe31342979af62cf3748bb60aff1c8dff38e5f7e6fcf9002cee720e87e2` | identical |
| `backend/app/services/activity.py` | `d605eead5b2acf3e80a852c87d41f63da22fae330ce933bde2cd8faaab53587c` | identical |
| `backend/app/models/base.py` | `de666ff773291bea2ea596eb8efacf9107a4a2e23c96ec86f06d7d5545fbe93d` | identical |

## Focused dependency classification

Reproduced the unchanged lockfile audit: **276 affected paths / 89 unique advisories**, with 4 critical, 182 high, 89 moderate and 1 low path findings. These are not 276 distinct vulnerabilities. No package/lockfile change was introduced by Stage B. The detailed [89-row classification](EC18_STAGE_B_DEPENDENCY_CLASSIFICATION.csv) records all advisory IDs, direct/transitive dependency paths, reachability conditions and candidate corrections.

The audit's devDependencies=0 is not a deployment classification: react-scripts is under package.json dependencies. `frontend/Dockerfile` builds with Node and ships only compiled assets in nginx; the API runtime is Python.

| Group | Classification and reachability | Candidate correction |
|---|---|---|
| Critical `tar` / GHSA-23hp-3jrh-7fpw (one path) | Transitive optional canvas/native-package install archive extraction, outside deployed browser/API runtime; install/build supply-chain risk remains | Compatible parent update; listed tar advisories extend through 7.5.21. Do not force tar 6 to 7 blindly. |
| Critical `shell-quote` / GHSA-pqg4-j6r4-53mv (two paths) | Transitive react-dev-utils/launch-editor development command construction, absent from deployed nginx runtime | >=1.11.0, validate command/editor behavior and existing override. |
| Critical `proxy-addr` / GHSA-jqcg-44mw-7w3h (one path) | Transitive Express dev-server proxy trust, absent from production nginx/Python stack | >=2.0.8 and explicit correct proxy-trust configuration; validate development server. |
| Direct browser `fabric` | Canvas markup is used; no toSVG/loadFromJSON trigger in source. Reported SVG serialization exploit chain not observed. | >=7.4.0 is a major migration needing markup parity verification. |
| Direct browser `pdfjs-dist` | PDF parsing/page-to-canvas is reachable, but viewer scripting manager is not instantiated. Do not claim arbitrary PDFs are proven safe. | >=6.2.108 requires major compatibility and scripting/CSP checks. Adding a viewer-only option to getDocument is not proof of a fix. |
| Direct browser `axios` | Assistant uses browser XHR/fixed application APIs; Node proxy/HTTP2 paths are absent. Other advisories require prior prototype pollution, alternate adapters, or untrusted serializer control; complete Assistant exploit not confirmed. | >=1.20.0 with auth/header/upload regression tests; not a reason to blindly update every dependency. |
| `react-router` via direct `react-router-dom` | Current declarative BrowserRouter does not use Framework/RSC/SSR features. Backslash redirect issue is conditional on attacker-controlled navigation; Assistant citations use server-constructed paths. | Align both packages >=7.18.2 and test routes/auth/dock. |
| Remaining paths | Build/development/test parsers and CSS/SVG tooling; form-data/follow-redirects are Node adapter/tooling paths. No blanket runtime-security exemption. | Compatible parent/branch patches; braces/sprintf-js list no patched release and need separate replacement/parent review. |

Advisory sources: [tar](https://github.com/advisories/GHSA-23hp-3jrh-7fpw), [shell-quote](https://github.com/advisories/GHSA-pqg4-j6r4-53mv), [proxy-addr](https://github.com/advisories/GHSA-jqcg-44mw-7w3h), [Router redirect](https://github.com/advisories/GHSA-wrjc-x8rr-h8h6), [PDF.js](https://github.com/advisories/GHSA-hq66-cqwq-w95j). Reachability is a static application/deployment assessment, not penetration-test proof.

**Decision:** no confirmed blocking advisory in the authorized Stage B text surface was found. No blind upgrade was performed. Unrelated/conditional/browser and tooling findings remain tracked in [dependency-maintenance issue #62](https://github.com/dnblack323/SIGNGUY-MVP/issues/62); production release is not granted a blanket security clearance.

## Stage B safety verification

Rechecked existing code and focused regression tests: tenant/user ownership, permission-aware tools/citations/history, inherited follow-up provenance, source-linked memory, changed permissions after response generation, private billing history, stable request fingerprints, duplicate/concurrent turn rejection, credit reservations, in-flight budgets, missing/observed usage, pre-dispatch failures, failed provider loops and timeouts. A new regression revokes permissions during the mocked provider response and verifies the restricted completion is neither returned nor saved and no customer credits are committed.

Only eight typed read tools are exposed to the model. There is no write/send/execute tool. Permanent provider keys are read only by the backend transport; tests use dummy keys and mock provider/HTTP transport. Existing visible preview/edit/confirm workflows remain separate. Text context, personality definitions, permissions and tool dispatch are transport-independent; no second voice business logic was created.

Local exit verification: 61 relevant backend tests passed; 74 relevant frontend tests passed; CI-mode production build passed; focused ESLint (0 errors/warnings), Flake8 correctness/unused-import checks, Black check and git diff --check passed. Previous full local backend result was 1,454 passed with the now-diagnosed unrelated Webstore failure, one skip and one expected failure; previous full frontend was 229 passed. Hosted current-head CI is authoritative for its run and must be reported separately after publication, including unchanged-main flaky failures rather than hidden reruns.

## Stage C readiness (read-only preparation)

The owner's latest Stage C scope explicitly includes voice selection/preview, Realtime, natural conversation, shared history/personality/tools, and voice cost controls; this supersedes the earlier plan's C-preview/D-Realtime split. No Stage C code was started.

- Reuse MVP's WebRTC/data-channel connection, push/VAD/interruption/reconnect/text-fallback controls, backend ephemeral credential boundary, session records, hashed safety identifier and ownership checks. Current `create_realtime_session` still has fixed instructions/global voice and a separate proposal tool, and browser-derived usage is not trustworthy cost reconciliation; these are future integration gaps, not completed voice proof.
- Read-only original `signguyai/backend/routes/ai.py` voice input/output: `/voice/transcribe` at 2917 uses Whisper, bounded filename suffixes and temporary-file cleanup; `/voice/speak` at 3002 uses TTS, independent voice/speed, capped text and credit previews/deductions. It is not the preferred new Realtime architecture and its Emergent wrappers/fallback credentials/client-returned audio are not to be wholesale imported. Useful donor behaviors are format handling, errors and independent voice settings, adapted through MVP.
- Before implementing C, require its owner-approved review and current official API/voice verification; reuse assistant_context, assistant_tools, assistant_personality and canonical Gateway ledgers. Add server-enforced audio/session budgets and trustworthy usage observation. Live compatibility/listening/latency/cost proof still requires separate paid-test authorization.

## Save and stop boundary

The existing `feat/business-assistant-v1` branch receives the Stage A/B commit and draft PR, with links to issues #61/#62. Owner acceptance remains pending. Do not merge, activate providers/commercial values or start Stage C automatically.
