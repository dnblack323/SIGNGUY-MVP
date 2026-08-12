import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Bot,
  CalendarDays,
  CheckCircle2,
  CircleHelp,
  DollarSign,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  ShieldAlert,
  ShoppingBag,
  Store,
  UserPlus,
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
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import NotificationBell from "@/components/notifications/NotificationBell";
import AssistantLauncher from "@/components/assistant/AssistantLauncher";
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
  newIntake: { key: "newIntake", label: "New Intake Request", icon: Plus, to: "/intake/new", permission: "intake:write" },
  newCustomer: { key: "newCustomer", label: "New Customer", icon: UserPlus, to: "/customers", permission: "customer:write" },
  newQuote: { key: "newQuote", label: "New Quote", icon: FileText, to: "/quotes", permission: "quote:write" },
  newOrder: { key: "newOrder", label: "New Order", icon: ShoppingBag, to: "/orders?new=1", permission: "order:write" },
  invitePortal: { key: "invitePortal", label: "Invite Customer to Portal", icon: UserPlus, to: "/customers?portalInvite=1", permission: "customer:write" },
  newWebstore: { key: "newWebstore", label: "New Webstore", icon: Store, to: "/webstores", permission: "webstore:write" },
  newWrapProject: { key: "newWrapProject", label: "New Wrap Project", icon: Plus, to: "/wrap-lab", permission: "wrap_lab:write" },
  pricing: { key: "pricing", label: "Pricing", icon: DollarSign, to: "/pricing-calculator", permission: "pricing:read" },
  task: { key: "task", label: "Task", icon: CheckCircle2, to: "/team/tasks", permission: "task:read" },
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
const QUICK_ACCESS_KEYS = ["newIntake", "newCustomer", "newQuote", "newOrder", "newWebstore", "newWrapProject", "assistant"];
const SIDEBAR_LEAVE_DELAY_MS = 180;
const DESKTOP_SIDEBAR_COLLAPSED_WIDTH = 76;
const DESKTOP_SIDEBAR_EXPANDED_WIDTH = 260;

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
  sales: ["newIntake", "newQuote", "newOrder"],
  customers: ["newCustomer", "newQuote", "newOrder"],
  production: ["newOrder", "calendar"],
  "approval-center": ["newQuote", "newOrder"],
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

