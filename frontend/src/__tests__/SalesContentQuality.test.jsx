import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../test-utils";
import IntakePage from "@/pages/IntakePage";
import QuotesPage from "@/pages/QuotesPage";
import api from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";

jest.mock("@/auth/AuthContext", () => ({
  useAuth: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
  },
}));

beforeEach(() => {
  jest.clearAllMocks();
  useAuth.mockReturnValue({
    hasPerm: () => true,
  });
});

test("Intake Requests show localized due dates instead of raw ISO timestamps", async () => {
  api.get.mockResolvedValueOnce({
    data: {
      items: [
        {
          id: "intake-1",
          intake_number: "1082",
          project_name: "Trailer graphics",
          source_type: "customer_portal",
          status: "new",
          priority: "high",
          requested_due_date: "2026-08-07T09:00:00+00:00",
          created_at: "2026-08-01T12:00:00+00:00",
          items: [{}],
          missing_information: [],
        },
      ],
    },
  });

  renderWithProviders(<IntakePage />, { route: "/intake" });

  await waitFor(() => expect(screen.getByTestId("intake-table")).toBeInTheDocument());
  expect(screen.getByText("Aug 07, 2026")).toBeInTheDocument();
  expect(screen.queryByText("2026-08-07T09:00:00+00:00")).not.toBeInTheDocument();
});

test("Quotes page uses the approved customer quote subtitle", async () => {
  api.get.mockResolvedValueOnce({ data: { items: [] } });

  renderWithProviders(<QuotesPage />, { route: "/quotes" });

  expect(await screen.findByText("Create, price, send, and track customer quotes.")).toBeInTheDocument();
  expect(screen.queryByText("Manual pricing. No calculators.")).not.toBeInTheDocument();
});
