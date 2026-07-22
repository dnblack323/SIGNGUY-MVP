import React from "react";
import { useLocation } from "react-router-dom";
import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Plus, Users } from "lucide-react";
import { renderWithProviders } from "../test-utils";
import CommandRibbon from "@/components/command-ribbon/CommandRibbon";

let mockPermissions = [];

jest.mock("@/auth/AuthContext", () => ({
  __esModule: true,
  useAuth: () => ({
    hasPerm: (perm) => mockPermissions.includes(perm),
    user: { id: "u1", tenant_id: "t1", role: "owner" },
  }),
}));

function LocationReadout() {
  const location = useLocation();
  return <div data-testid="location-readout">{location.pathname}</div>;
}

beforeEach(() => {
  mockPermissions = ["order:write", "customer:read", "customer:write"];
});

test("renders grouped icon commands and executes page actions with keyboard", async () => {
  const user = userEvent.setup();
  const onCreate = jest.fn();
  renderWithProviders(
    <CommandRibbon
      groups={[
        { id: "create", label: "Create", commands: [{ id: "new-order", label: "New Order", icon: Plus, permission: "order:write", onSelect: onCreate }] },
      ]}
    />,
  );

  expect(screen.getByTestId("command-ribbon")).toBeInTheDocument();
  expect(screen.getByTestId("ribbon-group-create")).toHaveTextContent("Create");
  const button = screen.getByRole("button", { name: "New Order" });
  act(() => button.focus());
  await user.keyboard("{Enter}");
  expect(onCreate).toHaveBeenCalledTimes(1);
});

test("executes navigation commands and marks active commands", async () => {
  const user = userEvent.setup();
  renderWithProviders(
    <>
      <CommandRibbon
        groups={[
          { id: "go", label: "Go", commands: [{ id: "customers", label: "Customers", icon: Users, permission: "customer:read", to: "/customers" }] },
        ]}
      />
      <LocationReadout />
    </>,
    { route: "/orders" },
  );

  await user.click(screen.getByRole("button", { name: "Customers" }));
  expect(screen.getByTestId("location-readout")).toHaveTextContent("/customers");
  expect(screen.getByRole("button", { name: "Customers" })).toHaveAttribute("data-active", "true");
});

test("hides unauthorized commands and disables entitlement-blocked commands", async () => {
  const user = userEvent.setup();
  const blocked = jest.fn();
  mockPermissions = ["order:write"];
  renderWithProviders(
    <CommandRibbon
      entitlements={{ wrap_lab: false }}
      groups={[
        {
          id: "mixed",
          label: "Mixed",
          commands: [
            { id: "visible", label: "Visible", icon: Plus, permission: "order:write", entitlement: "wrap_lab", onSelect: blocked },
            { id: "hidden", label: "Hidden", icon: Users, permission: "customer:read", onSelect: jest.fn() },
          ],
        },
      ]}
    />,
  );

  expect(screen.queryByRole("button", { name: "Hidden" })).not.toBeInTheDocument();
  const visible = screen.getByRole("button", { name: "Visible" });
  expect(visible).toHaveAttribute("aria-disabled", "true");
  await user.click(visible);
  expect(blocked).not.toHaveBeenCalled();
});

test("renders dropdown children and deterministic overflow commands", async () => {
  const user = userEvent.setup();
  const onDropdown = jest.fn();
  const onOverflow = jest.fn();
  renderWithProviders(
    <CommandRibbon
      maxPrimaryCommands={1}
      groups={[
        {
          id: "actions",
          label: "Actions",
          commands: [
            { id: "source", label: "Source", icon: Plus, children: [{ id: "manual", label: "Manual", onSelect: onDropdown }] },
            { id: "overflow", label: "Overflowed", icon: Users, onSelect: onOverflow },
          ],
        },
      ]}
    />,
  );

  await user.click(screen.getByRole("button", { name: "Source" }));
  await user.click(screen.getByTestId("ribbon-menu-command-manual"));
  expect(onDropdown).toHaveBeenCalledTimes(1);

  await user.click(screen.getByRole("button", { name: "More commands" }));
  await user.click(screen.getByTestId("ribbon-menu-command-overflow"));
  expect(onOverflow).toHaveBeenCalledTimes(1);
});

test("keeps dropdown children actionable when the parent command overflows", async () => {
  const user = userEvent.setup();
  const onManual = jest.fn();
  renderWithProviders(
    <CommandRibbon
      maxPrimaryCommands={0}
      groups={[
        {
          id: "filters",
          label: "Filters",
          commands: [
            {
              id: "source",
              label: "Source",
              icon: Plus,
              children: [{ id: "manual", label: "Manual", onSelect: onManual }],
            },
          ],
        },
      ]}
    />,
  );

  expect(screen.queryByRole("button", { name: "Source" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "More commands" }));
  await user.click(screen.getByTestId("ribbon-menu-command-manual"));
  expect(onManual).toHaveBeenCalledTimes(1);
});
