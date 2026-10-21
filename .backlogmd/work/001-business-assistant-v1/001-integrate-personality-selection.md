<!-- METADATA -->

```yaml
task: Integrate five personality choices into Business Assistant V1
status: plan
priority: 10
dep: ["work/001-business-assistant-v1/002-stage-a-review.md", "work/001-business-assistant-v1/003-stage-b-review.md"]
assignee: ""
requiresHumanReview: true
expiresAt: null
```

<!-- DESCRIPTION -->

Implement the personality requirements through the existing assistant as part of the A–F feature sequence, after the applicable Phase Review Report and owner approval. [The implementation plan](../../../docs/BUSINESS_ASSISTANT_V1_IMPLEMENTATION_PLAN.md) owns the source comparison, configuration/persistence/prompt design, stage integration, risks and complete acceptance matrix. This is planned product work; creating this task does not mean it has been implemented or tested.

<!-- ACCEPTANCE -->

- [ ] Required scoped phase review and Code Quality Assessment are presented and approved before code starts.
- [ ] Reuse the four original identities and selectable-card behavior; add the exact Sarcastic & Funny name, warning, description and rules.
- [ ] Persist per-user settings on canonical records; verify logout/login, failed saves, user/tenant isolation and independent voice updates.
- [ ] Share one backend catalog/prompt definition across real text, full-page, floating and Realtime; changing personality preserves memory and conversation.
- [ ] Prove sensitive-topic care, neutral customer artifacts and identical facts, pricing, permissions, tools and confirmations across all five.
- [ ] Complete the plan's mocked-provider, browser and separately capped live-response/voice evidence without overstating what was verified.
- [ ] Obtain owner review of the completed feature; required CI and any future PR/merge boundaries remain explicit.
