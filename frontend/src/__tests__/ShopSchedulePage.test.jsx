import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ShopSchedulePage from "@/pages/ShopSchedulePage";
import { renderWithProviders } from "@/test-utils";
import api from "@/lib/api";

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
  },
  extractError: (error) => error?.message || "Request failed",
}));

jest.mock("@/auth/AuthContext", () => ({
  useAuth: () => ({
    hasPerm: (permission) => ["schedule:read", "schedule:manage"].includes(permission),
  }),
}));

jest.mock("sonner", () => ({
  toast: {
    error: jest.fn(),
    success: jest.fn(),
    warning: jest.fn(),
  },
}));

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

test("Shop Schedule shows operational calendar items without employee shift or absence administration", async () => {
  renderWithProviders(<ShopSchedulePage />, { route: "/shop-schedule?date=2026-08-14" });

  expect(await screen.findByTestId("shop-schedule-page")).toBeInTheDocument();
  expect(screen.getByTestId("shop-schedule-view-calendar")).toHaveAttribute("data-active", "true");
  expect(await screen.findByText("Install at Rusty Lemon")).toBeInTheDocument();
  expect(screen.getByText("Production: Print & Cut")).toBeInTheDocument();
  expect(screen.getByText("Task due: Send proof")).toBeInTheDocument();
  expect(screen.getByTestId("shop-schedule-assignment-event-1")).toHaveTextContent("Donnell");
  expect(screen.getByTestId("calendar-equipment-filter")).toBeInTheDocument();
  expect(screen.getByTestId("calendar-vehicle-filter")).toBeInTheDocument();
  expect(screen.getByTestId("calendar-resource-filter")).toBeInTheDocument();
  expect(screen.getByTestId("calendar-attention-filter")).toBeInTheDocument();
  expect(screen.queryByText("Gary shift")).not.toBeInTheDocument();
  expect(screen.queryByText("Maria PTO")).not.toBeInTheDocument();
  expect(screen.queryByText("Internal team meeting")).not.toBeInTheDocument();
  expect(api.get).toHaveBeenCalledWith("/calendar/feed", expect.objectContaining({
    params: expect.objectContaining({
      start_at: "2026-08-14T00:00:00.000Z",
      end_at: "2026-08-21T00:00:00.000Z",
    }),
  }));
});

test("URL context opens create appointment with supported linked record IDs", async () => {
  const user = userEvent.setup();
  renderWithProviders(<ShopSchedulePage />, {
    route: "/shop-schedule?view=appointments&new=1&customer_id=customer-1&quote_id=quote-1&order_id=order-1&order_item_id=item-1&work_order_id=work-order-1&production_stage_id=stage-1&wrap_project_id=wrap-1&source_type=order_item_installation&source_id=item-1&type=installation&title=Install%20appointment",
  });

  const dialog = await screen.findByTestId("calendar-appointment-dialog");
  expect(within(dialog).getByTestId("calendar-event-title")).toHaveValue("Install appointment");
  expect(within(dialog).getByTestId("calendar-event-customer-id")).toHaveValue("customer-1");
  expect(within(dialog).getByTestId("calendar-event-quote-id")).toHaveValue("quote-1");
  expect(within(dialog).getByTestId("calendar-event-order-id")).toHaveValue("order-1");
  expect(within(dialog).getByTestId("calendar-event-order-item-id")).toHaveValue("item-1");
  expect(within(dialog).getByTestId("calendar-event-work-order-id")).toHaveValue("work-order-1");
  expect(within(dialog).getByTestId("calendar-event-production-stage-id")).toHaveValue("stage-1");
  expect(within(dialog).getByTestId("calendar-event-wrap-project-id")).toHaveValue("wrap-1");
  expect(within(dialog).getByTestId("calendar-event-source-id")).toHaveValue("item-1");
  expect(within(dialog).getByTestId("calendar-people-resources-section")).toBeInTheDocument();
  await user.click(await within(dialog).findByRole("checkbox", { name: "Bill" }));
  await user.click(await within(dialog).findByRole("checkbox", { name: "HP Latex" }));
  await user.click(await within(dialog).findByRole("checkbox", { name: "Install Van" }));
  await user.click(await within(dialog).findByRole("checkbox", { name: "Install Bay 1" }));
  expect(within(dialog).getByTestId("calendar-selected-resource-summary")).toHaveTextContent("Bill");

  await user.click(within(dialog).getByRole("button", { name: "Create" }));

  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/calendar/events", expect.objectContaining({
    title: "Install appointment",
    event_type: "installation",
    assigned_employee_ids: ["employee-2"],
    reserved_equipment_ids: ["equipment-1"],
    reserved_vehicle_ids: ["vehicle-1"],
    reserved_resource_ids: ["resource-1"],
    customer_id: "customer-1",
    quote_id: "quote-1",
    order_id: "order-1",
    order_item_id: "item-1",
    work_order_id: "work-order-1",
    production_stage_id: "stage-1",
    wrap_project_id: "wrap-1",
    source_type: "order_item_installation",
    source_id: "item-1",
  })));
});

