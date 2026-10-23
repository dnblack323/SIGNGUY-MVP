import "@testing-library/jest-dom";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";
import WebstoreOwnerPortalPage from "@/pages/WebstoreOwnerPortalPage";
import portalApi from "@/portal/portalApi";

jest.mock("@/portal/portalApi", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
  },
  portalExtractError: (error) => error?.response?.data?.detail || error?.message || "Request failed",
}));

jest.mock("@/components/webstores/WebstoreBranding", () => ({ products }) => (
  <div data-testid="portal-branding" data-product-ids={(products || []).map((p) => p.id).join(",")} />
));
jest.mock("@/components/decisionRoom/DecisionRoomMedia", () => ({
  DecisionRoomMedia: ({ src, authToken, alt }) => <img src={src} alt={alt} data-testid="authenticated-product-media" data-has-token={Boolean(authToken)} />,
}));

jest.mock("sonner", () => ({
  toast: {
    error: jest.fn(),
    success: jest.fn(),
  },
}));

beforeEach(() => {
  jest.clearAllMocks();
  portalApi.get.mockImplementation((url) => {
    if (url.endsWith("/questionnaire")) return Promise.resolve({ data: { templates: [] } });
    if (url.endsWith("/setup-progress")) return Promise.resolve({ data: { setup_state: "setup_in_progress", steps: [] } });
    if (url.endsWith("/setup-files")) return Promise.resolve({ data: { items: [] } });
    return Promise.resolve({
      data: {
        webstore: { id: "ws-1", name: "Team Store", status: "draft" },
        products: [
          {
            id: "prod-1",
            name: "Approval Shirt",
            description: "Owner review shirt",
            selling_price_cents: 2500,
            approval_status: "pending_owner_approval",
            images: [],
            mockups: [
              {
                id: "mock-1",
                alt_text: "Front mockup",
                approval_status: "pending_owner_approval",
              },
            ],
          },
        ],
      },
    });
  });
  portalApi.post.mockResolvedValue({ data: {} });
});

test("owner portal records product and mockup approval decisions separately from launch approval", async () => {
  const user = userEvent.setup();
  renderWithProviders(<WebstoreOwnerPortalPage />, { route: "/portal/webstores/ws-1", path: "/portal/webstores/:webstoreId" });
  await user.click(await screen.findByRole("tab", { name: "Store Setup" }));

  expect(await screen.findByText("Approval Shirt")).toBeInTheDocument();
  const product = screen.getByText("Approval Shirt").closest(".grid");
  expect(product).toHaveTextContent("pending owner approval");
  expect(product).toHaveTextContent("Front mockup");

  await user.click(within(product).getByRole("button", { name: "Approve Product" }));
  await waitFor(() =>
    expect(portalApi.post).toHaveBeenCalledWith(
      "/portal/webstores/ws-1/products/prod-1/approval",
      { decision: "approve", comment: "" },
    ),
  );

  await user.type(within(product).getByTestId("portal-product-approval-comment-prod-1"), "Use the blue version.");
  await user.click(within(product).getAllByRole("button", { name: "Request Changes" }).at(-1));
  await waitFor(() =>
    expect(portalApi.post).toHaveBeenCalledWith(
      "/portal/webstores/ws-1/products/prod-1/approval",
      { decision: "request_changes", comment: "Use the blue version." },
    ),
  );

  await user.click(within(product).getByRole("button", { name: "Approve Mockup" }));
  await waitFor(() =>
    expect(portalApi.post).toHaveBeenCalledWith(
      "/portal/webstores/ws-1/mockups/mock-1/approval",
      { decision: "approve", comment: expect.any(String) },
    ),
  );
  expect(portalApi.post).not.toHaveBeenCalledWith(expect.stringContaining("launch-packets"), expect.anything());
});

