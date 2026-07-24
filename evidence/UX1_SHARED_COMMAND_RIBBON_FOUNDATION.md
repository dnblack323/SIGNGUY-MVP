# UX1 Shared Command/Ribbon Foundation

## UX1 Corrective Reopen - Sidebar, Category Navigation, And Compact Ribbon

This section records the reopened UX1 corrective checkpoint after owner visual review rejected the original nested sidebar and oversized ribbon presentation. It supersedes the original UX1 visual layout record below; the original checkpoint history remains in this document for audit continuity.

### Corrective Starting Repository State

- VERIFIED_REPOSITORY_FACT: Corrective checkpoint branch was `CODEX-ux1-branch`.
- VERIFIED_REPOSITORY_FACT: Corrective checkpoint started from `HEAD` `7e8df66b185bb2ebe3937205eb323b217c4f7c0b`.
- VERIFIED_REPOSITORY_FACT: `HEAD` equaled accepted UX1 commit `7e8df66b185bb2ebe3937205eb323b217c4f7c0b`.
- VERIFIED_REPOSITORY_FACT: `origin/CODEX-ux1-branch` equaled `7e8df66b185bb2ebe3937205eb323b217c4f7c0b`.
- VERIFIED_REPOSITORY_FACT: `origin/main` was `b06589e4ba71d4296a7986c7ca918af84e3607d8`.
- VERIFIED_REPOSITORY_FACT: Ahead/behind versus `origin/CODEX-ux1-branch` was `0 0` before corrective edits.
- VERIFIED_REPOSITORY_FACT: `evidence/UX1_SHARED_COMMAND_RIBBON_FOUNDATION.md` and `evidence/screenshots/ux1` existed before corrective edits.
- VERIFIED_REPOSITORY_FACT: No Quotes or Work Orders ribbon adoption was found after `7e8df66b185bb2ebe3937205eb323b217c4f7c0b`.

### Owner Rejection And Corrective Requirement

- DOCUMENTED_REQUIREMENT: The original visual layout was rejected because the sidebar exposed an excessive nested navigation list, the page lacked required category-specific navigation above the ribbon, and the ribbon was too large.
- DOCUMENTED_REQUIREMENT: Required hierarchy is global application header, collapsible primary-category sidebar, category-specific top navigation, compact contextual command ribbon, then page content.
- DOCUMENTED_REQUIREMENT: The sidebar answers which major area is active; the category top navigation answers which module is active; the contextual ribbon answers what can be done on the current page.
- DOCUMENTED_REQUIREMENT: The ribbon must never become a horizontally scrolling strip.
- DOCUMENTED_REQUIREMENT: Do not begin Quotes or Work Orders ribbon adoption, Webstores, Wrap Lab, Workspace Dock, Dashboard Customizer, EC19, Stripe, or unrelated backend work in this corrective checkpoint.

### Corrective Navigation Inventory

- VERIFIED_REPOSITORY_FACT: Active global shell is `frontend/src/components/app-shell/AppShell.jsx`.
- VERIFIED_REPOSITORY_FACT: Active navigation configuration is `frontend/src/lib/navigation.js`.
- VERIFIED_REPOSITORY_FACT: Active routes are declared in `frontend/src/App.js`.
- VERIFIED_REPOSITORY_FACT: Original shell used a left sidebar plus nested flyout panels and a mobile sheet.
- VERIFIED_REPOSITORY_FACT: Original navigation config exposed Home plus six old areas: Shop Operations, Business & Finance, Team & Workflow, Creative Studio, Control Center, and Help & Community.
- VERIFIED_REPOSITORY_FACT: Original page ribbon adoption lived on Orders and Customers only.
- VERIFIED_REPOSITORY_FACT: No separate active competing sidebar implementation was found after the corrective shell change.
- VERIFIED_REPOSITORY_FACT: Backward-compatible exports `NAV_AREAS` and `filterFlyoutByPermissions` remain in `navigation.js` to avoid breaking stale imports, but the active shell uses `PRIMARY_NAV_AREAS`, module top navigation, and permission-filter helpers.
- DOCUMENTED_REQUIREMENT: Master planning documents still described the earlier EC1 flyout-only navigation. The owner corrective prompt supersedes that visual/navigation contract for UX1.

### Final Primary Sidebar Categories

