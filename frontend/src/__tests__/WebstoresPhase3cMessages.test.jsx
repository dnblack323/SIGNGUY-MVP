import "@testing-library/jest-dom";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";
import WebstoreMessages from "@/components/webstores/WebstoreMessages";

jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));

const THREAD = {
  items: [
    { id: "m1", from: "owner", sender_name: "Store owner", body: "Can we add a hoodie?", created_at: "2026-10-20T12:00:00Z" },
    { id: "m2", from: "shop", sender_name: "Print Shop", body: "Yes, adding it.", created_at: "2026-10-20T12:05:00Z" },
  ],
};

test("the shop sees the owner's messages and replies in the same thread", async () => {
  const load = jest.fn().mockResolvedValue(THREAD);
  const send = jest.fn().mockResolvedValue({ items: [...THREAD.items, { id: "m3", from: "shop", sender_name: "Sam", body: "Draft updated.", created_at: "2026-10-20T12:10:00Z" }] });
  const user = userEvent.setup();
  renderWithProviders(<WebstoreMessages webstoreId="ws-1" viewer="shop" load={load} send={send} extractError={(e) => e.message} />);

  expect(await screen.findByTestId("webstore-message-m1")).toHaveTextContent("Store owner");
  expect(screen.getByTestId("webstore-message-m2")).toHaveTextContent("You");
  expect(screen.getByTestId("webstore-message-send")).toBeDisabled();
  await user.type(screen.getByTestId("webstore-message-input"), "  Draft updated.  ");
  await user.click(screen.getByTestId("webstore-message-send"));
  await waitFor(() => expect(send).toHaveBeenCalledWith("ws-1", "Draft updated."));
  expect(await screen.findByTestId("webstore-message-m3")).toHaveTextContent("Draft updated.");
  expect(screen.getByTestId("webstore-message-input")).toHaveValue("");
});

test("the owner sees the shop by name and their own messages as theirs", async () => {
  renderWithProviders(<WebstoreMessages webstoreId="ws-1" viewer="owner" load={jest.fn().mockResolvedValue(THREAD)} send={jest.fn()} extractError={(e) => e.message} />);
  expect(await screen.findByTestId("webstore-message-m1")).toHaveTextContent("You");
  expect(screen.getByTestId("webstore-message-m2")).toHaveTextContent("Print Shop");
});
