import React from "react";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../test-utils";
import api from "@/lib/api";
import ShopSchedulePage from "@/pages/ShopSchedulePage";

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
  },
  extractError: () => "Request failed",
}));

beforeEach(() => {
  jest.clearAllMocks();
  api.get.mockImplementation((url) => {
    if (url === "/employees") {
      return Promise.resolve({ data: { items: [{ id: "emp-1", name: "Ada Installer" }] } });
    }
    if (url === "/calendar/feed") {
      return Promise.resolve({
        data: {
          items: [
            {
              id: "calendar_event:event-1",
              source_type: "calendar_event",
              source_id: "event-1",
              event_type: "installation",
              title: "Install lobby sign",
              display_title: "Install lobby sign",
              start_at: "2026-07-23T14:00:00.000Z",
              end_at: "2026-07-23T16:00:00.000Z",
              status: "scheduled",
              allowed_actions: ["cancel"],
            },
          ],
          total: 1,
        },
      });
    }
    return Promise.resolve({ data: { items: [] } });
  });
});

test("Shop Schedule requests the operational shop surface instead of employee shift overlays", async () => {
  renderWithProviders(<ShopSchedulePage />);

  expect(await screen.findByText("Install lobby sign")).toBeInTheDocument();
  expect(screen.getByText("Operational appointments, order deadlines, task due dates, and production milestones.")).toBeInTheDocument();
  expect(screen.queryByTestId("calendar-employee-filter")).not.toBeInTheDocument();

  await waitFor(() => {
    expect(api.get).toHaveBeenCalledWith(
      "/calendar/feed",
      expect.objectContaining({
        params: expect.objectContaining({ surface: "shop" }),
      }),
    );
  });
});
