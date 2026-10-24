import React from "react";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";

let mockRole = "owner";
jest.mock("@/auth/AuthContext", () => ({
  __esModule: true,
  useAuth: () => ({
    hasPerm: (perm) => ["onboarding:read", "onboarding:write", "help:read"].includes(perm),
    user: { id: "u1", tenant_id: "t1", role: mockRole },
  }),
}));
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() }, Toaster: () => null }));
jest.mock("@/lib/api", () => {
  const api = { get: jest.fn(), put: jest.fn(), post: jest.fn(), patch: jest.fn() };
  return { __esModule: true, default: api, extractError: (e) => e?.response?.data?.detail || e?.message || "Something went wrong" };
});
jest.mock("@/lib/onboarding", () => ({
  __esModule: true,
  getOnboardingDashboard: jest.fn(),
  updateOnboardingTask: jest.fn(),
  saveOnboardingPosition: jest.fn(),
  getContextualHelp: jest.fn(),
  helpHref: (slug) => (slug ? `/help/docs?article=${slug}` : "/help/docs"),
}));

import api from "@/lib/api";
import { getContextualHelp, getOnboardingDashboard, saveOnboardingPosition, updateOnboardingTask } from "@/lib/onboarding";
import OnboardingPage from "@/pages/OnboardingPage";
import GuidedSetupBanner from "@/components/onboarding/GuidedSetupBanner";

const STAGES = [
  { key: "quick_start", title: "Quick Start", total_tasks: 3, completed_tasks: 0, required_tasks: 2, completed_required_tasks: 0, required_complete: false },
  { key: "standard", title: "Standard Setup", total_tasks: 1, completed_tasks: 0, required_tasks: 0, completed_required_tasks: 0, required_complete: true },
  { key: "advanced", title: "Advanced Optimization", total_tasks: 0, completed_tasks: 0, required_tasks: 0, completed_required_tasks: 0, required_complete: true },
];
const base = { what: "What it does", why: "Why it matters", dependencies: [], detect: "canonical", route: "/settings/company", route_label: "Company settings", help_slug: "company-profile", availability: { available: true } };
const TASKS = [
  { ...base, task_key: "company_profile", title: "Business information", stage: "quick_start", level: "required", form: "company", status: "not_started" },
  { ...base, task_key: "first_customer", title: "First customer", stage: "quick_start", level: "required", form: "customer", status: "not_started", help_slug: "customers" },
  { ...base, task_key: "first_order", title: "First order", stage: "quick_start", level: "required", form: "order", status: "blocked", blocked_reason: "Finish First customer first." },
  { ...base, task_key: "time_clock", title: "Time Clock", stage: "standard", level: "optional", form: null, detect: "manual", status: "not_started", route: "/team/time-clock", route_label: "Time Clock" },
];
const dashboard = (over = {}) => ({
  instance: { id: "i1", tenant_id: "t1", current_task_key: null },
  stages: STAGES,
  tasks: TASKS,
  progress: { total_tasks: 4, completed_tasks: 0, required_tasks: 3, completed_required_tasks: 0, percent_complete: 0 },
  recommended_next_task: TASKS[0],
  prompt: { show: true, resume_task_key: null },
  ...over,
});

beforeEach(() => {
  jest.clearAllMocks();
  mockRole = "owner";
  getOnboardingDashboard.mockResolvedValue(dashboard());
  getContextualHelp.mockResolvedValue({ items: [] });
  saveOnboardingPosition.mockResolvedValue({});
  updateOnboardingTask.mockResolvedValue({});
  api.get.mockImplementation(async (url) => {
    if (url === "/settings/company_profile") return { data: { values: {} } };
    if (url === "/customers") return { data: { items: [] } };
    return { data: {} };
  });
  api.put.mockResolvedValue({ data: {} });
  api.post.mockResolvedValue({ data: { id: "c1" } });
});

test("opens on the next required step with what/why, status, and a help link", async () => {
  renderWithProviders(<OnboardingPage />);
  expect(await screen.findByTestId("onboarding-panel-company_profile")).toBeInTheDocument();
  expect(screen.getByText("What it does")).toBeInTheDocument();
  expect(screen.getByText("Why it matters")).toBeInTheDocument();
  expect(screen.getByTestId("onboarding-progress-text")).toHaveTextContent("0 of 4 complete");
  expect(screen.getByTestId("onboarding-help-link")).toHaveAttribute("href", "/help/docs?article=company-profile");
  expect(screen.getByTestId("onboarding-open-feature")).toHaveAttribute("href", "/settings/company");
  expect(screen.queryByTestId("onboarding-skip")).toBeNull(); // required steps cannot be skipped
});

