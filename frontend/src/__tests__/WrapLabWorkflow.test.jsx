import React from "react";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import axios from "axios";

import WrapLabPage from "@/pages/WrapLabPage";
import WrapLabDetailPage from "@/pages/WrapLabDetailPage";
import PublicApp from "@/public/PublicApp";
import api from "@/lib/api";
import { renderWithProviders } from "../test-utils";

jest.mock("@/auth/AuthContext", () => ({
  useAuth: () => ({
    hasPerm: (permission) => ["wrap_lab:read", "wrap_lab:write", "work_order:write"].includes(permission),
    user: { id: "owner-1", tenant_id: "tenant-1" },
  }),
}));

jest.mock("@/components/ai/AIContextualActions", () => ({ actions = [] }) => (
  <div data-testid="ai-actions">{actions.map((action) => <button key={action.label}>{action.label}</button>)}</div>
));

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn(), patch: jest.fn(), delete: jest.fn() },
  extractError: (error) => error?.response?.data?.detail || error?.message || "Request failed",
}));

jest.mock("axios", () => {
  const mockAxios = {
    get: jest.fn(),
    post: jest.fn(),
    create: jest.fn(),
    interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } },
  };
  mockAxios.create.mockReturnValue(mockAxios);
  return mockAxios;
});

beforeEach(() => {
  jest.clearAllMocks();
  api.get.mockImplementation((url) => {
    if (url === "/wrap-lab/projects") {
      return Promise.resolve({
        data: {
          items: [
            {
              id: "wrap-1",
              customer_id: "customer-1",
              order_item_id: "item-1",
              project_name: "Sprinter wrap",
              project_type: "full_wrap",
              status: "pre_install_ready",
            },
          ],
          total: 1,
        },
      });
    }
    if (url === "/wrap-lab/reports") {
      return Promise.resolve({ data: { project_count: 1, status_counts: { pre_install_ready: 1 } } });
    }
    if (url === "/wrap-lab/targets") {
      return Promise.resolve({
        data: {
          items: [
            { type: "customer", id: "customer-1", label: "Rusty Lemon", description: "rusty@example.com" },
            { type: "order_item", id: "item-1", label: "Full vehicle wrap", description: "O-91015 Sprinter", customer_id: "customer-1", order_id: "order-1" },
          ],
        },
      });
    }
    if (url === "/wrap-lab/projects/wrap-1") {
      return Promise.resolve({
        data: {
          project: {
            id: "wrap-1",
            customer_id: "customer-1",
            order_id: "order-1",
            order_item_id: "item-1",
            project_name: "Sprinter wrap",
            project_type: "full_wrap",
            status: "pre_install_ready",
            approval_revision: 2,
            coverage_summary: "Full wrap",
            specifications: { material: "cast wrap film", laminate: "gloss" },
          },
          vehicle: { id: "vehicle-1", year: "2024", make: "Mercedes", model: "Sprinter", requested_coverage: "Full wrap" },
          customer: { id: "customer-1", name: "Rusty Lemon" },
          order: { id: "order-1", number: 91015 },
          order_item: { id: "item-1", description: "Full vehicle wrap" },
          coverage_plans: [],
          inspections: [{ id: "inspection-1", inspection_type: "pre_install", version: 1, status: "ready_for_signature" }],
          design_scenes: [],
          panel_plans: [],
          packets: [],
          schedules: [],
          warranties: [],
          installation_records: [],
          approvals: [],
          decision_rooms: [],
          proofs: [],
          linked_assets: { files: [], documents: [] },
          readiness: {
            ready: false,
            blockers: [
              { code: "panel_plan_not_ready", label: "production panel plan is ready", required_action: "Create a ready production panel plan." },
              { code: "approval_evidence_stale", label: "Approved artwork or specifications changed after approval.", required_action: "Create/open current approval work for Wrap Project revision 2." },
            ],
            warnings: [],
          },
          timeline: [{ at: "2026-08-16T12:00:00Z", kind: "project", label: "Wrap Project created", entity_id: "wrap-1" }],
        },
      });
    }
    if (url === "/wrap-lab/inspections/inspection-1/review-links") {
      return Promise.resolve({
        data: {
          items: [
            { id: "token-1", audience_email: "rusty@example.com", parent_version: 1, computed_status: "viewed", expires_at: "2026-08-20T12:00:00Z" },
          ],
        },
      });
    }
    return Promise.resolve({ data: {} });
  });
  api.post.mockResolvedValue({ data: {} });
  api.patch.mockResolvedValue({ data: {} });
  api.delete.mockResolvedValue({ data: {} });
  axios.get.mockResolvedValue({
    data: {
      project: { id: "wrap-1", project_name: "Sprinter wrap", project_type: "full_wrap", coverage_summary: "Full wrap" },
      vehicle: { year: "2024", make: "Mercedes", model: "Sprinter", color: "white" },
      inspection: { id: "inspection-1", inspection_type: "pre_install", version: 1, status: "ready_for_signature", damage_items: [{ panel: "rear door", type: "scratch", severity: "minor", notes: "pre-existing" }] },
      token: { id: "token-1", status: "viewed", parent_version: 1, expires_at: "2026-08-20T12:00:00Z" },
    },
  });
  axios.post.mockResolvedValue({ data: { inspection: { status: "signed" } } });
});

