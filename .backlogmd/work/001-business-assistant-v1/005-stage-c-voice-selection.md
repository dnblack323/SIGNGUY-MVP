<!-- METADATA -->

```yaml
task: Implement Stage C voice selection preview and readiness
status: review
priority: 8
dep: ["work/001-business-assistant-v1/004-stage-b-implementation.md"]
assignee: codex
requiresHumanReview: true
expiresAt: null
```

<!-- DESCRIPTION -->

Owner accepted Stage B and authorized Stage C. Restore original C/D split per docs/BUSINESS_ASSISTANT_V1_STAGE_C_REVIEW.md. Use existing private preferences, shared Assistant state and interfaces. No paid generation/evaluations, full Realtime integration, Stage D–F, merge or unrelated work.

<!-- ACCEPTANCE -->

- [x] Compatible voice selection persists per user independently of every personality.
- [x] Prerecorded sample comparison works on demand without paid requests.
- [x] Microphone readiness has start/end, clear state/errors, cleanup and text fallback.
- [x] Paid session creation fails closed during Stage C; Gateway architecture is preserved.
- [x] Focused backend/frontend tests, browser smoke, build and quality checks pass; live limits are documented.

Evidence: evidence/EC18_STAGE_C_EVIDENCE.md. 51 backend / 20 frontend passed; build/quality passed. All six bundled samples played in the real browser; physical microphone capture and live provider quality/latency remain unverified. Stage D–F, paid calls and merge remain held. Owner review required.
