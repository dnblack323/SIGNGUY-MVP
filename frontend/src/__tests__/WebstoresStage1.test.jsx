import "@testing-library/jest-dom";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation } from "react-router-dom";
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
  getWebstorePaymentProviderStatus,
  getWebstoreSetupProgress,
  getWebstore,
  getWebstoreReports,
  getWebstoreOrders,
  handoffWebstoreOrderToProduction,
  getWebstoreBranding,
  listWebstoreAssignments,
  listWebstoreSetupFiles,
  listWebstores,
  listProductTemplates,
  listWebstoreArtwork,
  listWebstoreMockups,
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
  requestWebstorePaymentProviderAction,
  relaunchWebstore,
  approveWebstoreQuestionnaire,
  createWebstoreRequest,
  findWebstoreCustomerMatches,
  getWebstoreFulfillmentSettings,
  getWebstoreInformationPacket,
  getWebstoreQuestionnaireReview,
  returnWebstoreQuestionnaire,
  saveWebstoreFulfillmentSettings,
  sendWebstoreInformationPacket,
} from "@/lib/webstores";
import { useAuth } from "@/auth/AuthContext";
import { toast } from "sonner";

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
  getWebstorePaymentProviderStatus: jest.fn(),
  getWebstoreOrders: jest.fn(),
  handoffWebstoreOrderToProduction: jest.fn(),
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
  requestWebstorePaymentProviderAction: jest.fn(),
  relaunchWebstore: jest.fn(),
  approveWebstoreQuestionnaire: jest.fn(),
  createWebstoreRequest: jest.fn(),
  findWebstoreCustomerMatches: jest.fn(),
  getWebstoreFulfillmentSettings: jest.fn(),
  getWebstoreInformationPacket: jest.fn(),
  getWebstoreQuestionnaireReview: jest.fn(),
  returnWebstoreQuestionnaire: jest.fn(),
  saveWebstoreFulfillmentSettings: jest.fn(),
  sendWebstoreInformationPacket: jest.fn(),
}));

jest.mock("@/auth/AuthContext", () => ({
  useAuth: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: { get: jest.fn(() => Promise.resolve({ data: [] })) },
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
    message: jest.fn(),
  },
}));

// The backend read model (Phase 3) supplies stage and next action on the detail response.
function stageOf(key, label) {
  const path = key === "draft" ? [{ key, staff_label: label }] : [{ key: "draft", staff_label: "Request received" }, { key, staff_label: label }];
  return { key, staff_label: label, owner_label: label, path };
}

const PACKET = {
  webstore_id: "ws-1",
  recipient_email: "owner@example.com",
  preview: { subject: "Your Event store with Shop: next steps", body: "Hi Pat,\n\nCustom merchandise is final sale, except for our mistakes.", reply_to: "orders@shop.example" },
  sent_count: 0,
  delivery: { status: "prepared" },
};

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
  getWebstore.mockResolvedValue({
    webstore: { id: "ws-1", name: "Team Store", store_type: "general", status: "draft" },
    launch_packets: [],
    products: [],
  });
  getWebstoreQuestionnaire.mockResolvedValue({ templates: [] });
  getWebstoreQuestionnaireResponse.mockResolvedValue({ submission: null });
  generateLaunchPacket.mockResolvedValue({});
  getLaunchReadiness.mockResolvedValue({ setup_complete: false, ready_to_publish: false, checks: {}, payment_unavailable_reason: "Not configured." });
  getWebstoreSetupProgress.mockResolvedValue({ setup_state: "not_started", steps: [] });
  getWebstorePaymentProviderStatus.mockResolvedValue({ status: { label: "Not configured", reason: "Stripe integration is disabled." }, actions: {} });
  getWebstoreReports.mockResolvedValue({ order_count: 0, gross_sales_cents: 0, ledger_totals_cents: {} });
  getWebstoreOrders.mockResolvedValue({ items: [], total: 0 });
  handoffWebstoreOrderToProduction.mockResolvedValue({});
  listWebstoreAssignments.mockResolvedValue([]);
  listWebstoreSetupFiles.mockResolvedValue([]);
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
  requestWebstorePaymentProviderAction.mockResolvedValue({});
  relaunchWebstore.mockResolvedValue({ webstore: { status: "relaunch_ready" } });
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
  createWebstoreRequest.mockResolvedValue({ webstore: { id: "ws-new" }, customer_id: "cust-new", owner_id: "owner-new" });
  findWebstoreCustomerMatches.mockResolvedValue([]);
  getWebstoreInformationPacket.mockResolvedValue(PACKET);
  sendWebstoreInformationPacket.mockResolvedValue({
    ...PACKET,
    sent_count: 1,
    delivery: { status: "sent" },
    questionnaire_link: "https://app.example.test/portal/webstores/invitations/accept?t=abc",
  });
  getWebstoreQuestionnaireReview.mockResolvedValue({
    submission: { id: "sub-2", status: "submitted", revision: 2 },
    previous_revision: 1,
    can_apply: true,
    warnings: [{ code: "closing_before_opening", message: "Ordering closes (2099-03-01) before the store opens (2099-03-10)." }],
    comparison: [{ key: "pickup_location", label: "Pickup location", change: "changed", previous: "Field", current: "Gym", affects_settings: true, material: true }],
    proposed_changes: [{ answer_key: "pickup_location", target: "store_settings.fulfillment.pickup_location", label: "Pickup location", from: "", to: "Gym" }],
    rejected_changes: [],
    brief: [{ id: "event", title: "Event", items: [{ key: "event_name", label: "Event name", value: "Spring Fair" }] }],
  });
  approveWebstoreQuestionnaire.mockResolvedValue({ application: { id: "app-1" } });
  getWebstoreFulfillmentSettings.mockResolvedValue({ supported_methods: ["shop_pickup"], default_pickup_location: "", pickup_instructions: "", pickup_windows_enabled: true, default_window_start: "15:00", default_window_end: "18:00" });
});

