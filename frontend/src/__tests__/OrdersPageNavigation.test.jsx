import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../test-utils";
import api from "@/lib/api";
import OrdersPage from "@/pages/OrdersPage";

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
  },
  extractError: (error, fallback = "Something went wrong") => error?.response?.data?.detail || fallback,
}));

jest.mock("@/auth/AuthContext", () => ({
  __esModule: true,
  useAuth: () => ({
    hasPerm: (permission) => permission === "order:write",
  }),
}));

jest.mock("sonner", () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

const ORDER_ROWS = {
  all: [
    { id: "order-1", number: "91001", job_name: "All Orders Job", status: "confirmed", created_at: "2026-08-01T12:00:00Z" },
  ],
  ready: [
    { id: "order-ready", number: "91002", job_name: "Ready Job", status: "ready", created_at: "2026-08-02T12:00:00Z" },
  ],
  in_production: [
    { id: "order-prod", number: "91003", job_name: "Production Job", status: "in_production", created_at: "2026-08-03T12:00:00Z" },
  ],
};

beforeEach(() => {
  jest.clearAllMocks();
  api.get.mockImplementation((url, config = {}) => {
    if (url === "/orders") {
      const status = config.params?.status || "all";
      return Promise.resolve({ data: { items: ORDER_ROWS[status] || [] } });
    }
    if (url === "/customers") return Promise.resolve({ data: { items: [] } });
    return Promise.resolve({ data: { items: [] } });
  });
});

test("Orders page reads the ribbon view status from the route and filters the order list", async () => {
  renderWithProviders(<OrdersPage />, { route: "/orders?status=ready", path: "/orders" });

  expect(await screen.findByText("Ready Job")).toBeInTheDocument();
  expect(screen.getByTestId("orders-page")).toHaveAttribute("data-active-order-view", "ready");
  expect(api.get).toHaveBeenCalledWith("/orders", { params: { status: "ready", limit: 100 } });
  expect(screen.queryByTestId("orders-filter-all")).not.toBeInTheDocument();
  expect(screen.queryByTestId("orders-filter-ready")).not.toBeInTheDocument();
  expect(screen.queryByTestId("orders-create-button")).not.toBeInTheDocument();
  expect(screen.queryByTestId("orders-content-heading")).not.toBeInTheDocument();
  expect(screen.getByTestId("orders-table-utility-row")).toContainElement(screen.getByTestId("orders-result-count"));
  expect(screen.queryByText("Everything in flight.")).not.toBeInTheDocument();
});

test("Orders page defaults to all orders and omits status from the API query", async () => {
  renderWithProviders(<OrdersPage />, { route: "/orders", path: "/orders" });

  expect(await screen.findByText("All Orders Job")).toBeInTheDocument();
  expect(screen.getByTestId("orders-page")).toHaveAttribute("data-active-order-view", "all");
  expect(screen.getByTestId("orders-result-count")).toHaveTextContent("1 order");
  expect(api.get).toHaveBeenCalledWith("/orders", { params: { status: undefined, limit: 100 } });
});

test("New Order route opens the create dialog without a duplicate page header button", async () => {
  renderWithProviders(<OrdersPage />, { route: "/orders?new=1", path: "/orders" });

  expect(await screen.findByRole("dialog")).toHaveTextContent("New order");
  await waitFor(() => expect(screen.queryByTestId("orders-create-button")).not.toBeInTheDocument());
});
