import "@testing-library/jest-dom";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";
import WebstoreDetailPage from "@/pages/WebstoreDetailPage";
import {
  archiveProductTemplate,
  archiveWebstoreProduct,
  archiveWebstoreProductCategory,
  applyWebstoreAnswers,
  createProductFromTemplate,
  createProductTemplate,
  createWebstoreAssignment,
  createWebstoreProductCategory,
  duplicateWebstoreProduct,
  generateLaunchPacket,
  getLaunchReadiness,
  getWebstorePaymentProviderStatus,
  getWebstore,
  getWebstoreBranding,
  getWebstoreQuestionnaire,
  getWebstoreQuestionnaireResponse,
  getWebstoreReports,
  getWebstoreOrders,
  handoffWebstoreOrderToProduction,
  getWebstoreSetupProgress,
  listProductTemplates,
  listWebstoreArtwork,
  listWebstoreAssignments,
  listWebstoreMockups,
  listWebstoreProductCategories,
  previewWebstoreProductAiAction,
  listWebstoreSetupFiles,
  previewWebstoreAnswerApplication,
  reorderWebstoreProducts,
  resendWebstoreInvitation,
  restoreProductTemplate,
  restoreWebstoreProduct,
  restoreWebstoreProductCategory,
  reverseWebstoreAnswerApplication,
  runWebstoreProductAiAction,
  sendLaunchPacket,
  setWebstoreStatus,
  updateProductTemplate,
  updateWebstore,
  updateWebstoreChangeRequest,
  updateWebstoreProduct,
  updateWebstoreProductCategory,
  requestWebstorePaymentProviderAction,
  submitWebstoreMockupApproval,
  submitWebstoreProductApproval,
  uploadWebstoreSetupFile,
} from "@/lib/webstores";
import { useAuth } from "@/auth/AuthContext";

