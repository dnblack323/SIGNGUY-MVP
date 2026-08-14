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
    allowed_actions: ["update", "cancel"],
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
    if (url === "/employees") return Promise.resolve({ data: { items: [{ id: "employee-1", name: "Donnell" }] } });
    if (url === "/calendar/feed") return Promise.resolve({ data: { items, total: items.length } });
    return Promise.resolve({ data: {} });
  });
  api.post.mockResolvedValue({ data: { id: "event-created" } });
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
    route: "/shop-schedule?view=appointments&new=1&customer_id=customer-1&order_id=order-1&work_order_id=work-order-1&type=installation&title=Install%20appointment",
  });

  const dialog = await screen.findByTestId("calendar-appointment-dialog");
  expect(within(dialog).getByTestId("calendar-event-title")).toHaveValue("Install appointment");
  expect(within(dialog).getByTestId("calendar-event-customer-id")).toHaveValue("customer-1");
  expect(within(dialog).getByTestId("calendar-event-order-id")).toHaveValue("order-1");
  expect(within(dialog).getByTestId("calendar-event-work-order-id")).toHaveValue("work-order-1");

  await user.click(within(dialog).getByRole("button", { name: "Create" }));

  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/calendar/events", expect.objectContaining({
    title: "Install appointment",
    event_type: "installation",
    customer_id: "customer-1",
    order_id: "order-1",
    work_order_id: "work-order-1",
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
    customer_id: "customer-1",
    order_id: "order-1",
    work_order_id: "work-order-1",
  })));
});
