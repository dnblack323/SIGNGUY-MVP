import { screen } from "@testing-library/react";
import DashboardPage from "@/pages/DashboardPage";
import { renderWithProviders } from "@/test-utils";
import api from "@/lib/api";

jest.mock("@/auth/AuthContext", () => ({
  useAuth: () => ({
    hasPerm: (permission) => [
      "finance:read",
      "invoice:read",
      "employee:read",
      "timesheet:read",
      "timesheet:manage",
    ].includes(permission),
  }),
}));

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
  },
}));

beforeEach(() => {
  jest.clearAllMocks();
});

test("Home unpaid invoice due dates are human-readable", async () => {
  api.get.mockResolvedValueOnce({
    data: {
      layout: { version: 1, order: ["unpaid_invoices_list"], hidden: [], collapsed: [] },
      widgets: [{ key: "unpaid_invoices_list", family: "unpaid_invoices", kind: "list", title: "Unpaid invoices", to: "/invoices" }],
      restricted: [],
      data: {
        unpaid_invoices_list: {
          state: "ready",
          total: 1,
          items: [{
            id: "invoice-1", ref: "I-1048", title: "Party Squad Rentals", due_date: "2026-07-14T09:00:00+00:00",
            amount_cents: 125000, status: "sent", status_kind: "invoice", to: "/invoices/invoice-1",
          }],
        },
      },
    },
  });

  renderWithProviders(<DashboardPage />);

  expect(await screen.findByText("Due Jul 14, 2026")).toBeInTheDocument();
  expect(screen.queryByText(/2026-07-14T09:00:00\+00:00/)).not.toBeInTheDocument();
});
