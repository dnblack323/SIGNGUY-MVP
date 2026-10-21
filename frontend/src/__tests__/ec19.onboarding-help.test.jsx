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
  getOnboardingDashboard: jest.fn(),
  updateOnboardingTask: jest.fn(),
  applyCompanyProfile: jest.fn(),
  submitPricingScenario: jest.fn(),
  applyPricingScenario: jest.fn(),
  createHistoricalInvoiceImport: jest.fn(),
  getPlaceholderRegistry: jest.fn(),
  previewPlaceholders: jest.fn(),
  createTemplateExercise: jest.fn(),
  getSetupPackageHandoff: jest.fn(),
  updateSetupPackageHandoff: jest.fn(),
  recordTestPortal: jest.fn(),
}));

jest.mock("@/lib/help", () => ({
  ...jest.requireActual("@/lib/help"),
  getContextualHelp: jest.fn(),
}));

import { getOnboardingDashboard, getPlaceholderRegistry, getSetupPackageHandoff, previewPlaceholders } from "@/lib/onboarding";
import { getContextualHelp } from "@/lib/help";
import OnboardingPage from "@/pages/OnboardingPage";

beforeEach(() => {
  jest.clearAllMocks();
  getOnboardingDashboard.mockResolvedValue({
    instance: { id: "inst-1", tenant_id: "t1" },
    progress: { total_tasks: 3, completed_tasks: 1, required_tasks: 2, completed_required_tasks: 1, percent_complete: 33 },
    recommended_next_task: { task_key: "pricing_setup_assistant", title: "Pricing Setup Assistant", level: "required" },
    tasks: [
      { task_key: "company_profile", title: "Company profile", level: "required", family: "core", dependencies: [], status: "completed" },
      { task_key: "pricing_setup_assistant", title: "Pricing Setup Assistant", level: "required", family: "pricing", dependencies: ["company_profile"], status: "in_progress" },
      { task_key: "order_templates", title: "Order templates", level: "recommended", family: "templates", dependencies: [], status: "not_started" },
    ],
  });
  getPlaceholderRegistry.mockResolvedValue({ placeholders: [{ key: "customer_name", token: "{{customer_name}}" }, { key: "order_number", token: "{{order_number}}" }] });
  getSetupPackageHandoff.mockResolvedValue({ available: true, handoff_status: "not_started", purchase: { package_key: "standard" } });
  getContextualHelp.mockResolvedValue({ items: [{ id: "ctx-1", title: "Setup progress", body: "Required steps drive launch readiness." }] });
  previewPlaceholders.mockResolvedValue({ rendered: "Hi Acme", placeholders: ["customer_name"], missing_placeholders: [] });
});

test("renders EC19 onboarding dashboard and placeholder exercise controls", async () => {
  const user = userEvent.setup();
  renderWithProviders(<OnboardingPage />);

  expect(await screen.findByTestId("onboarding-page")).toBeInTheDocument();
  await waitFor(() => expect(getOnboardingDashboard).toHaveBeenCalled());
  expect(screen.getAllByText("Pricing Setup Assistant").length).toBeGreaterThan(0);
  expect(screen.getByTestId("onboarding-progress-text")).toHaveTextContent("1 of 3 complete");
  expect(screen.getByText("standard")).toBeInTheDocument();

  await user.click(screen.getByRole("tab", { name: /templates/i }));
  expect(await screen.findByText(/Placeholder Exercise/i)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /Preview/i }));
  await waitFor(() => expect(previewPlaceholders).toHaveBeenCalled());
  expect(await screen.findByText(/Hi Acme/i)).toBeInTheDocument();
});
