import "@testing-library/jest-dom";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import { renderWithProviders } from "../test-utils";
import PublicWebstorePage from "@/pages/PublicWebstorePage";
import { WebstoreBrandingPreview } from "@/components/webstores/WebstoreBranding";
import WebstoreDetailPage from "@/pages/WebstoreDetailPage";
import WebstoreOwnerPortalPage from "@/pages/WebstoreOwnerPortalPage";
import {
  getLaunchReadiness,
  getWebstore,
  getWebstoreBranding,
  getWebstoreQuestionnaire,
  getWebstoreQuestionnaireResponse,
  getWebstoreReports,
  getWebstoreSetupProgress,
  listProductTemplates,
  listWebstoreAssignments,
  listWebstoreSetupFiles,
  publishWebstoreBranding,
  requestWebstoreBrandingReview,
  saveWebstoreBrandingDraft,
  uploadWebstoreSetupFile,
} from "@/lib/webstores";
import portalApi from "@/portal/portalApi";

jest.mock("axios", () => ({ get: jest.fn(), post: jest.fn() }));

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

jest.mock("@/lib/webstores", () => ({
  getLaunchReadiness: jest.fn(),
  getWebstore: jest.fn(),
  getWebstoreBranding: jest.fn(),
  getWebstoreQuestionnaire: jest.fn(),
  getWebstoreQuestionnaireResponse: jest.fn(),
  getWebstoreReports: jest.fn(),
  getWebstoreSetupProgress: jest.fn(),
  listProductTemplates: jest.fn(),
  listWebstoreAssignments: jest.fn(),
  listWebstoreSetupFiles: jest.fn(),
  publishWebstoreBranding: jest.fn(),
  requestWebstoreBrandingReview: jest.fn(),
  saveWebstoreBrandingDraft: jest.fn(),
  uploadWebstoreSetupFile: jest.fn(),
  createProductFromTemplate: jest.fn(),
  createWebstoreAssignment: jest.fn(),
  applyWebstoreAnswers: jest.fn(),
  previewWebstoreAnswerApplication: jest.fn(),
  resendWebstoreInvitation: jest.fn(),
  revokeWebstoreAssignment: jest.fn(),
  reverseWebstoreAnswerApplication: jest.fn(),
  sendLaunchPacket: jest.fn(),
  setWebstoreStatus: jest.fn(),
  updateWebstore: jest.fn(),
}));

jest.mock("@/components/ai/AIContextualActions", () => () => <div data-testid="ai-actions" />);
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));

const draft = {
  brand_basics: {
    display_name: "Team Store",
    tagline: "Team gear",
    primary_logo: { url: "https://assets.example.test/logo.png", alt_text: "Team logo" },
    alternate_logo: { url: "https://assets.example.test/logo-dark.webp", alt_text: "Team logo dark" },
    favicon: { url: "https://assets.example.test/favicon.svg", alt_text: "Team icon" },
    social_image: { url: "https://assets.example.test/social.jpg", alt_text: "Social preview" },
  },
  colors_fonts: { primary_color: "#123456", secondary_color: "#1e293b", accent_color: "#22c55e", page_background_color: "#ffffff", main_text_color: "#111827", button_background_color: "#2563eb", button_text_color: "#ffffff", button_corner_style: "rounded", heading_font: "serif", body_font: "system" },
  header: { show_header: true, display_mode: "both", logo_size: "large", background_color: "#ffffff", announcement_enabled: true, announcement_text: "Order by Friday", announcement_link_destination: "catalog" },
  hero: { show_hero: true, image: { url: "https://assets.example.test/hero.webp", alt_text: "Hero artwork" }, image_focal_position: "right", overlay_color: "#000000", headline: "Shop the team store", supporting_text: "Approved gear", primary_button_enabled: true, primary_button_label: "Shop products", primary_button_destination: "catalog" },
  store_information: { show_section: true, welcome_heading: "Welcome", welcome_text: "Order by Friday.", supporting_image: { url: "https://assets.example.test/info.png", alt_text: "Info image" }, store_instructions: "Pick up on campus.", contact_display: "store" },
  store_type_content: { general_welcome: "Welcome shoppers.", about_store: "Open team store.", shopping_instructions: "Pick your items." },
  catalog_introduction: { show_catalog_area: true, heading: "Products", introduction: "Browse approved products.", background_color: "#ffffff" },
  footer: { show_footer: true, background_color: "#0f172a", text_color: "#ffffff", display_mode: "store_name", message: "Questions? Contact us.", show_contact: true, show_social_links: true, show_policy_links: true, show_powered_by: true },
};