- VERIFIED_REPOSITORY_FACT: Desktop sidebar now renders only `Home`, `Shop Operations`, `Business Management`, `Team`, and `AI / Platform / Community`.
- VERIFIED_REPOSITORY_FACT: Expanded state shows category icons and labels.
- VERIFIED_REPOSITORY_FACT: Collapsed state shows icons only, with accessible labels and tooltips.
- VERIFIED_REPOSITORY_FACT: Orders, Customers, Finance, Inventory, Tasks, Messages, and similar modules are no longer nested sidebar entries.
- VERIFIED_REPOSITORY_FACT: Mobile access uses the existing sheet pattern and exposes the same primary categories.

### Final Category-Specific Top Navigation

- VERIFIED_REPOSITORY_FACT: Shop Operations top nav: Orders `/orders`, Customers `/customers`, Production `/work-orders`, Shop Schedule `/shop-schedule`, Webstores `/webstores`, Documents `/documents`.
- VERIFIED_REPOSITORY_FACT: Business Management top nav: Finance `/finance`, Sales `/finance`, Taxes `/tax`, Inventory `/inventory`, Payroll `/team/payroll`, Reports `/reports`.
- VERIFIED_REPOSITORY_FACT: Team top nav: Tasks `/team/tasks`, Team Schedule `/team/schedule`, Messages `/team/messages`, Announcements `/team/announcements`, Employees `/team/employees`, Workflows `/settings/production-workflows`.
- VERIFIED_REPOSITORY_FACT: AI / Platform / Community top nav: AI Assistant `/studio/assistant`, AI Tools `/studio`, Onboarding `/help/onboarding`, Documentation `/help/docs`, Community `/help/community`, Bug Reports `/help/bugs`, Feature Requests `/help/feature-requests`, Settings `/settings`.
- VERIFIED_REPOSITORY_FACT: All implemented top-nav destinations point to active routes in `frontend/src/App.js`.
- VERIFIED_REPOSITORY_FACT: At narrower widths, lower-priority modules move into a labeled `More` menu; the active module is kept visible when practical.
- VERIFIED_REPOSITORY_FACT: Top navigation is above the contextual ribbon and does not duplicate ribbon commands.

### Missing Or Uncertain Route Decisions

- OWNER_DECISION_REQUIRED: Quotes has an active route at `/quotes`, but the corrective prompt said not to automatically add Quotes as a permanent category-navigation choice. Recommendation: keep Quotes as an Orders-adjacent workflow until owner confirms whether it belongs as a module, an Orders tab, or a related create route.
- OWNER_DECISION_REQUIRED: Work Orders has active routes at `/work-orders`, `/work-orders/board`, and `/work-orders/:id`. Recommendation: expose Work Orders through the `Production` module label rather than adding a separate Work Orders top-nav item.
- OWNER_DECISION_REQUIRED: Kanban has no distinct canonical top-level route separate from `/team/tasks`. Recommendation: keep it as a Tasks view until a route or tab is approved.
- OWNER_DECISION_REQUIRED: Notes has no distinct route separate from `/team/messages`. Recommendation: keep Notes inside Messages until a route or tab is approved.
- OWNER_DECISION_REQUIRED: Internal Workflows maps to `/settings/production-workflows`; the implemented customer-facing label is `Workflows`. Recommendation: owner should confirm whether the final label should be `Workflows`, `Internal Workflows`, or `Production Workflows`.
- REASONABLE_INFERENCE: Business Management `Sales` currently maps to `/finance` because no distinct Sales route exists. A future route/tab decision should decide whether this remains a Finance view or becomes a standalone route.

### Corrective Shell Changes

- VERIFIED_REPOSITORY_FACT: `AppShell.jsx` now renders a collapsible primary-category sidebar, category-specific top navigation, mobile category sheet, and the existing global header.
- VERIFIED_REPOSITORY_FACT: Selecting a primary category updates the module row and navigates to the first permitted module in that category.
- VERIFIED_REPOSITORY_FACT: Top-nav entries and primary-category navigation are filtered by the existing permission set from `useAuth()`.
- VERIFIED_REPOSITORY_FACT: The shell change affects all authenticated pages structurally because `AppShell` is shared, but page-level ribbon adoption remains limited to Orders and Customers.
- VERIFIED_REPOSITORY_FACT: No placeholder pages or missing-route links were created.

### Corrective Ribbon Changes