function NavigationStateProbe() {
  const location = useLocation();
  return <div data-testid="navigation-state">{JSON.stringify(location.state || {})}</div>;
}

test("public storefront adds to a server-priced cart without offering checkout", async () => {
  const user = userEvent.setup();
  axios.get.mockResolvedValue({
    data: {
      webstore: {
        id: "ws-1",
        name: "Team Store",
        description: "",
        checkout_enabled: false,
        checkout_unavailable_reason: "Payment setup is not available yet.",
        cart_config: {},
      },
      products: [{ id: "prod-1", name: "Team Shirt", product_type: "shirt", selling_price_cents: 2500, fulfillment_methods: ["pickup"] }],
    },
  });
  axios.post.mockResolvedValue({
    data: {
      quote_version: "webstore_cart_quote_v1",
      line_items: [{ product_id: "prod-1", quantity: 2 }],
      subtotal_cents: 5000,
      shipping_cents: 0,
      donation_cents: 0,
      discount_cents: 0,
      total_cents: 5000,
    },
  });

  renderWithProviders(<PublicWebstorePage />, { route: "/p/webstores/team-store", path: "/p/webstores/:slug" });

  expect(await screen.findByText(/Team Store/)).toBeInTheDocument();
  expect(screen.getByTestId("webstore-checkout-disabled")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /Add$/ }));

  await waitFor(() => expect(axios.post).toHaveBeenCalledWith(
    "/api/public/webstores/team-store/cart-quote",
    {
      line_items: [{ product_id: "prod-1", quantity: 1, variant: {}, personalization: {}, fulfillment_method: "pickup" }],
      donation_cents: 0,
    },
  ));
  expect(await screen.findByTestId("public-cart-total")).toHaveTextContent("$50.00");
  expect(screen.getByText(/Payment and order creation are unavailable/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /checkout/i })).not.toBeInTheDocument();
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
    setup_complete: false,
    ready_to_publish: false,
    checks: { payment_ready: false, active_public_products_with_prices: false },
    payment_unavailable_reason: "Real verified provider checkout is not connected yet.",
  });
  getWebstoreReports.mockResolvedValue({ order_count: 0, gross_sales_cents: 0, ledger_totals_cents: {} });
  listProductTemplates.mockResolvedValue([]);

  renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-1", path: "/webstores/:id" });

  expect(await screen.findByText(/Team Store/)).toBeInTheDocument();
  await userEvent.setup().click(screen.getByRole("tab", { name: "Approval & Launch" }));
  expect(screen.getByTestId("webstore-payment-readiness")).toHaveTextContent("Payment readiness: Not connected");
  expect(screen.queryByLabelText("Payment boundary ready")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Preview Not Ready/ })).toBeDisabled();
  expect(screen.queryByRole("link", { name: /Preview Portal/ })).not.toBeInTheDocument();
});

