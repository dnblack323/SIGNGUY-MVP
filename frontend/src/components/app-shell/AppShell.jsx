import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Bot,
  Building2,
  CalendarDays,
  CheckCircle2,
  CircleHelp,
  DollarSign,
  FileText,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  ShieldAlert,
  ShoppingBag,
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
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  activeModuleForPath,
  filterNavItemsByPermissions,
  findAreaForPath,
  firstAvailableModule,
  itemMatchesPath,
  PRIMARY_NAV_AREAS,
} from "@/lib/navigation";
import NotificationBell from "@/components/notifications/NotificationBell";

function moduleNavLimit(width) {
  if (!width) return 5;
  if (width < 380) return 2;
  if (width < 560) return 3;
  if (width < 760) return 4;
  if (width < 960) return 5;
  return 7;
}

function splitModuleNav(items, activeKey, limit) {
  if (items.length <= limit) return { visible: items, overflow: [] };
  const visible = items.slice(0, Math.max(1, limit));
  const overflow = items.slice(visible.length);
  const activeInOverflow = overflow.find((item) => item.key === activeKey);
  if (!activeInOverflow) return { visible, overflow };
  const swapped = visible[visible.length - 1];
  return {
    visible: [...visible.slice(0, -1), activeInOverflow],
    overflow: [swapped, ...overflow.filter((item) => item.key !== activeKey)],
  };
}

