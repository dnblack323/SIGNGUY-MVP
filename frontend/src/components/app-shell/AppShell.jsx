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
  Plus,
  Search,
  ShieldAlert,
  ShoppingBag,
  Sparkles,
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
import WorkspaceDock from "@/components/workspaces/WorkspaceDock";
import { WorkspaceProvider, useWorkspace } from "@/context/WorkspaceContext";
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
  newCustomer: { key: "newCustomer", label: "Customer", icon: UserPlus, to: "/customers", permission: "customer:write" },
  newQuote: { key: "newQuote", label: "Quote", icon: FileText, to: "/quotes", permission: "quote:write" },
  newOrder: { key: "newOrder", label: "Order", icon: ShoppingBag, to: "/orders", permission: "order:write" },
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

const QUICK_ACCESS_KEYS = ["dockNew", "newCustomer", "newQuote", "newOrder", "pricing", "task", "calendar", "assistant"];
const SIDEBAR_LEAVE_DELAY_MS = 180;
const DESKTOP_SIDEBAR_COLLAPSED_WIDTH = 76;
const DESKTOP_SIDEBAR_EXPANDED_WIDTH = 260;

const RIBBON_BY_AREA = {
  "shop-operations": ["newCustomer", "newQuote", "newOrder", "pricing", "calendar"],
  "business-finance": ["pricing", "newQuote", "newOrder"],
  "team-workflow": ["task", "calendar"],
  "design-studio": ["assistant", "pricing"],
  "control-center": ["pricing", "assistant", "help"],
  "help-community": ["help", "assistant"],
};

const RIBBON_BY_MODULE = {
  customers: ["newCustomer", "newQuote", "newOrder"],
  quotes: ["newQuote", "pricing", "newOrder"],
  orders: ["newOrder", "pricing"],
  pricing: ["pricing", "newQuote", "newOrder"],
  production: ["newOrder", "calendar"],
  "shop-schedule": ["calendar", "task"],
  tasks: ["task", "calendar"],
  "team-schedule": ["calendar", "task"],
  assistant: ["assistant"],
  "design-image": ["assistant"],
  "marketing-brand": ["assistant"],
  "writing-documents": ["assistant"],
  "pricing-profitability": ["assistant", "pricing"],
};

function allowedCommand(command, permissions) {
  return !command.permission || permissions?.includes(command.permission);
}

