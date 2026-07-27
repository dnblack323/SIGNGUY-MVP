import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import AppShell from "@/components/app-shell/AppShell";
import { useAuth } from "@/auth/AuthContext";
import api from "@/lib/api";
import { useWorkspaceDirty } from "@/context/WorkspaceContext";

jest.mock("@/auth/AuthContext", () => ({
  useAuth: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
  },
}));

jest.mock("@/components/notifications/NotificationBell", () => function NotificationBellMock() {
  return <button type="button" data-testid="notification-bell">Notifications</button>;
});

jest.mock("@/components/assistant/AssistantLauncher", () => function AssistantLauncherMock() {
  return <div data-testid="assistant-launcher" />;
});

const FULL_PERMISSIONS = [
  "customer:read", "customer:write", "quote:read", "quote:write", "order:read", "order:write",
  "pricing:read", "pricing:calculate", "work_order:read", "invoice:read", "schedule:read",
  "document:read", "webstore:read", "wrap_lab:read", "finance:read", "employee:read",
  "equipment:read", "task:read", "ai_tool:use", "ai_assistant:use", "help:read",
];

const emptyDock = {
  open_workspaces: [],
  recent_workspaces: [],
  limits: { max_open: 8, max_recent: 20 },
};

const orderWorkspace = {
  id: "workspace-order-1",
  workspace_type: "order",
  workspace_key: "order:order-1",
  record_id: "order-1",
  label: "O-000127 - Fayette EMS",
  pathname: "/orders/order-1",
  query_params: { tab: "items" },
  view_state: { selected_tab: "items" },
  active: true,
  pinned: false,
  position: 0,
  scroll_position: 240,
  dirty: false,
  status: "open",
};

const quoteWorkspace = {
  ...orderWorkspace,
  id: "workspace-quote-1",
  workspace_type: "quote",
  workspace_key: "quote:quote-1",
  record_id: "quote-1",
  label: "Q-000219 - Party Squad",
  pathname: "/quotes/quote-1",
  query_params: { tab: "summary" },
  active: false,
  position: 1,
};

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="current-location">{location.pathname}{location.search}</div>;
}

function Page({ name, dirty = false }) {
  useWorkspaceDirty(dirty);
  return <div data-testid={`${name}-page`}>{name}</div>;
}

function renderShell(initialPath = "/orders/order-1?tab=items") {
  useAuth.mockReturnValue({
    devBypass: false,
    hasPerm: (permission) => FULL_PERMISSIONS.includes(permission),
    logout: jest.fn(),
    permissions: FULL_PERMISSIONS,
    tenant: { id: "tenant-1", name: "Donnell Black's Shop", slug: "dev-shop" },
    user: { id: "user-1", email: "owner@example.com", role: "owner" },
  });

  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<><LocationProbe /><Page name="overview" /></>} />
          <Route path="/orders" element={<><LocationProbe /><Page name="orders-list" /></>} />
          <Route path="/orders/:id" element={<><LocationProbe /><Page name="order-detail" /></>} />
          <Route path="/quotes/:id" element={<><LocationProbe /><Page name="quote-detail" /></>} />
          <Route path="/pricing-calculator" element={<><LocationProbe /><Page name="pricing-calculator" /></>} />
          <Route path="/customers/:id" element={<><LocationProbe /><Page name="customer-detail" dirty /></>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  window.scrollTo = jest.fn();
  api.get.mockResolvedValue({ data: emptyDock });
  api.post.mockResolvedValue({ data: emptyDock });
  api.patch.mockResolvedValue({ data: emptyDock });
  api.delete.mockResolvedValue({ data: emptyDock });
});

test("supported record routes create or activate dock tabs while lists do not", async () => {
  api.post.mockResolvedValueOnce({ data: { ...emptyDock, open_workspaces: [orderWorkspace] } });
  renderShell("/orders/order-1?tab=items");

  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/workspaces/open", expect.objectContaining({
    workspace_type: "order",
    record_id: "order-1",
    pathname: "/orders/order-1",
    query_params: { tab: "items" },
  })));
  expect(await screen.findByText("O-000127 - Fayette EMS")).toBeInTheDocument();

  jest.clearAllMocks();
  api.get.mockResolvedValue({ data: emptyDock });
  renderShell("/orders");
  await waitFor(() => expect(api.get).toHaveBeenCalledWith("/workspaces"));
  expect(api.post).not.toHaveBeenCalledWith("/workspaces/open", expect.anything());
});

