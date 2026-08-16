import React from "react";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";

import CustomersPage from "@/pages/CustomersPage";
import CustomerDetailPage from "@/pages/CustomerDetailPage";
import api from "@/lib/api";
import { renderWithProviders } from "../test-utils";

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn(), patch: jest.fn(), delete: jest.fn() },
  extractError: (error) => error?.response?.data?.detail || error?.message || "Request failed",
}));

jest.mock("@/auth/AuthContext", () => ({
  useAuth: () => ({
    hasPerm: (permission) => ["customer:read", "customer:write", "schedule:manage"].includes(permission),
  }),
}));

jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock("@/components/ai/AIContextualActions", () => () => <div data-testid="ai-actions" />);
jest.mock("@/components/tasks/TaskHandoffButton", () => () => <button type="button">Task handoff</button>);

const customer = {
  id: "customer-1",
  name: "Rusty Lemon Boutique",
  company: "Rusty Lemon",
  customer_type: "business",
  lifecycle_status: "active",
  email: "rusty@example.com",
  phone: "724-555-0191",
  contacts: [{ name: "Sara Klein", email: "sara@example.com", phone: "724-555-0191", role: "primary", is_primary: true }],
  addresses: [{ label: "Shop", line1: "10 Main St", city: "Connellsville", state: "PA", postal_code: "15425", purposes: ["billing"], is_default: true }],
  archived: false,
  created_at: "2026-08-16T10:00:00+00:00",
};

beforeEach(() => {
  jest.clearAllMocks();
  api.get.mockImplementation((url) => {
    if (url === "/customers") {
      return Promise.resolve({ data: { items: [customer], total: 1 } });
    }
    if (url === "/customers/duplicates") {
      return Promise.resolve({
        data: {
          items: [
            {
              customer: { ...customer, id: "customer-2", name: "Rusty Lemon", company: "Rusty Lemon Boutique" },
              match_reasons: ["Matching phone", "Matching customer or company name"],
            },
          ],
        },
      });
    }
    if (url === "/customers/customer-1") {
      return Promise.resolve({ data: customer });
    }
    if (url === "/customers/customer-1/related") {
      return Promise.resolve({
        data: {
          quotes: [{ id: "quote-1", number: 101, job_name: "Window decals", status: "sent", total_cents: 42000 }],
          orders: [{ id: "order-1", number: 9101, job_name: "Trailer graphics", status: "confirmed" }],
          work_orders: [],
          invoices: [],
          payments: [],
          emails: [],
          documents: [{ id: "doc-1", title: "Logo file", category: "artwork" }],
          proofs: [{ id: "proof-1", title: "Window proof", status: "sent" }],
          files: [{ id: "file-1", original_filename: "proof.png", visibility: "internal" }],
          communication_threads: [{ id: "thread-1", title: "Order notes" }],
          internal_notes: [],
          schedule_events: [{ id: "event-1", title: "Install", status: "scheduled", start_at: "2026-08-20T13:00:00+00:00" }],
          approvals: [{ id: "approval-1", parent_type: "quote_revision", action: "approve" }],
          decision_rooms: [{ id: "room-1", title: "Approval room", status: "published" }],
          portal_identities: [{ id: "portal-1", email: "customer@example.com", status: "active" }],
          webstores: [{ id: "webstore-1", name: "Rusty Lemon Store", status: "active" }],
          tasks: [{ id: "task-1", title: "Follow up", status: "open" }],
        },
      });
    }
    if (url === "/audit") {
      return Promise.resolve({ data: { items: [] } });
    }
    return Promise.resolve({ data: {} });
  });
  api.post.mockResolvedValue({ data: {} });
  api.patch.mockResolvedValue({ data: customer });
});

test("Customers list filters archived records and exposes duplicate merge review", async () => {
  const user = userEvent.setup();
  renderWithProviders(<CustomersPage />, { route: "/customers" });

  expect(await screen.findByText("Rusty Lemon Boutique")).toBeInTheDocument();
  expect(api.get).toHaveBeenCalledWith("/customers", { params: { search: undefined, status: "active", limit: 100 } });

  await user.click(screen.getByTestId("customer-duplicates-customer-1"));
  expect(await screen.findByText("Matching phone")).toBeInTheDocument();
  await user.click(screen.getByTestId("customer-merge-customer-2"));

  await waitFor(() => {
    expect(api.post).toHaveBeenCalledWith("/customers/merge", {
      source_customer_id: "customer-2",
      surviving_customer_id: "customer-1",
      confirmation: "MERGE",
    });
  });
});

test("Customer detail edits contacts and shows expanded related records", async () => {
  const user = userEvent.setup();
  renderWithProviders(<CustomerDetailPage />, { route: "/customers/customer-1", path: "/customers/:id" });

  expect(await screen.findByDisplayValue("Rusty Lemon Boutique")).toBeInTheDocument();
  await user.click(screen.getByTestId("detail-tab-contacts"));
  await user.clear(screen.getByTestId("customer-contact-name-0"));
  await user.type(screen.getByTestId("customer-contact-name-0"), "Sara Klein Primary");
  await user.click(screen.getByTestId("customer-save-button"));

  await waitFor(() => {
    expect(api.patch).toHaveBeenCalledWith("/customers/customer-1", expect.objectContaining({
      contacts: [expect.objectContaining({ name: "Sara Klein Primary", is_primary: true })],
    }));
  });

  await user.click(screen.getByTestId("detail-tab-requests"));
  expect(await screen.findByText("Install")).toBeInTheDocument();
  expect(screen.getByText("Approval room")).toBeInTheDocument();
  expect(screen.getByText("quote revision")).toBeInTheDocument();

  await user.click(screen.getByTestId("detail-tab-files-forms"));
  expect(screen.getByText("Logo file")).toBeInTheDocument();
  expect(screen.getByText("Window proof")).toBeInTheDocument();
  expect(screen.getByText("proof.png")).toBeInTheDocument();

  await user.click(screen.getByTestId("detail-tab-portal"));
  expect(screen.getByText("customer@example.com")).toBeInTheDocument();
  expect(screen.getByText("Rusty Lemon Store")).toBeInTheDocument();
});
