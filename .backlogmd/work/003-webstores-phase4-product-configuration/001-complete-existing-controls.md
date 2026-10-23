<!-- METADATA -->
```yaml
task: Complete existing configuration controls and submitted owner review
status: review
priority: 10
assignee: /root
requiresHumanReview: true
expiresAt: null
```
<!-- DESCRIPTION -->
Expose missing canonical variant/personalization fields in the existing editor without duplicate controls. Show enough submitted detail for meaningful owner approval. Use existing validation, snapshots, file/mockup and credit services. Record bounded EC16 compatibility and logo-accurate future mockup architecture; leave mock-credit runtime correction separate.
<!-- ACCEPTANCE -->
- [x] Staff can configure multiple size/color/SKU variants, active/inactive status and explicitly manual availability.
- [x] Staff can configure required/optional text, maximum characters, placeholder and select choices using existing fields; validation is clear.
- [x] Saved, submitted and owner-reviewed configuration agrees; private later edits do not change the submitted snapshot/history.
- [x] Focused backend/frontend tests and real isolated Hoodie browser workflow/screenshots pass.
- [x] Existing AI capabilities and precise separate follow-ups documented without paid calls or runtime AI changes.
- [ ] Owner acceptance of one draft PR with normal six-check CI; final PR/check receipt in live GitHub and existing local nine-phase checklist. No merge/deploy.

Evidence: `evidence/WEBSTORES_PHASE4_PRODUCT_CONFIGURATION.md` and its actual browser screenshots. 28 distinct backend and 30 distinct frontend tests passed through focused runs. Current human-review handoff remains pending; no further implementation authorized.
