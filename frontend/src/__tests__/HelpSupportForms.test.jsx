import React from "react";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";

jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() }, Toaster: () => null }));
jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn() },
  extractError: (e) => String(e),
}));

import api from "@/lib/api";
import CommunityPage from "@/pages/CommunityPage";

beforeEach(() => {
  jest.clearAllMocks();
  api.get.mockImplementation(async (url) => {
    if (url === "/community/support/route-preview") return { data: { destination_label: "Your shop owner" } };
    if (url === "/community/bug-reports") return { data: { items: [{ id: "b1", title: "Board stuck", description: "d", severity: "high", status: "confirmed", staff_response: "Reproduced" }] } };
    if (url === "/community/support") return { data: { items: [{ id: "s1", subject: "Need help", description: "d", request_type: "shop_configuration_question", status: "open", destination_type: "tenant_owner" }] } };
    return { data: { items: [] } };
  });
  api.post.mockResolvedValue({ data: { id: "new" } });
});

test("bug report form sends steps and expected/actual behavior, and lists status", async () => {
  const user = userEvent.setup();
  renderWithProviders(<CommunityPage />, { route: "/help/bugs" });
  expect(await screen.findByRole("heading", { name: "Bug Reports" })).toBeInTheDocument();
  expect(screen.getByText("Board stuck")).toBeInTheDocument();
  expect(screen.getByText("confirmed")).toBeInTheDocument();
  expect(screen.getByText("Reproduced")).toBeInTheDocument();

  await user.type(screen.getAllByLabelText(/title/i)[0], "Cannot save");
  await user.type(screen.getByLabelText(/what happened/i), "Save does nothing");
  await user.type(screen.getByLabelText(/steps to repeat/i), "Open order{enter}Press save");
  await user.type(screen.getByLabelText(/what you expected/i), "It saves");
  await user.click(screen.getByRole("button", { name: /report bug/i }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/community/bug-reports", expect.objectContaining({
    title: "Cannot save",
    steps: ["Open order", "Press save"],
    expected_behavior: "It saves",
    browser_metadata: expect.any(Object),
  })));
});

test("Contact Support creates a request in the single community support queue and shows status", async () => {
  const user = userEvent.setup();
  renderWithProviders(<CommunityPage />, { route: "/help/contact" });
  expect(await screen.findByRole("heading", { name: "Contact Support" })).toBeInTheDocument();
  expect(await screen.findByText(/Routes to: Your shop owner/)).toBeInTheDocument();
  expect(screen.getByText("Need help")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "FAQ" })).toHaveAttribute("href", "/help/docs?article=faq");

  await user.type(screen.getByLabelText(/subject/i), "Printer setup");
  await user.type(screen.getAllByLabelText(/description/i)[0], "Please help");
  await user.click(screen.getByRole("button", { name: /create request/i }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/community/support", expect.objectContaining({ subject: "Printer setup" })));
  expect(api.post).not.toHaveBeenCalledWith(expect.stringContaining("/help/support"), expect.anything());
});

test("feature request submits to the community queue", async () => {
  const user = userEvent.setup();
  renderWithProviders(<CommunityPage />, { route: "/help/feature-requests" });
  expect(await screen.findByRole("heading", { name: "Feature Requests" })).toBeInTheDocument();
  await user.type(screen.getByLabelText(/title/i), "Dark mode");
  await user.type(screen.getByLabelText(/description/i), "Please");
  await user.click(screen.getByRole("button", { name: /submit/i }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/community/feature-requests", expect.objectContaining({ title: "Dark mode" })));
});
