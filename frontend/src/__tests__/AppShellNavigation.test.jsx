import React from "react";
import { Route, Routes } from "react-router-dom";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";
import AppShell from "@/components/app-shell/AppShell";

let mockPermissions = [];

jest.mock("@/auth/AuthContext", () => ({
  __esModule: true,
  useAuth: () => ({
    devBypass: false,
    permissions: mockPermissions,
    user: { id: "u1", tenant_id: "t1", role: "owner", full_name: "Dev Owner", email: "dev@example.com" },
    tenant: { name: "Dev Shop", slug: "dev-shop" },
    logout: jest.fn(),
  }),
}));

jest.mock("@/components/notifications/NotificationBell", () => function MockNotificationBell() {
  return <button type="button" aria-label="Notifications">Notifications</button>;
});

function ShellRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<div>Dashboard content</div>} />
        <Route path="/orders" element={<div>Orders content</div>} />
        <Route path="/customers" element={<div>Customers content</div>} />
        <Route path="/work-orders" element={<div>Production content</div>} />
        <Route path="/shop-schedule" element={<div>Operational shop schedule content</div>} />
        <Route path="/documents" element={<div>Documents content</div>} />
        <Route path="/finance" element={<div>Finance content</div>} />
        <Route path="/team/tasks" element={<div>Tasks content</div>} />
        <Route path="/team/schedule" element={<div>Employee team schedule content</div>} />
      </Route>
    </Routes>
  );
}

beforeEach(() => {
  mockPermissions = [
    "order:read",
    "customer:read",
    "work_order:read",
    "schedule:read",
    "webstore:read",
    "document:read",
    "finance:read",
    "tax_report:read",
    "inventory:read",
    "payroll:read",
    "report:read",
    "task:read",
    "message:read",
    "employee:read",
    "production_workflow:read",
    "ai_assistant:use",
    "ai_tool:use",
    "onboarding:read",
    "help:read",
    "community:read",
    "settings:read",
  ];
});

test("renders only primary categories in the sidebar and Shop Operations modules in top navigation", () => {
  renderWithProviders(<ShellRoutes />, { route: "/orders" });

  const sidebar = screen.getByTestId("primary-sidebar-nav");
  expect(within(sidebar).getByRole("button", { name: "Shop Operations" })).toHaveAttribute("aria-current", "page");
  expect(within(sidebar).getByRole("button", { name: "Business Management" })).toBeInTheDocument();
  expect(within(sidebar).getByRole("button", { name: "Productivity & Collaboration" })).toBeInTheDocument();
  expect(within(sidebar).getByRole("button", { name: "AI / Platform / Community" })).toBeInTheDocument();
  expect(within(sidebar).queryByText("Customers")).not.toBeInTheDocument();
  expect(within(sidebar).queryByText("Orders")).not.toBeInTheDocument();

  const topNav = screen.getByTestId("category-top-nav");
  expect(topNav).toHaveAttribute("data-category-key", "shop-operations");
  expect(within(topNav).getByRole("link", { name: "Orders" })).toHaveAttribute("aria-current", "page");
  expect(within(topNav).getByRole("link", { name: "Customers" })).toBeInTheDocument();
  expect(within(topNav).getByRole("link", { name: "Production" })).toBeInTheDocument();
  expect(within(topNav).getByRole("link", { name: "Scheduling" })).toHaveAttribute("href", "/shop-schedule");
  expect(screen.getByText("Orders content")).toBeInTheDocument();
});

test("renders quick access as a compact toolbar above workspace navigation", () => {
  renderWithProviders(<ShellRoutes />, { route: "/orders" });

  const toolbar = screen.getByTestId("quick-access-toolbar");
  expect(within(toolbar).getByPlaceholderText("Search orders, customers, quotes...")).toBeInTheDocument();
  expect(screen.queryByTestId("topbar-page-title")).not.toBeInTheDocument();
});

test("collapses and expands the sidebar while preserving accessible primary category labels", async () => {
  const user = userEvent.setup();
  renderWithProviders(<ShellRoutes />, { route: "/orders" });

  await user.click(screen.getByRole("button", { name: "Collapse sidebar" }));
  expect(screen.getByTestId("app-shell-sidebar")).toHaveAttribute("data-collapsed", "true");
  expect(screen.getByRole("button", { name: "Shop Operations" })).toHaveAttribute("data-active", "true");

  await user.click(screen.getByRole("button", { name: "Expand sidebar" }));
  expect(screen.getByTestId("app-shell-sidebar")).toHaveAttribute("data-collapsed", "false");
});

test("selecting a primary category changes the module row and navigates to the first permitted module", async () => {
  const user = userEvent.setup();
  renderWithProviders(<ShellRoutes />, { route: "/orders" });

  await user.click(screen.getByRole("button", { name: "Business Management" }));
  expect(screen.getByTestId("category-top-nav")).toHaveAttribute("data-category-key", "business-management");
  expect(screen.getByRole("link", { name: "Finance" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByText("Finance content")).toBeInTheDocument();
});

test("separates Shop Schedule and Team Schedule navigation destinations", async () => {
  const user = userEvent.setup();
  renderWithProviders(<ShellRoutes />, { route: "/orders" });

  await user.click(screen.getByRole("link", { name: "Scheduling" }));
  expect(screen.getByTestId("category-top-nav")).toHaveAttribute("data-category-key", "shop-operations");
  expect(screen.getByRole("link", { name: "Scheduling" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByText("Operational shop schedule content")).toBeInTheDocument();
  expect(screen.queryByText("Employee team schedule content")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Productivity & Collaboration" }));
  expect(screen.getByTestId("category-top-nav")).toHaveAttribute("data-category-key", "team");
  const teamScheduleLink = screen.getByRole("link", { name: "Team Schedule" });
  expect(teamScheduleLink).toHaveAttribute("href", "/team/schedule");

  await user.click(teamScheduleLink);
  expect(screen.getByRole("link", { name: "Team Schedule" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByText("Employee team schedule content")).toBeInTheDocument();
  expect(screen.queryByText("Operational shop schedule content")).not.toBeInTheDocument();
});

test("top navigation hides permission-blocked modules and keeps remaining modules reachable", () => {
  mockPermissions = ["order:read", "customer:read"];
  renderWithProviders(<ShellRoutes />, { route: "/orders" });

  const topNav = screen.getByTestId("category-top-nav");
  expect(within(topNav).getByRole("link", { name: "Orders" })).toBeInTheDocument();
  expect(within(topNav).getByRole("link", { name: "Customers" })).toBeInTheDocument();
  expect(within(topNav).queryByRole("link", { name: "Production" })).not.toBeInTheDocument();
  expect(within(topNav).queryByRole("link", { name: "Webstores" })).not.toBeInTheDocument();
});

test("top navigation condenses lower-priority modules into a labeled More menu", async () => {
  const user = userEvent.setup();
  const originalInnerWidth = window.innerWidth;
  Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: 700 });
  renderWithProviders(<ShellRoutes />, { route: "/orders" });

  await user.click(screen.getByRole("button", { name: "Shop Operations more modules" }));
  expect(await screen.findByTestId("category-nav-more-menu")).toBeInTheDocument();
  expect(screen.getByTestId("module-nav-documents-overflow")).toHaveTextContent("Documents");
  Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: originalInnerWidth });
});