function CommandButton({ command, permissions, compact = false, testPrefix = "shell-command", layout = "inline", active = false }) {
  const workspace = useWorkspace();
  if (!allowedCommand(command, permissions)) return null;
  const Icon = command.icon;
  const label = command.workspaceAction === "dockAndNew" && workspace.isCurrentRouteDocked
    ? command.dockedLabel
    : command.label;
  const content = command.workspaceAction === "dockAndNew" ? (
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className={cn(
          layout === "ribbon"
            ? "h-[52px] w-[72px] shrink-0 rounded-md border border-transparent px-1.5 py-1 text-[11px] whitespace-normal text-slate-700 hover:border-slate-200 hover:bg-white hover:text-slate-950 focus-visible:ring-2 focus-visible:ring-cyan-500"
            : "h-11 shrink-0 rounded-md px-2 text-xs text-slate-700 hover:bg-slate-100 hover:text-slate-950",
          compact && "size-9 px-0",
          active && "border-cyan-300 bg-cyan-50 text-slate-950 shadow-sm",
        )}
        data-testid={`${testPrefix}-${command.key}`}
        data-layout={layout}
        aria-label={label}
        title={compact ? undefined : command.tooltip}
        onClick={workspace.dockCurrentAndNew}
      >
        <span className={cn(
          "flex items-center justify-center",
          layout === "ribbon" ? "h-full flex-col gap-0.5 text-center" : "gap-0.5",
        )}>
          <Icon className={cn("size-4", layout === "ribbon" && "size-[18px]")} aria-hidden="true" />
          <span className={cn("leading-tight whitespace-normal", compact && "sr-only")}>{label}</span>
        </span>
      </Button>
    ) : (
    <Button
      asChild
      variant="ghost"
      size="sm"
      className={cn(
        layout === "ribbon"
          ? "h-[52px] w-[72px] shrink-0 rounded-md border border-transparent px-1.5 py-1 text-[11px] whitespace-normal text-slate-700 hover:border-slate-200 hover:bg-white hover:text-slate-950 focus-visible:ring-2 focus-visible:ring-cyan-500"
          : "h-11 shrink-0 rounded-md px-2 text-xs text-slate-700 hover:bg-slate-100 hover:text-slate-950",
        compact && "size-9 px-0",
        active && "border-cyan-300 bg-cyan-50 text-slate-950 shadow-sm",
      )}
      data-testid={`${testPrefix}-${command.key}`}
      data-layout={layout}
    >
      <Link
        to={command.to}
        aria-label={label}
        title={compact ? undefined : label}
        className={cn(
          "flex h-full items-center justify-center",
          layout === "ribbon" ? "flex-col gap-0.5 text-center" : "gap-0.5",
        )}
      >
        <Icon className={cn("size-4", layout === "ribbon" && "size-[18px]")} aria-hidden="true" />
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

function PrimaryAreaButton({ area, active, collapsed, onSelect }) {
  const Icon = area.icon;
  const button = (
    <button
      type="button"
      data-testid={area.testId}
      aria-label={area.label}
      aria-current={active ? "page" : undefined}
      data-active={active ? "true" : "false"}
      onClick={() => onSelect(area)}
      title={area.label}
      className={cn(
        "h-10 rounded-lg flex items-center gap-3 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/80",
        collapsed ? "w-10 justify-center px-0" : "w-full px-3",
        active ? "bg-white/10 text-white shadow-inner" : "text-slate-300 hover:bg-white/10 hover:text-white",
      )}
    >
      <Icon className={cn("size-4 shrink-0", area.accent)} aria-hidden="true" />
      {!collapsed && <span className="truncate">{area.label}</span>}
    </button>
  );

  if (!collapsed) return button;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{button}</TooltipTrigger>
      <TooltipContent side="right">{area.label}</TooltipContent>
    </Tooltip>
  );
}

function SidebarInner({ collapsed, selectedAreaKey, onSelectArea, onNavigate, mobile = false, pinned = false, onTogglePinned, tenant = null }) {
  const navAreas = PRIMARY_NAV_AREAS;
  return (
    <TooltipProvider delayDuration={200}>
      <div
        className="flex h-full flex-col bg-slate-950 text-slate-100"
        data-testid="app-shell-sidebar"
        data-collapsed={collapsed && !mobile ? "true" : "false"}
      >
        <div className={cn("border-b border-white/10", collapsed && !mobile ? "px-2 py-3" : "px-4 py-4")}>
          <div className={cn("flex items-center gap-3", collapsed && !mobile && "justify-center")}>
            {collapsed && !mobile ? (
              <SignGuyLogo
                variant="mark"
                className="size-11"
                alt="SignGuy AI"
                testId="sidebar-logo-compact"
              />
            ) : (
              <SignGuyLogo
                variant="full"
                className="h-20 w-full max-w-[228px] justify-start"
                imgClassName="object-left"
                alt="SignGuy AI"
                testId="sidebar-logo-full"
              />
            )}
            {(!collapsed || mobile) && (
              <div className="sr-only">
                <div className="font-display font-semibold text-sm truncate" data-testid="sidebar-tenant-name">
                  {tenant?.name || "SignGuy AI"}
                </div>
                <div className="text-[11px] text-slate-400 truncate">{tenant?.slug}</div>
              </div>
            )}
          </div>
        </div>

        <nav className="flex-1 px-2 py-2 space-y-1 overflow-y-auto overflow-x-hidden" data-testid="primary-sidebar-nav" aria-label="Main application areas">
          {navAreas.map((area) => (
            <div key={area.key} className={cn(area.key === "control-center" && "border-t border-white/10 pt-2 mt-2")}>
              <PrimaryAreaButton
                area={area}
                active={selectedAreaKey === area.key}
                collapsed={collapsed && !mobile}
                onSelect={(nextArea) => {
                  onSelectArea(nextArea);
                  onNavigate?.();
                }}
              />
            </div>
          ))}
        </nav>

        <div className="border-t border-white/10 px-2 py-2" data-testid="sidebar-bottom-controls">
          {!mobile && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  size="icon"
                  aria-label={pinned ? "Unpin sidebar" : "Pin sidebar open"}
                  className="mx-auto size-9 bg-transparent text-slate-300 hover:bg-white/10 hover:text-white"
                  data-testid="sidebar-pin-toggle"
                  onClick={onTogglePinned}
                >
                  {pinned ? <PanelLeftClose className="size-4" /> : <PanelLeftOpen className="size-4" />}
                </Button>
              </TooltipTrigger>
              <TooltipContent side={collapsed ? "right" : "top"}>{pinned ? "Unpin sidebar" : "Pin sidebar open"}</TooltipContent>
            </Tooltip>
          )}
        </div>
      </div>
    </TooltipProvider>
  );
}

