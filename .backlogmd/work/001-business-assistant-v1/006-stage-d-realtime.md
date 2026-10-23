<!-- METADATA -->

```yaml
task: Stage D shared server-controlled Realtime conversations
status: done
priority: 9
dep: ["work/001-business-assistant-v1/004-stage-b-implementation.md"]
assignee: ""
requiresHumanReview: true
expiresAt: null
```

<!-- DESCRIPTION -->

Owner accepted Stage D engineering implementation and mocked verification in the Stage E authorization, October 22. Live compatibility and commercial readiness are not accepted by this decision.

Owner explicitly accepts C as D's engineering foundation while retaining preview clearance as a V1 release requirement. D may proceed without marking task 005 fully accepted. Extend existing conversations/context/tools/personality and Gateway; media-only WebRTC plus backend sideband, canonical transcripts, interrupt/recovery and server budgets. No paid calls, E/F, merge or deploy. Preview procedure/cost research only.

<!-- ACCEPTANCE -->

- [x] Shared text/voice context, private canonical transcripts and source links.
- [x] Six saved voices/all personalities; server-only tools/credentials and fresh permissions.
- [x] Duration/idle/response/concurrency/budget limits, reservations and idempotent observed usage.
- [x] Interrupt, end, reconnect, orphan recovery, cleanup and text fallback.
- [x] Mocked regressions/browser/build/quality and required CI; live limitations explicit.
- [x] Preview generation procedure, estimated cost and rights/disclosure documented without generation.

Implementation and local verification complete. Required exact-head CI is recorded on the existing draft PR #63 checks after publication; owner review is not acceptance. The six documentation recordings remain excluded, with separately authorized generation still pending. No E/F or release.