- VERIFIED_REPOSITORY_FACT: `CommandRibbon.jsx` uses compact command buttons with `h-12`, smaller icons, tighter padding, tighter group spacing, and no horizontal scroll classes.
- VERIFIED_REPOSITORY_FACT: Real-browser measured Orders ribbon height is `77px` at `1440x900`, within the target `64-82px` range.
- VERIFIED_REPOSITORY_FACT: Previous accepted UX1 command buttons used `h-[70px]`; the corrected command buttons use `h-12` with a measured total ribbon height of `77px`.
- VERIFIED_REPOSITORY_FACT: Orders direct action: `New Order`.
- VERIFIED_REPOSITORY_FACT: Orders dropdowns: `Create` contains New Quote and New Customer; `Status` contains All, Draft, Confirmed, Production, Completed, Cancelled; `Source` contains All Orders, Manual, Quote, Webstore, Wrap Lab, Legacy / Unknown; `Workflow` contains New Task, Schedule Install, Open Calendar.
- VERIFIED_REPOSITORY_FACT: Customers direct action: `New Customer`.
- VERIFIED_REPOSITORY_FACT: Customers dropdowns: `Create` contains New Order and New Quote; `Tools` contains Pricing Calculator; `Workflow` contains New Task, Schedule Install, Open Calendar.
- VERIFIED_REPOSITORY_FACT: Customers list page does not show disabled customer record-dependent clutter.
- VERIFIED_REPOSITORY_FACT: Ribbon overflow at mobile width uses a labeled `More` command; it does not use horizontal scrolling.

### Orders Corrective Implementation

- VERIFIED_REPOSITORY_FACT: Orders page now has page-level search with `data-testid="orders-search-input"` and preserves source filters through the compact ribbon.
- VERIFIED_REPOSITORY_FACT: Orders table showed seeded Manual, Quote, Webstore, Wrap Lab, and Legacy / Unknown rows during visual QA.
- VERIFIED_REPOSITORY_FACT: Reserved `email` and `facebook` order sources remained hidden from visible source filters.
- VERIFIED_REPOSITORY_FACT: `Legacy / Unknown` displayed correctly in the Orders source dropdown and table.
- CANNOT_VERIFY: Orders pagination was requested in the corrective prompt but no existing pagination implementation was present on the active Orders page; no new pagination was invented in this checkpoint.

### Customers Corrective Implementation

- VERIFIED_REPOSITORY_FACT: Customers page preserves existing search, customer list/table, row actions, New Customer dialog, and focus return.
- VERIFIED_REPOSITORY_FACT: New Customer dialog opens from the ribbon with focus in `customer-name-input`.
- VERIFIED_REPOSITORY_FACT: Escape closes the New Customer dialog and returns focus to `ribbon-new-customer`.

### Real-Browser Corrective Visual QA

- PREVIEW_METHOD: Frontend `npm.cmd start` on `http://127.0.0.1:3000` with backend `http://127.0.0.1:8001`; backend health returned `{"status":"ok"}` and frontend returned HTTP 200.
- TESTED_WIDTHS: `1440x900`, `1200x800`, `900x800`, and `390x844`.
- TESTED_ZOOM_EQUIVALENT: `1152x720` for 125% layout pressure and `960x600` for 150% layout pressure.
- TESTED_THEME: Light theme verified. CANNOT_VERIFY: no supported user-facing dark-theme toggle was found; only CSS dark tokens and toast theme plumbing were present.
- VERIFIED_REPOSITORY_FACT: Desktop Orders expanded sidebar showed only primary categories, all six Shop Operations modules, compact ribbon, search, table, and source labels without horizontal page overflow.
- VERIFIED_REPOSITORY_FACT: Desktop Orders collapsed sidebar retained accessible primary category labels and no horizontal page overflow.
- VERIFIED_REPOSITORY_FACT: Orders `900x800` used top-nav `More` for Documents and kept Orders active.
- VERIFIED_REPOSITORY_FACT: Orders mobile used top-nav `More`, ribbon `More`, and mobile primary-category sheet without horizontal page overflow.
- VERIFIED_REPOSITORY_FACT: Customers desktop, narrow, and mobile kept search/list and New Customer action reachable without horizontal page overflow.
- VERIFIED_REPOSITORY_FACT: Category `More` menu opened, exposed overflowed modules, closed with Escape, and returned focus to `category-nav-more`.
- VERIFIED_REPOSITORY_FACT: Ribbon dropdowns opened with expected labels and entries; Escape or outside click closed them and focus returned to the trigger.
- CANNOT_VERIFY: Live browser permission-hidden state was not verified because the preview runs owner dev-bypass; permission-hidden behavior is verified by focused tests.