function CommandButton({ command, permissions, compact = false, testPrefix = "shell-command" }) {
  const workspace = useWorkspace();
  if (!allowedCommand(command, permissions)) return null;
  const Icon = command.icon;
  const label = command.workspaceAction === "dockAndNew" && workspace.isCurrentRouteDocked
    ? command.dockedLabel
    : command.label;
  if (command.workspaceAction === "dockAndNew") {
    return (
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className={cn(
          "h-11 shrink-0 rounded-md px-2 text-xs text-slate-700 hover:bg-slate-100 hover:text-slate-950",
          compact && "h-10 px-2",
        )}
        data-testid={`${testPrefix}-${command.key}`}
        aria-label={label}
        title={command.tooltip}
        onClick={workspace.dockCurrentAndNew}
      >
        <span className="flex flex-col items-center gap-0.5">
          <Icon className="size-4" aria-hidden="true" />
          <span className={cn("leading-tight", compact && "hidden xl:inline")}>{label}</span>
        </span>
      </Button>
    );
  }
  return (
    <Button
      asChild
      variant="ghost"
      size="sm"
      className={cn(
        "h-11 shrink-0 rounded-md px-2 text-xs text-slate-700 hover:bg-slate-100 hover:text-slate-950",
        compact && "h-10 px-2",
      )}
      data-testid={`${testPrefix}-${command.key}`}
    >
      <Link to={command.to} aria-label={label} className="flex flex-col items-center gap-0.5">
        <Icon className="size-4" aria-hidden="true" />
        <span className={cn("leading-tight", compact && "hidden xl:inline")}>{label}</span>
      </Link>
    </Button>
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

  return button;
}

function SidebarInner({ collapsed, selectedAreaKey, onSelectArea, onNavigate, mobile = false }) {
  const { tenant, user, logout } = useAuth();
  const { confirmBeforeAbandon } = useWorkspace();
  return (
    <TooltipProvider delayDuration={200}>
      <div
        className="flex h-full flex-col bg-slate-950 text-slate-100"
        data-testid="app-shell-sidebar"
        data-collapsed={collapsed && !mobile ? "true" : "false"}
      >
        <div className={cn("border-b border-white/10", collapsed && !mobile ? "px-2 py-3" : "px-4 py-4")}>
          <div className={cn("flex items-center gap-2", collapsed && !mobile && "justify-center")}>
            <div className="grid size-9 place-items-center rounded-lg bg-cyan-400/15 text-cyan-200 ring-1 ring-cyan-300/20">
              <Sparkles className="size-4" aria-hidden="true" />
            </div>
            {(!collapsed || mobile) && (
              <div className="min-w-0">
                <div className="font-display font-semibold text-sm truncate" data-testid="sidebar-tenant-name">
                  {tenant?.name || "SignGuy AI"}
                </div>
                <div className="text-[11px] text-slate-400 truncate">{tenant?.slug}</div>
              </div>
            )}
          </div>
        </div>

        <nav className="flex-1 px-2 py-2 space-y-1 overflow-y-auto overflow-x-hidden" data-testid="primary-sidebar-nav">
          {PRIMARY_NAV_AREAS.map((area) => (
            <PrimaryAreaButton
              key={area.key}
              area={area}
              active={selectedAreaKey === area.key}
              collapsed={collapsed && !mobile}
              onSelect={(nextArea) => {
                onSelectArea(nextArea);
                onNavigate?.();
              }}
            />
          ))}
        </nav>

        <div className="border-t border-white/10 px-2 py-2 space-y-2" data-testid="sidebar-bottom-controls">
          {collapsed && !mobile ? (
            <Button
              type="button"
              size="icon"
              aria-label="Global search"
              className="mx-auto size-9 bg-transparent text-slate-300 hover:bg-white/10 hover:text-white"
              data-testid="sidebar-global-search"
            >
              <Search className="size-4" />
            </Button>
          ) : (
            <label className="relative block" data-testid="sidebar-global-search">
              <span className="sr-only">Global search</span>
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-slate-400" />
              <input
                type="search"
                placeholder="Search orders, customers, quotes..."
                className="h-8 w-full rounded-md border border-white/10 bg-white/5 pl-8 pr-2 text-xs text-slate-100 outline-none placeholder:text-slate-500 focus:border-cyan-300"
              />
            </label>
          )}
          <div className={cn(
            "flex items-center gap-1",
            collapsed && !mobile ? "flex-col" : "justify-between px-1",
            "[&_[data-testid=notification-bell]]:text-slate-300 [&_[data-testid=notification-bell]]:hover:bg-white/10",
          )}>
            <Button
              asChild
              size="icon"
              aria-label="Help"
              className="size-9 bg-transparent text-slate-300 hover:bg-white/10 hover:text-white"
              data-testid="sidebar-help-link"
            >
              <Link to="/help"><CircleHelp className="size-4" /></Link>
            </Button>
            <NotificationBell />
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                className={cn(
                  "w-full h-11 px-2 rounded-lg hover:bg-white/10 flex items-center gap-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/80",
                  collapsed && !mobile && "justify-center",
                )}
                data-testid="sidebar-user-menu"
                aria-label="User menu"
              >
                <Avatar className="size-7">
                  <AvatarFallback>{(user?.full_name || user?.email || "U").slice(0, 1).toUpperCase()}</AvatarFallback>
                </Avatar>
                {(!collapsed || mobile) && (
                  <div className="min-w-0 flex-1">
                    <div className="text-sm truncate">{user?.full_name || user?.email}</div>
                    <div className="text-[11px] text-slate-400 truncate">{user?.role}</div>
                  </div>
                )}
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" side="top" className="w-[240px]">
              <DropdownMenuLabel className="truncate">{user?.email}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => confirmBeforeAbandon(logout, "Sign out and leave unsaved workspace changes?")} data-testid="sidebar-logout">
                <LogOut className="size-4 mr-2" /> Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
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
      className="border-b border-slate-200 bg-white px-4 md:px-6"
    >
      <div className="flex min-h-11 items-end gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
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
                "mb-[-1px] inline-flex h-10 shrink-0 items-center border-b-2 px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                active
                  ? "border-cyan-500 bg-slate-50 text-slate-950"
                  : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-950",
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

function ContextualRibbon({ area, module, permissions }) {
  const keys = RIBBON_BY_MODULE[module?.key] || RIBBON_BY_AREA[area?.key] || ["dashboard"];
  const commands = keys.map((key) => COMMANDS[key]).filter(Boolean);
  return (
    <div
      data-testid="contextual-ribbon"
      data-area-key={area?.key}
      data-module-key={module?.key}
      className="border-b border-slate-200 bg-slate-50 px-4 py-2 md:px-6"
    >
      <div className="flex min-h-12 items-center gap-2 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <div className="mr-2 hidden shrink-0 text-[11px] font-semibold uppercase tracking-wide text-slate-500 sm:block">
          {module?.label || area?.label}
        </div>
        {commands.map((command) => (
          <CommandButton key={command.key} command={command} permissions={permissions} testPrefix="ribbon-command" />
        ))}
      </div>
    </div>
  );
}

function QuickAccessToolbar({ permissions, onOpenMobileNav }) {
  return (
    <div
      className="border-b border-slate-200 bg-white px-4 py-1.5 md:px-6"
      data-testid="quick-access-toolbar"
      aria-label="Quick access toolbar"
    >
      <div className="flex min-w-0 items-center gap-2">
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
        <div className="flex min-w-0 items-center gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden" data-testid="quick-access-actions">
          {QUICK_ACCESS_KEYS.map((key) => (
            <CommandButton key={key} command={COMMANDS[key]} permissions={permissions} compact testPrefix="qat-command" />
          ))}
        </div>
      </div>
    </div>
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
  const [devBannerHeight, setDevBannerHeight] = useState(0);
  const [selectedAreaKey, setSelectedAreaKey] = useState(null);
  const leaveTimerRef = useRef(null);
  const sidebarFocusWithinRef = useRef(false);
  const desktopSidebarRef = useRef(null);
  const devBannerRef = useRef(null);
  const location = useLocation();
  const navigate = useNavigate();
  const { devBypass, permissions, user } = useAuth();
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
    clearLeaveTimer();
    leaveTimerRef.current = window.setTimeout(() => {
      if (!sidebarFocusWithinRef.current) setDesktopSidebarExpanded(false);
      leaveTimerRef.current = null;
    }, SIDEBAR_LEAVE_DELAY_MS);
  };

  useEffect(() => () => clearLeaveTimer(), []);

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
  const desktopSidebarWidth = desktopSidebarExpanded
    ? DESKTOP_SIDEBAR_EXPANDED_WIDTH
    : DESKTOP_SIDEBAR_COLLAPSED_WIDTH;

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
          data-expanded={desktopSidebarExpanded ? "true" : "false"}
          data-sidebar-width={desktopSidebarWidth}
          onMouseEnter={expandDesktopSidebar}
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
            collapsed={!desktopSidebarExpanded}
            selectedAreaKey={selectedArea.key}
            onSelectArea={selectArea}
          />
        </aside>

        <div
          className="min-w-0 transition-[padding-left] duration-150 ease-out lg:pl-[var(--app-shell-sidebar-width)]"
          style={{ "--app-shell-sidebar-width": `${desktopSidebarWidth}px` }}
          data-testid="app-shell-main-region"
          data-sidebar-width={desktopSidebarWidth}
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
              />
            </SheetContent>
          </Sheet>
          <header className="sticky top-0 z-30 bg-white shadow-sm" data-testid="app-shell-topbar">
            <ModuleTabs area={selectedArea} permissions={permissions} user={user} />
            <ContextualRibbon area={selectedArea} module={activeModule} permissions={permissions} />
            <QuickAccessToolbar permissions={permissions} onOpenMobileNav={() => setMobileOpen(true)} />
          </header>

          <ShellPageHeading area={selectedArea} module={activeModule} />
          <main className="px-4 md:px-6 py-5 pb-24 max-w-[1400px]" data-testid="app-shell-content" data-active-path={location.pathname}>
            <Outlet />
          </main>
          <div className="h-16 md:h-14" data-testid="workspace-dock-reserved-space" aria-hidden="true" />
          <WorkspaceDock sidebarCollapsed={!desktopSidebarExpanded} />
          <AssistantLauncher />
        </div>
      </div>
    </div>
  );
}
