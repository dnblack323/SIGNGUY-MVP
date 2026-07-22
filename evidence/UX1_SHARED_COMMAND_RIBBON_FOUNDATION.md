# UX1 Shared Command/Ribbon Foundation

## Starting-Point Verification

- VERIFIED_REPOSITORY_FACT: Branch at UX1 start was `CODEX-ux1-branch`.
- VERIFIED_REPOSITORY_FACT: UX1 starting `HEAD` was `11d9bc891755249ac6fdd4183e7027dcbd3a7d3e`.
- VERIFIED_REPOSITORY_FACT: `origin/CODEX-ux1-branch` was `11d9bc891755249ac6fdd4183e7027dcbd3a7d3e`.
- VERIFIED_REPOSITORY_FACT: `origin/main` was `b06589e4ba71d4296a7986c7ca918af84e3607d8`.
- VERIFIED_REPOSITORY_FACT: Ahead/behind versus `origin/CODEX-ux1-branch` was `0 0`.
- VERIFIED_REPOSITORY_FACT: Working tree was clean before UX1 changes began.
- VERIFIED_REPOSITORY_FACT: Canonical Order Source checkpoint commit was `11d9bc891755249ac6fdd4183e7027dcbd3a7d3e`.
- VERIFIED_REPOSITORY_FACT: Most recently completed checkpoint before UX1 was Canonical Order Source Foundation.

## Canonical Order Source Commit and Push Result

- VERIFIED_REPOSITORY_FACT: Commit message: `Orders: establish canonical source tracking and filtering`.
- VERIFIED_REPOSITORY_FACT: Commit hash: `11d9bc891755249ac6fdd4183e7027dcbd3a7d3e`.
- VERIFIED_REPOSITORY_FACT: Push target: `origin/CODEX-ux1-branch`.
- VERIFIED_REPOSITORY_FACT: Post-push ahead/behind state: `0 0`.

## Authoritative Requirements Used

- DOCUMENTED_REQUIREMENT: User attachment `SIGNGUY AI - CLOSE CANONICAL ORDER SOURCE CHECKPOINT AND BEGIN UX1 SHARED COMMAND/RIBBON FOUNDATION`.
- DOCUMENTED_REQUIREMENT: `frontend/src/lib/navigation.js` locked navigation contract says permanent second-level top navigation is not used, and page-specific ribbons/tabs/filters/actions are allowed when they do not duplicate sidebar or flyout entries.
- DOCUMENTED_REQUIREMENT: `evidence/CANONICAL_ORDER_SOURCE_CHECKPOINT.md` documents canonical Order source values and hidden future `email`/`facebook` sources.
- DOCUMENTED_REQUIREMENT: `SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md`, `memory/MASTER_CHECKPOINT_CHECKLIST.md`, EC3/EC14/EC15/EC16/EC18 preflight and evidence records were used for scope boundaries.
- VERIFIED_REPOSITORY_FACT: Active route definitions live in `frontend/src/App.js`.
- VERIFIED_REPOSITORY_FACT: Active global shell and flyout behavior live in `frontend/src/components/app-shell/AppShell.jsx` and `frontend/src/lib/navigation.js`.
- VERIFIED_REPOSITORY_FACT: Active Orders and Customers pages were `frontend/src/pages/OrdersPage.jsx` and `frontend/src/pages/CustomersPage.jsx`.

## Existing Navigation and Command Inventory

