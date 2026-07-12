/**
 * InventoryPage tests — Physical Count + Transfer dialogs.
 */
import React from "react";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";

// --- Mocks -----------------------------------------------------------------
jest.mock("@/lib/api", () => {
  const post = jest.fn();
  const get = jest.fn();
  return {
    __esModule: true,
    default: { get, post, patch: jest.fn(), delete: jest.fn() },
    extractError: (err, fb = "err") => err?.response?.data?.detail || fb,
  };
});
jest.mock("@/auth/AuthContext", () => ({
  __esModule: true,
  useAuth: () => ({ hasPerm: () => true, user: { id: "u1", tenant_id: "t1" } }),
}));
jest.mock("sonner", () => ({
  toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() },
  Toaster: () => null,
}));

import api from "@/lib/api";
import { toast } from "sonner";
import InventoryPage from "@/pages/InventoryPage";

const locations = [
  { id: "loc-1", name: "Main Shop", kind: "shop", active: true },
  { id: "loc-2", name: "Warehouse", kind: "warehouse", active: true },
];

beforeEach(() => {
  jest.clearAllMocks();
  api.get.mockImplementation((url) => {
    if (url === "/inventory/locations") return Promise.resolve({ data: { items: locations } });
    if (url === "/inventory/items") return Promise.resolve({ data: { items: [] } });
    if (url === "/inventory/movements") return Promise.resolve({ data: { items: [] } });
    if (url === "/materials") return Promise.resolve({ data: { items: [] } });
    return Promise.resolve({ data: { items: [] } });
  });
});

describe("InventoryPage — physical count + transfer", () => {
  test("renders header and tabs", async () => {
    renderWithProviders(<InventoryPage />);
    expect(await screen.findByTestId("inventory-page")).toBeInTheDocument();
    expect(screen.getByTestId("tab-items")).toBeInTheDocument();
    expect(screen.getByTestId("tab-materials")).toBeInTheDocument();
    expect(screen.getByTestId("tab-movements")).toBeInTheDocument();
    expect(screen.getByTestId("tab-locations")).toBeInTheDocument();
  });

  test("physical count dialog: reason is required (error path)", async () => {
    const user = userEvent.setup();
    renderWithProviders(<InventoryPage />);
    await user.click(await screen.findByTestId("physical-count-open"));
    const locSel = await screen.findByTestId("physical-count-location");
    await user.selectOptions(locSel, "loc-1");
    await user.type(screen.getByTestId("physical-count-material"), "mat-1");
    await user.type(screen.getByTestId("physical-count-observed"), "10");
    await user.click(screen.getByTestId("physical-count-confirm"));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(expect.stringMatching(/reason/i)));
    expect(api.post).not.toHaveBeenCalled();
  });

  test("physical count dialog: happy path posts to /inventory/adjustments/count with Idempotency-Key", async () => {
    const user = userEvent.setup();
    api.post.mockResolvedValue({ data: { id: "mv-1" } });
    renderWithProviders(<InventoryPage />);
    await user.click(await screen.findByTestId("physical-count-open"));
    await user.selectOptions(await screen.findByTestId("physical-count-location"), "loc-1");
    await user.type(screen.getByTestId("physical-count-material"), "mat-1");
    await user.type(screen.getByTestId("physical-count-observed"), "12");
    await user.type(screen.getByTestId("physical-count-reason"), "quarterly count");
    await user.click(screen.getByTestId("physical-count-confirm"));
    await waitFor(() => expect(api.post).toHaveBeenCalled());
    const [url, body, opts] = api.post.mock.calls[0];
    expect(url).toBe("/inventory/adjustments/count");
    expect(body).toMatchObject({ material_id: "mat-1", location_id: "loc-1", observed_quantity: 12, reason: "quarterly count" });
    expect(opts.headers["Idempotency-Key"]).toBeTruthy();
    expect(toast.success).toHaveBeenCalled();
  });

  test("transfer dialog: same source and destination is rejected", async () => {
    const user = userEvent.setup();
    renderWithProviders(<InventoryPage />);
    await user.click(await screen.findByTestId("transfer-open"));
    await user.type(await screen.findByTestId("transfer-material"), "mat-1");
    await user.selectOptions(screen.getByTestId("transfer-from"), "loc-1");
    await user.selectOptions(screen.getByTestId("transfer-to"), "loc-1");
    await user.type(screen.getByTestId("transfer-quantity"), "5");
    await user.click(screen.getByTestId("transfer-confirm"));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(expect.stringMatching(/differ/i)));
    expect(api.post).not.toHaveBeenCalled();
  });

  test("transfer dialog: happy path posts paired movement request", async () => {
    const user = userEvent.setup();
    api.post.mockResolvedValue({ data: { movements: [{}, {}] } });
    renderWithProviders(<InventoryPage />);
    await user.click(await screen.findByTestId("transfer-open"));
    await user.type(await screen.findByTestId("transfer-material"), "mat-1");
    await user.selectOptions(screen.getByTestId("transfer-from"), "loc-1");
    await user.selectOptions(screen.getByTestId("transfer-to"), "loc-2");
    await user.type(screen.getByTestId("transfer-quantity"), "3");
    await user.click(screen.getByTestId("transfer-confirm"));
    await waitFor(() => expect(api.post).toHaveBeenCalled());
    const [url, body, opts] = api.post.mock.calls[0];
    expect(url).toBe("/inventory/transfers");
    expect(body).toMatchObject({ from_location_id: "loc-1", to_location_id: "loc-2", quantity: 3 });
    expect(opts.headers["Idempotency-Key"]).toBeTruthy();
  });
});
