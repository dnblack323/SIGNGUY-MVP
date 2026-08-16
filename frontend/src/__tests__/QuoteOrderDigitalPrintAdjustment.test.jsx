import React from "react";
import { screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { renderWithProviders } from "../test-utils";
import QuoteDetailPage from "@/pages/QuoteDetailPage";
import OrderDetailPage from "@/pages/OrderDetailPage";
import PublicApp from "@/public/PublicApp";
import api from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import axios from "axios";

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn(), patch: jest.fn(), delete: jest.fn() },
  extractError: (error) => error?.response?.data?.detail || error?.message || "Request failed",
}));
jest.mock("axios", () => {
  const mock = {
    get: jest.fn(),
    post: jest.fn(),
    interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } },
  };
  mock.create = jest.fn(() => mock);
  return { __esModule: true, default: mock, ...mock };
});

jest.mock("@/auth/AuthContext", () => ({ useAuth: jest.fn() }));
jest.mock("@/context/WorkspaceContext", () => ({ useWorkspaceDirty: jest.fn() }));
jest.mock("@/components/commerce/LineItemDialog", () => () => null);
jest.mock("@/components/ai/AIContextualActions", () => () => null);
jest.mock("@/components/email/ComposeEmailDialog", () => () => null);
jest.mock("@/components/audit/AuditTimeline", () => ({ AuditTimeline: () => null }));
jest.mock("@/components/production/ProductionTimeline", () => () => null);
jest.mock("@/components/proofs/ProofsPanel", () => () => null);
jest.mock("@/components/tasks/TaskHandoffButton", () => () => null);
jest.mock("@/components/work-orders/GenerateWorkOrderDialog", () => {
  const Mock = () => null;
  return { __esModule: true, default: Mock, RegenerateDialog: Mock };
});

const totalsWithAdjustment = {
  subtotal_cents: 4000,
  discount_cents: 500,
  tax_cents: 300,
  total_cents: 3800,
  digital_print_order_minimum_adjustment_cents: 2000,
  digital_print_minimum: {
    category: "digital_print",
    eligible_subtotal_cents: 2000,
    order_minimum_cents: 4000,
    order_minimum_adjustment_cents: 2000,
    adjustment_applied: true,
  },
};

const digitalPrintLine = {
  id: "line-1",
  description: "Poster",
  category: "digital_print",
  quantity: 1,
  unit_price_cents: 2000,
  line_total_cents: 2000,
};

beforeEach(() => {
  jest.clearAllMocks();
  useAuth.mockReturnValue({ hasPerm: () => true });
  api.get.mockImplementation((url) => {
    if (url === "/quotes/quote-1") {
      return Promise.resolve({
        data: {
          quote: { id: "quote-1", number: 101, customer_id: "customer-1", job_name: "Poster quote", status: "draft", total_cents: 3800 },
          line_items: [digitalPrintLine],
          totals: totalsWithAdjustment,
          pricing_summary: {},
        },
      });
    }
    if (url === "/orders/order-1") {
      return Promise.resolve({
        data: {
          order: { id: "order-1", number: 202, customer_id: "customer-1", job_name: "Poster order", status: "draft" },
          items: [digitalPrintLine],
          totals: totalsWithAdjustment,
          pricing_summary: {},
        },
      });
    }
    if (url === "/customers/customer-1") {
      return Promise.resolve({ data: { id: "customer-1", name: "Donnell Black", email: "owner@example.com" } });
    }
    if (url === "/audit") return Promise.resolve({ data: { items: [] } });
    if (url === "/quotes/quote-1/revisions") return Promise.resolve({ data: { items: [], current_revision: 1 } });
    if (url === "/quotes/quote-1/public-preview") {
      return Promise.resolve({ data: { snapshot: { published_revision: 1 }, totals: totalsWithAdjustment } });
    }
    if (url === "/quotes/quote-1/share-tokens") return Promise.resolve({ data: { items: [] } });
    if (url === "/quotes/quote-1/linked-assets") return Promise.resolve({ data: { proofs: [], files: [], documents: [] } });
    if (url === "/quotes/quote-1/timeline") return Promise.resolve({ data: { items: [] } });
    if (url === "/work-orders") return Promise.resolve({ data: { items: [] } });
    return Promise.resolve({ data: {} });
  });
});

test("Quote detail shows one backend-evidence Digital Print order minimum adjustment row", async () => {
  renderWithProviders(<QuoteDetailPage />, { route: "/quotes/quote-1", path: "/quotes/:id" });

  expect(await screen.findByTestId("quote-detail-page")).toBeInTheDocument();
  expect(screen.getByTestId("digital-print-order-minimum-adjustment")).toHaveTextContent("$20.00");
  expect(screen.getByText("Digital Print order minimum adjustment")).toBeInTheDocument();
  expect(screen.getByTestId("quote-derived-total")).toHaveTextContent("$38.00");
});

test("Order detail shows the backend-evidence Digital Print adjustment in item and summary totals", async () => {
  renderWithProviders(<OrderDetailPage />, { route: "/orders/order-1", path: "/orders/:id" });

  expect(await screen.findByTestId("order-detail-page")).toBeInTheDocument();
  expect(screen.getByTestId("digital-print-order-minimum-adjustment")).toHaveTextContent("$20.00");
  expect(screen.getByTestId("order-summary-digital-print-order-minimum-adjustment")).toHaveTextContent("$20.00");
  expect(screen.getByTestId("order-derived-total")).toHaveTextContent("$38.00");
});