| Area | File/component | Current behavior | Permission behavior | Responsive/accessibility behavior | UX1 decision |
| --- | --- | --- | --- | --- | --- |
| Global shell | `AppShell.jsx` | Sidebar with flyout panels plus mobile sheet. | Uses `filterFlyoutByPermissions`. | Mobile sheet, sidebar hover/click flyouts, user dropdown. | Retain. Ribbon must not duplicate global navigation. |
| Navigation config | `lib/navigation.js` | Locked Home plus six area contract. | Entry `perm` and `platformOnly` filtering. | Flyouts and disabled future entries. | Retain as authoritative top-level navigation. |
| Page header | `PageHeader.jsx` | Per-page title/subtitle/actions. | Caller-controlled. | Flex layout. | Retain. Orders/Customers stop using header actions for adopted ribbon actions. |
| Orders commands | `OrdersPage.jsx` | Local New Order dialog and local status filter buttons. | `order:write` controls create. | Basic button strip. | Adapt to shared ribbon. |
| Customers commands | `CustomersPage.jsx` | Local New Customer dialog and search input. | `customer:write` controls create. | Search remains page content. | Adapt create/actions to shared ribbon; preserve search. |
| Webstore actions | `WebstoresPage.jsx`, `WebstoreDetailPage.jsx` | Page-level refresh/create and detail actions. | Existing Webstore permissions/service access. | Page-local forms/actions. | Defer. No Webstore redesign in this checkpoint. |
| Wrap Lab actions | `WrapLabPage.jsx`, `WrapLabDetailPage.jsx` | Page-level refresh/create and detail AI actions. | Existing Wrap Lab permissions/service access. | Page-local forms/actions. | Defer. No Wrap Lab redesign in this checkpoint. |
| Detail tabs | Customer, Work Order, Reports, Finance, etc. | Tabs organize record/page subviews. | Caller/page controlled. | Radix tabs. | Retain; not a ribbon replacement target here. |
| Markup toolbar | `MarkupToolbar.jsx` | Tool-specific drawing controls. | Context/page controlled. | Compact icon tool controls. | Retain as domain tool toolbar, not module ribbon. |
| Production Board row menu | `ProductionBoardPage.jsx` | Row-specific action dropdown. | Stage/action rules. | Dropdown with icon trigger and labels. | Retain as row command menu. |

## Competing Ribbon Findings

- VERIFIED_REPOSITORY_FACT: No active shared `CommandRibbon` existed before this checkpoint.
- VERIFIED_REPOSITORY_FACT: Existing page actions are mostly `PageHeader.actions`, local button strips, tabs, and row dropdowns.
- REASONABLE_INFERENCE: Webstores and Wrap Lab have page-local controls but are not competing shared module ribbons; they are deferred because this checkpoint is limited to Orders and Customers adoption.
- CANNOT_VERIFY: Full application-wide ribbon replacement was not attempted by scope.

## Shared Command Contract

- VERIFIED_REPOSITORY_FACT: `frontend/src/lib/commandRibbon.js` defines the shared command model and helpers.
- DOCUMENTED_REQUIREMENT: Commands support stable id, label, icon, action or destination, group, tooltip, permission, entitlement metadata, visibility, disabled/loading/active state, badge, dropdown children, responsive priority, keyboard shortcut metadata, analytics id, and test id.
- VERIFIED_REPOSITORY_FACT: Permission filtering uses trusted `useAuth().hasPerm`.
- VERIFIED_REPOSITORY_FACT: Entitlement metadata is supported through the `entitlements` prop without pretending frontend checks replace backend authorization.
- REASONABLE_INFERENCE: JSDoc is used for typed contract documentation because this frontend is JavaScript, not TypeScript.

## Shared Ribbon Architecture

- VERIFIED_REPOSITORY_FACT: `frontend/src/components/command-ribbon/CommandRibbon.jsx` renders grouped Microsoft Office-style compact commands.
- VERIFIED_REPOSITORY_FACT: Commands render icon above label, group captions, visible focus styles, `aria-label`, active state, disabled state, tooltips, dropdown children, and deterministic overflow.
- VERIFIED_REPOSITORY_FACT: Primary command capacity is capped responsively from the measured ribbon width; overflow commands are available under More.
- VERIFIED_REPOSITORY_FACT: Dropdown children remain actionable when their parent command moves into the overflow menu.
- VERIFIED_REPOSITORY_FACT: The component uses existing shadcn/Radix `Button`, `DropdownMenu`, `Tooltip`, `Badge`, Tailwind classes, and lucide icons.
- VERIFIED_REPOSITORY_FACT: No second design system was introduced.

## Command Execution and Routing

- VERIFIED_REPOSITORY_FACT: Navigation commands call `useNavigate()` with existing internal route paths.
- VERIFIED_REPOSITORY_FACT: Page actions call page-provided handlers, such as opening existing New Order/New Customer dialogs.
- VERIFIED_REPOSITORY_FACT: Dropdown child commands use the same execution model.
- VERIFIED_REPOSITORY_FACT: Disabled commands guard execution and expose disabled reasons.
- REASONABLE_INFERENCE: Domain business logic remains in existing pages/services; ribbon commands only invoke routes or handlers.

## Orders Adoption

