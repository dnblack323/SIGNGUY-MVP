import "@testing-library/jest-dom";
import { screen, waitFor } from "@testing-library/react";
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

jest.mock("@/components/webstores/WebstoreBranding", () => () => <div data-testid="portal-branding" />);

jest.mock("sonner", () => ({
  toast: {
    error: jest.fn(),
    success: jest.fn(),
  },
}));

function mockStage5PortalDetail() {
  portalApi.get.mockImplementation((url) => {
    if (url.endsWith("/questionnaire")) return Promise.resolve({ data: { templates: [] } });
    if (url.endsWith("/setup-progress")) return Promise.resolve({ data: { setup_state: "setup_complete", steps: [] } });
    if (url.endsWith("/setup-files")) return Promise.resolve({ data: { items: [] } });
    return Promise.resolve({
      data: {
        webstore: { id: "ws-1", name: "Stage 5 Store", status: "sent_for_approval" },
        products: [],
        launch_packet: {
          id: "packet-5",
          version: 5,
          status: "delivered",
          delivery_status: "sent",
          promotion_copy: "Manual launch copy from the shop.",
          snapshot: {
            owner_preview: {
              display_name: "Stage 5 Store",
              headline: "Final Launch Review",
              greeting: "Pickup at the front desk.",
              accent_color: "#2563eb",
            },
            qr_reference: {
              destination: "/p/webstores/stage-5-store",
              warning: "QR destination opens to buyers only after the Webstore lifecycle status is live.",
            },
            products: [{ packet_ref: "prod-1", name: "Launch Shirt", description: "Owner-safe description", selling_price_cents: 2500 }],
          },
          approval_history: [
            { id: "approval-1", action: "request_changes", reason: "Earlier pickup wording note." },
            { id: "approval-2", action: "decline", reason: "Earlier rejection note." },
          ],
        },
        current_terms_version: "webstore_terms_2026_07",
        terms_acceptance: null,
        readiness_summary: [
          { key: "questionnaire_complete", state: "ready", owner_wording: "Store Owner questionnaire has been submitted." },
          { key: "packet_approved", state: "waiting", owner_wording: "Packet approval is still needed." },
          { key: "payment_ready", state: "not_configured", owner_wording: "Payment setup is not ready yet." },
        ],
        public_launch_blocked_until_batch_3: true,
      },
    });
  });
  portalApi.post.mockResolvedValue({ data: {} });
}

beforeEach(() => {
  jest.clearAllMocks();
  mockStage5PortalDetail();
});

test("Stage 5 owner portal exposes packet decisions, terms, readiness, and QR prep without commerce controls", async () => {
  const user = userEvent.setup();
  renderWithProviders(<WebstoreOwnerPortalPage />, { route: "/portal/webstores/ws-1", path: "/portal/webstores/:webstoreId" });

  expect(await screen.findByText("Version 5")).toBeInTheDocument();
  expect(screen.getByText("Manual launch copy from the shop.")).toBeInTheDocument();
  expect(screen.getByTestId("portal-launch-packet-preview")).toHaveTextContent("Final Launch Review");
  expect(screen.getByTestId("portal-launch-packet-share")).toHaveTextContent("/p/webstores/stage-5-store");
  expect(screen.getByTestId("portal-launch-packet-share")).toHaveTextContent("only after the Webstore lifecycle status is live");
  expect(screen.getByTestId("portal-launch-packet-approval-history")).toHaveTextContent("Earlier pickup wording note.");
  expect(screen.getByTestId("portal-readiness-summary")).toHaveTextContent("Packet approval is still needed.");
  expect(screen.getByTestId("portal-terms-version")).toHaveTextContent("webstore_terms_2026_07");
  expect(portalApi.post).not.toHaveBeenCalled();

  expect(screen.queryByRole("button", { name: /cart/i })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /checkout/i })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /go live/i })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /launch store/i })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /generate.*ai/i })).not.toBeInTheDocument();

  await user.type(screen.getByTestId("portal-packet-decision-comment"), "Approved with final pickup wording.");
  await user.click(screen.getByTestId("portal-approve-packet"));
  await waitFor(() =>
    expect(portalApi.post).toHaveBeenCalledWith(
      "/portal/webstores/ws-1/launch-packets/packet-5/approve",
      { comment: "Approved with final pickup wording." },
    ),
  );

  await user.type(screen.getByTestId("portal-change-request-comment"), "Please add pickup dates.");
  await user.click(screen.getByTestId("portal-request-changes"));
  await waitFor(() =>
    expect(portalApi.post).toHaveBeenCalledWith(
      "/portal/webstores/ws-1/launch-packets/packet-5/request-changes",
      { category: "general", comment: "Please add pickup dates." },
    ),
  );

  await user.clear(screen.getByTestId("portal-packet-decision-comment"));
  expect(screen.getByTestId("portal-reject-packet")).toBeDisabled();
  await user.type(screen.getByTestId("portal-packet-decision-comment"), "Do not launch this packet.");
  await user.click(screen.getByTestId("portal-reject-packet"));
  await waitFor(() =>
    expect(portalApi.post).toHaveBeenCalledWith(
      "/portal/webstores/ws-1/launch-packets/packet-5/reject",
      { comment: "Do not launch this packet." },
    ),
  );

  await user.click(screen.getByTestId("portal-accept-terms"));
  await waitFor(() =>
    expect(portalApi.post).toHaveBeenCalledWith(
      "/portal/webstores/ws-1/terms/accept",
      { terms_version: "webstore_terms_2026_07" },
    ),
  );
});