test("Webstore request records a customer, contact and one of the six types plus the Employee preset", async () => {
  const user = userEvent.setup();
  renderWithProviders(<><WebstoresPage /><NavigationStateProbe /></>);

  expect(screen.queryByTestId("webstore-request-dialog")).not.toBeInTheDocument();
  await user.click(screen.getByTestId("new-webstore-button"));
  expect(await screen.findByTestId("webstore-request-dialog")).toBeInTheDocument();
  await user.click(screen.getByTestId("webstore-request-type"));
  for (const label of ["Fundraiser", "Event", "Team / School", "Business / B2B", "Promotional", "General"]) {
    expect(screen.getAllByText(label).length).toBeGreaterThan(0);
  }
  expect(screen.getByText("Employee / Company store (business preset)")).toBeInTheDocument();
  await user.click(screen.getByText("Team / School"));
  await user.click(screen.getByTestId("webstore-request-new"));
  await user.type(screen.getByTestId("webstore-request-customer-name"), "Lincoln Boosters");
  await user.type(screen.getByTestId("webstore-request-customer-email"), "boosters@example.com");
  await user.type(screen.getByTestId("webstore-request-name"), "Lions Spirit Store");
  await user.click(screen.getByTestId("webstore-request-submit"));

  await waitFor(() => expect(createWebstoreRequest).toHaveBeenCalledWith(expect.objectContaining({
    new_customer: expect.objectContaining({ name: "Lincoln Boosters", email: "boosters@example.com" }),
    store_type: "team_school",
    store_name: "Lions Spirit Store",
  })));
  expect(createWebstore).not.toHaveBeenCalled();
  expect(sendWebstoreInformationPacket).not.toHaveBeenCalled();
});

test("Webstore request warns about an existing customer before creating a duplicate", async () => {
  findWebstoreCustomerMatches.mockResolvedValue([
    { customer: { id: "cust-1", name: "Lincoln Boosters", email: "boosters@example.com" }, match_reasons: ["Matching email"], strong: true },
  ]);
  const user = userEvent.setup();
  renderWithProviders(<WebstoresPage />);

  await user.click(screen.getByTestId("new-webstore-button"));
  await user.click(await screen.findByTestId("webstore-request-new"));
  await user.type(screen.getByTestId("webstore-request-customer-name"), "Boosters");
  await user.type(screen.getByTestId("webstore-request-customer-email"), "boosters@example.com");
  await user.tab();
  expect(await screen.findByTestId("webstore-request-matches")).toHaveTextContent("This customer may already exist");
  expect(screen.getByTestId("webstore-request-submit")).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Use this customer" }));
  await user.click(screen.getByTestId("webstore-request-submit"));
  await waitFor(() => expect(createWebstoreRequest).toHaveBeenCalledWith(expect.objectContaining({ customer_id: "cust-1", new_customer: undefined })));
});

test("information packet preview sends once from the Webstore page", async () => {
  const user = userEvent.setup();
  renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-1", path: "/webstores/:id" });

  await user.click(await screen.findByTestId("webstore-information-packet"));
  expect(await screen.findByTestId("information-packet-body")).toHaveTextContent("final sale");
  expect(screen.getByTestId("information-packet-status")).toHaveTextContent("Prepared");
  await user.click(screen.getByTestId("information-packet-send"));
  await waitFor(() => expect(sendWebstoreInformationPacket).toHaveBeenCalledWith("ws-1", { resend: false }));
  expect(toast.success).toHaveBeenCalledWith("Information packet sent");
  expect(await screen.findByTestId("information-packet-link")).toHaveTextContent("https://app.example.test/portal/webstores/invitations/accept?t=abc");
  expect(screen.getByTestId("information-packet-resend")).toBeInTheDocument();
});