function ModuleTabs({ area, permissions, user }) {
  const location = useLocation();
  const visibleItems = filterNavItemsByPermissions(area?.moduleNav || [], permissions, user);
  if (!area || !visibleItems.length) return null;
  return (
    <div
      data-testid="module-tab-row"
      data-area-key={area.key}
      className="flex min-w-0 flex-1"
      aria-label={`${area.label} secondary navigation`}
    >
      <div className="flex h-11 items-end gap-1 overflow-x-auto rounded-t-lg [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
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
                "mb-[-1px] inline-flex h-9 shrink-0 items-center rounded-t-md border border-b-0 px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500",
                active
                  ? "border-cyan-300 bg-cyan-50 text-slate-950 shadow-sm"
                  : "border-slate-200 bg-white/70 text-slate-600 hover:border-slate-300 hover:bg-white hover:text-slate-950",
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

function GlobalSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
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

  return (
    <form
      className="relative hidden w-full max-w-md md:block"
      role="search"
      data-testid="global-search"
      onSubmit={(event) => {
        event.preventDefault();
        const q = query.trim();
        const first = results.flatMap((group) => group.items)[0];
        if (first) {
          navigate(first.to);
          setOpen(false);
        } else if (q) {
          navigate(`/customers?search=${encodeURIComponent(q)}`);
        }
      }}
    >
      <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
      <input
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search customers, orders, quotes..."
        className="h-9 w-full rounded-md border border-slate-200 bg-white pl-8 pr-3 text-sm outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100"
        aria-label="Global search"
        onFocus={() => setOpen(true)}
        onKeyDown={(event) => {
          if (event.key === "Escape") setOpen(false);
        }}
      />
      {open && (query.trim().length >= 2 || busy) && (
        <div className="absolute left-0 right-0 top-10 z-50 max-h-96 overflow-y-auto rounded-md border bg-white p-2 shadow-xl" data-testid="global-search-results">
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
                  }}
                >
                  {item.label}
                </button>
              ))}
            </section>
          ))}
        </div>
      )}
    </form>
  );
}

