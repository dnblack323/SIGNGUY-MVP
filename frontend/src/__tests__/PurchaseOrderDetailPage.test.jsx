import React from "react";
import { screen, waitFor } from "@testing-library/react";
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
import { toast } from "sonner";
import PurchaseOrderDetailPage from "@/pages/PurchaseOrderDetailPage";

const po = {
  id: "po-1", number: "1001", status: "submitted",
  vendor_id: "ven-1", vendor_snapshot: { name: "Northwind" },
  subtotal_cents: 30000, shipping_cents: 1500, handling_cents: 500, total_cents: 32000,
};
const lines = [
  { id: "line-1", description: "PermaCast 30\" Red", supplier_sku: "PC-RED-30", quantity_ordered: 10, quantity_received: 0, unit_price_cents: 18900, line_extended_cents: 189000 },
];
const movements = [
  { id: "mv-1", movement_type: "receive", direction: "in", quantity: 5, material_id: "mat-1", location_id: "loc-1", created_at: "2026-02-01T00:00:00Z" },
];

beforeEach(() => {
  jest.clearAllMocks();
  api.get.mockImplementation((url, cfg) => {
    if (url === "/purchase-orders/po-1") return Promise.resolve({ data: { purchase_order: po, lines, receiving_records: [] } });
    if (url === "/inventory/locations") return Promise.resolve({ data: { items: [{ id: "loc-1", name: "Main Shop" }] } });
    if (url === "/supply/supplier-orders") return Promise.resolve({ data: { items: [] } });
    if (url === "/inventory/movements") return Promise.resolve({ data: { items: movements } });
    return Promise.resolve({ data: {} });
  });
});

describe("PurchaseOrderDetailPage", () => {
  test("renders identity, lines and movements-from-PO table (happy path)", async () => {
    renderWithProviders(<PurchaseOrderDetailPage />, { route: "/purchase-orders/po-1", path: "/purchase-orders/:id" });
    expect(await screen.findByTestId("po-detail-page")).toBeInTheDocument();
    expect(screen.getByText(/PO #1001/)).toBeInTheDocument();
    expect(screen.getByTestId("po-vendor-link")).toHaveTextContent("Northwind");
    expect(screen.getByTestId("po-detail-status")).toHaveTextContent("submitted");
    expect(screen.getByTestId("po-line-line-1")).toBeInTheDocument();
    expect(screen.getByTestId("po-movements-table")).toBeInTheDocument();
    expect(await screen.findByTestId("po-movement-row-mv-1")).toBeInTheDocument();
  });

  test("receive dialog: zero across all lines is rejected (error path)", async () => {
    const user = userEvent.setup();
    renderWithProviders(<PurchaseOrderDetailPage />, { route: "/purchase-orders/po-1", path: "/purchase-orders/:id" });
    await user.click(await screen.findByTestId("po-receive-button"));
    // Set the only line qty to 0
    const qtyInput = await screen.findByTestId("po-receive-qty-line-1");
    await user.clear(qtyInput);
    await user.type(qtyInput, "0");
    await user.click(screen.getByTestId("po-receive-confirm"));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(expect.stringMatching(/non-zero/i)));
    expect(api.post).not.toHaveBeenCalled();
  });

  test("receive dialog: posts with Idempotency-Key (happy path)", async () => {
    const user = userEvent.setup();
    api.post.mockResolvedValue({ data: { id: "rec-1" } });
    renderWithProviders(<PurchaseOrderDetailPage />, { route: "/purchase-orders/po-1", path: "/purchase-orders/:id" });
    await user.click(await screen.findByTestId("po-receive-button"));
    await user.click(await screen.findByTestId("po-receive-confirm"));
    await waitFor(() => expect(api.post).toHaveBeenCalled());
    const [url, body, opts] = api.post.mock.calls[0];
    expect(url).toBe("/purchase-orders/po-1/receive");
    expect(opts.headers["Idempotency-Key"]).toBeTruthy();
    expect(body.lines[0]).toMatchObject({ po_line_id: "line-1" });
    expect(body.lines[0].quantity).toBeGreaterThan(0);
  });
});