test("information packet delivery failure is truthful and keeps the copy-link fallback", async () => {
  sendWebstoreInformationPacket.mockResolvedValueOnce({
    ...PACKET,
    sent_count: 1,
    delivery: { status: "failed", error: "sendgrid_not_configured" },
    questionnaire_link: "https://app.example.test/portal/webstores/invitations/accept?t=xyz",
  });
  const user = userEvent.setup();
  renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-1", path: "/webstores/:id" });

  await user.click(await screen.findByTestId("webstore-information-packet"));
  await user.click(await screen.findByTestId("information-packet-send"));
  await waitFor(() => expect(toast.error).toHaveBeenCalledWith(expect.stringContaining("Copy the link")));
  expect(toast.success).not.toHaveBeenCalled();
  expect(screen.getByTestId("information-packet-status")).toHaveTextContent("Not delivered");
  expect(screen.getByTestId("information-packet-link")).toHaveTextContent("t=xyz");
  expect(sendWebstoreInformationPacket).toHaveBeenCalledTimes(1);
});

test("webstore detail shows setup intake, assignments, files, and the one-click review", async () => {
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
      setup_profile: { starting_products: ["Team Shirts"] },
    },
    stage: stageOf("draft", "Request received"),
    next_action: { key: "review_questionnaire", actor: "shop", staff_text: "Review questionnaire revision 2", tab: "setup", blockers: [] },
    launch_packets: [],
    products: [],
  });
  getLaunchReadiness.mockResolvedValue({ setup_complete: false, ready_to_publish: false, checks: { payment_ready: false }, payment_unavailable_reason: "Real verified provider checkout is not connected yet." });
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
    submission: { id: "sub-2", status: "submitted", revision: 2, submitted_snapshot: { answers: { store_name: "New Name" } } },
  });

  const user = userEvent.setup();
  renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-2", path: "/webstores/:id" });

  expect(await screen.findByText(/Setup Store/)).toBeInTheDocument();
  expect(screen.getByText(/Webstores setup - event - Request received/)).toBeInTheDocument();
  expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual([
    "Overview", "Setup", "Products", "Storefront", "Approval & Launch", "Orders & Production", "Messages & Activity",
  ]);
  expect(screen.getByTestId("webstore-timeline-next-action")).toHaveTextContent("Review questionnaire revision 2");
  await user.click(screen.getByRole("tab", { name: "Products" }));
  expect(screen.getByTestId("webstore-starting-product-ideas")).toHaveTextContent("Team Shirts");
  await user.click(screen.getByRole("tab", { name: "Setup" }));
  expect(screen.getByTestId("webstore-setup-state")).toHaveTextContent("staff_review");
  expect(await screen.findAllByText("owner@example.com")).toHaveLength(1); // the assignments card (Setup tab)
  expect(await screen.findByTestId("webstore-assignment-resend-assign-2")).toBeInTheDocument();
  expect(await screen.findByText("logo.png")).toBeInTheDocument();
  expect(screen.getByTestId("questionnaire-status")).toHaveTextContent("Ready for review · revision 2");

  await user.click(screen.getByTestId("questionnaire-open-review"));
  expect(await screen.findByTestId("questionnaire-review-warnings")).toHaveTextContent("Ordering closes");
  expect(screen.getByTestId("questionnaire-review-comparison")).toHaveTextContent("Pickup location");
  expect(screen.getByTestId("questionnaire-review-changes")).toHaveTextContent("Gym");
  expect(screen.getByTestId("questionnaire-review-brief")).toHaveTextContent("Spring Fair");
  await user.click(screen.getByTestId("questionnaire-approve-apply"));
  await waitFor(() => expect(approveWebstoreQuestionnaire).toHaveBeenCalledWith("ws-2", "sub-2"));
  expect(toast.success).toHaveBeenCalledWith("Answers approved and applied to the draft store");
});

test("webstore overview shows the backend next action with one primary button", async () => {
  getWebstore.mockResolvedValue({
    webstore: { id: "ws-guided", name: "Guided Store", store_type: "fundraiser", status: "draft", setup_profile: {} },
    stage: stageOf("draft", "Request received"),
    next_action: { key: "send_information_packet", actor: "shop", staff_text: "Send the information packet", tab: "setup", blockers: [] },
    launch_packets: [],
    products: [],
  });
  getWebstoreQuestionnaire.mockResolvedValue({ templates: [{ id: "fundraiser-template", sections: [] }] });
  getWebstoreQuestionnaireResponse.mockResolvedValue({ submission: null });
  listWebstoreAssignments.mockResolvedValue([{ id: "owner-1", role: "owner", email: "owner@example.com", status: "active" }]);

  const user = userEvent.setup();
  renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-guided", path: "/webstores/:id" });

  expect(await screen.findByTestId("webstore-timeline")).toBeInTheDocument();
  expect(screen.getByTestId("webstore-timeline-stage-draft")).toHaveAttribute("aria-current", "step");
  expect(screen.getByTestId("webstore-timeline-next-action")).toHaveTextContent("Send the information packet");
  expect(screen.queryByText(/Next required action/)).not.toBeInTheDocument();
  await user.click(screen.getByTestId("webstore-primary-action"));
  expect(await screen.findByTestId("information-packet-dialog")).toBeInTheDocument();
  await waitFor(() => expect(getWebstoreInformationPacket).toHaveBeenCalledWith("ws-guided"));
});

