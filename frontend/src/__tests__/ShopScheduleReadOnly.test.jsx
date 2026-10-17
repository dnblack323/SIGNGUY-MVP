import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ShopSchedulePage from "@/pages/ShopSchedulePage";
import { renderWithProviders } from "@/test-utils";
import api from "@/lib/api";

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn(), patch: jest.fn() },
  extractError: (error) => error?.message || "Request failed",
}));
jest.mock("@/auth/AuthContext", () => ({
  useAuth: () => ({ hasPerm: (permission) => permission === "schedule:read" }),
}));
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn(), warning: jest.fn() } }));

const feedItems = [
  {
    id: "calendar_event:event-1",
    source_type: "calendar_event",
    source_id: "event-1",
    event_type: "installation",
    title: "Install at Rusty Lemon",
    display_title: "Install at Rusty Lemon",
    start_at: "2026-08-14T13:00:00.000Z",
    end_at: "2026-08-14T15:00:00.000Z",
    status: "scheduled",
    customer_id: "customer-1",
    order_id: "order-1",
    work_order_id: "work-order-1",
    assigned_employee_ids: ["employee-1", "employee-2"],
    reserved_equipment_ids: ["equipment-1"],
    reserved_vehicle_ids: ["vehicle-1"],
    reserved_resource_ids: ["resource-1"],
    assignment_summary: {
      employees: [{ id: "employee-1", name: "Donnell" }, { id: "employee-2", name: "Bill" }],
      equipment: [{ id: "equipment-1", name: "HP Latex" }],
      vehicles: [{ id: "vehicle-1", name: "Install Van" }],
      resources: [{ id: "resource-1", name: "Install Bay 1" }],
    },
    allowed_actions: ["update", "cancel", "complete"],
  },
  {
    id: "calendar_event:event-3",
    source_type: "calendar_event",
    source_id: "event-3",
    event_type: "vehicle_pickup",
    title: "Pickup completed",
    display_title: "Pickup completed",
    start_at: "2026-08-18T13:00:00.000Z",
    end_at: "2026-08-18T14:00:00.000Z",
    status: "completed",
    allowed_actions: ["reopen"],
  },
  {
    id: "production_stage:stage-1",
    source_type: "production_stage",
    source_id: "stage-1",
    event_type: "production_milestone",
    title: "Production: Print & Cut",
    display_title: "Production: Print & Cut",
    start_at: "2026-08-15T13:00:00.000Z",
    end_at: "2026-08-15T14:00:00.000Z",
    status: "in_progress",
    work_order_id: "work-order-1",
  },
  {
    id: "task:task-1",
    source_type: "task",
    source_id: "task-1",
    event_type: "task_due",
    title: "Task due: Send proof",
    display_title: "Task due: Send proof",
    start_at: "2026-08-16T13:00:00.000Z",
    end_at: "2026-08-16T13:30:00.000Z",
    status: "open",
  },
  {
    id: "shift:shift-1",
    source_type: "shift",
    source_id: "shift-1",
    event_type: "shift",
    title: "Gary shift",
    display_title: "Gary shift",
    start_at: "2026-08-14T09:00:00.000Z",
    end_at: "2026-08-14T17:00:00.000Z",
  },
  {
    id: "absence:absence-1",
    source_type: "time_off_request",
    source_id: "absence-1",
    event_type: "absence",
    title: "Maria PTO",
    display_title: "Maria PTO",
    start_at: "2026-08-14T09:00:00.000Z",
    end_at: "2026-08-14T17:00:00.000Z",
  },
  {
    id: "calendar_event:event-2",
    source_type: "calendar_event",
    source_id: "event-2",
    event_type: "internal_meeting",
    title: "Internal team meeting",
    display_title: "Internal team meeting",
    start_at: "2026-08-17T13:00:00.000Z",
    end_at: "2026-08-17T14:00:00.000Z",
  },
];

function mockScheduleApi(items = feedItems) {
  api.get.mockImplementation((url) => {
    if (url === "/employees") return Promise.resolve({ data: { items: [{ id: "employee-1", name: "Donnell" }, { id: "employee-2", name: "Bill" }] } });
    if (url === "/equipment") return Promise.resolve({ data: { items: [
      { id: "equipment-1", name: "HP Latex", category: "printer" },
      { id: "vehicle-1", name: "Install Van", category: "vehicle" },
    ] } });
    if (url === "/calendar/resources") return Promise.resolve({ data: { items: [{ id: "resource-1", name: "Install Bay 1", resource_type: "installation_bay" }] } });
    if (url === "/calendar/feed") return Promise.resolve({ data: { items, total: items.length } });
    return Promise.resolve({ data: {} });
  });
  api.post.mockImplementation((url) => {
    if (url === "/calendar/availability") return Promise.resolve({ data: { conflicts: [], warnings: [], summary: { assigned_employees: 0, reserved_equipment: 0, reserved_vehicles: 0, available_resources: 1 } } });
    return Promise.resolve({ data: { id: "event-created" } });
  });
  api.patch.mockResolvedValue({ data: { id: "event-1" } });
}

beforeEach(() => {
  jest.clearAllMocks();
  mockScheduleApi();
});

test("read-only schedule users can view and open items but cannot create or edit", async () => {
  const user = userEvent.setup();
  renderWithProviders(<ShopSchedulePage />, { route: "/shop-schedule?view=day&date=2026-08-14&new=1" });
  await user.click(await screen.findByTestId("schedule-day-item-calendar_event-event-1"));
  expect(await screen.findByTestId("schedule-event-details")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open Order" })).toHaveAttribute("href", "/orders/order-1");
  expect(screen.queryByTestId("schedule-details-edit")).not.toBeInTheDocument();
  expect(screen.queryByTestId("shop-schedule-complete-event-1")).not.toBeInTheDocument();
  expect(screen.queryByTestId("calendar-create-appointment")).not.toBeInTheDocument();
  expect(screen.queryByTestId("calendar-appointment-dialog")).not.toBeInTheDocument();
});
