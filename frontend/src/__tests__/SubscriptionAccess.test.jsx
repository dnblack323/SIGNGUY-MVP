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

describe("F1 entitlement-aware navigation", () => {
  test("hides paid add-on modules the shop does not hold", () => {
    const visible = keys(filterNavItemsByPermissions(shopOps.moduleNav, PERMS, { role: "owner" }, []));
    expect(visible).not.toContain("wrap-lab");
    expect(visible).not.toContain("webstores");
  });

  test("shows add-on modules the shop holds", () => {
    const visible = keys(filterNavItemsByPermissions(shopOps.moduleNav, PERMS, { role: "owner" }, ["wrap_lab"]));
    expect(visible).toContain("wrap-lab");
  });

  test("does not filter by entitlement when entitlements are unknown", () => {
    const visible = keys(filterNavItemsByPermissions(shopOps.moduleNav, PERMS, { role: "owner" }));
    expect(visible).toContain("wrap-lab");
  });

  test("Webstores stays unavailable to shops until released, purchased or not", () => {
    for (const entitlements of [[], ["webstores"], null]) {
      expect(keys(filterNavItemsByPermissions(shopOps.moduleNav, PERMS, { role: "owner" }, entitlements))).not.toContain("webstores");
    }
  });

  test("Webstores setup is not gated on the publishing entitlement", () => {
    const platform = { role: "staff", platform_admin: true, platform_role: "admin" };
    const visible = keys(filterNavItemsByPermissions(shopOps.moduleNav, [...PERMS, "platform:admin"], platform, []));
    expect(visible).toContain("webstores");
  });

  test("AI tools are included with the subscription, not hidden as add-ons", () => {
    const tools = PRIMARY_NAV_AREAS.find((area) => area.key === "tools-resources");
    const aiPerms = ["ai_tool:use", "ai_assistant:use", "ai_prompt:read"];
    const visible = keys(filterNavItemsByPermissions(tools.moduleNav, aiPerms, { role: "owner" }, []));
    expect(visible).toEqual(expect.arrayContaining(["overview", "assistant", "design-image", "prompts"]));
  });
});

describe("F1 subscription read-only banner", () => {
  const renderBanner = () => render(<MemoryRouter><SubscriptionAccessBanner /></MemoryRouter>);

  test("explains read-only mode and links to Billing", () => {
    useAuth.mockReturnValue({ commercialAccess: { state: "read_only", read_only: true, entitlements: [] } });
    renderBanner();
    expect(screen.getByTestId("subscription-read-only-banner")).toHaveTextContent(/read-only until you renew/i);
    expect(screen.getByTestId("subscription-read-only-billing-link")).toHaveAttribute("href", "/settings/subscriptions");
  });

  test("is hidden when the shop has access", () => {
    useAuth.mockReturnValue({ commercialAccess: { state: "full", read_only: false, entitlements: [] } });
    renderBanner();
    expect(screen.queryByTestId("subscription-read-only-banner")).toBeNull();
    expect(screen.queryByTestId("subscription-add-on-notice")).toBeNull();
  });

  test("a missing add-on shows a dismissible Billing action without navigating", () => {
    useAuth.mockReturnValue({ commercialAccess: { state: "full", read_only: false, entitlements: [] } });
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
