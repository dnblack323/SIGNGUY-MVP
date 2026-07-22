import React from "react";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";
import api from "@/lib/api";
import OrdersPage from "@/pages/OrdersPage";
import CustomersPage from "@/pages/CustomersPage";

let mockPermissions = [];

jest.mock("@/auth/AuthContext", () => ({
  __esModule: true,
  useAuth: () => ({
    hasPerm: (perm) => mockPermissions.includes(perm),
    user: { id: "u1", tenant_id: "t1", role: "owner" },
  }),
}));

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
  },
  extractError: () => "Request failed",
}));

const sourceFilters = {
  visible_sources: [
    { value: "manual", label: "Manual" },
    { value: "quote", label: "Quote" },
    { value: "webstore", label: "Webstore" },
    { value: "wrap_lab", label: "Wrap Lab" },
    { value: "legacy_unknown", label: "Legacy / Unknown" },
  ],
  reserved_hidden_sources: [
    { value: "email", label: "Email" },
    { value: "facebook", label: "Facebook" },
  ],
};

beforeEach(() => {
  mockPermissions = [
    "order:write",
    "customer:write",
    "quote:write",
    "pricing:read",
    "message:read",
    "task:read",
    "schedule:read",
    "document:write",
    "decision_room:write",
    "invoice:write",
  ];
  jest.clearAllMocks();
  api.get.mockImplementation((url, config = {}) => {
    if (url === "/orders/source-filters") return Promise.resolve({ data: sourceFilters });
    if (url === "/orders") {
      return Promise.resolve({
        data: {
          items: [
            {
              id: "order-1",
              number: 1001,
              job_name: "Lobby sign",
              status: "draft",
              order_source: config.params?.order_source || "manual",
              created_at: new Date().toISOString(),
            },
          ],
          total: 1,
        },
      });
    }
    if (url === "/customers") {
      return Promise.resolve({
        data: {
          items: [
            { id: "cust-1", name: "Ada Signs", company: "Ada Co", email: "ada@example.com", phone: "555", created_at: new Date().toISOString() },
          ],
          total: 1,
        },
      });
    }
    return Promise.resolve({ data: { items: [] } });
  });
});

test("Orders page uses shared ribbon and canonical source filters without reserved sources", async () => {
  const user = userEvent.setup();
  renderWithProviders(<OrdersPage />, { route: "/orders" });

  expect(await screen.findByTestId("orders-command-ribbon")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "New Order" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "More commands" })).toBeInTheDocument();
  expect(screen.queryByText("Email")).not.toBeInTheDocument();
  expect(screen.queryByText("Facebook")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "More commands" }));
  await user.click(await screen.findByTestId("ribbon-order-source-legacy_unknown"));

  await waitFor(() => {
    expect(api.get).toHaveBeenCalledWith(
      "/orders",
      expect.objectContaining({
        params: expect.objectContaining({ order_source: "legacy_unknown" }),
      }),
    );
  });
  expect((await screen.findAllByText("Legacy / Unknown")).length).toBeGreaterThan(0);
});

test("Orders ribbon opens the existing New Order dialog action", async () => {
  const user = userEvent.setup();
  renderWithProviders(<OrdersPage />, { route: "/orders" });

  await screen.findByTestId("orders-command-ribbon");
  await user.click(screen.getByRole("button", { name: "New Order" }));
  expect(await screen.findByText("Create an order directly (not from a quote).")).toBeInTheDocument();
});

test("Customers page uses shared ribbon while preserving search", async () => {
  const user = userEvent.setup();
  renderWithProviders(<CustomersPage />, { route: "/customers" });

  expect(await screen.findByTestId("customers-command-ribbon")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "New Customer" })).toBeInTheDocument();
  await user.type(screen.getByTestId("customers-search-input"), "Ada");

  await waitFor(() => {
    expect(api.get).toHaveBeenCalledWith(
      "/customers",
      expect.objectContaining({
        params: expect.objectContaining({ search: "Ada" }),
      }),
    );
  });

  await user.click(screen.getByRole("button", { name: "New Customer" }));
  expect(await screen.findByText("Add a customer to your shop.")).toBeInTheDocument();
  await user.keyboard("{Escape}");
  await waitFor(() => {
    expect(screen.queryByText("Add a customer to your shop.")).not.toBeInTheDocument();
  });
  await waitFor(() => {
    expect(screen.getByRole("button", { name: "New Customer" })).toHaveFocus();
  });
});
