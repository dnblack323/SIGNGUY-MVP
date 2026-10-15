import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import DashboardPage from "@/pages/DashboardPage";
import { moveWidget, toggleWidget } from "@/components/home/DashboardCustomizer";
import { renderWithProviders } from "@/test-utils";
import api from "@/lib/api";

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: { get: jest.fn(), put: jest.fn(), delete: jest.fn() },
  extractError: (_err, fallback) => fallback,
}));

const W = {
  ordersKpi: { key: "active_orders_kpi", family: "active_orders", kind: "kpi", title: "Active orders", to: "/orders" },
  ordersList: { key: "active_orders_list", family: "active_orders", kind: "list", title: "Active orders", to: "/orders" },
  production: { key: "production_status", family: "production", kind: "summary", title: "Production status", to: "/work-orders/board" },
  customers: { key: "recent_customers", family: "recent_customers", kind: "list", title: "Recent customers", to: "/customers" },
};
const widgets = Object.values(W);
const layout = { version: 1, order: widgets.map((w) => w.key), hidden: ["active_orders_list"], collapsed: [] };
const payload = {
  layout,
  widgets,
  restricted: [{ key: "todays_schedule", family: "todays_schedule", kind: "list", title: "Today's schedule", to: "/shop-schedule", required_permission: "schedule:read" }],
  data: {
    active_orders_kpi: { state: "ready", value: 7 },
    production_status: { state: "ready", total: 3, rows: [{ label: "In progress", value: 3, to: "/work-orders?production_status=in_progress" }] },
    recent_customers: {
      state: "ready", total: 6,
      items: Array.from({ length: 6 }, (_, i) => ({ id: `c${i}`, title: `Customer ${i}`, to: `/customers/c${i}` })),
    },
  },
};

beforeEach(() => {
  jest.clearAllMocks();
  api.get.mockResolvedValue({ data: payload });
  api.put.mockImplementation((_url, body) => Promise.resolve({ data: { layout: body } }));
  api.delete.mockResolvedValue({ data: { layout } });
});

test("enabling a widget replaces the other presentation of the same metric", () => {
  const { draft, replaced } = toggleWidget(layout, widgets, "active_orders_list");
  expect(draft.hidden).toContain("active_orders_kpi");
  expect(draft.hidden).not.toContain("active_orders_list");
  expect(replaced.key).toBe("active_orders_kpi");
});

test("reordering moves a widget one place", () => {
  expect(moveWidget(layout, "recent_customers", -1).order.slice(-2)).toEqual(["recent_customers", "production_status"]);
  expect(moveWidget(layout, "active_orders_kpi", -1)).toBe(layout);
});

test("Home renders KPI, summary and list zones with record links and real values", async () => {
  renderWithProviders(<DashboardPage />);
  const kpi = await screen.findByTestId("home-widget-active_orders_kpi");
  expect(kpi).toHaveAttribute("href", "/orders");
  expect(within(kpi).getByTestId("home-kpi-value")).toHaveTextContent("7");
  expect(screen.getByTestId("home-summary-zone")).toContainElement(screen.getByTestId("home-widget-production_status"));
  const list = screen.getByTestId("home-widget-recent_customers");
  expect(screen.getByTestId("home-list-column")).toContainElement(list);
  expect(within(list).getAllByRole("link", { name: /Customer/ })).toHaveLength(5);
  fireEvent.click(within(list).getByRole("button", { name: "Show all 6" }));
  expect(within(list).getByRole("link", { name: /Customer 5/ })).toHaveAttribute("href", "/customers/c5");
  expect(screen.queryByTestId("home-widget-active_orders_list")).not.toBeInTheDocument();
  expect(api.get).toHaveBeenCalledWith("/dashboard/home", expect.objectContaining({ params: expect.objectContaining({ day_start: expect.any(String) }) }));
});

test("collapsing a list widget saves the preference", async () => {
  renderWithProviders(<DashboardPage />);
  fireEvent.click(await screen.findByRole("button", { name: "Collapse Recent customers" }));
  await waitFor(() => expect(api.put).toHaveBeenCalledWith("/dashboard/home/layout", expect.objectContaining({ collapsed: ["recent_customers"] })));
});

test("customizer saves visibility and order, shows restricted widgets, and restores defaults", async () => {
  renderWithProviders(<DashboardPage />);
  fireEvent.click(await screen.findByTestId("home-customize-button"));
  const dialog = await screen.findByTestId("home-customizer");
  expect(within(dialog).getByTestId("home-customizer-restricted")).toHaveTextContent("Needs schedule:read");
  fireEvent.click(within(dialog).getByRole("checkbox", { name: /Active orders \(List\)/ }));
  expect(within(dialog).getByTestId("home-customizer-notice")).toHaveTextContent("replaces Active orders (Number)");
  fireEvent.click(within(dialog).getByRole("button", { name: "Move Recent customers up" }));
  fireEvent.click(within(dialog).getByRole("button", { name: "Save Home" }));
  await waitFor(() => expect(api.put).toHaveBeenCalledTimes(1));
  const saved = api.put.mock.calls[0][1];
  expect(saved.hidden).toEqual(expect.arrayContaining(["active_orders_kpi"]));
  expect(saved.hidden).not.toContain("active_orders_list");
  expect(saved.order.indexOf("recent_customers")).toBeLessThan(saved.order.indexOf("production_status"));

  fireEvent.click(screen.getByTestId("home-customize-button"));
  fireEvent.click(within(await screen.findByTestId("home-customizer")).getByRole("button", { name: "Restore default layout" }));
  await waitFor(() => expect(api.delete).toHaveBeenCalledWith("/dashboard/home/layout"));
});
