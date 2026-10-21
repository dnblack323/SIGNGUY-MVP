# Owner Portal Store Setup authentication correction

Owner-authorized handoff correction D1, 2026-10-21. Based on main `0f1c1cb`.
No Phase 4 features, permission changes, payment changes, production release or merge.

## Focused pre-implementation assessment

| Subsystem | Assessment | Smallest correction |
|---|---|---|
| Shared branding editor | Needs cleanup: portal mode reads setup files through the staff client and shares its cache | Select the existing portal endpoint/client; separate staff and portal query keys |
| Existing portal setup-files service | Clean: tenant plus active assignment checks, active files only, explicit safe fields | Reuse unchanged |
| Staff API auth-failure handling | Needs cleanup: redirects every surface to staff login or suspension page | On `/portal` routes leave portal navigation/authentication to the portal client; preserve normal staff handling elsewhere |

Existing review doc 11 already identified D1 and its correction; the October 21 owner handoff explicitly authorizes immediate implementation and a separate unmerged PR. No further scope approval is inferred.

## Behavior

Owner branding reads `GET /api/portal/webstores/{id}/setup-files` using the portal token. Staff branding retains its staff endpoint. The two file queries cannot share staff-only cached metadata. Backend authorization remains unchanged. A rejected staff request while viewing the portal still rejects to its caller but cannot redirect the portal to staff login/suspension or clear a separate staff token.

## Verification

- 20 frontend tests passed across `WebstoresStage3Branding.test.jsx` and `StaffApiPortalIsolation.test.js`. Includes owner-only route selection, shared-cache isolation, rejected staff 401s/tenant-suspension responses in the portal and retained staff logout/suspension behavior outside it.
- One focused backend regression passed in a private, disposable MongoDB through the existing test bootstrap. Includes real invitation token, unauthenticated denial, owner-only reads of all Store Setup APIs, active-file/safe-field projection, other-store and other-tenant denial, and rejection of staff/portal token crossover. No auth dependency override is active during those checks.
- Browser smoke used the existing guarded harness on backend 8126 / frontend 3126 with its own private MongoDB, random credentials, `AUTH_DEV_BYPASS=false`, blank provider secrets and isolated storage. Target preflight verified the frontend proxy and rejected dev auto-login. A fresh origin signed in only through Portal sign-in: opened Store Setup, viewed questionnaire/branding/products/packet/terms, saved a branding draft, and reloaded while retaining the owner session. No terms or commercial approvals were accepted.
- Screenshot: [owner Store Setup](webstore_owner_setup_auth.png). This supplements the existing 18 acceptance images; the full acceptance matrix was not rerun.
- On Windows the local CRA/Jest matcher mishandles the escaped `.codex` directory. The two affected suites were selected using `--testMatch '**/src/**/__tests__/*test*' --runTestsByPath ...`; application/test configuration was not changed.
- Required GitHub CI is evaluated on the PR head; consult its live checks. Local focused tests do not replace required CI or owner merge authorization.

The source checkout, owner documents, existing stashes and unrelated held PRs are preserved. The smoke host's exact owned processes and private database are disposed after verification.