test("Quote detail links into Approval Center with preserved quote context", async () => {
  renderWithProviders(<QuoteDetailPage />, { route: "/quotes/quote-1", path: "/quotes/:id" });

  expect(await screen.findByTestId("quote-detail-page")).toBeInTheDocument();
  expect(screen.getByTestId("approval-history-quote")).toBeInTheDocument();
  expect(screen.getByTestId("quote-approval-work-button")).toHaveAttribute("href", expect.stringContaining("/approval-center?new=1"));
  expect(screen.getByTestId("quote-approval-work-button")).toHaveAttribute("href", expect.stringContaining("target_type=quote"));
  expect(screen.getByTestId("quote-approval-work-button")).toHaveAttribute("href", expect.stringContaining("target_id=quote-1"));
});

test("Quote detail exposes quote completion controls without fake delivery claims", async () => {
  renderWithProviders(<QuoteDetailPage />, { route: "/quotes/quote-1", path: "/quotes/:id" });

  expect(await screen.findByTestId("quote-detail-page")).toBeInTheDocument();
  expect(screen.getByTestId("quote-share-panel")).toHaveTextContent("Email or SMS delivery is not marked successful");
  expect(screen.getByTestId("quote-public-preview-summary")).toHaveTextContent("Published revision");
  expect(screen.getByTestId("quote-public-preview-link")).toHaveAttribute("href", "/api/quotes/quote-1/artifact");
  expect(screen.getByTestId("quote-download-link")).toHaveAttribute("href", "/api/quotes/quote-1/download");
  expect(screen.getByTestId("quote-decision-room-create-link")).toHaveAttribute("href", expect.stringContaining("target_type=quote"));
});

test("Order detail links into Approval Center with preserved order context", async () => {
  renderWithProviders(<OrderDetailPage />, { route: "/orders/order-1", path: "/orders/:id" });

  expect(await screen.findByTestId("order-detail-page")).toBeInTheDocument();
  expect(screen.getByTestId("order-approval-work-button")).toHaveAttribute("href", expect.stringContaining("/approval-center?new=1"));
  expect(screen.getByTestId("order-approval-work-button")).toHaveAttribute("href", expect.stringContaining("target_type=order"));
  expect(screen.getByTestId("order-approval-work-button")).toHaveAttribute("href", expect.stringContaining("target_id=order-1"));
});

test("Digital Print adjustment row is omitted when backend evidence is zero or absent", async () => {
  api.get.mockImplementation((url) => {
    if (url === "/quotes/quote-1") {
      return Promise.resolve({
        data: {
          quote: { id: "quote-1", number: 101, customer_id: "customer-1", job_name: "Poster quote", status: "draft", total_cents: 2000 },
          line_items: [digitalPrintLine],
          totals: { ...totalsWithAdjustment, total_cents: 2000, digital_print_order_minimum_adjustment_cents: 0, digital_print_minimum: { order_minimum_adjustment_cents: 0 } },
          pricing_summary: {},
        },
      });
    }
    if (url === "/customers/customer-1") return Promise.resolve({ data: { id: "customer-1", name: "Donnell Black" } });
    if (url === "/audit") return Promise.resolve({ data: { items: [] } });
    if (url === "/quotes/quote-1/revisions") return Promise.resolve({ data: { items: [], current_revision: 1 } });
    return Promise.resolve({ data: {} });
  });

  renderWithProviders(<QuoteDetailPage />, { route: "/quotes/quote-1", path: "/quotes/:id" });

  expect(await screen.findByTestId("quote-detail-page")).toBeInTheDocument();
  expect(screen.queryByTestId("digital-print-order-minimum-adjustment")).not.toBeInTheDocument();
  expect(screen.queryByText("Digital Print order minimum adjustment")).not.toBeInTheDocument();
});

test("Public quote preview renders the published customer-safe quote and response controls", async () => {
  axios.get.mockResolvedValue({
    data: {
      quote: {
        id: "quote-1",
        number: 101,
        job_name: "Poster quote",
        revision_number: 2,
        status: "viewed",
        total_cents: 3800,
        notes_customer: "Customer-facing note",
      },
      line_items: [digitalPrintLine],
      totals: totalsWithAdjustment,
      snapshot: { published_revision: 2 },
    },
  });
  axios.post.mockResolvedValue({ data: { quote: { status: "approved" }, approval: { id: "approval-1" } } });

  renderWithProviders(<PublicApp />, { route: "/quotes/quote-1?t=public-token" });

  expect(await screen.findByTestId("public-quote-page")).toBeInTheDocument();
  expect(screen.getByText("Quote Q-101")).toBeInTheDocument();
  expect(screen.getByText("Customer-facing note")).toBeInTheDocument();
  expect(screen.getByTestId("public-quote-total")).toHaveTextContent("$38.00");
  expect(screen.getByTestId("public-quote-approve")).toBeEnabled();
  expect(screen.getByTestId("public-quote-decline")).toBeDisabled();
});
