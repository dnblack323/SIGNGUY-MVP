import React from "react";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";
import ProductionBoardPage from "@/pages/ProductionBoardPage";
import WorkOrderDetailPage from "@/pages/WorkOrderDetailPage";
import WorkOrderStagesPanel from "@/components/production/WorkOrderStagesPanel";
import api from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn(), patch: jest.fn() },
  extractError: (error) => error?.response?.data?.detail || error?.message || "Request failed",
}));

jest.mock("@/auth/AuthContext", () => ({ useAuth: jest.fn() }));
jest.mock("@/context/WorkspaceContext", () => ({
  useWorkspace: () => ({ openWorkspaceTarget: jest.fn() }),
  useWorkspaceDirty: jest.fn(),
}));
jest.mock("@/components/production/ProductionTimeline", () => () => <div data-testid="timeline" />);
jest.mock("@/components/tasks/TaskHandoffButton", () => () => null);
jest.mock("@/components/work-orders/GenerateWorkOrderDialog", () => ({
  __esModule: true,
  default: () => null,
  RegenerateDialog: () => null,
  TransitionReasonDialog: () => null,
  AssignDialog: () => null,
}));
jest.mock("@/components/work-orders/RequirementsDialog", () => () => null);
jest.mock("@/components/work-orders/PrintSummaryDialog", () => () => null);

const activeTimer = {
  id: "timer-1",
  employee_id: "emp-1",
  employee_name: "Alex Maker",
  started_at: "2026-08-16T14:00:00Z",
  status: "active",
  effective_elapsed_seconds: 1800,
  paused_duration_seconds: 600,
};

const boardRow = {
  id: "wo-1:wfi-1",
  work_order_id: "wo-1",
  work_order_number: 9101,
  order_id: "order-1",
  order_number: 501,
  customer_id: "customer-1",
  customer_name: "Acme Signs",
  order_item_id: "item-1",
  order_item_name: "Lobby banner",
  priority: "normal",
  current_stage_id: "stage-1",
  current_stage_key: "print",
  current_stage_name: "Print",
  current_stage_status: "in_progress",
  assigned_employee_id: "emp-1",
  assigned_employee_name: "Alex Maker",
  due_at: "2026-08-18",
  completed_stage_count: 1,
  total_stage_count: 3,
  progress_percent: 33,
  allowed_actions: ["timer_pause", "timer_stop", "timer_correct", "timer_void", "pricing_feedback", "complete", "add_note"],
  active_timer: activeTimer,
  current_timer: activeTimer,
  timer_status: "active",
  active_timer_session_id: "timer-1",
  active_timer_employee_name: "Alex Maker",
  active_timer_started_at: "2026-08-16T14:00:00Z",
  active_timer_effective_elapsed_seconds: 1800,
  active_timer_paused_duration_seconds: 600,
  actual_duration_seconds: 5400,
  planned_duration_minutes: 60,
  labor_variance_minutes: 30,
  timing_entry_count: 2,
  timer_history: [
    { id: "timer-done", employee_name: "Alex Maker", status: "completed", effective_elapsed_seconds: 3600, corrected_elapsed_seconds: 3300, paused_duration_seconds: 300 },
  ],
};

const pricingFeedback = {
  id: "pfb-1",
  status: "pending",
  mapped: true,
  stage_name: "Print",
  target_path: "category_defaults.banners.production_labor_hr_per_sqft",
  planned_seconds: 3600,
  effective_actual_seconds: 5400,
  variance_seconds: 1800,
  existing_value: 0.1,
  suggested_value: 0.15,
};

beforeEach(() => {
  jest.clearAllMocks();
  useAuth.mockReturnValue({
    user: { role: "production_manager" },
    hasPerm: (perm) => ["work_order:read", "work_order:write", "schedule:manage", "pricing:read", "pricing:write"].includes(perm),
  });
  api.get.mockImplementation((url) => {
    if (url === "/production/board") {
      return Promise.resolve({
        data: {
          items: [boardRow],
          summary_counts: { active_production: 1, active_timers: 1, in_progress: 1 },
          columns: { in_progress: [boardRow] },
        },
      });
    }
    if (url === "/production/pricing-feedback") return Promise.resolve({ data: { items: [pricingFeedback] } });
    if (url === "/employees") return Promise.resolve({ data: { items: [{ id: "emp-1", name: "Alex Maker" }] } });
    if (url === "/work-orders/wo-1") {
      return Promise.resolve({
        data: {
          id: "wo-1",
          number: 9101,
          order_id: "order-1",
          production_status: "in_progress",
          priority: "normal",
          financials_restricted: true,
          items_snapshot: [{ order_item_id: "item-1", description: "Lobby banner", quantity: 1 }],
          assigned_user_ids: [],
          required_equipment_ids: [],
        },
      });
    }
    if (url === "/users") return Promise.resolve({ data: [] });
    if (url === "/equipment") return Promise.resolve({ data: { items: [] } });
    if (url === "/work-orders/wo-1/stages") {
      return Promise.resolve({
        data: {
          workflow_instances: [{ id: "wfi-1", source_name: "Production Flow", resolution_source: "tenant_default" }],
          stages: [{
            id: "stage-1",
            sequence: 1,
            stage_name: "Print",
            status: "in_progress",
            required: true,
            active_timer: activeTimer,
            current_timer: activeTimer,
            timer_status: "active",
            actual_duration_seconds: 5400,
            default_estimated_duration_minutes: 60,
            timing_entry_count: 2,
            timer_history: boardRow.timer_history,
            production_notes: [],
          }],
        },
      });
    }
    if (url === "/work-orders/wo-1/stage-preview") return Promise.resolve({ data: { items: [] } });
    if (url === "/production-workflows") return Promise.resolve({ data: { items: [] } });
    return Promise.resolve({ data: {} });
  });
  api.post.mockResolvedValue({ data: { ok: true } });
  api.patch.mockResolvedValue({ data: { ok: true } });
});

