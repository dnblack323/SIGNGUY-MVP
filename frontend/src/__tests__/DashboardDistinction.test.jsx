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

beforeEach(() => {
  jest.clearAllMocks();
  mockPermissions = ["finance:read", "invoice:read", "employee:read", "timesheet:read", "timesheet:manage"];
  api.get.mockImplementation((url) => {
    if (url === "/dashboard/summary") return Promise.resolve({ data: summary });
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
  expect(await screen.findByTestId("home-section-business-finance")).toBeInTheDocument();
  expect(screen.getByTestId("home-section-team-productivity")).toBeInTheDocument();
  expect(screen.queryByTestId("shop-operations-snapshot")).not.toBeInTheDocument();
  expect(within(screen.getByTestId("home-section-business-finance")).getByRole("link", { name: /I-9001/i })).toHaveAttribute("href", "/invoices/invoice-1");
  home.unmount();

  renderDashboards("/shop-operations");
  expect(await screen.findByTestId("shop-operations-overview-page")).toBeInTheDocument();
  expect(await screen.findByTestId("shop-operations-snapshot")).toBeInTheDocument();
  expect(await screen.findByTestId("shop-list-production-attention")).toBeInTheDocument();
  expect(screen.queryByTestId("home-section-business-finance")).not.toBeInTheDocument();
  expect(screen.queryByTestId("home-section-team-productivity")).not.toBeInTheDocument();
  expect(within(screen.getByTestId("shop-list-production-attention")).getByRole("link", { name: /W-1042/i })).toHaveAttribute("href", "/work-orders/work-order-1");
});

test("Home uses honest empty states and hides restricted finance and team information", async () => {
  mockPermissions = [];
  api.get.mockImplementation((url) => {
    if (url === "/dashboard/summary") {
      return Promise.resolve({
        data: {
          counts: { active_orders: 0, quotes_follow_up: 0, work_orders_attention: 0, unpaid_invoices: 2 },
          active_orders: [],
          quotes_follow_up: [],
          work_orders_attention: [],
          unpaid_invoices: summary.unpaid_invoices,
          recent_emails: [],
          recent_activity: [],
        },
      });
    }
    return Promise.resolve({ data: {} });
  });

  renderDashboards("/");

  expect(await screen.findByText("No shop operations attention items from current records.")).toBeInTheDocument();
  expect(screen.getByText("Finance information is hidden because this account does not have finance or invoice access.")).toBeInTheDocument();
  expect(screen.getByText("Team information is hidden because this account does not have team access.")).toBeInTheDocument();
  expect(screen.queryByText("Party Squad Rentals")).not.toBeInTheDocument();
});
