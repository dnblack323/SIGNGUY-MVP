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
    const visible = keys(filterNavItemsByPermissions(shopOps.moduleNav, PERMS, { role: "owner" }, ["wrap_lab", "webstores"]));
    expect(visible).toEqual(expect.arrayContaining(["wrap-lab", "webstores"]));
  });

  test("does not filter when entitlements are unknown", () => {
    const visible = keys(filterNavItemsByPermissions(shopOps.moduleNav, PERMS, { role: "owner" }));
    expect(visible).toEqual(expect.arrayContaining(["wrap-lab", "webstores"]));
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
