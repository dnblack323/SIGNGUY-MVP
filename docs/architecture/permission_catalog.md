# Permission Catalog (LOCKED — EC1 foundation)

## Scopes

Three disjoint permission scopes:

- **Staff (`Perm`)** — internal tenant users. Backend `require_permission(Perm.X)` accepts these.
- **Platform (`PlatformPerm`)** — cross-tenant operators. Never satisfies a `Perm` check.
- **Portal (`PortalPerm`)** — external portal identities (Customer, Employee, Webstore Owner, Webstore Manager). Never satisfies a `Perm` check.

Source of truth: `backend/app/core/permissions.py`.

## Backend enforcement is authoritative

- Every mutating route MUST use `require_permission(...)` from `app.deps`.
- Frontend permission checks control **visibility only**.
- Frontend consumes permissions from `/api/auth/me` — no hardcoded frontend role maps.

## Namespace list (EC1 landing)

`customer, lead, quote, order, order_item, work_order, invoice, payment, document, email, audit, user, role, dashboard (DEPRECATED), pricing, settings, integration, inventory, vendor, purchasing, employee, task, schedule, time_clock, timesheet, payroll, report, analytics, webstore, wrap_lab, ai_tool, ai_assistant, ai_prompt, ai_history, subscription, ai_credit, community, support`.

Platform namespace: `platform:creator, platform:admin, platform:tenant_read, platform:tenant_write, platform:tenant_status, platform:audit_read, platform:broadcast_write, platform:subscription_admin, platform:ai_credit_admin`.

Portal namespace: `portal:customer_view, portal:customer_approve, portal:customer_sign, portal:customer_pay, portal:customer_message, portal:employee_view, portal:employee_time_clock, portal:employee_timesheet_view, portal:employee_payslip_view, portal:webstore_owner_admin, portal:webstore_manager_ops`.

## MVP role maps (preserved)

- `owner`, `admin` receive every staff Perm.
- `staff` receives the working MVP subset (see `STAFF_PERMS` in `permissions.py`).
- Future roles land in later checkpoints per Final Scope Register Part 9.

## Platform Creator Addendum

- `PLATFORM_CREATOR` is a stored backend platform role for the owner-approved platform creator account.
- Runtime platform-creator authorization is based only on stored user fields (`platform_role`, `platform_admin`, or platform permissions), never request-time email comparison.
- The owner-approved email `thesigntistslab@gmail.com` may be used only during controlled assignment/bootstrap to locate the existing account by normalized email.
- `PLATFORM_CREATOR` has legitimate Platform Administration authority through the shared backend platform-admin helper.
- Tenant `owner`/`admin` roles remain tenant-scoped and cannot assign platform roles.
- Portal and public users never satisfy staff or platform permission checks.
- Platform role assignment must create an audit event.

## Deprecated

- `dashboard:read` retained for MVP compat. New dashboards inherit read from underlying modules.

## Testing

- `backend/tests/test_permissions_scope.py` verifies:
  - Staff / platform / portal scopes are disjoint.
  - Staff role maps preserve the working MVP shape.
  - Platform and portal permissions cannot satisfy staff permission checks.

## EC16 AI Gateway Addendum

- Tenant AI credit reads use `ai_credit:read`.
- Tenant AI alert administration uses `ai_credit:admin`.
- Tenant AI history reads use `ai_history:read`.
- Gateway request creation requires `ai_tool:use` or `ai_assistant:use`.
- Platform AI provider, model, capability, prompt, governance, credit grant/adjustment, provider-health, and cost dashboard routes require platform AI admin authority (`platform:creator`, `platform:admin`, `platform:ai_credit_admin`, `platform_admin`, or stored platform role `admin`/`owner`/`PLATFORM_ADMIN`/`PLATFORM_CREATOR`).
- Portal tokens remain invalid for all EC16 staff/platform routes.