test("switching dock tabs restores the stored route and query parameters", async () => {
  api.get.mockResolvedValue({ data: { ...emptyDock, open_workspaces: [orderWorkspace, quoteWorkspace] } });
  api.post.mockImplementation((url) => {
    if (url === "/workspaces/workspace-quote-1/activate") {
      return Promise.resolve({ data: { ...emptyDock, open_workspaces: [{ ...orderWorkspace, active: false }, { ...quoteWorkspace, active: true }] } });
    }
    return Promise.resolve({ data: { ...emptyDock, open_workspaces: [orderWorkspace, quoteWorkspace] } });
  });
  const user = userEvent.setup();
  renderShell("/orders/order-1?tab=items");

  await user.click(await screen.findByText("Q-000219 - Party Squad"));

  await waitFor(() => expect(screen.getByTestId("current-location")).toHaveTextContent("/quotes/quote-1?tab=summary"));
});

test("pinning, reordering, closing, and recent reopen use the backend dock APIs", async () => {
  const dockState = { ...emptyDock, open_workspaces: [orderWorkspace, quoteWorkspace], recent_workspaces: [{ ...quoteWorkspace, id: "recent-quote", status: "recent" }] };
  api.get.mockResolvedValue({ data: dockState });
  api.post.mockResolvedValue({ data: dockState });
  const user = userEvent.setup();
  renderShell("/orders/order-1");

  await screen.findByText("O-000127 - Fayette EMS");
  await user.click(screen.getAllByLabelText("Pin workspace")[0]);
  expect(api.post).toHaveBeenCalledWith("/workspaces/workspace-order-1/pin");

  await user.click(screen.getAllByLabelText("Move workspace right")[0]);
  expect(api.post).toHaveBeenCalledWith("/workspaces/reorder", { workspace_ids: ["workspace-quote-1", "workspace-order-1"] });

  await user.click(screen.getAllByLabelText("Close workspace")[0]);
  expect(api.post).toHaveBeenCalledWith("/workspaces/workspace-order-1/close");

  await user.click(screen.getByText("Recent Work"));
  const recent = screen.getByTestId("workspace-recent-list");
  await user.click(within(recent).getByLabelText("Reopen recent workspace"));
  expect(api.post).toHaveBeenCalledWith("/workspaces/recent/recent-quote/reopen");
});

test("dirty workspaces warn before close and can be cancelled", async () => {
  const dirtyCustomer = {
    ...orderWorkspace,
    id: "workspace-customer-1",
    workspace_type: "customer",
    workspace_key: "customer:customer-1",
    record_id: "customer-1",
    label: "Customer - Summit Motors",
    pathname: "/customers/customer-1",
    query_params: {},
    dirty: true,
  };
  api.get.mockResolvedValue({ data: { ...emptyDock, open_workspaces: [dirtyCustomer] } });
  api.post.mockResolvedValue({ data: { ...emptyDock, open_workspaces: [dirtyCustomer] } });
  const user = userEvent.setup();
  renderShell("/customers/customer-1");

  await user.click(await screen.findByLabelText("Close workspace"));
  expect(await screen.findByTestId("workspace-dirty-dialog")).toBeInTheDocument();

  await user.click(screen.getByText("Cancel"));
  expect(api.post).not.toHaveBeenCalledWith("/workspaces/workspace-customer-1/close");
});

test("opening a ninth workspace displays the limit workflow", async () => {
  api.post.mockRejectedValueOnce({
    response: {
      status: 409,
      data: { detail: { message: "Workspace limit reached", limit: 8, open_workspaces: [orderWorkspace] } },
    },
  });
  const user = userEvent.setup();
  renderShell("/pricing-calculator");

  expect(await screen.findByTestId("workspace-limit-dialog")).toBeInTheDocument();
  expect(screen.getByText(/Close an unpinned workspace/)).toBeInTheDocument();
  await user.click(screen.getByText("Cancel"));
});

test("mobile Open Work drawer exposes open and recent work", async () => {
  const dockState = { ...emptyDock, open_workspaces: [orderWorkspace], recent_workspaces: [quoteWorkspace] };
  api.get.mockResolvedValue({ data: dockState });
  api.post.mockResolvedValue({ data: dockState });
  const user = userEvent.setup();
  renderShell("/orders/order-1");

  const mobileTrigger = await screen.findByTestId("mobile-open-work-trigger");
  expect(mobileTrigger).toHaveClass("left-4");
  expect(mobileTrigger).not.toHaveClass("right-4");

  await user.click(mobileTrigger);

  expect(screen.getByTestId("mobile-open-work-drawer")).toBeInTheDocument();
  expect(await screen.findAllByText("O-000127 - Fayette EMS")).toHaveLength(2);
  expect(screen.getAllByText("Q-000219 - Party Squad").length).toBeGreaterThan(0);
});

test("workspace API failures show a retry state without crashing the shell", async () => {
  api.get.mockRejectedValueOnce({ response: { data: { detail: "Backend unavailable" } } });
  api.post.mockRejectedValue({ response: { data: { detail: "Backend unavailable" } } });
  renderShell("/orders/order-1");

  expect(await screen.findByTestId("workspace-api-error")).toHaveTextContent("Backend unavailable");
  expect(screen.getByTestId("order-detail-page")).toBeInTheDocument();
});
