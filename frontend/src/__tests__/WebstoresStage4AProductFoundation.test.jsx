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
  generateLaunchPacket,
  getLaunchReadiness,
  getWebstore,
  getWebstoreBranding,
  getWebstoreQuestionnaire,
  getWebstoreQuestionnaireResponse,
  getWebstoreReports,
  getWebstoreSetupProgress,
  listProductTemplates,
  listWebstoreArtwork,
  listWebstoreAssignments,
  listWebstoreMockups,
  listWebstoreProductCategories,
  listWebstoreSetupFiles,
  previewWebstoreAnswerApplication,
  resendWebstoreInvitation,
  restoreProductTemplate,
  restoreWebstoreProduct,
  restoreWebstoreProductCategory,
  reverseWebstoreAnswerApplication,
  sendLaunchPacket,
  setWebstoreStatus,
  updateProductTemplate,
  updateWebstore,
  updateWebstoreProduct,
  updateWebstoreProductCategory,
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
  generateLaunchPacket: jest.fn(),
  getLaunchReadiness: jest.fn(),
  getWebstore: jest.fn(),
  getWebstoreBranding: jest.fn(),
  getWebstoreQuestionnaire: jest.fn(),
  getWebstoreQuestionnaireResponse: jest.fn(),
  getWebstoreReports: jest.fn(),
  getWebstoreSetupProgress: jest.fn(),
  listProductTemplates: jest.fn(),
  listWebstoreArtwork: jest.fn(),
  listWebstoreAssignments: jest.fn(),
  listWebstoreMockups: jest.fn(),
  listWebstoreProductCategories: jest.fn(),
  listWebstoreSetupFiles: jest.fn(),
  previewWebstoreAnswerApplication: jest.fn(),
  resendWebstoreInvitation: jest.fn(),
  restoreProductTemplate: jest.fn(),
  restoreWebstoreProduct: jest.fn(),
  restoreWebstoreProductCategory: jest.fn(),
  reverseWebstoreAnswerApplication: jest.fn(),
  sendLaunchPacket: jest.fn(),
  setWebstoreStatus: jest.fn(),
  updateProductTemplate: jest.fn(),
  updateWebstore: jest.fn(),
  updateWebstoreProduct: jest.fn(),
  updateWebstoreProductCategory: jest.fn(),
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
        customer_images: { primary: { file_id: "file-1", alt_text: "Shirt front" } },
        artwork_associations: [],
        mockup_associations: [],
        template_provenance: { source_template_id: "tpl-tenant", source_template_revision: 1 },
      },
    ],
  });
  getLaunchReadiness.mockResolvedValue({ ready: false, checks: { payment_ready: false }, payment_unavailable_reason: "Real verified provider checkout is not connected yet." });
  getWebstoreReports.mockResolvedValue({ order_count: 0, gross_sales_cents: 0, ledger_totals_cents: {} });
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
});

test("staff product image picker previews selected files before save", async () => {
  const user = userEvent.setup();
  renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-1", path: "/webstores/:id" });

  await screen.findByText("Team Store");
  await user.click(screen.getByRole("tab", { name: "Products" }));
  await user.click(screen.getByTestId("webstore-product-row-prod-1"));

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

  await user.click(screen.getByTestId("webstore-save-product"));
  await waitFor(() => expect(updateWebstoreProduct).toHaveBeenCalledWith("ws-1", "prod-1", expect.objectContaining({
    expected_revision: 3,
    customer_images: {
      primary: expect.objectContaining({
        file_id: "file-2",
        url: "/api/webstores/ws-1/setup-files/file-2/preview",
      }),
    },
  })));
});

test("staff product foundation tab manages drafts, templates, categories, and asset associations", async () => {
  const user = userEvent.setup();
  renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-1", path: "/webstores/:id" });

  expect(await screen.findByText("Team Store")).toBeInTheDocument();
  await user.click(screen.getByRole("tab", { name: "Products" }));

  expect(screen.getByTestId("webstore-product-foundation")).toBeInTheDocument();
  expect(screen.getByText(/Platform starter/)).toBeInTheDocument();
  expect(screen.getByText("Legacy free-text category preserved: Legacy / Unknown")).toBeInTheDocument();

  await user.click(screen.getByTestId("webstore-create-blank-product"));
  await waitFor(() => expect(createProductFromTemplate).toHaveBeenCalledWith("ws-1", { name: "New draft product", product_type: "general" }));

  fireEvent.change(screen.getByTestId("webstore-category-name"), { target: { value: "Spirit Wear" } });
  await user.click(screen.getByTestId("webstore-create-category"));
  await waitFor(() => expect(createWebstoreProductCategory).toHaveBeenCalledWith("ws-1", { name: "Spirit Wear", description: "" }));

  await user.click(screen.getByTestId("webstore-product-row-prod-1"));
  await user.click(screen.getByTestId("webstore-product-artwork-associations"));
  await user.click(await screen.findByText("artwork.png"));
  await user.click(screen.getByTestId("webstore-product-artwork-associations"));
  await user.click(await screen.findByText("artwork-2.png"));
  await user.click(screen.getByTestId("webstore-product-mockup-associations"));
  await user.click(await screen.findByText("Mockup preview"));
  fireEvent.change(screen.getByTestId("webstore-product-name"), { target: { value: "Updated Draft Shirt" } });
  await user.click(screen.getByTestId("webstore-save-product"));
  await waitFor(() => expect(updateWebstoreProduct).toHaveBeenCalledWith("ws-1", "prod-1", expect.objectContaining({
    expected_revision: 3,
    name: "Updated Draft Shirt",
    artwork_associations: [{ artwork_id: "art-1" }, { artwork_id: "art-2" }],
    mockup_associations: [{ mockup_id: "mock-1" }],
  })));

  await user.click(screen.getAllByRole("button", { name: "Edit" })[0]);
  await user.click(screen.getByTestId("webstore-save-template"));
  await waitFor(() => expect(updateProductTemplate).toHaveBeenCalledWith("tpl-tenant", expect.objectContaining({ expected_revision: 2 })));

  await user.click(screen.getAllByRole("button", { name: "Edit" })[1]);
  await user.click(screen.getByTestId("webstore-save-category"));
  await waitFor(() => expect(updateWebstoreProductCategory).toHaveBeenCalledWith("ws-1", "cat-1", expect.objectContaining({ expected_revision: 4 })));
});
