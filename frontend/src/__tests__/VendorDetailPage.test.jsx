import React from "react";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../test-utils";

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn() },
  extractError: (e, f = "err") => e?.response?.data?.detail || f,
}));
jest.mock("@/auth/AuthContext", () => ({
  __esModule: true,
  useAuth: () => ({ hasPerm: () => true, user: { id: "u1" } }),
}));
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() }, Toaster: () => null }));

import api from "@/lib/api";
import VendorDetailPage from "@/pages/VendorDetailPage";

const vendor = {
  id: "ven-1", name: "Northwind Signworks Supply", display_name: "Northwind",
  connector_key: "test_adapter", connector_tier: "api", preferred: true, active: true,
  account_number: "NW-000123", website: "https://northwind.example",
  contact_email: "sales@northwind.example", contact_phone: "555-1000",
  categories: ["vinyl", "laminate", "banner"],
};
const warehouses = [
  { id: "wh-1", code: "PDX", name: "Portland", region: "Pacific NW", lead_time_days: 1 },
  { id: "wh-2", code: "CLT", name: "Charlotte", region: "Southeast", lead_time_days: 3 },
];
const materials = [
  { id: "vm-1", material_id: "mat-1", supplier_sku: "PC-RED-30", preferred: true },
];
const pos = [
  { id: "po-1", number: "1001", status: "received", total_cents: 45000, created_at: "2026-01-10T00:00:00Z" },
  { id: "po-2", number: "1002", status: "submitted", total_cents: 12000, created_at: "2026-02-01T00:00:00Z" },
];

beforeEach(() => {
  jest.clearAllMocks();
  api.get.mockImplementation((url, cfg) => {
    if (url === "/vendors/ven-1") return Promise.resolve({ data: { vendor, warehouses } });
    if (url === "/vendors/materials") return Promise.resolve({ data: { items: materials } });
    if (url === "/purchase-orders") return Promise.resolve({ data: { items: pos } });
    return Promise.resolve({ data: {} });
  });
});

describe("VendorDetailPage", () => {
  test("renders vendor identity, warehouses, materials and PO history (happy path)", async () => {
    renderWithProviders(<VendorDetailPage />, { route: "/vendors/ven-1", path: "/vendors/:id" });
    expect(await screen.findByTestId("vendor-detail-page")).toBeInTheDocument();
    expect(screen.getByText(/Northwind/)).toBeInTheDocument();
    expect(screen.getByTestId("vendor-preferred-badge")).toBeInTheDocument();
    expect(screen.getByTestId("vendor-active-badge")).toHaveTextContent("active");
    expect(screen.getByTestId("vendor-connector-badge")).toHaveTextContent(/test_adapter/);
    expect(screen.getByTestId("vendor-account-number")).toHaveTextContent("NW-000123");
    expect(screen.getByTestId("vendor-warehouse-row-PDX")).toBeInTheDocument();
    expect(screen.getByTestId("vendor-warehouse-row-CLT")).toBeInTheDocument();
    expect(screen.getByTestId("vendor-material-row-vm-1")).toBeInTheDocument();
    expect(screen.getByTestId("vendor-po-row-po-1")).toBeInTheDocument();
    expect(screen.getByTestId("vendor-po-row-po-2")).toBeInTheDocument();
  });

  test("shows not-found when vendor is missing (error path)", async () => {
    api.get.mockImplementation((url) => {
      if (url === "/vendors/ven-1") return Promise.resolve({ data: null });
      return Promise.resolve({ data: { items: [] } });
    });
    renderWithProviders(<VendorDetailPage />, { route: "/vendors/ven-1", path: "/vendors/:id" });
    expect(await screen.findByTestId("vendor-detail-not-found")).toBeInTheDocument();
  });
});
