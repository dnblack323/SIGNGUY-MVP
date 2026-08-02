/**
 * Authenticated application shell navigation contract.
 *
 * Desktop shell:
 * - primary sidebar = six main application areas only;
 * - module navigation = persistent horizontal tabs in the content header;
 * - contextual ribbon = module-specific command surface.
 */
import {
  CircleHelp,
  DollarSign,
  HelpCircle,
  Palette,
  Settings,
  ShoppingBag,
  Sparkles,
  Users,
} from "lucide-react";

export const PRIMARY_NAV_AREAS = [
  {
    key: "shop-operations",
    label: "Shop Operations",
    icon: ShoppingBag,
    accent: "text-cyan-300",
    to: "/",
    testId: "primary-nav-shop-operations",
    moduleNav: [
      {
        key: "overview",
        label: "Overview",
        to: "/",
        testId: "module-nav-shop-overview",
      },
      {
        key: "intake",
        label: "Intake",
        to: "/intake",
        perm: "intake:read",
        testId: "module-nav-intake",
        match: ["/intake"],
      },
      {
        key: "customers",
        label: "Customers",
        to: "/customers",
        perm: "customer:read",
        testId: "module-nav-customers",
        match: ["/customers"],
      },
      {
        key: "quotes",
        label: "Quotes",
        to: "/quotes",
        perm: "quote:read",
        testId: "module-nav-quotes",
        match: ["/quotes"],
      },
      {
        key: "orders",
        label: "Orders",
        to: "/orders",
        perm: "order:read",
        testId: "module-nav-orders",
        match: ["/orders"],
      },
      {
        key: "pricing",
        label: "Pricing",
        to: "/pricing-calculator",
        perm: "pricing:read",
        testId: "module-nav-pricing",
        match: ["/pricing-calculator"],
      },
      {
        key: "production",
        label: "Production",
        to: "/work-orders",
        perm: "work_order:read",
        testId: "module-nav-production",
        match: ["/work-orders", "/kiosk/production"],
      },
      {
        key: "shop-schedule",
        label: "Shop Schedule",
        to: "/shop-schedule",
        perm: "schedule:read",
        testId: "module-nav-shop-schedule",
      },
      {
        key: "library",
        label: "Library/DocuLink",
        to: "/documents",
        perm: "document:read",
        testId: "module-nav-library",
        match: [
          "/documents",
          "/decision-rooms",
          "/decision-room-review-queue",
          "/templates",
          "/forms",
        ],
      },
      {
        key: "webstores",
        label: "Webstores",
        to: "/webstores",
        perm: "webstore:read",
        testId: "module-nav-webstores",
        match: ["/webstores"],
      },
      {
        key: "wrap-lab",
        label: "Wrap Lab",
        to: "/wrap-lab",
        perm: "wrap_lab:read",
        testId: "module-nav-wrap-lab",
        match: ["/wrap-lab"],
      },
    ],
  },
  {
    key: "business-finance",
    label: "Business & Finance",
    icon: DollarSign,
    accent: "text-emerald-300",
    to: "/finance",
    testId: "primary-nav-business-finance",
    moduleNav: [
      {
        key: "overview",
        label: "Overview",
        to: "/finance",
        perm: "finance:read",
        testId: "module-nav-finance-overview",
      },
      {
        key: "invoices",
        label: "Invoices",
        to: "/invoices",
        perm: "invoice:read",
        testId: "module-nav-invoices",
        match: ["/invoices"],
      },
      {
        key: "expenses",
        label: "Expenses",
        to: "/expenses",
        perm: "expense:read",
        testId: "module-nav-expenses",
      },
      {
        key: "taxes",
        label: "Taxes",
        to: "/tax",
        perm: "tax_report:read",
        testId: "module-nav-taxes",
      },
      {
        key: "reports",
        label: "Reports",
        to: "/reports",
        perm: "report:read",
        testId: "module-nav-reports",
      },
      {
        key: "pricing-defaults",
        label: "Pricing Defaults",
        to: "/pricing-foundation",
        perm: "pricing:read",
        testId: "module-nav-pricing-defaults",
      },
    ],
  },
  {
    key: "team-workflow",
    label: "Team & Workflow",
    icon: Users,
    accent: "text-violet-300",
    to: "/team",
    testId: "primary-nav-team-workflow",
    moduleNav: [
      {
        key: "overview",
        label: "Overview",
        to: "/team",
        testId: "module-nav-team-overview",
      },
      {
        key: "employees",
        label: "Employees",
        to: "/team/employees",
        perm: "employee:read",
        testId: "module-nav-employees",
        match: ["/team/employees"],
      },
      {
        key: "equipment",
        label: "Equipment",
        to: "/team/equipment",
        perm: "equipment:read",
        testId: "module-nav-equipment",
        match: ["/team/equipment"],
      },
      {
        key: "training",
        label: "Training",
        to: "/team/training",
        perm: "training:manage",
        testId: "module-nav-training",
      },
      {
        key: "certifications",
        label: "Certifications",
        to: "/team/certifications",
        perm: "certification:read",
        testId: "module-nav-certifications",
      },
      {
        key: "tasks",
        label: "Tasks",
        to: "/team/tasks",
        perm: "task:read",
        testId: "module-nav-tasks",
      },
      {
        key: "team-schedule",
        label: "Team Schedule",
        to: "/team/schedule",
        perm: "schedule:read",
        testId: "module-nav-team-schedule",
      },
      {
        key: "time-clock",
        label: "Time Clock",
        to: "/team/time-clock",
        perm: "timeclock:self",
        testId: "module-nav-time-clock",
      },
      {
        key: "timesheets",
        label: "Timesheets",
        to: "/team/timesheets",
        perm: "timesheet:self",
        testId: "module-nav-timesheets",
      },
      {
        key: "payroll",
        label: "Payroll",
        to: "/team/payroll",
        perm: "payroll:read",
        testId: "module-nav-payroll",
      },
      {
        key: "messages",
        label: "Messages",
        to: "/team/messages",
        perm: "message:read",
        testId: "module-nav-messages",
      },
      {
        key: "announcements",
        label: "Announcements",
        to: "/team/announcements",
        testId: "module-nav-announcements",
      },
      {
        key: "employee-portal",
        label: "Employee Portal",
        to: "/team/employee-portal",
        perm: "employee:manage",
        testId: "module-nav-employee-portal",
      },
    ],
  },
  {
    key: "design-studio",
    label: "Design Studio",
    icon: Palette,
    accent: "text-amber-300",
    to: "/studio",
    testId: "primary-nav-design-studio",
    moduleNav: [
      {
        key: "overview",
        label: "Overview",
        to: "/studio",
        perm: "ai_tool:use",
        testId: "module-nav-studio-overview",
      },
      {
        key: "assistant",
        label: "Business Assistant",
        to: "/studio/assistant",
        perm: "ai_assistant:use",
        testId: "module-nav-business-assistant",
      },
      {
        key: "design-image",
        label: "Design & Image",
        to: "/studio/design-image",
        perm: "ai_tool:use",
        testId: "module-nav-design-image",
      },
      {
        key: "marketing-brand",
        label: "Marketing & Brand",
        to: "/studio/marketing-brand",
        perm: "ai_tool:use",
        testId: "module-nav-marketing-brand",
      },
      {
        key: "writing-documents",
        label: "Writing & Documents",
        to: "/studio/writing-documents",
        perm: "ai_tool:use",
        testId: "module-nav-writing-documents",
      },
      {
        key: "pricing-profitability",
        label: "Pricing & Profitability",
        to: "/studio/pricing-profitability",
        perm: "ai_tool:use",
        testId: "module-nav-pricing-profitability",
      },
      {
        key: "prompts",
        label: "Prompt Library",
        to: "/studio/prompts",
        perm: "ai_prompt:read",
        testId: "module-nav-prompt-library",
      },
      {
        key: "assets",
        label: "Generated Assets",
        to: "/studio/assets",
        perm: "document:read",
        testId: "module-nav-generated-assets",
      },
      {
        key: "activity",
        label: "AI Activity",
        to: "/studio/activity",
        perm: "ai_history:read",
        testId: "module-nav-ai-activity",
      },
    ],
  },
  {
    key: "control-center",
    label: "Control Center",
    icon: Settings,
    accent: "text-rose-300",
    to: "/settings",
    testId: "primary-nav-control-center",
    moduleNav: [
      {
        key: "overview",
        label: "Overview",
        to: "/settings",
        testId: "module-nav-settings-overview",
      },
      {
        key: "company",
        label: "Company Settings",
        to: "/settings/company",
        perm: "settings:read",
        testId: "module-nav-company-settings",
      },
      {
        key: "integrations",
        label: "Integrations",
        to: "/settings/integrations",
        perm: "integration:read",
        testId: "module-nav-integrations",
      },
      {
        key: "production-workflows",
        label: "Production Workflows",
        to: "/settings/production-workflows",
        perm: "production_workflow:read",
        testId: "module-nav-production-workflows",
      },
      {
        key: "subscriptions",
        label: "Subscriptions",
        to: "/settings/subscriptions",
        perm: "subscription:read",
        testId: "module-nav-subscriptions",
      },
      {
        key: "ai-credits",
        label: "AI Credits",
        to: "/settings/ai-credits",
        perm: "ai_credit:read",
        testId: "module-nav-ai-credits",
      },
      {
        key: "feature-access",
        label: "Feature Access",
        to: "/settings/features",
        perm: "settings:read",
        testId: "module-nav-feature-access",
      },
      {
        key: "ai-governance",
        label: "AI Governance",
        to: "/settings/ai-governance",
        platformOnly: true,
        testId: "module-nav-ai-governance",
      },
      {
        key: "data-security",
        label: "Data & Security",
        to: "/settings/data-security",
        perm: "audit:read",
        testId: "module-nav-data-security",
      },
    ],
  },
  {
    key: "help-community",
    label: "Help & Community",
    icon: HelpCircle,
    accent: "text-sky-300",
    to: "/help",
    testId: "primary-nav-help-community",
    moduleNav: [
      {
        key: "overview",
        label: "Help Center",
        to: "/help",
        perm: "help:read",
        testId: "module-nav-help-center",
      },
      {
        key: "documentation",
        label: "Documentation",
        to: "/help/docs",
        perm: "help:read",
        testId: "module-nav-documentation",
      },
      {
        key: "onboarding",
        label: "Onboarding",
        to: "/help/onboarding",
        perm: "onboarding:read",
        testId: "module-nav-onboarding",
        match: ["/help/onboarding", "/onboarding"],
      },
      {
        key: "community",
        label: "Community",
        to: "/help/community",
        perm: "community:read",
        testId: "module-nav-community",
      },
      {
        key: "bug-reports",
        label: "Bug Reports",
        to: "/help/bugs",
        perm: "community:read",
        testId: "module-nav-bug-reports",
      },
      {
        key: "feature-requests",
        label: "Feature Requests",
        to: "/help/feature-requests",
        perm: "community:read",
        testId: "module-nav-feature-requests",
      },
      {
        key: "contact-support",
        label: "Contact Support",
        to: "/help/contact",
        perm: "support:write",
        testId: "module-nav-contact-support",
      },
      {
        key: "whats-new",
        label: "What's New",
        to: "/help/whats-new",
        perm: "help:read",
        testId: "module-nav-whats-new",
      },
    ],
  },
];

