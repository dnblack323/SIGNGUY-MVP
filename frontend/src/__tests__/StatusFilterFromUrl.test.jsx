import { screen, waitFor } from "@testing-library/react";
import QuotesPage from "@/pages/QuotesPage";
import WorkOrdersPage from "@/pages/WorkOrdersPage";
import { renderWithProviders } from "@/test-utils";
import api from "@/lib/api";

jest.mock("@/auth/AuthContext", () => ({ useAuth: () => ({ hasPerm: () => false }) }));
jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: { get: jest.fn(() => Promise.resolve({ data: { items: [] } })) },
  extractError: (_e, fallback) => fallback,
}));

beforeEach(() => jest.clearAllMocks());

test("Quotes opens with the status from the URL (Home breakdown links)", async () => {
  renderWithProviders(<QuotesPage />, { route: "/quotes?status=viewed" });
  await waitFor(() => expect(api.get).toHaveBeenCalledWith("/quotes", { params: { status: "viewed", limit: 100 } }));
  expect(screen.getByTestId("quotes-filter-viewed").className).toMatch(/bg-primary/);
  expect(screen.getByTestId("quotes-filter-all").className).not.toMatch(/bg-primary /);
});

test("Quotes without a status parameter is unfiltered", async () => {
  renderWithProviders(<QuotesPage />, { route: "/quotes" });
  await waitFor(() => expect(api.get).toHaveBeenCalledWith("/quotes", { params: { status: undefined, limit: 100 } }));
});

test("Work Orders opens with the production status from the URL", async () => {
  renderWithProviders(<WorkOrdersPage />, { route: "/work-orders?production_status=blocked" });
  await waitFor(() => expect(api.get).toHaveBeenCalledWith("/work-orders", expect.objectContaining({
    params: expect.objectContaining({ production_status: "blocked" }),
  })));
});

test("an unknown status falls back to all", async () => {
  renderWithProviders(<WorkOrdersPage />, { route: "/work-orders?production_status=bogus" });
  await waitFor(() => expect(api.get).toHaveBeenCalledWith("/work-orders", expect.objectContaining({
    params: expect.objectContaining({ production_status: undefined }),
  })));
});
