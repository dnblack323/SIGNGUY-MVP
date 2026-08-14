import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Bot,
  Calculator,
  CalendarDays,
  CheckCircle2,
  CircleHelp,
  ClipboardCheck,
  ClipboardList,
  ClipboardPlus,
  Clock3,
  CopyPlus,
  DollarSign,
  Download,
  ExternalLink,
  Filter,
  FileText,
  KanbanSquare,
  LayoutDashboard,
  LogOut,
  Mail,
  Menu,
  MessageSquare,
  Monitor,
  Plus,
  RefreshCw,
  Search,
  Send,
  ShieldAlert,
  ShoppingBag,
  Store,
  Upload,
  User,
  UserCheck,
  UserPlus,
  Zap,
} from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import NotificationBell from "@/components/notifications/NotificationBell";
import SupportModeBanner from "@/components/platform/SupportModeBanner";
import WorkspaceDock from "@/components/workspaces/WorkspaceDock";
import { WorkspaceProvider, useWorkspace } from "@/context/WorkspaceContext";
import SignGuyLogo from "@/components/brand/SignGuyLogo";
import api from "@/lib/api";
import { cn } from "@/lib/utils";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  activeModuleForPath,
  filterNavItemsByPermissions,
  findAreaForPath,
  firstAvailableModule,
  itemMatchesPath,
  PRIMARY_NAV_AREAS,
} from "@/lib/navigation";

const COMMANDS = {
  dashboard: { key: "dashboard", label: "Overview", icon: LayoutDashboard, to: "/" },
  newIntake: { key: "newIntake", label: "New Intake", icon: ClipboardList, to: "/intake/new", permission: "intake:write" },
  newCustomer: { key: "newCustomer", label: "New Customer", icon: UserPlus, to: "/customers", permission: "customer:write" },
  newQuote: { key: "newQuote", label: "New Quote", icon: FileText, to: "/quotes", permission: "quote:write" },
  newOrder: { key: "newOrder", label: "New Order", icon: ClipboardPlus, to: "/orders?new=1", permission: "order:write" },
  sendQuote: { key: "sendQuote", label: "Send Quote", icon: Mail, to: "/quotes", permission: "quote:write" },
  followUp: { key: "followUp", label: "Follow Up", icon: MessageSquare, to: "/quotes", permission: "quote:read" },
  convertOrder: { key: "convertOrder", label: "Convert to Order", icon: ShoppingBag, to: "/quotes", permission: "order:write" },
  invitePortal: { key: "invitePortal", label: "Invite Customer to Portal", icon: UserPlus, to: "/customers?portalInvite=1", permission: "customer:write" },
  newWebstore: { key: "newWebstore", label: "New Webstore", icon: Store, to: "/webstores", permission: "webstore:write" },
  newWrapProject: { key: "newWrapProject", label: "New Wrap Project", icon: Plus, to: "/wrap-lab", permission: "wrap_lab:write" },
  pricing: { key: "pricing", label: "Pricing Calculator", icon: DollarSign, quickIcon: Calculator, to: "/pricing-calculator", permission: "pricing:read" },
  sendProof: { key: "sendProof", label: "Send Proof", icon: Send, to: "/decision-rooms", permission: "decision_room:read" },
  scheduleInstall: { key: "scheduleInstall", label: "Schedule Install", icon: CalendarDays, to: "/shop-schedule", permission: "schedule:read" },
  newAppointment: { key: "newAppointment", label: "New Appointment", icon: CalendarDays, to: "/shop-schedule?view=appointments&new=1", permission: "schedule:manage" },
  scheduleToday: { key: "scheduleToday", label: "Today", icon: Clock3, to: "/shop-schedule?date=today", permission: "schedule:read" },
  scheduleCalendar: { key: "scheduleCalendar", label: "Calendar", icon: CalendarDays, to: "/shop-schedule?view=calendar", permission: "schedule:read" },
  scheduleAgenda: { key: "scheduleAgenda", label: "Agenda", icon: ClipboardList, to: "/shop-schedule?view=agenda", permission: "schedule:read" },
  scheduleAppointments: { key: "scheduleAppointments", label: "Appointments", icon: ClipboardCheck, to: "/shop-schedule?view=appointments", permission: "schedule:read" },
  filter: { key: "filter", label: "Filter", icon: Filter, to: "#", permission: null },
  emailCustomer: { key: "emailCustomer", label: "Email Customer", icon: Mail, to: "/email-history", permission: "customer:read" },
  sendDocument: { key: "sendDocument", label: "Send Document", icon: FileText, to: "/documents", permission: "document:read" },
  requestApproval: { key: "requestApproval", label: "Request Approval", icon: UserCheck, to: "/decision-rooms", permission: "decision_room:read" },
  import: { key: "import", label: "Import", icon: Upload, to: "/customers", permission: "customer:write" },
  export: { key: "export", label: "Export", icon: Download, to: "/customers", permission: "customer:read" },
  mergeDuplicates: { key: "mergeDuplicates", label: "Merge Duplicates", icon: CopyPlus, to: "/customers", permission: "customer:write" },
  assignMe: { key: "assignMe", label: "Assign to Me", icon: UserCheck, to: "/approval-center", permission: "decision_room:read" },
  addInternalNote: { key: "addInternalNote", label: "Add Internal Note", icon: FileText, to: "/approval-center", permission: "decision_room:read" },
  markReviewed: { key: "markReviewed", label: "Mark Reviewed", icon: CheckCircle2, to: "/approval-center", permission: "decision_room:read" },
  applyDecision: { key: "applyDecision", label: "Apply Decision", icon: ClipboardCheck, to: "/approval-center", permission: "decision_room:read" },
  respond: { key: "respond", label: "Respond", icon: MessageSquare, to: "/approval-center", permission: "decision_room:read" },
  newDecisionRoom: { key: "newDecisionRoom", label: "New Decision Room", icon: FileText, to: "/decision-rooms", permission: "decision_room:read" },
  openRoom: { key: "openRoom", label: "Open Room", icon: ExternalLink, to: "/decision-rooms", permission: "decision_room:read" },
  workOrders: { key: "workOrders", label: "Work Orders", icon: ClipboardList, to: "/work-orders", permission: "work_order:read" },
  productionBoard: { key: "productionBoard", label: "Production Board", icon: KanbanSquare, to: "/work-orders/board", permission: "work_order:read" },
  openKiosk: { key: "openKiosk", label: "Open Kiosk", icon: Monitor, to: "/kiosk/production", permission: "work_order:read" },
  assignWork: { key: "assignWork", label: "Assign", icon: UserPlus, to: "/work-orders", permission: "work_order:read" },
  startWork: { key: "startWork", label: "Start", icon: CheckCircle2, to: "/work-orders", permission: "work_order:read" },
  waitWork: { key: "waitWork", label: "Wait", icon: CircleHelp, to: "/work-orders", permission: "work_order:read" },
  blockWork: { key: "blockWork", label: "Block", icon: ShieldAlert, to: "/work-orders", permission: "work_order:read" },
  completeWork: { key: "completeWork", label: "Complete", icon: ClipboardCheck, to: "/work-orders", permission: "work_order:read" },
  dueDate: { key: "dueDate", label: "Due Date", icon: CalendarDays, to: "/work-orders", permission: "work_order:read" },
  addNote: { key: "addNote", label: "Add Note", icon: FileText, to: "/work-orders", permission: "work_order:read" },
  refresh: { key: "refresh", label: "Refresh", icon: RefreshCw, to: "#", permission: null },
  task: { key: "task", label: "Task", icon: CheckCircle2, to: "/team/tasks", permission: "task:read" },
  taskList: { key: "taskList", label: "Task List", icon: ClipboardList, to: "/team/tasks", permission: "task:read" },
  timeClock: { key: "timeClock", label: "Time Clock", icon: Clock3, to: "/team/time-clock", permission: "timeclock:self" },
  calendar: { key: "calendar", label: "Calendar", icon: CalendarDays, to: "/shop-schedule", permission: "schedule:read" },
  assistant: { key: "assistant", label: "Assistant", icon: Bot, to: "/studio/assistant", permission: "ai_assistant:use" },
  help: { key: "help", label: "Help", icon: CircleHelp, to: "/help", permission: "help:read" },
  dockNew: {
    key: "dockNew",
    label: "Dock & New",
    dockedLabel: "New Workspace",
    icon: Plus,
    workspaceAction: "dockAndNew",
    tooltip: "Dock current work and open a new workspace",
  },
};

