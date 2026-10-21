import React from "react";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";

jest.mock("@/auth/AuthContext", () => ({
  __esModule: true,
  useAuth: () => ({
    hasPerm: (perm) => [
      "onboarding:read",
      "onboarding:write",
      "help:read",
      "support:write",
      "subscription:read",
    ].includes(perm),
    user: { id: "u1", tenant_id: "t1", role: "owner" },
  }),
}));

jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() }, Toaster: () => null }));

jest.mock("@/lib/onboarding", () => ({
  __esModule: true,
  searchHelp: jest.fn(),
  getContextualHelp: jest.fn(),
  sendHelpFeedback: jest.fn(),
  createSupportEscalation: jest.fn(),
  getFailedSubscriptionGuidance: jest.fn(),
}));

import {
  createSupportEscalation,
  getContextualHelp,
  getFailedSubscriptionGuidance,
  searchHelp,
  sendHelpFeedback,
} from "@/lib/onboarding";
import HelpCenterPage from "@/pages/HelpCenterPage";

beforeEach(() => {
  jest.clearAllMocks();
  getContextualHelp.mockResolvedValue({ items: [{ id: "ctx-1", title: "Setup progress", body: "Required steps drive launch readiness." }] });
  searchHelp.mockResolvedValue({
    items: [
      { id: "help-1", slug: "pricing-setup-guide", title: "Pricing setup guide", category: "module_guides", body: "Use Pricing Foundation and approve only selected fields." },
      { id: "help-2", slug: "failed-subscription-guidance", title: "Failed subscription guidance", category: "billing", body: "Past-due billing states come from EC13." },
    ],
  });
  getFailedSubscriptionGuidance.mockResolvedValue({ dunning_state: "day_8_14_soft_restriction", guidance: "Resolve billing to avoid deeper restrictions.", mutated_billing: false });
  sendHelpFeedback.mockResolvedValue({ id: "fb-1" });
  createSupportEscalation.mockResolvedValue({ id: "sup-1", status: "open" });
});

test("renders EC19 Help Center articles, billing guidance, feedback, and support", async () => {
  const user = userEvent.setup();
  renderWithProviders(<HelpCenterPage />);

  expect(await screen.findByTestId("help-center-page")).toBeInTheDocument();
  await waitFor(() => expect(searchHelp).toHaveBeenCalled());
  expect(screen.getAllByText("Pricing setup guide").length).toBeGreaterThan(0);
  expect(screen.getByText("day_8_14_soft_restriction")).toBeInTheDocument();
  expect(screen.getByText("read-only")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /Helpful/i }));
  await waitFor(() => expect(sendHelpFeedback).toHaveBeenCalledWith(expect.objectContaining({ article_slug: "pricing-setup-guide" })));

  await user.type(screen.getByLabelText(/Subject/i), "Need setup help");
  await user.type(screen.getByLabelText(/Message/i), "Please review onboarding.");
  await user.click(screen.getByRole("button", { name: /Send/i }));
  await waitFor(() => expect(createSupportEscalation).toHaveBeenCalledWith(expect.objectContaining({ source_surface: "help_center" })));
});
