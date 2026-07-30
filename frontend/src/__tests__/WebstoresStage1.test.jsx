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
  createWebstoreAssignment,
  createWebstoreOwner,
  createProductFromTemplate,
  getWebstoreQuestionnaire,
  getWebstoreQuestionnaireResponse,
  generateLaunchPacket,
  getLaunchReadiness,
  getWebstoreSetupProgress,
  getWebstore,
  getWebstoreReports,
  getWebstoreBranding,
  listWebstoreAssignments,
  listWebstoreSetupFiles,
  listWebstores,
  listProductTemplates,
  listWebstoreArtwork,
  listWebstoreMockups,
  applyWebstoreAnswers,
  previewWebstoreAnswerApplication,
  resendWebstoreInvitation,
  revokeWebstoreAssignment,
  reverseWebstoreAnswerApplication,
  sendLaunchPacket,
  setWebstoreStatus,
  uploadWebstoreSetupFile,
  updateProductTemplate,
  updateWebstore,
  saveWebstoreBrandingDraft,
  requestWebstoreBrandingReview,
  publishWebstoreBranding,
  updateWebstoreProduct,
  archiveProductTemplate,
  archiveWebstoreProduct,
  archiveWebstoreProductCategory,
  restoreProductTemplate,
  restoreWebstoreProduct,
  restoreWebstoreProductCategory,
  createProductTemplate,
  createWebstoreProductCategory,
  listWebstoreProductCategories,
  updateWebstoreProductCategory,
} from "@/lib/webstores";
import { useAuth } from "@/auth/AuthContext";

jest.mock("axios", () => ({
  get: jest.fn(),
  post: jest.fn(),
}));

jest.mock("@/lib/webstores", () => ({
  createWebstore: jest.fn(),
  createWebstoreAssignment: jest.fn(),
  createWebstoreOwner: jest.fn(),
  createProductFromTemplate: jest.fn(),
  getWebstoreQuestionnaire: jest.fn(),
  getWebstoreQuestionnaireResponse: jest.fn(),
  generateLaunchPacket: jest.fn(),
  getLaunchReadiness: jest.fn(),
  getWebstoreSetupProgress: jest.fn(),
  getWebstore: jest.fn(),
  getWebstoreReports: jest.fn(),
  getWebstoreBranding: jest.fn(),
  listWebstoreAssignments: jest.fn(),
  listWebstoreSetupFiles: jest.fn(),
  listWebstores: jest.fn(),
  listProductTemplates: jest.fn(),
  listWebstoreArtwork: jest.fn(),
  listWebstoreMockups: jest.fn(),
  applyWebstoreAnswers: jest.fn(),
  previewWebstoreAnswerApplication: jest.fn(),
  resendWebstoreInvitation: jest.fn(),
  revokeWebstoreAssignment: jest.fn(),
  reverseWebstoreAnswerApplication: jest.fn(),
  sendLaunchPacket: jest.fn(),
  setWebstoreStatus: jest.fn(),
  uploadWebstoreSetupFile: jest.fn(),
  updateProductTemplate: jest.fn(),
  updateWebstore: jest.fn(),
  saveWebstoreBrandingDraft: jest.fn(),
  requestWebstoreBrandingReview: jest.fn(),
  publishWebstoreBranding: jest.fn(),
  updateWebstoreProduct: jest.fn(),
  archiveProductTemplate: jest.fn(),
  archiveWebstoreProduct: jest.fn(),
  archiveWebstoreProductCategory: jest.fn(),
  restoreProductTemplate: jest.fn(),
  restoreWebstoreProduct: jest.fn(),
  restoreWebstoreProductCategory: jest.fn(),
  createProductTemplate: jest.fn(),
  createWebstoreProductCategory: jest.fn(),
  listWebstoreProductCategories: jest.fn(),
  updateWebstoreProductCategory: jest.fn(),
}));

jest.mock("@/auth/AuthContext", () => ({
  useAuth: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {},
  extractError: (error) => error?.response?.data?.detail || error?.message || "Request failed",
}));

