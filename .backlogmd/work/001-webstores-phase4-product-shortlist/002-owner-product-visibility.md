<!-- METADATA -->
```yaml
task: Keep unfinished product revisions private until staff submits them
status: review
priority: 20
dep: []
assignee: /root
requiresHumanReview: true
expiresAt: null
```
<!-- DESCRIPTION -->
Owner authorized this correction in existing PR #64. Persist the existing safe approval snapshot on the canonical product at staff submission. Owner product lists and branding previews consume the same backend submitted projection. Preserve prior submitted content across staff edits and returned-for-changes/resubmission, retaining canonical approval history and public gates. Recover legacy submitted evidence from existing approval snapshots or verifiable unchanged submitted records; never infer old content from an edited draft. No new catalog, workflow, pricing or versioning system.
<!-- ACCEPTANCE -->
- [x] Never-submitted drafts stay staff-only; submission reveals the frozen product to its assigned owner.
- [x] Staff edits remain private; previously submitted/approved and returned products retain last shared content/history until resubmission.
- [x] Owner-facing responses and previews share backend rules; approval and public eligibility remain enforced.
- [x] Focused backend/frontend tenant/access/workflow tests and isolated browser demonstration pass; updated screenshots/report recorded.
- [x] Existing draft PR #64 handoff prepared; normal CI and exact head receipt are recorded in the local owner checklist at closeout. Stop for owner acceptance without merge/deployment.