export function isPlatformUser(user = null, permissions = []) {
  const set = new Set(permissions || []);
  return !!(
    user?.platform_admin ||
    ["admin", "owner", "PLATFORM_ADMIN", "PLATFORM_CREATOR"].includes(
      user?.platform_role,
    ) ||
    set.has("platform:admin") ||
    set.has("platform:creator")
  );
}

export function filterNavItemsByPermissions(items, permissions, user = null) {
  if (!Array.isArray(items)) return [];
  const set = new Set(permissions || []);
  const platformUser = isPlatformUser(user, permissions);
  return items.filter((entry) => {
    if (entry.platformOnly && !platformUser) return false;
    const requiredPermission = entry.perm || entry.permission;
    return !requiredPermission || set.has(requiredPermission);
  });
}

function itemMatchStrength(item, pathname) {
  if (!item || !pathname) return -1;
  const targets = item.match || [item.to];
  const matches = targets.filter((target) =>
    target === "/"
      ? pathname === "/"
      : pathname === target || pathname.startsWith(`${target}/`),
  );
  if (!matches.length) return -1;
  return Math.max(...matches.map((target) => target.length));
}

export function itemMatchesPath(item, pathname) {
  return itemMatchStrength(item, pathname) >= 0;
}

export function areaMatchesPath(area, pathname) {
  return area?.moduleNav?.some((item) => itemMatchesPath(item, pathname));
}

export function findAreaForPath(pathname) {
  return (
    PRIMARY_NAV_AREAS.find((area) => areaMatchesPath(area, pathname)) ||
    PRIMARY_NAV_AREAS[0]
  );
}

export function firstAvailableModule(area, permissions, user = null) {
  return (
    filterNavItemsByPermissions(area?.moduleNav || [], permissions, user)[0] ||
    null
  );
}

export function activeModuleForPath(area, pathname, permissions, user = null) {
  const visible = filterNavItemsByPermissions(
    area?.moduleNav || [],
    permissions,
    user,
  );
  const matches = visible
    .map((item) => ({ item, strength: itemMatchStrength(item, pathname) }))
    .filter(({ strength }) => strength >= 0)
    .sort((a, b) => b.strength - a.strength);
  return matches[0]?.item || visible[0] || null;
}

export const HELP_ICON = CircleHelp;
export const ASSISTANT_ICON = Sparkles;

export const NAV_AREAS = PRIMARY_NAV_AREAS;
