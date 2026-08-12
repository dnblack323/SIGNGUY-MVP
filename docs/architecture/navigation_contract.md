# Navigation Contract

## Structure

The authenticated desktop shell uses the current owner-approved shell hierarchy:

1. Global header with current workspace title/subtitle, Global Search, Create, Messages, Notifications, and Account.
2. Compact breadcrumbs.
3. Persistent secondary module navigation with Quick Access aligned to its right.
4. Internal tabs when applicable.
5. Contextual ribbon.
6. Page content.
7. Numbered Workspace Dock fixed to the bottom of the workspace.

Portals, public storefronts, and kiosk routes remain separately routed and do not render the internal authenticated shell.

## Main-Area Sidebar

The sidebar contains only these single-level application areas, in order:

- Home
- Shop Operations
- Business & Finance
- Team & Productivity
- Tools & Resources
- Control Center
- Help & Community

Selecting a main area opens that area's overview/dashboard destination. Desktop must not render nested sidebar links, flyouts, accordions, secondary modules, record links, search, messages, notifications, or account controls in the sidebar.

The sidebar bottom contains only the sidebar pin/collapse control. The official SignGuy AI logo asset appears at the top; the full logo is used when expanded and the compact mark is used when collapsed.

## Module Navigation And Ribbon

`frontend/src/lib/navigation.js` is the source of truth for main areas and module tabs. Module entries define `key`, `label`, `to`, `testId`, optional permission requirements, and optional match prefixes.

Rules:

- Second-level modules render as persistent horizontal tabs, not sidebar flyouts.
- The active module is styled as a selected tab.
- Shop Operations secondary modules are exactly: Overview, Sales, Customers, Production, Approval Center, Webstores, Wrap Lab.
- The prior direct Shop Operations secondary links for Intake, Quotes, and Orders are superseded. They now live inside Sales as internal tabs: Intake Requests, Quotes, Orders.
- Existing `/intake`, `/quotes`, and `/orders` routes remain valid and activate Shop Operations -> Sales.
- The contextual ribbon appears below module tabs and changes by active area/module.
- Ribbon commands must not duplicate module navigation.
- Quick Access Toolbar commands share shell command definitions with the ribbon.
- Quick Access pinning, reordering, and toolbar persistence are intentionally deferred from this visual correction checkpoint. The current toolbar remains a permission-aware static shortcut row.
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
- The dock `+` button opens recent/search-to-open workspace access. Creating business records belongs to the global Create menu.
- Eligible record context menus may call the same workspace service through `Open in New Workspace`; they must not replace or destroy the currently active workspace first.
- Workspace metadata must not store sensitive form contents.
- Workspace persistence must not modify underlying Orders, Quotes, Customers, Work Orders, Invoices, pricing snapshots, saved calculations, artwork, or proof records.

Supported workspaces are record-detail or work-surface routes such as Orders, Quotes, Customers, Work Orders, Invoices, Pricing Calculator, saved calculations where applicable, Decision Rooms/proof/artwork surfaces, Webstores, Wrap Lab, materials, purchase orders, vendors, employees, and equipment.

Ordinary dashboards, overviews, record lists, reports landing pages, settings pages, Help pages, and general navigation destinations must not open dock tabs.

## Permanent Placement

- Payroll, Time Clock, Timesheets, and Team Schedule remain reachable under Team & Productivity while that area's detailed secondary navigation remains deferred.
- Installation, pickup, delivery, shipping, rework, returns, corrections, reprints, warranties, and installation return visits are represented through Sales request types or Production filters/saved views, not permanent Shop Operations secondary modules.
- Materials, inventory, vendors, suppliers, and purchasing do not belong under current Shop Operations navigation.
- Customer invoice and payment operations remain operational record workflows; financial analysis and reporting belong under Business & Finance.
- Pricing configuration belongs under Control Center -> Pricing Defaults.
- Tenant subscription and AI-credit purchasing belong under Control Center.
- AI creation tools belong under Tools & Resources.
- Community, bugs, feature requests, support, and documentation belong under Help & Community.
- Approval Center is the permanent Shop Operations module for cross-order approval work. Its only internal tabs are Approval Queue and Decision Rooms; statuses are filters, not tabs.
- Proofs and approvals remain connected workflows reachable from records and Approval Center. A Decision Room is an enhanced approval experience, not a separate business module.
- Use Webstores in active navigation and implementation-facing documentation. Order Portals is superseded terminology.

## Customer And Order Records

Customer records use these internal tabs: Overview, Contacts, Communications, Requests, Quotes, Orders, Files & Forms, Portal, Activity. Communications, files, forms, completed questionnaires, and portal data are linked from their source records instead of copied.

Order records use these internal tabs: Overview, Order Items, Production, Documents & Approvals, Files & Artwork, Financial, Activity. The current production terminology is Order -> Order Items -> Work Order Summary. Job Ticket is banned as current product terminology.

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
