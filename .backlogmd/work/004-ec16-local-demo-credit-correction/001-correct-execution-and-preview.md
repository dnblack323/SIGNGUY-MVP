<!-- METADATA -->
```yaml
task: Enforce trusted execution and matching free demo previews
status: review
priority: 10
assignee: /root
requiresHumanReview: true
expiresAt: null
```
<!-- DESCRIPTION -->
Keep canonical EC16 accounting. Identify actual registered local providers and missing provider executors; enforce permissions, entitlement and availability before idempotent execution or reservation. Existing billable mock records must remain free; previews/UI must agree. Inspect PR #63 interaction read-only.
<!-- ACCEPTANCE -->
- [x] Local demo included/purchased/reserved balances unchanged, including zero-credit and preexisting billable capabilities; production denied before reservation.
- [x] Provider-backed configured charges and failure settlement retained with isolated test executor; unknown/unconnected providers fail closed.
- [x] Permissions, tenants, governance, usage/cost history and idempotency preserved; forged client billing/execution flags cannot bypass policy.
- [x] Webstore and Studio availability/credit presentation reflects backend execution; no misleading generated images.
- [x] Focused backend/frontend regressions and isolated browser smoke pass; evidence/EC16_LOCAL_DEMO_CREDIT_CORRECTION.md records 45 backend and 15 distinct frontend tests and the zero-credit account capture.
- [ ] Owner acceptance of one focused draft PR with normal six-check CI; final receipt in GitHub and existing local Webstores/release checklists. No merge/deploy.