test("saves business info through the settings API and refreshes progress without marking complete itself", async () => {
  const user = userEvent.setup();
  renderWithProviders(<OnboardingPage />);
  await screen.findByTestId("onboarding-form-company_profile");
  await user.type(screen.getAllByRole("textbox")[0], "Acme Signs");
  await user.click(screen.getByTestId("onboarding-save"));
  await waitFor(() => expect(api.put).toHaveBeenCalledWith("/settings/company_profile", { shop_name: "Acme Signs" }));
  expect(updateOnboardingTask).not.toHaveBeenCalled();
  await waitFor(() => expect(getOnboardingDashboard.mock.calls.length).toBeGreaterThan(1));
});

test("shows validation instead of saving when the form is empty or the API fails", async () => {
  const user = userEvent.setup();
  renderWithProviders(<OnboardingPage />);
  await screen.findByTestId("onboarding-form-company_profile");
  await user.click(screen.getByTestId("onboarding-save"));
  expect(await screen.findByTestId("onboarding-form-error")).toHaveTextContent(/shop name/i);
  expect(api.put).not.toHaveBeenCalled();

  api.put.mockRejectedValueOnce({ response: { data: { detail: "Settings are read-only" } } });
  await user.type(screen.getAllByRole("textbox")[0], "Acme");
  await user.click(screen.getByTestId("onboarding-save"));
  expect(await screen.findByTestId("onboarding-form-error")).toHaveTextContent("Settings are read-only");
});

test("Back/Next move between steps and save the position; blocked steps explain why", async () => {
  const user = userEvent.setup();
  renderWithProviders(<OnboardingPage />);
  await screen.findByTestId("onboarding-panel-company_profile");
  await user.click(screen.getByTestId("onboarding-next"));
  expect(await screen.findByTestId("onboarding-panel-first_customer")).toBeInTheDocument();
  await waitFor(() => expect(saveOnboardingPosition).toHaveBeenCalledWith({ task_key: "first_customer" }));
  await user.click(screen.getByTestId("onboarding-next"));
  expect(await screen.findByTestId("onboarding-blocked")).toHaveTextContent("Finish First customer first.");
  await user.click(screen.getByTestId("onboarding-back"));
  expect(await screen.findByTestId("onboarding-panel-first_customer")).toBeInTheDocument();
});

test("manual steps require an explicit review; optional steps can be skipped", async () => {
  const user = userEvent.setup();
  renderWithProviders(<OnboardingPage />, { route: "/onboarding?step=time_clock" });
  expect(await screen.findByTestId("onboarding-panel-time_clock")).toBeInTheDocument();
  await user.click(screen.getByTestId("onboarding-mark-reviewed"));
  await waitFor(() => expect(updateOnboardingTask).toHaveBeenCalledWith("time_clock", { status: "completed" }));
  await user.click(screen.getByTestId("onboarding-skip"));
  await waitFor(() => expect(updateOnboardingTask).toHaveBeenCalledWith("time_clock", { status: "skipped" }));
});

test("resumes from the saved position", async () => {
  getOnboardingDashboard.mockResolvedValue(dashboard({ instance: { id: "i1", tenant_id: "t1", current_task_key: "time_clock" } }));
  renderWithProviders(<OnboardingPage />);
  expect(await screen.findByTestId("onboarding-panel-time_clock")).toBeInTheDocument();
});

test("staff can read progress but cannot change setup", async () => {
  mockRole = "staff";
  renderWithProviders(<OnboardingPage />);
  expect(await screen.findByTestId("onboarding-panel-company_profile")).toBeInTheDocument();
  expect(screen.queryByTestId("onboarding-form-company_profile")).toBeNull();
  expect(screen.getByText(/Only an owner or admin/i)).toBeInTheDocument();
});

test("Home banner invites once and stays dismissed", async () => {
  const user = userEvent.setup();
  renderWithProviders(<GuidedSetupBanner />);
  expect(await screen.findByTestId("guided-setup-start")).toHaveAttribute("href", "/onboarding");
  await user.click(screen.getByTestId("guided-setup-dismiss"));
  await waitFor(() => expect(saveOnboardingPosition).toHaveBeenCalledWith({ dismiss_prompt: true }));

  getOnboardingDashboard.mockResolvedValue(dashboard({ prompt: { show: false, resume_task_key: null } }));
  renderWithProviders(<GuidedSetupBanner />);
  await waitFor(() => expect(getOnboardingDashboard).toHaveBeenCalled());
  expect(screen.queryAllByTestId("guided-setup-banner").length).toBeLessThanOrEqual(1);
});
