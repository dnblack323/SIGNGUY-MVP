<!-- METADATA -->
```yaml
task: Connect and verify private product presentations
status: review
priority: 10
dep: []
assignee: /root
requiresHumanReview: true
expiresAt: null
```
<!-- DESCRIPTION -->
Implement one provider-connected increment behind a default-off server gate. Verify request construction, image bytes, private storage, staff review, original artwork composition, approval snapshots and EC16 accounting using an isolated transport double. Document current provider comparison and live-test gates. Keep PR #63 untouched.
<!-- ACCEPTANCE -->
- [x] Pinned adapter constructs bounded requests without automatic retries or paid activation.
- [x] EC16 owns authorization, configured charge, admission, reservation and settlement; ambiguous outcomes remain recoverable without redispatch.
- [x] Private validated assets require staff review and reuse the composer and owner submission workflow.
- [x] Focused tests and isolated browser screenshots complete; normal required CI remains a mandatory final PR gate, with live receipt in GitHub and the local checklist.
- [x] Provider research, limitations and PR #63 conflicts documented for one draft PR and owner acceptance. Final PR/head/checks are recorded in the existing local checklist without a self-referencing source commit.
