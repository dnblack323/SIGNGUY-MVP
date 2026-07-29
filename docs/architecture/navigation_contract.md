# Navigation Contract

## Structure

The authenticated desktop shell uses the owner-approved UX1 hierarchy:

1. Compact collapsible main-area sidebar.
2. Persistent second-level module tabs across the top of the content area.
3. Compact contextual ribbon.
4. Quick Access Toolbar.
5. Breadcrumb and page heading.
6. Page content.
7. Bottom Workspace Dock.

Portals, public storefronts, and kiosk routes remain separately routed and do not render the internal authenticated shell.

## Main-Area Sidebar

The sidebar contains only the six approved main application areas:

- Shop Operations
- Business & Finance
- Team & Workflow
- Design Studio
- Control Center
- Help & Community

Selecting a main area opens that area's overview/dashboard destination. Desktop must not render the obsolete long module flyout/dropdown navigation.

Global search, notifications, Help, and account controls remain at the bottom of the sidebar.

## Module Navigation And Ribbon

`frontend/src/lib/navigation.js` is the source of truth for main areas and module tabs. Module entries define `key`, `label`, `to`, `testId`, optional permission requirements, and optional match prefixes.

Rules:

- Second-level modules render as persistent horizontal tabs, not sidebar flyouts.
- The active module is styled as a selected tab.
- The contextual ribbon appears below module tabs and changes by active area/module.
- Ribbon commands must not duplicate module navigation.
- Quick Access Toolbar commands share shell command definitions with the ribbon.
- Existing route destinations remain authoritative; navigation correction must not invent replacement pages.

## Workspace Dock

The Workspace Dock is the owner-approved bottom row of open-work tabs for authenticated users.

Rules:

- Only one workspace is displayed at a time.
- Workspaces never overlap, split, drag, or resize.
- Desktop uses the bottom tab row.
- Desktop workspace tabs render as compact occupied numbered slots from 1-8, not permanent long titles.
- Mobile uses an Open Work drawer/switcher.
- Maximum open workspaces: 8.
- Recent work references retained per tenant/user: 20.
- Dock state persists to the authenticated account and is scoped by both tenant and user.
- `Dock & New` in the Quick Access Toolbar docks the current eligible work, then opens the neutral dashboard workspace. If the current route is already docked, its visible label becomes `New Workspace` and no duplicate workspace is created.
- The `+` button beside the dock opens the neutral dashboard workspace.
- Eligible record context menus may call the same workspace service through `Open in New Workspace`; they must not replace or destroy the currently active workspace first.
- Workspace metadata must not store sensitive form contents.
- Workspace persistence must not modify underlying Orders, Quotes, Customers, Work Orders, Invoices, pricing snapshots, saved calculations, artwork, or proof records.

Supported workspaces are record-detail or work-surface routes such as Orders, Quotes, Customers, Work Orders, Invoices, Pricing Calculator, saved calculations where applicable, Decision Rooms/proof/artwork surfaces, Webstores, Wrap Lab, materials, purchase orders, vendors, employees, and equipment.

Ordinary dashboards, overviews, record lists, reports landing pages, settings pages, Help pages, and general navigation destinations must not open dock tabs.

## Permanent Placement

- Payroll, Time Clock, Timesheets, and Team Schedule belong under Team & Workflow.
- Shop Schedule belongs under Shop Operations and represents production/installation/delivery workload, not employee shifts.
- Inventory, Vendors, and Purchasing belong under Shop Operations or their existing approved module placements.
- Customer invoice and payment operations remain operational record workflows; financial analysis and reporting belong under Business & Finance.
- Pricing configuration belongs under Control Center -> Pricing Defaults. The dedicated Pricing Calculator workspace belongs under Shop Operations.
- Tenant subscription and AI-credit purchasing belong under Control Center.
- AI creation tools belong under Design Studio.
- Community, bugs, feature requests, support, and documentation belong under Help & Community.
- Proofs and approvals remain connected workflows reachable from records and document/library workflows; they are not permanent main-sidebar destinations.

## Testing

Required shell/dock coverage includes:

- Six main-area sidebar items only.
- No obsolete desktop flyout.
- Persistent module tabs.
- Contextual ribbon and one Quick Access Toolbar.
- Supported record/work routes auto-open or activate a workspace.
- Lists, dashboards, settings, Help, and ordinary navigation routes do not open workspaces.
- Dock activate, close, pin, reorder, recent reopen, limit, dirty-warning, reload, and mobile Open Work behavior.
- `Dock & New`, `New Workspace`, the dock `+` button, numbered slots/tooltips, context `Open in New Workspace`, and the eight-slot replacement chooser.
- Authenticated routes continue rendering inside the corrected shell.

## Workspace Dock Visual QA

Completed on 2026-07-27 against the authenticated local preview at `http://localhost:3000/`.

Screenshots:

- `evidence/screenshots/workspace-dock/workspace-dock-desktop-shell.png`
- `evidence/screenshots/workspace-dock/workspace-dock-order-active.png`
- `evidence/screenshots/workspace-dock/workspace-dock-dirty-close-warning.png`
- `evidence/screenshots/workspace-dock/workspace-dock-eight-limit-warning.png`
- `evidence/screenshots/workspace-dock/workspace-dock-mobile-open-work-drawer.png`

Result:

- Desktop dock rendered with multiple real workspaces and no horizontal document scroll.
- Order workspace activation restored the stored route.
- Dirty-close warning displayed and could be cancelled or continued.
- Ninth workspace attempt showed the eight-workspace limit workflow without evicting existing work.
- Mobile Open Work drawer rendered after relocating the dock trigger away from the Assistant launcher.

## Workspace Dock Completion Pass

Completed on 2026-07-29 on branch `CODEX-ux1-workspace-dock-completion`.

Additional verified behavior:

- Bottom dock slots now render as compact occupied numbers and keep long titles in accessible tooltips.
- Workspace tooltips include slot number, full label, record number/ID where available, route, and dirty status.
- Route query state now contributes allowlisted tab/filter/sort/view/category metadata for restoration.
- The Quick Access Toolbar includes `Dock & New`; it changes to `New Workspace` when the current route is already docked.
- The dock includes a compact `+` action for opening a fresh neutral workspace.
- The eight-workspace chooser lists the eight occupied slots from the backend limit response, identifies dirty/pinned state, and requires the existing dirty confirmation before replacement.
- Production board row actions expose `Open in New Workspace` for eligible Work Order records through the shared workspace service.
