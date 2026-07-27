import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import AppShell from "@/components/app-shell/AppShell";
import { useAuth } from "@/auth/AuthContext";

jest.mock("@/auth/AuthContext", () => ({
  useAuth: jest.fn(),
}));

jest.mock("@/components/notifications/NotificationBell", () => function NotificationBellMock() {
  return <button type="button" data-testid="notification-bell">Notifications</button>;
});

jest.mock("@/components/assistant/AssistantLauncher", () => function AssistantLauncherMock() {
  return <div data-testid="assistant-launcher" />;
});

const FULL_PERMISSIONS = [
  "customer:read",
  "customer:write",
  "quote:read",
  "quote:write",
  "order:read",
  "order:write",
  "pricing:read",
  "pricing:calculate",
  "pricing:write",
  "work_order:read",
  "schedule:read",
  "document:read",
  "webstore:read",
  "wrap_lab:read",
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
  return <div data-testid="current-path">{location.pathname}</div>;
}

function Page({ name }) {
  return <div data-testid={`${name}-route`}>{name} route</div>;
}

function renderShell(initialPath = "/") {
  useAuth.mockReturnValue({
    devBypass: false,
    hasPerm: (permission) => FULL_PERMISSIONS.includes(permission),
    logout: jest.fn(),
    permissions: FULL_PERMISSIONS,
    tenant: { id: "tenant-1", name: "Donnell Black's Shop" },
    user: { id: "user-1", email: "thesigntistslab@gmail.com", full_name: "Donnell Black", roles: ["platform_admin"] },
  });

  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<><LocationProbe /><Page name="overview" /></>} />
          <Route path="/customers" element={<><LocationProbe /><Page name="customers" /></>} />
          <Route path="/quotes" element={<><LocationProbe /><Page name="quotes" /></>} />
          <Route path="/orders" element={<><LocationProbe /><Page name="orders" /></>} />
          <Route path="/pricing-calculator" element={<><LocationProbe /><Page name="pricing" /></>} />
          <Route path="/finance" element={<><LocationProbe /><Page name="finance" /></>} />
          <Route path="/studio/design-image" element={<><LocationProbe /><Page name="design-image" /></>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

test("clicking a main-area sidebar item opens that area's overview route", async () => {
  const user = userEvent.setup();
  renderShell("/customers");

  await user.click(screen.getByTestId("primary-nav-business-finance"));

  expect(screen.getByTestId("current-path")).toHaveTextContent("/finance");
  expect(screen.getByTestId("finance-route")).toBeInTheDocument();
});

test("desktop shell does not render the obsolete long module flyout", () => {
  renderShell("/orders");

  expect(screen.getByTestId("primary-sidebar-nav")).toBeInTheDocument();
  expect(screen.getByTestId("module-tab-row")).toBeInTheDocument();
  expect(screen.queryByTestId("flyout-shop-operations")).not.toBeInTheDocument();
  expect(screen.queryByTestId("category-nav-more")).not.toBeInTheDocument();
});

test("active area module row is visible and module tabs navigate to existing routes", async () => {
  const user = userEvent.setup();
  renderShell("/orders");

  const tabs = screen.getByTestId("module-tab-row");
  expect(tabs).toHaveAttribute("data-area-key", "shop-operations");
  expect(screen.getByTestId("module-nav-orders")).toHaveAttribute("aria-current", "page");

  await user.click(screen.getByTestId("module-nav-customers"));

  expect(screen.getByTestId("current-path")).toHaveTextContent("/customers");
  expect(screen.getByTestId("customers-route")).toBeInTheDocument();
});

test("contextual ribbon is visible and changes with the active module", async () => {
  const user = userEvent.setup();
  renderShell("/orders");

  expect(screen.getByTestId("contextual-ribbon")).toHaveAttribute("data-module-key", "orders");
  expect(screen.getByTestId("ribbon-command-newOrder")).toBeInTheDocument();

  await user.click(screen.getByTestId("module-nav-customers"));

  expect(screen.getByTestId("contextual-ribbon")).toHaveAttribute("data-module-key", "customers");
  expect(screen.getByTestId("ribbon-command-newCustomer")).toBeInTheDocument();
});

test("quick access toolbar renders once and uses the shared command definitions", () => {
  renderShell("/orders");

  expect(screen.getAllByTestId("quick-access-toolbar")).toHaveLength(1);
  expect(screen.getByTestId("qat-command-newCustomer")).toBeInTheDocument();
  expect(screen.getByTestId("qat-command-newOrder")).toBeInTheDocument();
  expect(screen.getByTestId("qat-command-assistant")).toBeInTheDocument();
});

test("global search, notifications, and account controls remain at the sidebar bottom", () => {
  renderShell("/orders");

  const bottomControls = screen.getByTestId("sidebar-bottom-controls");
  expect(within(bottomControls).getByTestId("sidebar-global-search")).toBeInTheDocument();
  expect(within(bottomControls).getByTestId("notification-bell")).toBeInTheDocument();
  expect(within(bottomControls).getByTestId("sidebar-user-menu")).toBeInTheDocument();
});

test("authenticated shell renders after Google login state is present", () => {
  renderShell("/");

  expect(screen.getByTestId("authenticated-app-shell")).toBeInTheDocument();
  expect(screen.getByTestId("overview-route")).toBeInTheDocument();
  expect(screen.getByTestId("sidebar-tenant-name")).toHaveTextContent("Donnell Black's Shop");
});

test("existing feature routes still render inside the corrected shell", () => {
  renderShell("/studio/design-image");

  expect(screen.getByTestId("authenticated-app-shell")).toBeInTheDocument();
  expect(screen.getByTestId("design-image-route")).toBeInTheDocument();
  expect(screen.getByTestId("module-tab-row")).toHaveAttribute("data-area-key", "design-studio");
  expect(screen.getByTestId("contextual-ribbon")).toHaveAttribute("data-module-key", "design-image");
});
