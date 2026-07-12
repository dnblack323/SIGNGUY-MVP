import React from "react";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
import MaterialDetailPage from "@/pages/MaterialDetailPage";

const material = {
  id: "mat-1", name: "PermaCast Red 30\"", sku: "PC-RED-30", category: "vinyl",
  manufacturer: "Orafol", brand: "PermaCast", series: "970", purchase_unit: "linear_foot",
  unit_of_measure: "linear_foot", current_cost_cents: 18900, cost_unit: "linear_foot",
  reorder_point: 20, active: true,
};
const balances = [
  { id: "b1", material_id: "mat-1", location_id: "loc-1", quantity_on_hand: 30, quantity_reserved: 5, last_received_at: "2026-01-01T00:00:00Z" },
  { id: "b2", material_id: "mat-1", location_id: "loc-2", quantity_on_hand: 10, quantity_reserved: 0 },
];
const costHistory = [
  { id: "h1", material_id: "mat-1", cost_cents: 18900, cost_unit: "linear_foot", effective_at: "2026-01-15T00:00:00Z", source: "receiving" },
  { id: "h2", material_id: "mat-1", cost_cents: 17500, cost_unit: "linear_foot", effective_at: "2025-11-01T00:00:00Z", source: "manual" },
];

beforeEach(() => {
  jest.clearAllMocks();
  api.get.mockImplementation((url) => {
    if (url === "/materials/mat-1") return Promise.resolve({ data: { material, balances, cost_history: costHistory } });
    if (url === "/inventory/movements") return Promise.resolve({ data: { items: [] } });
    return Promise.resolve({ data: {} });
  });
});

describe("MaterialDetailPage", () => {
  test("shows metadata, balances and totals (happy path)", async () => {
    renderWithProviders(<MaterialDetailPage />, { route: "/materials/mat-1", path: "/materials/:id" });
    expect(await screen.findByTestId("material-detail-page")).toBeInTheDocument();
    expect(screen.getByText(/PermaCast Red/)).toBeInTheDocument();
    expect(screen.getByTestId("material-sku")).toHaveTextContent("PC-RED-30");
    // on hand = 30+10 = 40; reserved = 5; available = 35
    expect(screen.getByTestId("material-on-hand")).toHaveTextContent("40");
    expect(screen.getByTestId("material-reserved")).toHaveTextContent("5");
    expect(screen.getByTestId("material-available")).toHaveTextContent("35");
    expect(screen.getByTestId("material-current-cost")).toHaveTextContent("$189.00");
    expect(screen.getByTestId("material-balance-row-loc-1")).toBeInTheDocument();
    expect(screen.getByTestId("material-balance-row-loc-2")).toBeInTheDocument();
  });

  test("cost history drawer opens and lists immutable rows", async () => {
    const user = userEvent.setup();
    renderWithProviders(<MaterialDetailPage />, { route: "/materials/mat-1", path: "/materials/:id" });
    await user.click(await screen.findByTestId("material-cost-history-open"));
    expect(await screen.findByTestId("material-cost-history-drawer")).toBeInTheDocument();
    expect(screen.getByTestId("material-cost-row-h1")).toBeInTheDocument();
    expect(screen.getByTestId("material-cost-row-h2")).toBeInTheDocument();
  });

  test("shows not-found when the material id is unknown (error path)", async () => {
    api.get.mockImplementation((url) => {
      if (url === "/materials/mat-1") return Promise.resolve({ data: null });
      return Promise.resolve({ data: {} });
    });
    renderWithProviders(<MaterialDetailPage />, { route: "/materials/mat-1", path: "/materials/:id" });
    expect(await screen.findByTestId("material-detail-not-found")).toBeInTheDocument();
  });
});
