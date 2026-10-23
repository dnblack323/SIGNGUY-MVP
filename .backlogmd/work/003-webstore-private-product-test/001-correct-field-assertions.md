<!-- METADATA -->
```yaml
task: Assert submitted product fields without matching timestamp digits
status: review
priority: 10
dep: []
assignee: /root
requiresHumanReview: true
expiresAt: null
```
<!-- DESCRIPTION -->
Check submitted price, name, description and image content explicitly. Retain whole-response private-content guards and prove a legitimate timestamp containing 9900 is accepted. Production Webstore code stays unchanged.
<!-- ACCEPTANCE -->
- [x] Deterministic timestamp collision covered for all three approval decisions.
- [x] Affected Webstore tests pass (12 tests; 6 existing deprecation warnings); whitespace check passes.
- [ ] Required CI and separate PR owner acceptance (exact results maintained on the PR).
- [x] Assistant #63 remains draft and unchanged; correction is isolated on codex/webstore-private-product-test.
