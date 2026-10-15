import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import SubscriptionAccessBanner from "@/components/billing/SubscriptionAccessBanner";
import { useAuth } from "@/auth/AuthContext";
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

  test("AI tools are hidden unless the shop holds the AI add-ons", () => {
    const tools = PRIMARY_NAV_AREAS.find((area) => area.key === "tools-resources");
    const aiPerms = ["ai_tool:use", "ai_assistant:use", "ai_prompt:read"];
    const without = keys(filterNavItemsByPermissions(tools.moduleNav, aiPerms, { role: "owner" }, []));
    expect(without).not.toContain("overview");
    expect(without).not.toContain("assistant");
    expect(without).not.toContain("design-image");
    expect(without).toContain("prompts");
    const withAddOns = keys(filterNavItemsByPermissions(tools.moduleNav, aiPerms, { role: "owner" }, ["ai_studio", "business_assistant"]));
    expect(withAddOns).toEqual(expect.arrayContaining(["overview", "assistant", "design-image"]));
  });

  test("staff permissions still apply to entitled modules", () => {
    const visible = keys(filterNavItemsByPermissions(shopOps.moduleNav, ["customer:read"], { role: "staff" }, ["wrap_lab"]));
    expect(visible).not.toContain("wrap-lab");
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
  });
});
