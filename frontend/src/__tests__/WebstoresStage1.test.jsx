import "@testing-library/jest-dom";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";
import PublicWebstorePage from "@/pages/PublicWebstorePage";
import WebstoreDetailPage from "@/pages/WebstoreDetailPage";
import WebstoresPage from "@/pages/WebstoresPage";
import axios from "axios";
import {
  createWebstore,
  createWebstoreOwner,
  createProductFromTemplate,
  generateLaunchPacket,
  getLaunchReadiness,
  getWebstore,
  getWebstoreReports,
  listWebstores,
  listProductTemplates,
  sendLaunchPacket,
  setWebstoreStatus,
  updateWebstore,
} from "@/lib/webstores";
import { useAuth } from "@/auth/AuthContext";

jest.mock("axios", () => ({
  get: jest.fn(),
  post: jest.fn(),
}));

jest.mock("@/lib/webstores", () => ({
  createWebstore: jest.fn(),
  createWebstoreOwner: jest.fn(),
  createProductFromTemplate: jest.fn(),
  generateLaunchPacket: jest.fn(),
  getLaunchReadiness: jest.fn(),
  getWebstore: jest.fn(),
  getWebstoreReports: jest.fn(),
  listWebstores: jest.fn(),
  listProductTemplates: jest.fn(),
  sendLaunchPacket: jest.fn(),
  setWebstoreStatus: jest.fn(),
  updateWebstore: jest.fn(),
}));

jest.mock("@/auth/AuthContext", () => ({
  useAuth: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {},
  extractError: (error) => error?.response?.data?.detail || error?.message || "Request failed",
}));

jest.mock("@/components/ai/AIContextualActions", () => () => <div data-testid="ai-actions" />);

jest.mock("sonner", () => ({
  toast: {
    error: jest.fn(),
    success: jest.fn(),
  },
}));

beforeEach(() => {
  jest.clearAllMocks();
  global.crypto = { randomUUID: jest.fn(() => "intent-key-1") };
  window.HTMLElement.prototype.hasPointerCapture = window.HTMLElement.prototype.hasPointerCapture || (() => false);
  window.HTMLElement.prototype.setPointerCapture = window.HTMLElement.prototype.setPointerCapture || (() => {});
  window.HTMLElement.prototype.releasePointerCapture = window.HTMLElement.prototype.releasePointerCapture || (() => {});
  window.HTMLElement.prototype.scrollIntoView = window.HTMLElement.prototype.scrollIntoView || (() => {});
  useAuth.mockReturnValue({ hasPerm: () => true });
  createWebstore.mockResolvedValue({ id: "ws-new" });
  createWebstoreOwner.mockResolvedValue({ id: "owner-new" });
  createProductFromTemplate.mockResolvedValue({});
  generateLaunchPacket.mockResolvedValue({});
  sendLaunchPacket.mockResolvedValue({});
  setWebstoreStatus.mockResolvedValue({});
  updateWebstore.mockResolvedValue({});
  listWebstores.mockResolvedValue({ items: [] });
});

test("public storefront saves a purchase intent and keeps checkout unavailable", async () => {
  const user = userEvent.setup();
  axios.get.mockResolvedValue({
    data: {
      webstore: {
        id: "ws-1",
        name: "Team Store",
        description: "",
        checkout_enabled: false,
        checkout_unavailable_reason: "Real Webstore checkout is not connected yet.",
      },
      products: [{ id: "prod-1", name: "Team Shirt", product_type: "shirt", selling_price_cents: 2500 }],
    },
  });
  axios.post.mockResolvedValue({
    data: {
      purchase_intent: { id: "pi-1", status: "pending_payment", product_subtotal_cents: 5000, total_cents: 5000 },
      checkout_available: false,
    },
  });

  renderWithProviders(<PublicWebstorePage />, { route: "/p/webstores/team-store", path: "/p/webstores/:slug" });

  expect(await screen.findByText("Team Store")).toBeInTheDocument();
  expect(screen.getByTestId("webstore-checkout-disabled")).toHaveTextContent("Real Webstore checkout is not connected yet.");
  fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "2" } });
  const buyerFields = screen.getAllByRole("textbox");
  await user.type(buyerFields[0], "Casey Buyer");
  await user.type(buyerFields[1], "casey@example.com");
  await user.click(screen.getByRole("button", { name: /Save purchase request/ }));

  await waitFor(() => expect(axios.post).toHaveBeenCalledWith(
    "/api/public/webstores/team-store/purchase-intents",
    {
      buyer_name: "Casey Buyer",
      buyer_email: "casey@example.com",
      buyer_phone: "",
      line_items: [{ product_id: "prod-1", quantity: 2 }],
      idempotency_key: "intent-key-1",
    },
  ));
  expect(await screen.findByText("Purchase request saved")).toBeInTheDocument();
  expect(screen.getByText(/Checkout is not connected yet/)).toBeInTheDocument();
});

test("webstore detail exposes computed payment readiness without a manual ready toggle", async () => {
  getWebstore.mockResolvedValue({
    webstore: {
      id: "ws-1",
      name: "Team Store",
      slug: "team-store",
      public_slug: "shop-team-store",
      public_url: "/p/webstores/shop-team-store",
      store_type: "general",
      status: "draft",
      terms_fee_acknowledged: false,
      stripe_payment_ready: true,
    },
    launch_packets: [],
    products: [],
  });
  getLaunchReadiness.mockResolvedValue({
    ready: false,
    checks: { payment_ready: false, active_public_products_with_prices: false },
    payment_unavailable_reason: "Real verified provider checkout is not connected yet.",
  });
  getWebstoreReports.mockResolvedValue({ order_count: 0, gross_sales_cents: 0, ledger_totals_cents: {} });
  listProductTemplates.mockResolvedValue([]);

  renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-1", path: "/webstores/:id" });

  expect(await screen.findByText("Team Store")).toBeInTheDocument();
  expect(screen.getByTestId("webstore-payment-readiness")).toHaveTextContent("Payment readiness: Not connected");
  expect(screen.queryByLabelText("Payment boundary ready")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Public/ })).toHaveAttribute("href", "/p/webstores/shop-team-store");
});

test("authenticated Webstores creation supports the six official store types", async () => {
  const user = userEvent.setup();
  renderWithProviders(<WebstoresPage />);

  expect(await screen.findByText("New Webstore")).toBeInTheDocument();
  await user.type(screen.getByTestId("webstore-owner-name"), "Owner Name");
  await user.type(screen.getByTestId("webstore-owner-email"), "owner@example.com");
  await user.type(screen.getByTestId("webstore-name"), "Employee Store");
  await user.click(screen.getByTestId("webstore-type"));
  await user.click(await screen.findByText("Employee"));
  await user.click(screen.getByTestId("webstore-create"));

  await waitFor(() => expect(createWebstore).toHaveBeenCalledWith({
    owner_id: "owner-new",
    name: "Employee Store",
    slug: undefined,
    store_type: "employee",
  }));
});
