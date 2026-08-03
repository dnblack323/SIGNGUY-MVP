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
  requestWebstorePaymentProviderAction,
  sendWebstoreQuestionnaire,
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
  requestWebstorePaymentProviderAction: jest.fn(),
  sendWebstoreQuestionnaire: jest.fn(),
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
  getWebstorePaymentProviderStatus.mockResolvedValue({ status: { label: "Not configured", reason: "Stripe integration is disabled." }, actions: {} });
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
  requestWebstorePaymentProviderAction.mockResolvedValue({});
  sendWebstoreQuestionnaire.mockResolvedValue({ email_sent: true, request_url: "/forms/request-1" });
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
    ready: false,
    checks: { payment_ready: false, active_public_products_with_prices: false },
    payment_unavailable_reason: "Real verified provider checkout is not connected yet.",
  });
  getWebstoreReports.mockResolvedValue({ order_count: 0, gross_sales_cents: 0, ledger_totals_cents: {} });
  listProductTemplates.mockResolvedValue([]);

  renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-1", path: "/webstores/:id" });

  expect(await screen.findByText(/Team Store/)).toBeInTheDocument();
  await userEvent.setup().click(screen.getByTestId("webstore-advanced-setup-toggle"));
  expect(screen.getByTestId("webstore-payment-readiness")).toHaveTextContent("Payment readiness: Not connected");
  expect(screen.queryByLabelText("Payment boundary ready")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Preview Not Ready/ })).toBeDisabled();
  expect(screen.queryByRole("link", { name: /Preview Portal/ })).not.toBeInTheDocument();
});

test("authenticated Webstores creation uses the five approved types and opens a guided setup", async () => {
  const user = userEvent.setup();
  renderWithProviders(<WebstoresPage />);

  expect(screen.queryByTestId("new-webstore-dialog")).not.toBeInTheDocument();
  await user.click(screen.getByTestId("new-webstore-button"));
  expect(await screen.findByTestId("new-webstore-dialog")).toBeInTheDocument();
  expect(screen.getByText("Create a Webstore")).toBeInTheDocument();
  await user.click(screen.getByTestId("webstore-type"));
  expect(screen.queryByText("Employee")).not.toBeInTheDocument();
  await user.click(await screen.findByText("Event"));
  await user.click(screen.getByTestId("webstore-setup-next"));
  await user.type(screen.getByTestId("webstore-owner-name"), "Owner Name");
  await user.type(screen.getByTestId("webstore-owner-email"), "owner@example.com");
  await user.click(screen.getByTestId("webstore-setup-next"));
  expect(screen.getByTestId("webstore-type-specific")).toBeInTheDocument();
  await user.clear(screen.getByTestId("webstore-name"));
  await user.type(screen.getByTestId("webstore-name"), "Event Store");
  await user.click(screen.getByTestId("webstore-setup-next"));
  await user.click(screen.getByTestId("webstore-create"));

  await waitFor(() => expect(createWebstore).toHaveBeenCalledWith(expect.objectContaining({
    owner_id: "owner-new",
    name: "Event Store",
    store_type: "event",
    target_launch_at: undefined,
    deadline_at: undefined,
    setup_profile: expect.objectContaining({ store_purpose: "", audience: "" }),
    store_settings: expect.objectContaining({ access_policy: { mode: "open" } }),
    send_owner_invitation: false,
  })));
});

test("successful questionnaire delivery is reported and passed to the Webstore detail route", async () => {
  const user = userEvent.setup();
  const questionnaire = {
    email_sent: true,
    request_url: "/forms/request-success",
    recipient: "owner@example.com",
  };
  sendWebstoreQuestionnaire.mockResolvedValueOnce(questionnaire);

  renderWithProviders(<><WebstoresPage /><NavigationStateProbe /></>);

  await user.click(screen.getByTestId("new-webstore-button"));
  await user.click(screen.getByTestId("webstore-setup-next"));
  await user.type(screen.getByTestId("webstore-owner-name"), "Owner Name");
  await user.type(screen.getByTestId("webstore-owner-email"), "owner@example.com");
  await user.click(screen.getByTestId("webstore-setup-next"));
  await user.click(screen.getByTestId("webstore-setup-next"));
  await user.click(screen.getByTestId("webstore-continuation-questionnaire"));
  await user.click(screen.getByTestId("webstore-create"));

  await waitFor(() => expect(sendWebstoreQuestionnaire).toHaveBeenCalledTimes(1));
  expect(sendWebstoreQuestionnaire).toHaveBeenCalledWith("ws-new", { email: "owner@example.com", name: "Owner Name" });
  expect(toast.success).toHaveBeenCalledWith("Webstore created and questionnaire sent");
  expect(toast.error).not.toHaveBeenCalled();
  expect(screen.getByTestId("navigation-state")).toHaveTextContent(JSON.stringify({ questionnaireDelivery: questionnaire }));
});

