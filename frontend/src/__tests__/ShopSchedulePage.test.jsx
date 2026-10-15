import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ShopSchedulePage from "@/pages/ShopSchedulePage";
import { groupByDate, itemDateKeys, layoutDayItems, localDateKey, scheduleType, visibleDateKeys } from "@/components/schedule/scheduleModel";
import { toast } from "sonner";
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

let mockRole = "manager";
jest.mock("@/auth/AuthContext", () => ({
  useAuth: () => ({
    user: { role: mockRole },
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
  mockRole = "manager";
  mockScheduleApi();
});

const localMidnightIso = (y, m, d) => new Date(y, m - 1, d).toISOString();

test("Day view shows operational items in type lanes without shifts, absences or internal meetings", async () => {
  renderWithProviders(<ShopSchedulePage />, { route: "/shop-schedule?view=day&date=2026-08-14" });

  expect(await screen.findByTestId("schedule-day")).toBeInTheDocument();
  expect(screen.getByTestId("shop-schedule-view-day")).toHaveAttribute("aria-selected", "true");
  const install = await screen.findByTestId("schedule-day-item-calendar_event-event-1");
  expect(install).toHaveTextContent("Install at Rusty Lemon");
  expect(install).toHaveTextContent("Donnell");
  expect(install).toHaveTextContent("Order");
  expect(screen.getByTestId("schedule-lane-installation")).toBeInTheDocument();
  expect(screen.queryByText("Gary shift")).not.toBeInTheDocument();
  expect(screen.queryByText("Maria PTO")).not.toBeInTheDocument();
  expect(screen.queryByText("Internal team meeting")).not.toBeInTheDocument();
  expect(api.get).toHaveBeenCalledWith("/calendar/feed", expect.objectContaining({
    params: expect.objectContaining({
      start_at: localMidnightIso(2026, 8, 14),
      end_at: localMidnightIso(2026, 8, 15),
      window_first: true,
    }),
  }));
});

test("Month view shows color-coded daily counts and opens the selected day", async () => {
  const user = userEvent.setup();
  renderWithProviders(<ShopSchedulePage />, { route: "/shop-schedule?date=2026-08-14" });

  expect(await screen.findByTestId("schedule-month")).toBeInTheDocument();
  expect(screen.getByTestId("schedule-date-label")).toHaveTextContent(/August 2026/);
  expect(await screen.findByTestId("schedule-month-count-2026-08-14-installation")).toHaveTextContent("1");
  expect(screen.getByTestId("schedule-month-count-2026-08-15-production")).toHaveTextContent("1");
  expect(screen.getByTestId("schedule-month-count-2026-08-16-task")).toHaveTextContent("1");
  expect(screen.queryByTestId("schedule-month-count-2026-08-14-other")).not.toBeInTheDocument();
  await user.click(screen.getByTestId("schedule-month-count-2026-08-14-installation"));
  expect(await screen.findByTestId("schedule-day")).toBeInTheDocument();
  expect(screen.getByTestId("schedule-filter-installation")).toHaveAttribute("aria-selected", "true");
});

test("Production and Installation filters limit the schedule; All keeps other activity types", async () => {
  const user = userEvent.setup();
  renderWithProviders(<ShopSchedulePage />, { route: "/shop-schedule?date=2026-08-14" });
  await screen.findByTestId("schedule-month-count-2026-08-14-installation");

  await user.click(screen.getByTestId("schedule-filter-production"));
  await waitFor(() => expect(screen.queryByTestId("schedule-month-count-2026-08-14-installation")).not.toBeInTheDocument());
  expect(screen.getByTestId("schedule-month-count-2026-08-15-production")).toBeInTheDocument();
  expect(screen.queryByTestId("schedule-month-count-2026-08-16-task")).not.toBeInTheDocument();

  await user.click(screen.getByTestId("schedule-filter-installation"));
  expect(await screen.findByTestId("schedule-month-count-2026-08-14-installation")).toBeInTheDocument();
  expect(screen.queryByTestId("schedule-month-count-2026-08-15-production")).not.toBeInTheDocument();

  await user.click(screen.getByTestId("schedule-filter-all"));
  expect(await screen.findByTestId("schedule-month-count-2026-08-16-task")).toBeInTheDocument();
  expect(screen.getByTestId("schedule-month-count-2026-08-18-pickup_delivery")).toBeInTheDocument();
});

test("legacy view links still open the new views", async () => {
  renderWithProviders(<ShopSchedulePage />, { route: "/shop-schedule?view=appointments&date=2026-08-14" });
  expect(await screen.findByTestId("schedule-day")).toBeInTheDocument();
});

test("URL context opens create appointment with supported linked record IDs", async () => {
  const user = userEvent.setup();
  renderWithProviders(<ShopSchedulePage />, {
    route: "/shop-schedule?view=day&new=1&customer_id=customer-1&quote_id=quote-1&order_id=order-1&order_item_id=item-1&work_order_id=work-order-1&production_stage_id=stage-1&wrap_project_id=wrap-1&source_type=order_item_installation&source_id=item-1&type=installation&title=Install%20appointment",
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

test("event details show people, resources and record links, and Edit saves through the canonical endpoint", async () => {
  const user = userEvent.setup();
  renderWithProviders(<ShopSchedulePage />, { route: "/shop-schedule?view=day&date=2026-08-14" });

  await user.click(await screen.findByTestId("schedule-day-item-calendar_event-event-1"));
  const details = await screen.findByTestId("schedule-event-details");
  expect(within(details).getByTestId("schedule-details-people")).toHaveTextContent("Donnell, Bill");
  expect(within(details).getByTestId("schedule-details-resources")).toHaveTextContent("HP Latex");
  expect(within(details).getByRole("link", { name: "Open Order" })).toHaveAttribute("href", "/orders/order-1");
  expect(within(details).getByRole("link", { name: "Open Work Order" })).toHaveAttribute("href", "/work-orders/work-order-1");

  await user.click(within(details).getByTestId("schedule-details-edit"));
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
  renderWithProviders(<ShopSchedulePage />, { route: "/shop-schedule?new=1&date=2026-08-14" });

  const dialog = await screen.findByTestId("calendar-appointment-dialog");
  await user.type(within(dialog).getByTestId("calendar-event-title"), "Conflicting install");
  await user.click(await within(dialog).findByRole("checkbox", { name: "Install Bay 1" }));
  expect(await within(dialog).findByTestId("calendar-resource-conflicts")).toHaveTextContent("Install Bay 1");

  await user.click(within(dialog).getByRole("button", { name: "Create" }));

  expect(await within(dialog).findByTestId("calendar-conflict-warning")).toHaveTextContent("Install Bay 1");
  expect(api.post).not.toHaveBeenCalledWith("/calendar/events", expect.anything());
});

test("appointment lifecycle actions complete and reopen canonical calendar events", async () => {
  const user = userEvent.setup();
  renderWithProviders(<ShopSchedulePage />, { route: "/shop-schedule?view=day&date=2026-08-14" });

  await user.click(await screen.findByTestId("schedule-day-item-calendar_event-event-1"));
  await user.click(await screen.findByTestId("shop-schedule-complete-event-1"));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/calendar/events/event-1/complete", { outcome_note: "Completed from Shop Schedule" }));

  for (let i = 0; i < 4; i += 1) await user.click(screen.getByRole("button", { name: "Next day" }));
  await user.click(await screen.findByTestId("schedule-day-item-calendar_event-event-3"));
  await user.click(await screen.findByTestId("shop-schedule-reopen-event-3"));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/calendar/events/event-3/reopen", { reason: "Reopened from Shop Schedule" }));
});

function rejectReopenWithConflict() {
  const conflictError = Object.assign(new Error("Calendar conflict requires manager override reason"), {
    response: { status: 409, data: { detail: { code: "conflict", message: "Calendar conflict requires manager override reason",
      conflicts: [{ resource_name: "Install Van", title: "Fleet decals", start_at: "2026-08-18T13:00:00.000Z", end_at: "2026-08-18T14:00:00.000Z" }] } } },
  });
  api.post.mockImplementation((url, body) => {
    if (url === "/calendar/events/event-3/reopen") {
      return body?.conflict_override_reason ? Promise.resolve({ data: { id: "event-3", status: "scheduled" } }) : Promise.reject(conflictError);
    }
    return Promise.resolve({ data: {} });
  });
}

async function openCompletedPickup(user) {
  renderWithProviders(<ShopSchedulePage />, { route: "/shop-schedule?view=day&date=2026-08-18" });
  await user.click(await screen.findByTestId("schedule-day-item-calendar_event-event-3"));
  await user.click(await screen.findByTestId("shop-schedule-reopen-event-3"));
  return screen.findByTestId("calendar-conflict-warning");
}

test("a manager reopening into a booked slot sees the conflict and can reopen with an override reason", async () => {
  const user = userEvent.setup();
  rejectReopenWithConflict();
  const warning = await openCompletedPickup(user);
  expect(warning).toHaveTextContent("Install Van: Fleet decals");
  const submit = screen.getByTestId("calendar-conflict-override-submit");
  expect(submit).toBeDisabled();
  await user.type(screen.getByTestId("calendar-conflict-override-reason"), "Second van borrowed");
  await user.click(submit);
  await waitFor(() => expect(api.post).toHaveBeenLastCalledWith("/calendar/events/event-3/reopen", {
    reason: "Reopened from Shop Schedule", conflict_override_reason: "Second van borrowed",
  }));
  expect(toast.success).toHaveBeenCalledWith("Appointment reopened with override · now scheduled");
  await waitFor(() => expect(screen.queryByTestId("schedule-event-details")).not.toBeInTheDocument());
});

test("staff without override authority see the reopen conflict but are not offered an override", async () => {
  mockRole = "staff";
  const user = userEvent.setup();
  rejectReopenWithConflict();
  const warning = await openCompletedPickup(user);
  expect(warning).toHaveTextContent("Install Van: Fleet decals");
  expect(screen.getByTestId("calendar-conflict-manager-required")).toBeInTheDocument();
  expect(screen.queryByTestId("calendar-conflict-override-reason")).not.toBeInTheDocument();
  expect(screen.queryByTestId("calendar-conflict-override-submit")).not.toBeInTheDocument();
  expect(api.post).toHaveBeenCalledTimes(1);
});

test("a busy month is read page by page so later days are not dropped", async () => {
  const at = (day, hour) => new Date(2026, 7, day, hour).toISOString();
  const page1 = [{ ...feedItems[0], id: "calendar_event:early", source_id: "early", start_at: at(3, 9), end_at: at(3, 10) }];
  const page2 = [{ ...feedItems[0], id: "calendar_event:late", source_id: "late", start_at: at(28, 9), end_at: at(28, 10) }];
  const base = api.get.getMockImplementation();
  api.get.mockImplementation((url, config) => {
    if (url !== "/calendar/feed") return base(url, config);
    const skip = config.params.skip;
    return Promise.resolve({ data: skip === 0 ? { items: page1, total: 2, has_more: true } : { items: page2, total: 2, has_more: false } });
  });
  renderWithProviders(<ShopSchedulePage />, { route: "/shop-schedule?date=2026-08-14" });
  expect(await screen.findByTestId("schedule-month-count-2026-08-28-installation")).toHaveTextContent("1");
  expect(screen.getByTestId("schedule-month-count-2026-08-03-installation")).toHaveTextContent("1");
  const feedCalls = api.get.mock.calls.filter(([url]) => url === "/calendar/feed");
  expect(feedCalls.map(([, config]) => config.params.skip)).toEqual([0, 500]);
  expect(feedCalls.every(([, config]) => config.params.limit === 500 && config.params.window_first)).toBe(true);
  expect(screen.queryByTestId("shop-schedule-truncated")).not.toBeInTheDocument();
});

test("a window larger than the page cap says so instead of silently hiding items", async () => {
  const base = api.get.getMockImplementation();
  api.get.mockImplementation((url, config) => {
    if (url !== "/calendar/feed") return base(url, config);
    const n = config.params.skip / 500;
    return Promise.resolve({ data: { items: [{ ...feedItems[0], id: `calendar_event:e${n}`, source_id: `e${n}` }], total: 6000, has_more: true } });
  });
  renderWithProviders(<ShopSchedulePage />, { route: "/shop-schedule?date=2026-08-14" });
  expect(await screen.findByTestId("shop-schedule-truncated")).toHaveTextContent("of 6,000 scheduled items");
  expect(api.get.mock.calls.filter(([url]) => url === "/calendar/feed")).toHaveLength(10);
});

describe("schedule model", () => {
  test("events longer than two months appear on every visible date they overlap", () => {
    const long = { start_at: new Date(2026, 3, 1, 8).toISOString(), end_at: new Date(2026, 8, 30, 17).toISOString() }; // Apr 1 - Sep 30
    const august = visibleDateKeys("month", "2026-08-14");
    const keys = itemDateKeys(long, august);
    expect(keys[0]).toBe(august.first);
    expect(keys[keys.length - 1]).toBe(august.last);
    expect(keys).toHaveLength(42);
    expect(groupByDate([long], august).get("2026-08-31")).toHaveLength(1);
    expect(itemDateKeys(long, visibleDateKeys("day", "2026-09-29"))).toEqual(["2026-09-29"]);
    expect(itemDateKeys(long, visibleDateKeys("day", "2026-10-01"))).toEqual([]);
  });
  test("events land on their local calendar date and multi-day events cover every date", () => {
    const late = { start_at: new Date(2026, 7, 14, 21, 30).toISOString(), end_at: new Date(2026, 7, 14, 23, 0).toISOString() };
    expect(itemDateKeys(late)).toEqual(["2026-08-14"]);
    const span = { start_at: new Date(2026, 7, 14, 16).toISOString(), end_at: new Date(2026, 7, 16, 10).toISOString() };
    expect(itemDateKeys(span)).toEqual(["2026-08-14", "2026-08-15", "2026-08-16"]);
    const endsAtMidnight = { start_at: new Date(2026, 7, 14, 22).toISOString(), end_at: new Date(2026, 7, 15, 0).toISOString() };
    expect(itemDateKeys(endsAtMidnight)).toEqual(["2026-08-14"]);
    expect(groupByDate([span]).get("2026-08-15")).toHaveLength(1);
    expect(localDateKey(new Date(2026, 0, 31, 23, 59))).toBe("2026-01-31");
  });

  test("overlapping items in one lane are placed side by side", () => {
    const at = (h, m = 0) => new Date(2026, 7, 14, h, m).toISOString();
    const laid = layoutDayItems([
      { id: "a", start_at: at(9), end_at: at(11) },
      { id: "b", start_at: at(10), end_at: at(12) },
      { id: "c", start_at: at(11), end_at: at(12) },
      { id: "d", start_at: at(14), end_at: at(15) },
    ], "2026-08-14");
    const byId = Object.fromEntries(laid.map((e) => [e.item.id, e]));
    expect(byId.a.columns).toBe(2);
    expect(byId.a.column).not.toBe(byId.b.column);
    expect(byId.c.column).toBe(byId.a.column);
    expect(byId.d.columns).toBe(1);
  });

  test("activity types map production, installation and other operational items", () => {
    expect(scheduleType({ source_type: "production_stage" })).toBe("production");
    expect(scheduleType({ event_type: "installation" })).toBe("installation");
    expect(scheduleType({ event_type: "vehicle_pickup" })).toBe("pickup_delivery");
    expect(scheduleType({ event_type: "site_survey" })).toBe("appointment");
    expect(scheduleType({ source_type: "task", event_type: "task_due" })).toBe("task");
    expect(scheduleType({ event_type: "custom" })).toBe("other");
  });
});