test("Appointments view edits stored calendar events through the canonical event endpoint", async () => {
  const user = userEvent.setup();
  renderWithProviders(<ShopSchedulePage />, { route: "/shop-schedule?view=appointments&date=2026-08-14" });

  expect(await screen.findByTestId("shop-schedule-appointments-list")).toBeInTheDocument();
  await user.click(screen.getByTestId("shop-schedule-edit-event-1"));
  const dialog = await screen.findByTestId("calendar-appointment-dialog");
  const title = within(dialog).getByTestId("calendar-event-title");
  await user.clear(title);
  await user.type(title, "Updated install appointment");
  await user.click(within(dialog).getByRole("button", { name: "Save" }));

  await waitFor(() => expect(api.patch).toHaveBeenCalledWith("/calendar/events/event-1", expect.objectContaining({
    title: "Updated install appointment",
    assigned_employee_ids: ["employee-1", "employee-2"],
    reserved_equipment_ids: ["equipment-1"],
    reserved_vehicle_ids: ["vehicle-1"],
    reserved_resource_ids: ["resource-1"],
    customer_id: "customer-1",
    order_id: "order-1",
    work_order_id: "work-order-1",
  })));
});

test("availability conflicts identify the blocked resource and prevent normal save", async () => {
  api.post.mockImplementation((url) => {
    if (url === "/calendar/availability") {
      return Promise.resolve({ data: {
        conflicts: [{
          resource_type: "resource",
          resource_id: "resource-1",
          resource_name: "Install Bay 1",
          title: "Trailer install",
          start_at: "2026-08-14T13:00:00.000Z",
          end_at: "2026-08-14T15:00:00.000Z",
        }],
        warnings: [],
        summary: { assigned_employees: 1, reserved_equipment: 1, reserved_vehicles: 1, available_resources: 0 },
      } });
    }
    return Promise.resolve({ data: { id: "event-created" } });
  });
  const user = userEvent.setup();
  renderWithProviders(<ShopSchedulePage />, { route: "/shop-schedule?view=appointments&new=1&date=2026-08-14" });

  const dialog = await screen.findByTestId("calendar-appointment-dialog");
  await user.type(within(dialog).getByTestId("calendar-event-title"), "Conflicting install");
  await user.click(await within(dialog).findByRole("checkbox", { name: "Install Bay 1" }));
  expect(await within(dialog).findByTestId("calendar-resource-conflicts")).toHaveTextContent("Install Bay 1");

  await user.click(within(dialog).getByRole("button", { name: "Create" }));

  expect(await within(dialog).findByTestId("calendar-conflict-warning")).toHaveTextContent("Install Bay 1");
  expect(api.post).not.toHaveBeenCalledWith("/calendar/events", expect.anything());
});

test("agenda and appointments display assigned people and reserved resources", async () => {
  renderWithProviders(<ShopSchedulePage />, { route: "/shop-schedule?view=agenda&date=2026-08-14" });

  expect(await screen.findByTestId("shop-schedule-agenda-list")).toBeInTheDocument();
  expect(screen.getByTestId("shop-schedule-row-assignment-event-1")).toHaveTextContent("HP Latex");
});

test("appointment lifecycle actions complete and reopen canonical calendar events", async () => {
  const user = userEvent.setup();
  renderWithProviders(<ShopSchedulePage />, { route: "/shop-schedule?view=appointments&date=2026-08-14" });

  expect(await screen.findByTestId("shop-schedule-appointments-list")).toBeInTheDocument();
  await user.click(screen.getByTestId("shop-schedule-complete-event-1"));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/calendar/events/event-1/complete", { outcome_note: "Completed from Shop Schedule" }));

  await user.click(screen.getByTestId("shop-schedule-reopen-event-3"));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/calendar/events/event-3/reopen", { reason: "Reopened from Shop Schedule" }));
});
