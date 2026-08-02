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

jest.mock("@/components/webstores/WebstoreBranding", () => () => <div data-testid="portal-branding" />);

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