### Corrective Screenshots

- SCREENSHOT: `evidence/screenshots/ux1/corrective/orders-desktop-expanded-1440x900.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/orders-desktop-collapsed-1440x900.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/orders-narrow-collapsed-1200x800.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/orders-tablet-900x800.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/orders-mobile-390x844.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/orders-mobile-primary-nav-open-390x844.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/category-more-menu-900x800.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/orders-mobile-category-more-390x844.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/orders-ribbon-create-dropdown-900x800.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/orders-ribbon-status-dropdown-900x800.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/orders-ribbon-source-dropdown-900x800.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/orders-ribbon-workflow-dropdown-900x800.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/customers-desktop-expanded-1440x900.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/customers-narrow-1200x800.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/customers-mobile-390x844.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/customers-new-customer-dialog-1440x900.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/customers-ribbon-create-dropdown-1440x900.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/customers-ribbon-tools-dropdown-1440x900.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/customers-ribbon-workflow-dropdown-1440x900.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/customers-mobile-ribbon-overflow-390x844.png`.

### Corrective Defects Found And Fixed

- FIXED: Mobile sheet initially showed a desktop sidebar collapse control. It was removed from the mobile sheet.
- FIXED: Category top nav originally used an overly conservative desktop overflow threshold that moved Documents into `More` at `1440x900`; thresholds now show all six Shop Operations modules when the row has room.
- FIXED: Category top nav used `NavLink`, which could mark duplicate route aliases as active; it now uses explicit active-state logic with `Link`.
- FIXED: Schedule separation defect. Shop Operations `Shop Schedule` now points to the operational `/shop-schedule` calendar surface, Team `Team Schedule` now points to `/team/schedule`, and the `/api/calendar/feed?surface=shop` feed omits employee shift and time-off overlays while preserving Team Schedule records and permissions.
- FIXED: Static guard test no longer includes a literal `overflow-x-auto` token that could confuse source scans.

### Corrective Verification Results

- PASS: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ec12_phase12d_calendar_appointments.py -q` -> 1 passed, 6 warnings; verified `surface=shop` omits `shift` and `time_off_request` overlays while retaining task, production-stage, and calendar-event items.
- PASS: `CI=true yarn.cmd test --runInBand --watchAll=false src/__tests__/AppShellNavigation.test.jsx src/__tests__/ShopSchedulePage.test.jsx` from `frontend/` -> 2 suites passed, 7 tests passed; verified Shop Schedule and Team Schedule navigate to distinct routes and Shop Schedule requests the operational feed surface.
- PASS: `CI=true yarn.cmd test --runInBand --watchAll=false src/__tests__/CommandRibbon.test.jsx src/__tests__/OrdersCustomersRibbon.test.jsx` from `frontend/` -> 2 suites passed, 10 tests passed.
- PASS: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_canonical_order_source.py -q` -> 5 passed, 6 warnings.
- PASS: `CI=true npm.cmd test -- --runInBand --watchAll=false` from `frontend/` -> 14 suites passed, 50 tests passed.
- PASS: `npm.cmd run build` from `frontend/` -> production build compiled successfully.
- PASS: Route scan confirmed implemented top-nav destinations exist in `frontend/src/App.js`.
- PASS: Static ribbon scroll scan found no `overflow-x-auto` or `overflow-x-scroll` in `CommandRibbon.jsx`; existing hits are pre-existing page/table overflow containers.
- PASS: New `Job Ticket` terminology was not introduced by this corrective diff.

### Corrective Files Modified Or Added

- `frontend/src/components/app-shell/AppShell.jsx`
- `frontend/src/lib/navigation.js`
- `frontend/src/components/command-ribbon/CommandRibbon.jsx`
- `frontend/src/lib/shopOperationRibbon.js`
- `frontend/src/pages/OrdersPage.jsx`
- `frontend/src/pages/ShopSchedulePage.jsx`
- `frontend/src/__tests__/AppShellNavigation.test.jsx`
- `frontend/src/__tests__/ShopSchedulePage.test.jsx`
- `frontend/src/__tests__/CommandRibbon.test.jsx`
- `frontend/src/__tests__/OrdersCustomersRibbon.test.jsx`
- `backend/app/routers/calendar.py`
- `backend/app/services/calendar_service.py`
- `backend/app/services/business_assistant.py`
- `backend/tests/test_ec12_phase12d_calendar_appointments.py`
- `evidence/UX1_SHARED_COMMAND_RIBBON_FOUNDATION.md`
- `evidence/screenshots/ux1/corrective/*.png`