function brandingResponse(overrides = {}) {
  return {
    webstore: { id: "ws-1", name: "Team Store", store_type: "general", status: "draft", setup_state: "setup_complete" },
    branding: { status: "draft", draft, validation: { errors: [], warnings: [] }, ...overrides.branding },
    permissions: { can_save_draft: true, can_request_review: true, can_publish: true, can_control_whole_sections: true, ...overrides.permissions },
    history: overrides.history || [],
    activity: overrides.activity || [],
  };
}

beforeEach(() => {
  jest.clearAllMocks();
  window.HTMLElement.prototype.hasPointerCapture = window.HTMLElement.prototype.hasPointerCapture || (() => false);
  window.HTMLElement.prototype.setPointerCapture = window.HTMLElement.prototype.setPointerCapture || (() => {});
  window.HTMLElement.prototype.releasePointerCapture = window.HTMLElement.prototype.releasePointerCapture || (() => {});
  window.HTMLElement.prototype.scrollIntoView = window.HTMLElement.prototype.scrollIntoView || (() => {});
  global.URL.createObjectURL = jest.fn(() => "blob:branding-preview");
  getWebstore.mockResolvedValue({
    webstore: { id: "ws-1", name: "Team Store", slug: "team-store", public_slug: "shop-team-store", public_url: "/p/webstores/shop-team-store", store_type: "general", status: "draft", setup_state: "setup_complete" },
    launch_packets: [],
    products: [{ id: "prod-1", name: "Team Shirt", selling_price_cents: 2500, status: "active", public: true }],
  });
  getLaunchReadiness.mockResolvedValue({ ready: false, checks: { payment_ready: false }, payment_unavailable_reason: "Real verified provider checkout is not connected yet." });
  getWebstoreReports.mockResolvedValue({ order_count: 0, gross_sales_cents: 0, ledger_totals_cents: {} });
  getWebstoreSetupProgress.mockResolvedValue({ setup_state: "setup_complete", steps: [] });
  listWebstoreAssignments.mockResolvedValue([]);
  getWebstoreQuestionnaire.mockResolvedValue({ templates: [] });
  getWebstoreQuestionnaireResponse.mockResolvedValue({ submission: null });
  listWebstoreSetupFiles.mockResolvedValue([]);
  listProductTemplates.mockResolvedValue([]);
  getWebstoreBranding.mockResolvedValue(brandingResponse());
  saveWebstoreBrandingDraft.mockResolvedValue(brandingResponse());
  requestWebstoreBrandingReview.mockResolvedValue(brandingResponse({ branding: { status: "waiting_owner_approval" } }));
  publishWebstoreBranding.mockResolvedValue(brandingResponse({ branding: { status: "published" }, history: [{ id: "v1", version: 1 }] }));
  uploadWebstoreSetupFile.mockResolvedValue({ file: { id: "file-1", file_name: "logo.png", detected_content_type: "image/png" } });
});

test("staff Branding tab exposes category cards, preview modes, and ribbon actions", async () => {
  const user = userEvent.setup();
  renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-1", path: "/webstores/:id" });

  await user.click(await screen.findByRole("tab", { name: /Branding/ }));
  expect(await screen.findByTestId("webstore-branding-editor")).toBeInTheDocument();
  expect(screen.getByTestId("branding-category-cards")).toHaveTextContent("Brand Basics");
  expect(screen.getByTestId("branding-category-cards")).toHaveTextContent("Footer");
  await user.click(screen.getByText("Colors & Fonts"));
  fireEvent.change(screen.getByTestId("branding-field-colors_fonts.primary_color"), { target: { value: "#123456" } });
  await user.click(screen.getByRole("button", { name: /Save Draft/ }));
  await waitFor(() => expect(saveWebstoreBrandingDraft).toHaveBeenCalled());
  await user.click(screen.getByRole("button", { name: /^Mobile$/ }));
  expect(screen.getByTestId("branding-mobile-preview")).toHaveTextContent("Draft Preview");
  await user.click(screen.getByRole("button", { name: /Request Owner Review/ }));
  await waitFor(() => expect(requestWebstoreBrandingReview).toHaveBeenCalledWith("ws-1", ""));
});