test("blank draft path creates only the required Webstore information", async () => {
  const user = userEvent.setup();
  renderWithProviders(<WebstoresPage />);

  await user.click(screen.getByTestId("new-webstore-button"));
  await user.click(screen.getByTestId("webstore-setup-next"));
  await user.type(screen.getByTestId("webstore-owner-name"), "Blank Owner");
  await user.type(screen.getByTestId("webstore-owner-email"), "blank@example.com");
  await user.click(screen.getByTestId("webstore-setup-next"));
  await user.click(screen.getByTestId("webstore-setup-next"));
  await user.click(screen.getByTestId("webstore-continuation-blank"));
  await user.click(screen.getByTestId("webstore-create"));

  await waitFor(() => expect(createWebstore).toHaveBeenCalledWith(expect.objectContaining({
    name: "Blank Owner Store",
    setup_profile: {},
    store_settings: {},
    branding: {},
  })));
  expect(sendWebstoreQuestionnaire).not.toHaveBeenCalled();
});

test("questionnaire delivery failures are truthful and preserve the manual recovery link", async () => {
  const user = userEvent.setup();
  const questionnaire = {
    email_sent: false,
    delivery_error: "sendgrid_not_configured",
    request_url: "/forms/request-recovery",
    recipient: "owner@example.com",
  };
  sendWebstoreQuestionnaire.mockResolvedValueOnce(questionnaire);

  renderWithProviders(<><WebstoresPage /><NavigationStateProbe /></>);

  await user.click(screen.getByTestId("new-webstore-button"));
  await user.click(screen.getByTestId("webstore-setup-next"));
  await user.type(screen.getByTestId("webstore-owner-name"), "Owner Name");
  await user.type(screen.getByTestId("webstore-owner-email"), "owner@example.com");
  await user.click(screen.getByTestId("webstore-setup-next"));
  await user.click(screen.getByTestId("webstore-setup-next"));
  await user.click(screen.getByTestId("webstore-continuation-questionnaire"));
  await user.click(screen.getByTestId("webstore-create"));

  await waitFor(() => expect(toast.error).toHaveBeenCalled());
  expect(toast.error.mock.calls[0][0]).toEqual(expect.stringContaining("sendgrid_not_configured"));
  expect(toast.error.mock.calls[0][0]).toEqual(expect.stringContaining("link is available on the Webstore page"));
  expect(toast.success).not.toHaveBeenCalled();
  expect(sendWebstoreQuestionnaire).toHaveBeenCalledTimes(1);
  expect(screen.getByTestId("navigation-state")).toHaveTextContent(JSON.stringify({ questionnaireDelivery: questionnaire }));
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
      setup_profile: { starting_products: ["Team Shirts"] },
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

  expect(await screen.findByText(/Setup Store/)).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Overview" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Products" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Storefront" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Review & Launch" })).toBeInTheDocument();
  expect(screen.queryByText("Setup Timeline")).not.toBeInTheDocument();
  expect(screen.getByTestId("webstore-setup-checklist")).toBeInTheDocument();
  expect(screen.queryByTestId("webstore-setup-state")).not.toBeInTheDocument();
  await user.click(screen.getByRole("tab", { name: "Products" }));
  expect(screen.getByTestId("webstore-starting-product-ideas")).toHaveTextContent("Team Shirts");
  expect(screen.getByTestId("webstore-starting-product-ideas")).toHaveTextContent("Idea only - not yet a configured product.");
  createProductFromTemplate.mockResolvedValueOnce({ id: "prod-team-shirts", name: "Team Shirts", status: "draft" });
  await user.click(screen.getByRole("button", { name: "Start Product" }));
  await waitFor(() => expect(createProductFromTemplate).toHaveBeenCalledWith("ws-2", {
    name: "Team Shirts",
    product_type: "general",
  }));
  expect(screen.getByTestId("webstore-starting-product-ideas")).toHaveTextContent("Idea only - not yet a configured product.");
  await user.click(screen.getByRole("tab", { name: "Overview" }));
  await user.click(screen.getByTestId("webstore-advanced-setup-toggle"));
  expect(screen.getByTestId("webstore-advanced-setup")).toBeInTheDocument();
  expect(screen.getByTestId("webstore-setup-state")).toHaveTextContent("staff_review");
  expect(await screen.findAllByText("owner@example.com")).toHaveLength(2);
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
  getLaunchReadiness.mockResolvedValue({ ready: false, checks: { payment_ready: false }, payment_unavailable_reason: "Real verified provider checkout is not connected yet." });
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
  expect(screen.getAllByRole("tab")).toHaveLength(4);
  await user.click(screen.getByRole("tab", { name: "Overview" }));
  expect(screen.getByTestId("webstore-setup-checklist")).toBeInTheDocument();
});
