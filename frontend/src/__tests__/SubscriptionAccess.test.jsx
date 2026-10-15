import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import SubscriptionAccessBanner from "@/components/billing/SubscriptionAccessBanner";
import { useAuth } from "@/auth/AuthContext";
import { ACCESS_CHANGED_EVENT } from "@/lib/api";
import { PRIMARY_NAV_AREAS, filterNavItemsByPermissions } from "@/lib/navigation";

jest.mock("@/auth/AuthContext", () => ({
  useAuth: jest.fn(),
}));

const shopOps = PRIMARY_NAV_AREAS.find((area) => area.moduleNav?.some((item) => item.key === "wrap-lab"));
const PERMS = ["webstore:read", "wrap_lab:read", "customer:read"];
const keys = (items) => items.map((item) => item.key);

describe("F1 commercial navigation", () => {
  test("Core modules, including Wrap Lab, are not hidden as add-ons", () => {
    expect(keys(filterNavItemsByPermissions(shopOps.moduleNav, PERMS, { role: "owner" }))).toContain("wrap-lab");
  });

  test("staff permissions still apply", () => {
    expect(keys(filterNavItemsByPermissions(shopOps.moduleNav, ["customer:read"], { role: "staff" }))).not.toContain("wrap-lab");
  });

  test("Webstores, the only paid add-on, stays unavailable to shops until released", () => {
    expect(keys(filterNavItemsByPermissions(shopOps.moduleNav, PERMS, { role: "owner" }))).not.toContain("webstores");
  });

  test("platform users can still reach unreleased Webstores setup", () => {
    const platform = { role: "staff", platform_admin: true, platform_role: "admin" };
    expect(keys(filterNavItemsByPermissions(shopOps.moduleNav, [...PERMS, "platform:admin"], platform))).toContain("webstores");
  });

  test("AI tools are included with the subscription, not hidden as add-ons", () => {
    const tools = PRIMARY_NAV_AREAS.find((area) => area.key === "tools-resources");
    const aiPerms = ["ai_tool:use", "ai_assistant:use", "ai_prompt:read"];
    const visible = keys(filterNavItemsByPermissions(tools.moduleNav, aiPerms, { role: "owner" }));
    expect(visible).toEqual(expect.arrayContaining(["overview", "assistant", "design-image", "prompts"]));
  });
});

describe("F1 subscription read-only banner", () => {
  const renderBanner = () => render(<MemoryRouter><SubscriptionAccessBanner /></MemoryRouter>);

  test("explains read-only mode and links to Billing", () => {
    useAuth.mockReturnValue({ commercialAccess: { state: "read_only", read_only: true } });
    renderBanner();
    expect(screen.getByTestId("subscription-read-only-banner")).toHaveTextContent(/read-only until you renew/i);
    expect(screen.getByTestId("subscription-read-only-billing-link")).toHaveAttribute("href", "/settings/subscriptions");
  });

  test("is hidden when the shop has access", () => {
    useAuth.mockReturnValue({ commercialAccess: { state: "full", read_only: false } });
    renderBanner();
    expect(screen.queryByTestId("subscription-read-only-banner")).toBeNull();
    expect(screen.queryByTestId("subscription-add-on-notice")).toBeNull();
  });

  test("a missing add-on shows a dismissible Billing action without navigating", () => {
    useAuth.mockReturnValue({ commercialAccess: { state: "full", read_only: false } });
    renderBanner();
    act(() => {
      window.dispatchEvent(new CustomEvent(ACCESS_CHANGED_EVENT, { detail: { code: "feature_not_entitled" } }));
    });
    expect(screen.getByTestId("subscription-add-on-notice")).toHaveTextContent(/not included in your current subscription/i);
    expect(screen.getByTestId("subscription-read-only-billing-link")).toHaveAttribute("href", "/settings/subscriptions");
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByTestId("subscription-add-on-notice")).toBeNull();
  });
});
