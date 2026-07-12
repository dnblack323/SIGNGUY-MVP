/**
 * Smoke tests for the remaining EC7 screens — verify the page renders its top-
 * level test-id and does not crash on an empty backend response. Covers:
 * SupplyCenter, PurchaseOrders, Expenses, FinanceDashboard, TaxReports, Reports.
 */
import React from "react";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../test-utils";

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: { get: jest.fn().mockResolvedValue({ data: {} }), post: jest.fn() },
  extractError: (e, f = "err") => e?.response?.data?.detail || f,
}));
jest.mock("@/auth/AuthContext", () => ({
  __esModule: true,
  useAuth: () => ({ hasPerm: () => true, user: { id: "u1" } }),
}));
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() }, Toaster: () => null }));

import api from "@/lib/api";
import SupplyCenterPage from "@/pages/SupplyCenterPage";
import PurchaseOrdersPage from "@/pages/PurchaseOrdersPage";
import ExpensesPage from "@/pages/ExpensesPage";
import FinanceDashboardPage from "@/pages/FinanceDashboardPage";
import TaxReportsPage from "@/pages/TaxReportsPage";
import ReportsPage from "@/pages/ReportsPage";

beforeEach(() => {
  jest.clearAllMocks();
  // Return a safe empty shape for anything that resembles a list.
  api.get.mockResolvedValue({ data: { items: [], reports: [], datasets: [] } });
});

describe("EC7 screens smoke", () => {
  test("SupplyCenterPage mounts", async () => {
    renderWithProviders(<SupplyCenterPage />);
    expect(await screen.findByTestId("supply-center-page")).toBeInTheDocument();
  });

  test("PurchaseOrdersPage mounts and shows empty state", async () => {
    renderWithProviders(<PurchaseOrdersPage />);
    expect(await screen.findByTestId("purchase-orders-page")).toBeInTheDocument();
    expect(await screen.findByText(/No purchase orders yet/i)).toBeInTheDocument();
  });

  test("ExpensesPage mounts", async () => {
    renderWithProviders(<ExpensesPage />);
    expect(await screen.findByTestId("expenses-page")).toBeInTheDocument();
  });

  test("FinanceDashboardPage mounts", async () => {
    renderWithProviders(<FinanceDashboardPage />);
    expect(await screen.findByTestId("finance-page")).toBeInTheDocument();
  });

  test("TaxReportsPage mounts", async () => {
    renderWithProviders(<TaxReportsPage />);
    expect(await screen.findByTestId("tax-page")).toBeInTheDocument();
  });

  test("ReportsPage mounts", async () => {
    renderWithProviders(<ReportsPage />);
    expect(await screen.findByTestId("reports-page")).toBeInTheDocument();
  });
});
