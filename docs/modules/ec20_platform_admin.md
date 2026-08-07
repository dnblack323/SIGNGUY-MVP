# EC20 Platform Admin, Analytics, Dunning, and Support

Status: COMPLETE - CLOSED for the implemented Platform Admin checkpoint.

## Runtime Scope

EC20 adds the platform-operator cockpit for tenant oversight, support, communications, governance, and platform analytics.

Implemented surfaces:

- `/platform-admin` tenant dashboard with exact platform summary totals, bounded tenant list paging, tenant search, sample-data seeding, and links to all Platform Admin work areas.
- `/platform-admin/tenants/{id}` tenant cockpit with tenant profile, owner, plan, founder state, billing and day-based dunning state, email deliverability mini-summary, users, support impersonation, onboarding checklist controls, suspend/reactivate, manual paid reset, and support log.
- `/platform-admin/analytics` platform analytics with overview, charts, users, routes, sessions, referrers, errors, suspicious traffic, commercial conversion, feature usage, and AI cost/credit activity.
- `/platform-admin/broadcast-email` broadcast email to tenant owner audiences, with personalization placeholders, test send, deduped recipients, rate limits, email logs, and audit rows.
- `/platform-admin/site-settings` global announcement banner and maintenance mode controls.
- `/platform-admin/email-logs` email deliverability dashboard with summary tiles, filters, SendGrid/internal event detail, and per-tenant drill-in.
- `/platform-admin/audit-log` privileged action history with action, actor, tenant, entity type, and date range filters.
- `/platform-admin/impersonation-logs` support-mode session review and active session ending.

## Dunning Model

The EC20 draft's three-strike dunning wording is superseded by the authoritative EC13 day-based dunning model:

- Days 1-7: payment-failed warning period.
- Days 8-14: soft-restriction/grace period.
- Day 15+: eligible for suspension review, not automatic deletion.

The Platform Admin UI displays day-based dunning details: failed-since, days past due, last failure, last paid, manual grace, review day, review eligibility date, and suspension-review eligibility. The existing `/dunning-threshold` endpoint is retained for compatibility, but it now stores the per-tenant review day override as `dunning_review_after_days`.

## Safety Boundaries

- Sample Platform Admin data is disabled in production.
- Tenant suspension refuses tenants that contain a platform admin user.
- Maintenance mode blocks non-platform-admin write methods while allowing reads, platform-admin routes, auth, webhooks, and health checks.
- Broadcast sends require configured email service, per-admin rate limits, recipient dedupe, per-email logs, and a broadcast audit row.
- Impersonation creates support-mode tokens and logs sessions/audit metadata; admins must still obtain tenant consent before changing data.
- No routine tenant deletion UI or API was added for EC20.

## Verification

Focused local validation:

- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ec20_platform_admin.py -q` -> 11 passed, 6 warnings.
- `yarn.cmd build` from `frontend` -> compiled successfully.
- Direct current-service smoke against local data:
  - tenant list, limit 25: 238 ms, exact total/page/global summary returned.
  - broadcast counts: 1320 ms across 48,591 local tenants, no 10,000 cap.
  - email summary: 20 ms, bounced/delivered/complaints counted by distinct email log.
  - analytics 7d: 3256 ms, populated overview/errors/session data.

The existing localhost `8001` backend process may need to be restarted to pick up the latest code because process control was unavailable during verification.