test.each([false, true])("owner product list and branding consume the same submitted projection: visible=%s", async (visible) => {
  const notice = "Showing the last submitted version. The shop is preparing an update.";
  const products = visible ? [{ id: "shared-hat", name: "Submitted Hat", selling_price_cents: 3200,
    approval_status: "superseded", review_notice: notice, approval_history: [{ id: "a1", action: "approve" }] }] : [];
  portalApi.get.mockImplementation((url) => {
    if (url.endsWith("/questionnaire")) return Promise.resolve({ data: { templates: [] } });
    if (url.endsWith("/setup-progress")) return Promise.resolve({ data: { steps: [] } });
    if (url.endsWith("/setup-files")) return Promise.resolve({ data: { items: [] } });
    return Promise.resolve({ data: { webstore: { id: "ws-1", name: "Team Store", status: "draft" }, products } });
  });
  renderWithProviders(<WebstoreOwnerPortalPage />, { route: "/portal/webstores/ws-1", path: "/portal/webstores/:webstoreId" });
  await userEvent.click(await screen.findByRole("tab", { name: "Store Setup" }));
  expect(await screen.findByTestId("portal-branding")).toHaveAttribute("data-product-ids", visible ? "shared-hat" : "");
  if (visible) {
    expect(screen.getByText("Submitted Hat")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(notice);
    expect(screen.getByText(/approve - No comment/)).toBeInTheDocument();
  } else {
    expect(screen.getByText("No product previews are available yet.")).toBeInTheDocument();
  }
  expect(screen.queryByRole("button", { name: "Approve Product" })).not.toBeInTheDocument();
});

test.each([false, true])("only protected submitted media uses the authenticated renderer: managed=%s", async (managed) => {
  localStorage.setItem("sg_portal_token", "test-owner-token");
  portalApi.get.mockImplementation((url) => {
    if (url.endsWith("/questionnaire")) return Promise.resolve({ data: { templates: [] } });
    if (url.endsWith("/setup-progress")) return Promise.resolve({ data: { steps: [] } });
    if (url.endsWith("/setup-files")) return Promise.resolve({ data: { items: [] } });
    return Promise.resolve({ data: { webstore: { id: "ws-1", name: "Team Store" }, products: [{
      id: "shared-hat", name: "Submitted Hat", approval_status: "approved", selling_price_cents: 3200,
      images: [{ url: managed ? "/api/portal/webstores/ws-1/products/shared-hat/images/primary?revision=2" : "https://example.com/shared.png", owner_review_media: managed }],
    }] } });
  });
  renderWithProviders(<WebstoreOwnerPortalPage />, { route: "/portal/webstores/ws-1", path: "/portal/webstores/:webstoreId" });
  await userEvent.click(await screen.findByRole("tab", { name: "Store Setup" }));
  if (managed) expect(screen.getByTestId("authenticated-product-media")).toHaveAttribute("data-has-token", "true");
  else expect(screen.queryByTestId("authenticated-product-media")).not.toBeInTheDocument();
  localStorage.removeItem("sg_portal_token");
});

test("owner portal shows launch packet preview and submits explicit rejection comment", async () => {
  const user = userEvent.setup();
  portalApi.get.mockImplementation((url) => {
    if (url.endsWith("/questionnaire")) return Promise.resolve({ data: { templates: [] } });
    if (url.endsWith("/setup-progress")) return Promise.resolve({ data: { setup_state: "setup_complete", steps: [] } });
    if (url.endsWith("/setup-files")) return Promise.resolve({ data: { items: [] } });
    return Promise.resolve({
      data: {
        webstore: { id: "ws-1", name: "Team Store", status: "sent_for_approval" },
        products: [],
        launch_packet: {
          id: "packet-1",
          version: 3,
          status: "delivered",
          delivery_status: "sent",
          promotion_copy: "Please review the final launch packet.",
          snapshot: {
            owner_preview: {
              display_name: "Team Store",
              headline: "Team Store Launch",
              greeting: "Pickup at the front office.",
              accent_color: "#2563eb",
            },
            qr_reference: {
              destination: "/p/webstores/team-store",
              warning: "QR destination opens to buyers only after the Webstore lifecycle status is live.",
            },
            products: [{ packet_ref: "prod-1", name: "Approval Shirt", selling_price_cents: 2500 }],
          },
          approval_history: [{ id: "approval-1", action: "request_changes", reason: "Earlier note." }],
        },
      },
    });
  });

  renderWithProviders(<WebstoreOwnerPortalPage />, { route: "/portal/webstores/ws-1", path: "/portal/webstores/:webstoreId" });
  await user.click(await screen.findByRole("tab", { name: "Store Setup" }));

  expect(await screen.findByText("Version 3")).toBeInTheDocument();
  expect(screen.getByTestId("portal-launch-packet-preview")).toHaveTextContent("Team Store Launch");
  expect(screen.getByTestId("portal-launch-packet-share")).toHaveTextContent("/p/webstores/team-store");
  expect(screen.getByTestId("portal-launch-packet-approval-history")).toHaveTextContent("Earlier note.");

  const rejectButton = screen.getByTestId("portal-reject-packet");
  expect(rejectButton).toBeDisabled();
  await user.type(screen.getByTestId("portal-packet-decision-comment"), "Do not launch with this copy.");
  expect(rejectButton).toBeEnabled();
  await user.click(rejectButton);

  await waitFor(() =>
    expect(portalApi.post).toHaveBeenCalledWith(
      "/portal/webstores/ws-1/launch-packets/packet-1/reject",
      { comment: "Do not launch with this copy." },
    ),
  );
});

test.each([
  ["live", "Live", "shop_working", false, "Your store is live."],
  ["intake_pending", "Complete your questionnaire", "owner_complete_questionnaire", true, "Complete your store questionnaire."],
  ["intake_pending", "Complete your questionnaire", "owner_update_questionnaire", true, "The shop asked for changes to your questionnaire."],
  ["owner_review", "Review and approve your store", "terms_current", true, "Accept the current terms."],
])("owner guidance follows the canonical %s / %s action", async (stage, label, key, forYou, text) => {
  portalApi.get.mockImplementation((url) => {
    if (url.endsWith("/questionnaire")) return Promise.resolve({ data: {
      templates: [{ id: "intake", name: "Store questionnaire", sections: [] }],
      welcome: { title: "Welcome packet", body: "Start your questionnaire" },
    } });
    if (url.endsWith("/setup-progress")) return Promise.resolve({ data: {
      setup_state: "staff_review", setup_label: label,
      steps: [{ key: "next_action", label: "Current update", status: "information", status_label: text }],
    } });
    if (url.endsWith("/setup-files")) return Promise.resolve({ data: { items: [] } });
    return Promise.resolve({ data: {
      webstore: { id: "ws-1", name: "Team Store", status: stage }, products: [],
      journey: { stage: { key: stage, label, path: [{ key: stage, label }] }, next_action: { key, for_you: forYou, text } },
    } });
  });
  renderWithProviders(<WebstoreOwnerPortalPage />, { route: "/portal/webstores/ws-1", path: "/portal/webstores/:webstoreId" });
  await screen.findByTestId("portal-webstore-setup-state");
  expect(screen.getByTestId("portal-webstore-setup-state")).toHaveTextContent(label);
  expect(screen.queryByText("staff_review")).not.toBeInTheDocument();
  if (key === "owner_complete_questionnaire") expect(screen.getByTestId("owner-portal-welcome")).toHaveTextContent("Start your questionnaire");
  else expect(screen.queryByTestId("owner-portal-welcome")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("tab", { name: "Store Setup" }));
  const expectedQuestionnaire = ["owner_complete_questionnaire", "owner_update_questionnaire"].includes(key);
  if (expectedQuestionnaire) expect(screen.getByRole("button", { name: "Submit" })).toBeInTheDocument();
  else expect(screen.queryByRole("button", { name: "Submit" })).not.toBeInTheDocument();
});