- VERIFIED_REPOSITORY_FACT: `OrdersPage.jsx` now uses `CommandRibbon`.
- VERIFIED_REPOSITORY_FACT: New Order is opened through the shared ribbon and still uses the existing Order dialog and `/orders` POST behavior.
- VERIFIED_REPOSITORY_FACT: Status filters are rendered as shared commands.
- VERIFIED_REPOSITORY_FACT: Canonical Order source filtering uses `GET /orders/source-filters` and `GET /orders?order_source=...`.
- VERIFIED_REPOSITORY_FACT: Visible source filters are All Orders, Manual, Quote, Webstore, Wrap Lab, and Legacy / Unknown.
- VERIFIED_REPOSITORY_FACT: Reserved `email` and `facebook` are not exposed in the normal Orders ribbon source dropdown.
- VERIFIED_REPOSITORY_FACT: Order sources remain filters inside Orders, not separate tabs or separate Order systems.

## Customers Adoption

- VERIFIED_REPOSITORY_FACT: `CustomersPage.jsx` now uses `CommandRibbon`.
- VERIFIED_REPOSITORY_FACT: New Customer is opened through the shared ribbon and still uses the existing Customer dialog and `/customers` POST behavior.
- VERIFIED_REPOSITORY_FACT: Existing customer search remains page content and continues to call `/customers?search=...`.
- VERIFIED_REPOSITORY_FACT: Customer record-dependent commands are not advertised on the Customers list page.

## Owner Review Decisions Recorded

- OWNER_DECISION_RECORDED: Record-dependent actions normally appear only on the applicable record-detail page or in a contextual row menu when a specific record is known.
- OWNER_DECISION_RECORDED: Disabled record-dependent commands must not appear on Orders or Customers list pages merely to advertise future availability.
- OWNER_DECISION_RECORDED: A disabled command may remain on a list page only when it becomes available through an obvious list-page selection workflow, explains the required selection, and does not add unnecessary ribbon clutter.
- OWNER_DECISION_RECORDED: Next controlled adoption surfaces are Quotes and Work Orders.
- OWNER_DECISION_RECORDED: Webstores and Wrap Lab remain deferred until Quotes and Work Orders verify that the shared architecture works across ordinary operational modules.
- OWNER_DECISION_RECORDED: Quotes and Work Orders adoption was not started in this checkpoint.

## Responsive and Accessibility Findings

- VERIFIED_REPOSITORY_FACT: Ribbon groups use compact fixed command dimensions and responsive primary-command caps so right-side commands move into More instead of creating a ribbon scrollbar.
- VERIFIED_REPOSITORY_FACT: Deterministic overflow is available via the More command when primary command count exceeds the measured responsive cap.
- VERIFIED_REPOSITORY_FACT: Buttons have accessible names, visible focus ring classes, native Enter/Space activation, and Radix-managed Escape behavior for menus.
- VERIFIED_REPOSITORY_FACT: Disabled commands expose `aria-disabled` and a tooltip/title reason while preventing execution.
- VERIFIED_REPOSITORY_FACT: `rg --pcre2` search found icon-only buttons with accessible labels, including the new ribbon buttons.
- VERIFIED_REPOSITORY_FACT: Real-browser visual QA was performed against the active Orders and Customers pages.
- VERIFIED_REPOSITORY_FACT: Programmatically opened New Order/New Customer dialogs return focus to their ribbon trigger after Escape close.
- VERIFIED_REPOSITORY_FACT: Browser DOM-level keyboard activation opened the New Customer dialog from the focused ribbon button.
- VERIFIED_REPOSITORY_FACT: The in-app browser did not expose a user-facing dark-theme toggle; Tailwind remains configured for class-based dark mode, but no supported app switch was found.

## Real-Browser Visual QA

