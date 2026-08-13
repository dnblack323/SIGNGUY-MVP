import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import AppShell from "@/components/app-shell/AppShell";
import { useAuth } from "@/auth/AuthContext";
import api from "@/lib/api";

jest.mock("@/auth/AuthContext", () => ({
  useAuth: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
  },
}));

jest.mock("@/components/notifications/NotificationBell", () => function NotificationBellMock() {
  return <button type="button" data-testid="notification-bell">Notifications</button>;
});

jest.mock("@/components/assistant/AssistantLauncher", () => function AssistantLauncherMock() {
  return <div data-testid="assistant-launcher" />;
});

const FULL_PERMISSIONS = [
  "intake:read",
  "intake:write",
  "customer:read",
  "customer:write",
  "quote:read",
  "quote:write",
  "order:read",
  "order:write",
  "pricing:read",
  "work_order:read",
  "decision_room:read",
  "schedule:read",
  "document:read",
  "webstore:read",
  "webstore:write",
  "wrap_lab:read",
  "wrap_lab:write",
  "finance:read",
  "invoice:read",
  "expense:read",
  "tax_report:read",
  "report:read",
  "employee:read",
  "employee:manage",
  "equipment:read",
  "training:manage",
  "certification:read",
  "task:read",
  "timeclock:self",
  "timesheet:self",
  "payroll:read",
  "message:read",
  "ai_tool:use",
  "ai_assistant:use",
  "ai_prompt:read",
  "ai_history:read",
  "settings:read",
  "integration:read",
  "production_workflow:read",
  "subscription:read",
  "ai_credit:read",
  "audit:read",
  "help:read",
  "onboarding:read",
  "community:read",
  "support:write",
  "platform:admin",
];

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="current-path">{location.pathname}{location.search}</div>;
}

function Page({ name }) {
  return <div data-testid={`${name}-route`}>{name} route</div>;
}

