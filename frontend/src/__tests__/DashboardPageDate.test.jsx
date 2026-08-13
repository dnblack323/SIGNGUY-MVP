import { screen } from "@testing-library/react";
import DashboardPage from "@/pages/DashboardPage";
import { renderWithProviders } from "@/test-utils";
import api from "@/lib/api";

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
      counts: {
        active_orders: 0,
        quotes_follow_up: 0,
        work_orders_attention: 0,
        unpaid_invoices: 1,
      },
      quotes_follow_up: [],
      work_orders_attention: [],
      unpaid_invoices: [
        {
          id: "invoice-1",
          number: "1048",
          title: "Party Squad Rentals",
          due_date: "2026-07-14T09:00:00+00:00",
          total_cents: 125000,
          status: "unpaid",
        },
      ],
      recent_emails: [],
      recent_activity: [],
    },
  });

  renderWithProviders(<DashboardPage />);

  expect(await screen.findByText("Due Jul 14, 2026")).toBeInTheDocument();
  expect(screen.queryByText(/2026-07-14T09:00:00\+00:00/)).not.toBeInTheDocument();
});