const CREATE_KEYS = ["newIntake", "newCustomer", "newQuote", "newOrder", "invitePortal", "newWebstore", "newWrapProject"];
const QUICK_ACCESS_KEYS = ["timeClock", "newOrder", "pricing", "productionBoard", "taskList"];
const DESKTOP_SIDEBAR_WIDTH = 96;

const COMMAND_COLOR_CLASSES = {
  document: "text-blue-700",
  approval: "text-violet-700",
  completion: "text-emerald-700",
  warning: "text-orange-700",
  destructive: "text-red-700",
  view: "text-slate-600",
  neutral: "text-slate-700",
};

const COMMAND_CATEGORY_BY_KEY = {
  newCustomer: "document",
  newIntake: "document",
  newQuote: "document",
  sendQuote: "document",
  followUp: "approval",
  requestApproval: "approval",
  sendProof: "approval",
  respond: "approval",
  newDecisionRoom: "approval",
  newOrder: "document",
  convertOrder: "completion",
  markReviewed: "completion",
  applyDecision: "completion",
  startWork: "completion",
  completeWork: "completion",
  scheduleInstall: "warning",
  newAppointment: "document",
  scheduleToday: "view",
  scheduleCalendar: "view",
  scheduleAgenda: "view",
  scheduleAppointments: "view",
  waitWork: "warning",
  dueDate: "warning",
  blockWork: "destructive",
  filter: "view",
  refresh: "view",
  openRoom: "view",
  openKiosk: "view",
  import: "view",
  export: "view",
};

const RIBBON_BY_AREA = {
  home: ["newIntake", "newCustomer", "newQuote", "newOrder"],
  "shop-operations": ["newIntake", "newCustomer", "newQuote", "newOrder"],
  "business-finance": ["pricing", "newQuote", "newOrder"],
  "team-productivity": ["task", "calendar"],
  "tools-resources": ["assistant", "pricing"],
  "control-center": ["pricing", "assistant", "help"],
  "help-community": ["help", "assistant"],
};

const RIBBON_BY_MODULE = {
  overview: [
    ["Create", ["newCustomer", "newIntake", "newQuote", "newOrder"]],
    ["Customer/Workflow", ["pricing", "sendProof", "scheduleInstall"]],
    ["View", ["filter"]],
  ],
  sales: [
    ["Create", ["newIntake", "newQuote", "newOrder"]],
    ["Pricing", ["pricing"]],
    ["Customer", ["sendQuote", "followUp", "requestApproval"]],
    ["Workflow", ["convertOrder", "scheduleInstall"]],
    ["View", ["filter"]],
  ],
  customers: [
    ["Create", ["newCustomer", "newQuote", "newOrder"]],
    ["Customer", ["emailCustomer", "sendDocument", "requestApproval"]],
    ["Manage", ["import", "export", "mergeDuplicates"]],
    ["View", ["filter"]],
  ],
  production: [
    ["Work", ["workOrders", "openKiosk"]],
    ["Stage", ["assignWork", "startWork", "waitWork", "blockWork", "completeWork"]],
    ["Manage", ["dueDate", "addNote"]],
    ["View", ["refresh", "filter"]],
  ],
  schedule: [
    ["Create", ["newAppointment"]],
    ["Schedule", ["scheduleToday", "scheduleCalendar", "scheduleAgenda", "scheduleAppointments"]],
  ],
  "approval-center": [
    ["Create", ["newDecisionRoom"]],
    ["Review", ["assignMe", "addInternalNote", "markReviewed", "applyDecision"]],
    ["Respond", ["respond", "openRoom"]],
    ["View", ["filter"]],
  ],
  webstores: [
    ["Create", ["newWebstore"]],
    ["Customer", ["sendProof", "requestApproval"]],
    ["View", ["filter"]],
  ],
  "wrap-lab": [
    ["Create", ["newWrapProject"]],
    ["Customer/Workflow", ["pricing", "sendProof", "scheduleInstall"]],
    ["View", ["filter"]],
  ],
  tasks: ["task", "calendar"],
  "team-schedule": ["calendar", "task"],
  assistant: ["assistant"],
  "design-image": ["assistant"],
  "marketing-brand": ["assistant"],
  "writing-documents": ["assistant"],
  "pricing-profitability": ["assistant", "pricing"],
};

const ORDER_VIEW_OPTIONS = [
  { key: "all", label: "All Orders", status: "all", icon: LayoutDashboard },
  { key: "draft", label: "Draft", status: "draft", icon: FileText },
  { key: "confirmed", label: "Confirmed", status: "confirmed", icon: CheckCircle2 },
  { key: "ready", label: "Ready", status: "ready", icon: CheckCircle2 },
  { key: "in_production", label: "In Production", status: "in_production", icon: ShoppingBag },
  { key: "completed", label: "Completed", status: "completed", icon: CheckCircle2 },
  { key: "cancelled", label: "Cancelled", status: "cancelled", icon: CircleHelp },
];

const ORDER_QUICK_VIEW_KEYS = ["all", "in_production", "ready"];

function allowedCommand(command, permissions) {
  return !command.permission || permissions?.includes(command.permission);
}

function commandCategory(command) {
  return COMMAND_CATEGORY_BY_KEY[command?.key] || "neutral";
}

