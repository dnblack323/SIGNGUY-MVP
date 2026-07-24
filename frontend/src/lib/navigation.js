/**
 * UX1 corrective navigation contract.
 *
 * Primary sidebar = major application area.
 * Category top navigation = module inside the active area.
 * Contextual ribbon = page action surface.
 *
 * This supersedes the earlier flyout-only EC1 navigation contract for UX1.
 */
import {
  BriefcaseBusiness,
  CircleHelp,
  FileText,
  Home,
  Layers,
  MessageSquare,
  Package,
  PanelTop,
  Receipt,
  Settings,
  ShoppingBag,
  Sparkles,
  Users,
} from "lucide-react";

export const PRIMARY_NAV_AREAS = [
  {
    key: "home",
    label: "Home",
    icon: Home,
    accent: "text-sky-300",
    to: "/",
    testId: "primary-nav-home",
    home: true,
    moduleNav: [],
  },
  {
    key: "shop-operations",
    label: "Shop Operations",
    icon: ShoppingBag,
    accent: "text-cyan-300",
    testId: "primary-nav-shop-operations",
    moduleNav: [
      { key: "orders", label: "Orders", to: "/orders", perm: "order:read", testId: "module-nav-orders" },
      { key: "customers", label: "Customers", to: "/customers", perm: "customer:read", testId: "module-nav-customers" },
      { key: "production", label: "Production", to: "/work-orders", perm: "work_order:read", testId: "module-nav-production", match: ["/work-orders", "/work-orders/board"] },
      { key: "shop-schedule", label: "Scheduling", to: "/shop-schedule", perm: "schedule:read", testId: "module-nav-shop-schedule" },
      { key: "webstores", label: "Webstores", to: "/webstores", perm: "webstore:read", testId: "module-nav-webstores" },
      { key: "documents", label: "Documents", to: "/documents", perm: "document:read", testId: "module-nav-documents" },
    ],
  },
  {
    key: "business-management",
    label: "Business Management",
    icon: BriefcaseBusiness,
    accent: "text-emerald-300",
    testId: "primary-nav-business-management",
    moduleNav: [
      { key: "finance", label: "Finance", to: "/finance", perm: "finance:read", testId: "module-nav-finance" },
      { key: "sales", label: "Sales", to: "/finance", perm: "finance:read", testId: "module-nav-sales" },
      { key: "taxes", label: "Taxes", to: "/tax", perm: "tax_report:read", testId: "module-nav-taxes" },
      { key: "inventory", label: "Inventory", to: "/inventory", perm: "inventory:read", testId: "module-nav-inventory", match: ["/inventory", "/materials", "/supply-center", "/purchase-orders", "/vendors"] },
      { key: "payroll", label: "Payroll", to: "/team/payroll", perm: "payroll:read", testId: "module-nav-payroll" },
      { key: "reports", label: "Reports", to: "/reports", perm: "report:read", testId: "module-nav-reports" },
    ],
  },
  {
    key: "team",
    label: "Productivity & Collaboration",
    shortLabel: "Productivity",
    icon: Layers,
    accent: "text-violet-300",
    testId: "primary-nav-productivity-collaboration",
    moduleNav: [
      { key: "tasks", label: "Tasks", to: "/team/tasks", perm: "task:read", testId: "module-nav-tasks" },
      { key: "team-schedule", label: "Team Schedule", to: "/team/schedule", perm: "schedule:read", testId: "module-nav-team-schedule" },
      { key: "messages", label: "Messages", to: "/team/messages", perm: "message:read", testId: "module-nav-messages" },
      { key: "announcements", label: "Announcements", to: "/team/announcements", perm: null, testId: "module-nav-announcements" },
      { key: "employees", label: "Employees", to: "/team/employees", perm: "employee:read", testId: "module-nav-employees", match: ["/team/employees"] },
      { key: "workflows", label: "Workflows", to: "/settings/production-workflows", perm: "production_workflow:read", testId: "module-nav-workflows" },
    ],
  },
  {
    key: "ai-platform-community",
    label: "AI / Platform / Community",
    shortLabel: "AI & Community",
    icon: Sparkles,
    accent: "text-amber-300",
    testId: "primary-nav-ai-platform-community",
    moduleNav: [
      { key: "ai-assistant", label: "AI Assistant", to: "/studio/assistant", perm: "ai_assistant:use", testId: "module-nav-ai-assistant" },
      { key: "ai-tools", label: "AI Tools", to: "/studio", perm: "ai_tool:use", testId: "module-nav-ai-tools", match: ["/studio", "/studio/design-image", "/studio/marketing-brand", "/studio/writing-documents", "/studio/pricing-profitability"] },
      { key: "onboarding", label: "Onboarding", to: "/help/onboarding", perm: "onboarding:read", testId: "module-nav-onboarding", match: ["/help/onboarding", "/onboarding"] },
      { key: "documentation", label: "Documentation", to: "/help/docs", perm: "help:read", testId: "module-nav-documentation" },
      { key: "community", label: "Community", to: "/help/community", perm: "community:read", testId: "module-nav-community" },
      { key: "bug-reports", label: "Bug Reports", to: "/help/bugs", perm: "community:read", testId: "module-nav-bug-reports" },
      { key: "feature-requests", label: "Feature Requests", to: "/help/feature-requests", perm: "community:read", testId: "module-nav-feature-requests" },
      { key: "settings", label: "Settings", to: "/settings", perm: "settings:read", testId: "module-nav-settings", icon: Settings, match: ["/settings", "/pricing-foundation"] },
    ],
  },
];

