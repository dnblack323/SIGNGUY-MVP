import "@testing-library/jest-dom";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";
import ReportsPage from "@/pages/ReportsPage";
import api from "@/lib/api";

jest.mock("@/lib/api", () => ({
  __esModule: true,
  API: "http://api.test/api",
  default: {
    get: jest.fn(),
    post: jest.fn(),
  },
  extractError: (error) => error?.response?.data?.detail || error?.message || "Request failed",
}));

jest.mock("sonner", () => ({
  toast: {
    error: jest.fn(),
    success: jest.fn(),
  },
}));

const catalog = {
  authority: {
    title: "SIGNGUY AI | REPORT CATALOG & CUSTOM REPORT BUILDER SPEC",
    pages: 11,
    location: "Business & Finance -> Reports",
  },
  official_webstore_types: ["B2B", "Fundraiser", "Event", "Promotional", "Employee", "General"],
  blocked_requirements: [{ id: "blocked-1", name: "Dashboard widget publishing", reason: "Dashboard Customizer contract is deferred." }],
  reports: [
    {
      key: "overview.executive_summary",
      title: "Executive Summary",
      category: "overview",
      data_source: "finance+orders",
      date_basis: "mixed",
      calc_basis: "stored_source_values",
      limitations: ["Do not sum mixed-basis metrics."],
      columns: [
        { key: "metric", label: "Metric" },
        { key: "value_cents", label: "Value", money: true },
      ],
    },
    {
      key: "orders.by_status",
      title: "Orders by Status",
      category: "operations",
      data_source: "orders",
      date_basis: "created_at",
      calc_basis: "stored_order_totals",
      limitations: [],
      columns: [
        { key: "status", label: "Status" },
        { key: "order_count", label: "Orders" },
      ],
    },
    {
      key: "webstores.sales_by_store",
      title: "Webstore Sales by Store",
      category: "webstores",
      data_source: "webstore_buyer_orders",
      date_basis: "created_at",
      calc_basis: "stored_webstore_order_totals",
      limitations: [],
      columns: [
        { key: "store_name", label: "Store" },
        { key: "sales_cents", label: "Sales", money: true },
      ],
    },
  ],
  custom_datasets: [
    {
      key: "orders",
      date_field: "created_at",
      fields: ["number", "status", "total_cents"],
      filters: ["status", "date_from", "date_to"],
      group_by: ["status"],
      sort: ["created_at", "total_cents"],
    },
  ],
};

function mockCommonApis() {
  api.get.mockImplementation((path) => {
    if (path === "/reports") return Promise.resolve({ data: catalog });
    if (path === "/reports/saved") {
      return Promise.resolve({
        data: {
          saved_reports: [
            { id: "saved-1", name: "Saved Executive Summary", source_kind: "standard", standard_report_key: "overview.executive_summary", status: "active" },
          ],
        },
      });
    }
    if (path === "/reports/schedules") return Promise.resolve({ data: { schedules: [{ id: "sched-1", report_definition_id: "saved-1", cadence: "weekly" }] } });
    if (path === "/reports/exports/history") {
      return Promise.resolve({ data: { exports: [{ id: "exp-1", export_format: "csv", standard_report_key: "overview.executive_summary", row_count: 1, status: "completed", created_at: "2026-07-29T12:00:00Z" }] } });
    }
    return Promise.resolve({ data: {} });
  });
  api.post.mockImplementation((path) => {
    if (path === "/reports/overview.executive_summary/run") {
      return Promise.resolve({
        data: {
          key: "overview.executive_summary",
          title: "Executive Summary",
          category: "overview",
          columns: [...catalog.reports[0].columns, { key: "drill_down", label: "Drill-down" }],
          rows: [{ metric: "Revenue collected", value_cents: 250000, drill_down: [{ entity_type: "payments", entity_id: "confirmed", route: "/payments" }] }],
          row_count: 1,
          filters: {},
        },
      });
    }
    if (path === "/reports/custom/preview") {
      return Promise.resolve({
        data: {
          dataset: "orders",
          fields: ["number", "status", "total_cents"],
          rows: [{ status: "confirmed", row_count: 2, total_cents: 100000 }],
          row_count: 1,
          filters: {},
        },
      });
    }
    if (path === "/reports/saved") return Promise.resolve({ data: { saved_report: { id: "saved-new" } } });
    if (path === "/reports/saved/saved-1/run") {
      return Promise.resolve({
        data: {
          title: "Saved Executive Summary",
          columns: catalog.reports[0].columns,
          rows: [{ metric: "Open order value", value_cents: 100000 }],
          row_count: 1,
        },
      });
    }
    if (path === "/reports/saved/saved-1/duplicate") return Promise.resolve({ data: { saved_report: { id: "saved-copy" } } });
    if (path === "/reports/saved/saved-1/archive") return Promise.resolve({ data: { status: "archived" } });
    if (path === "/reports/schedules") return Promise.resolve({ data: { schedule: { id: "sched-new" } } });
    if (path === "/reports/schedules/sched-1/run") return Promise.resolve({ data: { schedule_run: { id: "run-1", status: "succeeded" } } });
    return Promise.resolve({ data: {} });
  });
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    headers: { get: () => 'attachment; filename="report.csv"' },
    blob: () => Promise.resolve(new Blob(["csv"])),
  });
  global.URL.createObjectURL = jest.fn(() => "blob://report");
  global.URL.revokeObjectURL = jest.fn();
  jest.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
}

