<!-- METADATA -->
```yaml
task: Connect explained questionnaire product matches to existing draft selection
status: review
priority: 10
dep: []
assignee: /root
requiresHumanReview: true
expiresAt: null
```
<!-- DESCRIPTION -->
Produce a tenant-scoped deterministic shortlist from existing active tenant/platform product templates and visible completed questionnaire answers. Explain matches, honor declined extra suggestions, flag unmatched requests and preserve staff choice. Show it in the existing Products tab; selecting a recommendation only selects the existing template control. Do not calculate/approve prices, invent stock facts or change owner approvals, files, mockups or publishing. Existing downstream draft behavior stays intact.
<!-- ACCEPTANCE -->
- [x] Questionnaire requests and declared store-type compatibility yield stable explained matches; drafts/hidden answers and archived/foreign templates are excluded.
- [x] No match is honest; no pricing, stock, personalization or shipping capability is invented.
- [x] Staff read/write and portal/tenant boundaries are verified; existing draft/approval paths remain usable.
- [x] Focused backend/frontend tests and isolated staff/owner browser evidence pass.
- [x] Draft PR handoff prepared and existing local checklist records scope, evidence and remaining dependencies; no merge/deployment.