test("Production Board shows active timers and pauses/checks a timer through authoritative endpoints", async () => {
  renderWithProviders(<ProductionBoardPage />, { route: "/work-orders/board" });

  expect(await screen.findByText("Active Timers")).toBeInTheDocument();
  expect(await screen.findByTestId("board-active-timer-stage-1")).toHaveTextContent("Alex Maker");
  expect(screen.getByTestId("board-active-timer-stage-1")).toHaveTextContent("working 30m");
  expect(screen.getByTestId("board-active-timer-stage-1")).toHaveTextContent("paused 10m");
  expect(screen.getAllByText(/Actual 1h 30m/).length).toBeGreaterThan(0);

  await userEvent.click(screen.getByLabelText("Stage actions"));
  await userEvent.click(await screen.findByText("Pause Timer"));
  fireEvent.change(screen.getByTestId("board-reason-input"), { target: { value: "Material question" } });
  await userEvent.click(screen.getByRole("button", { name: "Apply" }));

  await waitFor(() => {
    expect(api.post).toHaveBeenCalledWith("/production-stages/stage-1/timer/pause", {
      session_id: "timer-1",
      reason: "Material question",
    });
  });

  await userEvent.click(screen.getByLabelText("Stage actions"));
  await userEvent.click(await screen.findByText("Check In"));
  fireEvent.change(screen.getByTestId("board-reason-input"), { target: { value: "Shift ended" } });
  fireEvent.change(screen.getByTestId("board-note-input"), { target: { value: "Clean handoff" } });
  await userEvent.click(screen.getByRole("button", { name: "Apply" }));

  await waitFor(() => {
    expect(api.post).toHaveBeenCalledWith("/production-stages/stage-1/timer/stop", {
      session_id: "timer-1",
      notes: "Clean handoff",
      interruption_reason: "Shift ended",
    });
  });
});

test("Production Board exposes manager time correction and pricing feedback review", async () => {
  renderWithProviders(<ProductionBoardPage />, { route: "/work-orders/board" });

  expect(await screen.findByTestId("pricing-feedback-panel")).toHaveTextContent("Pricing Foundation Feedback");
  await waitFor(() => {
    expect(screen.getByTestId("pricing-feedback-panel")).toHaveTextContent("Suggested 0.1500");
  });

  await userEvent.click(screen.getByLabelText("Stage actions"));
  await userEvent.click(await screen.findByText("Correct Time"));
  fireEvent.change(screen.getByTestId("board-corrected-seconds-input"), { target: { value: "3300" } });
  fireEvent.change(screen.getByTestId("board-reason-input"), { target: { value: "Removed setup wait" } });
  await userEvent.click(screen.getByRole("button", { name: "Apply" }));

  await waitFor(() => {
    expect(api.post).toHaveBeenCalledWith("/production-stages/stage-1/timer/correct", {
      session_id: "timer-done",
      corrected_elapsed_seconds: 3300,
      reason: "Removed setup wait",
    });
  });

  await userEvent.click(screen.getByRole("button", { name: "Approve" }));
  await waitFor(() => {
    expect(api.post).toHaveBeenCalledWith("/production/pricing-feedback/pfb-1/approve", {
      approved_value: 0.15,
      reason: "Manager approved production variance feedback",
    });
  });
});

test("Work Order stages show timer attribution and use timer endpoints", async () => {
  const prompt = jest.spyOn(window, "prompt").mockReturnValue("Finished pass");
  renderWithProviders(<WorkOrderStagesPanel workOrderId="wo-1" />);

  expect(await screen.findByTestId("stage-active-timer-stage-1")).toHaveTextContent("Alex Maker");
  expect(screen.getByTestId("stage-active-timer-stage-1")).toHaveTextContent("working 30m");
  expect(screen.getByText("Actual 1h 30m")).toBeInTheDocument();
  expect(screen.getByText("Planned 60m")).toBeInTheDocument();
  expect(screen.getByTestId("stage-timer-history-stage-1")).toHaveTextContent("corrected");

  await userEvent.click(screen.getByRole("button", { name: "Pause" }));
  await waitFor(() => {
    expect(api.post).toHaveBeenCalledWith("/production-stages/stage-1/timer/pause", {
      session_id: "timer-1",
      reason: "Finished pass",
    });
  });

  await userEvent.click(screen.getByRole("button", { name: "Check In" }));
  await waitFor(() => {
    expect(api.post).toHaveBeenCalledWith("/production-stages/stage-1/timer/stop", {
      session_id: "timer-1",
      notes: "Finished pass",
    });
  });
  prompt.mockRestore();
});

test("Work Order detail omits item pricing columns when backend restricts financials", async () => {
  renderWithProviders(<WorkOrderDetailPage />, { route: "/work-orders/wo-1", path: "/work-orders/:id" });

  expect(await screen.findByText("Lobby banner")).toBeInTheDocument();
  expect(screen.queryByText("Unit")).not.toBeInTheDocument();
  expect(screen.queryByText("Line total")).not.toBeInTheDocument();
  expect(screen.queryByText("$0.00")).not.toBeInTheDocument();
});
