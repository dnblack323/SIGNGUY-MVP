# Navigation Contract (LOCKED — EC1)

## Structure

Collapsible left sidebar with **side flyouts**. Home + six areas + divider between Creative Studio and Control Center.

```
[HOME]
Shop Operations
Business & Finance
Team & Workflow
Creative Studio
─── (divider) ───
Control Center
Help & Community
```

Portals + public systems are separately routed and do not appear in the internal sidebar.

## Rules

- **No permanent second-level top navigation.**
- **Page-specific ribbons / tabs / filters / view selectors / actions / breadcrumbs** are permitted and must not duplicate sidebar or flyout entries.
- **No permanent "More" overflow menu** as a substitute for proper flyout organization.
- **Permission and entitlement aware** — flyout entries hide when the user lacks the required permission.
- **Placeholder entries** display a "soon" marker with `data-disabled="true"` — no route target.

## Source of truth

`frontend/src/lib/navigation.js` — `NAV_AREAS` array. Every area entry has `key`, `label`, `icon`, `testId`. Flyout entries have `key`, `label`, `to`, `perm`, `testId`, optional `disabled`, optional `platformOnly`.

## Permanent placement (LOCKED)

- Payroll / Time Clock / Timesheets / Employee Scheduling → **Team & Workflow**.
- Inventory / Vendors / Purchasing → **Shop Operations → Inventory & Purchasing**.
- Customer invoice + payment operations → **Shop Operations → Orders** (operational). Financial analysis + reporting → **Business & Finance**.
- Pricing configuration → **Control Center → Pricing Defaults**. Pricing Calculator may appear as an operational shortcut inside Quotes/Orders.
- Tenant subscription + AI-credit purchasing → **Control Center → Subscriptions & AI Credits**.
- AI creation tools → **Creative Studio**.
- Community / bugs / feature requests / support / documentation → **Help & Community**.
- Proofs and Approvals are connected workflows accessible from Orders / Production / Customer records / Asset Library — **NOT** a permanent sidebar destination.

## Testing

Frontend smoke: `data-testid="app-shell-sidebar"` renders every area's `data-testid`. Divider present between Creative Studio and Control Center. Existing routes remain accessible.
