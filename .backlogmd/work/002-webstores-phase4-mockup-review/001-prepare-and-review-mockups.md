<!-- METADATA -->
```yaml
task: Prepare reviewed mockups and show protected submitted images to owners
status: review
priority: 10
assignee: /root
requiresHumanReview: true
expiresAt: null
```
<!-- DESCRIPTION -->
Add artwork/mockup preparation to existing product review controls using managed uploads, explicit staff image review and existing associations. Render submitted mockup images through authenticated owner access, binding them to existing submission evidence. Preserve last submitted images and approval history through private replacements. Document remaining Phase 4 dependencies and real AI readiness. User explicitly authorized implementation without routine confirmations.
<!-- ACCEPTANCE -->
- [x] Staff can upload or select artwork and mockup files and attach a reviewed mockup to a product.
- [x] Owner sees only submitted product/mockup content, can inspect the actual image, and approve or request changes.
- [x] Private revisions preserve submitted image identity and approval history; public eligibility remains unchanged.
- [x] Focused backend/frontend tests cover permissions, tenant scope and protected asset access.
- [x] Real isolated staff/owner browser checks and screenshots captured. Evidence: evidence/WEBSTORES_PHASE4_MOCKUP_REVIEW.md.
- [ ] Owner acceptance of the focused draft PR and its normal CI receipt. Exact PR/head/check status belongs to the PR and existing local checklist; no automatic merge.
- [x] Existing checklist/roadmap and AI readiness assessment updated; no P1/P2 or paid calls.