function CreateMenu({ permissions }) {
  const actions = CREATE_KEYS.map((key) => COMMANDS[key]).filter((command) => command && allowedCommand(command, permissions));
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size="sm" data-testid="global-create-menu"><Plus className="mr-1 size-4" />Create</Button>
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

function AccountMenu() {
  const { user, tenant, logout, permissions } = useAuth();
  const { confirmBeforeAbandon } = useWorkspace();
  const canPlatformAdmin = permissions?.includes("platform:admin") || permissions?.includes("platform:creator") || user?.platform_admin || user?.platform_role;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="grid size-9 place-items-center rounded-lg hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500"
          data-testid="global-account-menu"
          aria-label="Account menu"
        >
          <Avatar className="size-8">
            <AvatarFallback>{(user?.full_name || user?.email || "U").slice(0, 1).toUpperCase()}</AvatarFallback>
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

function GlobalHeader({ area, module, permissions, onOpenMobileNav }) {
  const headerTitle = module?.label || area?.label || "Overview";
  return (
    <div className="border-b border-slate-200 bg-white px-4 md:px-6" data-testid="global-header">
      <div className="flex h-16 items-center gap-3">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-8 shrink-0 lg:hidden"
          data-testid="sidebar-open-mobile"
          aria-label="Open navigation"
          onClick={onOpenMobileNav}
        >
          <Menu className="size-4" />
        </Button>
        <div className="min-w-0 shrink-0 md:w-[260px]">
          <h1 className="truncate text-lg font-semibold leading-tight text-slate-950" data-testid="global-header-title">{headerTitle}</h1>
          <div className="mt-0.5 min-w-0" data-testid="global-breadcrumb-row">
            <Breadcrumbs area={area} module={module} />
          </div>
        </div>
        <div className="min-w-0 flex-1" />
        <GlobalSearch />
        <div className="flex shrink-0 items-center gap-1">
          <CreateMenu permissions={permissions} />
          <Button asChild size="icon" variant="ghost" data-testid="global-messages-button" aria-label="Messages">
            <Link to="/team/messages"><MessageSquare className="size-4" /></Link>
          </Button>
          <NotificationBell />
          <AccountMenu />
        </div>
      </div>
    </div>
  );
}

function ContextualRibbon({ area, module, permissions }) {
  const location = useLocation();
  const navigate = useNavigate();
  const activeSalesTab = module?.key === "sales" ? routeInternalTab(location.pathname, location.search) : null;
  const isSalesModule = module?.key === "sales";
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
  const keys = isSalesModule
    ? {
        intake: ["newIntake"],
        quotes: ["newQuote"],
        orders: ["newOrder"],
      }[activeSalesTab?.key] || []
    : RIBBON_BY_MODULE[module?.key] || RIBBON_BY_AREA[area?.key] || ["dashboard"];
  const commands = keys.map((key) => COMMANDS[key]).filter(Boolean);
  return (
    <TooltipProvider delayDuration={200}>
      <div
        data-testid="contextual-ribbon"
        data-area-key={area?.key}
        data-module-key={module?.key}
        className="border-b border-slate-200 bg-slate-50 px-4 py-1 md:px-6"
      >
        <div className="flex h-14 items-center gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {isSalesModule && (
            <>
              <div
                role="tablist"
                aria-label="Sales navigation"
                data-testid="sales-command-selector"
                className="flex h-8 shrink-0 items-center overflow-hidden rounded-md border border-slate-200 bg-white"
              >
                {SALES_INTERNAL_TABS.map((tab) => {
                  const active = activeSalesTab?.key === tab.key;
                  return (
                    <Link
                      key={tab.key}
                      to={tab.to}
                      role="tab"
                      aria-selected={active ? "true" : "false"}
                      aria-current={active ? "page" : undefined}
                      data-active={active ? "true" : "false"}
                      data-testid={`internal-tab-${tab.key}`}
                      className={cn(
                        "inline-flex h-full shrink-0 items-center border-r border-slate-200 px-2.5 text-xs font-medium transition-colors last:border-r-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-cyan-500",
                        active ? "bg-slate-950 text-white" : "text-slate-600 hover:bg-slate-50 hover:text-slate-950",
                      )}
                    >
                      {tab.label}
                    </Link>
                  );
                })}
              </div>
              <div className="mx-1 h-9 w-px shrink-0 bg-slate-200" aria-hidden="true" data-testid="sales-command-divider" />
            </>
          )}
          {commands.map((command) => (
            <CommandButton key={command.key} command={command} permissions={permissions} testPrefix="ribbon-command" layout="ribbon" />
          ))}
          {isOrdersPage && (
            <>
              <div className="mx-1 h-9 w-px shrink-0 bg-slate-200" aria-hidden="true" data-testid="ribbon-group-divider" />
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
                          "flex h-[52px] w-[76px] shrink-0 flex-col items-center justify-center gap-0.5 rounded-md border px-1.5 py-1 text-center text-[11px] leading-tight transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500",
                          active
                            ? "border-cyan-300 bg-cyan-50 text-slate-950 shadow-sm"
                            : "border-transparent text-slate-700 hover:border-slate-200 hover:bg-white hover:text-slate-950",
                        )}
                        onClick={() => setOrderView(view.status)}
                      >
                        <Icon className="size-[18px]" aria-hidden="true" />
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
                    className="flex h-[52px] w-[76px] shrink-0 flex-col items-center justify-center gap-0.5 rounded-md border border-transparent px-1.5 py-1 text-center text-[11px] leading-tight text-slate-700 transition-colors hover:border-slate-200 hover:bg-white hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500"
                  >
                    <ShoppingBag className="size-[18px]" aria-hidden="true" />
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
                        <Icon className="mr-2 size-4" aria-hidden="true" />
                        {view.label}
                        {active && <span className="ml-auto text-xs text-cyan-700">Active</span>}
                      </DropdownMenuItem>
                    );
                  })}
                </DropdownMenuContent>
              </DropdownMenu>
            </>
          )}
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
        "inline-flex h-9 shrink-0 items-center rounded-md border px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500",
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
  }

  if (!tabs.length) return null;

  return (
    <div className="border-b border-slate-200 bg-white px-4 py-1.5 md:px-6" data-testid="shell-internal-tabs">
      <div role="tablist" aria-label="Internal page tabs" className="flex gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {tabs.map((tab) => {
          const to = tab.to || `${basePath}?tab=${tab.key}`;
          return <InternalTabLink key={tab.key} tab={tab} active={activeKey === tab.key} to={to} />;
        })}
      </div>
    </div>
  );
}