function renderShell(initialPath = "/", authOverrides = {}) {
  const permissions = authOverrides.permissions || FULL_PERMISSIONS;
  api.get.mockResolvedValue({ data: { open_workspaces: [], recent_workspaces: [], limits: { max_open: 8, max_recent: 20 } } });
  api.post.mockResolvedValue({ data: { open_workspaces: [], recent_workspaces: [], limits: { max_open: 8, max_recent: 20 } } });
  useAuth.mockReturnValue({
    devBypass: authOverrides.devBypass ?? false,
    hasPerm: (permission) => permissions.includes(permission),
    logout: jest.fn(),
    permissions,
    tenant: { id: "tenant-1", name: "Donnell Black's Shop", slug: "dev-shop" },
    user: { id: "user-1", email: "owner@example.com", full_name: "Owner User", platform_admin: true },
  });

  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<><LocationProbe /><Page name="overview" /></>} />
          <Route path="/home" element={<><LocationProbe /><Page name="home" /></>} />
          <Route path="/shop-operations" element={<><LocationProbe /><Page name="shop-operations-overview" /></>} />
          <Route path="/intake" element={<><LocationProbe /><Page name="intake" /></>} />
          <Route path="/intake/:id" element={<><LocationProbe /><Page name="intake-detail" /></>} />
          <Route path="/quotes" element={<><LocationProbe /><Page name="quotes" /></>} />
          <Route path="/quotes/:id" element={<><LocationProbe /><Page name="quote-detail" /></>} />
          <Route path="/orders" element={<><LocationProbe /><Page name="orders" /></>} />
          <Route path="/orders/:id" element={<><LocationProbe /><Page name="order-detail" /></>} />
          <Route path="/customers" element={<><LocationProbe /><Page name="customers" /></>} />
          <Route path="/customers/:id" element={<><LocationProbe /><Page name="customer-detail" /></>} />
          <Route path="/work-orders" element={<><LocationProbe /><Page name="production" /></>} />
          <Route path="/webstores" element={<><LocationProbe /><Page name="webstores" /></>} />
          <Route path="/approval-center" element={<><LocationProbe /><Page name="approval-center" /></>} />
          <Route path="/webstores/:id" element={<><LocationProbe /><Page name="webstore-detail" /></>} />
          <Route path="/wrap-lab" element={<><LocationProbe /><Page name="wrap-lab" /></>} />
          <Route path="/finance" element={<><LocationProbe /><Page name="finance" /></>} />
          <Route path="/studio/design-image" element={<><LocationProbe /><Page name="design-image" /></>} />
          <Route path="/team/messages" element={<><LocationProbe /><Page name="messages" /></>} />
          <Route path="/platform-admin" element={<><LocationProbe /><Page name="platform-admin" /></>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

function renderAppRouteHarness(initialPath = "/") {
  const permissions = FULL_PERMISSIONS;
  api.get.mockResolvedValue({ data: { open_workspaces: [], recent_workspaces: [], limits: { max_open: 8, max_recent: 20 } } });
  api.post.mockResolvedValue({ data: { open_workspaces: [], recent_workspaces: [], limits: { max_open: 8, max_recent: 20 } } });
  useAuth.mockReturnValue({
    devBypass: false,
    hasPerm: (permission) => permissions.includes(permission),
    logout: jest.fn(),
    permissions,
    tenant: { id: "tenant-1", name: "Donnell Black's Shop", slug: "dev-shop" },
    user: { id: "user-1", email: "owner@example.com", full_name: "Owner User", platform_admin: true },
  });

  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/kiosk/production" element={<><LocationProbe /><Page name="kiosk" /></>} />
        <Route element={<AppShell />}>
          <Route path="/" element={<><LocationProbe /><Page name="home" /></>} />
          <Route path="/home" element={<Navigate to="/" replace />} />
          <Route path="/shop-operations" element={<><LocationProbe /><Page name="shop-operations-overview" /></>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

function expectActiveArea(activeLabel) {
  const buttons = within(screen.getByTestId("primary-sidebar-nav")).getAllByRole("button");
  const active = buttons.find((button) => button.getAttribute("data-active") === "true");
  expect(active).toHaveAttribute("aria-label", activeLabel);
}

beforeEach(() => {
  jest.clearAllMocks();
  window.localStorage.clear();
});

function waitMs(ms) {
  return act(async () => {
    await new Promise((resolve) => {
      window.setTimeout(resolve, ms);
    });
  });
}

test("single-level sidebar renders the exact area order and bottom account controls", async () => {
  renderShell("/orders");

  const navButtons = within(screen.getByTestId("primary-sidebar-nav")).getAllByRole("button");
  expect(navButtons.map((button) => button.getAttribute("aria-label"))).toEqual([
    "Home",
    "Shop Operations",
    "Business & Finance",
    "Team & Productivity",
    "Tools & Resources",
    "Control Center",
    "Help & Community",
  ]);
  expect(screen.queryByTestId("flyout-shop-operations")).not.toBeInTheDocument();
  expect(within(screen.getByTestId("sidebar-bottom-controls")).getByTestId("sidebar-pin-toggle")).toBeInTheDocument();
  expect(within(screen.getByTestId("sidebar-bottom-controls")).getByTestId("sidebar-account-menu")).toBeInTheDocument();
  expect(within(screen.getByTestId("sidebar-bottom-controls")).getByTestId("sidebar-notifications-button")).toBeInTheDocument();
  expect(within(screen.getByTestId("sidebar-bottom-controls")).queryByTestId("notification-bell")).not.toBeInTheDocument();
  expect(within(screen.getByTestId("sidebar-bottom-controls")).queryByTestId("sidebar-global-search")).not.toBeInTheDocument();
});

test("root and Shop Operations overview have distinct route ownership", async () => {
  const root = renderShell("/");
  expect(screen.getByTestId("current-path")).toHaveTextContent("/");
  expectActiveArea("Home");
  expect(screen.getByTestId("module-nav-home-overview")).toHaveAttribute("aria-current", "page");
  expect(screen.queryByTestId("module-nav-shop-overview")).not.toBeInTheDocument();
  root.unmount();

  renderShell("/shop-operations");
  expect(screen.getByTestId("current-path")).toHaveTextContent("/shop-operations");
  expectActiveArea("Shop Operations");
  expect(screen.getByTestId("module-nav-shop-overview")).toHaveAttribute("aria-current", "page");
});

test.each([
  ["/customers", "Customers", "module-nav-customers"],
  ["/intake", "Sales", "module-nav-sales"],
  ["/quotes", "Sales", "module-nav-sales"],
  ["/orders", "Sales", "module-nav-sales"],
  ["/approval-center", "Approval Center", "module-nav-approval-center"],
  ["/work-orders", "Production", "module-nav-production"],
  ["/webstores", "Webstores", "module-nav-webstores"],
  ["/wrap-lab", "Wrap Lab", "module-nav-wrap-lab"],
])("%s belongs to Shop Operations and activates %s", async (route, _moduleLabel, testId) => {
  renderShell(route);

  expectActiveArea("Shop Operations");
  expect(screen.getByTestId(testId)).toHaveAttribute("aria-current", "page");
});

test("Production Kiosk route renders outside AppShell", async () => {
  renderAppRouteHarness("/kiosk/production");

  expect(screen.getByTestId("current-path")).toHaveTextContent("/kiosk/production");
  expect(screen.getByTestId("kiosk-route")).toBeInTheDocument();
  expect(screen.queryByTestId("authenticated-app-shell")).not.toBeInTheDocument();
  expect(screen.queryByTestId("app-shell-sidebar")).not.toBeInTheDocument();
});

test("/home redirects to the Home dashboard route outside the kiosk route", async () => {
  renderAppRouteHarness("/home");

  await waitFor(() => expect(screen.getByTestId("current-path")).toHaveTextContent("/"));
  expect(screen.getByTestId("home-route")).toBeInTheDocument();
  expect(screen.getByTestId("authenticated-app-shell")).toBeInTheDocument();
  expectActiveArea("Home");
});

test("desktop sidebar hover and pin expand as an overlay without shifting the workspace", async () => {
  const user = userEvent.setup();
  renderShell("/orders");

  const sidebar = screen.getByTestId("desktop-sidebar-shell");
  const mainRegion = screen.getByTestId("app-shell-main-region");
  expect(sidebar).toHaveAttribute("data-expanded", "false");
  expect(mainRegion.style.getPropertyValue("--app-shell-sidebar-width")).toBe("96px");

  fireEvent.mouseEnter(sidebar);
  expect(sidebar).toHaveAttribute("data-expanded", "true");
  expect(sidebar).toHaveAttribute("data-sidebar-width", "96");
  expect(mainRegion.style.getPropertyValue("--app-shell-sidebar-width")).toBe("96px");

  await user.click(screen.getByTestId("sidebar-pin-toggle"));
  expect(sidebar).toHaveAttribute("data-pinned", "true");
  expect(window.localStorage.getItem("signguy.sidebarPinned")).toBe("true");
  fireEvent.mouseLeave(sidebar);
  await waitMs(220);
  expect(sidebar).toHaveAttribute("data-expanded", "true");
  expect(mainRegion.style.getPropertyValue("--app-shell-sidebar-width")).toBe("96px");
});

test("global header contains breadcrumbs, search, create, messages, notifications, and account controls", async () => {
  renderShell("/orders/order-1042?tab=items");

  const header = screen.getByTestId("global-header");
  expect(within(header).getByTestId("global-header-title")).toHaveTextContent("Shop Operations");
  expect(within(header).queryByTestId("global-header-subtitle")).not.toBeInTheDocument();
  expect(within(header).getByTestId("global-breadcrumbs")).toHaveTextContent("Shop Operations/Orders/Order #order-1042");
  expect(within(header).getByTestId("global-search")).toBeInTheDocument();
  expect(within(header).getByTestId("global-create-menu")).toBeInTheDocument();
  expect(within(header).getByTestId("global-messages-button")).toBeInTheDocument();
  expect(within(header).getByTestId("notification-bell")).toBeInTheDocument();
  expect(within(header).getByTestId("global-account-menu")).toBeInTheDocument();
});

test("Orders hierarchy uses one compact header, one module tab row, and one combined Sales command bar", async () => {
  renderShell("/orders");

  expect(screen.getByTestId("global-header-title")).toHaveTextContent("Shop Operations");
  expect(screen.queryByTestId("global-header-subtitle")).not.toBeInTheDocument();
  expect(screen.getByTestId("global-breadcrumbs")).toHaveTextContent("Shop Operations/Orders");
  expect(screen.queryByTestId("shell-page-heading")).not.toBeInTheDocument();
  expect(screen.queryByTestId("shell-page-title")).not.toBeInTheDocument();
  expect(screen.queryByText("Shop Operations workspace")).not.toBeInTheDocument();

  const secondaryNav = screen.getByTestId("secondary-navigation-row");
  const ribbon = screen.getByTestId("contextual-ribbon");
  expect(screen.getByTestId("shell-internal-tabs")).toBeInTheDocument();
  expect(within(screen.getByTestId("shell-internal-tabs")).getByTestId("sales-command-selector")).toBeInTheDocument();
  expect(within(ribbon).queryByTestId("sales-command-selector")).not.toBeInTheDocument();
  expect(secondaryNav.compareDocumentPosition(ribbon) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

test("Shop Operations secondary navigation uses Sales and omits direct Intake, Quotes, and Orders modules", async () => {
  renderShell("/orders");

  const labels = within(screen.getByTestId("module-tab-row")).getAllByRole("link").map((link) => link.textContent);
  expect(labels).toEqual(["Overview", "Customers", "Sales", "Approval Center", "Production", "Webstores", "Wrap Lab"]);
  expect(screen.getByTestId("module-nav-sales")).toHaveAttribute("aria-current", "page");
  expect(screen.queryByTestId("module-nav-intake")).not.toBeInTheDocument();
  expect(screen.queryByTestId("module-nav-quotes")).not.toBeInTheDocument();
  expect(screen.queryByTestId("module-nav-orders")).not.toBeInTheDocument();
});

test("Sales selector preserves Intake Request, Quote, and Order routes in order", async () => {
  renderShell("/quotes");

  const tabs = within(screen.getByTestId("sales-command-selector")).getAllByRole("tab");
  expect(tabs.map((tab) => tab.textContent)).toEqual(["Intake Requests", "Quotes", "Orders"]);
  expect(screen.getByTestId("internal-tab-quotes")).toHaveAttribute("aria-current", "page");
  expect(screen.getByTestId("quotes-route")).toBeInTheDocument();
});

test("Orders route activates Sales and Orders tabs with the ribbon directly below", async () => {
  renderShell("/orders");

  expect(screen.getByTestId("module-nav-sales")).toHaveAttribute("data-active", "true");
  expect(screen.getByTestId("internal-tab-orders")).toHaveAttribute("data-active", "true");
  expect(screen.getByTestId("internal-tab-orders")).toHaveAttribute("aria-current", "page");
  expect(screen.queryByText(/^SALES$/)).not.toBeInTheDocument();
  expect(screen.getByTestId("shell-internal-tabs")).toContainElement(screen.getByTestId("sales-command-selector"));
  expect(screen.getByTestId("contextual-ribbon")).not.toContainElement(screen.getByTestId("sales-command-selector"));
});

test("Orders ribbon uses icon-over-label commands and exposes all order views", async () => {
  const user = userEvent.setup();
  renderShell("/orders");

  const newOrderCommand = screen.getByTestId("ribbon-command-newOrder");
  expect(newOrderCommand).toHaveAttribute("data-layout", "ribbon");
  expect(newOrderCommand).toHaveAttribute("href", "/orders?new=1");
  expect(newOrderCommand).toHaveClass("flex-col");
  expect(newOrderCommand.querySelector("svg")).toBeInTheDocument();
  expect(screen.queryByTestId("ribbon-command-newIntake")).not.toBeInTheDocument();
  expect(screen.queryByTestId("ribbon-command-newQuote")).not.toBeInTheDocument();

  expect(screen.getByTestId("ribbon-order-view-all")).toHaveTextContent("All Orders");
  expect(screen.getByTestId("ribbon-order-view-in_production")).toHaveTextContent("In Production");
  expect(screen.getByTestId("ribbon-order-view-ready")).toHaveTextContent("Ready");
  expect(screen.getByTestId("ribbon-order-view-all")).toHaveAttribute("aria-pressed", "true");

  await user.click(screen.getByTestId("ribbon-order-view-in_production"));
  await waitFor(() => expect(screen.getByTestId("current-path")).toHaveTextContent("/orders?status=in_production"));

  await user.click(screen.getByTestId("ribbon-order-views-dropdown"));
  expect(screen.getByTestId("ribbon-order-view-option-all")).toHaveTextContent("All Orders");
  expect(screen.getByTestId("ribbon-order-view-option-draft")).toHaveTextContent("Draft");
  expect(screen.getByTestId("ribbon-order-view-option-confirmed")).toHaveTextContent("Confirmed");
  expect(screen.getByTestId("ribbon-order-view-option-ready")).toHaveTextContent("Ready");
  expect(screen.getByTestId("ribbon-order-view-option-in_production")).toHaveTextContent("In Production");
  expect(screen.getByTestId("ribbon-order-view-option-completed")).toHaveTextContent("Completed");
  expect(screen.getByTestId("ribbon-order-view-option-cancelled")).toHaveTextContent("Cancelled");

  await user.click(screen.getByTestId("ribbon-order-view-option-ready"));
  await waitFor(() => expect(screen.getByTestId("current-path")).toHaveTextContent("/orders?status=ready"));
});

test("Order and Customer records expose the required shell-level internal tab order", async () => {
  const first = renderShell("/orders/order-1042");
  expect(within(screen.getByTestId("shell-internal-tabs")).getAllByRole("tab").map((tab) => tab.textContent)).toEqual([
    "Overview",
    "Order Items",
    "Production",
    "Documents & Approvals",
    "Files & Artwork",
    "Financial",
    "Activity",
  ]);
  first.unmount();

  renderShell("/customers/customer-1");
  expect(within(screen.getByTestId("shell-internal-tabs")).getAllByRole("tab").map((tab) => tab.textContent)).toEqual([
    "Overview",
    "Contacts",
    "Communications",
    "Requests",
    "Quotes",
    "Orders",
    "Files & Forms",
    "Portal",
    "Activity",
  ]);
});

test("Create menu is permission-aware and keeps Intake Request, Quote, and Order separate", async () => {
  const user = userEvent.setup();
  renderShell("/orders", { permissions: FULL_PERMISSIONS.filter((perm) => perm !== "quote:write") });

  await user.click(screen.getByTestId("global-create-menu"));

  expect(screen.getByTestId("create-action-newIntake")).toHaveTextContent("New Intake");
  expect(screen.queryByTestId("create-action-newQuote")).not.toBeInTheDocument();
  expect(screen.getByTestId("create-action-newOrder")).toHaveTextContent("New Order");
});

test("global search queries only permitted record groups and opens the selected Sales context", async () => {
  const user = userEvent.setup();
  renderShell("/orders", { permissions: ["order:read", "order:write", "message:read"] });
  api.get.mockImplementation((url) => {
    if (url === "/workspaces") return Promise.resolve({ data: { open_workspaces: [], recent_workspaces: [], limits: { max_open: 8, max_recent: 20 } } });
    if (url === "/orders") return Promise.resolve({ data: { items: [{ id: "order-1042", number: 1042, job_name: "Smith Landscaping" }] } });
    return Promise.resolve({ data: { items: [] } });
  });

  await user.type(screen.getByLabelText("Global search"), "smith");
  await screen.findByTestId("global-search-group-orders");
  await user.click(screen.getByText("O-1042 Smith Landscaping"));

  expect(screen.getByTestId("current-path")).toHaveTextContent("/orders/order-1042");
});

test("authorized platform users switch through the account menu, not the customer-facing sidebar", async () => {
  const user = userEvent.setup();
  renderShell("/orders");

  expect(screen.queryByTestId("primary-nav-platform-admin")).not.toBeInTheDocument();
  await user.click(screen.getByTestId("global-account-menu"));
  await user.click(screen.getByTestId("account-platform-admin-link"));

  await waitFor(() => expect(screen.getByTestId("current-path")).toHaveTextContent("/platform-admin"));
});

test("current active navigation does not expose banned terminology", async () => {
  renderShell("/orders");

  expect(screen.queryByText(/Order Portals/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/Job Ticket/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/Design Studio/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/Team & Workflow/i)).not.toBeInTheDocument();
});