### Corrective Remaining Risks

- MEDIUM: Quotes route exists but category-level placement remains owner decision required.
- MEDIUM: Work Orders route exists but is intentionally represented as Production until owner confirms placement.
- MEDIUM: Kanban and Notes are documented as missing distinct routes; no placeholders were created.
- LOW: Business Management Sales currently maps to `/finance`; owner should confirm whether this is a Finance view or future standalone route.
- LOW: Permission-hidden behavior was verified in tests, not live browser, because the preview runs owner dev-bypass.
- INFORMATIONAL: The shared shell structure affects all authenticated pages, but ribbon adoption remains limited to Orders and Customers.
- INFORMATIONAL: Dark theme could not be visually verified because no supported user-facing toggle exists.

### Corrective No-Unrelated-Work Confirmation

- VERIFIED_REPOSITORY_FACT: Quotes ribbon adoption was not started.
- VERIFIED_REPOSITORY_FACT: Work Orders ribbon adoption was not started.
- VERIFIED_REPOSITORY_FACT: Webstores and Wrap Lab functionality were not started.
- VERIFIED_REPOSITORY_FACT: Workspace Dock and Dashboard Customizer were not started.
- VERIFIED_REPOSITORY_FACT: EC19 was not started.
- VERIFIED_REPOSITORY_FACT: No Stripe, backend security, portal, canonical source, or unrelated backend behavior was changed.
- VERIFIED_REPOSITORY_FACT: Corrective changes remain uncommitted and unpushed for owner visual review.

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

## Corrective Application Shell and Sales Layout QA - 2026-07-24

### Scope

- VERIFIED_REPOSITORY_FACT: Corrected the application shell structure for the Sales/Shop Operations surfaces without changing backend behavior, API contracts, database models, authentication, permissions, tenant behavior, pricing, or Order business logic.
- VERIFIED_REPOSITORY_FACT: Corrected Orders and Customers layout order to: Quick Access Toolbar, workspace navigation, contextual ribbon, page header, page tabs, search/views/filters, page content.
- VERIFIED_REPOSITORY_FACT: Did not begin Quotes, Work Orders, Webstores, Wrap Lab, EC19, or any unrelated module adoption.

### Preview Method

- VERIFIED_REPOSITORY_FACT: Backend preview used `backend/.venv/Scripts/python.exe -m uvicorn server:app --host 127.0.0.1 --port 8001`.
- VERIFIED_REPOSITORY_FACT: Frontend preview used `yarn start` from `frontend/` with `BROWSER=none` and `PORT=3000`.
- VERIFIED_REPOSITORY_FACT: Frontend compiled successfully and served at `http://localhost:3000`.
- VERIFIED_REPOSITORY_FACT: Development bypass banner remained visible above the application shell.

### Widths, Zoom, and Themes

- TESTED_WIDTHS: `1440x900` desktop expanded sidebar, `1024x800` narrow/collapsed sidebar, `390x844` mobile.
- TESTED_THEME: Current light working surface with dark navy sidebar was visually verified. No supported user-facing dark-theme switch was found in this preview pass.
- ZOOM_LIMITATION: Browser zoom shortcuts `Ctrl+Plus`, `ControlOrMeta+Plus`, and reset were attempted in the in-app browser, but `window.devicePixelRatio` and viewport dimensions did not change. Native browser zoom at 125% and 150% could not be verified through this browser-control surface.
- ZOOM_FALLBACK_RESULT: The attempted browser-zoom states still reported no page-level horizontal overflow and retained a 64px contextual ribbon height.

### Screenshots Produced

- SCREENSHOT: `evidence/screenshots/ux1/corrective/orders-desktop-expanded-1440x900.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/orders-narrow-collapsed-1024x800.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/orders-mobile-390x844.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/orders-category-overflow-mobile-390x844.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/orders-ribbon-create-dropdown-1440x900.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/orders-source-filter-dropdown-1440x900.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/orders-mobile-sidebar-open-390x844.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/customers-desktop-expanded-1440x900.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/customers-narrow-collapsed-1024x800.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/customers-mobile-390x844.png`.
- SCREENSHOT: `evidence/screenshots/ux1/corrective/customers-new-customer-dialog-1440x900.png`.

### Visual Findings