export const MODULE_NAV_UNCERTAIN_DESTINATIONS = [
  {
    label: "Quotes",
    route: "/quotes",
    recommendation: "Keep as an Orders-adjacent workflow until owner confirms category-level placement.",
  },
  {
    label: "Work Orders",
    route: "/work-orders",
    recommendation: "Expose through the Production module label rather than adding separate Work Orders top navigation.",
  },
  {
    label: "Kanban",
    route: "/team/tasks",
    recommendation: "Treat as a Tasks view until a distinct route or tab exists.",
  },
  {
    label: "Notes",
    route: "/team/messages",
    recommendation: "Treat as part of Messages until a distinct Notes route exists.",
  },
  {
    label: "Internal Workflows",
    route: "/settings/production-workflows",
    recommendation: "Use existing Production Workflows route; owner may rename later.",
  },
];

export const CATEGORY_ICON_HINTS = {
  shop: Package,
  document: FileText,
  finance: Receipt,
  collaboration: MessageSquare,
  support: CircleHelp,
  platform: PanelTop,
};

export function filterNavItemsByPermissions(items, permissions, user = null) {
  if (!Array.isArray(items)) return [];
  const set = new Set(permissions || []);
  const platformUser = !!(
    user?.platform_admin
    || ["admin", "owner", "PLATFORM_ADMIN", "PLATFORM_CREATOR"].includes(user?.platform_role)
    || set.has("platform:admin")
    || set.has("platform:creator")
  );
  return items.filter((entry) => {
    if (entry.platformOnly && !platformUser) return false;
    return !entry.perm || set.has(entry.perm);
  });
}

export function itemMatchesPath(item, pathname) {
  if (!item || !pathname) return false;
  const targets = item.match || [item.to];
  return targets.some((target) => (
    target === "/"
      ? pathname === "/"
      : pathname === target || pathname.startsWith(`${target}/`)
  ));
}

export function findAreaForPath(pathname) {
  if (pathname === "/") return PRIMARY_NAV_AREAS[0];
  return PRIMARY_NAV_AREAS.find((area) => (
    area.moduleNav?.some((item) => itemMatchesPath(item, pathname))
  )) || PRIMARY_NAV_AREAS[1];
}

export function firstAvailableModule(area, permissions, user = null) {
  return filterNavItemsByPermissions(area?.moduleNav || [], permissions, user)[0] || null;
}

export function activeModuleForPath(area, pathname, permissions, user = null) {
  const visible = filterNavItemsByPermissions(area?.moduleNav || [], permissions, user);
  return visible.find((item) => itemMatchesPath(item, pathname)) || null;
}

// Backward-compatible alias for code/tests that import the old name.
export const NAV_AREAS = PRIMARY_NAV_AREAS;

// Backward-compatible alias for the old flyout helper name.
export const filterFlyoutByPermissions = filterNavItemsByPermissions;