function PrimaryCategoryButton({ area, active, collapsed, onSelect }) {
  const Icon = area.icon;
  const label = area.shortLabel || area.label;
  const button = (
    <button
      type="button"
      data-testid={area.testId}
      aria-label={area.label}
      aria-current={active ? "page" : undefined}
      data-active={active ? "true" : "false"}
      onClick={() => onSelect(area)}
      className={cn(
        "h-10 rounded-lg flex items-center gap-3 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/80",
        collapsed ? "w-10 justify-center px-0" : "w-full px-3",
        active ? "bg-white/10 text-white shadow-inner" : "text-slate-300 hover:bg-white/10 hover:text-white",
      )}
    >
      <Icon className={cn("size-4 shrink-0", area.accent)} aria-hidden="true" />
      {!collapsed && <span className="truncate">{label}</span>}
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

function SidebarInner({ collapsed, setCollapsed, selectedAreaKey, onSelectArea, onNavigate, mobile = false }) {
  const { tenant, user, logout } = useAuth();
  return (
    <TooltipProvider delayDuration={200}>
      <div
        className="flex h-full flex-col relative bg-slate-950 text-slate-100"
        data-testid="app-shell-sidebar"
        data-collapsed={collapsed ? "true" : "false"}
      >
        <div className={cn("border-b border-white/10", collapsed && !mobile ? "px-2 py-3" : "px-4 py-4")}>
          <div className={cn("flex items-center gap-2", collapsed && !mobile && "justify-center")}>
            <div className="grid size-9 place-items-center rounded-lg bg-cyan-400/15 text-cyan-200 ring-1 ring-cyan-300/20">
              <Building2 className="size-4" aria-hidden="true" />
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

        {!mobile && (
          <div className={cn("px-2 py-2", collapsed && "flex justify-center")}>
            <Button
              type="button"
              size="sm"
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              data-testid="sidebar-collapse-toggle"
              onClick={() => setCollapsed((value) => !value)}
              className={cn(
                "h-9 border border-white/10 bg-white/5 text-slate-200 hover:bg-white/10 hover:text-white",
                collapsed ? "w-10 px-0" : "w-full justify-start gap-2",
              )}
            >
              {collapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
              {!collapsed && <span>Collapse</span>}
            </Button>
          </div>
        )}

        <nav className="flex-1 px-2 py-2 space-y-1 overflow-hidden" data-testid="primary-sidebar-nav">
          {PRIMARY_NAV_AREAS.map((area) => (
            <PrimaryCategoryButton
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

        <div className="border-t border-white/10 px-2 py-2 space-y-1">
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
              <Link to="/help/docs"><CircleHelp className="size-4" /></Link>
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
              <DropdownMenuItem onClick={logout} data-testid="sidebar-logout">
                <LogOut className="size-4 mr-2" /> Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </TooltipProvider>
  );
}

function CategoryTopNavigation({ area, permissions, user }) {
  const location = useLocation();
  const navRef = useRef(null);
  const [width, setWidth] = useState(typeof window === "undefined" ? 0 : window.innerWidth);
  const visibleItems = filterNavItemsByPermissions(area?.moduleNav || [], permissions, user);
  const activeItem = activeModuleForPath(area, location.pathname, permissions, user);
  const limit = moduleNavLimit(width);
  const { visible, overflow } = splitModuleNav(visibleItems, activeItem?.key, limit);

  useEffect(() => {
    if (!navRef.current || typeof window === "undefined") return undefined;
    const updateWidth = () => setWidth(navRef.current?.getBoundingClientRect().width || window.innerWidth);
    updateWidth();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", updateWidth);
      return () => window.removeEventListener("resize", updateWidth);
    }
    const observer = new ResizeObserver(updateWidth);
    observer.observe(navRef.current);
    return () => observer.disconnect();
  }, []);

  if (!area || area.home || !visibleItems.length) return null;

  return (
    <div
      ref={navRef}
      data-testid="category-top-nav"
      data-category-key={area.key}
      className="border-b bg-white px-4 py-2 md:px-6"
    >
      <div className="flex max-w-full items-center gap-1 overflow-hidden">
        <div className="mr-2 hidden shrink-0 text-[11px] font-semibold uppercase tracking-wide text-slate-500 sm:block">
          {area.shortLabel || area.label}
        </div>
        {visible.map((item) => {
          const active = itemMatchesPath(item, location.pathname);
          return (
            <Link
              key={item.key}
              to={item.to}
              data-testid={item.testId}
              aria-current={active ? "page" : undefined}
              data-active={active ? "true" : "false"}
              className={cn(
                "h-8 shrink-0 rounded-md px-3 text-sm inline-flex items-center whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                active ? "bg-slate-100 text-slate-950 font-medium" : "text-slate-600 hover:bg-slate-50 hover:text-slate-950",
              )}
            >
              {item.label}
            </Link>
          );
        })}
        {overflow.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 shrink-0 px-3"
                aria-label={`${area.label} more modules`}
                data-testid="category-nav-more"
              >
                More
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" data-testid="category-nav-more-menu">
              <DropdownMenuLabel>{area.shortLabel || area.label}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {overflow.map((item) => (
                <DropdownMenuItem key={item.key} asChild>
                  <Link
                    to={item.to}
                    data-testid={`${item.testId}-overflow`}
                    aria-current={itemMatchesPath(item, location.pathname) ? "page" : undefined}
                  >
                    {item.label}
                  </Link>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
    </div>
  );
}

function QuickAccessAction({ to, label, icon: Icon, permission, permissions }) {
  if (permission && !permissions?.includes(permission)) return null;
  return (
    <Button
      asChild
      variant="ghost"
      size="sm"
      className="h-8 shrink-0 px-2 text-xs text-slate-700 hover:bg-slate-100 hover:text-slate-950 xl:px-2.5"
      data-testid={`quick-access-${label.toLowerCase().replaceAll(" ", "-")}`}
    >
      <Link to={to} aria-label={label}>
        <Icon className="size-3.5" aria-hidden="true" />
        <span className="hidden xl:inline">{label}</span>
      </Link>
    </Button>
  );
}

function QuickAccessToolbar({ permissions, onOpenMobileNav }) {
  const actions = [
    { to: "/customers", label: "New Customer", icon: UserPlus, permission: "customer:write" },
    { to: "/quotes", label: "New Quote", icon: FileText, permission: "quote:write" },
    { to: "/orders", label: "New Order", icon: ShoppingBag, permission: "order:write" },
    { to: "/pricing-calculator", label: "Pricing", icon: DollarSign, permission: "pricing:read" },
    { to: "/team/tasks", label: "New Task", icon: CheckCircle2, permission: "task:read" },
    { to: "/shop-schedule", label: "Calendar", icon: CalendarDays, permission: "schedule:read" },
    { to: "/studio/assistant", label: "Assistant", icon: Bot, permission: "ai_assistant:use" },
  ];

  return (
    <div
      className="border-b bg-white px-4 py-2 md:px-6"
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
        <div className="relative min-w-[180px] flex-1 max-w-md">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            aria-label="Global search"
            placeholder="Search orders, customers, quotes..."
            data-testid="quick-access-global-search"
            className="h-8 w-full rounded-md border border-slate-200 bg-slate-50 pl-8 pr-2 text-sm outline-none transition focus:border-cyan-500 focus:bg-white focus:ring-2 focus:ring-cyan-100"
          />
        </div>
        <div
          className="flex min-w-0 items-center gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          data-testid="quick-access-actions"
        >
          {actions.map((action) => (
            <QuickAccessAction key={action.label} {...action} permissions={permissions} />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [selectedAreaKey, setSelectedAreaKey] = useState(null);
  const location = useLocation();
  const navigate = useNavigate();
  const { devBypass, permissions, user } = useAuth();
  const pathArea = useMemo(() => findAreaForPath(location.pathname), [location.pathname]);
  const selectedArea = PRIMARY_NAV_AREAS.find((area) => area.key === (selectedAreaKey || pathArea.key)) || pathArea;

  useEffect(() => {
    setSelectedAreaKey(pathArea.key);
  }, [pathArea.key]);

  const selectArea = (area) => {
    setSelectedAreaKey(area.key);
    if (area.home) {
      navigate(area.to);
      return;
    }
    const target = firstAvailableModule(area, permissions, user);
    if (target) navigate(target.to);
  };

  return (
    <div className="min-h-dvh bg-background text-foreground">
      {devBypass && (
        <div className="w-full bg-amber-50 border-b border-amber-200 text-amber-900 text-xs px-4 py-1.5 flex items-center justify-center gap-2" data-testid="dev-bypass-banner">
          <ShieldAlert className="size-3.5" />
          <span><span className="font-semibold">Auth bypass ON</span> &middot; you're browsing as Dev Shop owner. Set <span className="mono">AUTH_DEV_BYPASS=false</span> before deploying.</span>
        </div>
      )}
      <div className={cn("grid grid-cols-1", sidebarCollapsed ? "lg:grid-cols-[76px_1fr]" : "lg:grid-cols-[260px_1fr]")}>
        <aside className="hidden lg:flex flex-col border-r border-slate-900 bg-slate-950 h-dvh sticky top-0 z-20">
          <SidebarInner
            collapsed={sidebarCollapsed}
            setCollapsed={setSidebarCollapsed}
            selectedAreaKey={selectedArea.key}
            onSelectArea={selectArea}
          />
        </aside>

        <div className="min-w-0">
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetContent side="left" className="w-[280px] border-slate-900 bg-slate-950 p-0">
              <SidebarInner
                collapsed={false}
                setCollapsed={setSidebarCollapsed}
                selectedAreaKey={selectedArea.key}
                onSelectArea={selectArea}
                onNavigate={() => setMobileOpen(false)}
                mobile
              />
            </SheetContent>
          </Sheet>
          <header className="sticky top-0 z-30 bg-white shadow-sm" data-testid="app-shell-topbar">
            <QuickAccessToolbar permissions={permissions} onOpenMobileNav={() => setMobileOpen(true)} />
            <CategoryTopNavigation area={selectedArea} permissions={permissions} user={user} />
          </header>

          <main className="px-4 md:px-6 py-5 max-w-[1400px]" data-testid="app-shell-content" data-active-path={location.pathname}>
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
