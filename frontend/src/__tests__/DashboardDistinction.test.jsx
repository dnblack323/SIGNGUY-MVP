import { screen, within } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import DashboardPage from "@/pages/DashboardPage";
import ShopOperationsOverviewPage from "@/pages/ShopOperationsOverviewPage";
import { renderWithProviders } from "@/test-utils";
import api from "@/lib/api";

let mockPermissions = [];

jest.mock("@/auth/AuthContext", () => ({
  useAuth: () => ({
    hasPerm: (permission) => mockPermissions.includes(permission),
  }),
}));

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
  },
}));

const summary = {
  counts: {
    active_orders: 1,
    quotes_follow_up: 1,
    work_orders_attention: 1,
    unpaid_invoices: 1,
  },
  active_orders: [
    { id: "order-1", number: "91015", job_name: "Window decals", status: "confirmed", created_at: "2026-08-12T10:00:00Z" },
  ],
  quotes_follow_up: [
    { id: "quote-1", number: "1048", job_name: "Trailer graphics", status: "sent", total_cents: 125000, created_at: "2026-08-12T09:00:00Z" },
  ],
  work_orders_attention: [
    { id: "work-order-1", number: "1042", production_status: "in_progress", created_at: "2026-08-12T08:00:00Z" },
  ],
  unpaid_invoices: [
    { id: "invoice-1", number: "9001", title: "Party Squad Rentals", due_date: "2026-08-14T09:00:00Z", total_cents: 50000, status: "overdue" },
  ],
  recent_emails: [
    { id: "email-1", subject: "Proof sent", to_email: "owner@example.com", status: "sent", created_at: "2026-08-12T07:00:00Z" },
  ],
  recent_activity: [
    { id: "audit-1", summary: "Order moved to production", created_at: "2026-08-12T06:00:00Z" },
  ],
};

const invoiceList = {
  key: "unpaid_invoices_list", family: "unpaid_invoices", kind: "list", title: "Unpaid invoices", to: "/invoices",
};
const quoteList = {
  key: "quotes_awaiting_list", family: "quotes_awaiting", kind: "list", title: "Quotes awaiting decision", to: "/quotes",
};
const home = {
  layout: { version: 1, order: ["unpaid_invoices_list", "quotes_awaiting_list"], hidden: [], collapsed: [] },
  widgets: [invoiceList, quoteList],
  restricted: [],
  data: {
    unpaid_invoices_list: {
      state: "ready", total: 1,
      items: [{ id: "invoice-1", ref: "I-9001", title: "Party Squad Rentals", status: "overdue", status_kind: "invoice", amount_cents: 50000, due_date: "2026-08-14T09:00:00Z", to: "/invoices/invoice-1" }],
    },
    quotes_awaiting_list: { state: "ready", total: 0, items: [] },
  },
};

beforeEach(() => {
  jest.clearAllMocks();
  mockPermissions = ["finance:read", "invoice:read", "employee:read", "timesheet:read", "timesheet:manage"];
  api.get.mockImplementation((url) => {
    if (url === "/dashboard/home") return Promise.resolve({ data: home });
    if (url === "/dashboard/summary") return Promise.resolve({ data: summary });
    if (url === "/dashboard/shop-operations/analytics") {
      return Promise.resolve({
        data: {
          counts: { blocked_stages: 1, waiting_stages: 2, open_completion_issues: 1, completed_orders: 3 },
          bottlenecks: [{ label: "Print", active_count: 4, signal: "stage_capacity" }],
          restricted_financial_data: false,
        },
      });
    }
    if (url === "/team/dashboard") return Promise.resolve({ data: { employee_status_counts: { active: 4 } } });
    if (url === "/timesheets/pending-review") return Promise.resolve({ data: { items: [{ id: "time-1" }] } });
    return Promise.resolve({ data: {} });
  });
});

function renderDashboards(route = "/") {
  return renderWithProviders(
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/shop-operations" element={<ShopOperationsOverviewPage />} />
    </Routes>,
    { route },
  );
}

test("Home and Shop Operations Overview have materially different compositions", async () => {
  const home = renderDashboards("/");
  expect(await screen.findByTestId("home-dashboard-page")).toBeInTheDocument();
  expect(await screen.findByTestId("home-widget-unpaid_invoices_list")).toBeInTheDocument();
  expect(screen.getByTestId("home-widget-quotes_awaiting_list")).toHaveTextContent("No quotes awaiting a decision.");
  expect(screen.queryByTestId("shop-operations-snapshot")).not.toBeInTheDocument();
  expect(within(screen.getByTestId("home-widget-unpaid_invoices_list")).getByRole("link", { name: /I-9001/i })).toHaveAttribute("href", "/invoices/invoice-1");
  home.unmount();

  renderDashboards("/shop-operations");
  expect(await screen.findByTestId("shop-operations-overview-page")).toBeInTheDocument();
  expect(await screen.findByTestId("shop-operations-snapshot")).toBeInTheDocument();
  expect(await screen.findByTestId("shop-operations-analytics")).toHaveTextContent("Operational Analytics");
  expect(screen.getByTestId("shop-operations-analytics")).toHaveTextContent("Production analytics exclude restricted financial data.");
  expect(await screen.findByTestId("shop-list-production-attention")).toBeInTheDocument();
  expect(screen.queryByTestId("home-dashboard-page")).not.toBeInTheDocument();
  expect(within(screen.getByTestId("shop-list-production-attention")).getByRole("link", { name: /W-1042/i })).toHaveAttribute("href", "/work-orders/work-order-1");
});

test("Home uses honest empty states and hides restricted finance and team information", async () => {
  mockPermissions = [];
  api.get.mockImplementation((url) => {
    if (url === "/dashboard/home") {
      return Promise.resolve({
        data: {
          layout: { version: 1, order: ["quotes_awaiting_list", "unpaid_invoices_list", "active_team_kpi"], hidden: [], collapsed: [] },
          widgets: [quoteList],
          restricted: [
            { ...invoiceList, required_permission: "invoice:read" },
            { key: "active_team_kpi", family: "active_team", kind: "kpi", title: "Active team members", to: "/team/employees", required_permission: "employee:read" },
          ],
          data: { quotes_awaiting_list: { state: "ready", total: 0, items: [] } },
        },
      });
    }
    return Promise.resolve({ data: {} });
  });

  renderDashboards("/");

  expect(await screen.findByText("No quotes awaiting a decision.")).toBeInTheDocument();
  expect(screen.queryByTestId("home-widget-unpaid_invoices_list")).not.toBeInTheDocument();
  expect(screen.queryByTestId("home-widget-active_team_kpi")).not.toBeInTheDocument();
  expect(screen.queryByText("Party Squad Rentals")).not.toBeInTheDocument();
});