test("Wrap Lab list exposes searchable source selection and project readiness context", async () => {
  const user = userEvent.setup();
  renderWithProviders(<WrapLabPage />, { route: "/wrap-lab" });

  expect(await screen.findByText("Sprinter wrap")).toBeInTheDocument();
  expect(screen.getByTestId("wrap-project-create-panel")).toBeInTheDocument();

  await user.type(screen.getByTestId("wrap-target-search"), "wrap");

  await waitFor(() => {
    expect(api.get).toHaveBeenCalledWith("/wrap-lab/targets", { params: { search: "wrap" } });
  });
});

test("Wrap Lab detail saves user-entered inspection and keeps AI actions explicit", async () => {
  const user = userEvent.setup();
  renderWithProviders(<WrapLabDetailPage />, { route: "/wrap-lab/wrap-1", path: "/wrap-lab/:id" });

  expect(await screen.findByText("Sprinter wrap")).toBeInTheDocument();
  expect(screen.getByText("AI Create Mockup")).toBeInTheDocument();
  expect(screen.getByText("AI Help Describe Damage")).toBeInTheDocument();
  expect(screen.getByText("AI Suggest Coverage Notes")).toBeInTheDocument();
  expect(screen.getByText("Approved artwork or specifications changed after approval.")).toBeInTheDocument();

  await user.click(screen.getByRole("tab", { name: "Inspection" }));
  await user.clear(screen.getByTestId("wrap-damage-panel"));
  await user.type(screen.getByTestId("wrap-damage-panel"), "rear door");
  await user.clear(screen.getByTestId("wrap-damage-notes"));
  await user.type(screen.getByTestId("wrap-damage-notes"), "Customer pointed out old adhesive marks.");
  await user.click(screen.getByRole("button", { name: "Save inspection" }));

  await waitFor(() => {
    expect(api.post).toHaveBeenCalledWith("/wrap-lab/projects/wrap-1/inspections", expect.objectContaining({
      inspection_type: "pre_install",
      damage_items: [expect.objectContaining({ panel: "rear door", notes: "Customer pointed out old adhesive marks." })],
    }));
  });
});

test("Wrap Lab detail creates customer-safe inspection links and shows token history", async () => {
  const user = userEvent.setup();
  renderWithProviders(<WrapLabDetailPage />, { route: "/wrap-lab/wrap-1", path: "/wrap-lab/:id" });

  expect(await screen.findByText("Sprinter wrap")).toBeInTheDocument();
  await user.click(screen.getByRole("tab", { name: "Inspection" }));

  expect(await screen.findByTestId("wrap-inspection-share-panel")).toBeInTheDocument();
  expect(screen.getByText("viewed")).toBeInTheDocument();
  await user.type(screen.getByTestId("wrap-inspection-share-email"), "rusty@example.com");
  api.post.mockResolvedValueOnce({ data: { token: "raw-token" } });
  await user.click(screen.getByTestId("wrap-inspection-share-create"));

  await waitFor(() => {
    expect(api.post).toHaveBeenCalledWith("/wrap-lab/inspections/inspection-1/review-links", expect.objectContaining({
      audience_email: "rusty@example.com",
      ttl_hours: 168,
    }));
  });
  expect(await screen.findByDisplayValue(/\/p\/wrap-inspections\/inspection-1/)).toBeInTheDocument();
});

test("Public Wrap inspection review renders pinned customer-safe details and signs", async () => {
  const user = userEvent.setup();
  renderWithProviders(<PublicApp />, { route: "/wrap-inspections/inspection-1?t=raw-token", path: "/*" });

  expect(await screen.findByTestId("public-wrap-inspection-page")).toHaveTextContent("Sprinter wrap");
  expect(screen.getByTestId("public-wrap-inspection-damage")).toHaveTextContent("rear door");
  await user.type(screen.getByTestId("public-wrap-inspection-name"), "Rusty Lemon");
  await user.type(screen.getByTestId("public-wrap-inspection-email"), "rusty@example.com");
  await user.type(screen.getByTestId("public-wrap-inspection-signature"), "Rusty Lemon");
  await user.click(screen.getByTestId("public-wrap-inspection-submit"));

  await waitFor(() => {
    expect(axios.post).toHaveBeenCalledWith(
      expect.stringContaining("/public/wrap-inspections/inspection-1/signature"),
      expect.objectContaining({ signer_name: "Rusty Lemon", signature_data: "Rusty Lemon" }),
      { params: { t: "raw-token" } },
    );
  });
});