- PASS: The large main-content `SignGuy AI` product header was removed. Product identity appears compactly in the sidebar shop identity area.
- PASS: Expanded sidebar uses a dark navy application rail, compact shop identity, main areas only, icons and labels, active-area styling, bottom Help/notification/user controls, and a clear collapse control.
- PASS: Collapsed sidebar stays dark, icon-only, accessible by labels/tooltips, and preserves Help/notification/user access.
- PASS: Quick Access Toolbar is a compact row above workspace navigation and includes global search plus New Customer, New Quote, New Order, Pricing, New Task, Calendar, and Assistant actions.
- PASS: At 1024px, Quick Access actions collapse to icons to avoid permanent cropping. At 390px, the action strip uses internal horizontal scrolling while the page itself has no horizontal overflow.
- PASS: Shop Operations workspace navigation appears below Quick Access and contains Orders, Customers, Production, Scheduling, Webstores, Documents, and a More overflow when space is constrained.
- PASS: Contextual ribbon is compact, appears below workspace navigation and above the page header, and keeps icons above labels with readable group captions.
- PASS: Orders tabs are page tabs, not ribbon commands. Source filtering moved into the search/views/filter row.
- PASS: Customers has a page-tab row and search/views row outside the ribbon.
- PASS: Orders source dropdown shows `Legacy / Unknown` and does not show reserved `email` or `facebook` sources.
- PASS: No page-level horizontal scrolling was introduced at tested desktop, narrow, or mobile widths.

### Interaction Findings

- PASS: Orders source filter dropdown opened in the real browser, showed approved visible sources, and selected `Legacy / Unknown`.
- PASS: Orders ribbon Create dropdown opened in the real browser.
- PASS: Customers New Customer dialog opened from the ribbon and remained usable.
- PASS: Mobile sidebar opened from the Quick Access hamburger button and displayed the same dark application rail.
- PASS: Mobile sidebar closed with Escape.
- PASS: Focus-return behavior remains covered by targeted Jest tests for New Customer Escape close and return to the ribbon trigger.

### Measurements

- ORDERS_DESKTOP_1440: quick access 49px high; workspace navigation 49px high; contextual ribbon 64px high; page header 80px high; no horizontal page overflow.
- ORDERS_NARROW_1024_COLLAPSED: sidebar collapsed; contextual ribbon 64px high; no horizontal page overflow; Quick Access actions `scrollWidth=248`, `clientWidth=248`.
- ORDERS_MOBILE_390: contextual ribbon 64px high; no horizontal page overflow; Quick Access actions use internal overflow only with `scrollWidth=248`, `clientWidth=130`.
- CUSTOMERS_DESKTOP_1440: quick access 49px high; workspace navigation 49px high; contextual ribbon 64px high; page header 80px high; no horizontal page overflow.
- CUSTOMERS_MOBILE_390: contextual ribbon 64px high; no horizontal page overflow; Quick Access actions use internal overflow only with `scrollWidth=248`, `clientWidth=130`.

### Defects Found and Corrected

- FIXED: The prior shell used a light/sidebar-heavy structure and retained a large main-content product header. Reworked the shell into a dark left application rail plus compact working-area hierarchy.
- FIXED: Quick Access actions were permanently cropped at `1024x800`. Action labels now appear only on wide desktop and icon-only accessible actions remain at narrower widths.
- FIXED: Quick Access actions were permanently clipped on mobile. The action group now scrolls internally without introducing page-level horizontal scrolling.
- FIXED: Orders list status/source controls were still ribbon-like command groups. They now live in page tabs and the search/views/filter row.
- FIXED: Page header lacked a stable default QA hook. `PageHeader` now defaults to `data-testid="page-header"`.

### Verification Commands

- PASS: `cmd /c yarn test --watchAll=false --runInBand src/__tests__/AppShellNavigation.test.jsx src/__tests__/OrdersCustomersRibbon.test.jsx src/__tests__/CommandRibbon.test.jsx` from `frontend/` -> 3 suites passed, 17 tests passed.

### Remaining Risks

- REMAINING_RISK: Native browser zoom at 125% and 150% could not be changed through the in-app browser automation surface; it should be manually spot-checked before final merge approval if native zoom coverage is required.
- REMAINING_RISK: The Quick Access action strip intentionally scrolls internally on mobile because all requested global actions cannot fit beside the global search in a single 390px row.
- REMAINING_RISK: The screenshot folder contains earlier untracked UX1 corrective images from previous QA passes; this section lists only the screenshots produced for the corrected 2026-07-24 shell pass.