beforeEach(() => {
  jest.clearAllMocks();
  mockCommonApis();
});

test("renders the PDF-governed report catalog and runs a standard report", async () => {
  const user = userEvent.setup();
  renderWithProviders(<ReportsPage />);

  expect(await screen.findByText(/SIGNGUY AI \| REPORT CATALOG/)).toBeInTheDocument();
  expect(screen.getByText(/B2B, Fundraiser, Event, Promotional, Employee, General/)).toBeInTheDocument();
  expect(screen.getByTestId("tab-overview")).toBeInTheDocument();
  expect(screen.getByTestId("tab-webstores")).toBeInTheDocument();

  await user.click(screen.getByTestId("report-run"));

  expect(await screen.findByText("Revenue collected")).toBeInTheDocument();
  expect(screen.getByText("$2,500.00")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "payments" })).toHaveAttribute("href", "/payments");
  expect(screen.getByText(/Dashboard widget publishing/)).toBeInTheDocument();
});

test("exports standard reports through the backend export endpoint", async () => {
  const user = userEvent.setup();
  renderWithProviders(<ReportsPage />);

  await waitFor(() => expect(screen.getAllByText("Executive Summary").length).toBeGreaterThan(0));
  await user.click(screen.getByTestId("report-run"));
  await screen.findByText("Revenue collected");
  await user.click(screen.getByTestId("report-export-xlsx"));

  await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
    "http://api.test/api/reports/overview.executive_summary/export/xlsx",
    expect.objectContaining({ method: "POST" }),
  ));
});

test("custom builder uses approved datasets, fields, grouping, and save action", async () => {
  const user = userEvent.setup();
  renderWithProviders(<ReportsPage />);

  await user.click(await screen.findByTestId("tab-custom"));
  await screen.findByTestId("custom-field-number");
  await user.click(screen.getByTestId("custom-field-number"));
  await user.click(screen.getByTestId("custom-field-status"));
  await user.click(screen.getByTestId("custom-field-total_cents"));
  await user.click(screen.getByTestId("custom-group-status"));
  await user.click(screen.getByTestId("custom-run-preview"));

  expect(await screen.findByText("confirmed")).toBeInTheDocument();
  await user.click(screen.getByTestId("report-save"));

  expect(api.post).toHaveBeenCalledWith("/reports/custom/preview", expect.objectContaining({
    dataset: "orders",
    fields: ["number", "status", "total_cents"],
    group_by: ["status"],
  }));
  expect(api.post).toHaveBeenCalledWith("/reports/saved", expect.objectContaining({
    source_kind: "custom",
    custom_dataset: "orders",
  }));
});

test("saved reports, schedule runs, and export history render as working surfaces", async () => {
  const user = userEvent.setup();
  renderWithProviders(<ReportsPage />);

  await user.click(await screen.findByTestId("tab-saved"));
  expect(await screen.findByText("Saved Executive Summary")).toBeInTheDocument();
  await user.click(screen.getByText("Run"));
  expect(await screen.findByText("Open order value")).toBeInTheDocument();

  await user.click(screen.getByTestId("tab-scheduled"));
  expect(await screen.findByText("weekly")).toBeInTheDocument();
  await user.click(screen.getByText("Run now"));
  expect(api.post).toHaveBeenCalledWith("/reports/schedules/sched-1/run");

  await user.click(screen.getByTestId("tab-exports"));
  const panel = await screen.findByTestId("reports-exports-panel");
  expect(within(panel).getByText("overview.executive_summary")).toBeInTheDocument();
});