function commandIconClass(command) {
  return COMMAND_COLOR_CLASSES[commandCategory(command)] || COMMAND_COLOR_CLASSES.neutral;
}

function orderViewIconClass(view) {
  if (view.status === "completed" || view.status === "ready" || view.status === "confirmed") return COMMAND_COLOR_CLASSES.completion;
  if (view.status === "cancelled") return COMMAND_COLOR_CLASSES.destructive;
  if (view.status === "in_production") return COMMAND_COLOR_CLASSES.warning;
  return COMMAND_COLOR_CLASSES.view;
}

function CommandButton({ command, permissions, compact = false, testPrefix = "shell-command", layout = "inline", active = false }) {
  const workspace = useWorkspace();
  if (!allowedCommand(command, permissions)) return null;
  const Icon = command.icon;
  const category = commandCategory(command);
  const label = command.workspaceAction === "dockAndNew" && workspace.isCurrentRouteDocked
    ? command.dockedLabel
    : command.label;
  const baseClass = cn(
    layout === "ribbon"
      ? "flex h-[48px] w-[64px] shrink-0 flex-col items-center justify-center gap-0.5 rounded-sm border border-transparent px-1 py-1 text-center text-[10px] leading-tight text-slate-900 hover:border-slate-200 hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
      : compact
        ? "grid size-11 shrink-0 place-items-center rounded-md text-white/90 hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80"
        : "h-9 shrink-0 rounded-md px-2 text-xs text-slate-700 hover:bg-slate-100 hover:text-slate-950",
    active && "border-blue-300 bg-blue-50 text-slate-950 shadow-sm",
  );
  const iconClass = cn(
    layout === "ribbon" ? "size-[19px]" : "size-5",
    compact && "size-6",
  );

  const content = command.workspaceAction === "dockAndNew" ? (
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className={baseClass}
        data-testid={`${testPrefix}-${command.key}`}
        data-layout={layout}
        data-command-category={category}
        aria-label={label}
        title={compact ? undefined : command.tooltip}
        onClick={workspace.dockCurrentAndNew}
      >
        <span className={cn("flex items-center justify-center", layout === "ribbon" ? "h-full flex-col gap-1 text-center" : "gap-1")}>
          <Icon className={cn(iconClass, commandIconClass(command))} aria-hidden="true" />
          <span className={cn("leading-tight whitespace-normal", compact && "sr-only")}>{label}</span>
        </span>
      </Button>
    ) : (
    <Button
      asChild
      variant="ghost"
      size="sm"
      className={baseClass}
      data-testid={`${testPrefix}-${command.key}`}
      data-layout={layout}
      data-command-category={category}
    >
      <Link
        to={command.to}
        aria-label={label}
        title={compact ? undefined : label}
        className={cn(
          "flex h-full items-center justify-center",
          layout === "ribbon" ? "flex-col gap-1 text-center" : "gap-1",
        )}
      >
        <Icon className={cn(iconClass, commandIconClass(command))} aria-hidden="true" />
        <span className={cn("leading-tight whitespace-normal", compact && "sr-only")}>{label}</span>
      </Link>
    </Button>
  );

  if (!compact) return content;

  return (
    <Tooltip>
      <TooltipTrigger asChild>{content}</TooltipTrigger>
      <TooltipContent side="bottom">{command.tooltip || label}</TooltipContent>
    </Tooltip>
  );
}

function PrimaryAreaButton({ area, active, onSelect }) {
  const Icon = area.icon;
  return (
    <button
      type="button"
      data-testid={area.testId}
      aria-label={area.label}
      aria-current={active ? "page" : undefined}
      data-active={active ? "true" : "false"}
      onClick={() => onSelect(area)}
      title={area.label}
      className={cn(
        "flex min-h-[62px] w-full flex-col items-center justify-center gap-1 rounded-md px-1 py-1.5 text-center text-[11px] font-semibold leading-tight transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80",
        active ? "bg-blue-600 text-white shadow-inner" : "text-slate-200 hover:bg-white/10 hover:text-white",
      )}
    >
      <Icon className="size-5 shrink-0 stroke-[1.8] text-current" aria-hidden="true" />
      <span className="block max-w-[82px] text-balance">{area.label}</span>
    </button>
  );
}

function SidebarSignOutButton({ mobile = false }) {
  const { logout } = useAuth();
  const { confirmBeforeAbandon } = useWorkspace();
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="mx-auto size-10 text-white hover:bg-white/10 focus-visible:ring-2 focus-visible:ring-white/80"
          data-testid="sidebar-sign-out-button"
          aria-label="Sign out"
          title="Sign out"
          onClick={() => confirmBeforeAbandon(logout, "Sign out and leave unsaved workspace changes?")}
        >
          <LogOut className="size-5" aria-hidden="true" />
        </Button>
      </TooltipTrigger>
      <TooltipContent side={mobile ? "bottom" : "right"}>Sign out</TooltipContent>
    </Tooltip>
  );
}

function SidebarInner({ selectedAreaKey, onSelectArea, onNavigate, mobile = false, tenant = null }) {
  const navAreas = PRIMARY_NAV_AREAS;
  return (
    <TooltipProvider delayDuration={200}>
      <div
        className="flex h-full flex-col bg-[#06172a] text-slate-100"
        data-testid="app-shell-sidebar"
        data-collapsed="false"
      >
        <div className="grid h-[72px] place-items-center border-b border-white/10 px-2">
          <Tooltip>
            <TooltipTrigger asChild>
              <div>
                <SignGuyLogo
                  variant="mark"
                  className="h-10 w-[70px]"
                  alt="SignGuy AI"
                  testId="sidebar-logo-compact"
                />
              </div>
            </TooltipTrigger>
            <TooltipContent side={mobile ? "bottom" : "right"}>SignGuy AI</TooltipContent>
          </Tooltip>
          <div className="sr-only">
            <div data-testid="sidebar-tenant-name">{tenant?.name || "SignGuy AI"}</div>
            <div>{tenant?.slug}</div>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto overflow-x-hidden px-1 py-1 lg:overflow-y-hidden" data-testid="primary-sidebar-nav" aria-label="Main application areas">
          {navAreas.map((area) => (
            <div key={area.key} className={cn("py-px", area.key === "control-center" && "mt-1 border-t border-white/15 pt-1.5")}>
              <PrimaryAreaButton
                area={area}
                active={selectedAreaKey === area.key}
                onSelect={(nextArea) => {
                  onSelectArea(nextArea);
                  onNavigate?.();
                }}
              />
            </div>
          ))}
        </nav>

        <div className="space-y-1.5 border-t border-white/10 px-2 py-2" data-testid="sidebar-bottom-controls">
          <AccountMenu sidebar />
          {!mobile && (
            <NotificationBell
              testId="sidebar-notifications-button"
              tooltip="Notifications"
              className="mx-auto size-10 text-white hover:bg-white/10 focus-visible:ring-2 focus-visible:ring-white/80"
              iconClassName="size-5"
              badgeClassName="bg-blue-600 text-white"
            />
          )}
          <SidebarSignOutButton mobile={mobile} />
        </div>
      </div>
    </TooltipProvider>
  );
}