jest.mock("@/portal/portalApi", () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn(), patch: jest.fn() },
  portalExtractError: (error) => error?.response?.data?.detail || error?.message || "Portal request failed",
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
  createWebstoreAssignment.mockResolvedValue({});
  createWebstoreOwner.mockResolvedValue({ id: "owner-new" });
  createProductFromTemplate.mockResolvedValue({});
  getWebstoreQuestionnaire.mockResolvedValue({ templates: [] });
  getWebstoreQuestionnaireResponse.mockResolvedValue({ submission: null });
  generateLaunchPacket.mockResolvedValue({});
  getWebstoreSetupProgress.mockResolvedValue({ setup_state: "not_started", steps: [] });
  listWebstoreAssignments.mockResolvedValue([]);
  listWebstoreSetupFiles.mockResolvedValue([]);
  applyWebstoreAnswers.mockResolvedValue({});
  previewWebstoreAnswerApplication.mockResolvedValue({ proposed_changes: [], rejected_changes: [] });
  resendWebstoreInvitation.mockResolvedValue({});
  revokeWebstoreAssignment.mockResolvedValue({});
  reverseWebstoreAnswerApplication.mockResolvedValue({});
  uploadWebstoreSetupFile.mockResolvedValue({});
  updateProductTemplate.mockResolvedValue({});
  sendLaunchPacket.mockResolvedValue({});
  setWebstoreStatus.mockResolvedValue({});
  updateWebstore.mockResolvedValue({});
  updateWebstoreProduct.mockResolvedValue({});
  archiveProductTemplate.mockResolvedValue({});
  archiveWebstoreProduct.mockResolvedValue({});
  archiveWebstoreProductCategory.mockResolvedValue({});
  restoreProductTemplate.mockResolvedValue({});
  restoreWebstoreProduct.mockResolvedValue({});
  restoreWebstoreProductCategory.mockResolvedValue({});
  createProductTemplate.mockResolvedValue({});
  createWebstoreProductCategory.mockResolvedValue({});
  listWebstoreProductCategories.mockResolvedValue({ items: [], legacy_categories: [] });
  listWebstoreArtwork.mockResolvedValue([]);
  listWebstoreMockups.mockResolvedValue([]);
  updateWebstoreProductCategory.mockResolvedValue({});
  getWebstoreBranding.mockResolvedValue({
    webstore: { id: "ws-1", name: "Team Store", store_type: "general" },
    branding: {
      status: "draft",
      draft: {
        brand_basics: { display_name: "Team Store" },
        colors_fonts: {},
        header: { show_header: true, display_mode: "name" },
        hero: { show_hero: true },
        store_information: { show_section: true },
        store_type_content: { general_welcome: "Welcome shoppers." },
        catalog_introduction: { show_catalog_area: true },
        footer: { show_footer: true },
      },
      validation: { errors: [], warnings: [] },
    },
    permissions: { can_save_draft: true, can_request_review: true, can_publish: true, can_control_whole_sections: true },
    history: [],
    activity: [],
  });
  saveWebstoreBrandingDraft.mockResolvedValue({});
  requestWebstoreBrandingReview.mockResolvedValue({});
  publishWebstoreBranding.mockResolvedValue({});
  listWebstores.mockResolvedValue({ items: [] });
  listProductTemplates.mockResolvedValue([]);
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
    target_launch_at: undefined,
    deadline_at: undefined,
    manager_emails: [],
    additional_owner_emails: [],
    idempotency_key: "webstore-create-owner@example.com-employee store",
    send_owner_invitation: true,
  }));
});

test("webstore detail shows setup intake, assignments, files, and answer preview", async () => {
  getWebstore.mockResolvedValue({
    webstore: {
      id: "ws-2",
      name: "Setup Store",
      slug: "setup-store",
      public_slug: "setup-public",
      public_url: "/p/webstores/setup-public",
      store_type: "event",
      status: "draft",
      setup_state: "staff_review",
      terms_fee_acknowledged: false,
    },
    launch_packets: [],
    products: [],
  });
  getLaunchReadiness.mockResolvedValue({ ready: false, checks: { payment_ready: false }, payment_unavailable_reason: "Real verified provider checkout is not connected yet." });
  getWebstoreReports.mockResolvedValue({ order_count: 0, gross_sales_cents: 0, ledger_totals_cents: {} });
  getWebstoreSetupProgress.mockResolvedValue({
    setup_state: "staff_review",
    steps: [{ key: "questionnaire", label: "Owner intake questionnaire", status: "review" }],
  });
  listWebstoreAssignments.mockResolvedValue([
    { id: "assign-1", email: "owner@example.com", role: "owner", status: "active", is_primary_owner: true },
    { id: "assign-2", email: "manager@example.com", role: "manager", status: "invited", is_primary_owner: false },
  ]);
  listWebstoreSetupFiles.mockResolvedValue([{ id: "file-1", file_name: "logo.png", category: "logo", version: 1, private_download_only: false }]);
  getWebstoreQuestionnaire.mockResolvedValue({ templates: [{ id: "tpl-1", sections: [] }] });
  getWebstoreQuestionnaireResponse.mockResolvedValue({
    submission: { id: "sub-1", status: "submitted", submitted_snapshot: { answers: { store_name: "New Name" } } },
  });
  previewWebstoreAnswerApplication.mockResolvedValue({
    proposed_changes: [{ answer_key: "store_name", target: "name", label: "Store name", from: "Setup Store", to: "New Name" }],
    rejected_changes: [],
  });

  const user = userEvent.setup();
  renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-2", path: "/webstores/:id" });

  expect(await screen.findByText("Setup Store")).toBeInTheDocument();
  expect(screen.getByTestId("webstore-setup-state")).toHaveTextContent("staff_review");
  expect(await screen.findByText("owner@example.com")).toBeInTheDocument();
  expect(await screen.findByTestId("webstore-assignment-resend-assign-2")).toBeInTheDocument();
  expect(await screen.findByTestId("webstore-assignment-revoke-assign-2")).toBeInTheDocument();
  expect(await screen.findByText("logo.png")).toBeInTheDocument();
  await user.click(screen.getByTestId("webstore-select-answer-store_name"));
  await user.click(screen.getByRole("button", { name: /Preview apply/ }));
  await waitFor(() => expect(previewWebstoreAnswerApplication).toHaveBeenCalledWith("ws-2", expect.objectContaining({
    selected_answer_keys: ["store_name"],
    proposed_values: expect.objectContaining({ store_name: "New Name" }),
  })));
  expect(await screen.findByTestId("webstore-answer-preview")).toHaveTextContent("Store name");
});