- PREVIEW_METHOD: Backend `uvicorn server:app --host 127.0.0.1 --port 8001` using `backend/.venv`, development env vars, `AUTH_DEV_BYPASS=true`, and MongoDB database `signguy_ux1_visual_qa`; frontend `npm.cmd start` with `REACT_APP_BACKEND_URL=http://127.0.0.1:8001` on `http://127.0.0.1:3000`.
- PREVIEW_NOTE: `backend/.venv` was missing dependencies; installed pinned backend requirements except the unreachable optional `litellm` wheel. MongoDB service was already running locally.
- TESTED_WIDTHS: `1440x900` desktop, `900x800` narrow/collapsed global sidebar, `390x844` mobile.
- TESTED_ZOOM: Chrome/CDP layout-equivalent zoom captures for 125% and 150% using reduced CSS viewport widths with matching device scale factors.
- TESTED_THEME: Current light theme verified. No user-facing dark theme toggle was found; forced/app dark theme was not claimed as supported.
- SCREENSHOT: `evidence/screenshots/ux1/orders-desktop-1440.png`.
- SCREENSHOT: `evidence/screenshots/ux1/orders-narrow-collapsed-900.png`.
- SCREENSHOT: `evidence/screenshots/ux1/orders-mobile-390.png`.
- SCREENSHOT: `evidence/screenshots/ux1/customers-desktop-1440.png`.
- SCREENSHOT: `evidence/screenshots/ux1/customers-narrow-collapsed-900.png`.
- SCREENSHOT: `evidence/screenshots/ux1/customers-mobile-390.png`.
- SCREENSHOT: `evidence/screenshots/ux1/orders-overflow-menu-900.png`.
- SCREENSHOT: `evidence/screenshots/ux1/orders-source-dropdown-1440.png`.
- SCREENSHOT: `evidence/screenshots/ux1/orders-desktop-chrome-layout-zoom-125.png`.
- SCREENSHOT: `evidence/screenshots/ux1/orders-desktop-chrome-layout-zoom-150.png`.
- SCREENSHOT: `evidence/screenshots/ux1/customers-staff-permission-hidden-1440.png`.

## Visual QA Findings

- PASS: Orders desktop shows icons above labels, readable labels, understandable group captions, visible Source dropdown, visible More overflow, and no ribbon scrollbar.
- PASS: Orders narrow/collapsed-sidebar view moves lower-priority commands into More and keeps primary commands reachable without ribbon horizontal scrolling.
- PASS: Orders mobile keeps New Order, New Quote, New Customer, and More reachable; the existing Orders table retains its own horizontal overflow for tabular data.
- PASS: Orders source filters rendered and worked for Manual, Quote, Webstore, Wrap Lab, and Legacy / Unknown.
- PASS: Reserved `email` and `facebook` sources remained hidden in Orders source-filter UI.
- PASS: `Legacy / Unknown` displayed correctly in the Orders table and source filter.
- PASS: Customers desktop/narrow/mobile kept search usable and did not show customer record-dependent disabled commands.
- PASS: Customers search for `long.label` filtered to the expected seeded customer.
- PASS: New Customer dialog opened from the ribbon, closed with Escape, and returned focus to the New Customer ribbon button.
- PASS: Overflow menu opened, grouped commands clearly, exposed overflowed Source child filters, and closed with Escape.
- PASS: Staff-role permission render hid Schedule Install and Open Calendar while retaining staff-allowed customer rows and commands.
- PASS: Browser zoom-equivalent 125% and 150% layout captures kept the ribbon readable and reachable through More.

## Defects Found and Corrected

- FIXED: Orders list ribbon still exposed `Send Email`, which conflicted with the owner decision against record-dependent list-page commands. Removed the list-page Send Email command.
- FIXED: Customers list ribbon previously retained disabled customer record-dependent commands. Removed those list-page disabled commands.
- FIXED: Ribbon used horizontal scrolling at desktop/narrow/mobile widths instead of moving commands into More. Added measured responsive primary-command caps and removed ribbon horizontal scrolling.
- FIXED: Overflowed dropdown parent commands appeared as dead menu items. Overflow now flattens dropdown children so Source filters remain actionable inside More.
- FIXED: Programmatically opened New Order/New Customer dialogs returned focus to `body` after Escape. Pages now restore focus to the matching ribbon trigger.

## Permission and Entitlement Findings

- VERIFIED_REPOSITORY_FACT: Permission-required commands are hidden unless `useAuth().hasPerm(permission)` returns true.
- VERIFIED_REPOSITORY_FACT: Frontend hiding does not replace backend authorization; existing backend route/service enforcement remains unchanged.
- VERIFIED_REPOSITORY_FACT: The ribbon does not manufacture tenant IDs, trusted source metadata, Stripe data, portal data, or canonical Order source values.
- VERIFIED_REPOSITORY_FACT: No permission, role, tenant, entitlement, or backend security behavior was changed.
- REASONABLE_INFERENCE: Entitlement support is metadata-driven and ready for pages that already fetch entitlement state.

## Tests Added

