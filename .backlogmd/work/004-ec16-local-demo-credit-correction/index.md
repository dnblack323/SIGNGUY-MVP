<!-- METADATA -->
```yaml
work: EC16 local demonstration credit correction
status: in-progress
assignee: /root
```
<!-- DESCRIPTION -->
Owner-authorized focused correction from attachment 7495a363-ed9d-4543-9e95-7084acde81fc. Base main 1a1f0b4f723e73f8033ff266fa185998b28bde4e. Reuse Gateway balances, settlement, capability configuration and ledgers.

Implementation and focused verification complete; task in owner review. 45 backend and 15 distinct frontend tests passed, plus actual zero-credit Webstore/credits-history browser smoke in a disposed private environment. Evidence: evidence/EC16_LOCAL_DEMO_CREDIT_CORRECTION.md. Normal CI/draft PR receipt maintained in GitHub and existing local checklist. PR #63 shared Gateway hunks require reconciliation in its own conversation; its worktree was not modified. Overall item remains in progress pending owner acceptance.
<!-- CONTEXT -->
Correct trusted execution classification before reservation across Gateway, Studio, Webstores and existing Assistant callers. Local demonstrations must be free in explicitly nonproduction execution and unavailable in commercial production. Unconnected provider profiles must not simulate paid success. Preserve existing accounting tests using test-only injected provider execution, not customer-controlled flags. No provider implementation/calls, historical mutations, pricing changes, Business Assistant feature/worktree modifications, P1/P2, image generation, merge or deploy. One focused draft PR, normal CI, owner acceptance stop.