function QuickAccessToolbar({ permissions }) {
  return (
    <TooltipProvider delayDuration={200}>
      <div
        className="shrink-0 py-1"
        data-testid="quick-access-toolbar"
        aria-label="Quick access toolbar"
      >
        <div className="flex min-w-0 items-center gap-2">
          <div className="flex min-w-0 items-center gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden" data-testid="quick-access-actions">
            {QUICK_ACCESS_KEYS.map((key) => (
              <CommandButton key={key} command={COMMANDS[key]} permissions={permissions} compact testPrefix="qat-command" />
            ))}
          </div>
        </div>
      </div>
    </TooltipProvider>
  );
}

function ShellPageHeading({ area, module }) {
  return (
    <div className="border-b border-slate-200 bg-white px-4 py-3 md:px-6" data-testid="shell-page-heading">
      <div className="text-xs text-slate-500" data-testid="shell-breadcrumb">
        {area?.label || "Shop Operations"} / {module?.label || "Overview"}
      </div>
      <div className="mt-1 flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-normal text-slate-950" data-testid="shell-page-title">
            {module?.label || area?.label || "Overview"}
          </h1>
          <p className="text-sm text-slate-500" data-testid="shell-page-description">
            {area?.label || "Shop Operations"} workspace
          </p>
        </div>
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
  const [desktopSidebarExpanded, setDesktopSidebarExpanded] = useState(false);
  const [desktopSidebarPinned, setDesktopSidebarPinned] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem("signguy.sidebarPinned") === "true";
  });
  const [devBannerHeight, setDevBannerHeight] = useState(0);
  const [selectedAreaKey, setSelectedAreaKey] = useState(null);
  const leaveTimerRef = useRef(null);
  const sidebarFocusWithinRef = useRef(false);
  const desktopSidebarRef = useRef(null);
  const devBannerRef = useRef(null);
  const location = useLocation();
  const navigate = useNavigate();
  const { devBypass, permissions, user, tenant } = useAuth();
  const pathArea = useMemo(() => findAreaForPath(location.pathname), [location.pathname]);
  const selectedArea = PRIMARY_NAV_AREAS.find((area) => area.key === (selectedAreaKey || pathArea.key)) || pathArea;
  const activeModule = activeModuleForPath(selectedArea, location.pathname, permissions, user);
  const isWebstoreDetailRoute = activeModule?.key === "webstores" && location.pathname.startsWith("/webstores/");

  useEffect(() => {
    setSelectedAreaKey(pathArea.key);
  }, [pathArea.key]);

  const selectArea = (area) => {
    setSelectedAreaKey(area.key);
    const target = firstAvailableModule(area, permissions, user);
    if (target) navigate(target.to);
  };

  const clearLeaveTimer = () => {
    if (!leaveTimerRef.current) return;
    window.clearTimeout(leaveTimerRef.current);
    leaveTimerRef.current = null;
  };

  const expandDesktopSidebar = () => {
    clearLeaveTimer();
    setDesktopSidebarExpanded(true);
  };

  const collapseDesktopSidebarSoon = () => {
    if (desktopSidebarPinned) return;
    clearLeaveTimer();
    leaveTimerRef.current = window.setTimeout(() => {
      if (!sidebarFocusWithinRef.current) setDesktopSidebarExpanded(false);
      leaveTimerRef.current = null;
    }, SIDEBAR_LEAVE_DELAY_MS);
  };

  useEffect(() => () => clearLeaveTimer(), []);

  useEffect(() => {
    if (desktopSidebarPinned) setDesktopSidebarExpanded(true);
    window.localStorage.setItem("signguy.sidebarPinned", String(desktopSidebarPinned));
  }, [desktopSidebarPinned]);

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
  const desktopSidebarWidth = desktopSidebarExpanded || desktopSidebarPinned
    ? DESKTOP_SIDEBAR_EXPANDED_WIDTH
    : DESKTOP_SIDEBAR_COLLAPSED_WIDTH;
  const mainSidebarOffset = DESKTOP_SIDEBAR_COLLAPSED_WIDTH;

  return (
    <div className="min-h-dvh overflow-x-hidden bg-slate-100 text-foreground" data-testid="authenticated-app-shell">
      {devBypass && (
        <div ref={devBannerRef} className="w-full bg-amber-50 border-b border-amber-200 text-amber-900 text-xs px-4 py-1.5 flex items-center justify-center gap-2" data-testid="dev-bypass-banner">
          <ShieldAlert className="size-3.5" />
          <span><span className="font-semibold">Auth bypass ON</span> · you're browsing as Dev Shop owner. Set <span className="mono">AUTH_DEV_BYPASS=false</span> before deploying.</span>
        </div>
      )}
      <div className="min-h-dvh" data-testid="app-shell-layout">
        <aside
          ref={desktopSidebarRef}
          className={cn(
            "fixed left-0 z-40 hidden flex-col border-r border-slate-900 bg-slate-950 shadow-2xl transition-[width] duration-150 ease-out lg:flex",
          )}
          style={{
            top: `${desktopSidebarOffset}px`,
            height: `calc(100dvh - ${desktopSidebarOffset}px)`,
            width: `${desktopSidebarWidth}px`,
          }}
          data-testid="desktop-sidebar-shell"
          data-expanded={(desktopSidebarExpanded || desktopSidebarPinned) ? "true" : "false"}
          data-pinned={desktopSidebarPinned ? "true" : "false"}
          data-sidebar-width={desktopSidebarWidth}
          onMouseEnter={() => !desktopSidebarPinned && expandDesktopSidebar()}
          onMouseLeave={collapseDesktopSidebarSoon}
          onFocusCapture={() => {
            sidebarFocusWithinRef.current = true;
            expandDesktopSidebar();
          }}
          onBlurCapture={(event) => {
            if (desktopSidebarRef.current?.contains(event.relatedTarget)) return;
            sidebarFocusWithinRef.current = false;
            collapseDesktopSidebarSoon();
          }}
        >
          <SidebarInner
            collapsed={!(desktopSidebarExpanded || desktopSidebarPinned)}
            selectedAreaKey={selectedArea.key}
            onSelectArea={selectArea}
            pinned={desktopSidebarPinned}
            onTogglePinned={() => setDesktopSidebarPinned((value) => !value)}
            tenant={tenant}
          />
        </aside>

        <div
          className="min-w-0 lg:pl-[var(--app-shell-sidebar-width)]"
          style={{ "--app-shell-sidebar-width": `${mainSidebarOffset}px` }}
          data-testid="app-shell-main-region"
          data-sidebar-width={mainSidebarOffset}
        >
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetContent side="left" className="w-[280px] border-slate-900 bg-slate-950 p-0">
              <SheetTitle className="sr-only">Application navigation</SheetTitle>
              <SheetDescription className="sr-only">Mobile navigation drawer for SignGuy AI work areas and account controls.</SheetDescription>
              <SidebarInner
                collapsed={false}
                selectedAreaKey={selectedArea.key}
                onSelectArea={selectArea}
                onNavigate={() => setMobileOpen(false)}
                mobile
                tenant={tenant}
              />
            </SheetContent>
          </Sheet>
          <header className="sticky top-0 z-30 bg-white shadow-sm" data-testid="app-shell-topbar">
            <GlobalHeader area={selectedArea} module={activeModule} permissions={permissions} onOpenMobileNav={() => setMobileOpen(true)} />
            <div className="flex h-11 min-w-0 items-center gap-3 border-b border-slate-200 bg-white px-4 md:px-6" data-testid="secondary-navigation-row">
              <ModuleTabs area={selectedArea} permissions={permissions} user={user} />
              <QuickAccessToolbar permissions={permissions} />
            </div>
          </header>

          <SupportModeBanner />
          {!isWebstoreDetailRoute && activeModule?.key !== "sales" && <ShellPageHeading area={selectedArea} module={activeModule} />}
          <ShellInternalTabs module={activeModule} />
          <ContextualRibbon area={selectedArea} module={activeModule} permissions={permissions} />
          <main className="w-full px-4 py-3 pb-24 md:px-6" data-testid="app-shell-content" data-active-path={location.pathname}>
            <Outlet />
          </main>
          <div className="h-16 md:h-14" data-testid="workspace-dock-reserved-space" aria-hidden="true" />
          <WorkspaceDock sidebarCollapsed />
          <AssistantLauncher />
        </div>
      </div>
    </div>
  );
}