test("an owner-owned next action never offers a shop control, and publishing appears only when the backend says so", async () => {
  getWebstore.mockResolvedValue({
    webstore: { id: "ws-wait", name: "Waiting Store", store_type: "general", status: "sent_for_approval" },
    stage: stageOf("owner_review", "Owner approval"),
    next_action: {
      key: "packet_approved", actor: "owner", staff_text: "Waiting for the owner to approve the launch packet", tab: "review-launch",
      blockers: [{ key: "packet_approved", reason: "Store Owner approval is required." }, { key: "payment_ready", reason: "Real verified provider checkout is not connected yet." }],
    },
    launch_packets: [],
    products: [],
  });
  const user = userEvent.setup();
  const view = renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-wait", path: "/webstores/:id" });

  expect(await screen.findByTestId("webstore-primary-action")).toHaveTextContent("Open Approval & Launch");
  expect(screen.getByTestId("webstore-timeline-next-action")).toHaveTextContent("Waiting on owner");
  expect(screen.getByTestId("webstore-timeline-blockers")).toHaveTextContent("not connected");
  expect(screen.queryByRole("button", { name: /Publish Webstore/ })).not.toBeInTheDocument();
  await user.click(screen.getByTestId("webstore-primary-action"));
  expect(screen.getByRole("tab", { name: "Approval & Launch" })).toHaveAttribute("data-state", "active");
  view.unmount();

  getWebstore.mockResolvedValue({
    webstore: { id: "ws-ready", name: "Ready Store", store_type: "general", status: "launch_ready" },
    stage: stageOf("ready_to_launch", "Ready to publish"),
    next_action: { key: "publish", actor: "shop", staff_text: "Ready to publish", tab: "review-launch", blockers: [] },
    launch_packets: [],
    products: [],
  });
  renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-ready", path: "/webstores/:id" });
  expect(await screen.findByTestId("webstore-primary-action")).toHaveTextContent("Publish Webstore");
});

