# EC12 Phase 12G Completion Report

**Date:** 2026-07-17  
**Scope:** EC12 Phase 12G - Community, Founders Area, Bug Reports, Feature Requests, Voting, and Support Routing  
**Branch:** `CODEX-ec12-branch`  
**Implementation commit validated by CI:** `8c4c5c74db9d4c076a11e784bdc0e6ea7777e8d7`  
**GitHub Actions:** run `29575234924` passed `backend-tests`, `frontend-tests`, and `frontend-build`.

## Existing Systems Reused

- Existing staff authentication, role permissions, tenant scoping, Activity/Audit service, Notifications service, file records, customers/orders/tasks linked-record validation, AppShell navigation, and Help & Community flyout.
- Existing EC12 productivity stack remains authoritative for tasks, communications, calendar, shop schedule, Employee Portal account experience, and notifications.
- Existing Template system, onboarding system, subscriptions, feature entitlements, billing, pricing, payroll, production, quote/order, and customer portal systems were not duplicated or mutated.

## Implementation Summary

- Added canonical community/support models for `CommunitySpace`, `CommunityPost`, `CommunityComment`, `CommunityVote`, `FeatureRequest`, `BugReport`, `FounderAccess`, `SupportRequest`, and `SupportRequestNote`.
- Added one backend community service and router under `/api/community` for spaces, posts, comments, voting, feature requests, bug reports, explicit founder access grants/revocations, support route preview, support requests, support internal notes, and moderation actions.
- Added tenant/platform/founder community scopes with backend access checks.
- Added explicit platform-managed founder access; founder access is not inferred from subscription, billing, email address, or tenant status.
- Added support routing that distinguishes tenant-admin requests from platform-admin requests and returns visible destination labels before submission.
- Added moderation controls for posts/comments, abuse reports, rate-limit checks, secret-like content rejection, idempotency keys for append-only actions, and audit/activity records.
- Added one compact frontend `CommunityPage` with Community, Founders, Bugs, Features, and Support tabs.
- Enabled only the existing Help & Community flyout items for Phase 12G routes; Help Center, Documentation, Onboarding, and What's New remain disabled.

## Security and Tenant Isolation

- Tenant community spaces and posts are visible only to the owning tenant.
- Platform spaces and feature/bug feedback are visible to staff users through staff permissions.
- Founder spaces are visible only to explicit founder users and platform admins.
- Platform/admin mutations are checked in the service layer even when a user has broad route permissions.
- Customer portal tokens are denied from staff community routes.
- File attachments for bug reports must reference tenant-owned files.
- Linked customer/order/task records are tenant-validated before being attached to posts or support requests.

## Support Boundaries

- Tenant operational support routes to active tenant admins when available.
- Platform/product/account/privacy support routes to platform admins.
- Support request lists are filtered by requester, tenant admin destination, or platform admin authority.
- Internal support notes are only returned to the appropriate admin role when explicitly requested.
- Support routing does not create billing, entitlement, subscription, or commercial records.

## Customer-Safe and Commercial Boundaries

- No customer-facing community route was added.
- No Quote, Order, Order Item, pricing, proof, production, payroll, or commercial billing mutation was added.
- No paid Template Vault, paid support package, subscription inference, billing, EC13, EC19, or EC20 implementation was added.
- Base-app community/support remains usable without paid template packs.

## Validation

- Local compile passed: `python -m compileall backend/app backend/tests/test_ec12_phase12g_community_support.py`.
- New targeted backend test passed:
  `python -m pytest backend/tests/test_ec12_phase12g_community_support.py -q` -> 3 passed.
- EC12 targeted backend stack plus permission scope passed:
  `python -m pytest backend/tests/test_permissions_scope.py backend/tests/test_ec12_phase12a_tasks.py backend/tests/test_ec12_phase12b_tasks_experience.py backend/tests/test_ec12_phase12c_time_off.py backend/tests/test_ec12_phase12d_calendar_appointments.py backend/tests/test_ec12_phase12e_communications.py backend/tests/test_ec12_phase12f_employee_account_experience.py backend/tests/test_ec12_phase12g_community_support.py -q` -> 20 passed.
- Frontend tests passed: `yarn.cmd test --watchAll=false` -> 7 suites, 29 tests.
- Frontend production build passed: `yarn.cmd build`.
- `git diff --check` passed.
- GitHub Actions run `29575234924` passed `backend-tests`, `frontend-tests`, and `frontend-build`.

## Targeted Test File

- `backend/tests/test_ec12_phase12g_community_support.py`

## Known Gaps

- Phase 12H and EC12 closure remain not started.
- Help Center, documentation, onboarding, contextual help, and what's-new surfaces remain EC19 or later scope.
- Paid Template Vault, support billing, platform admin analytics/dunning, and commercial entitlements remain later-checkpoint scope.
- External support integrations, public roadmap publishing, and customer portal community participation remain not started.

## Status

- Phase 12G COMPLETE.
- Phase 12H and later NOT STARTED.
- EC12 remains IN PROGRESS.
- EC13 NOT STARTED.
- EC19 NOT STARTED.