function ModuleTabs({ area, permissions, user }) {
  const location = useLocation();
  const visibleItems = filterNavItemsByPermissions(area?.moduleNav || [], permissions, user).filter((item) => !item.hidden);
  if (!area || !visibleItems.length) return null;
  return (
    <div
      data-testid="module-tab-row"
      data-area-key={area.key}
      className="flex min-w-0 flex-1 justify-center"
      aria-label={`${area.label} secondary navigation`}
    >
      <div className="flex h-11 items-center gap-3 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {visibleItems.map((item) => {
          const active = itemMatchesPath(item, location.pathname);
          return (
            <Link
              key={item.key}
              to={item.to}
              data-testid={item.testId}
              aria-current={active ? "page" : undefined}
              data-active={active ? "true" : "false"}
              className={cn(
                "inline-flex h-11 shrink-0 items-center border-b-2 px-2 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500",
                active
                  ? "border-blue-600 text-blue-700"
                  : "border-transparent text-slate-950 hover:border-blue-200 hover:text-blue-700",
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </div>
    </div>
  );
}

const SALES_INTERNAL_TABS = [
  { key: "intake", label: "Intake Requests", to: "/intake", match: ["/intake"] },
  { key: "quotes", label: "Quotes", to: "/quotes", match: ["/quotes"] },
  { key: "orders", label: "Orders", to: "/orders", match: ["/orders"] },
];

const CUSTOMER_RECORD_TABS = [
  { key: "overview", label: "Overview" },
  { key: "contacts", label: "Contacts" },
  { key: "communications", label: "Communications" },
  { key: "requests", label: "Requests" },
  { key: "quotes", label: "Quotes" },
  { key: "orders", label: "Orders" },
  { key: "files-forms", label: "Files & Forms" },
  { key: "portal", label: "Portal" },
  { key: "activity", label: "Activity" },
];

const ORDER_RECORD_TABS = [
  { key: "overview", label: "Overview" },
  { key: "items", label: "Order Items" },
  { key: "production", label: "Production" },
  { key: "documents-approvals", label: "Documents & Approvals" },
  { key: "files-artwork", label: "Files & Artwork" },
  { key: "financial", label: "Financial" },
  { key: "activity", label: "Activity" },
];

function routeInternalTab(pathname, search) {
  const params = new URLSearchParams(search || "");
  if (pathname.startsWith("/intake")) return { key: "intake", label: "Intake Requests", to: "/intake" };
  if (pathname.startsWith("/quotes")) return { key: "quotes", label: "Quotes", to: "/quotes" };
  if (pathname.startsWith("/orders")) return { key: "orders", label: "Orders", to: "/orders" };
  if (pathname === "/approval-center") {
    const key = params.get("tab") === "decision-rooms" ? "decision-rooms" : "approval-queue";
    return { key, label: key === "decision-rooms" ? "Decision Rooms" : "Approval Queue", to: `/approval-center?tab=${key === "decision-rooms" ? "decision-rooms" : "queue"}` };
  }
  return null;
}

function recordCrumb(pathname) {
  const parts = pathname.split("/").filter(Boolean);
  if (parts[0] === "intake" && parts[1] && parts[1] !== "new") return { label: `Request #${decodeURIComponent(parts[1])}`, type: "Intake Request" };
  if (parts[0] === "quotes" && parts[1]) return { label: `Quote #${decodeURIComponent(parts[1])}`, type: "Quote" };
  if (parts[0] === "orders" && parts[1]) return { label: `Order #${decodeURIComponent(parts[1])}`, type: "Order" };
  if (parts[0] === "customers" && parts[1]) return { label: `Customer ${decodeURIComponent(parts[1])}`, type: "Customer" };
  if (parts[0] === "work-orders" && parts[1] && parts[1] !== "board") return { label: `Work Order ${decodeURIComponent(parts[1])}`, type: "Work Order" };
  if (parts[0] === "decision-rooms" && parts[1] && parts[1] !== "new") return { label: `Decision Room ${decodeURIComponent(parts[1])}`, type: "Decision Room" };
  if (parts[0] === "webstores" && parts[1]) return { label: `Webstore ${decodeURIComponent(parts[1])}`, type: "Webstore" };
  if (parts[0] === "wrap-lab" && parts[1]) return { label: `Wrap Project ${decodeURIComponent(parts[1])}`, type: "Wrap Project" };
  return null;
}

function buildBreadcrumbs(area, module, location) {
  const pathname = location?.pathname || "/";
  const internal = routeInternalTab(pathname, location?.search);
  const record = recordCrumb(pathname);
  const crumbs = [{ label: area?.label || "Home", to: area?.to || "/" }];
  if (module && !(module.key === "sales" && internal)) crumbs.push({ label: module.label, to: module.to });
  if (internal && internal.label !== module?.label) crumbs.push({ label: internal.label, to: internal.to });
  if (record) crumbs.push({ label: record.label, current: true });
  if (!record && crumbs.length) crumbs[crumbs.length - 1] = { ...crumbs[crumbs.length - 1], current: true };
  return crumbs;
}

function Breadcrumbs({ area, module }) {
  const location = useLocation();
  const allCrumbs = buildBreadcrumbs(area, module, location);
  const crumbs = allCrumbs.length > 4
    ? [allCrumbs[0], { label: "...", overflow: true }, ...allCrumbs.slice(-2)]
    : allCrumbs;
  return (
    <nav aria-label="Breadcrumb" data-testid="global-breadcrumbs" className="min-w-0 text-xs">
      <ol className="flex min-w-0 items-center gap-1 text-slate-500">
        {crumbs.map((crumb, index) => (
          <li key={`${crumb.label}-${index}`} className="flex min-w-0 items-center gap-1">
            {index > 0 && <span aria-hidden="true">/</span>}
            {crumb.overflow ? (
              <button type="button" className="rounded px-1 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500" aria-label="Collapsed breadcrumb levels" title={allCrumbs.slice(1, -2).map((item) => item.label).join(" / ")}>...</button>
            ) : crumb.current ? (
              <span className="truncate font-medium text-slate-700" aria-current="page">{crumb.label}</span>
            ) : (
              <Link className="truncate rounded-sm hover:text-slate-950 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500" to={crumb.to}>{crumb.label}</Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

function GlobalSearch({ blue = false }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const [compactOpen, setCompactOpen] = useState(false);
  const navigate = useNavigate();
  const { permissions } = useAuth();

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setResults([]);
      return undefined;
    }
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setBusy(true);
      const searches = [
        permissions?.includes("customer:read") && {
          type: "Customers",
          run: () => api.get("/customers", { params: { search: q, limit: 5 } }),
          map: (item) => ({ label: item.name || item.company || item.email || "Customer", to: `/customers/${item.id}` }),
        },
        permissions?.includes("intake:read") && {
          type: "Intake Requests",
          run: () => api.get("/intake", { params: { q, limit: 5 } }),
          map: (item) => ({ label: `IN-${item.intake_number || item.id} ${item.project_name || item.contact_name || ""}`.trim(), to: `/intake/${item.id}` }),
        },
        permissions?.includes("quote:read") && {
          type: "Quotes",
          run: () => api.get("/quotes", { params: { q, limit: 5 } }),
          map: (item) => ({ label: `Q-${item.number || item.id} ${item.job_name || ""}`.trim(), to: `/quotes/${item.id}` }),
        },
        permissions?.includes("order:read") && {
          type: "Orders",
          run: () => api.get("/orders", { params: { q, limit: 5 } }),
          map: (item) => ({ label: `O-${item.number || item.id} ${item.job_name || ""}`.trim(), to: `/orders/${item.id}` }),
        },
        permissions?.includes("decision_room:read") && {
          type: "Approvals",
          run: () => api.get("/decision-room-review-queue", { params: { search: q, limit: 5 } }),
          map: (item) => ({ label: item.decision_room_title || item.decision_room_id || "Decision Room", to: item.decision_room_id ? `/decision-rooms/${item.decision_room_id}` : "/approval-center" }),
        },
      ].filter(Boolean);

      const settled = await Promise.allSettled(searches.map(async (entry) => {
        const response = await entry.run();
        const items = response?.data?.items || [];
        return { type: entry.type, items: items.map(entry.map).filter((item) => item.to && item.label) };
      }));
      if (!cancelled) {
        setResults(settled.filter((item) => item.status === "fulfilled").map((item) => item.value).filter((group) => group.items.length));
        setBusy(false);
        setOpen(true);
      }
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query, permissions]);

  const submitSearch = (event) => {
    event.preventDefault();
    const q = query.trim();
    const first = results.flatMap((group) => group.items)[0];
    if (first) {
      navigate(first.to);
      setOpen(false);
      setCompactOpen(false);
    } else if (q) {
      navigate(`/customers?search=${encodeURIComponent(q)}`);
      setCompactOpen(false);
    }
  };

  const searchResults = (
    <>
      {busy && <div className="px-2 py-2 text-xs text-slate-500">Searching...</div>}
      {!busy && results.length === 0 && <div className="px-2 py-2 text-xs text-slate-500">No permitted records found.</div>}
      {results.map((group) => (
        <section key={group.type} className="py-1" data-testid={`global-search-group-${group.type.toLowerCase().replace(/\s+/g, "-")}`}>
          <div className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">{group.type}</div>
          {group.items.map((item) => (
            <button
              key={`${group.type}-${item.to}`}
              type="button"
              className="block w-full rounded px-2 py-1.5 text-left text-sm hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500"
              onClick={() => {
                navigate(item.to);
                setOpen(false);
                setCompactOpen(false);
              }}
            >
              {item.label}
            </button>
          ))}
        </section>
      ))}
    </>
  );

  return (
    <>
      <form
        className="relative hidden w-[clamp(190px,20vw,250px)] min-[1024px]:block"
        role="search"
        data-testid="global-search"
        onSubmit={submitSearch}
      >
        <Search className={cn("pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2", blue ? "text-white" : "text-slate-400")} />
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search"
          className={cn(
            "h-9 w-full rounded-md border pl-8 pr-3 text-sm outline-none",
            blue
              ? "border-white/80 bg-white/5 text-white placeholder:text-white focus:border-white focus:ring-2 focus:ring-white/30"
              : "border-slate-200 bg-white text-slate-950 placeholder:text-slate-400 focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100",
          )}
          aria-label="Global search"
          onFocus={() => setOpen(true)}
          onKeyDown={(event) => {
            if (event.key === "Escape") setOpen(false);
          }}
        />
        {open && (query.trim().length >= 2 || busy) && (
          <div className="absolute left-0 right-0 top-10 z-50 max-h-96 overflow-y-auto rounded-md border bg-white p-2 shadow-xl" data-testid="global-search-results">
            {searchResults}
          </div>
        )}
      </form>
      <DropdownMenu open={compactOpen} onOpenChange={setCompactOpen}>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="grid size-10 shrink-0 place-items-center rounded-md text-white/95 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80 min-[1024px]:hidden"
            data-testid="global-search-compact-trigger"
            aria-label="Open global search"
            title="Search"
          >
            <Search className="size-5 stroke-[1.9]" aria-hidden="true" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-72 p-2" data-testid="global-search-compact-menu">
          <form role="search" data-testid="global-search-compact" onSubmit={submitSearch}>
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search"
                className="h-9 w-full rounded-md border border-slate-200 bg-white pl-8 pr-3 text-sm text-slate-950 outline-none placeholder:text-slate-400 focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100"
                aria-label="Compact global search"
                onFocus={() => setOpen(true)}
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    setOpen(false);
                    setCompactOpen(false);
                  }
                }}
              />
            </div>
          </form>
          {(open || compactOpen) && (query.trim().length >= 2 || busy) && (
            <div className="mt-2 max-h-80 overflow-y-auto rounded-md border bg-white p-2 shadow-sm" data-testid="global-search-compact-results">
              {searchResults}
            </div>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );
}

function CreateMenu({ permissions, blue = false }) {
  const actions = CREATE_KEYS.map((key) => COMMANDS[key]).filter((command) => command && allowedCommand(command, permissions));
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          size="sm"
          data-testid="global-create-menu"
          aria-label="Create"
          title="Create"
          className={cn("h-9 min-w-9 px-2 min-[900px]:px-3", blue && "border border-slate-950 bg-slate-950 text-white hover:bg-slate-900")}
        >
          <Plus className="size-4 min-[900px]:mr-1" />
          <span className="hidden min-[900px]:inline">Create</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        {actions.map((action) => {
          const Icon = action.icon;
          return (
            <DropdownMenuItem key={action.key} asChild data-testid={`create-action-${action.key}`}>
              <Link to={action.to}><Icon className="mr-2 size-4" />{action.label}</Link>
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function quickAccessCommands(permissions) {
  return QUICK_ACCESS_KEYS
    .map((key) => COMMANDS[key])
    .filter((command) => command && allowedCommand(command, permissions));
}

function QuickAccessLink({ command, mode = "desktop", onSelect }) {
  const Icon = command.quickIcon || command.icon;
  const label = command.label;
  if (mode === "menu") {
    return (
      <DropdownMenuItem asChild data-testid={`quick-access-menu-${command.key}`}>
        <Link to={command.to} aria-label={label} title={label} onClick={onSelect}>
          <Icon className="mr-2 size-4 text-slate-600" aria-hidden="true" />
          {label}
        </Link>
      </DropdownMenuItem>
    );
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Link
          to={command.to}
          data-testid={`quick-access-${command.key}`}
          aria-label={label}
          title={label}
          className="grid size-9 shrink-0 place-items-center rounded-md text-white/90 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80"
        >
          <Icon className="size-5 stroke-[1.9]" aria-hidden="true" />
        </Link>
      </TooltipTrigger>
      <TooltipContent side="bottom">{label}</TooltipContent>
    </Tooltip>
  );
}

function QuickAccessBar({ permissions }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const triggerRef = useRef(null);
  const commands = quickAccessCommands(permissions);

  const closeMenu = () => {
    setMenuOpen(false);
    requestAnimationFrame(() => triggerRef.current?.focus?.());
  };

  if (!commands.length) {
    return <div className="min-w-0" data-testid="quick-access-empty" />;
  }

  return (
    <TooltipProvider delayDuration={200}>
      <nav className="hidden items-center gap-1 min-[1400px]:flex" aria-label="Quick Access" data-testid="quick-access-bar">
        {commands.map((command) => <QuickAccessLink key={command.key} command={command} />)}
      </nav>
      <DropdownMenu open={menuOpen} onOpenChange={setMenuOpen}>
        <DropdownMenuTrigger asChild>
          <button
            ref={triggerRef}
            type="button"
            className="inline-flex h-10 min-w-10 items-center justify-center gap-2 rounded-md px-2 text-white/95 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80 min-[1400px]:hidden"
            data-testid="quick-access-menu-trigger"
            aria-label="Quick Access"
            title="Quick Access"
          >
            <Zap className="size-5 stroke-[1.9]" aria-hidden="true" />
            <span className="hidden text-sm font-medium sm:inline">Quick Access</span>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-64" data-testid="quick-access-menu">
          <DropdownMenuLabel>Quick Access</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {commands.map((command) => <QuickAccessLink key={command.key} command={command} mode="menu" onSelect={closeMenu} />)}
        </DropdownMenuContent>
      </DropdownMenu>
    </TooltipProvider>
  );
}

function accountInitials(user) {
  const source = (user?.full_name || user?.name || user?.email || "").trim();
  if (!source) return "";
  const parts = source.includes("@") ? source.split("@")[0].split(/[._-]+/) : source.split(/\s+/);
  return parts
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

function AccountMenu({ sidebar = false }) {
  const { user, tenant, logout, permissions } = useAuth();
  const { confirmBeforeAbandon } = useWorkspace();
  const canPlatformAdmin = permissions?.includes("platform:admin") || permissions?.includes("platform:creator") || user?.platform_admin || user?.platform_role;
  const initials = accountInitials(user);
  const avatarSrc = user?.profile_image_url || user?.avatar_url || user?.picture || user?.image_url;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={cn(
            "grid size-10 place-items-center rounded-lg focus-visible:outline-none focus-visible:ring-2",
            sidebar
              ? "mx-auto text-white hover:bg-white/10 focus-visible:ring-white/80"
              : "hover:bg-white/10 focus-visible:ring-white/80",
          )}
          data-testid={sidebar ? "sidebar-account-menu" : "global-account-menu"}
          aria-label="Account menu"
        >
          <Avatar className="size-8">
            {avatarSrc && <AvatarImage src={avatarSrc} alt="" data-testid={sidebar ? "sidebar-account-avatar-image" : "global-account-avatar-image"} />}
            <AvatarFallback
              className={cn(
                "bg-slate-100 text-sm font-semibold text-slate-700",
                sidebar && "bg-white text-slate-900",
              )}
              data-testid={sidebar ? "sidebar-account-avatar-fallback" : "global-account-avatar-fallback"}
            >
              {initials || <User className="size-4" aria-hidden="true" />}
            </AvatarFallback>
          </Avatar>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel>
          <span className="block truncate">{user?.full_name || user?.email}</span>
          <span className="block truncate text-xs font-normal text-muted-foreground">{tenant?.name || "SignGuy AI"}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild><Link to="/settings">Personal preferences</Link></DropdownMenuItem>
        <DropdownMenuItem asChild><Link to="/settings/company">Current company/shop</Link></DropdownMenuItem>
        <DropdownMenuItem asChild><Link to="/team/messages">Notification preferences</Link></DropdownMenuItem>
        <DropdownMenuItem asChild><Link to="/help">Help</Link></DropdownMenuItem>
        {canPlatformAdmin && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild data-testid="account-platform-admin-link"><Link to="/platform-admin">Switch to Platform Administration</Link></DropdownMenuItem>
          </>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => confirmBeforeAbandon(logout, "Sign out and leave unsaved workspace changes?")} data-testid="global-logout">
          <LogOut className="mr-2 size-4" />Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function GlobalHeader({ area, module, permissions, onToggleNavigation }) {
  const headerTitle = area?.key === "shop-operations" ? "Shop Operations" : area?.label || module?.label || "Overview";
  return (
    <div className="bg-blue-600 px-3 text-white shadow-sm md:px-5" data-testid="global-header">
      <div className="relative flex h-[58px] min-w-0 items-center justify-between gap-2 overflow-hidden">
        <div className="z-10 flex min-w-0 flex-1 items-center gap-1.5 pr-2" data-testid="global-header-left">
          <button
            type="button"
            className="grid size-10 place-items-center rounded-md text-white/95 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80 lg:hidden"
            data-testid="mobile-sidebar-menu-button"
            aria-label="Open navigation"
            title="Open navigation"
            onClick={onToggleNavigation}
          >
            <Menu className="size-6" aria-hidden="true" />
          </button>
          <QuickAccessBar permissions={permissions} />
        </div>
        <div className="pointer-events-none absolute inset-x-14 top-1/2 z-0 -translate-y-1/2 text-center sm:inset-x-20 lg:inset-x-36 min-[1400px]:inset-x-72" data-testid="global-header-title-frame">
          <h1 className="mx-auto max-w-[180px] truncate text-lg font-bold leading-tight text-white sm:max-w-[240px] min-[1024px]:max-w-[340px] min-[1400px]:max-w-[440px] min-[1400px]:text-xl" data-testid="global-header-title">{headerTitle}</h1>
          <div className="sr-only" data-testid="global-breadcrumb-row">
            <Breadcrumbs area={area} module={module} />
          </div>
        </div>
        <div className="z-10 flex min-w-0 flex-1 items-center justify-end gap-1.5 pl-2" data-testid="global-header-right">
          <GlobalSearch blue />
          <CreateMenu permissions={permissions} blue />
          <NotificationBell className="size-10 text-white hover:bg-white/10 focus-visible:ring-2 focus-visible:ring-white/80 lg:hidden" />
        </div>
      </div>
    </div>
  );
}

function normalizeRibbonGroups(area, module, activeSalesTab) {
  if (module?.key === "sales") {
    if (activeSalesTab?.key === "orders") {
      return [
        ["Create", ["newOrder"]],
        ["Views", []],
      ];
    }
    if (activeSalesTab?.key === "quotes") {
      return [
        ["Create", ["newQuote"]],
        ["Pricing", ["pricing"]],
        ["Customer", ["sendQuote", "followUp", "requestApproval"]],
        ["Workflow", ["convertOrder", "scheduleInstall"]],
        ["View", ["filter"]],
      ];
    }
    return RIBBON_BY_MODULE.sales;
  }

  const configured = RIBBON_BY_MODULE[module?.key] || RIBBON_BY_AREA[area?.key] || ["dashboard"];
  if (!Array.isArray(configured)) return [["Actions", ["dashboard"]]];
  if (Array.isArray(configured[0])) return configured;
  return [["Actions", configured]];
}

function ContextualRibbon({ area, module, permissions }) {
  const location = useLocation();
  const navigate = useNavigate();
  const activeSalesTab = module?.key === "sales" ? routeInternalTab(location.pathname, location.search) : null;
  const isOrdersPage = activeSalesTab?.key === "orders" && location.pathname === "/orders";
  const params = new URLSearchParams(location.search || "");
  const currentOrderView = ORDER_VIEW_OPTIONS.some((view) => view.status === params.get("status"))
    ? params.get("status")
    : "all";
  const selectedOrderView = ORDER_VIEW_OPTIONS.find((view) => view.status === currentOrderView) || ORDER_VIEW_OPTIONS[0];
  const setOrderView = (status) => {
    const next = new URLSearchParams(location.search || "");
    if (status === "all") next.delete("status");
    else next.set("status", status);
    const query = next.toString();
    navigate(`${location.pathname}${query ? `?${query}` : ""}`);
  };
  const groups = normalizeRibbonGroups(area, module, activeSalesTab);
  return (
    <TooltipProvider delayDuration={200}>
      <div
        data-testid="contextual-ribbon"
        data-area-key={area?.key}
        data-module-key={module?.key}
        className="border-b border-slate-200 bg-white px-4 md:px-6"
      >
        <div className="flex h-[84px] items-stretch gap-0 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {groups.map(([groupLabel, keys], groupIndex) => {
            const commands = keys.map((key) => COMMANDS[key]).filter(Boolean);
            const showOrderViews = isOrdersPage && groupLabel === "Views";
            return (
              <div
                key={`${groupLabel}-${groupIndex}`}
                className={cn("flex shrink-0 flex-col justify-between px-2 py-2", groupIndex > 0 && "border-l border-slate-200")}
                data-testid={`ribbon-group-${groupLabel.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
              >
                <div className="flex items-center gap-1">
                  {commands.map((command) => (
                    <CommandButton key={command.key} command={command} permissions={permissions} testPrefix="ribbon-command" layout="ribbon" />
                  ))}
                  {showOrderViews && (
                    <>
              {ORDER_QUICK_VIEW_KEYS.map((key) => ORDER_VIEW_OPTIONS.find((view) => view.key === key)).filter(Boolean).map((view) => {
                const Icon = view.icon;
                const active = currentOrderView === view.status;
                return (
                  <Tooltip key={view.key}>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        data-testid={`ribbon-order-view-${view.key}`}
                        data-active={active ? "true" : "false"}
                        aria-pressed={active ? "true" : "false"}
                        className={cn(
                          "flex h-[48px] w-[64px] shrink-0 flex-col items-center justify-center gap-0.5 rounded-sm border px-1 py-1 text-center text-[10px] leading-tight transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500",
                          active
                            ? "border-blue-300 bg-blue-50 text-slate-950 shadow-sm"
                            : "border-transparent text-slate-700 hover:border-slate-200 hover:bg-white hover:text-slate-950",
                        )}
                        onClick={() => setOrderView(view.status)}
                      >
                        <Icon className={cn("size-[18px]", orderViewIconClass(view))} aria-hidden="true" />
                        <span>{view.label}</span>
                      </button>
                    </TooltipTrigger>
                    <TooltipContent side="bottom">Show {view.label.toLowerCase()}</TooltipContent>
                  </Tooltip>
                );
              })}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    type="button"
                    data-testid="ribbon-order-views-dropdown"
                    className="flex h-[48px] w-[64px] shrink-0 flex-col items-center justify-center gap-0.5 rounded-sm border border-transparent px-1 py-1 text-center text-[10px] leading-tight text-slate-700 transition-colors hover:border-slate-200 hover:bg-white hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                  >
                    <ShoppingBag className={cn("size-[18px]", COMMAND_COLOR_CLASSES.view)} aria-hidden="true" />
                    <span>Order Views</span>
                    <span className="sr-only">Current view: {selectedOrderView.label}</span>
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-52" data-testid="ribbon-order-views-menu">
                  <DropdownMenuLabel>Order Views</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  {ORDER_VIEW_OPTIONS.map((view) => {
                    const Icon = view.icon;
                    const active = currentOrderView === view.status;
                    return (
                      <DropdownMenuItem
                        key={view.key}
                        onClick={() => setOrderView(view.status)}
                        data-testid={`ribbon-order-view-option-${view.key}`}
                        aria-current={active ? "true" : undefined}
                      >
                        <Icon className={cn("mr-2 size-4", orderViewIconClass(view))} aria-hidden="true" />
                        {view.label}
                        {active && <span className="ml-auto text-xs text-blue-700">Active</span>}
                      </DropdownMenuItem>
                    );
                  })}
                </DropdownMenuContent>
              </DropdownMenu>
                    </>
                  )}
                </div>
                <div className="pt-0.5 text-center text-[10px] font-medium uppercase tracking-wide text-slate-500">{groupLabel}</div>
              </div>
            );
          })}
        </div>
      </div>
    </TooltipProvider>
  );
}

function InternalTabLink({ tab, active, to }) {
  return (
    <Link
      to={to}
      role="tab"
      aria-selected={active ? "true" : "false"}
      aria-current={active ? "page" : undefined}
      data-active={active ? "true" : "false"}
      data-testid={`internal-tab-${tab.key}`}
      className={cn(
        "inline-flex h-8 shrink-0 items-center rounded-md border px-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500",
        active ? "border-slate-950 bg-slate-950 text-white shadow-sm" : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50 hover:text-slate-950",
      )}
    >
      {tab.label}
    </Link>
  );
}

function ShellInternalTabs({ module }) {
  const location = useLocation();
  const params = new URLSearchParams(location.search || "");
  const pathname = location.pathname;
  let tabs = [];
  let activeKey = null;
  let basePath = pathname;

  if (/^\/customers\/[^/]+/.test(pathname)) {
    tabs = CUSTOMER_RECORD_TABS;
    activeKey = params.get("tab") || "overview";
  } else if (/^\/orders\/[^/]+/.test(pathname)) {
    tabs = ORDER_RECORD_TABS;
    activeKey = params.get("tab") || "overview";
  } else if (module?.key === "sales" && ["/intake", "/quotes", "/orders"].includes(pathname)) {
    tabs = SALES_INTERNAL_TABS;
    activeKey = routeInternalTab(pathname, location.search)?.key;
  }

  if (!tabs.length) return null;

  return (
    <div className="border-b border-slate-200 bg-white px-4 py-1 md:px-6" data-testid="shell-internal-tabs">
      <div
        role="tablist"
        aria-label={module?.key === "sales" ? "Sales navigation" : "Internal page tabs"}
        data-testid={module?.key === "sales" ? "sales-command-selector" : undefined}
        className="flex gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {tabs.map((tab) => {
          const to = tab.to || `${basePath}?tab=${tab.key}`;
          return <InternalTabLink key={tab.key} tab={tab} active={activeKey === tab.key} to={to} />;
        })}
      </div>
    </div>
  );
}

export default function AppShell() {
  return (
    <WorkspaceProvider>
      <AppShellFrame />
    </WorkspaceProvider>
  );
}

function AppShellFrame() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [devBannerHeight, setDevBannerHeight] = useState(0);
  const [selectedAreaKey, setSelectedAreaKey] = useState(null);
  const desktopSidebarRef = useRef(null);
  const devBannerRef = useRef(null);
  const mobileMenuButtonRef = useRef(null);
  const location = useLocation();
  const navigate = useNavigate();
  const { devBypass, permissions, user, tenant } = useAuth();
  const pathArea = useMemo(() => findAreaForPath(location.pathname), [location.pathname]);
  const selectedArea = PRIMARY_NAV_AREAS.find((area) => area.key === (selectedAreaKey || pathArea.key)) || pathArea;
  const activeModule = activeModuleForPath(selectedArea, location.pathname, permissions, user);

  useEffect(() => {
    setSelectedAreaKey(pathArea.key);
  }, [pathArea.key]);

  const selectArea = (area) => {
    setSelectedAreaKey(area.key);
    const target = firstAvailableModule(area, permissions, user);
    if (target) navigate(target.to);
  };

  useLayoutEffect(() => {
    if (!devBypass) {
      setDevBannerHeight(0);
      return undefined;
    }

    const banner = devBannerRef.current;
    if (!banner) return undefined;

    const updateBannerHeight = () => {
      setDevBannerHeight(Math.ceil(banner.getBoundingClientRect().height));
    };

    updateBannerHeight();

    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(updateBannerHeight) : null;
    observer?.observe(banner);
    window.addEventListener("resize", updateBannerHeight);

    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", updateBannerHeight);
    };
  }, [devBypass]);

  const desktopSidebarOffset = devBypass ? devBannerHeight : 0;
  const desktopSidebarWidth = DESKTOP_SIDEBAR_WIDTH;
  const mainSidebarOffset = desktopSidebarWidth;
  const toggleNavigation = () => {
    mobileMenuButtonRef.current = document.activeElement;
    setMobileOpen(true);
  };

  const setMobileNavigationOpen = (open) => {
    setMobileOpen(open);
    if (!open) {
      requestAnimationFrame(() => mobileMenuButtonRef.current?.focus?.());
    }
  };

  return (
    <div className="min-h-dvh overflow-x-hidden bg-slate-100 text-foreground" data-testid="authenticated-app-shell" style={{ "--workspace-dock-height": "56px" }}>
      {devBypass && (
        <div ref={devBannerRef} className="w-full bg-amber-50 border-b border-amber-200 text-amber-900 text-xs px-4 py-1.5 flex items-center justify-center gap-2" data-testid="dev-bypass-banner">
          <ShieldAlert className="size-3.5" />
          <span><span className="font-semibold">Auth bypass ON</span> - you're browsing as Dev Shop owner. Set <span className="mono">AUTH_DEV_BYPASS=false</span> before deploying.</span>
        </div>
      )}
      <div className="min-h-dvh" data-testid="app-shell-layout">
        <aside
          ref={desktopSidebarRef}
          className={cn(
            "fixed left-0 z-40 hidden flex-col border-r border-slate-900 bg-[#06172a] shadow-2xl lg:flex",
          )}
          style={{
            top: `${desktopSidebarOffset}px`,
            height: `calc(100dvh - ${desktopSidebarOffset}px)`,
            width: `${desktopSidebarWidth}px`,
          }}
          data-testid="desktop-sidebar-shell"
          data-expanded="true"
          data-pinned="true"
          data-sidebar-width={desktopSidebarWidth}
        >
          <SidebarInner
            selectedAreaKey={selectedArea.key}
            onSelectArea={selectArea}
            tenant={tenant}
          />
        </aside>

        <div
          className="min-w-0 lg:pl-[var(--app-shell-sidebar-width)]"
          style={{ "--app-shell-sidebar-width": `${mainSidebarOffset}px` }}
          data-testid="app-shell-main-region"
          data-sidebar-width={mainSidebarOffset}
        >
          <Sheet open={mobileOpen} onOpenChange={setMobileNavigationOpen}>
            <SheetContent
              side="left"
              className="w-[280px] border-slate-900 bg-slate-950 p-0"
              closeClassName="grid size-11 place-items-center rounded-md border border-white/20 bg-slate-900/90 text-white opacity-100 hover:bg-slate-800 focus:ring-white focus:ring-offset-slate-950"
              closeLabel="Close navigation"
            >
              <SheetTitle className="sr-only">Application navigation</SheetTitle>
              <SheetDescription className="sr-only">Mobile navigation drawer for SignGuy AI work areas and account controls.</SheetDescription>
              <SidebarInner
                selectedAreaKey={selectedArea.key}
                onSelectArea={selectArea}
                onNavigate={() => setMobileOpen(false)}
                mobile
                tenant={tenant}
              />
            </SheetContent>
          </Sheet>
          <header className="sticky top-0 z-30 bg-white shadow-sm" data-testid="app-shell-topbar">
            <GlobalHeader
              area={selectedArea}
              module={activeModule}
              permissions={permissions}
              onToggleNavigation={toggleNavigation}
            />
            <div className="flex h-11 min-w-0 items-center gap-3 border-b border-slate-200 bg-white px-4 md:px-6" data-testid="secondary-navigation-row">
              <ModuleTabs area={selectedArea} permissions={permissions} user={user} />
            </div>
            <ContextualRibbon area={selectedArea} module={activeModule} permissions={permissions} />
          </header>

          <SupportModeBanner />
          <ShellInternalTabs module={activeModule} />
          <main className="w-full bg-slate-50 px-4 py-5 pb-24 md:px-6" data-testid="app-shell-content" data-active-path={location.pathname}>
            <Outlet />
          </main>
          <div className="h-16 md:h-[var(--workspace-dock-height)]" data-testid="workspace-dock-reserved-space" aria-hidden="true" />
          <WorkspaceDock />
        </div>
      </div>
    </div>
  );
}