test("branding images can be uploaded, immediately previewed, replaced, removed, and locally validated", async () => {
  const user = userEvent.setup();
  renderWithProviders(<WebstoreDetailPage />, { route: "/webstores/ws-1", path: "/webstores/:id" });

  await user.click(await screen.findByRole("tab", { name: /Branding/ }));
  const uploadedLogo = new File(["logo"], "replacement-logo.png", { type: "image/png" });
  fireEvent.change(screen.getByTestId("branding-upload-primary-logo"), { target: { files: [uploadedLogo] } });
  await waitFor(() => expect(uploadWebstoreSetupFile).toHaveBeenCalled());
  await waitFor(() => expect(screen.getByTestId("branding-image-primary-logo")).toHaveValue("blob:branding-preview"));
  expect(screen.getAllByAltText("Team logo").some((img) => img.getAttribute("src") === "blob:branding-preview")).toBe(true);

  fireEvent.change(screen.getByTestId("branding-image-primary-logo"), { target: { value: "https://assets.example.test/replacement.webp" } });
  expect(screen.getByTestId("branding-image-primary-logo")).toHaveValue("https://assets.example.test/replacement.webp");
  await user.click(screen.getByTestId("branding-remove-primary-logo"));
  expect(screen.getByTestId("branding-image-primary-logo")).toHaveValue("");

  await user.click(screen.getByText("Hero Section"));
  const svgHero = new File(["<svg />"], "hero.svg", { type: "image/svg+xml" });
  fireEvent.change(screen.getByTestId("branding-upload-hero-image"), { target: { files: [svgHero] } });
  expect(await screen.findByText(/SVG for logos only/)).toBeInTheDocument();
});

test("public storefront renders only published branding from the public response", async () => {
  axios.get.mockResolvedValue({
    data: {
      webstore: { id: "ws-1", name: "Team Store", branding: { ...draft, brand_basics: { ...draft.brand_basics, display_name: "Published Team Store" } }, checkout_unavailable_reason: "Real Webstore checkout is not connected yet." },
      products: [{ id: "prod-1", name: "Published Shirt", selling_price_cents: 2500 }],
    },
  });
  renderWithProviders(<PublicWebstorePage />, { route: "/p/webstores/shop-team-store", path: "/p/webstores/:slug" });

  await waitFor(() => expect(screen.getAllByText("Published Team Store").length).toBeGreaterThan(0));
  expect(screen.getByTestId("branding-preview-catalog")).toHaveTextContent("Published Shirt");
  expect(screen.getByTestId("branding-preview-announcement")).toHaveTextContent("Order by Friday");
  expect(screen.getByTestId("branding-preview-hero")).toHaveStyle({ backgroundPosition: "right center" });
  expect(screen.getByAltText("Info image")).toHaveAttribute("src", "https://assets.example.test/info.png");
  expect(screen.getByTestId("branding-preview-footer")).toHaveTextContent("Social links will display when configured.");
  expect(screen.queryByText(/Owner Approved/)).not.toBeInTheDocument();
});

test("public storefront omits disabled branded sections and handles missing optional content", async () => {
  const hiddenBranding = {
    ...draft,
    header: { ...draft.header, show_header: false },
    hero: { ...draft.hero, show_hero: false },
    catalog_introduction: { ...draft.catalog_introduction, show_catalog_area: false },
    store_information: { show_section: true, welcome_heading: "Welcome", welcome_text: "" },
  };
  axios.get.mockResolvedValue({
    data: {
      webstore: { id: "ws-1", name: "Team Store", branding: hiddenBranding, checkout_unavailable_reason: "Real Webstore checkout is not connected yet." },
      products: [],
    },
  });
  renderWithProviders(<PublicWebstorePage />, { route: "/p/webstores/shop-team-store", path: "/p/webstores/:slug" });

  await waitFor(() => expect(screen.queryByTestId("branding-preview-header")).not.toBeInTheDocument());
  expect(screen.queryByTestId("branding-preview-hero")).not.toBeInTheDocument();
  expect(screen.queryByTestId("branding-preview-catalog")).not.toBeInTheDocument();
  expect(await screen.findByTestId("branding-preview-store-information")).toHaveTextContent("Welcome");
});

test.each([
  ["b2b", { business_welcome: "Welcome purchasing team", ordering_instructions: "Use your account." }, "B2B"],
  ["fundraiser", { campaign_message: "Support the boosters.", organization_name: "Boosters", show_goal_progress: true }, "Fundraiser"],
  ["event", { event_message: "Pick up at the event.", event_display_name: "Summer Classic", show_location: true }, "Event"],
  ["promotional", { campaign_message: "Limited promo.", offer_wording: "Order today.", show_deadline: true }, "Promotional"],
  ["employee", { company_welcome: "Employee gear", employee_ordering_instructions: "Use employee pickup." }, "Employee Store"],
  ["general", { general_welcome: "Welcome shoppers.", about_store: "Open store." }, "General Store"],
])("preview renders %s store-type presentation without commerce behavior", (storeType, content, label) => {
  renderWithProviders(
    <WebstoreBrandingPreview branding={{ ...draft, store_type_content: content }} webstore={{ id: "ws-1", name: "Type Store", store_type: storeType }} products={[]} draft />,
  );
  expect(screen.getByTestId(`branding-preview-type-${storeType}`)).toHaveTextContent(label);
});

