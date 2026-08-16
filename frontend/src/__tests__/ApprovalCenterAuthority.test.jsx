import React from "react";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";

import ApprovalCenterPage from "@/pages/ApprovalCenterPage";
import api from "@/lib/api";
import { renderWithProviders } from "../test-utils";

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn(), patch: jest.fn(), delete: jest.fn() },
  extractError: (error) => error?.response?.data?.detail || error?.message || "Request failed",
}));

jest.mock("@/pages/DecisionRoomsPage", () => () => <div data-testid="decision-rooms-page">Decision Rooms</div>);

beforeEach(() => {
  jest.clearAllMocks();
  api.get.mockImplementation((url) => {
    if (url === "/approval-center/queue") {
      return Promise.resolve({
        data: {
          items: [
            {
              id: "approval:approval-1",
              queue_type: "approval_record",
              record_type: "approval",
              record_id: "approval-1",
              activity_type: "approve",
              title: "Window decal quote",
              target_type: "quote_revision",
              target_id: "quote-1",
              quote_id: "quote-1",
              customer_name: "Rusty Lemon Boutique",
              status: "current",
              submitted_at: "2026-08-16T10:00:00+00:00",
              source_url: "/quotes/quote-1",
            },
            {
              id: "decision_room_activity:customer_decision:decision-1",
              queue_type: "decision_room_activity",
              record_type: "customer_decision",
              record_id: "decision-1",
              decision_room_id: "room-1",
              activity_type: "option_selected",
              title: "Trailer wrap approval",
              target_type: "decision_room",
              target_id: "room-1",
              customer_name: "Party Squad Rentals",
              status: "pending_review",
              submitted_at: "2026-08-16T10:15:00+00:00",
              source_url: "/decision-rooms/room-1",
            },
            {
              id: "decision_room_activity:question:question-1",
              queue_type: "decision_room_activity",
              record_type: "question",
              record_id: "question-1",
              decision_room_id: "room-1",
              activity_type: "question",
              title: "Trailer wrap approval",
              target_type: "decision_room",
              target_id: "room-1",
              customer_name: "Party Squad Rentals",
              status: "open",
              unresolved: true,
              submitted_at: "2026-08-16T10:20:00+00:00",
              source_url: "/decision-rooms/room-1",
              source_summary: "Decision Room question Does this include install?",
            },
            {
              id: "proof:proof-1",
              queue_type: "proof",
              record_type: "proof",
              record_id: "proof-1",
              activity_type: "proof",
              title: "Window proof",
              target_type: "proof_version",
              target_id: "proof-1",
              customer_name: "Rusty Lemon Boutique",
              status: "sent",
              submitted_at: "2026-08-16T10:25:00+00:00",
              source_url: "/quotes/quote-1",
              source_summary: "Proof quote quote-1",
            },
          ],
          total: 4,
        },
      });
    }
    if (url === "/approval-center/targets") {
      return Promise.resolve({
        data: {
          items: [
            {
              id: "quote-1",
              target_type: "quote",
              label: "Q-101 Window decals",
              subtitle: "Rusty Lemon Boutique",
              customer_id: "customer-1",
            },
            {
              id: "quote-line-1",
              target_type: "quote_line_item",
              label: "Front window decal",
              subtitle: "Q-101 Window decals Rusty Lemon Boutique",
              customer_id: "customer-1",
              quote_id: "quote-1",
            },
          ],
        },
      });
    }
    return Promise.resolve({ data: {} });
  });
  api.post.mockResolvedValue({ data: { id: "room-2" } });
});

test("Approval Center shows unified approval authority queue and applies Decision Room activity", async () => {
  const user = userEvent.setup();
  jest.spyOn(window, "prompt").mockReturnValue("Yes, installation is included.");
  renderWithProviders(<ApprovalCenterPage />, { route: "/approval-center" });

  expect(await screen.findByText("Window decal quote")).toBeInTheDocument();
  expect(screen.getAllByText("Trailer wrap approval").length).toBeGreaterThanOrEqual(1);
  expect(screen.getByText("Window proof")).toBeInTheDocument();

  await user.click(screen.getByTestId("approval-queue-apply-decision-1"));
  await user.click(screen.getByTestId("approval-queue-respond-question-1"));
  await user.click(screen.getByTestId("approval-queue-proof-approve-proof-1"));

  await waitFor(() => {
    expect(api.post).toHaveBeenCalledWith("/decision-rooms/room-1/decisions/decision-1/apply", {});
    expect(api.post).toHaveBeenCalledWith("/decision-rooms/room-1/questions/question-1/respond", { staff_response: "Yes, installation is included." });
    expect(api.post).toHaveBeenCalledWith("/proofs/proof-1/transition", { target: "approved", reason: null });
  });
  window.prompt.mockRestore();
});

test("Approval Center creates Decision Room work from a prefilled commercial target", async () => {
  const user = userEvent.setup();
  renderWithProviders(<ApprovalCenterPage />, {
    route: "/approval-center?new=1&target_type=quote&target_id=quote-1&customer_id=customer-1&title=Q-101%20Window%20decals",
  });

  expect(await screen.findByTestId("approval-work-dialog")).toBeInTheDocument();
  expect(screen.getByText("Selected Quote")).toBeInTheDocument();
  expect(screen.getByDisplayValue("Q-101 Window decals")).toBeInTheDocument();

  await user.click(screen.getByTestId("approval-work-create"));

  await waitFor(() => {
    expect(api.post).toHaveBeenCalledWith("/approval-center/work", expect.objectContaining({
      target_type: "quote",
      target_id: "quote-1",
      title: "Q-101 Window decals",
    }));
  });
});

test("Approval Center creates Decision Room work for searchable quote line items", async () => {
  const user = userEvent.setup();
  renderWithProviders(<ApprovalCenterPage />, {
    route: "/approval-center?new=1&target_type=quote_line_item&target_id=quote-line-1&customer_id=customer-1&title=Front%20window%20decal",
  });

  expect(await screen.findByTestId("approval-work-dialog")).toBeInTheDocument();
  expect(screen.getByText("Selected Quote line item")).toBeInTheDocument();
  await user.click(screen.getByTestId("approval-work-create"));

  await waitFor(() => {
    expect(api.post).toHaveBeenCalledWith("/approval-center/work", expect.objectContaining({
      target_type: "quote_line_item",
      target_id: "quote-line-1",
    }));
  });
});
