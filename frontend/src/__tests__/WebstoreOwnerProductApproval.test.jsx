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
