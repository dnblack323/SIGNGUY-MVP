/**
 * EC1 — Locked Navigation Contract.
 *
 * Collapsible left sidebar with side flyouts. Home + six areas + divider between
 * Creative Studio and Control Center. Permanent second-level top navigation is
 * NOT used. Page-specific ribbons/tabs/filters/actions/breadcrumbs are allowed
 * but must not duplicate sidebar or flyout entries.
 *
 * Structure MUST match Part 3.2 of the Final Scope & Decision Register and the
 * flyout structure in Prompt 5 (EC1 section 9). Do not add duplicate entries.
 * Do not add a permanent "More" overflow menu.
 *
 * Fields:
 *   key       stable id used in tests + progress tracking
 *   label     user-facing sidebar label
 *   icon      lucide-react component
 *   testId    data-testid attribute for the sidebar entry
 *   flyout    array of entries { key, label, to, perm, testId, disabled }
 *   perm      backend permission required to see the AREA at all
 *   home      set to true for the home entry (no flyout)
 *   divider   set to true to render a divider AFTER this entry
 */
import {
  Home,
  ShoppingBag,
  DollarSign,
  Users,
  Sparkles,
  Settings,
  HelpCircle,
} from "lucide-react";

export const NAV_AREAS = [
  {
    key: "home",
    label: "Home",
    icon: Home,
    to: "/",
    testId: "nav-home",
    home: true,
    perm: null,
  },
  {
    key: "shop-operations",
    label: "Shop Operations",
    icon: ShoppingBag,
    testId: "nav-shop-operations",
    perm: null,
    flyout: [
      { key: "overview", label: "Overview", to: "/", perm: null, testId: "flyout-shop-overview" },
      { key: "intake", label: "Intake", to: "/intake", perm: "intake:read", testId: "flyout-intake" },
      { key: "decision-rooms", label: "Decision Rooms", to: "/decision-rooms", perm: "decision_room:read", testId: "flyout-decision-rooms" },
      { key: "decision-room-review-queue", label: "Decision Review Queue", to: "/decision-room-review-queue", perm: "decision_room:read", testId: "flyout-decision-room-review-queue" },
      { key: "templates", label: "Templates", to: "/templates", perm: "template:read", testId: "flyout-templates" },
      { key: "customers", label: "Customers", to: "/customers", perm: "customer:read", testId: "flyout-customers" },
      { key: "quotes", label: "Quotes", to: "/quotes", perm: "quote:read", testId: "flyout-quotes" },
      { key: "orders", label: "Orders", to: "/orders", perm: "order:read", testId: "flyout-orders" },
      { key: "production", label: "Production", to: "/work-orders", perm: "work_order:read", testId: "flyout-production" },
      { key: "production-board", label: "Production Board", to: "/work-orders/board", perm: "work_order:read", testId: "flyout-production-board" },
      { key: "shop-schedule", label: "Shop Schedule", to: "/shop-schedule", perm: "schedule:read", testId: "flyout-shop-schedule", disabled: true },
      { key: "asset-library", label: "Asset Library", to: "/documents", perm: "document:read", testId: "flyout-asset-library" },
      { key: "inventory-purchasing", label: "Inventory & Purchasing", to: "/inventory", perm: "inventory:read", testId: "flyout-inventory-purchasing" },
      { key: "supply-center", label: "Supply Center", to: "/supply-center", perm: "purchasing:read", testId: "flyout-supply-center" },
      { key: "purchase-orders", label: "Purchase Orders", to: "/purchase-orders", perm: "purchasing:read", testId: "flyout-purchase-orders" },
      { key: "webstores", label: "Webstores", to: "/webstores", perm: "webstore:read", testId: "flyout-webstores", disabled: true },
      { key: "wrap-lab", label: "Wrap Lab", to: "/wrap-lab", perm: "wrap_lab:read", testId: "flyout-wrap-lab", disabled: true },
    ],
  },
  {
    key: "business-finance",
    label: "Business & Finance",
    icon: DollarSign,
    testId: "nav-business-finance",
    perm: null,
    flyout: [
      { key: "overview", label: "Overview", to: "/finance", perm: "finance:read", testId: "flyout-bf-overview" },
      { key: "financials", label: "Financials", to: "/finance", perm: "finance:read", testId: "flyout-financials" },
      { key: "sales", label: "Sales", to: "/finance", perm: "finance:read", testId: "flyout-sales" },
      { key: "expenses", label: "Expenses", to: "/expenses", perm: "expense:read", testId: "flyout-expenses" },
      { key: "taxes", label: "Taxes", to: "/tax", perm: "tax_report:read", testId: "flyout-taxes" },
      { key: "reports", label: "Reports", to: "/reports", perm: "report:read", testId: "flyout-reports" },
      { key: "analytics", label: "Business Analytics", to: "/business-finance/analytics", perm: "analytics:read", testId: "flyout-analytics", disabled: true },
    ],
  },
  {
    key: "team-workflow",
    label: "Team & Workflow",
    icon: Users,
    testId: "nav-team-workflow",
    perm: null,
    flyout: [
      { key: "overview", label: "Overview", to: "/team", perm: null, testId: "flyout-team-overview" },
      { key: "employees", label: "Employees", to: "/team/employees", perm: "employee:read", testId: "flyout-employees" },
      { key: "equipment", label: "Equipment", to: "/team/equipment", perm: "equipment:read", testId: "flyout-equipment" },
      { key: "training", label: "Training", to: "/team/training", perm: "training:manage", testId: "flyout-training" },
      { key: "certifications", label: "Certifications", to: "/team/certifications", perm: "certification:read", testId: "flyout-certifications" },
      { key: "tasks-kanban", label: "Tasks & Kanban", to: "/team/tasks", perm: "task:read", testId: "flyout-tasks-kanban", disabled: true },
      { key: "team-schedule", label: "Team Schedule", to: "/team/schedule", perm: "schedule:read", testId: "flyout-team-schedule" },
      { key: "time-clock", label: "Time Clock", to: "/team/time-clock", perm: "timeclock:self", testId: "flyout-time-clock" },
      { key: "timesheets", label: "Timesheets", to: "/team/timesheets", perm: "timesheet:self", testId: "flyout-timesheets" },
      { key: "payroll", label: "Payroll", to: "/team/payroll", perm: "payroll:read", testId: "flyout-payroll" },
      { key: "messages-notes", label: "Messages & Notes", to: "/team/messages", perm: null, testId: "flyout-messages-notes", disabled: true },
      { key: "announcements", label: "Announcements", to: "/team/announcements", perm: null, testId: "flyout-announcements" },
      { key: "employee-portal", label: "Employee Portal", to: "/team/employee-portal", perm: "employee:manage", testId: "flyout-employee-portal" },
    ],
  },
  {
    key: "creative-studio",
    label: "Creative Studio",
    icon: Sparkles,
    testId: "nav-creative-studio",
    perm: null,
    divider: true,
    flyout: [
      { key: "studio-overview", label: "Studio Overview", to: "/studio", perm: null, testId: "flyout-studio-overview", disabled: true },
      { key: "ai-assistant", label: "AI Assistant", to: "/studio/assistant", perm: "ai_assistant:use", testId: "flyout-ai-assistant", disabled: true },
      { key: "image-tools", label: "Image Tools", to: "/studio/image", perm: "ai_tool:use", testId: "flyout-image-tools", disabled: true },
      { key: "design-tools", label: "Design Tools", to: "/studio/design", perm: "ai_tool:use", testId: "flyout-design-tools", disabled: true },
      { key: "writing-tools", label: "Writing Tools", to: "/studio/writing", perm: "ai_tool:use", testId: "flyout-writing-tools", disabled: true },
      { key: "prompt-library", label: "Prompt Library", to: "/studio/prompts", perm: "ai_prompt:read", testId: "flyout-prompt-library", disabled: true },
      { key: "artwork-workspace", label: "Artwork Workspace", to: "/studio/artwork", perm: "ai_tool:use", testId: "flyout-artwork-workspace", disabled: true },
      { key: "generated-assets", label: "Generated Assets", to: "/studio/assets", perm: "document:read", testId: "flyout-generated-assets", disabled: true },
      { key: "ai-history", label: "AI History", to: "/studio/history", perm: "ai_history:read", testId: "flyout-ai-history", disabled: true },
    ],
  },
  {
    key: "control-center",
    label: "Control Center",
    icon: Settings,
    testId: "nav-control-center",
    perm: null,
    flyout: [
      { key: "overview", label: "Overview", to: "/settings", perm: null, testId: "flyout-cc-overview" },
      { key: "company-settings", label: "Company Settings", to: "/settings/company", perm: "settings:read", testId: "flyout-company-settings" },
      { key: "users-permissions", label: "Users & Permissions", to: "/settings/users", perm: "user:read", testId: "flyout-users-permissions", disabled: true },
      { key: "integrations", label: "Integrations", to: "/settings/integrations", perm: "integration:read", testId: "flyout-integrations" },
      { key: "pricing-defaults", label: "Pricing Defaults", to: "/pricing-foundation", perm: "pricing:read", testId: "flyout-pricing-defaults" },
      { key: "production-workflows", label: "Production Workflows", to: "/settings/production-workflows", perm: "production_workflow:read", testId: "flyout-production-workflows" },
      { key: "portals", label: "Portals", to: "/settings/portals", perm: "settings:read", testId: "flyout-portals", disabled: true },
      { key: "subscriptions-credits", label: "Subscriptions & AI Credits", to: "/settings/subscriptions", perm: "subscription:read", testId: "flyout-subscriptions-credits", disabled: true },
      { key: "feature-access", label: "Feature Access", to: "/settings/features", perm: "settings:read", testId: "flyout-feature-access" },
      { key: "platform-governance", label: "Platform Governance", to: "/settings/platform", perm: null, testId: "flyout-platform-governance", disabled: true, platformOnly: true },
      { key: "data-security", label: "Data & Security", to: "/settings/data-security", perm: "audit:read", testId: "flyout-data-security" },
    ],
  },
  {
    key: "help-community",
    label: "Help & Community",
    icon: HelpCircle,
    testId: "nav-help-community",
    perm: null,
    flyout: [
      { key: "help-center", label: "Help Center", to: "/help", perm: null, testId: "flyout-help-center", disabled: true },
      { key: "documentation", label: "Documentation", to: "/help/docs", perm: null, testId: "flyout-documentation", disabled: true },
      { key: "onboarding", label: "Onboarding", to: "/help/onboarding", perm: null, testId: "flyout-onboarding", disabled: true },
      { key: "community", label: "Community", to: "/help/community", perm: "community:read", testId: "flyout-community", disabled: true },
      { key: "bug-reports", label: "Bug Reports", to: "/help/bugs", perm: "community:read", testId: "flyout-bug-reports", disabled: true },
      { key: "feature-requests", label: "Feature Requests", to: "/help/feature-requests", perm: "community:read", testId: "flyout-feature-requests", disabled: true },
      { key: "contact-support", label: "Contact Support", to: "/help/contact", perm: null, testId: "flyout-contact-support", disabled: true },
      { key: "whats-new", label: "What's New", to: "/help/whats-new", perm: null, testId: "flyout-whats-new", disabled: true },
    ],
  },
];

export function filterFlyoutByPermissions(flyout, permissions) {
  if (!Array.isArray(flyout)) return [];
  const set = new Set(permissions || []);
  return flyout.filter((entry) => !entry.perm || set.has(entry.perm));
}
