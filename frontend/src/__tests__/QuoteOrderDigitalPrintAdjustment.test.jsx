import React from "react";
import { fireEvent, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import userEvent from "@testing-library/user-event";
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
  const Mock = ({ open, useHandoff, readiness }) => (
    open ? (
      <div data-testid="generate-wo-dialog">
        {useHandoff ? "Server readiness gate enabled" : "Direct work order generation"}
        {readiness && !readiness.ready ? <div data-testid="gen-wo-readiness-override">Order is not ready for production.</div> : null}
      </div>
    ) : null
  );
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
          work_orders: [],
          approvals: [{ id: "approval-1", action: "approve", status: "current", created_at: "2026-08-16T10:00:00+00:00" }],
          decision_rooms: [{ id: "room-1", title: "Poster decision room", status: "closed", created_at: "2026-08-16T10:05:00+00:00" }],
          proofs: [{ id: "proof-1", title: "Poster proof", status: "approved", created_at: "2026-08-16T10:10:00+00:00" }],
          linked_assets: {
            attachments: [{ id: "att-1", file_id: "file-1" }],
            files: [{ id: "file-1", filename: "poster-artwork.pdf" }],
            documents: [{ id: "doc-1", title: "Signed terms" }],
          },
          financial_summary: {
            available: true,
            restricted: false,
            invoices: [{ id: "invoice-1", number: 301, title: "Poster invoice", status: "sent", document_status: "issued", financial_status: "partial", total_cents: 3800, amount_paid_cents: 1000, balance_due_cents: 2800 }],
            payments: [],
            total_invoiced_cents: 3800,
            amount_paid_cents: 1000,
            amount_refunded_cents: 0,
            balance_due_cents: 2800,
          },
          readiness: {
            ready: true,
            status: "ready",
            blockers: [],
            warnings: [],
            summary: { item_count: 1, production_required_count: 1, approval_count: 1, decision_room_count: 1, proof_count: 1, file_count: 1, document_count: 1 },
            evaluated_at: "2026-08-16T10:15:00+00:00",
          },
          permissions: { financials_visible: true },
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

test("Order detail shows readiness, finance, approval, and linked asset coverage", async () => {
  const user = userEvent.setup();
  renderWithProviders(<OrderDetailPage />, { route: "/orders/order-1", path: "/orders/:id" });

  expect(await screen.findByTestId("order-detail-page")).toBeInTheDocument();
  expect(screen.getAllByTestId("order-readiness-status")[0]).toHaveTextContent("Ready");
  expect(screen.getAllByTestId("order-readiness-clear")[0]).toHaveTextContent("No production blockers");
  await user.click(screen.getByTestId("detail-tab-financial"));
  expect(await screen.findByTestId("order-financial-summary")).toHaveTextContent("Invoice and deposit status");
  expect(screen.getByTestId("order-invoice-row-invoice-1")).toHaveTextContent("I-301");
  await user.click(screen.getByTestId("detail-tab-files-artwork"));
  expect(await screen.findByTestId("order-linked-assets")).toHaveTextContent("poster-artwork.pdf");
  expect(screen.getByTestId("order-linked-assets")).toHaveTextContent("Signed terms");
  await user.click(screen.getByTestId("detail-tab-documents-approvals"));
  expect(await screen.findByTestId("order-approval-decision-summary")).toHaveTextContent("Poster decision room");
  await user.click(screen.getByTestId("detail-tab-activity"));
  expect((await screen.findAllByTestId("order-lifecycle-event")).length).toBeGreaterThan(0);
});

test("Order detail launches production handoff with readiness blockers preserved", async () => {
  api.get.mockImplementation((url) => {
    if (url === "/orders/order-1") {
      return Promise.resolve({
        data: {
          order: { id: "order-1", number: 202, customer_id: "customer-1", job_name: "Poster order", status: "confirmed" },
          items: [digitalPrintLine],
          totals: totalsWithAdjustment,
          pricing_summary: {},
          work_orders: [],
          approvals: [],
          decision_rooms: [],
          proofs: [],
          linked_assets: { attachments: [], files: [], documents: [] },
          financial_summary: { available: true, restricted: false, invoices: [], payments: [], total_invoiced_cents: 0, amount_paid_cents: 0, amount_refunded_cents: 0, balance_due_cents: 0 },
          readiness: {
            ready: false,
            status: "not_ready",
            blockers: [{ code: "missing_proof", label: "Proof approval is required but no active proof exists.", source: "proof", owner: "staff", required_action: "Create and send a proof for approval." }],
            warnings: [],
            summary: { item_count: 1, production_required_count: 1, approval_count: 0 },
            evaluated_at: "2026-08-16T10:15:00+00:00",
          },
          permissions: { financials_visible: true },
        },
      });
    }
    if (url === "/customers/customer-1") return Promise.resolve({ data: { id: "customer-1", name: "Donnell Black" } });
    if (url === "/audit") return Promise.resolve({ data: { items: [] } });
    if (url === "/work-orders") return Promise.resolve({ data: { items: [] } });
    return Promise.resolve({ data: {} });
  });

  renderWithProviders(<OrderDetailPage />, { route: "/orders/order-1", path: "/orders/:id" });

  expect(await screen.findByTestId("order-detail-page")).toBeInTheDocument();
  expect(screen.getAllByTestId("order-readiness-status")[0]).toHaveTextContent("Not ready");
  expect(screen.getAllByTestId("order-readiness-blockers")[0]).toHaveTextContent("Proof approval is required");
  fireEvent.click(screen.getAllByTestId("order-readiness-handoff-button")[0]);
  expect(screen.getByTestId("generate-wo-dialog")).toHaveTextContent("Server readiness gate enabled");
  expect(screen.getByTestId("gen-wo-readiness-override")).toHaveTextContent("Order is not ready for production");
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