jest.mock("@/lib/webstores", () => ({
  archiveProductTemplate: jest.fn(),
  archiveWebstoreProduct: jest.fn(),
  archiveWebstoreProductCategory: jest.fn(),
  applyWebstoreAnswers: jest.fn(),
  createProductFromTemplate: jest.fn(),
  createProductTemplate: jest.fn(),
  createWebstoreAssignment: jest.fn(),
  createWebstoreProductCategory: jest.fn(),
  duplicateWebstoreProduct: jest.fn(),
  generateLaunchPacket: jest.fn(),
  getLaunchReadiness: jest.fn(),
  getWebstorePaymentProviderStatus: jest.fn(),
  getWebstore: jest.fn(),
  getWebstoreBranding: jest.fn(),
  getWebstoreQuestionnaire: jest.fn(),
  getWebstoreQuestionnaireResponse: jest.fn(),
  getWebstoreReports: jest.fn(),
  getWebstoreOrders: jest.fn(),
  handoffWebstoreOrderToProduction: jest.fn(),
  getWebstoreSetupProgress: jest.fn(),
  listProductTemplates: jest.fn(),
  listWebstoreArtwork: jest.fn(),
  listWebstoreAssignments: jest.fn(),
  listWebstoreMockups: jest.fn(),
  listWebstoreProductCategories: jest.fn(),
  previewWebstoreProductAiAction: jest.fn(),
  listWebstoreSetupFiles: jest.fn(),
  previewWebstoreAnswerApplication: jest.fn(),
  reorderWebstoreProducts: jest.fn(),
  resendWebstoreInvitation: jest.fn(),
  restoreProductTemplate: jest.fn(),
  restoreWebstoreProduct: jest.fn(),
  restoreWebstoreProductCategory: jest.fn(),
  reverseWebstoreAnswerApplication: jest.fn(),
  runWebstoreProductAiAction: jest.fn(),
  sendLaunchPacket: jest.fn(),
  setWebstoreStatus: jest.fn(),
  updateProductTemplate: jest.fn(),
  updateWebstore: jest.fn(),
  updateWebstoreChangeRequest: jest.fn(),
  updateWebstoreProduct: jest.fn(),
  updateWebstoreProductCategory: jest.fn(),
  requestWebstorePaymentProviderAction: jest.fn(),
  submitWebstoreMockupApproval: jest.fn(),
  submitWebstoreProductApproval: jest.fn(),
  uploadWebstoreSetupFile: jest.fn(),
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

jest.setTimeout(10000);

beforeEach(() => {
  jest.clearAllMocks();
  window.HTMLElement.prototype.hasPointerCapture = window.HTMLElement.prototype.hasPointerCapture || (() => false);
  window.HTMLElement.prototype.setPointerCapture = window.HTMLElement.prototype.setPointerCapture || (() => {});
  window.HTMLElement.prototype.releasePointerCapture = window.HTMLElement.prototype.releasePointerCapture || (() => {});
  window.HTMLElement.prototype.scrollIntoView = window.HTMLElement.prototype.scrollIntoView || (() => {});
  useAuth.mockReturnValue({ hasPerm: () => true });
  getWebstore.mockResolvedValue({
    webstore: {
      id: "ws-1",
      name: "Team Store",
      slug: "team-store",
      public_slug: "team-store-public",
      public_url: "/p/webstores/team-store-public",
      status: "draft",
      store_type: "general",
    },
    launch_packets: [],
    products: [
      {
        id: "prod-1",
        name: "Draft Shirt",
        status: "draft",
        public: false,
        revision: 3,
        product_type: "shirt",
        category_id: "cat-1",
        category_name: "Team Wear",
        selling_price_cents: 0,
        approval_status: "not_submitted",
        customer_images: { primary: { file_id: "file-1", alt_text: "Shirt front" } },
        artwork_associations: [],
        mockup_associations: [],
        template_provenance: { source_template_id: "tpl-tenant", source_template_revision: 1 },
      },
      {
        id: "prod-archived",
        name: "Archived Draft",
        status: "archived",
        public: false,
        revision: 5,
        product_type: "shirt",
        category_id: "cat-1",
        category_name: "Team Wear",
        selling_price_cents: 0,
        approval_status: "not_submitted",
        customer_images: {},
        artwork_associations: [],
        mockup_associations: [],
      },
    ],
  });
  getLaunchReadiness.mockResolvedValue({ ready: false, checks: { payment_ready: false }, payment_unavailable_reason: "Real verified provider checkout is not connected yet." });
  getWebstorePaymentProviderStatus.mockResolvedValue({ status: { label: "Not configured", reason: "Stripe integration is disabled." }, actions: {} });
  getWebstoreReports.mockResolvedValue({ order_count: 0, gross_sales_cents: 0, ledger_totals_cents: {} });
  getWebstoreOrders.mockResolvedValue({ items: [], total: 0 });
  handoffWebstoreOrderToProduction.mockResolvedValue({});
  getWebstoreSetupProgress.mockResolvedValue({ setup_state: "not_started", steps: [] });
  listWebstoreAssignments.mockResolvedValue([]);
  listWebstoreSetupFiles.mockResolvedValue([
    {
      id: "file-1",
      file_name: "front.png",
      content_type: "image/png",
      preview_url: "/api/webstores/ws-1/setup-files/file-1/preview",
      safe_preview_available: true,
      inline_preview_allowed: true,
    },
    {
      id: "file-2",
      file_name: "front-new.png",
      content_type: "image/png",
      preview_url: "/api/webstores/ws-1/setup-files/file-2/preview",
      safe_preview_available: true,
      inline_preview_allowed: true,
    },
    {
      id: "file-3",
      file_name: "detail.png",
      content_type: "image/png",
      preview_url: "/api/webstores/ws-1/setup-files/file-3/preview",
      safe_preview_available: true,
      inline_preview_allowed: true,
    },
  ]);
  getWebstoreQuestionnaire.mockResolvedValue({ templates: [] });
  getWebstoreQuestionnaireResponse.mockResolvedValue({ submission: null });
  previewWebstoreAnswerApplication.mockResolvedValue({ proposed_changes: [], rejected_changes: [] });
  applyWebstoreAnswers.mockResolvedValue({});
  reverseWebstoreAnswerApplication.mockResolvedValue({});
  createWebstoreAssignment.mockResolvedValue({});
  uploadWebstoreSetupFile.mockResolvedValue({});
  resendWebstoreInvitation.mockResolvedValue({});
  generateLaunchPacket.mockResolvedValue({});
  sendLaunchPacket.mockResolvedValue({});
  setWebstoreStatus.mockResolvedValue({});
  updateWebstore.mockResolvedValue({});
  updateWebstoreChangeRequest.mockResolvedValue({});
  getWebstoreBranding.mockResolvedValue({ branding: { draft: {}, validation: { errors: [], warnings: [] } }, permissions: {} });
  listProductTemplates.mockResolvedValue([
    { id: "tpl-platform", scope: "platform", status: "active", template_name: "Starter Shirt", product_category: "Apparel", product_type: "shirt" },
    { id: "tpl-tenant", scope: "tenant", status: "active", revision: 2, template_name: "Tenant Shirt", default_title: "Tenant Draft", product_category: "Apparel", product_type: "shirt" },
  ]);
  listWebstoreArtwork.mockResolvedValue([
    { id: "art-1", file_name: "artwork.png", purpose: "production" },
    { id: "art-2", file_name: "artwork-2.png", purpose: "production" },
  ]);
  listWebstoreMockups.mockResolvedValue([{ id: "mock-1", alt_text: "Mockup preview", purpose: "preview" }]);
  listWebstoreProductCategories.mockResolvedValue({
    items: [{ id: "cat-1", name: "Team Wear", description: "Team gear", status: "active", revision: 4, product_count: 1 }],
    legacy_categories: ["Legacy / Unknown"],
  });
  previewWebstoreProductAiAction.mockResolvedValue({
    action: "product_description",
    label: "Product description draft",
    credit_charge_credits: 1,
    available_credits: 8,
    credit_display: "1 AI credit",
    confirmation_required: true,
    insufficient_credits: false,
    auto_apply: false,
    manual_setup_available: true,
  });
  runWebstoreProductAiAction.mockResolvedValue({
    auto_apply: false,
    review_required: true,
    ai_result: {
      id: "draft-1",
      record_type: "editable_draft",
      title: "Product description draft - Draft Shirt",
      content_text: "Local mock draft for Webstore Product Content: booster club shirt",
    },
  });
  createProductFromTemplate.mockResolvedValue({ id: "prod-new", name: "New draft product", status: "draft", public: false, revision: 1 });
  updateWebstoreProduct.mockResolvedValue({ id: "prod-1", name: "Updated Draft Shirt", status: "draft", public: false, revision: 4 });
  createProductTemplate.mockResolvedValue({});
  updateProductTemplate.mockResolvedValue({});
  archiveProductTemplate.mockResolvedValue({});
  restoreProductTemplate.mockResolvedValue({});
  createWebstoreProductCategory.mockResolvedValue({});
  updateWebstoreProductCategory.mockResolvedValue({});
  archiveWebstoreProductCategory.mockResolvedValue({});
  restoreWebstoreProductCategory.mockResolvedValue({});
  archiveWebstoreProduct.mockResolvedValue({});
  restoreWebstoreProduct.mockResolvedValue({});
  duplicateWebstoreProduct.mockResolvedValue({ id: "prod-copy", name: "Draft Shirt Copy", status: "draft", public: false, revision: 1 });
  reorderWebstoreProducts.mockResolvedValue({ items: [] });
  submitWebstoreProductApproval.mockResolvedValue({ id: "prod-1", name: "Draft Shirt", status: "draft", public: false, revision: 3, approval_status: "pending_owner_approval" });
  submitWebstoreMockupApproval.mockResolvedValue({ id: "mock-1", approval_status: "pending_owner_approval" });
  requestWebstorePaymentProviderAction.mockResolvedValue({});
});

test("staff product image picker previews selected files before save", async () => {
  const user = userEvent.setup();
  updateWebstoreProduct
    .mockImplementationOnce((_webstoreId, productId, payload) => Promise.resolve({
      id: productId,
      name: payload.name,
      status: "draft",
      public: false,
      revision: 4,
      product_type: payload.product_type,
      category_id: payload.category_id,
      category_name: payload.category_name,
      selling_price_cents: 0,
      images: [
        {
          slot: "primary",
          role: "primary",
          file_id: payload.customer_images.primary.file_id,
          url: "/api/public/webstores/team-store-public/product-images/prod-1/primary",
          preview_url: `/api/webstores/ws-1/setup-files/${payload.customer_images.primary.file_id}/preview`,
          alt_text: payload.customer_images.primary.alt_text,
        },
      ],
      artwork_associations: payload.artwork_associations,
      mockup_associations: payload.mockup_associations,
    }))
    .mockImplementationOnce((_webstoreId, productId, payload) => Promise.resolve({
      id: productId,
      name: payload.name,
      status: "draft",
      public: false,
      revision: 5,
      product_type: payload.product_type,
      category_id: payload.category_id,
      category_name: payload.category_name,
      selling_price_cents: 0,
      customer_images: payload.customer_images,
      images: [
        {
          slot: "primary",
          role: "primary",
          file_id: payload.customer_images.primary.file_id,
          url: "/api/public/webstores/team-store-public/product-images/prod-1/primary",
          preview_url: `/api/webstores/ws-1/setup-files/${payload.customer_images.primary.file_id}/preview`,
          alt_text: payload.customer_images.primary.alt_text,
        },
      ],
      artwork_associations: payload.artwork_associations,
      mockup_associations: payload.mockup_associations,
    }));
  renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-1", path: "/webstores/:id" });

  await screen.findByText(/Team Store/);
  expect(screen.getByText(/Webstores setup/)).toBeInTheDocument();
  await user.click(screen.getByRole("tab", { name: "Products" }));
  await user.click(screen.getByTestId("webstore-product-row-prod-1"));
  await user.click(screen.getByRole("tab", { name: "Images and Mockups" }));

  const primary = screen.getByTestId("webstore-product-image-primary");
  await user.click(within(primary).getByTestId("webstore-product-image-primary-file"));
  await user.click(await screen.findByText("front-new.png"));
  await waitFor(() => {
    const image = within(primary).getByRole("img", { name: "Shirt front" });
    expect(image).toHaveAttribute("src", "/api/webstores/ws-1/setup-files/file-2/preview");
  });

  const secondary = screen.getByTestId("webstore-product-image-secondary");
  await user.click(within(secondary).getByTestId("webstore-product-image-secondary-file"));
  await user.click(await screen.findByText("detail.png"));
  await waitFor(() => expect(secondary.querySelector("img")).toHaveAttribute("src", "/api/webstores/ws-1/setup-files/file-3/preview"));
  await user.click(within(secondary).getByRole("button", { name: "Remove" }));
  expect(within(secondary).queryByRole("img")).not.toBeInTheDocument();
  expect(within(primary).getByRole("img", { name: "Shirt front" })).toHaveAttribute("src", "/api/webstores/ws-1/setup-files/file-2/preview");

  await user.click(screen.getByRole("tab", { name: "Review Status" }));
  await user.click(screen.getByTestId("webstore-save-product"));
  await waitFor(() => expect(updateWebstoreProduct).toHaveBeenCalledWith("ws-1", "prod-1", expect.objectContaining({
    expected_revision: 3,
    customer_images: {
      primary: expect.objectContaining({
        file_id: "file-2",
      }),
    },
  })));

  await user.click(screen.getByRole("tab", { name: "Images and Mockups" }));
  await waitFor(() => {
    expect(within(primary).getByRole("img", { name: "Shirt front" })).toHaveAttribute("src", "/api/webstores/ws-1/setup-files/file-2/preview");
  });

  await user.click(screen.getByRole("tab", { name: "Review Status" }));
  await user.click(screen.getByTestId("webstore-save-product"));
  await waitFor(() => expect(updateWebstoreProduct).toHaveBeenCalledTimes(2));
  expect(updateWebstoreProduct.mock.calls[1][2]).toEqual(expect.objectContaining({
    expected_revision: 4,
    customer_images: {
      primary: expect.objectContaining({
        file_id: "file-2",
        alt_text: "Shirt front",
      }),
    },
  }));
});

test("staff previews and confirms Webstore product AI output without applying it", async () => {
  const user = userEvent.setup();
  renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-1", path: "/webstores/:id" });

  await screen.findByText(/Team Store/);
  await user.click(screen.getByRole("tab", { name: "Products" }));
  await user.click(screen.getByTestId("webstore-product-row-prod-1"));

  await user.click(screen.getByTestId("webstore-ai-preview-description"));
  expect(await screen.findByTestId("webstore-ai-preview")).toBeInTheDocument();
  expect(screen.getByTestId("webstore-ai-credit-display")).toHaveTextContent("1 AI credit");
  expect(screen.getByText(/8 credits available/)).toBeInTheDocument();

  await user.type(screen.getByTestId("webstore-ai-prompt"), "booster club shirt");
  await user.click(screen.getByTestId("webstore-ai-run-confirmed"));

  await waitFor(() => {
    expect(runWebstoreProductAiAction).toHaveBeenCalledWith("ws-1", "prod-1", expect.objectContaining({
      action: "product_description",
      confirmed_credit_charge_credits: 1,
      prompt: "booster club shirt",
    }));
  });
  expect(await screen.findByTestId("webstore-ai-review-output")).toHaveTextContent("Local mock draft");
  expect(screen.getByTestId("webstore-ai-review-output")).toHaveTextContent("not applied automatically");
  expect(updateWebstoreProduct).not.toHaveBeenCalled();
});

test("staff launch readiness shows packet versioning, terms, QR, schedule, and change-request controls", async () => {
  const user = userEvent.setup();
  getWebstore.mockResolvedValueOnce({
    webstore: {
      id: "ws-1",
      name: "Team Store",
      slug: "team-store",
      public_slug: "team-store-public",
      public_url: "/p/webstores/team-store-public",
      status: "sent_for_approval",
      store_type: "fundraiser",
      launch_packet_id: "packet-2",
      launch_packet_version: 2,
      required_terms_version: "webstore_terms_2026_07",
    },
    current_terms_version: "webstore_terms_2026_07",
    terms_acceptance: null,
    launch_packets: [{
      id: "packet-2",
      version: 2,
      status: "delivered",
      delivery_status: "test_capture_unavailable",
      promotion_copy: "Review the booster launch.",
      snapshot_hash: "hash-2",
      pricing_summary: { product_count: 1 },
      snapshot: { qr_reference: { destination: "/p/webstores/team-store-public" }, products: [{ packet_ref: "prod-1", name: "Draft Shirt", selling_price_cents: 2500 }] },
    }],
    change_requests: [{
      id: "change-1",
      packet_version: 2,
      category: "description",
      owner_comment: "Please mention Friday pickup.",
      status: "open",
    }],
    products: [{
      id: "prod-1",
      name: "Draft Shirt",
      status: "ready",
      public: false,
      revision: 3,
      product_type: "shirt",
      category_id: "cat-1",
      category_name: "Team Wear",
      selling_price_cents: 2500,
      launch_packet_eligible: true,
      launch_packet_include: true,
      customer_images: { primary: { file_id: "file-1", alt_text: "Shirt front" } },
      artwork_associations: [],
      mockup_associations: [],
    }],
  });
  getLaunchReadiness.mockResolvedValueOnce({
    ready: false,
    current_terms_version: "webstore_terms_2026_07",
    terms_acceptance: null,
    payment_readiness: { state: "not_configured" },
    payment_unavailable_reason: "Real verified provider checkout is not connected yet.",
    public_launch_blocked_until_batch_3: false,
    gates: [
      { key: "packet_delivered", state: "ready", reason: "Current packet version was delivered.", blocking: false, action: "Send the current packet version." },
      { key: "packet_approved", state: "blocked", reason: "Store Owner approval is required.", blocking: true, action: "Owner approves v2." },
      { key: "terms_current", state: "blocked", reason: "Store Owner must accept Terms version webstore_terms_2026_07.", blocking: true, action: "Owner accepts Terms." },
      { key: "buyer_commerce_connected", state: "ready", reason: "Public storefront, checkout, Orders, and Production handoff are connected.", blocking: false },
    ],
  });
  renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-1", path: "/webstores/:id" });

  await user.click(await screen.findByTestId("webstore-advanced-setup-toggle"));
  expect(await screen.findByTestId("webstore-readiness-gate-packet_delivered")).toHaveTextContent("Current packet version was delivered");
  expect(screen.getByTestId("webstore-readiness-gate-buyer_commerce_connected")).toHaveTextContent("connected");
  expect(screen.getByTestId("webstore-terms-readiness")).toHaveTextContent("Waiting on separate Store Owner Terms acceptance");
  expect(screen.getByTestId("webstore-launch-packet-summary")).toHaveTextContent("Version 2");
  expect(screen.getByTestId("webstore-qr-preview")).toHaveTextContent("/p/webstores/team-store-public");
  expect(screen.getByTestId("webstore-change-requests")).toHaveTextContent("Please mention Friday pickup");

  expect(screen.queryByTestId("webstore-intended-launch-at")).not.toBeInTheDocument();
  expect(screen.queryByTestId("webstore-intended-close-at")).not.toBeInTheDocument();
});

test("staff persisted product images prefer authenticated previews over public URLs after reload", async () => {
  const user = userEvent.setup();
  getWebstore.mockResolvedValue({
    webstore: {
      id: "ws-1",
      name: "Team Store",
      slug: "team-store",
      public_slug: "team-store-public",
      public_url: "/p/webstores/team-store-public",
      status: "draft",
      store_type: "general",
    },
    launch_packets: [],
    products: [
      {
        id: "prod-1",
        name: "Persisted Draft Shirt",
        status: "draft",
        public: false,
        revision: 4,
        product_type: "shirt",
        category_id: "cat-1",
        category_name: "Team Wear",
        selling_price_cents: 0,
        customer_images: {
          primary: { file_id: "file-1", alt_text: "Persisted primary" },
          secondary: { file_id: "file-3", alt_text: "Persisted secondary" },
        },
        images: [
          {
            slot: "primary",
            role: "primary",
            file_id: "file-1",
            url: "/api/public/webstores/team-store-public/product-images/prod-1/primary",
            preview_url: "/api/webstores/ws-1/setup-files/file-1/preview",
            alt_text: "Persisted primary",
          },
          {
            slot: "secondary",
            role: "secondary",
            file_id: "file-3",
            url: "/api/public/webstores/team-store-public/product-images/prod-1/secondary",
            preview_url: "/api/webstores/ws-1/setup-files/file-3/preview",
            alt_text: "Persisted secondary",
          },
        ],
        artwork_associations: [],
        mockup_associations: [],
      },
      {
        id: "prod-fallback",
        name: "Public Fallback Product",
        status: "active",
        public: true,
        revision: 1,
        product_type: "shirt",
        selling_price_cents: 0,
        customer_images: {},
        images: [
          {
            slot: "primary",
            role: "primary",
            url: "/api/public/webstores/team-store-public/product-images/prod-fallback/primary",
            alt_text: "Fallback primary",
          },
        ],
        artwork_associations: [],
        mockup_associations: [],
      },
    ],
  });

  renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-1", path: "/webstores/:id" });

  await screen.findByText(/Team Store/);
  await user.click(screen.getByRole("tab", { name: "Products" }));

  expect(screen.getByTestId("webstore-product-card-prod-1").querySelector("img")).toHaveAttribute("src", "/api/webstores/ws-1/setup-files/file-1/preview");
  expect(screen.getByTestId("webstore-product-card-prod-fallback").querySelector("img")).toHaveAttribute("src", "/api/public/webstores/team-store-public/product-images/prod-fallback/primary");

  await user.click(screen.getByTestId("webstore-product-row-prod-1"));
  await user.click(screen.getByRole("tab", { name: "Images and Mockups" }));

  const primary = screen.getByTestId("webstore-product-image-primary");
  const secondary = screen.getByTestId("webstore-product-image-secondary");
  expect(within(primary).getByRole("img", { name: "Persisted primary" })).toHaveAttribute("src", "/api/webstores/ws-1/setup-files/file-1/preview");
  expect(within(secondary).getByRole("img", { name: "Persisted secondary" })).toHaveAttribute("src", "/api/webstores/ws-1/setup-files/file-3/preview");
  expect(within(primary).getByDisplayValue("Persisted primary")).toBeInTheDocument();
  expect(within(secondary).getByDisplayValue("Persisted secondary")).toBeInTheDocument();

  await user.click(within(primary).getByTestId("webstore-product-image-primary-file"));
  await user.click(await screen.findByText("front-new.png"));
  expect(within(primary).getByRole("img", { name: "Persisted primary" })).toHaveAttribute("src", "/api/webstores/ws-1/setup-files/file-2/preview");
  expect(within(secondary).getByRole("img", { name: "Persisted secondary" })).toHaveAttribute("src", "/api/webstores/ws-1/setup-files/file-3/preview");

  await user.click(within(secondary).getByRole("button", { name: "Remove" }));
  expect(within(secondary).queryByRole("img")).not.toBeInTheDocument();
  expect(within(primary).getByRole("img", { name: "Persisted primary" })).toHaveAttribute("src", "/api/webstores/ws-1/setup-files/file-2/preview");

  await user.click(screen.getByRole("tab", { name: "Review Status" }));
  await user.click(screen.getByTestId("webstore-save-product"));
  await waitFor(() => expect(updateWebstoreProduct).toHaveBeenCalledWith("ws-1", "prod-1", expect.objectContaining({
    expected_revision: 4,
    customer_images: {
      primary: expect.objectContaining({
        file_id: "file-2",
        alt_text: "Persisted primary",
      }),
    },
  })));
  expect(updateWebstoreProduct.mock.calls[0][2].customer_images.secondary).toBeUndefined();
  expect(screen.getByTestId("webstore-product-card-prod-1")).toHaveTextContent("planned - private catalog");
});

test("staff product builder separates planning from focused product setup", async () => {
  const user = userEvent.setup();
  renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-1", path: "/webstores/:id" });

  expect(await screen.findByText(/Team Store/)).toBeInTheDocument();
  expect(screen.getByText(/Webstores setup/)).toBeInTheDocument();
  expect(screen.getByTestId("webstore-builder-progress")).toHaveTextContent("Webstores Feed");
  expect(screen.getByRole("tab", { name: "Storefront" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Review & Launch" })).toBeInTheDocument();

  await user.click(screen.getByRole("tab", { name: "Products" }));
  const plan = screen.getByTestId("webstore-product-plan");
  expect(plan).toHaveTextContent("Questionnaire Summary");
  expect(plan).toHaveTextContent("AI Product Suggestions");
  expect(plan).toHaveTextContent("No generated suggestions yet");
  expect(within(plan).getByRole("button", { name: "Ask AI for Another Suggestion" })).toBeDisabled();
  expect(within(plan).getByRole("button", { name: "Create Custom Product" })).toBeInTheDocument();
  expect(screen.queryByText(/Create Blank Product/i)).not.toBeInTheDocument();
  expect(screen.queryByTestId("webstore-create-template")).not.toBeInTheDocument();
  expect(screen.queryByTestId("webstore-create-category")).not.toBeInTheDocument();

  await user.click(within(plan).getByTestId("webstore-create-blank-product"));
  await waitFor(() => expect(createProductFromTemplate).toHaveBeenCalledWith("ws-1", { name: "New draft product", product_type: "general" }));

  await user.click(within(plan).getByTestId("webstore-stage4-template-select"));
  await user.click(await screen.findByRole("option", { name: "Tenant Shirt" }));
  await user.click(within(plan).getByTestId("webstore-add-template-draft"));
  await waitFor(() => expect(createProductFromTemplate).toHaveBeenCalledWith("ws-1", expect.objectContaining({ source_template_id: "tpl-tenant" })));

  expect(screen.getByTestId("webstore-product-foundation")).toHaveTextContent("Selected Products");
  expect(screen.getByTestId("webstore-product-card-prod-1")).toHaveTextContent("Continue Setup");
  expect(screen.getByTestId("webstore-product-card-prod-1")).toHaveTextContent("planned - private catalog");
  expect(screen.getByTestId("webstore-product-card-prod-1")).toHaveTextContent("not submitted");
  await user.click(within(screen.getByTestId("webstore-product-card-prod-1")).getByRole("button", { name: "Duplicate" }));
  await waitFor(() => expect(duplicateWebstoreProduct).toHaveBeenCalledWith("ws-1", "prod-1", expect.objectContaining({ expected_revision: 3 })));
  await user.click(within(screen.getByTestId("webstore-product-card-prod-1")).getByRole("button", { name: "Send Product Approval" }));
  await waitFor(() => expect(submitWebstoreProductApproval).toHaveBeenCalledWith("ws-1", "prod-1", expect.objectContaining({ expected_revision: 3 })));
  expect(screen.getByText(/Platform starter/)).toBeInTheDocument();
  expect(screen.getByText("Legacy free-text category preserved: Legacy / Unknown")).toBeInTheDocument();
  await user.click(screen.getByTestId("webstore-product-row-prod-1"));
  expect(screen.getByTestId("webstore-product-editor-sections")).toHaveTextContent("Basic Information");
  fireEvent.change(screen.getByTestId("webstore-product-name"), { target: { value: "Updated Draft Shirt" } });
  await user.click(screen.getByRole("tab", { name: "Pricing and Shares" }));
  fireEvent.change(screen.getByTestId("webstore-product-selling-price"), { target: { value: "2500" } });
  fireEvent.change(screen.getByTestId("webstore-product-production-cost"), { target: { value: "900" } });
  fireEvent.change(screen.getByTestId("webstore-product-owner-share"), { target: { value: "300" } });
  await user.click(screen.getByRole("tab", { name: "Options and Personalization" }));
  fireEvent.change(screen.getByTestId("webstore-product-sku"), { target: { value: "TEAM-SHIRT" } });
  await user.click(screen.getByRole("button", { name: "Add Variant" }));
  fireEvent.change(screen.getByTestId("webstore-variant-size-0"), { target: { value: "L" } });
  fireEvent.change(screen.getByTestId("webstore-variant-color-0"), { target: { value: "Black" } });
  fireEvent.change(screen.getByTestId("webstore-variant-sku-0"), { target: { value: "TEAM-SHIRT-L-BLK" } });
  fireEvent.change(screen.getByTestId("webstore-variant-price-0"), { target: { value: "2600" } });
  await user.click(screen.getByTestId("webstore-add-personalization"));
  fireEvent.change(screen.getByTestId("webstore-personalization-label-0"), { target: { value: "Player name" } });
  await user.click(screen.getByRole("tab", { name: "Review Status" }));
  await user.click(screen.getByTestId("webstore-product-packet-eligible"));
  await user.click(screen.getByTestId("webstore-product-packet-include"));
  await user.click(screen.getByTestId("webstore-product-artwork-associations"));
  await user.click(await screen.findByText("artwork.png"));
  await user.click(screen.getByTestId("webstore-product-artwork-associations"));
  await user.click(await screen.findByText("artwork-2.png"));
  await user.click(screen.getByTestId("webstore-product-mockup-associations"));
  await user.click(await screen.findByText("Mockup preview"));
  await user.click(screen.getByRole("button", { name: "Send Mockup Approval" }));
  await waitFor(() => expect(submitWebstoreMockupApproval).toHaveBeenCalledWith("ws-1", "mock-1"));
  await user.click(screen.getByTestId("webstore-save-product"));
  await waitFor(() => expect(updateWebstoreProduct).toHaveBeenCalledWith("ws-1", "prod-1", expect.objectContaining({
    expected_revision: 3,
    name: "Updated Draft Shirt",
    sku: "TEAM-SHIRT",
    selling_price_cents: 2500,
    production_cost_cents: 900,
    store_owner_share_cents: 300,
    variants: [expect.objectContaining({ size: "L", color: "Black", sku: "TEAM-SHIRT-L-BLK", selling_price_cents: 2600 })],
    personalization_enabled: true,
    personalization_fields: [expect.objectContaining({ label: "Player name", type: "text" })],
    launch_packet_eligible: true,
    launch_packet_include: true,
    artwork_associations: [{ artwork_id: "art-1" }, { artwork_id: "art-2" }],
    mockup_associations: [{ mockup_id: "mock-1" }],
  })));

  await user.click(within(screen.getByTestId("webstore-category-resources")).getByRole("button", { name: "Edit" }));
  await user.click(screen.getByTestId("webstore-save-category"));
  await waitFor(() => expect(updateWebstoreProductCategory).toHaveBeenCalledWith("ws-1", "cat-1", expect.objectContaining({ expected_revision: 4 })));

  await user.click(within(screen.getByTestId("webstore-product-card-prod-1")).getByRole("button", { name: "Archive" }));
  await waitFor(() => expect(archiveWebstoreProduct).toHaveBeenCalledWith("ws-1", "prod-1", expect.objectContaining({ expected_revision: 3 })));
  await user.click(within(screen.getByTestId("webstore-product-card-prod-archived")).getByRole("button", { name: "Restore" }));
  await waitFor(() => expect(restoreWebstoreProduct).toHaveBeenCalledWith("ws-1", "prod-archived", expect.objectContaining({ expected_revision: 5 })));
});

test("stale product saves keep the editor open and offer a reload action", async () => {
  const user = userEvent.setup();
  updateWebstoreProduct.mockRejectedValueOnce({ response: { data: { detail: "This product changed after you opened it. Reload it before saving." } } });
  renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-1", path: "/webstores/:id" });

  await screen.findByText(/Team Store/);
  await user.click(screen.getByRole("tab", { name: "Products" }));
  await user.click(screen.getByTestId("webstore-product-row-prod-1"));
  fireEvent.change(screen.getByTestId("webstore-product-name"), { target: { value: "Updated Draft Shirt" } });
  await user.click(screen.getByRole("tab", { name: "Review Status" }));
  await user.click(screen.getByTestId("webstore-save-product"));

  expect(await screen.findByText("Product was not saved")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reload latest product data" })).toBeInTheDocument();
  expect(updateWebstoreProduct).toHaveBeenCalledWith("ws-1", "prod-1", expect.objectContaining({ expected_revision: 3 }));
});