test("guided setup branding files and appearance carry into Storefront without publishing", async () => {
  const user = userEvent.setup();
  getWebstore.mockResolvedValue({
    webstore: {
      id: "ws-3",
      name: "Brand Setup Store",
      slug: "brand-setup-store",
      public_slug: "brand-setup-store",
      public_url: "/p/webstores/brand-setup-store",
      store_type: "general",
      status: "draft",
      setup_state: "not_started",
      setup_profile: {},
    },
    launch_packets: [],
    products: [],
  });
  getLaunchReadiness.mockResolvedValue({ setup_complete: false, ready_to_publish: false, checks: { payment_ready: false }, payment_unavailable_reason: "Real verified provider checkout is not connected yet." });
  getWebstoreReports.mockResolvedValue({ order_count: 0, gross_sales_cents: 0, ledger_totals_cents: {} });
  listWebstoreSetupFiles.mockResolvedValue([
    {
      id: "logo-file",
      category: "logo",
      status: "active",
      file_name: "setup-logo.png",
      detected_content_type: "image/png",
      preview_url: "/api/webstores/ws-3/setup-files/logo-file/preview",
    },
    {
      id: "banner-file",
      category: "banner",
      status: "active",
      file_name: "setup-banner.png",
      detected_content_type: "image/png",
      preview_url: "/api/webstores/ws-3/setup-files/banner-file/preview",
    },
  ]);
  getWebstoreBranding.mockResolvedValueOnce({
    webstore: { id: "ws-3", name: "Brand Setup Store", store_type: "general" },
    branding: {
      status: "draft",
      draft: {
        brand_basics: { display_name: "Brand Setup Store", primary_logo: {} },
        colors_fonts: { primary_color: "#123456", accent_color: "#abcdef" },
        header: { show_header: true, display_mode: "name" },
        hero: { show_hero: true, image: {} },
        store_information: { show_section: true, welcome_heading: "Welcome setup" },
        store_type_content: {},
        catalog_introduction: { show_catalog_area: true },
        footer: { show_footer: true },
      },
      validation: { errors: [], warnings: [] },
    },
    permissions: { can_save_draft: true, can_request_review: true, can_publish: true, can_control_whole_sections: true },
    history: [],
    activity: [],
  });

  renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-3", path: "/webstores/:id" });

  await user.click(await screen.findByRole("tab", { name: "Storefront" }));
  expect(screen.getByTestId("branding-image-primary-logo")).toHaveValue("/api/webstores/ws-3/setup-files/logo-file/preview");
  expect(screen.getByAltText("Primary logo")).toHaveAttribute("src", "/api/webstores/ws-3/setup-files/logo-file/preview");
  await user.click(screen.getByRole("button", { name: "Hero Section" }));
  expect(screen.getByTestId("branding-image-hero-image")).toHaveValue("/api/webstores/ws-3/setup-files/banner-file/preview");
  expect(screen.getByAltText("Hero image")).toHaveAttribute("src", "/api/webstores/ws-3/setup-files/banner-file/preview");
  await user.click(screen.getByRole("button", { name: "Colors & Fonts" }));
  expect(screen.getByTestId("branding-field-colors_fonts.primary_color")).toHaveValue("#123456");
  expect(screen.getByTestId("branding-field-colors_fonts.accent_color")).toHaveValue("#abcdef");
  await user.click(screen.getByRole("button", { name: "Store Information" }));
  expect(screen.getByTestId("branding-field-store_information.welcome_heading")).toHaveValue("Welcome setup");
  expect(screen.getByRole("button", { name: "Publish" })).toBeDisabled();
  expect(publishWebstoreBranding).not.toHaveBeenCalled();
  expect(screen.getAllByRole("tab")).toHaveLength(7);
  await user.click(screen.getByRole("tab", { name: "Overview" }));
  expect(screen.getByTestId("webstore-timeline")).toBeInTheDocument();
});

test("Stage 8B shows canonical Webstore Orders on the Orders & Production tab", async () => {
  getWebstoreOrders.mockResolvedValue({
    source_of_truth: "canonical_orders",
    total: 1,
    items: [
      {
        id: "order-stage8b-ui",
        number: 801,
        status: "confirmed",
        created_at: "2026-08-03T12:00:00Z",
        customer: { name: "Projection Buyer", email: "buyer@example.com" },
        total_cents: 3200,
        payment: { status: "confirmed" },
        fulfillment: { status: "awaiting_production_handoff" },
        items: [{ quantity: 2, description: "Projection Shirt" }],
      },
    ],
  });

  renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-1", path: "/webstores/:id" });

  await userEvent.setup().click(await screen.findByRole("tab", { name: "Orders & Production" }));
  expect(await screen.findByTestId("webstore-order-order-stage8b-ui")).toHaveTextContent("Order #801");
  expect(screen.getByTestId("webstore-order-order-stage8b-ui")).toHaveTextContent("Projection Buyer");
  expect(screen.getByTestId("webstore-order-order-stage8b-ui")).toHaveTextContent("$32.00");
  expect(screen.getAllByRole("tab")).toHaveLength(7);
  expect(screen.queryByText(/internal_cost|stripe_payment_intent/i)).not.toBeInTheDocument();
});

test("Stage 8E offers a readiness-gated relaunch for closed Webstores", async () => {
  getWebstore.mockResolvedValue({
    webstore: { id: "ws-closed", name: "Closed Store", store_type: "general", status: "closed" },
    stage: stageOf("closed", "Closed"),
    next_action: { key: "review_closed_orders", actor: "shop", staff_text: "Ordering closed - finish production and fulfillment", tab: "overview", blockers: [] },
    launch_packets: [],
    products: [],
  });

  renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-closed", path: "/webstores/:id" });

  const user = userEvent.setup();
  await user.click(await screen.findByTestId("webstore-relaunch"));
  await waitFor(() => expect(relaunchWebstore).toHaveBeenCalledWith("ws-closed", "Staff requested Webstore relaunch"));
  expect(screen.getAllByRole("tab")).toHaveLength(7);
});