test("owner portal can approve submitted branding but cannot publish", async () => {
  portalApi.get.mockImplementation((url) => {
    if (url.endsWith("/branding")) return Promise.resolve({ data: brandingResponse({
      branding: { status: "waiting_owner_approval", feedback_note: "Use the blue logo" },
      permissions: { can_publish: false, can_owner_decide: true, can_request_review: false, can_control_whole_sections: false },
      activity: [{ id: "act-1", summary: "Changes requested", actor_email: "owner@example.com", created_at: "2026-01-01T00:00:00Z", metadata: { note: "Use the blue logo" } }],
    }) });
    if (url.endsWith("/questionnaire")) return Promise.resolve({ data: { templates: [] } });
    if (url.endsWith("/setup-progress")) return Promise.resolve({ data: { setup_state: "setup_complete", steps: [] } });
    if (url.endsWith("/setup-files")) return Promise.resolve({ data: { items: [] } });
    return Promise.resolve({ data: { webstore: { id: "ws-1", name: "Team Store", status: "draft", setup_state: "setup_complete" }, products: [], launch_packet: null } });
  });
  portalApi.post.mockResolvedValue({ data: brandingResponse({ branding: { status: "owner_approved" } }) });

  renderWithProviders(<WebstoreOwnerPortalPage />, { route: "/portal/webstores/ws-1", path: "/portal/webstores/:webstoreId" });

  const editor = await screen.findByTestId("webstore-branding-editor");
  expect(within(editor).queryByRole("button", { name: /Publish/ })).not.toBeInTheDocument();
  expect(within(editor).getByTestId("branding-feedback")).toHaveTextContent("Use the blue logo");
  expect(within(editor).getByTestId("branding-activity")).toHaveTextContent("owner@example.com");
  await userEvent.click(within(editor).getByRole("button", { name: /Approve/ }));
  await waitFor(() => expect(portalApi.post).toHaveBeenCalledWith("/portal/webstores/ws-1/branding/approve", { note: "" }));
});

test("owner portal separates packet approval, change requests, and Terms acceptance", async () => {
  portalApi.get.mockImplementation((url) => {
    if (url.endsWith("/branding")) return Promise.resolve({ data: brandingResponse({ permissions: { can_publish: false, can_owner_decide: false } }) });
    if (url.endsWith("/questionnaire")) return Promise.resolve({ data: { templates: [] } });
    if (url.endsWith("/setup-progress")) return Promise.resolve({ data: { setup_state: "setup_complete", steps: [] } });
    if (url.endsWith("/setup-files")) return Promise.resolve({ data: { items: [] } });
    return Promise.resolve({ data: {
      webstore: { id: "ws-1", name: "Team Store", status: "sent_for_approval", setup_state: "setup_complete" },
      products: [],
      current_terms_version: "webstore_terms_2026_07",
      terms_acceptance: null,
      readiness_summary: [
        { key: "packet_approval", state: "waiting", owner_wording: "Packet approval is still needed." },
        { key: "terms", state: "waiting", owner_wording: "Terms version webstore_terms_2026_07 still needs acceptance." },
      ],
      launch_packet: {
        id: "packet-2",
        version: 2,
        status: "delivered",
        delivery_status: "test_capture_unavailable",
        promotion_copy: "Review the launch packet.",
        snapshot: { products: [{ packet_ref: "prod-1", name: "Team Shirt", description: "Cotton tee", selling_price_cents: 2500 }] },
      },
      change_requests: [],
    } });
  });
  portalApi.post.mockResolvedValue({ data: {} });

  renderWithProviders(<WebstoreOwnerPortalPage />, { route: "/portal/webstores/ws-1", path: "/portal/webstores/:webstoreId" });

  expect(await screen.findByTestId("portal-launch-packet-products")).toHaveTextContent("Team Shirt");
  expect(screen.getByTestId("portal-readiness-summary")).toHaveTextContent("Packet approval is still needed");
  await userEvent.click(screen.getByTestId("portal-approve-packet"));
  await waitFor(() => expect(portalApi.post).toHaveBeenCalledWith("/portal/webstores/ws-1/launch-packets/packet-2/approve"));

  await userEvent.type(screen.getByTestId("portal-change-request-comment"), "Please use the navy mockup.");
  await userEvent.click(screen.getByTestId("portal-request-changes"));
  await waitFor(() => expect(portalApi.post).toHaveBeenCalledWith(
    "/portal/webstores/ws-1/launch-packets/packet-2/request-changes",
    expect.objectContaining({ category: "general", comment: "Please use the navy mockup." }),
  ));

  expect(screen.getByTestId("portal-terms-version")).toHaveTextContent("webstore_terms_2026_07");
  await userEvent.click(screen.getByTestId("portal-accept-terms"));
  await waitFor(() => expect(portalApi.post).toHaveBeenCalledWith("/portal/webstores/ws-1/terms/accept", { terms_version: "webstore_terms_2026_07" }));
});