- VERIFIED_REPOSITORY_FACT: `frontend/src/__tests__/CommandRibbon.test.jsx`
  - grouped rendering;
  - icon and accessible label rendering;
  - keyboard command execution;
  - route navigation execution;
  - active state;
  - permission-hidden command behavior;
  - entitlement-disabled behavior;
  - dropdown behavior;
  - deterministic overflow behavior.
- VERIFIED_REPOSITORY_FACT: `frontend/src/__tests__/OrdersCustomersRibbon.test.jsx`
  - Orders shared ribbon rendering;
  - canonical source filter integration;
  - hidden reserved Order sources;
  - Legacy / Unknown source presentation;
  - New Order dialog execution;
  - Customers shared ribbon rendering;
  - Customer search preservation;
  - New Customer dialog execution;
  - New Customer Escape close and focus return.

## Verification Commands and Results

- PASS: `CI=true npm.cmd test -- --runInBand --watchAll=false src/__tests__/CommandRibbon.test.jsx src/__tests__/OrdersCustomersRibbon.test.jsx` -> 2 suites passed, 8 tests passed.
- PASS: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_canonical_order_source.py -q` -> 5 passed, 6 warnings.
- PASS: `CI=true npm.cmd test -- --runInBand --watchAll=false` from `frontend/` -> 13 suites passed, 43 tests passed.
- PASS: `npm.cmd run build` from `frontend/` -> production build compiled successfully.
- PASS: `rg -n 'Ribbon|ribbon|CommandRibbon|command-ribbon|toolbar|Toolbar|PageHeader|actions=|DropdownMenu' frontend/src/pages frontend/src/components frontend/src/lib`.
- PASS: `rg --pcre2 -n 'aria-label=""|<Button[^>]*size="icon"(?![^>]*aria-label)' frontend/src`.
- PASS: route-target search for ribbon command destinations; configured routes exist in `App.js`.
- PASS: `git diff --check` -> exit 0; reported CRLF normalization warnings for touched JSX files only.

## Remaining Risks

- LOW: The controlled adoption proves Orders and Customers only; many pages still use local `PageHeader.actions`, tabs, and row menus by design.
- INFORMATIONAL: Quotes and Work Orders are the next controlled adoption surfaces but were not started in this checkpoint.
- INFORMATIONAL: Webstores and Wrap Lab are explicitly deferred until after Quotes and Work Orders adoption verification.
- INFORMATIONAL: Workspace Dock and Dashboard Customizer remain deferred.
- INFORMATIONAL: No supported user-facing dark-theme switch was found during visual QA; only the current light theme was verified.

## Files Modified

- `frontend/src/components/command-ribbon/CommandRibbon.jsx`
- `frontend/src/lib/commandRibbon.js`
- `frontend/src/lib/shopOperationRibbon.js`
- `frontend/src/pages/OrdersPage.jsx`
- `frontend/src/pages/CustomersPage.jsx`
- `frontend/src/__tests__/CommandRibbon.test.jsx`
- `frontend/src/__tests__/OrdersCustomersRibbon.test.jsx`
- `evidence/UX1_SHARED_COMMAND_RIBBON_FOUNDATION.md`

## Documentation Updated

- VERIFIED_REPOSITORY_FACT: Created `evidence/UX1_SHARED_COMMAND_RIBBON_FOUNDATION.md`.

## Recommended Next Checkpoint

- RECOMMENDATION: Continue UX1 with Quotes and Work Orders adoption only after this checkpoint is committed and reviewed.
- RECOMMENDATION: Keep Webstores and Wrap Lab deferred until Quotes and Work Orders verify the shared architecture across ordinary operational modules.

## No-Unrelated-Work Confirmation

- VERIFIED_REPOSITORY_FACT: Workspace Dock was not started.
- VERIFIED_REPOSITORY_FACT: Dashboard Customizer was not started.
- VERIFIED_REPOSITORY_FACT: No complete application-wide ribbon rollout was attempted.
- VERIFIED_REPOSITORY_FACT: Global navigation was not replaced.
- VERIFIED_REPOSITORY_FACT: No separate Order tabs by source were added.
- VERIFIED_REPOSITORY_FACT: No email/Facebook Order-creation, duplicate, reorder, Admin Communication Center, Stripe, bootstrap, EC19, or unrelated backend work was started.
- VERIFIED_REPOSITORY_FACT: UX1 shared command/ribbon checkpoint remains uncommitted and unpushed for owner review.
